extends SceneTree
## Every creation class is race-independent, so its representative kit must
## survive the same live equipment path on all sixteen playable body rigs.

var failures := 0
var checks := 0


func _init() -> void:
	call_deferred("run")


func expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)


func run() -> void:
	var models_document: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(
		"res://data/actors/models.json"))
	var models: Dictionary = models_document.get("models", {}) as Dictionary
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(
		"res://data/actors/equipment.json"))
	var equipment_models: Dictionary = equipment.get("models", {}) as Dictionary
	var suppressed_backing_models: Array[String] = []
	for model_key_value: Variant in equipment_models:
		var model_key := str(model_key_value)
		var equipment_model := equipment_models[model_key_value] as Dictionary
		if not equipment_model.has("suppressGeneratedBacking"):
			continue
		expect(equipment_model["suppressGeneratedBacking"] is bool and
			bool(equipment_model["suppressGeneratedBacking"]),
			model_key + " backing suppression is an explicit true boolean")
		suppressed_backing_models.append(model_key)
	suppressed_backing_models.sort()
	expect(suppressed_backing_models == ["4:179", "5:216", "6:192"],
		"only the visually verified Warded set suppresses generated backing draws")
	var body_templates: Dictionary = equipment.get("bodyTemplates", {}) as Dictionary
	var slugs: Array = body_templates.keys()
	slugs.sort()
	expect(slugs.size() == 16, "class equipment sweep covers all sixteen player rigs")
	expect(CreationArchetypes.count() == 4, "four creation classes are fitted")
	expect(CreationArchetypes.loadout_at(0) == {0: 114, 1: 106, 2: 105, 5: 209},
		"Vanguard leaves the clean native lower wardrobe visible")
	expect(CreationArchetypes.loadout_at(1) == {0: 164, 4: 230, 5: 225, 6: 224},
		"Ranger uses the rotated-fit Sidelace Breeches and Ankle Boots")
	expect(CreationArchetypes.loadout_at(2) == {0: 142, 4: 179, 5: 216, 6: 192},
		"Arcanist keeps its coherent Warded set")
	expect(CreationArchetypes.loadout_at(3) == {0: 163, 2: 100, 5: 189},
		"Warden leaves the clean native lower wardrobe visible")
	for slug_value: Variant in slugs:
		var slug := str(slug_value)
		var model: Dictionary = models.get(slug, {}) as Dictionary
		expect(not model.is_empty(), slug + " model config exists")
		if model.is_empty():
			continue
		var animation_path := str(model.get("animationMap",
			"res://data/animations/luminous.json"))
		var animations: Dictionary = JSON.parse_string(
			FileAccess.get_file_as_string(animation_path))
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var errors := actor.configure({
			"actor_id": 9100, "x": 0, "y": 0, "rotation": 0,
			"kind": 1, "name": "", "appearance": {},
			"equipment_visuals": {},
		}, CoordinateAdapter.new({"walkingHeight": 0.0}), model,
			animations, equipment)
		expect(errors.is_empty(), slug + " configures for class equipment")
		if not errors.is_empty():
			actor.queue_free()
			await process_frame
			continue
		actor.set_process(false)
		actor.set_physics_process(false)
		for class_index: int in range(CreationArchetypes.count()):
			var entry := CreationArchetypes.at(class_index)
			var label := "%s %s" % [slug, str(entry.get("label", "class"))]
			var loadout := CreationArchetypes.loadout_at(class_index)
			actor.apply_equipment_visuals(loadout)
			await process_frame
			var diagnostics := actor.equipment_diagnostics()
			expect((diagnostics.get("visuals", {}) as Dictionary) == loadout,
				label + " replaces the previous class without stale equipment")
			expect(int(diagnostics.get("fallback", -1)) == 0,
				label + " loads only shipped equipment models")
			for raw_part: Variant in loadout:
				var part := int(raw_part)
				var nodes: Array = actor._equipment_nodes.get(part, []) as Array
				expect(not nodes.is_empty(), "%s creates equipment part %d" % [label, part])
			_check_skin_contract(actor, label, loadout)
			_check_fitted_backings(actor, label, loadout)
			_check_hand_socket(actor, label, str(entry.get("label", "class")))
		var mixed_backing_loadouts: Array[Dictionary] = [
			{5: 216},
			{4: 179},
			{6: 192},
			{4: 179, 6: 224},
			{4: 230, 6: 192},
			{4: 179, 5: 216, 6: 192},
		]
		for mixed_loadout: Dictionary in mixed_backing_loadouts:
			actor.apply_equipment_visuals(mixed_loadout)
			await process_frame
			_check_fitted_backings(actor, "%s mixed %s" % [slug, mixed_loadout],
				mixed_loadout)
		actor.apply_equipment_visuals({})
		await process_frame
		expect(actor._equipment_nodes.is_empty(),
			slug + " unequip removes every class equipment node")
		_check_native_body_restored(actor, slug)
		actor.queue_free()
		await process_frame
	NativeAnimationImporter.clear()
	print("CREATION_CLASS_EQUIPMENT_FIT checks=", checks,
		" failures=", failures, " rigs=", slugs.size())
	quit(1 if failures else 0)


func _check_skin_contract(actor: ReplicatedActor3D, label: String,
		loadout: Dictionary) -> void:
	var skeleton := actor.get_skeleton()
	var skinned := 0
	for nodes_value: Variant in actor._equipment_nodes.values():
		for node_value: Variant in nodes_value as Array:
			var node := node_value as Node
			if node is not MeshInstance3D:
				continue
			var mesh_node := node as MeshInstance3D
			if mesh_node.skin == null:
				continue
			skinned += 1
			var skin := mesh_node.skin
			for bind: int in range(skin.get_bind_count()):
				expect(skeleton.find_bone(skin.get_bind_name(bind)) >= 0,
					label + " retains every named equipment bind")
	var expected_minimum := 6 if loadout.has(4) or loadout.has(6) else 2
	expect(skinned >= expected_minimum,
		label + " has every skinned garment required by its preview loadout")


func _check_fitted_backings(actor: ReplicatedActor3D, label: String,
		loadout: Dictionary) -> void:
	var suppressed_parts := 0
	var expected_suppressed_parts := 0
	var reviewed_suppressed_visuals := {
		ReplicatedActor3D.BODY_PART: 216,
		4: 179,
		6: 192,
	}
	for part_value: Variant in reviewed_suppressed_visuals:
		var part := int(part_value)
		if int(loadout.get(part, -1)) == int(reviewed_suppressed_visuals[part_value]):
			expected_suppressed_parts += 1
	for part: int in [ReplicatedActor3D.BODY_PART, 4, 6]:
		if not loadout.has(part):
			continue
		var model := actor._equipment_model_config(part, int(loadout[part]))
		if not bool(model.get("suppressGeneratedBacking", false)):
			continue
		suppressed_parts += 1
		var suppressed_nodes := 0
		var cover_nodes := 0
		for piece_value: Variant in actor._equipment_nodes.get(part, []) as Array:
			var piece := piece_value as Node
			if piece.has_meta("generated_body_cover"):
				cover_nodes += 1
			if not piece.has_meta("suppress_generated_backing"):
				continue
			suppressed_nodes += 1
			expect(not (piece as MeshInstance3D).visible,
				"%s keeps suppressed generated backing hidden for part %d" % [label, part])
		expect(suppressed_nodes > 0,
			"%s carries suppression metadata onto generated part %d nodes" % [label, part])
		expect(cover_nodes > 0,
			"%s retains body-cover metadata while hiding part %d backing" % [label, part])
	if loadout.has(6):
		var visible_boot_backings := 0
		for piece_value: Variant in actor._equipment_nodes.get(6, []) as Array:
			var piece := piece_value as Node
			if piece.has_meta("boot_backing_with_legs") and (piece as MeshInstance3D).visible:
				visible_boot_backings += 1
		var boot_model := actor._equipment_model_config(6, int(loadout[6]))
		var expected_boot_backings := 0 if bool(boot_model.get(
			"suppressGeneratedBacking", false)) else 1
		expect(visible_boot_backings == expected_boot_backings,
			label + " uses one boot lining against its trousers")
	if loadout.has(4):
		var visible_leg_backings := 0
		for piece_value: Variant in actor._equipment_nodes.get(4, []) as Array:
			var piece := piece_value as Node
			if piece.has_meta("leg_backing_with_boots") and (piece as MeshInstance3D).visible:
				visible_leg_backings += 1
		var leg_model := actor._equipment_model_config(4, int(loadout[4]))
		var expected_leg_backings := 0 if bool(leg_model.get(
			"suppressGeneratedBacking", false)) else 1
		expect(visible_leg_backings == expected_leg_backings,
			label + " uses one trouser lining against its boots")
	expect(suppressed_parts == expected_suppressed_parts,
		label + " suppresses exactly the selected reviewed backing draws")
	if expected_suppressed_parts > 0:
		var covered_surfaces := 0
		var native_model := actor.get_node_or_null("NativeModel") as Node3D
		for mesh_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
			var mesh_node := mesh_value as MeshInstance3D
			if not mesh_node.has_meta("uncovered_body_mesh"):
				continue
			covered_surfaces += 1
			expect(mesh_node.mesh != (mesh_node.get_meta("uncovered_body_mesh") as Mesh),
				label + " still applies body cover behind hidden generated backing")
		expect(covered_surfaces > 0,
			label + " keeps at least one native body surface covered")


func _check_native_body_restored(actor: ReplicatedActor3D, label: String) -> void:
	var native_model := actor.get_node_or_null("NativeModel") as Node3D
	var restored := 0
	for mesh_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node := mesh_value as MeshInstance3D
		if not mesh_node.has_meta("uncovered_body_mesh"):
			continue
		restored += 1
		expect(mesh_node.mesh == (mesh_node.get_meta("uncovered_body_mesh") as Mesh),
			label + " restores the exact native body mesh after unequip")
	expect(restored > 0, label + " exercised body-cover restoration")


func _check_hand_socket(actor: ReplicatedActor3D, label: String,
		class_label: String) -> void:
	var attachments := 0
	var hand := actor.get_skeleton().find_bone("hand_r")
	for piece_value: Variant in actor._equipment_nodes.get(0, []) as Array:
		var piece := piece_value as Node
		if piece is not BoneAttachment3D or piece.get_child_count() == 0:
			continue
		attachments += 1
		var prop := piece.get_child(0) as Node3D
		var hand_world := actor.get_skeleton().global_transform * \
			actor.get_skeleton().get_bone_global_pose(hand).origin
		var grip_distance := prop.global_position.distance_to(hand_world)
		expect(grip_distance >= 0.025 and grip_distance <= 0.13,
			label + " places its weapon grip inside the palm reach")
		# The Ranger's visible bow is a separate animated left-hand visual. The
		# other three class props use this socket directly. Sword and wand origins
		# are authored at the grip centre; the quarterstaff's source origin is
		# displaced from its visible wrapped handle, so it needs its own measured
		# character-space placement.
		if class_label != "Ranger":
			var socket_offsets := {
				"Vanguard": Vector3(-0.0757, -0.05, 0.0),
				"Arcanist": Vector3(-0.0757, -0.05, 0.0),
				"Warden": Vector3(-0.02, -0.09, -0.07955),
			}
			var socket_offset: Vector3 = socket_offsets[class_label]
			var expected_local := actor.get_skeleton().get_bone_global_rest(hand).basis.inverse() * \
				(socket_offset * actor.rig_fit_scale("legacy"))
			expect(prop.position.distance_to(expected_local) <= 0.0005,
				label + " uses its reviewed right-palm socket placement")
	expect(attachments == 1, label + " has exactly one right-hand attachment")
