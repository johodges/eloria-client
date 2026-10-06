extends SceneTree
## Run with --headless --script res://tests/integration/torso_body_cover.gd.

var failures := 0

func _init() -> void:
	call_deferred("run")

func expect(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	var paths := DirAccess.get_files_at("res://assets/actors/native/races")
	var races := 0
	var race_names := PackedStringArray()
	for path: String in paths:
		if not path.ends_with(".glb"):
			continue
		var scene := load("res://assets/actors/native/races/" + path) as PackedScene
		var body := scene.instantiate()
		root.add_child(body)
		var skeleton := body.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
		var fit := skeleton.get_bone_global_rest(skeleton.find_bone("Head")).origin.y / 1.5684900288581848
		var removed := 0
		var retained := 0
		var bridge_surfaces := 0
		for node: Node in body.find_children("*", "MeshInstance3D", true, false):
			var mesh := node as MeshInstance3D
			if mesh.skin == null:
				continue
			var original := mesh.mesh
			var transform := skeleton.global_transform.affine_inverse() * mesh.global_transform
			TorsoBodyCover.apply(mesh, true, transform, fit)
			var covered_mesh := mesh.mesh
			expect(mesh.mesh != original, path + " has a private covered mesh")
			expect(mesh.mesh.get_surface_count() == original.get_surface_count(), "surface numbering survives")
			for surface: int in range(original.get_surface_count()):
				var before := original.surface_get_arrays(surface)
				var after := mesh.mesh.surface_get_arrays(surface)
				var material := original.surface_get_material(surface)
				var bridge_surface := (material != null
					and material.resource_name == "Shared neck bridge")
				if mesh.name.to_lower() in ["body", "char1", "mesh_node"] and bridge_surface:
					bridge_surfaces += 1
				expect(before[Mesh.ARRAY_VERTEX] == after[Mesh.ARRAY_VERTEX], "positions stay intact")
				expect(before[Mesh.ARRAY_BONES] == after[Mesh.ARRAY_BONES], "bones stay intact")
				expect(before[Mesh.ARRAY_WEIGHTS] == after[Mesh.ARRAY_WEIGHTS], "weights stay intact")
				expect(original.surface_get_material(surface) == mesh.mesh.surface_get_material(surface),
					"surface material stays intact")
				var vertices: PackedVector3Array = before[Mesh.ARRAY_VERTEX]
				var source: PackedInt32Array = before[Mesh.ARRAY_INDEX]
				if source.is_empty():
					for index: int in range(vertices.size()):
						source.append(index)
				var expected := PackedInt32Array()
				for i: int in range(0, source.size(), 3):
					var center := (transform * ((vertices[source[i]] + vertices[source[i + 1]]
						+ vertices[source[i + 2]]) / 3.0)) / fit
					var covered := independently_covered(mesh.name.to_lower(), center)
					if independently_retained(mesh, before, source, i, center,
							transform, fit, bridge_surface, covered):
						expected.append_array(source.slice(i, i + 3))
				if expected.is_empty():
					expected = PackedInt32Array([0, 0, 0])
				var indices: PackedInt32Array = after[Mesh.ARRAY_INDEX]
				expect(indices == expected,
					path + " " + str(mesh.name) + " surface " + str(surface)
					+ " retains the independently reconstructed face set")
				removed += source.size() - indices.size()
				for i: int in range(0, indices.size(), 3):
					if indices[i] == indices[i + 1]:
						continue
					retained += 1
			TorsoBodyCover.apply(mesh, true, transform, fit)
			expect(mesh.mesh == covered_mesh, "identical coverage reuses its cached mesh")
			if path.begins_with("luminous_") \
					and mesh.name.to_lower() in ["body", "char1", "mesh_node"]:
				var original_faces := _face_count(original)
				TorsoBodyCover.apply(mesh, true, transform, fit, [], false, {}, true)
				var masked_faces := _face_count(mesh.mesh)
				# The 2026-10-05 Human bodies close the collar: no detached shell is
				# left to strip, only the narrow apron under the wardrobe neckline.
				expect(original_faces - masked_faces > 0,
					path + " wardrobe neckline removes the narrow apron: %d faces"
					% (original_faces - masked_faces))
				for surface: int in range(original.get_surface_count()):
					var before := original.surface_get_arrays(surface)
					var after := mesh.mesh.surface_get_arrays(surface)
					var material := original.surface_get_material(surface)
					var bridge_surface := (material != null
						and material.resource_name == "Shared neck bridge")
					var vertices: PackedVector3Array = before[Mesh.ARRAY_VERTEX]
					var source: PackedInt32Array = before[Mesh.ARRAY_INDEX]
					if source.is_empty():
						for source_index: int in range(vertices.size()):
							source.append(source_index)
					var detached_neck_vertices := independently_detached_neck_vertices(
						source, vertices, transform, fit)
					var detached_faces := 0
					for source_index: int in range(0, source.size(), 3):
						if (detached_neck_vertices.has(source[source_index])
								or detached_neck_vertices.has(source[source_index + 1])
								or detached_neck_vertices.has(source[source_index + 2])):
							detached_faces += 1
					var expected_detached := 0
					expect(detached_faces == expected_detached,
						path + " identifies exactly %d detached collar faces, got %d"
						% [expected_detached, detached_faces])
					var expected := PackedInt32Array()
					for source_index: int in range(0, source.size(), 3):
						var center := (transform * ((vertices[source[source_index]]
							+ vertices[source[source_index + 1]]
							+ vertices[source[source_index + 2]]) / 3.0)) / fit
						var covered := independently_covered(
							mesh.name.to_lower(), center, true)
						if independently_retained(mesh, before, source, source_index,
								center, transform, fit, bridge_surface, covered, true,
								detached_neck_vertices):
							expected.append_array(source.slice(source_index, source_index + 3))
					var expected_vertices := independently_inset_neckline_rim(
						vertices, expected, transform, fit)
					expect((after[Mesh.ARRAY_VERTEX] as PackedVector3Array) == expected_vertices,
						path + " insets only the independently reconstructed welded rim")
					var moved := 0
					for vertex: int in range(vertices.size()):
						if vertices[vertex] == expected_vertices[vertex]:
							continue
						moved += 1
						var before_point := (transform * vertices[vertex]) / fit
						var after_point := (transform * expected_vertices[vertex]) / fit
						expect(is_equal_approx(after_point.y,
							independently_wardrobe_neckline_y(before_point))
							and is_equal_approx(after_point.x,
								before_point.x * TorsoBodyCover.NECK_RIM_INSET)
							and is_equal_approx(after_point.z,
								before_point.z * TorsoBodyCover.NECK_RIM_INSET),
							path + " inset rim follows the shaped neckline")
					expect(moved > 0, path + " insets a non-empty welded rim")
					expect(before[Mesh.ARRAY_TEX_UV] == after[Mesh.ARRAY_TEX_UV],
						path + " wardrobe neckline preserves UVs")
					expect(before[Mesh.ARRAY_BONES] == after[Mesh.ARRAY_BONES],
						path + " wardrobe neckline preserves bone indices")
					expect(before[Mesh.ARRAY_WEIGHTS] == after[Mesh.ARRAY_WEIGHTS],
						path + " wardrobe neckline preserves skin weights")
					if expected.is_empty():
						expected = PackedInt32Array([0, 0, 0])
					expect((after[Mesh.ARRAY_INDEX] as PackedInt32Array) == expected,
						path + " wardrobe neckline retains the independently reconstructed faces")
			TorsoBodyCover.apply(mesh, false, transform, fit)
			expect(mesh.mesh == original, "unequip restores the exact body resource")
		var expected_bridge_surfaces := 0 if path.begins_with("luminous_") else 2
		expect(bridge_surfaces == expected_bridge_surfaces,
			path + " imports the authored Shared neck bridge surface contract")
		expect(removed > 100, path + " removes covered clothing")
		expect(retained > 100, path + " preserves uncovered body")
		races += 1
		race_names.append(path.get_basename())
		body.free()
	print("TORSO BODY COVER: %d races, %d failures" % [races, failures])
	expect(races == 16, "all races tested")
	# Exercise the actual attachment path, including replacement detection and
	# three equip/unequip cycles. Checking cut() alone would miss a node-name or
	# wardrobe-refresh integration failure.
	var models: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/models.json"))["models"]
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/equipment.json"))
	for race: String in race_names:
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var config: Dictionary = models[race]
		var animations: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config["animationMap"]))
		var errors := actor.configure({"actor_id": 991, "x": 0, "y": 0, "rotation": 0,
			"kind": 1, "name": race, "appearance": {}, "equipment_visuals": {}},
			CoordinateAdapter.new({"walkingHeight": 0.0}), config, animations, equipment)
		expect(errors.is_empty(), race + " actor configures: " + str(errors))
		for visual: int in [192, 228, 187]:
			actor.apply_equipment_visuals({5: visual})
			var covered := 0
			for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
				var mesh := node as MeshInstance3D
				if mesh.name.to_lower() in ["hair", "eyes"]:
					expect(not mesh.has_meta("uncovered_body_mesh"), "coverage leaves hair and eyes alone")
				if mesh.has_meta("uncovered_body_mesh") and mesh.mesh != mesh.get_meta("uncovered_body_mesh"):
					covered += 1
			expect(covered > 0, race + " generated armour activates body replacement")
			actor.apply_equipment_visuals({})
			for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
				var mesh := node as MeshInstance3D
				if mesh.has_meta("uncovered_body_mesh"):
					expect(mesh.mesh == mesh.get_meta("uncovered_body_mesh"), "actor unequip restores body")
		actor.free()
	print("TORSO EQUIP/UNEQUIP: %d failures" % failures)
	quit(1 if failures else 0)

func independently_covered(instance_name: String, point: Vector3,
		mask_to_wardrobe_neckline: bool = false) -> bool:
	if (mask_to_wardrobe_neckline
			and instance_name in ["body", "char1", "mesh_node"]):
		var collar := (point.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y
			and point.y < TorsoBodyCover.HIGH
			and absf(point.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH)
		var front_apron := (point.y > TorsoBodyCover.FRONT_APRON_MIN_Y
			and point.y < TorsoBodyCover.FRONT_APRON_MAX_Y
			and absf(point.x) < TorsoBodyCover.FRONT_APRON_HALF_WIDTH
			and point.z > TorsoBodyCover.FRONT_APRON_MIN_Z)
		return collar and not front_apron
	var covered := (point.y > .95 and point.y < 1.535 and absf(point.x) < .665)
	if instance_name == "wardrobe_shirt":
		covered = covered or (point.y > 1.40 and point.y < 1.65 and absf(point.x) < .20)
	return covered

func independently_retained(instance: MeshInstance3D, arrays: Array,
		ids: PackedInt32Array, start: int, center: Vector3,
		to_rig: Transform3D, fit: float, bridge_surface: bool, covered: bool,
		mask_to_wardrobe_neckline: bool = false,
		detached_neck_vertices: Dictionary = {}) -> bool:
	if instance.name.to_lower() not in ["body", "char1", "mesh_node"] or instance.skin == null:
		return not covered
	if (mask_to_wardrobe_neckline
			and (detached_neck_vertices.has(ids[start])
				or detached_neck_vertices.has(ids[start + 1])
				or detached_neck_vertices.has(ids[start + 2]))):
		return false
	var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var stride: int = bones.size()/vertices.size()
	var all_corners_protected := true
	for corner: int in range(3):
		var corner_weight := 0.0
		for slot: int in range(stride):
			var offset := ids[start+corner]*stride+slot
			var bone_name := instance.skin.get_bind_name(bones[offset])
			if bone_name.is_empty():
				var skeleton := instance.get_node(instance.skeleton) as Skeleton3D
				bone_name = skeleton.get_bone_name(instance.skin.get_bind_bone(bones[offset]))
			if bone_name in [&"Head", &"neck_01"]:
				corner_weight += weights[offset]
		all_corners_protected = all_corners_protected and corner_weight > .5
	# Without a reviewed per-face profile, a fitted collar removes the complete
	# authoring bridge so no rear prong can cross the armour shell.
	if bridge_surface:
		return false
	var protected_face := all_corners_protected
	var neck_envelope := (covered
		and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y
		and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH)
	if neck_envelope:
		return protected_face
	return protected_face or not covered

func independently_wardrobe_neckline_y(point: Vector3) -> float:
	var front := smoothstep(-0.040, 0.010, point.z)
	var centre := 1.0 - smoothstep(0.015, 0.100, absf(point.x))
	return lerpf(1.462, 1.450, front * centre)

func independently_inset_neckline_rim(source_vertices: PackedVector3Array,
		kept: PackedInt32Array, to_rig: Transform3D,
		fit: float) -> PackedVector3Array:
	var vertices := source_vertices.duplicate()
	if kept.is_empty():
		return vertices
	var point_ids := {}
	var welded := PackedInt32Array()
	welded.resize(vertices.size())
	for vertex: int in range(vertices.size()):
		var point := (to_rig * vertices[vertex]) / fit
		var key := Vector3i(roundi(point.x * 100000.0), roundi(point.y * 100000.0),
			roundi(point.z * 100000.0))
		if not point_ids.has(key):
			point_ids[key] = point_ids.size()
		welded[vertex] = int(point_ids[key])
	var edge_counts := {}
	for index: int in range(0, kept.size(), 3):
		for corners: Vector2i in [
				Vector2i(kept[index], kept[index + 1]),
				Vector2i(kept[index + 1], kept[index + 2]),
				Vector2i(kept[index + 2], kept[index])]:
			var first := welded[corners.x]
			var second := welded[corners.y]
			var edge := Vector2i(mini(first, second), maxi(first, second))
			edge_counts[edge] = int(edge_counts.get(edge, 0)) + 1
	var boundary_points := {}
	for edge_value: Variant in edge_counts:
		if int(edge_counts[edge_value]) != 1:
			continue
		var edge := edge_value as Vector2i
		boundary_points[edge.x] = true
		boundary_points[edge.y] = true
	var from_rig := to_rig.affine_inverse()
	for vertex: int in range(vertices.size()):
		if not boundary_points.has(welded[vertex]):
			continue
		var point := (to_rig * vertices[vertex]) / fit
		if (point.y <= TorsoBodyCover.NECK_RIM_MIN_Y
				or point.y >= TorsoBodyCover.NECK_RIM_MAX_Y
				or absf(point.x) >= TorsoBodyCover.NECK_RIM_HALF_WIDTH
				or point.z <= TorsoBodyCover.NECK_RIM_MIN_Z
				or point.z >= TorsoBodyCover.NECK_RIM_MAX_Z):
			continue
		point.y = independently_wardrobe_neckline_y(point)
		point.x *= TorsoBodyCover.NECK_RIM_INSET
		point.z *= TorsoBodyCover.NECK_RIM_INSET
		vertices[vertex] = from_rig * (point * fit)
	return vertices

func independently_detached_neck_vertices(ids: PackedInt32Array,
		vertices: PackedVector3Array, to_rig: Transform3D, fit: float) -> Dictionary:
	var point_ids := {}
	var welded := PackedInt32Array()
	welded.resize(vertices.size())
	var rest_points := PackedVector3Array()
	for vertex: int in range(vertices.size()):
		var point := (to_rig * vertices[vertex]) / fit
		var key := Vector3i(roundi(point.x * 100000.0), roundi(point.y * 100000.0),
			roundi(point.z * 100000.0))
		if not point_ids.has(key):
			point_ids[key] = rest_points.size()
			rest_points.append(point)
		welded[vertex] = int(point_ids[key])
	var parents := PackedInt32Array()
	parents.resize(rest_points.size())
	for point_id: int in range(parents.size()):
		parents[point_id] = point_id
	for start: int in range(0, ids.size(), 3):
		var first_root := independent_component_root(parents, welded[ids[start]])
		for corner: int in range(1, 3):
			var other_root := independent_component_root(parents, welded[ids[start + corner]])
			if first_root != other_root:
				parents[other_root] = first_root
	var face_counts := {}
	for start: int in range(0, ids.size(), 3):
		var root := independent_component_root(parents, welded[ids[start]])
		face_counts[root] = int(face_counts.get(root, 0)) + 1
	var minima := {}
	var maxima := {}
	for point_id: int in range(rest_points.size()):
		var root := independent_component_root(parents, point_id)
		var point := rest_points[point_id]
		minima[root] = point if not minima.has(root) else (minima[root] as Vector3).min(point)
		maxima[root] = point if not maxima.has(root) else (maxima[root] as Vector3).max(point)
	var detached_roots := {}
	for root_value: Variant in face_counts:
		var root := int(root_value)
		var minimum := minima[root] as Vector3
		var maximum := maxima[root] as Vector3
		if (int(face_counts[root]) <= 128
				and minimum.y >= 1.460 and maximum.y <= 1.520
				and maxf(absf(minimum.x), absf(maximum.x)) <= 0.100
				and minimum.z >= -0.110 and maximum.z <= 0.040):
			detached_roots[root] = true
	var result := {}
	for vertex: int in range(vertices.size()):
		if detached_roots.has(independent_component_root(parents, welded[vertex])):
			result[vertex] = true
	return result

func independent_component_root(parents: PackedInt32Array, point_id: int) -> int:
	var root := point_id
	while parents[root] != root:
		root = parents[root]
	return root

func _face_count(mesh: Mesh) -> int:
	var count := 0
	for surface: int in range(mesh.get_surface_count()):
		var indices := mesh.surface_get_arrays(surface)[Mesh.ARRAY_INDEX] as PackedInt32Array
		if indices.size() == 3 and indices[0] == indices[1]:
			continue
		count += indices.size() / 3
	return count
