#!/usr/bin/env python3
"""Render concept-versus-client review boards for every invasion creature."""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from build_production_invasion_creatures import INVASION_CREATURES
from render_native_glb_preview import render


def _concept_tile(path: Path, column: int, row: int, size: int) -> Image.Image:
    sheet = Image.open(path).convert("RGB")
    rows = 4 if path.name == "amberwood_forest_spirits_creatures_sheet.png" else 3
    cell_width = sheet.width / 4.0
    cell_height = sheet.height / float(rows)
    # A slight inset removes adjacent silhouettes while retaining antlers,
    # wings, and tails that intentionally occupy most of their concept cell.
    inset_x, inset_y = cell_width * .018, cell_height * .018
    box = (
        round(column * cell_width + inset_x),
        round(row * cell_height + inset_y),
        round((column + 1) * cell_width - inset_x),
        round((row + 1) * cell_height - inset_y),
    )
    tile = sheet.crop(box)
    return ImageOps.contain(tile, (size, size), Image.Resampling.LANCZOS)


def _client_tile(path: Path, size: int) -> Image.Image:
    """Crop the centered creature from the real 1280x720 Godot review frame."""
    image = Image.open(path).convert("RGB")
    crop_size = min(image.width, image.height)
    left = (image.width - crop_size) // 2
    top = (image.height - crop_size) // 2
    return ImageOps.fit(
        image.crop((left, top, left + crop_size, top + crop_size)),
        (size, size), Image.Resampling.LANCZOS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_repo = Path(__file__).resolve().parents[2]
    parser.add_argument("--concept-root", required=True, type=Path)
    parser.add_argument(
        "--model-root",
        type=Path,
        default=default_repo / "godot-client/assets/actors/native/creatures",
    )
    parser.add_argument(
        "--render-root",
        type=Path,
        help="Optional real Godot render directory; falls back to software previews.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--columns", type=int, default=4)
    args = parser.parse_args()

    tile_size, label_height, header_height = 300, 42, 34
    columns = max(1, args.columns)
    rows = math.ceil(len(INVASION_CREATURES) / columns)
    pair_width = tile_size * 2
    board = Image.new(
        "RGB",
        (pair_width * columns, header_height + (tile_size + label_height) * rows),
        (19, 24, 27),
    )
    draw = ImageDraw.Draw(board)
    font = ImageFont.load_default(size=15)
    header_font = ImageFont.load_default(size=18)
    for column in range(columns):
        left = column * pair_width
        draw.text((left + tile_size // 2 - 38, 7), "CONCEPT", font=header_font,
                  fill=(226, 181, 92))
        draw.text((left + tile_size + tile_size // 2 - 31, 7), "CLIENT", font=header_font,
                  fill=(91, 193, 210))
    for index, spec in enumerate(INVASION_CREATURES):
        column = index % columns
        row = index // columns
        x = column * pair_width
        y = header_height + row * (tile_size + label_height)
        concept_path = args.concept_root / spec.concept_sheet
        if not concept_path.is_file():
            raise FileNotFoundError(concept_path)
        concept = _concept_tile(concept_path, *spec.concept_slot, tile_size)
        concept_canvas = Image.new("RGB", (tile_size, tile_size), (29, 36, 39))
        concept_canvas.paste(concept, ((tile_size - concept.width) // 2,
                                       (tile_size - concept.height) // 2))
        render_path = (args.render_root / f"{spec.actor_type:03d}-{spec.slug}.png"
                       if args.render_root is not None else None)
        client = (_client_tile(render_path, tile_size)
                  if render_path is not None and render_path.is_file()
                  else render(args.model_root / f"{spec.slug}.glb", tile_size))
        board.paste(concept_canvas, (x, y))
        board.paste(client, (x + tile_size, y))
        draw.line((x + tile_size, y, x + tile_size, y + tile_size), fill=(72, 83, 86), width=2)
        label = f"{spec.actor_type}  {spec.label}  ·  {spec.region}"
        draw.text((x + 12, y + tile_size + 11), label, font=font,
                  fill=(216, 225, 221))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    board.save(args.output, optimize=True)


if __name__ == "__main__":
    main()
