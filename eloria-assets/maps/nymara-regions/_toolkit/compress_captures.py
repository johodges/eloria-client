#!/usr/bin/env python3
"""Convert the comparison captures to WebP.

Thirty-five 1280x800 PNGs is around 45 MB of repository for images whose only
job is to be looked at. WebP at quality 88 is visually indistinguishable here
and roughly a tenth of the size.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

import regionpaths

ROOT = regionpaths.package_root() / "references"


def convert(directory: Path, quality: int = 88) -> tuple[int, int]:
    before = after = 0
    for path in sorted(directory.glob("*.png")):
        if not path.exists():        # a concurrent run may have taken it already
            continue
        before += path.stat().st_size
        target = path.with_suffix(".webp")
        Image.open(path).convert("RGB").save(target, "WEBP", quality=quality, method=5)
        after += target.stat().st_size
        path.unlink(missing_ok=True)
    return before, after


def main() -> int:
    total_before = total_after = 0
    for directory in (ROOT / "captures", ROOT / "comparisons"):
        if not directory.exists():
            continue
        before, after = convert(directory)
        total_before += before
        total_after += after
    index_path = ROOT / "captures" / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
        for entry in index:
            entry["file"] = entry["file"].replace(".png", ".webp")
        index_path.write_text(json.dumps(index, indent=2) + "\n")
    print(f"[captures] {total_before / 1e6:.1f} MB PNG -> "
          f"{total_after / 1e6:.1f} MB WebP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
