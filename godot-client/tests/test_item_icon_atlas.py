#!/usr/bin/env python3
"""Grid and coverage checks for the inventory item icon atlases.

Added 2026-08-28 for Eloria Client.

``ItemAtlas`` slices every icon at ``(id % columns) * cell, (id / columns) *
cell``.  The shipped atlases were pasted below that grid, so icons from id 25
upwards rendered with a slice of their neighbour, and the sixteen Nymara
materials were flat placeholder polygons.  These tests pin the grid, the icon
coverage and the fallback so a future atlas edit cannot silently drift again.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import struct
import unittest

# The generated armour set is defined once, by the importer's roster, and this
# suite counts its icons from there so the two cannot disagree.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "eloria-assets" / "tools"))
FIRST_GENERATED_IMAGE_ID = 118


def generated_piece_count() -> int:
    # Both generated sets: the armour from 118 and the weapons and shields
    # after it, handed out from one run of numbers so the painted prefix stays
    # contiguous.  Counting only one of them would leave the other's cells
    # looking like a gap the atlas had failed to fill.
    import import_generated_equipment as armour
    import import_generated_weapons as weapons
    return len(armour.roster()) + len(weapons.roster())

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "godot-client"

# The frame's corner brackets sit within this many pixels of the cell edge, and
# the plate behind them is opaque all the way out.
FRAME_BAND = 6
FIRST_NYMARA_IMAGE_ID = 85


def read_png(path: Path):
    from PIL import Image
    import numpy as np
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)


def read_dds(path: Path):
    import numpy as np
    raw = path.read_bytes()
    header = struct.unpack("<31I", raw[4:128])
    height, width = header[2], header[3]
    pixels = np.frombuffer(raw[128:128 + width * height * 4],
                           dtype=np.uint8).reshape(height, width, 4)
    return np.dstack((pixels[:, :, 2], pixels[:, :, 1], pixels[:, :, 0],
                      pixels[:, :, 3])).astype(np.int16)


class ItemIconAtlasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((CLIENT / "data/items/atlases.json").read_text())
        cls.cell = int(cls.config["cellSize"][0])
        cls.columns = int(cls.config["columns"])
        cls.per_atlas = int(cls.config["imagesPerAtlas"])
        cls.atlases = [read_png(CLIENT / path.removeprefix("res://"))
                       for path in cls.config["atlases"]]

    def cell_for(self, image_id: int):
        atlas, local = divmod(image_id, self.per_atlas)
        row, column = divmod(local, self.columns)
        return self.atlases[atlas][row * self.cell:(row + 1) * self.cell,
                                   column * self.cell:(column + 1) * self.cell]

    def test_atlas_declares_its_painted_range(self) -> None:
        # 0-117 are the painted originals and everything above them is the
        # generated armour set, one rendered cell per piece
        # (tools/build_item_icon_atlases.py).  Counted from the roster rather
        # than written down: the set grew from sixty pieces to two hundred and
        # fifty-six, and a number pinned here only says what the set used to
        # be.  What matters is that the painted prefix stays contiguous with
        # the generated range and that the declared count covers all of it.
        self.assertEqual(FIRST_GENERATED_IMAGE_ID + generated_piece_count(),
                         self.config["imageCount"])
        self.assertEqual(117, self.config["fallbackImageId"])
        capacity = len(self.config["atlases"]) * self.per_atlas
        self.assertLessEqual(self.config["imageCount"], capacity)

    def test_every_declared_icon_is_painted(self) -> None:
        for image_id in range(self.config["imageCount"]):
            with self.subTest(image_id=image_id):
                cell = self.cell_for(image_id)
                opaque = (cell[:, :, 3] > 8).mean()
                self.assertGreater(opaque, .90,
                                   f"image {image_id} is not a painted cell")

    def test_icons_sit_on_the_sampling_grid(self) -> None:
        """A misaligned paste shows as a transparent or black band at one edge.

        Each icon's plate reaches its own cell border on every side, so any
        residual offset leaves a dead strip this catches.
        """
        band = FRAME_BAND
        for image_id in range(self.config["imageCount"]):
            cell = self.cell_for(image_id)
            alpha = cell[:, :, 3]
            edges = {
                "top": alpha[:band].mean(), "bottom": alpha[-band:].mean(),
                "left": alpha[:, :band].mean(), "right": alpha[:, -band:].mean()}
            for edge, value in edges.items():
                with self.subTest(image_id=image_id, edge=edge):
                    self.assertGreater(value, 200,
                                       f"image {image_id} has a dead {edge} edge")

    def test_nymara_materials_are_no_longer_flat_placeholders(self) -> None:
        """The placeholders were single-colour polygons on an empty cell."""
        import numpy as np
        for image_id in range(FIRST_NYMARA_IMAGE_ID, self.config["fallbackImageId"]):
            cell = self.cell_for(image_id)
            with self.subTest(image_id=image_id):
                colours = len(np.unique(cell.reshape(-1, 4), axis=0))
                self.assertGreater(colours, 600,
                                   f"image {image_id} is still flat art")

    def test_client_png_matches_the_authored_dds(self) -> None:
        import numpy as np
        for index, path in enumerate(self.config["atlases"]):
            source = ROOT / f"eloria-assets/ui/items/items{index + 1}.dds"
            with self.subTest(atlas=path):
                self.assertTrue(np.array_equal(read_dds(source), self.atlases[index]))


if __name__ == "__main__":
    unittest.main()
