#!/usr/bin/env python3
"""Make the ground a region draws under a player walkable in its walk grid.

A region's `collision.bin` is not built from its geometry. The build derives it
from the terrain height field and then re-opens the decks - causeways, quays,
bridges, jetties - by guessing each one's footprint from its placement bounds.
Ten regions each carry their own copy of that code and the copies drifted: four
of them fold a deck as a rotated rectangle, and six still use the circle
inscribed in its bounds, which covers 2.3 m of a 40 m causeway. Mirrorhold's
marble causeway was blocked over its whole length bar a five-tile disc in the
middle; Crownwater's harbour quays lost their ends and their edges.

Rather than repair the guess ten times, this reads the answer out of the
package. Every surface a player can stand on is a `Walk_*` node - that is what
the client's downward ray finds - so those nodes are rasterised onto the
package's own half-metre grid and every cell they cover is opened, at the
height of the surface itself. A surface drawn under one of the map's `Water_*`
bodies is left blocked: the drowned court in Crownwater's lagoon is scenery,
not a floor. So is anything inside a landmark box `stamp_solid_landmarks.py`
has closed, because a hall's floor is a walk surface too and the hall is shut.

    python _toolkit/open_walk_surfaces.py <region> [<region> ...]
    python _toolkit/open_walk_surfaces.py --all
    python _toolkit/open_walk_surfaces.py --all --check     # report, write nothing

Run it after a region build, before `stamp_solid_landmarks.py`, and then the
server's `sync_authored_collision.py`. What it did is recorded in `world.json`
under `collision.openedWalkSurfaces`, and running it twice changes nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import glb_reader as GLB   # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WALK = "Walk_"
WATER = "Water_"
# How far under the water a surface may sit and still be a floor. A jetty deck
# is flush with the water it stands in; the drowned court is metres below it.
WADE = 0.25
LEVELS = 63
MINIMUM_STEP = 0.2


def decode(grid: np.ndarray, encoding: dict) -> np.ndarray:
    """The grid as metres, NaN where it is blocked."""
    origin, step = float(encoding["origin"]), float(encoding["step"])
    return np.where(grid != 0, origin + grid.astype(np.float64) * step, np.nan)


def encode(heights: np.ndarray, encoding: dict) -> tuple[np.ndarray, dict]:
    """Metres back to cell bytes, keeping the package's own encoding when the
    heights still fit it so that a run that changes nothing writes nothing."""
    walkable = ~np.isnan(heights)
    if not walkable.any():
        return np.zeros(heights.shape, dtype=np.uint8), encoding
    origin, step = float(encoding["origin"]), float(encoding["step"])
    codes = np.where(walkable, np.round((heights - origin) / step), 0)
    if codes[walkable].min() >= 1 and codes[walkable].max() <= LEVELS:
        return np.where(walkable, codes, 0).astype(np.uint8), encoding
    low = float(np.nanmin(heights))
    relief = float(np.nanmax(heights)) - low
    step = max(MINIMUM_STEP, relief / (LEVELS - 1))
    origin = low - step
    codes = np.clip(np.round((heights - origin) / step), 1, LEVELS)
    return (np.where(walkable, codes, 0).astype(np.uint8),
            dict(encoding, origin=round(origin, 4), step=round(step, 6)))


def stamped(manifest: dict, shape, origin, cell: float) -> np.ndarray:
    """Cells inside a landmark box `stamp_solid_landmarks.py` has closed."""
    out = np.zeros(shape, dtype=bool)
    for entry in (manifest.get("collision") or {}).get("stampedLandmarks", ()):
        x0, z0, x1, z1 = entry["box"]
        margin = float(entry.get("marginMetres", 0.0))
        c0 = int(np.ceil((x0 - margin - origin[0]) / cell - 0.5))
        c1 = int(np.floor((x1 + margin - origin[0]) / cell - 0.5))
        r0 = int(np.ceil((origin[1] - z1 - margin) / cell - 0.5))
        r1 = int(np.floor((origin[1] - z0 + margin) / cell - 0.5))
        out[max(r0, 0):r1 + 1, max(c0, 0):c1 + 1] = True
    return out


def open_package(package: Path, write: bool) -> dict | None:
    grid, manifest = GLB.read_grid(package)
    collision = manifest["collision"]
    encoding = collision.get("heightEncoding")
    if not encoding or not (package / "world.glb").is_file():
        print(f"[open] {package.name}: no world.glb or no height encoding; skipped")
        return None
    cell = float(collision["cellMetres"])
    origin = GLB.grid_origin(manifest)
    document, body = GLB.load(package / "world.glb")
    walk_nodes = GLB.named(document, WALK)
    if not walk_nodes:
        print(f"[open] {package.name}: no {WALK}* nodes; nothing to open")
        return None
    covered, top = GLB.rasterise(GLB.triangles(document, body, walk_nodes),
                                 grid.shape[1], grid.shape[0], origin[0], origin[1], cell)
    water_nodes = GLB.named(document, WATER)
    wet, water_top = GLB.rasterise(GLB.triangles(document, body, water_nodes),
                                   grid.shape[1], grid.shape[0], origin[0], origin[1], cell)
    drowned = covered & wet & (top < water_top - WADE)
    shut = stamped(manifest, grid.shape, origin, cell)
    usable = covered & ~drowned & ~shut

    heights = decode(grid, encoding)
    blocked = np.isnan(heights)
    opened = usable & blocked
    raised = usable & ~blocked & (top > heights + 1e-6)
    heights = np.where(usable & (blocked | (top > heights)), top, heights)
    codes, new_encoding = encode(heights, encoding)

    record = {"prefix": WALK, "cellsCovered": int(covered.sum()),
              "cellsOpened": int(opened.sum()), "cellsRaised": int(raised.sum()),
              "cellsDrowned": int(drowned.sum()), "cellsInsideLandmarks": int((covered & shut).sum())}
    print(f"[open] {package.name}: {record['cellsCovered']} cells carry a walk surface; "
          f"opened {record['cellsOpened']}, raised {record['cellsRaised']}, "
          f"left {record['cellsDrowned']} under water and {record['cellsInsideLandmarks']} inside landmarks")
    if not write:
        return record
    walkable = int((codes != 0).sum())
    collision["heightEncoding"] = new_encoding
    collision["walkableCells"] = walkable
    collision["walkableFraction"] = round(walkable / codes.size, 4)
    # Keep the record the first run wrote: a second run finds nothing to open
    # because the first one opened it, and zero would read as "there was none".
    previous = collision.get("openedWalkSurfaces") or {}
    for key in ("cellsOpened", "cellsRaised"):
        record[key] = max(record[key], int(previous.get(key, 0)))
    collision["openedWalkSurfaces"] = record
    manifest["collision"] = collision
    GLB.write_grid(package, manifest, codes)
    GLB.write_manifest(package / "world.json", manifest)
    return record


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    write = "--check" not in sys.argv
    if "--all" in sys.argv:
        packages = sorted(p.parent for p in ROOT.glob("*/world.json")
                          if (p.parent / "world.glb").is_file() and (p.parent / "collision.bin").is_file())
    elif args:
        packages = [ROOT / name for name in args]
    else:
        print(__doc__)
        return 2
    for package in packages:
        open_package(package, write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
