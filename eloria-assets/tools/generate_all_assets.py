#!/usr/bin/env python3
"""Generate the complete independent Eloria data pack in dependency order."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


GENERATORS = (
    "generate_bootstrap_pack.py", "generate_characters.py",
    "generate_humanoid_enemies.py", "generate_fantasy_archetypes.py",
    "generate_npcs.py", "generate_creatures.py", "generate_scenery.py",
    "generate_interactives.py", "generate_regions.py",
    "generate_item_atlas.py", "generate_runtime_assets.py",
    "generate_effects.py", "generate_nymara_complete.py",
)


def validate_cal3d(root: Path) -> None:
    skeletons = tuple(root.glob("actors/**/*.xsf"))
    if not skeletons:
        raise RuntimeError("complete generation produced no Cal3D skeletons")
    stale = [path for path in skeletons if b"NUMCHILDS=" in path.read_bytes()]
    if stale:
        raise RuntimeError("stale Cal3D skeleton metadata: " +
                           ", ".join(str(path) for path in stale))


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
