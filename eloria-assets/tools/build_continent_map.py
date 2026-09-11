#!/usr/bin/env python3
"""Compose the continent map from the regions' own tab maps, and write the
client's cartography.

    python eloria-assets/tools/build_continent_map.py [--check]

The Tab map shows the map the player is standing on the way the client draws
it: straight down, north up, one metre a pixel. Every exterior region ships
that same picture of itself as `minimap.webp` (see `unify_minimap_scale.py`),
so the continent can be the real thing - each region's tab map laid on one
canvas, to scale, in the arrangement `continent-layout.json` gives - and a
region a player clicks on it can open as the tab map they would see standing
there, not a painting of what the region was meant to look like.

Two files are written:

* `maps/nymara-regions/continent-map.webp`, the continent as one picture;
* `godot-client/data/maps/cartography.json`, what the client needs to use it -
  the rectangle each region occupies on that picture (its click target), the
  region's own tab-map image, the pixels of it the live Tab map frames, and
  the world coordinates of that framing so the sidebar can name the tile
  under the cursor.

The framing follows `map_view.gd` exactly - `mapBounds`, then
`playableBounds`, then the server's addressable rectangle, then the mesh
bounds - so a preview shows what the player will see on arrival: Four Gates
without its backdrop rim, the Sunmane steppe without the landform past its
last tile.

`--check` builds everything in memory and exits non-zero when the checked-in
cartography or the continent picture is stale: a region redrew its minimap, a
region moved on the layout, or the JSON was edited by hand. It is what
`godot-client/tests/test_cartography.py` runs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "godot-client" / "data" / "maps" / "registry.json"
LAYOUT = ROOT / "eloria-assets" / "maps" / "nymara-regions" / "continent-layout.json"
CONNECTIONS = LAYOUT.with_name("region-connections.json")
CONTINENT_IMAGE = ROOT / "eloria-assets" / "maps" / "nymara-regions" / "continent-map.webp"
CARTOGRAPHY = ROOT / "godot-client" / "data" / "maps" / "cartography.json"
RESOURCE_PREFIX = "res://../"
## The same encoding the region minimaps use.
WEBP_QUALITY = 92
SCHEMA_VERSION = 2


def resource_to_path(resource: str) -> Path:
    """`res://../eloria-assets/x` is the repository's `eloria-assets/x`."""
    if not resource.startswith(RESOURCE_PREFIX):
        raise SystemExit(f"not a repository resource path: {resource}")
    return ROOT / resource[len(RESOURCE_PREFIX):]


def path_to_resource(path: Path) -> str:
    return RESOURCE_PREFIX + path.resolve().relative_to(ROOT).as_posix()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def framing(manifest: dict) -> tuple[float, float, float, float]:
    """The X/Z rectangle the live Tab map frames, as (min_x, min_z, max_x, max_z).

    The precedence is `map_view.gd`'s `bounds_for`: a map that states its own
    extent is believed over the mesh, and the server's addressable rectangle
    stands in for the older packages that never declared one.
    """
    asset = manifest.get("asset", {})
    for key in ("mapBounds", "playableBounds"):
        bounds = asset.get(key, {})
        low, high = bounds.get("min"), bounds.get("max")
        if isinstance(low, list) and isinstance(high, list) and len(low) == 3 and len(high) == 3:
            if float(high[0]) > float(low[0]) and float(high[2]) > float(low[2]):
                return float(low[0]), float(low[2]), float(high[0]), float(high[2])
    addressable = manifest.get("coordinateTransform", {}).get("addressableWorldBounds", {})
    low, high = addressable.get("min"), addressable.get("max")
    if isinstance(low, list) and isinstance(high, list) and len(low) == 2 and len(high) == 2:
        return float(low[0]), float(low[1]), float(high[0]), float(high[1])
    bounds = asset.get("bounds", {})
    low, high = bounds.get("min"), bounds.get("max")
    if isinstance(low, list) and isinstance(high, list) and len(low) == 3 and len(high) == 3:
        return float(low[0]), float(low[2]), float(high[0]), float(high[2])
    raise SystemExit("manifest declares no bounds to frame")


def tab_map_crop(minimap: dict, frame: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """The pixels of the minimap image that show `frame`, as (x, y, w, h)."""
    scale = float(minimap.get("pixelsPerMetre", 1.0))
    low = minimap["worldMin"]
    width, height = (int(value) for value in minimap["imageSize"])
    x0 = int(round((frame[0] - float(low[0])) * scale))
    y0 = int(round((frame[1] - float(low[1])) * scale))
    x1 = int(round((frame[2] - float(low[0])) * scale))
    y1 = int(round((frame[3] - float(low[1])) * scale))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(width, x1), min(height, y1)
    if x1 <= x0 or y1 <= y0:
        raise SystemExit("the live map's framing lies outside the minimap image")
    return x0, y0, x1 - x0, y1 - y0


def crop_world(minimap: dict, crop: tuple[int, int, int, int]) -> tuple[list[float], list[float]]:
    """The world X/Z rectangle a pixel crop covers, so a pixel maps back to a tile."""
    scale = float(minimap.get("pixelsPerMetre", 1.0))
    low = minimap["worldMin"]
    x, y, w, h = crop
    return ([float(low[0]) + x / scale, float(low[1]) + y / scale],
            [float(low[0]) + (x + w) / scale, float(low[1]) + (y + h) / scale])


def registry_entries(registry: dict, layout: dict) -> list[tuple[str, dict]]:
    """The laid-out regions in the registry's order, each with its manifest path."""
    maps = registry.get("maps", {})
    missing = [key for key in layout["regions"] if key not in maps]
    if missing:
        raise SystemExit(f"layout names maps the registry does not have: {missing}")
    entries = []
    for key, entry in maps.items():
        if key in layout["regions"]:
            entries.append((key, entry))
    return entries


def atlas_connections(layout: dict) -> list[dict]:
    """Draw only actual graph edges; bends route ferries around unrelated land."""
    scale = float(layout['metresPerPixel'])
    result = []
    for link in load_json(CONNECTIONS)['connections']:
        a, b = link['from'], link['to']
        if a not in layout['regions'] or b not in layout['regions']:
            continue
        key = a + '--' + b
        points = [layout['regions'][a], *layout.get('routeBends', {}).get(key, []), layout['regions'][b]]
        result.append({'from': a, 'to': b, 'type': link['type'],
                       'points': [[round(float(v)/scale, 3) for v in p] for p in points]})
    return result


def compose(layout: dict, registry: dict) -> tuple[dict, list[dict]]:
    """The cartography document, and what to paste where to draw the picture."""
    metres_per_pixel = float(layout["metresPerPixel"])
    canvas_w, canvas_h = (int(round(float(v) / metres_per_pixel)) for v in layout["canvasMetres"])
    regions: list[dict] = []
    tiles: list[dict] = []
    sources: dict[str, str] = {}
    for key, entry in registry_entries(registry, layout):
        manifest_path = resource_to_path(entry["manifest"])
        manifest = load_json(manifest_path)
        minimap = manifest.get("minimap", {})
        image_name = minimap.get("image")
        if not image_name:
            raise SystemExit(f"{key}: package has no minimap image to draw the continent from")
        image_path = manifest_path.parent / image_name
        if not image_path.exists():
            raise SystemExit(f"{key}: {image_path} is missing")
        with Image.open(image_path) as image:
            if list(image.size) != [int(v) for v in minimap.get("imageSize", [])]:
                raise SystemExit(f"{key}: minimap.imageSize {minimap.get('imageSize')} "
                                 f"does not match the image, {list(image.size)}")
        frame = framing(manifest)
        crop = tab_map_crop(minimap, frame)
        world_min, world_max = crop_world(minimap, crop)
        centre = layout["regions"][key]
        width_m = world_max[0] - world_min[0]
        height_m = world_max[1] - world_min[1]
        rect = [int(round((float(centre[0]) - width_m * 0.5) / metres_per_pixel)),
                int(round((float(centre[1]) - height_m * 0.5) / metres_per_pixel)),
                max(1, int(round(width_m / metres_per_pixel))),
                max(1, int(round(height_m / metres_per_pixel)))]
        if rect[0] < 0 or rect[1] < 0 or rect[0] + rect[2] > canvas_w or rect[1] + rect[3] > canvas_h:
            raise SystemExit(f"{key}: lies outside the {canvas_w}x{canvas_h} canvas at {rect}")
        sources[key] = digest(image_path)
        regions.append({
            "name": str(manifest.get("asset", {}).get("name", key)),
            "serverMap": key,
            "continentRect": rect,
            "tabMap": {
                "texture": path_to_resource(image_path),
                "region": list(crop),
                "worldMin": world_min,
                "worldMax": world_max,
            },
        })
        tiles.append({"key": key, "image": image_path, "crop": crop, "rect": rect})
    for index, first in enumerate(regions):
        a = first["continentRect"]
        for second in regions[index + 1:]:
            b = second["continentRect"]
            if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                raise SystemExit(f"{first['serverMap']} and {second['serverMap']} overlap on the continent")
    cartography = {
        "schemaVersion": SCHEMA_VERSION,
        "generator": "eloria-assets/tools/build_continent_map.py",
        "note": ("Generated: the continent picture is every exterior region's own tab map "
                 "(its minimap.webp) laid out to scale as continent-layout.json says, and "
                 "each region's tabMap names the pixels of that image the live Tab map "
                 "frames. Re-run the tool after a region redraws its minimap or moves; "
                 "test_cartography.py fails while this file is stale."),
        "continent": {
            "name": str(layout.get("continent", "Nymara")),
            "texture": path_to_resource(CONTINENT_IMAGE),
            "imageSize": [canvas_w, canvas_h],
            "metresPerPixel": metres_per_pixel,
            "sources": sources,
        },
        "regions": regions,
        "connections": atlas_connections(layout),
    }
    return cartography, tiles


def draw(layout: dict, cartography: dict, tiles: list[dict]) -> Image.Image:
    metres_per_pixel = float(layout["metresPerPixel"])
    width, height = cartography["continent"]["imageSize"]
    canvas = Image.new("RGB", (width, height), tuple(int(v) for v in layout["sea"]))
    lake = layout.get("lake")
    if lake:
        cx, cy = (float(v) / metres_per_pixel for v in lake["centre"])
        radius = float(lake["radius"]) / metres_per_pixel
        ImageDraw.Draw(canvas).ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=tuple(int(v) for v in lake["colour"]))
    pen = ImageDraw.Draw(canvas)
    for link in cartography['connections']:
        points = [tuple(p) for p in link['points']]
        if link['type'] != 'ferry':
            pen.line(points, fill=(53, 48, 36), width=6, joint='curve')
            pen.line(points, fill=(218, 193, 137), width=3, joint='curve')
        else:
            # Dash spacing is in image pixels, so the ferry stays distinct
            # from a road even across a narrow gap between real lake tiles.
            for a, b in zip(points, points[1:]):
                length = math.dist(a, b)
                for begin in range(0, int(length), 9):
                    end = min(begin+5, length)
                    at = lambda d: tuple(a[i]+(b[i]-a[i])*d/length for i in (0, 1))
                    pen.line([at(begin), at(end)], fill=(129, 204, 221), width=2)
    for tile in tiles:
        x, y, w, h = tile["crop"]
        rect = tile["rect"]
        with Image.open(tile["image"]) as image:
            piece = image.convert("RGB").crop((x, y, x + w, y + h))
            piece = piece.resize((rect[2], rect[3]), Image.LANCZOS)
        canvas.paste(piece, (rect[0], rect[1]))
    return canvas


def check() -> list[str]:
    """Everything that would change if the tool ran now. Empty means current."""
    problems: list[str] = []
    layout = load_json(LAYOUT)
    registry = load_json(REGISTRY)
    wanted, tiles = compose(layout, registry)
    if not CARTOGRAPHY.exists():
        return [f"{CARTOGRAPHY} is missing; run build_continent_map.py"]
    current = load_json(CARTOGRAPHY)
    if current != wanted:
        for key in sorted(set(current) | set(wanted)):
            if current.get(key) != wanted.get(key):
                problems.append(f"cartography.json '{key}' is stale; run build_continent_map.py")
    if not CONTINENT_IMAGE.exists():
        problems.append(f"{CONTINENT_IMAGE} is missing; run build_continent_map.py")
    else:
        with Image.open(CONTINENT_IMAGE) as image:
            if list(image.size) != wanted["continent"]["imageSize"]:
                problems.append(f"continent image is {list(image.size)}, cartography says "
                                f"{wanted['continent']['imageSize']}; run build_continent_map.py")
        encoded = io.BytesIO()
        draw(layout, wanted, tiles).save(encoded, 'WEBP', quality=WEBP_QUALITY, method=6)
        if CONTINENT_IMAGE.read_bytes() != encoded.getvalue():
            problems.append('continent picture content is stale; run build_continent_map.py')
    return problems


def build() -> None:
    layout = load_json(LAYOUT)
    registry = load_json(REGISTRY)
    cartography, tiles = compose(layout, registry)
    picture = draw(layout, cartography, tiles)
    CONTINENT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    picture.save(CONTINENT_IMAGE, "WEBP", quality=WEBP_QUALITY, method=6)
    CARTOGRAPHY.write_text(json.dumps(cartography, indent=2) + "\n", encoding="utf-8")
    print(f"continent {picture.size[0]}x{picture.size[1]} -> {CONTINENT_IMAGE.relative_to(ROOT)}")
    print(f"{len(cartography['regions'])} regions -> {CARTOGRAPHY.relative_to(ROOT)}")
    for region in cartography["regions"]:
        print(f"  {region['serverMap']:18s} at {region['continentRect']} "
              f"from {region['tabMap']['region']} of {Path(region['tabMap']['texture']).name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="report what is stale instead of writing anything")
    args = parser.parse_args(argv)
    if args.check:
        problems = check()
        for problem in problems:
            print(problem)
        return 1 if problems else 0
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
