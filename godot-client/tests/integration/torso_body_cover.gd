extends SceneTree
## Run with --headless --script res://tests/integration/torso_body_cover.gd.

var failures := 0

## The high-collar torsos that floated every bridged race's head on
## 2026-10-06: two starter kits (Studded Jack, Acolyte Tunic) plus the Bark
## Jerkin and the Furtrim Coat.
const HIGH_COLLAR_TORSOS := [209, 222, 184, 189]
## Measured ceiling, with about 10% headroom, on the "Shared neck bridge" faces
## a high collar may remove from each rig: the unweighted chest rows, the
## flared rows behind and beside the neck and the cut's spikes and loose
## shards (and Orun's 88 reviewed rows). Measured 2026-10-06: 398 to 440 per
## generic rig, 114 for Orun. Dropping the whole bridge removed 809 to 1,754 faces per bridged rig
## and left the head floating.
## These are measurements of the current race GLBs, not design limits: after
## ANY regeneration of a race body (the race rebase onto the new Human body is
## in progress on feature/race-rebase-2026-10-06) re-measure every ceiling
## from this test's own "removed %d faces" output before trusting a failure
## or a pass, and keep about 10% headroom.
const BRIDGE_REMOVAL_CEILING := {
	"glasswarden_female": 470, "glasswarden_male": 440,
	"greyhaven_female": 485, "greyhaven_male": 475,
	"luminous_female": 0, "luminous_male": 0,
	"mycelari_female": 485, "mycelari_male": 475,
	"orun_female": 485, "orun_male": 130,
	"ssarathi_female": 470, "ssarathi_male": 440,
	"stoneborn_female": 485, "stoneborn_male": 475,
	"votary_female": 485, "votary_male": 475,
}
## Spikes and loose shards the bridge cut may drop per mesh beyond the
## per-face rule (measured up to 48 on 2026-10-06; re-measure with the
## ceilings above after a race GLB regeneration).
const BRIDGE_DEBRIS_CEILING := 64
## The bridged rig whose wardrobe-only neckline must leave the visible neck
## in place (develop still marks 5:189/5:209/5:216/5:225 wardrobeOnly).
const WARDROBE_BRIDGED_RIG := "glasswarden_male.glb"
## The neck between the jaw and every generated collar's rear rim.
const ATTACHED_NECK_BAND := Vector2(1.52, 1.57)

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
			var bridged_mesh := false
			for surface: int in range(original.get_surface_count()):
				var surface_material := original.surface_get_material(surface)
				bridged_mesh = bridged_mesh or (surface_material != null
					and surface_material.resource_name == "Shared neck bridge")
			var bridge_debris := 0
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
				expect(independently_hem_moves_only(before[Mesh.ARRAY_VERTEX],
					after[Mesh.ARRAY_VERTEX], transform, fit, bridged_mesh),
					path + " " + str(mesh.name) + " surface " + str(surface)
					+ " keeps positions apart from the levelled neck-bridge hems")
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
				var debris := independently_dropped_faces(expected, indices)
				expect(debris == 0 or (debris > 0 and bridge_surface),
					path + " " + str(mesh.name) + " surface " + str(surface)
					+ " retains the independently reconstructed face set, less only"
					+ " neck-bridge cut debris (%d)" % debris)
				bridge_debris += maxi(debris, 0)
				removed += source.size() - indices.size()
				for i: int in range(0, indices.size(), 3):
					if indices[i] == indices[i + 1]:
						continue
					retained += 1
			expect(bridge_debris <= BRIDGE_DEBRIS_CEILING,
				path + " " + str(mesh.name) + " drops %d neck-bridge debris faces, ceiling %d"
				% [bridge_debris, BRIDGE_DEBRIS_CEILING])
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
			if path == WARDROBE_BRIDGED_RIG \
					and mesh.name.to_lower() in ["body", "char1", "mesh_node"]:
				verify_wardrobe_keeps_bridge(mesh, original, transform, fit, path)
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
		for visual: int in HIGH_COLLAR_TORSOS:
			actor.apply_equipment_visuals({5: visual})
			verify_attached_neck(actor, race, visual)
		actor.apply_equipment_visuals({})
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
	var lowest_corner_weight := 1.0
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
		lowest_corner_weight = minf(lowest_corner_weight, corner_weight)
	var protected_face := all_corners_protected
	var neck_envelope := (covered
		and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y
		and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH)
	# The shared bridge is the visible neck. Under armour its flared rows go:
	# below 1.53 m behind the canonical neck_01 (0, 1.452, -.051) -> Head
	# (0, 1.568, .011) axis, and beside it below a line falling to 1.49 m at
	# 60 degrees from the front. In front of the axis the rest is the throat
	# inside an open collar and stays while every corner keeps a quarter of
	# its Head/neck_01 weight; behind it the rest takes the whole-face test.
	if (bridge_surface and neck_envelope and not mask_to_wardrobe_neckline
			and center.y < independent_bridge_trim_y(center)):
		return false
	var axis_z := lerpf(-.051, .011, (center.y - 1.452) / (1.568 - 1.452))
	if bridge_surface and neck_envelope and center.z >= axis_z:
		return lowest_corner_weight > .25
	if neck_envelope:
		return protected_face
	return protected_face or not covered

## Regression for heads floating above a high collar. The rig's own rest
## skeleton supplies the neck axis, so the check does not trust the constants
## it guards. Five contracts: the bridge loses no more than its measured
## ceiling; every 30 degree sector keeps at least half of the neck surface just
## below the jaw; no flared rear bridge row survives to hang outside the
## collar, which is what the old whole-bridge drop was preventing; and the
## cut leaves no spike (a bridge face hanging by one edge, the saw-tooth in an
## open front) and no loose bridge shard. Orun's reviewed profile owns its cut.
func verify_attached_neck(actor: ReplicatedActor3D, race: String, visual: int) -> void:
	var label := "%s with torso 5:%d" % [race, visual]
	var skeleton := actor.get_skeleton()
	var fit := actor.rig_fit_scale()
	var neck := skeleton.get_bone_global_rest(skeleton.find_bone("neck_01")).origin / fit
	var head := skeleton.get_bone_global_rest(skeleton.find_bone("Head")).origin / fit
	expect(neck.distance_to(Vector3(0., 1.452, -.051)) < .002
		and head.distance_to(Vector3(0., 1.568, .011)) < .002,
		race + " keeps the canonical neck axis the rear bridge trim assumes")
	var band_before: Array[int] = []
	var band_after: Array[int] = []
	for sector: int in range(12):
		band_before.append(0)
		band_after.append(0)
	var removed := 0
	var flared_rear_kept := 0
	var bodies := 0
	for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		if mesh.name.to_lower() not in ["body", "char1", "mesh_node"] \
				or not mesh.has_meta("uncovered_body_mesh"):
			continue
		bodies += 1
		var original := mesh.get_meta("uncovered_body_mesh") as Mesh
		var transform := skeleton.global_transform.affine_inverse() * mesh.global_transform
		for surface: int in range(original.get_surface_count()):
			var material := original.surface_get_material(surface)
			var bridge_surface := (material != null
				and material.resource_name == "Shared neck bridge")
			var profiled := race == "orun_male" and surface == 3
			for pass_index: int in range(2):
				var arrays := (original if pass_index == 0 else mesh.mesh).surface_get_arrays(surface)
				var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
				var ids: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
				if ids.is_empty():
					for index: int in range(vertices.size()):
						ids.append(index)
				for start: int in range(0, ids.size(), 3):
					if ids[start] == ids[start + 1] and ids[start] == ids[start + 2]:
						continue
					if bridge_surface:
						removed += 1 if pass_index == 0 else -1
					var center := (transform * ((vertices[ids[start]] + vertices[ids[start + 1]]
						+ vertices[ids[start + 2]]) / 3.0)) / fit
					var axis := neck.lerp(head, (center.y - neck.y) / (head.y - neck.y))
					var radial := Vector2(center.x - axis.x, center.z - axis.z)
					if pass_index == 1 and bridge_surface and not profiled \
							and center.y < 1.528 and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y \
							and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH \
							and center.z < axis.z - .002:
						flared_rear_kept += 1
					if center.y <= ATTACHED_NECK_BAND.x or center.y >= ATTACHED_NECK_BAND.y \
							or radial.length() <= .035 or radial.length() >= .11:
						continue
					var sector := int(floor(fposmod(atan2(radial.x, radial.y), TAU) / TAU * 12.0)) % 12
					if pass_index == 0:
						band_before[sector] += 1
					else:
						band_after[sector] += 1
	expect(bodies > 0, label + " cuts a body mesh under the collar")
	expect(removed <= int(BRIDGE_REMOVAL_CEILING.get(race, 0)),
		label + " keeps the shared neck bridge: removed %d faces, ceiling %d"
		% [removed, int(BRIDGE_REMOVAL_CEILING.get(race, 0))])
	for sector: int in range(12):
		expect(band_after[sector] * 2 >= band_before[sector],
			label + " keeps its neck attached in sector %d: %d of %d faces"
			% [sector, band_after[sector], band_before[sector]])
	expect(flared_rear_kept == 0,
		label + " trims every flared rear bridge row: %d kept" % flared_rear_kept)
	if race != "orun_male":
		var debris := independent_bridge_debris(actor)
		expect(debris.x == 0, label + " leaves no neck-bridge spike: %d" % debris.x)
		expect(debris.y == 0, label + " leaves no loose neck-bridge shard: %d faces" % debris.y)

## Bridge faces of the covered body with two open edges (x) and faces in
## components made only of bridge faces (y), welded by rest position across
## every surface: the spikes and loose shards a cut through the bridge leaves.
func independent_bridge_debris(actor: ReplicatedActor3D) -> Vector2i:
	var skeleton := actor.get_skeleton()
	var fit := actor.rig_fit_scale()
	var result := Vector2i.ZERO
	for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		if mesh.name.to_lower() not in ["body", "char1", "mesh_node"] \
				or not mesh.has_meta("uncovered_body_mesh"):
			continue
		var transform := skeleton.global_transform.affine_inverse() * mesh.global_transform
		var point_ids := {}
		var faces: Array[PackedInt32Array] = []
		var bridge_faces: Array[bool] = []
		for surface: int in range(mesh.mesh.get_surface_count()):
			var material := mesh.mesh.surface_get_material(surface)
			var bridge := material != null and material.resource_name == "Shared neck bridge"
			var arrays := mesh.mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			var ids: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
			for start: int in range(0, ids.size(), 3):
				if ids[start] == ids[start + 1] and ids[start] == ids[start + 2]:
					continue
				var corners := PackedInt32Array()
				for corner: int in range(3):
					var point := (transform * vertices[ids[start + corner]]) / fit
					var key := Vector3i(roundi(point.x * 100000.0), roundi(point.y * 100000.0),
						roundi(point.z * 100000.0))
					if not point_ids.has(key):
						point_ids[key] = point_ids.size()
					corners.append(int(point_ids[key]))
				faces.append(corners)
				bridge_faces.append(bridge)
		var edge_counts := {}
		var edge_faces := {}
		for face: int in range(faces.size()):
			for corner: int in range(3):
				var a := faces[face][corner]
				var b := faces[face][(corner + 1) % 3]
				var edge := Vector2i(mini(a, b), maxi(a, b))
				edge_counts[edge] = int(edge_counts.get(edge, 0)) + 1
				if not edge_faces.has(edge):
					edge_faces[edge] = []
				(edge_faces[edge] as Array).append(face)
		var component := PackedInt32Array()
		component.resize(faces.size())
		component.fill(-1)
		for first: int in range(faces.size()):
			if component[first] >= 0:
				continue
			var members: Array[int] = [first]
			component[first] = first
			var only_bridge := true
			var cursor := 0
			while cursor < members.size():
				var face := members[cursor]
				cursor += 1
				only_bridge = only_bridge and bridge_faces[face]
				for corner: int in range(3):
					var a := faces[face][corner]
					var b := faces[face][(corner + 1) % 3]
					for other: Variant in edge_faces[Vector2i(mini(a, b), maxi(a, b))]:
						if component[int(other)] < 0:
							component[int(other)] = first
							members.append(int(other))
			if only_bridge:
				result.y += members.size()
		for face: int in range(faces.size()):
			if not bridge_faces[face]:
				continue
			var open_edges := 0
			for corner: int in range(3):
				var a := faces[face][corner]
				var b := faces[face][(corner + 1) % 3]
				if int(edge_counts[Vector2i(mini(a, b), maxi(a, b))]) == 1:
					open_edges += 1
			if open_edges >= 2:
				result.x += 1
	return result

## A wardrobe-only neckline (develop's 5:189/5:209/5:216/5:225) tucks the open
## rim behind the fitted shirt. On a bridged race the bridge, head and body
## meet along welded seams that are not the rim: no kept vertex of the visible
## neck above 1.50 m may move more than 1 cm, and the bridge stays.
func verify_wardrobe_keeps_bridge(mesh: MeshInstance3D, original: Mesh,
		transform: Transform3D, fit: float, path: String) -> void:
	TorsoBodyCover.apply(mesh, true, transform, fit, [], false, {}, true)
	var moved := 0
	var largest := 0.0
	var bridge_kept := 0
	for surface: int in range(original.get_surface_count()):
		var material := original.surface_get_material(surface)
		var bridge := material != null and material.resource_name == "Shared neck bridge"
		var before: PackedVector3Array = original.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX]
		var arrays := mesh.mesh.surface_get_arrays(surface)
		var after: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var ids: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		var counted := {}
		for start: int in range(0, ids.size(), 3):
			if ids[start] == ids[start + 1] and ids[start] == ids[start + 2]:
				continue
			if bridge:
				bridge_kept += 1
			for corner: int in range(3):
				var vertex := ids[start + corner]
				if counted.has(vertex):
					continue
				counted[vertex] = true
				var point := (transform * before[vertex]) / fit
				if point.y <= 1.50:
					continue
				var distance := ((transform * after[vertex]) / fit).distance_to(point)
				largest = maxf(largest, distance)
				if distance > .01:
					moved += 1
	expect(moved == 0, path + " wardrobe neckline keeps the visible bridged neck in"
		+ " place: %d kept vertices above 1.50 m moved over 1 cm (largest %.1f cm)"
		% [moved, largest * 100.0])
	expect(bridge_kept > 0, path + " wardrobe neckline keeps the shared neck bridge")

## Number of faces in `expected` missing from `actual`, or -1 when `actual`
## is not an ordered subset of it (a face added, reordered or re-wound).
func independently_dropped_faces(expected: PackedInt32Array,
		actual: PackedInt32Array) -> int:
	var placeholder := PackedInt32Array([0, 0, 0])
	if actual == placeholder and expected != placeholder:
		actual = PackedInt32Array()
	var cursor := 0
	var dropped := 0
	for start: int in range(0, expected.size(), 3):
		if (cursor < actual.size() and actual[cursor] == expected[start]
				and actual[cursor + 1] == expected[start + 1]
				and actual[cursor + 2] == expected[start + 2]):
			cursor += 3
		else:
			dropped += 1
	return dropped if cursor == actual.size() else -1

## The generic bridge's trim line in rest space: 1.53 m behind the canonical
## neck axis, falling beside it to 1.49 m at 60 degrees from the front.
func independent_bridge_trim_y(point: Vector3) -> float:
	var ahead := point.z - lerpf(-.051, .011, (point.y - 1.452) / (1.568 - 1.452))
	if ahead < 0.0:
		return 1.53
	var angle := rad_to_deg(atan2(absf(point.x), ahead))
	return -INF if angle < 60.0 else lerpf(1.49, 1.53, (angle - 60.0) / 30.0)

## Positions are untouched except the cut neck bridge's hems, levelled in rest
## space: points within 3 cm of the trim line go onto it, points within 50
## degrees of the front move under 2 cm in height.
func independently_hem_moves_only(before: PackedVector3Array,
		after: PackedVector3Array, transform: Transform3D, fit: float,
		bridged: bool) -> bool:
	if before.size() != after.size():
		return false
	for vertex: int in range(before.size()):
		if before[vertex] == after[vertex]:
			continue
		if not bridged:
			return false
		var point := (transform * before[vertex]) / fit
		var moved := (transform * after[vertex]) / fit
		if (absf(moved.x - point.x) > .0001 or absf(moved.z - point.z) > .0001
				or absf(point.x) >= .18):
			return false
		var trim_y := independent_bridge_trim_y(point)
		var ahead := point.z - lerpf(-.051, .011, (point.y - 1.452) / (1.568 - 1.452))
		if trim_y > -INF:
			if absf(moved.y - trim_y) > .0001 or absf(point.y - trim_y) >= .03:
				return false
		elif absf(moved.y - point.y) >= .02 or absf(point.x) >= ahead * tan(deg_to_rad(50.0)):
			return false
	return true

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
