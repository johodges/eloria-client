extends SceneTree
## Exercise combined generated armour through the real attachment path.
## Optional user argument: directory containing candidate leg/boot/head GLBs.

var failures := 0
var checks := 0

func _init() -> void:
	call_deferred("run")

func expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func verify_body(actor: ReplicatedActor3D, active: Dictionary, label: String) -> void:
	var regions: Array = []
	var backing_parts: Array = []
	for part: int in active:
		for piece: Node in actor._equipment_nodes.get(part, []):
			if piece.has_meta("replaces_torso_body"):
				regions.append(Vector3(.95, 1.535, .665))
				backing_parts.append(part)
			if piece.has_meta("generated_body_cover"):
				regions.append(piece.get_meta("generated_body_cover"))
				backing_parts.append(part)
	for part: int in [4, 5, 6]:
		expect(backing_parts.has(part) == active.has(part), label + " backing metadata for slot " + str(part))
	var visible_boot_backings := 0
	for piece: Node in actor._equipment_nodes.get(6, []):
		if piece.has_meta("boot_backing_with_legs"):
			var expected_visible := bool(piece.get_meta("boot_backing_with_legs")) == active.has(4)
			expect((piece as MeshInstance3D).visible == expected_visible, label + " chooses the matching cuff lining")
			visible_boot_backings += int((piece as MeshInstance3D).visible)
	if active.has(6):
		expect(visible_boot_backings == 1, label + " has exactly one boot lining")
	var visible_leg_backings := 0
	for piece: Node in actor._equipment_nodes.get(4, []):
		if piece.has_meta("leg_backing_with_boots"):
			var expected_visible := bool(piece.get_meta("leg_backing_with_boots")) == active.has(6)
			expect((piece as MeshInstance3D).visible == expected_visible, label + " chooses the matching trouser hem")
			visible_leg_backings += int((piece as MeshInstance3D).visible)
	if active.has(4):
		expect(visible_leg_backings == 1, label + " has exactly one trouser lining")
	var changed := 0
	var removed := 0
	var retained := 0
	for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var instance := node as MeshInstance3D
		if instance.name.to_lower() in ["hair", "eyes"]:
			expect(not instance.has_meta("uncovered_body_mesh"), "hair and eyes stay intact")
		if not instance.has_meta("uncovered_body_mesh"):
			continue
		var original := instance.get_meta("uncovered_body_mesh") as Mesh
		if regions.is_empty():
			expect(instance.mesh == original, label + " exact resource restored")
			continue
		changed += int(instance.mesh != original)
		var transform := actor._native_skeleton.global_transform.affine_inverse() * instance.global_transform
		for surface: int in range(original.get_surface_count()):
			var before := original.surface_get_arrays(surface)
			var after := instance.mesh.surface_get_arrays(surface)
			for field: int in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_BONES, Mesh.ARRAY_WEIGHTS]:
				expect(before[field] == after[field], label + " preserves vertex data " + str(field))
			# ArrayMesh repacks octahedral normals when rebuilding an index buffer.
			# Allow its quantization, but no change in surface direction.
			var before_normals: PackedVector3Array = before[Mesh.ARRAY_NORMAL]
			var after_normals: PackedVector3Array = after[Mesh.ARRAY_NORMAL]
			var normal_error := 0.0
			for i: int in range(before_normals.size()):
				normal_error = maxf(normal_error, before_normals[i].distance_to(after_normals[i]))
			expect(normal_error < .0002, label + " normal quantization " + str(normal_error))
			var vertices: PackedVector3Array = before[Mesh.ARRAY_VERTEX]
			var expected := PackedInt32Array()
			var indices: PackedInt32Array = before[Mesh.ARRAY_INDEX]
			for i: int in range(0, indices.size(), 3):
				var center := transform * ((vertices[indices[i]] + vertices[indices[i + 1]] + vertices[indices[i + 2]]) / 3.0)
				center /= actor.rig_fit_scale()
				var covered := false
				for region: Vector3 in regions:
					covered = covered or (center.y > region.x and center.y < region.y and absf(center.x) < region.z)
				if covered:
					removed += 1
				else:
					retained += 1
					expected.append_array(indices.slice(i, i + 3))
			if expected.is_empty():
				expected = PackedInt32Array([0, 0, 0])
			expect(after[Mesh.ARRAY_INDEX] == expected, label + " retains exactly the uncovered triangles")
	if not regions.is_empty():
		expect(changed > 0 and removed > 20 and retained > 20, label + " has active, bounded clothing replacement")

func run() -> void:
	var models: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/models.json"))["models"]
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/equipment.json"))
	var candidate_args := OS.get_cmdline_user_args()
	if not candidate_args.is_empty():
		for key: String in equipment["models"]:
			if int(key.get_slice(":", 0)) not in [3, 4, 6]:
				continue
			var entry: Dictionary = equipment["models"][key]
			var path := candidate_args[0].path_join(str(entry.get("scene", "")).get_file())
			if FileAccess.file_exists(path):
				entry["scene"] = path
	var sets: Array = [
		["legendary_hero_cuirass_01", "legendary_leg_armor_01", "legendary_sabatons_01", "legendary_eloria_helm_01"],
		["amberwood_woodland_cuirass_04", "amberwood_woodland_legguards_04", "amberwood_woodland_boots_04", "amberwood_forest_helm_04"],
		["eloria_arcane_armor_03", "arcane_leg_armor_03", "arcane_fantasy_boots_03", "arcane_ethereal_circlet_03"]]
	var outfits: Array = []
	for slugs: Array in sets:
		var outfit: Dictionary = {}
		for key: String in equipment["models"]:
			var scene: String = equipment["models"][key].get("scene", "")
			if scene.get_file().get_basename() in slugs:
				outfit[int(key.get_slice(":", 0))] = int(key.get_slice(":", 1))
		expect(outfit.size() == 4, "complete outfit resolves in catalogue")
		outfits.append(outfit)
	var races := 0
	var transitions := 0
	for path: String in DirAccess.get_files_at("res://assets/actors/native/races"):
		if not path.ends_with(".glb"):
			continue
		var race := path.get_basename()
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var config: Dictionary = models[race]
		var animations: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config["animationMap"]))
		var errors := actor.configure({"actor_id": 992, "x": 0, "y": 0, "rotation": 0,
			"kind": 1, "name": race, "appearance": {}, "equipment_visuals": {}},
			CoordinateAdapter.new({"walkingHeight": 0.0}), config, animations, equipment)
		expect(errors.is_empty(), race + " configures: " + str(errors))
		var initial_hair: Dictionary = {}
		for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
			if node.name.to_lower() in ["hair", "scalp"]:
				initial_hair[node.get_instance_id()] = (node as MeshInstance3D).visible
		for outfit: Dictionary in outfits:
			# Every single slot, then two different removal orders from a full set.
			var states: Array = [{4: outfit[4]}, {6: outfit[6]}, {3: outfit[3]}, outfit,
				{3: outfit[3], 5: outfit[5], 6: outfit[6]}, {3: outfit[3], 6: outfit[6]}, {},
				outfit, {3: outfit[3], 4: outfit[4], 5: outfit[5]}, {4: outfit[4]}, {}]
			for active: Dictionary in states:
				actor.apply_equipment_visuals(active)
				verify_body(actor, active, race + " " + str(active.keys()))
				var covered_hair := active.has(3) and int(active[3]) != int(outfits[2][3])
				for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
					var mesh := node as MeshInstance3D
					if mesh.name.to_lower() in ["hair", "scalp"]:
						expect(mesh.visible == (bool(initial_hair[mesh.get_instance_id()]) and not covered_hair), race + " restores sculpted hair visibility")
					if mesh.name.to_lower() == "eyes":
						expect(mesh.visible, race + " preserves eyes")
				for node: Node in actor._native_skeleton.get_children():
					if node.name.begins_with("AppearanceHair_"):
						expect((node as Node3D).visible != covered_hair, race + " restores chosen hairstyle for circlets and unequip")
				transitions += 1
		actor.free()
		races += 1
		print("ARMOUR COVER: %s complete, %d failures" % [race, failures])
	expect(races == 16, "all sixteen races exercised")
	print("ARMOUR COVER: %d races, %d transitions, %d checks, %d failures" % [races, transitions, checks, failures])
	quit(1 if failures else 0)
