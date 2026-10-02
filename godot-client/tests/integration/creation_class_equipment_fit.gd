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
	var body_templates: Dictionary = equipment.get("bodyTemplates", {}) as Dictionary
	var slugs: Array = body_templates.keys()
	slugs.sort()
	expect(slugs.size() == 16, "class equipment sweep covers all sixteen player rigs")
	expect(CreationArchetypes.count() == 4, "four creation classes are fitted")
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
			_check_skin_contract(actor, label)
			_check_fitted_backings(actor, label, loadout)
			_check_hand_socket(actor, label)
		actor.apply_equipment_visuals({})
		actor.queue_free()
		await process_frame
	NativeAnimationImporter.clear()
	print("CREATION_CLASS_EQUIPMENT_FIT checks=", checks,
		" failures=", failures, " rigs=", slugs.size())
	quit(1 if failures else 0)


func _check_skin_contract(actor: ReplicatedActor3D, label: String) -> void:
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
	expect(skinned >= 6, label + " has torso, leg and boot skins plus fitted backing")


func _check_fitted_backings(actor: ReplicatedActor3D, label: String,
		loadout: Dictionary) -> void:
	if loadout.has(6):
		var visible_boot_backings := 0
		for piece_value: Variant in actor._equipment_nodes.get(6, []) as Array:
			var piece := piece_value as Node
			if piece.has_meta("boot_backing_with_legs") and (piece as MeshInstance3D).visible:
				visible_boot_backings += 1
		expect(visible_boot_backings == 1,
			label + " uses one boot lining against its trousers")
	if loadout.has(4):
		var visible_leg_backings := 0
		for piece_value: Variant in actor._equipment_nodes.get(4, []) as Array:
			var piece := piece_value as Node
			if piece.has_meta("leg_backing_with_boots") and (piece as MeshInstance3D).visible:
				visible_leg_backings += 1
		expect(visible_leg_backings == 1,
			label + " uses one trouser lining against its boots")


func _check_hand_socket(actor: ReplicatedActor3D, label: String) -> void:
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
	expect(attachments == 1, label + " has exactly one right-hand attachment")
