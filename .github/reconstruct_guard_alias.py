from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

equipment_path = ROOT / "godot-client/data/actors/equipment.json"
equipment = json.loads(equipment_path.read_text())
aliases = {
    "0:11": "0:112",
    "1:5": "1:105",
    "2:11": "2:105",
}
existing_aliases = equipment.get("aliases")
if existing_aliases not in (None, aliases):
    raise SystemExit(f"unexpected existing equipment aliases: {existing_aliases!r}")
if len(equipment.get("models", {})) != 63:
    raise SystemExit("native equipment model registry is not the expected 63-entry head")
for target in aliases.values():
    if target not in equipment["models"]:
        raise SystemExit(f"native alias target is missing: {target}")
equipment["aliases"] = aliases
equipment_path.write_text(json.dumps(equipment, indent=2) + "\n")

actor_path = ROOT / "godot-client/src/actors/replicated_actor_3d.gd"
actor = actor_path.read_text()
old_lookup = '''\tvar models: Dictionary = _equipment_config.get("models", {}) as Dictionary
\tvar model_config: Dictionary = models.get("%d:%d" % [part, visual_id], {}) as Dictionary
'''
new_lookup = '''\tvar aliases: Dictionary = _equipment_config.get("aliases", {}) as Dictionary
\tvar model_key: String = "%d:%d" % [part, visual_id]
\tmodel_key = str(aliases.get(model_key, model_key))
\tvar models: Dictionary = _equipment_config.get("models", {}) as Dictionary
\tvar model_config: Dictionary = models.get(model_key, {}) as Dictionary
'''
if old_lookup not in actor:
    raise SystemExit("equipment model lookup block no longer matches expected head")
actor_path.write_text(actor.replace(old_lookup, new_lookup, 1))

test_path = ROOT / "godot-client/tests/test_native_glb_assets.py"
tests = test_path.read_text()
marker = '    def test_every_playable_actor_type_has_creation_option(self) -> None:\n'
addition = '''    def test_legacy_guard_visuals_alias_to_native_models(self) -> None:
        expected = {
            "0:11": "0:112",
            "1:5": "1:105",
            "2:11": "2:105",
        }
        self.assertEqual(expected, self.equipment["aliases"])
        for native_visual in expected.values():
            self.assertIn(native_visual, self.equipment["models"])

'''
if addition not in tests:
    if marker not in tests:
        raise SystemExit("native GLB test insertion point no longer matches expected head")
    test_path.write_text(tests.replace(marker, addition + marker, 1))

trace_path = ROOT / "godot-client/docs/migration/TRACEABILITY.md"
trace = trace_path.read_text()
old_row = '| Equipment | `items.c`, `items.h`; server `protocol.py`, `world.py`, `items.py` | equipment slots and actor attachment presentation | exact wear-slot/move fixtures; rendered real-server spear equip/unwear, slot reconciliation, actor visual, skeleton fallback, and cleanup; native GLB mapping remains pending | IMPLEMENTED |'
new_row = '| Equipment | `items.c`, `items.h`; server `protocol.py`, `world.py`, `items.py` | equipment slots and actor attachment presentation | exact wear-slot/move fixtures; rendered real-server spear equip/unwear, slot reconciliation, actor visual, skeleton fallback, and cleanup; data-driven aliases resolve legacy guard visuals `0:11`, `1:5`, and `2:11` to native visuals `0:112`, `1:105`, and `2:105`; rendered native verification remains pending | IMPLEMENTED |'
if old_row not in trace:
    raise SystemExit("equipment traceability row no longer matches expected head")
trace_path.write_text(trace.replace(old_row, new_row, 1))
