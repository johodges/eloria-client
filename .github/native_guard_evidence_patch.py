from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

session_path = ROOT / "godot-client/tests/integration/rendered_server_session.gd"
session = session_path.read_text()
start_marker = '''\tmain.call("_on_inventory_button_pressed")
\tmain.call("_on_inventory_slot_pressed", 0)
\tmain.call("_on_inventory_equip_pressed")
'''
end_marker = '''

\thelper_network.disconnect_from_server()
'''
start = session.find(start_marker)
if start < 0:
    raise SystemExit("legacy single-spear evidence block start not found")
end = session.find(end_marker, start)
if end < 0:
    raise SystemExit("legacy single-spear evidence block end not found")
new_block = '''\tvar guard_specs: Array[Dictionary] = [
\t\t{
\t\t\t"name": "spear",
\t\t\t"part": 0,
\t\t\t"source_slot": _inspection_slot_for(inventory_inspections,
\t\t\t\t"Four Gates Guard Spear"),
\t\t\t"wear_slot": 36,
\t\t\t"allowed_visuals": [11, 112],
\t\t\t"bone": "hand_r",
\t\t},
\t\t{
\t\t\t"name": "shield",
\t\t\t"part": 1,
\t\t\t"source_slot": _inspection_slot_for(inventory_inspections,
\t\t\t\t"Guard Shield"),
\t\t\t"wear_slot": 37,
\t\t\t"allowed_visuals": [5, 105],
\t\t\t"bone": "hand_l",
\t\t},
\t\t{
\t\t\t"name": "cape",
\t\t\t"part": 2,
\t\t\t"source_slot": _inspection_slot_for(inventory_inspections,
\t\t\t\t"Guard Cape"),
\t\t\t"wear_slot": 38,
\t\t\t"allowed_visuals": [11, 105],
\t\t\t"bone": "spine_03",
\t\t},
\t]
\tmain.call("_on_inventory_button_pressed")
\tvar guard_server_visuals: Dictionary = {}
\tfor guard_spec: Dictionary in guard_specs:
\t\tvar source_slot: int = int(guard_spec.get("source_slot", -1))
\t\tvar wear_slot: int = int(guard_spec.get("wear_slot", -1))
\t\tvar part: int = int(guard_spec.get("part", -1))
\t\tvar guard_name: String = str(guard_spec.get("name", "guard item"))
\t\t_expect(source_slot >= 0, "real inventory contains the Four Gates guard " + guard_name)
\t\tif source_slot < 0:
\t\t\tcontinue
\t\tmain.call("_on_inventory_slot_pressed", source_slot)
\t\tmain.call("_on_inventory_equip_pressed")
\t\tvar guard_equipped: Callable = func() -> bool:
\t\t\tvar current_inventory: Dictionary = _app_state.get("inventory") as Dictionary
\t\t\tvar current_actors: Dictionary = _app_state.get("actors") as Dictionary
\t\t\tvar current_dto: Dictionary = current_actors.get(local_actor_id, {}) as Dictionary
\t\t\tvar current_visuals: Dictionary = current_dto.get("equipment_visuals", {}) as Dictionary
\t\t\treturn current_inventory.has(wear_slot) and not current_inventory.has(source_slot) \\
\t\t\t\tand _equipment_visual_id(current_visuals, part) >= 0
\t\tvar equipped_ok: bool = await _wait_for(guard_equipped, 8.0)
\t\t_expect(equipped_ok,
\t\t\t"real MOVE_INVENTORY_ITEM equips guard %s into wear slot %d and broadcasts part %d"
\t\t\t% [guard_name, wear_slot, part])
\t\tif not equipped_ok:
\t\t\tcontinue
\t\tvar equipped_actors: Dictionary = _app_state.get("actors") as Dictionary
\t\tvar equipped_dto: Dictionary = equipped_actors.get(local_actor_id, {}) as Dictionary
\t\tvar equipped_visuals: Dictionary = equipped_dto.get("equipment_visuals", {}) as Dictionary
\t\tvar server_visual_id: int = _equipment_visual_id(equipped_visuals, part)
\t\tguard_server_visuals[part] = server_visual_id
\t\tvar allowed_visuals: Array = guard_spec.get("allowed_visuals", []) as Array
\t\t_expect(allowed_visuals.has(server_visual_id),
\t\t\t"server guard %s visual id %d is a supported legacy/native compatibility id"
\t\t\t% [guard_name, server_visual_id])
\tmain.call("_sync_inventory")
\tfor guard_spec: Dictionary in guard_specs:
\t\tvar wear_slot: int = int(guard_spec.get("wear_slot", -1))
\t\tvar button_index: int = wear_slot - 36
\t\tvar equipped_button: Button = equipment_grid.get_child(button_index) as Button
\t\t_expect(equipped_button != null and equipped_button.icon != null
\t\t\tand equipped_button.text.contains("×1"),
\t\t\t"authoritative guard %s appears in wear slot %d"
\t\t\t% [str(guard_spec.get("name", "item")), wear_slot])
\tvar equipped_actor: ReplicatedActor3D = (
\t\tmain.get("actor_nodes") as Dictionary).get(local_actor_id) as ReplicatedActor3D
\tvar equipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()
\t_expect(int(equipped_diagnostics.get("native", 0)) == 3
\t\tand int(equipped_diagnostics.get("fallback", 0)) == 0,
\t\t"all three guard visuals resolve to native equipment with zero fallback")
\tvar native_attachments: Dictionary = _native_equipment_attachments(equipped_actor)
\tfor guard_spec: Dictionary in guard_specs:
\t\tvar part: int = int(guard_spec.get("part", -1))
\t\tvar attachment: Dictionary = native_attachments.get(part, {}) as Dictionary
\t\t_expect(str(attachment.get("bone", "")) == str(guard_spec.get("bone", ""))
\t\t\tand int(attachment.get("visible_meshes", 0)) > 0
\t\t\tand bool(attachment.get("under_skeleton", false)),
\t\t\t"native guard %s attaches to %s with visible geometry under the actor skeleton"
\t\t\t% [str(guard_spec.get("name", "item")), str(guard_spec.get("bone", ""))])
\tvar attachment_positions_before: Dictionary = _native_equipment_attachment_positions(
\t\tequipped_actor)
\tequipped_actor.play_action(&"walk")
\tfor unused_equipment_animation_frame: int in range(12):
\t\tawait process_frame
\tvar attachment_positions_after: Dictionary = _native_equipment_attachment_positions(
\t\tequipped_actor)
\tvar animation_followed_parts: int = 0
\tfor guard_spec: Dictionary in guard_specs:
\t\tvar part: int = int(guard_spec.get("part", -1))
\t\tvar before_value: Variant = attachment_positions_before.get(part)
\t\tvar after_value: Variant = attachment_positions_after.get(part)
\t\tif before_value is Vector3 and after_value is Vector3 and (
\t\t\t\tbefore_value as Vector3).distance_to(after_value as Vector3) > 0.0005:
\t\t\tanimation_followed_parts += 1
\t_expect(animation_followed_parts == 3,
\t\t"spear, shield, and cape bone attachments follow native actor animation")
\tequipped_actor.play_action(&"idle")
\tmain.call("_on_inventory_close_pressed")
\tvar equipment_capture_distance: float = camera_rig.distance
\tvar equipment_capture_yaw: float = camera_rig.yaw_degrees
\tvar equipment_capture_pitch: float = camera_rig.pitch_degrees
\tcamera_rig.distance = 9.0
\tcamera_rig.pitch_degrees = -38.0
\tcamera_rig.set_focus(equipped_actor.global_position + Vector3.UP * 0.2)
\tcamera_rig.yaw_degrees = default_yaw - 38.0
\tawait _capture("world-equipment-native-spear.png")
\tcamera_rig.yaw_degrees = default_yaw + 38.0
\tawait _capture("world-equipment-native-shield.png")
\tcamera_rig.yaw_degrees = default_yaw + 180.0
\tawait _capture("world-equipment-native-cape.png")
\tcamera_rig.distance = equipment_capture_distance
\tcamera_rig.yaw_degrees = equipment_capture_yaw
\tcamera_rig.pitch_degrees = equipment_capture_pitch
\tcamera_rig.set_focus(equipped_actor.global_position)
\tmain.call("_on_inventory_button_pressed")
\tfor guard_index: int in range(guard_specs.size() - 1, -1, -1):
\t\tvar guard_spec: Dictionary = guard_specs[guard_index]
\t\tvar wear_slot: int = int(guard_spec.get("wear_slot", -1))
\t\tvar part: int = int(guard_spec.get("part", -1))
\t\tmain.call("_on_equipment_slot_pressed", wear_slot)
\t\tmain.call("_on_inventory_unequip_pressed")
\t\tvar guard_unequipped: Callable = func() -> bool:
\t\t\tvar current_inventory: Dictionary = _app_state.get("inventory") as Dictionary
\t\t\tvar current_actors: Dictionary = _app_state.get("actors") as Dictionary
\t\t\tvar current_dto: Dictionary = current_actors.get(local_actor_id, {}) as Dictionary
\t\t\tvar current_visuals: Dictionary = current_dto.get("equipment_visuals", {}) as Dictionary
\t\t\treturn not current_inventory.has(wear_slot) \\
\t\t\t\tand _equipment_visual_id(current_visuals, part) < 0
\t\t_expect(await _wait_for(guard_unequipped, 8.0),
\t\t\t"real MOVE_INVENTORY_ITEM unequips guard %s from wear slot %d and clears part %d"
\t\t\t% [str(guard_spec.get("name", "item")), wear_slot, part])
\tmain.call("_on_inventory_close_pressed")
\tvar unequipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()
\tvar restored_inventory: Dictionary = _app_state.get("inventory") as Dictionary
\t_expect(int(unequipped_diagnostics.get("native", 0)) == 0
\t\tand int(unequipped_diagnostics.get("fallback", 0)) == 0,
\t\t"authoritative unwear removes every native guard attachment cleanly")
\t_expect(_inventory_item_count(restored_inventory, 0, 36) == expected_inventory_buttons,
\t\t"all guard items return to the backpack after authoritative unwear")
\t_write_json("equipment.json", {
\t\t"wear_slots": [36, 37, 38],
\t\t"server_visual_ids": _json_safe(guard_server_visuals),
\t\t"supported_visual_ids": {
\t\t\t"0": [11, 112],
\t\t\t"1": [5, 105],
\t\t\t"2": [11, 105],
\t\t},
\t\t"native_attachments": _json_safe(native_attachments),
\t\t"animation_followed_parts": animation_followed_parts,
\t\t"equipped_diagnostics": _json_safe(equipped_diagnostics),
\t\t"unequipped_diagnostics": _json_safe(unequipped_diagnostics),
\t\t"restored_inventory": _json_safe(restored_inventory),
\t\t"credentials": "REDACTED",
\t})
'''
session = session[:start] + new_block + session[end:]

helper_marker = '''func _populated_item_buttons(container: Container) -> int:
'''
helpers = '''func _inspection_slot_for(inspections: Array[Dictionary], marker: String) -> int:
\tfor inspection: Dictionary in inspections:
\t\tif str(inspection.get("text", "")).contains(marker):
\t\t\treturn int(inspection.get("slot", -1))
\treturn -1

func _equipment_visual_id(visuals: Dictionary, part: int) -> int:
\tif visuals.has(part):
\t\treturn int(visuals[part])
\tif visuals.has(str(part)):
\t\treturn int(visuals[str(part)])
\treturn -1

func _equipment_attachment_part(attachment: BoneAttachment3D) -> int:
\tvar attachment_name: String = str(attachment.name)
\tfor part: int in range(8):
\t\tif attachment_name.begins_with("EquipmentPart_%d_Visual_" % part):
\t\t\treturn part
\treturn -1

func _native_equipment_attachments(actor: ReplicatedActor3D) -> Dictionary:
\tvar attachments: Dictionary = {}
\tfor node_value: Node in actor.find_children("*", "BoneAttachment3D", true, false):
\t\tvar attachment: BoneAttachment3D = node_value as BoneAttachment3D
\t\tif not attachment.has_meta("native_equipment"):
\t\t\tcontinue
\t\tvar part: int = _equipment_attachment_part(attachment)
\t\tif part < 0:
\t\t\tcontinue
\t\tattachments[part] = {
\t\t\t"bone": str(attachment.bone_name),
\t\t\t"path": str(attachment.get_path()),
\t\t\t"under_skeleton": attachment.get_parent() is Skeleton3D,
\t\t\t"visible_meshes": _visible_native_mesh_count(attachment),
\t\t}
\treturn attachments

func _native_equipment_attachment_positions(actor: ReplicatedActor3D) -> Dictionary:
\tvar positions: Dictionary = {}
\tfor node_value: Node in actor.find_children("*", "BoneAttachment3D", true, false):
\t\tvar attachment: BoneAttachment3D = node_value as BoneAttachment3D
\t\tif not attachment.has_meta("native_equipment"):
\t\t\tcontinue
\t\tvar part: int = _equipment_attachment_part(attachment)
\t\tif part >= 0:
\t\t\tpositions[part] = attachment.global_transform.origin
\treturn positions

'''
if helpers not in session:
    marker_index = session.find(helper_marker)
    if marker_index < 0:
        raise SystemExit("integration helper insertion marker not found")
    session = session[:marker_index] + helpers + session[marker_index:]
session_path.write_text(session)

workflow_path = ROOT / ".github/workflows/godot-client.yml"
workflow = workflow_path.read_text()
old_capture = '          test -s "$ELORIA_ARTIFACT_DIR/world-equipment-fallback.png"\n'
new_captures = '''          test -s "$ELORIA_ARTIFACT_DIR/world-equipment-native-spear.png"
          test -s "$ELORIA_ARTIFACT_DIR/world-equipment-native-shield.png"
          test -s "$ELORIA_ARTIFACT_DIR/world-equipment-native-cape.png"
'''
if old_capture not in workflow:
    raise SystemExit("legacy rendered equipment artifact assertion not found")
workflow_path.write_text(workflow.replace(old_capture, new_captures, 1))
