#!/usr/bin/env python3
"""Build the concept-to-client comparison sheets and report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
CAPTURES = PACKAGE / "references" / "captures"
BOARD = PACKAGE / "references" / "00-concept-detail-board.png"
AERIAL = PACKAGE / "references" / "01-concept-aerial-overview.png"
OUT = PACKAGE / "references" / "comparisons"

PANELS = {
    1: ("01-forest-road", "Leaf-covered forest road under the amber canopy"),
    2: ("02-moot-hall", "Multi-storey timber-and-stone civic hall"),
    3: ("03-forest-lodge", "Player-scale forest lodge with porch and workshop"),
    4: ("04-hollow-tree", "Colossal hollow-tree entrance"),
    5: ("05-high-bridge", "High stone bridge over a rocky watercourse"),
    6: ("06-root-arch", "Root-overgrown ancient stone arch"),
    7: ("07-garden-terrace", "Formal garden: fountain, statues, rotunda, terrace"),
    8: ("08-canopy-amber", "Canopy platform and amber working"),
    9: ("09-high-overlook", "High overlook toward the settlement"),
    10: ("10-material-study", "Material study: amber, carved wood, moss, leaves"),
}


def _label(image: Image.Image, text: str, height: int = 26) -> Image.Image:
    out = Image.new("RGB", (image.width, image.height + height), (16, 16, 18))
    out.paste(image, (0, height))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    draw.text((8, 5), text, fill=(226, 214, 190), font=font)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    board = Image.open(BOARD).convert("RGB")
    panel_w = board.width // 5
    panel_h = board.height // 2

    cell = (560, 380)
    rows = []
    for number in range(1, 11):
        column = (number - 1) % 5
        row = 0 if number <= 5 else 1
        concept = board.crop((column * panel_w, row * panel_h,
                              (column + 1) * panel_w, (row + 1) * panel_h))
        concept = concept.resize(cell, Image.LANCZOS)
        name, caption = PANELS[number]
        capture_path = CAPTURES / f"{name}.png"
        if not capture_path.exists():
            capture_path = CAPTURES / f"{name}.webp"
        if capture_path.exists():
            capture = Image.open(capture_path).convert("RGB")
            capture = capture.resize(cell, Image.LANCZOS)
        else:
            capture = Image.new("RGB", cell, (40, 30, 24))
        pair = Image.new("RGB", (cell[0] * 2 + 12, cell[1]), (16, 16, 18))
        pair.paste(concept, (0, 0))
        pair.paste(capture, (cell[0] + 12, 0))
        rows.append(_label(pair, f"Panel {number} - {caption}   "
                                 f"[left: concept | right: Amberwood build]"))

    sheet_height = sum(r.height + 8 for r in rows)
    sheet = Image.new("RGB", (rows[0].width, sheet_height), (10, 10, 12))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 8
    sheet.save(OUT / "panel-comparison.png")
    sheet.convert("RGB").save(OUT / "panel-comparison.webp", "WEBP", quality=88, method=5)
    (OUT / "panel-comparison.png").unlink()

    # aerial pair
    aerial_concept = Image.open(AERIAL).convert("RGB")
    aerial_name = CAPTURES / "00-aerial-overview.png"
    if not aerial_name.exists():
        aerial_name = CAPTURES / "00-aerial-overview.webp"
    aerial_capture = Image.open(aerial_name).convert("RGB")
    width = 900
    a = aerial_concept.resize((width, int(width * aerial_concept.height
                                          / aerial_concept.width)), Image.LANCZOS)
    b = aerial_capture.resize((width, int(width * aerial_capture.height
                                          / aerial_capture.width)), Image.LANCZOS)
    pair = Image.new("RGB", (width, a.height + b.height + 12), (10, 10, 12))
    pair.paste(a, (0, 0))
    pair.paste(b, (0, a.height + 12))
    _label(pair, "Aerial overview  [top: concept | bottom: Amberwood build]").save(
        OUT / "aerial-comparison.png")
    Image.open(OUT / "aerial-comparison.png").convert("RGB").save(
        OUT / "aerial-comparison.webp", "WEBP", quality=88, method=5)
    (OUT / "aerial-comparison.png").unlink()

    # contact sheet of everything else
    index = json.loads((CAPTURES / "index.json").read_text())
    extras = [entry for entry in index if entry["panel"] is None]
    cols = 3
    thumb = (420, 280)
    sheet2 = Image.new("RGB", (cols * thumb[0], ((len(extras) + cols - 1) // cols)
                               * (thumb[1] + 24)), (10, 10, 12))
    for i, entry in enumerate(extras):
        path = CAPTURES / entry["file"]
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        image.thumbnail(thumb)
        tile = _label(image, entry["id"], 22)
        sheet2.paste(tile, ((i % cols) * thumb[0], (i // cols) * (thumb[1] + 24)))
    sheet2.convert("RGB").save(OUT / "landmark-contact-sheet.webp", "WEBP",
                               quality=86, method=5)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
