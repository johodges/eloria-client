#!/usr/bin/env python3
"""Generate the complete independent Eloria data pack in dependency order."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


GENERATORS = (
    "generate_bootstrap_pack.py", "generate_characters.py",
    "generate_humanoid_enemies.py", "generate_fantasy_archetypes.py",
    "generate_npcs.py", "generate_creatures.py", "generate_scenery.py",
    "generate_interactives.py", "generate_regions.py",
    "generate_item_atlas.py", "generate_runtime_assets.py",
    "generate_effects.py", "generate_special_event_assets.py",
    "generate_nymara_complete.py",
)


def validate_cal3d(root: Path) -> None:
    skeletons = tuple(root.glob("actors/**/*.xsf"))
    if not skeletons:
        raise RuntimeError("complete generation produced no Cal3D skeletons")
    stale = [path for path in skeletons if b"NUMCHILDS=" in path.read_bytes()]
    if stale:
        raise RuntimeError("stale Cal3D skeleton metadata: " +
                           ", ".join(str(path) for path in stale))
    bad_magic = [path for path in skeletons if b'MAGIC="XSF"' not in path.read_bytes()]
    if bad_magic:
        raise RuntimeError("invalid Cal3D skeleton magic: " +
                           ", ".join(str(path) for path in bad_magic))
    actor_defs = root / "actor_defs/actor_defs.xml"
    for value in re.findall(r"<CAL_[^>]+>([^<]+)</CAL_", actor_defs.read_text(encoding="utf-8")):
        if not re.search(r" [01]$", value):
            raise RuntimeError(f"animation entry lacks cycle/action mode: {value}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", default="build/eloria-data")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    tools = Path(__file__).resolve().parent
    for generator in GENERATORS:
        subprocess.run((sys.executable, str(tools / generator), str(output)),
                       check=True)
    validate_cal3d(output)
    print(f"Generated complete Eloria data pack at {output}")


if __name__ == "__main__":
    main()
