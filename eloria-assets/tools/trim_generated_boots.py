#!/usr/bin/env python3
"""Cut the sabatons off the generated leg pieces that came with feet attached.

Added 2026-09-06 for Eloria Client.

Legs and feet are separate slots, so a leg piece owns the body from the waist
to the ankle and nothing below it.  One of the eight generated leg sheets
disagrees: every design on ``Eight_legendary_fantasy_leg_armor_designs`` was
drawn -- and generated -- as a full harness ending in an armoured boot, so
``Legendary Leg Armor I``..``VIII`` each ship a pair of sabatons that a player
wearing boots would be wearing twice.

**Which sheets, and how that was settled.**  A foot is the one part of a leg
piece that reaches *forward* past the shin above it, so the side silhouette
says it plainly.  Measured against the six real boot sheets as a control, the
bottom slab of a boot is about twice as deep as the column above it; of the
eight leg sheets only the legendary one reads that way, on all eight of its
designs, and the rendered silhouettes agree -- legendary shows the boot
control's L-shaped foot and the other seven end flat at the ankle.

That measurement is *not* what selects a sheet here.  Taken as a threshold it
does not separate cleanly: a flared trouser cuff on the militia sheet reaches
almost as far forward as the shallowest legendary sabaton, and trimming a cuff
because it flared would quietly restyle a design nobody complained about.  The
sheets are therefore named below after looking at them, which is the same
bargain ``import_generated_equipment.SHEETS`` makes -- what a piece *is* is
authored, and only its geometry is measured.

**Where the cut lands** is measured, per design, because the eight sabatons are
different heights.  Walking up the forward profile from the floor, the toe's
reach falls away and settles at the shin's own minimum: that settling point is
the ankle, and it lands between 11% and 19% of each mesh's height.  Cutting
there leaves the piece ending at the ankle, where ``conform_equipment`` will
stretch it across ``SPAN["legs"]`` (0.184..1.088) instead of across a span that
was measuring to the toe -- so the trim also un-squashes the leg armour proper.

The cut is left open, like every other edge in this set: these are generated
shells with hundreds of boundary edges already, and the hem sits inside the
boot's own span (a boot reaches up to 0.320) where nothing can see it.

Only ``<piece>.glb`` is rewritten.  ``<piece>.glb.orig`` is the raw generator
export and stays as it is -- it is what marks a source as preprocessed for
``import_generated_equipment.roster`` and what the icon renderer prefers -- and
the pre-trim ``.glb`` is kept beside it as ``.glb.booted`` so this is
reversible.  A source that already has a ``.glb.booted`` is left alone, so the
tool is idempotent.

  python trim_generated_boots.py                  trim, and say what moved
  python trim_generated_boots.py --dry-run        measure only
  python trim_generated_boots.py --restore        put the sabatons back

Rebuild the wearable meshes afterwards -- the trim changes geometry only, so
the definitions do not move:

  python import_generated_equipment.py --sheet legendary_leg_armor --meshes-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

import conform_equipment as ce
import equipment_authoring as ea

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent.parent
GENERATED = PROJECT / "generate_models" / "meshy-armor-individual-glb"

#: Generated sheets whose leg pieces were drawn with the foot attached, and so
#: have to be cut back to the ankle before they can be worn as leg armour.  See
#: the note above on why this is a list and not a threshold.
BOOTED_SHEETS = ("Eight_legendary_fantasy_leg_armor_designs",)

#: Rows in the height profile.  400 over a unit-tall mesh is a 2.5 mm band --
#: finer than the generator's own triangles, so the profile is limited by the
#: mesh rather than by the sampling.
ROWS = 400

#: How far up to look for the ankle, as a fraction of the piece's height.  A
#: leg piece spans roughly the waist to the sole, so a third of it is well
#: above any boot and safely below the knee.
SEARCH = 0.35

#: How much of the toe's forward reach may survive at the cut.  The profile
#: falls from the toe to a plateau at the shin; taking the first row within a
#: sixth of that fall lands on the top of the boot rather than partway up it.
SETTLED = 0.15


def forward_profile(points: np.ndarray, triangles: np.ndarray,
                    rows: int = ROWS) -> tuple[float, float, np.ndarray]:
    """How far forward the filled side view reaches, per height band.

    Rasterised from the triangles rather than the vertices: a generated shell
    is hollow and sparse, and a point cloud read straight off it reports the
    gaps between triangles as the silhouette.
    """
    height = points[:, 1]
    low, high = float(height.min()), float(height.max())
    step = (high - low) / rows
    reach = np.full(rows, -np.inf)
    for triangle in triangles:
        corner = points[triangle]
        first = max(0, int((corner[:, 1].min() - low) / step))
        last = min(rows - 1, int((corner[:, 1].max() - low) / step))
        front = corner[:, 2].max()
        band = reach[first:last + 1]
        np.maximum(band, front, out=band)
    return low, high, reach


def ankle_of(points: np.ndarray, triangles: np.ndarray) -> tuple[float, float]:
    """World Y of the ankle, and the toe's reach above the shin that found it."""
    low, high, reach = forward_profile(points, triangles)
    span = high - low
    window = reach[:int(ROWS * SEARCH)]
    live = np.isfinite(window)
    toe = float(window[live][:12].max())
    shin = float(window[live].min())
    settled = shin + SETTLED * (toe - shin)
    rows = np.flatnonzero(live & (window <= settled))
    row = int(rows[0]) if len(rows) else int(ROWS * SEARCH)
    return low + row * (span / ROWS), (toe - shin) / span


def clip_above(points, normals, uvs, triangles, cut):
    """The part of the mesh at or above world Y `cut`, straddlers cut in two.

    Left open at the cut.  Capping it would be the odd thing to do here: these
    shells carry hundreds of boundary edges already, and the hem lands inside
    the boot that covers it.
    """
    keep = points[:, 1] >= cut
    out_points = list(points)
    out_normals = list(normals)
    out_uvs = list(uvs)
    made: dict[tuple[int, int], int] = {}

    def cross(inside: int, outside: int) -> int:
        """The vertex where the edge meets the cut, made once per edge."""
        key = (inside, outside) if inside < outside else (outside, inside)
        if key in made:
            return made[key]
        here, there = points[inside], points[outside]
        share = (cut - here[1]) / (there[1] - here[1])
        point = here + (there - here) * share
        point[1] = cut
        normal = normals[inside] + (normals[outside] - normals[inside]) * share
        length = float(np.linalg.norm(normal))
        out_points.append(point)
        out_normals.append(normal / length if length > 1e-9 else normals[inside])
        out_uvs.append(uvs[inside] + (uvs[outside] - uvs[inside]) * share)
        made[key] = len(out_points) - 1
        return made[key]

    kept: list[tuple[int, int, int]] = []
    for triangle in triangles:
        inside = [corner for corner in triangle if keep[corner]]
        if len(inside) == 3:
            kept.append(tuple(int(c) for c in triangle))
        elif len(inside) == 2:
            # Clipping one corner off leaves a quad; both halves keep the
            # triangle's winding by starting from the same new edge.
            at = next(n for n in range(3) if not keep[triangle[n]])
            gone, near, far = (int(triangle[at]), int(triangle[(at + 1) % 3]),
                               int(triangle[(at + 2) % 3]))
            first, second = cross(near, gone), cross(far, gone)
            kept.append((first, near, far))
            kept.append((first, far, second))
        elif len(inside) == 1:
            at = next(n for n in range(3) if keep[triangle[n]])
            stays, after, before = (int(triangle[at]), int(triangle[(at + 1) % 3]),
                                    int(triangle[(at + 2) % 3]))
            kept.append((stays, cross(stays, after), cross(stays, before)))

    if not kept:
        raise ValueError("the cut removed the whole mesh")
    faces = np.asarray(kept, dtype=np.int64)
    used = np.unique(faces)
    remap = np.full(len(out_points), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    return (np.asarray(out_points)[used], np.asarray(out_normals)[used],
            np.asarray(out_uvs)[used], remap[faces])


def trim(source: Path, *, dry_run: bool) -> str:
    backup = source.with_name(source.name + ".booted")
    if backup.exists():
        return "%-14s already trimmed" % source.stem.split("__")[-1]

    piece, png = ce.read_source(source)
    points, normals, uvs = piece.positions, piece.normals, piece.uvs
    triangles = piece.indices.reshape(-1, 3)
    cut, reach = ankle_of(points, triangles)
    low, high = float(points[:, 1].min()), float(points[:, 1].max())

    kept = clip_above(points, normals, uvs, triangles, cut)
    told = ("%-14s ankle at %5.1f%% of height, toe reached %.3f past the shin, "
            "%d -> %d triangles"
            % (source.stem.split("__")[-1], 100 * (cut - low) / (high - low),
               reach, len(triangles), len(kept[3])))
    if dry_run:
        return told

    glb = ea.EquipmentGLB(generator="Eloria trim_generated_boots")
    material = ce.textured_material(glb, source.stem, png)
    glb.mesh(source.stem, [glb.primitive(kept[0], kept[1], kept[2], kept[3],
                                         material)])
    source.replace(backup)
    glb.write(source)
    return told


def restore(source: Path) -> str:
    backup = source.with_name(source.name + ".booted")
    if not backup.exists():
        return "%-14s no backup to restore" % source.stem.split("__")[-1]
    backup.replace(source)
    return "%-14s restored" % source.stem.split("__")[-1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="cut the sabatons off generated leg pieces built with feet")
    parser.add_argument("--generated", type=Path, default=GENERATED,
                        help="directory of generated meshes")
    parser.add_argument("--sheet", default=None,
                        help="only this sheet stem, of the ones listed above")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--restore", action="store_true",
                        help="put back the pre-trim meshes")
    args = parser.parse_args()

    if not args.generated.is_dir():
        print("no generated meshes at %s" % args.generated)
        return 2
    sheets = [s for s in BOOTED_SHEETS if not args.sheet or s == args.sheet]
    if not sheets:
        print("not a sheet with boots built in: %s" % args.sheet)
        return 2

    for sheet in sheets:
        sources = sorted(args.generated.glob(sheet + "__*.glb"))
        print("%s -- %d piece(s)" % (sheet, len(sources)))
        for source in sources:
            print("  " + (restore(source) if args.restore
                          else trim(source, dry_run=args.dry_run)))
    if args.dry_run:
        print("\nnothing written (--dry-run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
