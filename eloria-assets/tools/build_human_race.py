#!/usr/bin/env python3
"""Build the Human race and register it, without rebuilding anything else.

``build_native_nymara_glbs.py`` knows about this race and a full run produces
the same two files, but a full run also rewrites every other GLB in the
library, and those do not currently round-trip byte-for-byte across platforms.
Rebuilding one race through this entry point keeps a change to one race a
change to one race.

What it writes:

  * ``godot-client/assets/actors/native/races/human_{female,male}.glb``
  * the two ``races`` entries and the validation list in the asset catalogue
  * the two preview models and the ``previewModels`` list in the model
    registry -- they carry a null ``serverActorType`` because actor-type
    allocation belongs to eloria-server
  * the two ``bodyGirth`` measurements the garment fitter needs

    python3 eloria-assets/tools/build_human_race.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_native_nymara_glbs as native
import equipment_authoring
import human_race


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=root / "godot-client/assets/actors/native")
    parser.add_argument("--manifest", type=Path,
                        default=root / "godot-client/data/actors/native_asset_catalog.json")
    parser.add_argument("--models", type=Path,
                        default=root / "godot-client/data/actors/models.json")
    parser.add_argument("--equipment-registry", type=Path,
                        default=root / "godot-client/data/actors/equipment.json")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    equipment = json.loads(args.equipment_registry.read_text(encoding="utf-8"))
    # The model registry is rebuilt whole rather than patched: it is generated
    # from tables, so regenerating it is what a full run of the shared builder
    # would write, and a merge would drift from that silently.
    models = native.build_model_registry()

    for race in native.PREVIEW_RACES:
        label = native.RACES[race]["label"]
        for gender in ("female", "male"):
            model_id = f"{race}_{gender}"
            path = args.output / "races" / f"{model_id}.glb"
            record = human_race.build_human_player(native.GLB, path, gender, label)
            manifest["races"][model_id] = record | {
                "path": path.relative_to(root).as_posix()}
            equipment["bodyGirth"][model_id] = equipment_authoring.body_girth(
                equipment_authoring.load_rig(path))
            print(model_id, record)
    equipment["bodyGirth"] = dict(sorted(equipment["bodyGirth"].items()))
    native.carry_forward_ambient(args.manifest, args.models, manifest, models)

    validation = {path.relative_to(root).as_posix(): native.validate_glb(path)
                  for path in args.output.rglob("*.glb")}
    manifest["validation"] = {"files": len(validation), "results": validation}
    write_json(args.manifest, manifest)
    write_json(args.models, models)
    write_json(args.equipment_registry, equipment)
    print(f"registered {len(native.PREVIEW_RACES) * 2} human rigs; "
          f"{len(validation)} native GLBs on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
