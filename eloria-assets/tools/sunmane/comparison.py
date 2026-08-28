#!/usr/bin/env python3
"""Assemble the concept-versus-client comparison sheets.

Pairs each of the ten detail-board panels, and the aerial overview, with the
matching screenshot captured from the running Godot client, and writes both
per-panel sheets and one contact sheet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "eloria-assets" / "maps" / "nymara-regions" / "sunmane_steppe"
REFERENCES = PACKAGE / "references"
SHOTS = ROOT / "godot-client" / "test-artifacts" / "sunmane-steppe"
OUTPUT = PACKAGE / "comparison"

BOARD_GRID = (5, 2)

# panel index (row-major in the detail board), capture id, subject
PANELS = [
    (0, "p01-caravan-road", "Caravan road, wheat and riders"),
    (1, "p02-round-tent-camp", "Round-tent camp"),
    (2, "p03-seasonal-market", "Seasonal market"),
    (3, "p04-banner-shrine", "Banner shrine"),
    (4, "p05-caravanserai-gate", "Fortified gate"),
    (5, "p06-windmill", "Windmill and crop block"),
    (6, "p07-well-and-pens", "Well and horse pens"),
    (7, "golden-p08-standing-stones", "Standing stones at golden hour"),
    (8, "p09-steppe-overlook", "Steppe overlook"),
    (9, "p10-market-props", "Prop and material language"),
]

EXTRA = [
    ("great-hall", "Central hall"), ("gate-north", "North gate"),
    ("caravanserai-west", "West caravanserai"), ("coast-southwest", "Cove landing"),
    ("mesa-north", "Northern mesas"), ("burial-field", "Barrow field"),
    ("animal-pens", "Horse paddocks"), ("outpost-ridge", "Rider outpost"),
    ("gameplay-default", "Default gameplay camera"),
    ("gameplay-zoomed-out", "Maximum zoom-out"),
    ("golden-p09-steppe-overlook", "Overlook, golden hour"),
    ("golden-p08-standing-stones", "Standing stones, golden hour"),
]

CARD = (760, 428)
LABEL = 34


def board_panel(board: Image.Image, index: int) -> Image.Image:
    columns, rows = BOARD_GRID
    width = board.width // columns
    height = board.height // rows
    column, row = index % columns, index // columns
    return board.crop((column * width, row * height,
                       (column + 1) * width, (row + 1) * height))


def fit(image: Image.Image) -> Image.Image:
    return image.convert("RGB").resize(CARD, Image.LANCZOS)


def labelled(image: Image.Image, text: str) -> Image.Image:
    canvas = Image.new("RGB", (CARD[0], CARD[1] + LABEL), (22, 22, 24))
    canvas.paste(image, (0, LABEL))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 9), text, fill=(232, 228, 216))
    return canvas


def pair(reference: Image.Image, capture: Image.Image, title: str) -> Image.Image:
    sheet = Image.new("RGB", (CARD[0] * 2 + 12, CARD[1] + LABEL * 2 + 8), (22, 22, 24))
    sheet.paste(labelled(fit(reference), "concept reference"), (0, LABEL))
    sheet.paste(labelled(fit(capture), "Godot client"), (CARD[0] + 12, LABEL))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 10), title, fill=(255, 214, 138))
    return sheet


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    board = Image.open(REFERENCES / "00-concept-detail-board.png")
    aerial = Image.open(REFERENCES / "01-aerial-overview.png")
    written: list[dict] = []

    missing = []
    for index, capture_id, subject in PANELS:
        capture_path = SHOTS / f"{capture_id}.png"
        if not capture_path.exists():
            missing.append(capture_id)
            continue
        sheet = pair(board_panel(board, index), Image.open(capture_path),
                     f"Panel {index + 1} - {subject}")
        # WebP: these are review images, and a lossless PNG set costs about
        # 20 MiB in the tree for no extra information.
        name = f"panel-{index + 1:02d}-{capture_id}.webp"
        sheet.save(OUTPUT / name, quality=90, method=5)
        written.append({"panel": index + 1, "subject": subject,
                        "capture": capture_id, "sheet": f"comparison/{name}"})

    if (SHOTS / "aerial-overview.png").exists():
        sheet = pair(aerial, Image.open(SHOTS / "aerial-overview.png"),
                     "Aerial overview - regional composition")
        sheet.save(OUTPUT / "aerial-overview.webp", quality=90, method=5)
        written.append({"panel": 0, "subject": "Aerial overview",
                        "capture": "aerial-overview",
                        "sheet": "comparison/aerial-overview.webp"})
    else:
        missing.append("aerial-overview")

    # Landmarks the ten panels do not cover, as a plain contact sheet.
    tiles = []
    for capture_id, subject in EXTRA:
        path = SHOTS / f"{capture_id}.png"
        if path.exists():
            tiles.append(labelled(fit(Image.open(path)), subject))
        else:
            missing.append(capture_id)
    if tiles:
        columns = 3
        rows = (len(tiles) + columns - 1) // columns
        contact = Image.new("RGB", (columns * (CARD[0] + 8), rows * (CARD[1] + LABEL + 8)),
                            (22, 22, 24))
        for index, tile in enumerate(tiles):
            contact.paste(tile, ((index % columns) * (CARD[0] + 8),
                                 (index // columns) * (CARD[1] + LABEL + 8)))
        contact.save(OUTPUT / "additional-landmarks.webp", quality=90, method=5)
        written.append({"panel": None, "subject": "Additional landmarks",
                        "capture": "contact-sheet",
                        "sheet": "comparison/additional-landmarks.webp"})

    index_path = OUTPUT / "index.json"
    index_path.write_text(json.dumps(
        {"schemaVersion": 1,
         "references": {"detailBoard": "references/00-concept-detail-board.png",
                        "aerial": "references/01-aerial-overview.png"},
         "captureSource": ("godot-client/tests/integration/"
                           "rendered_sunmane_steppe.gd, Godot 4.7.2, "
                           "gl_compatibility renderer"),
         "sheets": written, "missing": missing}, indent=2) + "\n")
    print(f"wrote {len(written)} comparison sheets to {OUTPUT}")
    if missing:
        print("missing captures:", ", ".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
