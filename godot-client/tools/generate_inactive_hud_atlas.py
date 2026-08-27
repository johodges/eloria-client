#!/usr/bin/env python3
"""Build the inactive HUD atlas by removing the baked gold corner markers."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "ui" / "eloria_gamebuttons.png"
DESTINATION = ROOT / "assets" / "ui" / "eloria_gamebuttons_inactive.png"
CELL_SIZE = 32
CORNER_RADIUS = 11


def is_corner_pixel(x: int, y: int) -> bool:
    edge = CELL_SIZE - 1
    return min(x + y, edge - x + y, x + edge - y, edge - x + edge - y) < CORNER_RADIUS


def main() -> None:
    image = Image.open(SOURCE).convert("RGBA")
    pixels = image.load()
    for atlas_y in range(image.height):
        for atlas_x in range(image.width):
            local_x = atlas_x % CELL_SIZE
            local_y = atlas_y % CELL_SIZE
            if not is_corner_pixel(local_x, local_y):
                continue
            red, green, blue, _alpha = pixels[atlas_x, atlas_y]
            pixels[atlas_x, atlas_y] = (red, green, blue, 0)
    image.save(DESTINATION, optimize=True)


if __name__ == "__main__":
    main()
