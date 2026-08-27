#!/usr/bin/env python3
"""Apply native equipment-space and legacy NPC actor-type compatibility fixes."""
from __future__ import annotations

import json
from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{label} marker missing in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Native equipment GLBs are generated upright in actor/character space. Cancel
# the attachment bone's rest basis while retaining its origin and animated pose.
replace_once(
    "godot-client/src/actors/replicated_actor_3d.gd",
    '''\tif not model_config.is_empty() and not bones.is_empty():\n\t\tvar native_model: Node3D = _load_native_equipment(str(model_config.get("scene", "")))\n\t\tif native_model != null:\n\t\t\t_apply_equipment_import(native_model, model_config.get("import", {}) as Dictionary)\n\t\t\tvar native_attachment: BoneAttachment3D = _bone_attachment(bones[0], part, visual_id)\n''',
    '''\tif not model_config.is_empty() and not bones.is_empty():\n\t\tvar native_model: Node3D = _load_native_equipment(str(model_config.get("scene", "")))\n\t\tif native_model != null:\n\t\t\tvar bone_index: int = _native_skeleton.find_bone(bones[0])\n\t\t\t_apply_equipment_import(native_model,\n\t\t\t\tmodel_config.get("import", {}) as Dictionary, bone_index)\n\t\t\tvar native_attachment: BoneAttachment3D = _bone_attachment(bones[0], part, visual_id)\n''',
    "equipment attachment",
)
replace_once(
    "godot-client/src/actors/replicated_actor_3d.gd",
    '''func _apply_equipment_import(model: Node3D, config: Dictionary) -> void:\n\tmodel.scale = Vector3.ONE * float(config.get("scale", 1.0))\n\tvar translation_value: Variant = config.get("translation", [0, 0, 0])\n\tif translation_value is Array and (translation_value as Array).size() >= 3:\n\t\tvar translation: Array = translation_value as Array\n\t\tmodel.position = Vector3(float(translation[0]), float(translation[1]),\n\t\t\tfloat(translation[2]))\n\tvar rotation_value: Variant = config.get("rotationDegrees", [0, 0, 0])\n\tif rotation_value is Array and (rotation_value as Array).size() >= 3:\n\t\tvar rotation: Array = rotation_value as Array\n\t\tmodel.rotation_degrees = Vector3(float(rotation[0]), float(rotation[1]),\n\t\t\tfloat(rotation[2]))\n''',
    '''func _apply_equipment_import(model: Node3D, config: Dictionary,\n\t\tbone_index: int = -1) -> void:\n\tmodel.scale = Vector3.ONE * float(config.get("scale", 1.0))\n\tvar translation_value: Variant = config.get("translation", [0, 0, 0])\n\tif translation_value is Array and (translation_value as Array).size() >= 3:\n\t\tvar translation: Array = translation_value as Array\n\t\tmodel.position = Vector3(float(translation[0]), float(translation[1]),\n\t\t\tfloat(translation[2]))\n\tvar rotation_value: Variant = config.get("rotationDegrees", [0, 0, 0])\n\tif rotation_value is Array and (rotation_value as Array).size() >= 3:\n\t\tvar rotation: Array = rotation_value as Array\n\t\tmodel.rotation_degrees = Vector3(float(rotation[0]), float(rotation[1]),\n\t\t\tfloat(rotation[2]))\n\tif bool(config.get("characterSpace", false)) and _native_skeleton != null \\\n\t\t\tand bone_index >= 0:\n\t\t# Generated Nymara equipment is authored upright in actor space, while\n\t\t# BoneAttachment3D presents the attachment bone's rest-space axes. Cancel\n\t\t# only that rest basis; the bone origin and animated pose still drive gear.\n\t\tvar rest_basis: Basis = _native_skeleton.get_bone_global_rest(\n\t\t\tbone_index).basis.orthonormalized()\n\t\tmodel.transform = Transform3D(rest_basis.inverse(), Vector3.ZERO) * model.transform\n''',
    "equipment import",
)

replace_once(
    "eloria-assets/tools/build_native_nymara_glbs.py",
    '''            "import": {"translation": translation, "rotationDegrees": [0, 0, 0],\n                       "scale": 1},\n''',
    '''            "import": {"translation": translation, "rotationDegrees": [0, 0, 0],\n                       "scale": 1, "characterSpace": True},\n''',
    "equipment generator contract",
)

equipment_path = Path("godot-client/data/actors/equipment.json")
equipment = json.loads(equipment_path.read_text())
for model in equipment.get("models", {}).values():
    model.setdefault("import", {})["characterSpace"] = True
equipment_path.write_text(json.dumps(equipment, indent=2) + "\n")

replace_once(
    "godot-client/tests/test_native_glb_assets.py",
    '''    def test_legacy_guard_visuals_alias_to_native_models(self) -> None:\n''',
    '''    def test_generated_equipment_uses_character_space_axes(self) -> None:\n        for model_key, model in self.equipment["models"].items():\n            with self.subTest(model=model_key):\n                self.assertTrue(model["import"].get("characterSpace"), model_key)\n\n    def test_legacy_guard_visuals_alias_to_native_models(self) -> None:\n''',
    "equipment registry test",
)

replace_once(
    "godot-client/tests/integration/rendered_server_session.gd",
    '''\tvar unequipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()\n\tvar restored_inventory: Dictionary = _app_state.get("inventory") as Dictionary\n\t_expect(int(unequipped_diagnostics.get("native", 0)) == 0\n\t\tand int(unequipped_diagnostics.get("fallback", 0)) == 0,\n\t\t"authoritative unwear removes every native guard attachment cleanly")\n''',
    '''\tvar unequipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()\n\tvar restored_native_attachments: Dictionary = _native_equipment_attachments(equipped_actor)\n\tvar restored_inventory: Dictionary = _app_state.get("inventory") as Dictionary\n\t_expect(int(unequipped_diagnostics.get("native", 0)) == 3\n\t\tand int(unequipped_diagnostics.get("fallback", 0)) == 0\n\t\tand not restored_native_attachments.has(0)\n\t\tand not restored_native_attachments.has(1)\n\t\tand not restored_native_attachments.has(2)\n\t\tand restored_native_attachments.has(4)\n\t\tand restored_native_attachments.has(5)\n\t\tand restored_native_attachments.has(6),\n\t\t"authoritative unwear removes guard gear while retaining the default Luminous outfit")\n''',
    "live equipment unequip assertion",
)

# The unmodified server stores the actor type in the legacy one-byte actor
# record, even though Nymara NPC definitions occupy IDs 256-357. Reconstruct the
# full configured ID for non-player records only when that expanded ID exists in
# the client registry. This keeps player bytes and native 200-series creatures
# unambiguous and requires no server protocol change.
replace_once(
    "godot-client/src/app/main.gd",
    '''func _model_for_actor(dto: Dictionary) -> String:\n\tvar actor_type_value := int(dto.get("actor_type", 1))\n\tvar actor_type := str(actor_type_value)\n\tvar kind := int(dto.get("kind", 0))\n\t# Player actor IDs are not safe for NPC wire records: the server may send an\n\t# enhanced packet for an NPC while keeping the legacy actor_type byte at 1.\n\t# Nymara NPC/creature/enemy IDs occupy the dedicated 200+ registry range.\n\tif actor_type_models.has(actor_type) and (kind in [1, 4] or actor_type_value >= 200):\n\t\treturn str(actor_type_models[actor_type])\n\t# The server uses the enhanced wire layout for most NPCs so their appearance\n\t# bytes survive replication. Registry actor type wins for native NPCs and\n\t# creatures; actor kind decides the fallback for unknown records.\n\tif kind not in [1, 4]:\n\t\treturn ""\n\treturn "luminous_female" if actor_type_value == 0 else "luminous_male"\n\nfunc _presentation_dto(dto: Dictionary) -> Dictionary:\n\tvar result: Dictionary = dto.duplicate(true)\n\tvar actor_type: int = int(dto.get("actor_type", -1))\n\tvar appearance: Dictionary = dto.get("appearance", {}) as Dictionary\n\tvar visuals: Dictionary = AppearanceVariants.equipment_visuals(\n\t\tactor_type, appearance)\n\tvar look: Dictionary = npc_looks.get(str(int(dto.get("actor_type", -1))), {}) as Dictionary\n''',
    '''func _resolved_actor_type(dto: Dictionary) -> int:\n\tvar wire_actor_type: int = int(dto.get("actor_type", 1))\n\tvar kind: int = int(dto.get("kind", 0))\n\tif kind not in [1, 4] and wire_actor_type >= 0 and wire_actor_type < 256:\n\t\tvar expanded_actor_type: int = wire_actor_type + 256\n\t\tvar expanded_key: String = str(expanded_actor_type)\n\t\tif actor_type_models.has(expanded_key) or npc_looks.has(expanded_key):\n\t\t\treturn expanded_actor_type\n\treturn wire_actor_type\n\nfunc _model_for_actor(dto: Dictionary) -> String:\n\tvar actor_type_value: int = _resolved_actor_type(dto)\n\tvar actor_type: String = str(actor_type_value)\n\tvar kind: int = int(dto.get("kind", 0))\n\tif actor_type_models.has(actor_type) and (kind in [1, 4] or actor_type_value >= 200):\n\t\treturn str(actor_type_models[actor_type])\n\tif kind not in [1, 4]:\n\t\treturn ""\n\treturn "luminous_female" if actor_type_value == 0 else "luminous_male"\n\nfunc _presentation_dto(dto: Dictionary) -> Dictionary:\n\tvar result: Dictionary = dto.duplicate(true)\n\tvar actor_type: int = _resolved_actor_type(dto)\n\tvar appearance: Dictionary = dto.get("appearance", {}) as Dictionary\n\tvar visuals: Dictionary = AppearanceVariants.equipment_visuals(\n\t\tactor_type, appearance)\n\tvar look: Dictionary = npc_looks.get(str(actor_type), {}) as Dictionary\n''',
    "NPC actor-type resolver",
)

replace_once(
    "godot-client/tests/test_world_input.gd",
    '''\t_expect(str(main.call("_model_for_actor", {\n\t\t"enhanced": true, "kind": 2, "actor_type": 1})).is_empty(),\n\t\t"enhanced NPC wire packets never select a luminous player model")\n\t_expect(str(main.call("_model_for_actor", {\n\t\t"enhanced": true, "kind": 1, "actor_type": 1})) == "luminous_male",\n\t\t"enhanced player wire packets retain the native luminous model")\n''',
    '''\tvar registered_actor_types: Dictionary = main.get("actor_type_models") as Dictionary\n\tvar registered_npc_looks: Dictionary = main.get("npc_looks") as Dictionary\n\tvar toran_wire: Dictionary = {"enhanced": true, "kind": 2, "actor_type": 51}\n\t_expect(int(main.call("_resolved_actor_type", toran_wire)) == 307,\n\t\t"legacy one-byte NPC actor type reconstructs the configured Four Gates ID")\n\t_expect(str(main.call("_model_for_actor", toran_wire)) ==\n\t\tstr(registered_actor_types.get("307", "")),\n\t\t"reconstructed Four Gates NPC uses its native registered model")\n\tvar toran_presentation: Dictionary = main.call("_presentation_dto", toran_wire) as Dictionary\n\tvar toran_visuals: Dictionary = toran_presentation.get("equipment_visuals", {}) as Dictionary\n\tvar toran_look: Dictionary = registered_npc_looks.get("307", {}) as Dictionary\n\tvar toran_expected_visuals: Dictionary = toran_look.get("equipmentVisuals", {}) as Dictionary\n\tvar toran_gear_matches: bool = not toran_expected_visuals.is_empty()\n\tfor raw_part: Variant in toran_expected_visuals:\n\t\tif int(toran_visuals.get(raw_part, -1)) != int(toran_expected_visuals[raw_part]):\n\t\t\ttoran_gear_matches = false\n\t_expect(toran_gear_matches,\n\t\t"reconstructed Four Gates NPC applies its concept-native equipment look")\n\t_expect(str(main.call("_model_for_actor", {\n\t\t"enhanced": true, "kind": 1, "actor_type": 1})) == "luminous_male",\n\t\t"enhanced player wire packets retain the native luminous model")\n''',
    "NPC presentation fixture",
)

print("runtime compatibility fixes applied")
