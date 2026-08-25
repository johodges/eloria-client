#!/usr/bin/env python3
"""Generate the Eloria map-editor toolbar atlas and individual source icons."""

from pathlib import Path
from PIL import Image, ImageDraw

CELL = 32
SCALE = 4
SIZE = CELL * SCALE
ATLAS = 256

ROOT = Path(__file__).resolve().parents[2]
TEXTURES = ROOT / "textures"
SOURCES = ROOT / "map_editor" / "toolbar_icons"

GOLD = (226, 184, 86, 255)
LIGHT = (255, 229, 150, 255)
TEAL = (29, 184, 191, 255)
BLUE = (31, 98, 135, 255)
RED = (202, 72, 65, 255)
DARK = (8, 20, 29, 255)
EDGE = (2, 9, 14, 255)

PLACEMENTS = {
    "mode_3d": (0, 0), "mode_2d": (1, 0), "mode_tile": (2, 0),
    "mode_light": (3, 0), "mode_map": (4, 0), "tool_kill": (6, 0),
    "tool_new": (7, 0), "tool_select": (0, 1), "tool_clone": (1, 1),
    "save_map": (2, 1), "open_map": (3, 1), "new_map": (4, 1),
    "mode_height": (5, 1), "mode_particles": (6, 1), "mode_eye_candy": (7, 1),
}


def pts(values):
    return [(int(x * SCALE), int(y * SCALE)) for x, y in values]


def icon_canvas():
    im = Image.new("RGBA", (SIZE, SIZE), DARK)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((1*SCALE, 1*SCALE, 30*SCALE, 30*SCALE), radius=5*SCALE,
                        fill=(12, 35, 46, 255), outline=(58, 104, 116, 255), width=SCALE)
    d.line(pts([(4, 27), (28, 27)]), fill=(3, 12, 18, 255), width=SCALE)
    return im, d


def line(d, xy, fill=GOLD, width=2):
    d.line(pts(xy), fill=EDGE, width=(width+2)*SCALE, joint="curve")
    d.line(pts(xy), fill=fill, width=width*SCALE, joint="curve")


def poly(d, xy, fill=BLUE, outline=GOLD, width=1):
    p = pts(xy)
    d.polygon(p, fill=fill)
    d.line(p + [p[0]], fill=outline, width=width*SCALE, joint="curve")


def draw_icon(name):
    im, d = icon_canvas()
    if name == "mode_3d":
        poly(d, [(16,5),(26,10),(16,16),(6,10)], BLUE)
        poly(d, [(6,10),(16,16),(16,27),(6,21)], (22,73,99,255))
        poly(d, [(16,16),(26,10),(26,21),(16,27)], (14,52,73,255))
    elif name == "mode_2d":
        poly(d, [(6,8),(24,6),(26,23),(8,26)], (26,89,108,255))
        line(d, [(9,20),(14,14),(18,18),(23,11)], TEAL, 2)
    elif name == "mode_tile":
        for y in (7,16):
            for x in (7,16):
                d.rectangle((x*SCALE,y*SCALE,(x+8)*SCALE,(y+8)*SCALE), fill=BLUE, outline=GOLD, width=SCALE)
    elif name == "mode_light":
        d.ellipse((10*SCALE,5*SCALE,22*SCALE,17*SCALE), fill=LIGHT, outline=GOLD, width=2*SCALE)
        line(d, [(16,2),(16,5)], LIGHT, 1); line(d, [(7,7),(10,9)], LIGHT, 1)
        line(d, [(25,7),(22,9)], LIGHT, 1); line(d, [(11,18),(13,22),(19,22),(21,18)], GOLD, 2)
        line(d, [(13,25),(19,25)], TEAL, 2)
    elif name == "mode_map":
        poly(d, [(5,7),(12,5),(20,8),(27,5),(27,24),(20,27),(12,24),(5,27)], (26,78,83,255))
        line(d, [(12,5),(12,24)], LIGHT, 1); line(d, [(20,8),(20,27)], LIGHT, 1)
        d.ellipse((17*SCALE,11*SCALE,23*SCALE,17*SCALE), fill=TEAL, outline=LIGHT, width=SCALE)
    elif name == "tool_select":
        poly(d, [(8,4),(24,17),(17,19),(14,27)], LIGHT, EDGE, 1)
        line(d, [(17,19),(23,26)], GOLD, 2)
    elif name == "tool_clone":
        d.rounded_rectangle((6*SCALE,9*SCALE,19*SCALE,24*SCALE), radius=2*SCALE, fill=BLUE, outline=GOLD, width=2*SCALE)
        d.rounded_rectangle((12*SCALE,5*SCALE,26*SCALE,20*SCALE), radius=2*SCALE, fill=(24,84,105,255), outline=LIGHT, width=2*SCALE)
    elif name == "tool_new":
        d.ellipse((5*SCALE,5*SCALE,27*SCALE,27*SCALE), fill=(21,72,88,255), outline=GOLD, width=2*SCALE)
        line(d, [(16,9),(16,23)], LIGHT, 3); line(d, [(9,16),(23,16)], LIGHT, 3)
    elif name == "tool_kill":
        d.ellipse((5*SCALE,5*SCALE,27*SCALE,27*SCALE), fill=(74,31,36,255), outline=RED, width=2*SCALE)
        line(d, [(10,10),(22,22)], LIGHT, 3); line(d, [(22,10),(10,22)], LIGHT, 3)
    elif name == "save_map":
        poly(d, [(7,5),(24,5),(27,8),(27,27),(5,27),(5,5)], (22,76,93,255))
        d.rectangle((10*SCALE,6*SCALE,21*SCALE,13*SCALE), fill=LIGHT, outline=EDGE, width=SCALE)
        d.rectangle((9*SCALE,18*SCALE,23*SCALE,27*SCALE), fill=BLUE, outline=GOLD, width=SCALE)
    elif name == "open_map":
        poly(d, [(4,11),(13,11),(16,14),(27,14),(24,26),(5,26)], (25,88,104,255))
        poly(d, [(5,8),(14,8),(17,11),(26,11),(27,14),(16,14),(13,11),(5,11)], (39,111,123,255))
    elif name == "new_map":
        poly(d, [(6,5),(21,5),(26,10),(26,27),(6,27)], (24,74,91,255))
        poly(d, [(21,5),(21,10),(26,10)], LIGHT)
        line(d, [(11,18),(21,18)], TEAL, 2); line(d, [(16,13),(16,23)], TEAL, 2)
    elif name == "mode_height":
        poly(d, [(4,25),(10,15),(15,20),(21,8),(28,25)], (31,92,83,255))
        line(d, [(7,23),(12,19),(16,22),(22,13),(26,23)], LIGHT, 1)
    elif name == "mode_particles":
        for x,y,r,c in [(9,20,3,GOLD),(15,12,3,TEAL),(22,18,4,LIGHT),(20,7,2,GOLD),(8,8,2,TEAL)]:
            d.ellipse(((x-r)*SCALE,(y-r)*SCALE,(x+r)*SCALE,(y+r)*SCALE), fill=c, outline=EDGE, width=SCALE)
    elif name == "mode_eye_candy":
        poly(d, [(16,3),(19,11),(27,14),(20,19),(21,28),(16,22),(11,28),(12,19),(5,14),(13,11)], TEAL, LIGHT, 1)
        d.ellipse((13*SCALE,11*SCALE,19*SCALE,17*SCALE), fill=LIGHT)
    return im.resize((CELL, CELL), Image.Resampling.LANCZOS)


def main():
    TEXTURES.mkdir(parents=True, exist_ok=True)
    SOURCES.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGB", (ATLAS, ATLAS), (8, 20, 29))
    for name, (col, row) in PLACEMENTS.items():
        icon = draw_icon(name)
        icon.save(SOURCES / f"{name}.png")
        atlas.paste(icon.convert("RGB"), (col * CELL, row * CELL))
    atlas.save(TEXTURES / "buttons.bmp", format="BMP")
    atlas.save(SOURCES / "buttons_atlas_preview.png")
    print(f"Wrote {TEXTURES / 'buttons.bmp'} and {len(PLACEMENTS)} source icons")


if __name__ == "__main__":
    main()
