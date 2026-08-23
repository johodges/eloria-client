#!/usr/bin/env python3
"""Fail when generated assets lack provenance or use prohibited EL map names."""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROHIBITED = {
    "startmap.elm", "map2.elm", "map3.elm", "map4f.elm", "map5nf.elm",
    "map6nf.elm", "map7.elm", "map8.elm", "map9f.elm", "map11.elm",
    "map12.elm", "map13.elm", "map14f.elm", "map15f.elm"
}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((root / "provenance.json").read_text())
    if not provenance.get("assets"):
        print("asset provenance is empty", file=sys.stderr)
        return 1
    offenders = sorted(p for p in root.rglob("*") if p.name.casefold() in PROHIBITED)
    if offenders:
        print("prohibited official asset names:\n" + "\n".join(map(str, offenders)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
