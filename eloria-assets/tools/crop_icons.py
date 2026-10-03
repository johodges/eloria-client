#!/usr/bin/env python3
"""The island crops' inventory icons: the fifth set packed into the atlases.

Added 2026-10-02 for Eloria Client.

The south-west isle grows two signature crops the server does not ship yet,
Olive and Lemon (island content plan, harvest plan section 5). A harvested
item reaches the bag as its `image_id` and nothing else, so each crop needs a
painted cell before the server hands one out - otherwise the bag draws the
unknown-item glyph for it, which is what happened to the regional harvest
resources until `paint_material_icons.py` painted them.

Like the potion shelf, the crops have no mesh worth rendering at 50 pixels (a
harvest node is a shrub, the item is the fruit), so they are painted here, in
the same height-field light as the Nymara material icons and on the same
empty-slot plate as every generated set since 118.

Ids follow the ledger's rules (memory `eloria-item-economy`): image ids
continue the atlas's single contiguous run after the distillates' 593, and
this roster is append only. The roster owns IMAGE ids only. The server's
items.txt owns the item ids; the island content plan proposes Olive = item
1860 and Lemon = item 1861, recorded in SERVER_ITEM_IDS so potion_icons.py
continues after them instead of handing the next distillate the same ids.
The server stream appends the two [item] blocks AFTER the
`# --- end potion and magic supplies ---` marker, never inside that fence:
potion_icons.py rewrites the fenced block whole and would delete them.
Nothing here writes into the server checkout.

  python crop_icons.py --preview <dir>   paint the icons to a directory
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from paint_material_icons import _over, _rotate, _shade
import potion_icons

#: The first icon after the distillates (potion_icons.DISTILLATE_IMAGE_ID + 10).
FIRST_IMAGE_ID = 594
#: The item ids the server stream gives the crops (island content plan; the
#: server's items.txt owns them). Recorded so the potion shelf, which writes
#: item ids into the server's fence, never hands one out again.
SERVER_ITEM_IDS = {"Olive": 1860, "Lemon": 1861}

CELL = 50
#: Painted at four times the cell and reduced, as the potion shelf is.
SS = 4


class Crop:
    """A crop's icon. Its item - name, item id, food value, description - is
    the server's; the client owns only the picture and the id it sits at."""
    __slots__ = ("name", "shape", "image_id")

    def __init__(self, name: str, shape: str):
        self.name, self.shape = name, shape
        self.image_id = 0  # assigned by roster order

    @property
    def slug(self) -> str:
        return self.name.casefold().replace(" ", "_")


#: Order is the id order: append only.
CROPS = [
    Crop("Olive", "olive_sprig"),
    Crop("Lemon", "lemon"),
]

for index, crop in enumerate(CROPS):
    crop.image_id = FIRST_IMAGE_ID + index


def roster() -> list[Crop]:
    """Every crop, in the fixed order that owns its icon ids."""
    return list(CROPS)


# ---------------------------------------------------------------------------
# painting
# ---------------------------------------------------------------------------

def _grid(size: int):
    axis = (np.arange(size) + .5) / size * 2. - 1.
    return np.meshgrid(axis, axis)


def _ellipse(size: int, cx: float, cy: float, rx: float, ry: float,
             angle: float = 0., power: float = 2.):
    """A rounded solid's height field, rotated by `angle` (radians)."""
    x, y = _grid(size)
    x, y = x - cx, y - cy
    cos, sin = math.cos(angle), math.sin(angle)
    u, v = x * cos + y * sin, -x * sin + y * cos
    radial = np.abs(u / rx) ** power + np.abs(v / ry) ** power
    mask = radial <= 1.
    # Heights scale with the canvas so `_shade`'s per-pixel gradient lights a
    # supersampled solid the way it lights one painted at cell size.
    height = np.where(mask, np.sqrt(np.clip(1. - radial, 0., 1.)) * min(rx, ry), 0.)
    return height * (size / CELL), mask


def _stroke(size: int, start, end, width: float):
    """A twig: a flat-topped band from `start` to `end` in unit coordinates."""
    x, y = _grid(size)
    a, b = np.asarray(start), np.asarray(end)
    along = b - a
    length = float(np.linalg.norm(along))
    t = np.clip(((x - a[0]) * along[0] + (y - a[1]) * along[1]) / length ** 2, 0., 1.)
    distance = np.hypot(x - (a[0] + t * along[0]), y - (a[1] + t * along[1]))
    mask = distance <= width / 2.
    height = np.where(mask, np.sqrt(np.clip(1. - (distance / (width / 2.)) ** 2, 0., 1.))
                      * width * .5, 0.)
    return height * (size / CELL), mask


def _leaf(layer, size, cx, cy, angle, length, width, base, accent):
    height, mask = _ellipse(size, cx, cy, width, length, angle, power=1.5)
    layer = _over(layer, _shade(height, mask, base, accent, gloss=.45, rim=.24))
    # The midrib catches the light along the leaf's long axis.
    tip = _rotate(np.array([[0., -length * .85], [0., length * .85]]), -angle)
    rib, rib_mask = _stroke(size, tip[0] + (cx, cy), tip[1] + (cx, cy), .022)
    return _over(layer, _shade(rib, rib_mask & mask, accent, (255, 255, 255),
                               gloss=.3, rim=.0))


def _olive_sprig(size: int) -> np.ndarray:
    layer = np.zeros((size, size, 4))
    twig = (88, 66, 46), (150, 118, 84)
    layer = _over(layer, _shade(*_stroke(size, (-.70, -.54), (.46, .36), .065),
                                *twig, gloss=.2))
    silver = (112, 132, 92), (196, 210, 178)
    for cx, cy, angle in ((-.34, -.50, -1.05), (.07, -.25, -.80), (.48, -.04, -1.30)):
        layer = _leaf(layer, size, cx, cy, angle, .42, .10, *silver)
    # Three ripe olives and one still green: ripe ones are the isle's harvest,
    # the green one keeps a dark cluster from reading as grapes.
    for cx, cy, angle, base, accent in (
            (-.36, .09, .5, (70, 38, 64), (176, 132, 170)),
            (.00, .32, .2, (62, 34, 58), (170, 128, 166)),
            (.36, .56, .4, (78, 44, 70), (182, 140, 176)),
            (-.05, -.05, .3, (120, 134, 50), (214, 222, 140))):
        height, mask = _ellipse(size, cx, cy, .20, .26, angle)
        layer = _over(layer, _shade(height, mask, base, accent, gloss=.95,
                                    shininess=44., rim=.30))
    return layer


def _lemon(size: int) -> np.ndarray:
    layer = np.zeros((size, size, 4))
    angle = -.55
    yellow, highlight = (236, 196, 46), (255, 244, 170)
    body, body_mask = _ellipse(size, .02, .10, .62, .43, angle, power=2.1)
    axis = np.array([math.cos(angle), math.sin(angle)])
    for side in (-1., 1.):
        nub_x, nub_y = np.array([.02, .10]) + axis * side * .65
        nub, nub_mask = _ellipse(size, nub_x, nub_y, .11, .085, angle)
        body, body_mask = np.maximum(body, nub * .9), body_mask | nub_mask
    layer = _over(layer, _shade(body, body_mask, yellow, highlight, gloss=.70,
                                shininess=30., rim=.30))
    # Pitted rind: a fine stipple the light picks out on the lit side.
    x, y = _grid(size)
    pits = (np.sin(x * 90.) * np.sin(y * 84.)) > .82
    layer = _over(layer, _shade(np.zeros((size, size)), pits & body_mask,
                                (214, 170, 34), (214, 170, 34), gloss=0., rim=0.))
    stem_end = np.array([.02, .10]) + axis * .74
    layer = _over(layer, _shade(*_stroke(size, stem_end, stem_end + (.06, -.12), .05),
                                (96, 78, 48), (150, 128, 82), gloss=.2))
    return _leaf(layer, size, stem_end[0] - .24, stem_end[1] - .20, .95, .30, .13,
                 (70, 116, 50), (156, 196, 112))


PAINTERS = {"olive_sprig": _olive_sprig, "lemon": _lemon}


def paint(crop: Crop) -> Image.Image:
    """One 50x50 cell: the shared plate with this crop on it."""
    plate = Image.open(potion_icons.TEMPLATE).convert("RGBA")
    size = CELL * SS
    art = PAINTERS[crop.shape](size)
    art = Image.fromarray(np.clip(art, 0, 255).astype(np.uint8), "RGBA")
    inset = int(CELL * .86)
    art = art.resize((inset, inset), Image.LANCZOS)
    layer = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    origin = (CELL - inset) // 2
    layer.paste(art, (origin, origin))
    # A soft contact shadow seats the crop on the plate, as on the materials.
    alpha = np.asarray(layer.split()[3], dtype=np.float64) / 255.
    shadow = alpha
    for _ in range(3):
        shadow = (shadow + np.roll(shadow, 1, 0) + np.roll(shadow, -1, 0)
                  + np.roll(shadow, 1, 1) + np.roll(shadow, -1, 1)) / 5.
    shadow = np.roll(np.roll(shadow, 2, 0), 2, 1) * .5
    base = np.asarray(plate, dtype=np.float64)
    frame = base[:, :, 3] > 8
    base[:, :, :3] *= (1. - shadow[..., None] * frame[..., None])
    plate = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    return Image.alpha_composite(plate, layer)


def main() -> int:
    ap = argparse.ArgumentParser(description="paint the island crops' icons")
    ap.add_argument("--preview", type=Path, required=True,
                    help="write each painted icon to this directory")
    args = ap.parse_args()
    crops = roster()
    args.preview.mkdir(parents=True, exist_ok=True)
    for crop in crops:
        paint(crop).save(args.preview / ("%s.png" % crop.slug))
        print("  %-8s icon %d" % (crop.name, crop.image_id))
    print("previews in %s" % args.preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
