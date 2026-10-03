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
							bridge_surface, covered):
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

func independently_covered(instance_name: String, point: Vector3) -> bool:
	var covered := (point.y > .95 and point.y < 1.535 and absf(point.x) < .665)
	if instance_name == "wardrobe_shirt":
		covered = covered or (point.y > 1.40 and point.y < 1.65 and absf(point.x) < .20)
	return covered

func independently_retained(instance: MeshInstance3D, arrays: Array,
		ids: PackedInt32Array, start: int, center: Vector3,
		bridge_surface: bool, covered: bool) -> bool:
	if instance.name.to_lower() not in ["body", "char1", "mesh_node"] or instance.skin == null:
		return not covered
	var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var stride: int = bones.size()/vertices.size()
	var mean_weight := 0.0
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
		mean_weight += corner_weight / 3.0
	var neck_envelope := (covered
		and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y
		and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH)
	if neck_envelope:
		return bridge_surface or mean_weight > .5
	return mean_weight > .5 or not covered
