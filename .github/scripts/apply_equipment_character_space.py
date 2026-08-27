from pathlib import Path

actor = Path('godot-client/src/actors/replicated_actor_3d.gd')
s = actor.read_text(encoding='utf-8')
old = '''\tif not model_config.is_empty() and not bones.is_empty():
\t\tvar native_model: Node3D = _load_native_equipment(str(model_config.get("scene", "")))
\t\tif native_model != null:
\t\t\t_apply_equipment_import(native_model, model_config.get("import", {}) as Dictionary)
\t\t\tvar native_attachment: BoneAttachment3D = _bone_attachment(bones[0], part, visual_id)
'''
new = '''\tif not model_config.is_empty() and not bones.is_empty():
\t\tvar native_model: Node3D = _load_native_equipment(str(model_config.get("scene", "")))
\t\tif native_model != null:
\t\t\tvar bone_index: int = _native_skeleton.find_bone(bones[0])
\t\t\t_apply_equipment_import(native_model,
\t\t\t\tmodel_config.get("import", {}) as Dictionary, bone_index)
\t\t\tvar native_attachment: BoneAttachment3D = _bone_attachment(bones[0], part, visual_id)
'''
if old not in s:
    raise SystemExit('native equipment creation marker missing')
s = s.replace(old, new, 1)
old = '''func _apply_equipment_import(model: Node3D, config: Dictionary) -> void:
\tmodel.scale = Vector3.ONE * float(config.get("scale", 1.0))
\tvar translation_value: Variant = config.get("translation", [0, 0, 0])
\tif translation_value is Array and (translation_value as Array).size() >= 3:
\t\tvar translation: Array = translation_value as Array
\t\tmodel.position = Vector3(float(translation[0]), float(translation[1]),
\t\t\tfloat(translation[2]))
\tvar rotation_value: Variant = config.get("rotationDegrees", [0, 0, 0])
\tif rotation_value is Array and (rotation_value as Array).size() >= 3:
\t\tvar rotation: Array = rotation_value as Array
\t\tmodel.rotation_degrees = Vector3(float(rotation[0]), float(rotation[1]),
\t\t\tfloat(rotation[2]))
'''
new = '''func _apply_equipment_import(model: Node3D, config: Dictionary,
\t\tbone_index: int = -1) -> void:
\tmodel.scale = Vector3.ONE * float(config.get("scale", 1.0))
\tvar translation_value: Variant = config.get("translation", [0, 0, 0])
\tif translation_value is Array and (translation_value as Array).size() >= 3:
\t\tvar translation: Array = translation_value as Array
\t\tmodel.position = Vector3(float(translation[0]), float(translation[1]),
\t\t\tfloat(translation[2]))
\tvar rotation_value: Variant = config.get("rotationDegrees", [0, 0, 0])
\tif rotation_value is Array and (rotation_value as Array).size() >= 3:
\t\tvar rotation: Array = rotation_value as Array
\t\tmodel.rotation_degrees = Vector3(float(rotation[0]), float(rotation[1]),
\t\t\tfloat(rotation[2]))
\tif (bool(config.get("characterSpace", false))
\t\t\tand _native_skeleton != null and bone_index >= 0):
\t\t# Generated Nymara equipment is authored upright in actor space, while
\t\t# BoneAttachment3D presents the attachment bone's rest-space axes.
\t\t# Cancel only the rest basis: the bone origin stays the anchor and pose
\t\t# deltas still drive weapons, clothing, shields, and capes in animation.
\t\tvar rest_basis: Basis = _native_skeleton.get_bone_global_rest(
\t\t\tbone_index).basis.orthonormalized()
\t\tmodel.transform = Transform3D(rest_basis.inverse(), Vector3.ZERO) * model.transform
'''
if old not in s:
    raise SystemExit('equipment import marker missing')
actor.write_text(s.replace(old, new, 1), encoding='utf-8')

builder = Path('eloria-assets/tools/build_native_nymara_glbs.py')
s = builder.read_text(encoding='utf-8')
old = '''            "import": {"translation": translation, "rotationDegrees": [0, 0, 0],
                       "scale": 1},
'''
new = '''            "import": {"translation": translation, "rotationDegrees": [0, 0, 0],
                       "scale": 1, "characterSpace": True},
'''
if old not in s:
    raise SystemExit('equipment registry marker missing')
builder.write_text(s.replace(old, new, 1), encoding='utf-8')

tests = Path('godot-client/tests/test_native_glb_assets.py')
s = tests.read_text(encoding='utf-8')
marker = '''    def test_legacy_guard_visuals_alias_to_native_models(self) -> None:
'''
addition = '''    def test_generated_equipment_uses_character_space_axes(self) -> None:
        for model_key, model in self.equipment["models"].items():
            with self.subTest(model=model_key):
                self.assertTrue(model["import"].get("characterSpace"), model_key)

'''
if marker not in s:
    raise SystemExit('native asset test marker missing')
tests.write_text(s.replace(marker, addition + marker, 1), encoding='utf-8')

session = Path('godot-client/tests/integration/rendered_server_session.gd')
s = session.read_text(encoding='utf-8')
old = '''\tvar unequipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()
\tvar restored_inventory: Dictionary = _app_state.get("inventory") as Dictionary
\t_expect(int(unequipped_diagnostics.get("native", 0)) == 0
\t\tand int(unequipped_diagnostics.get("fallback", 0)) == 0,
\t\t"authoritative unwear removes every native guard attachment cleanly")
'''
new = '''\tvar unequipped_diagnostics: Dictionary = equipped_actor.equipment_diagnostics()
\tvar restored_native_attachments: Dictionary = _native_equipment_attachments(equipped_actor)
\tvar restored_inventory: Dictionary = _app_state.get("inventory") as Dictionary
\t_expect(int(unequipped_diagnostics.get("native", 0)) == 3
\t\tand int(unequipped_diagnostics.get("fallback", 0)) == 0
\t\tand not restored_native_attachments.has(0)
\t\tand not restored_native_attachments.has(1)
\t\tand not restored_native_attachments.has(2)
\t\tand restored_native_attachments.has(4)
\t\tand restored_native_attachments.has(5)
\t\tand restored_native_attachments.has(6),
\t\t"authoritative unwear removes guard gear while retaining the default Luminous outfit")
'''
if old not in s:
    raise SystemExit('live-session unequip marker missing')
session.write_text(s.replace(old, new, 1), encoding='utf-8')
