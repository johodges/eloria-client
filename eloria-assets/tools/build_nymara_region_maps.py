#!/usr/bin/env python3
"""Build Godot-native production starters for the eleven Nymara exteriors.

The checked-in ELM files remain the terrain and placement authority.  This
builder converts that authored topology to portable GLB 2.0, generates an
original regional PBR texture kit, and records one production checkpoint for
every panel in the ten-view concept board.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np
from PIL import Image

from build_native_nymara_glbs import GLB, ShapeMesh
from generate_nymara_complete import (
    amberwood_placements, amethyst_placements, crownwater_placements,
    grey_moors_placements, manymouth_placements, mirrorhold_placements,
    ssarathi_placements, sunmane_placements, verdant_placements,
    westhaven_placements, whitehorn_placements,
)


ROOT = Path(__file__).resolve().parents[1]
MAP_ROOT = ROOT / "maps" / "nymara-regions"
SOURCE_ROOT = MAP_ROOT / "source-elm"

REGIONS = {
    "mirrorhold": {
        "title": "Mirrorhold", "palette": ((47, 70, 73), (174, 151, 92), (66, 151, 181)),
        "water": True, "subjects": ["citadel approach", "canal street", "civic fountain",
        "radial bridge", "observatory exterior", "lens mechanism", "cliff terraces",
        "lake dock", "rooftop skyline", "slate brass crystal materials"]},
    "crownwater": {
        "title": "Crownwater", "palette": ((221, 217, 180), (192, 153, 73), (36, 125, 145)),
        "water": True, "subjects": ["ferry arrival", "stone quay", "domed civic plaza",
        "radial causeway", "satellite island", "patrol boat", "submerged waystone",
        "fountain garden", "archipelago skyline", "limestone brass tile materials"]},
    "whitehorn_range": {
        "title": "Whitehorn Range", "palette": ((183, 211, 219), (65, 78, 83), (220, 237, 242)),
        "water": False, "subjects": ["glacial approach", "monastery court", "rope bridge",
        "glacier shrine", "cairn path", "ice cave", "silver mine", "frozen waterfall",
        "ridge panorama", "ice granite rope materials"]},
    "amethyst_barrens": {
        "title": "Amethyst Barrens", "palette": ((122, 99, 65), (184, 132, 194), (112, 62, 166)),
        "water": False, "subjects": ["basin road", "Glasswarden observatory", "crystal bridge",
        "geode cave", "levitating shards", "storm ruin", "harvesting site",
        "field station", "mesa overlook", "amethyst brass stormglass materials"]},
    "sunmane_steppe": {
        "title": "Sunmane Steppe", "palette": ((171, 126, 56), (130, 70, 38), (221, 166, 72)),
        "water": False, "subjects": ["caravan road", "round-tent camp", "seasonal market",
        "banner shrine", "caravanserai", "windmill", "well and pens", "burial mound",
        "steppe overlook", "hide bone timber materials"]},
    "amberwood": {
        "title": "Amberwood", "palette": ((65, 91, 55), (119, 72, 35), (210, 119, 39)),
        "water": False, "subjects": ["forest road", "estate terrace", "hunting lodge",
        "hollow tree", "old ravine bridge", "ruin arch", "garden fountain",
        "resin canopy trail", "estate overlook", "leaf resin manor materials"]},
    "grey_moors": {
        "title": "Grey Moors", "palette": ((72, 77, 68), (105, 83, 108), (92, 119, 126)),
        "water": True, "subjects": ["raised causeway", "turf barrow", "standing stones",
        "bog boardwalk", "crypt threshold", "abandoned cottage", "wisp tree",
        "peat and orchids", "coastal panorama", "peat slate heather materials"]},
    "westhaven": {
        "title": "Westhaven", "palette": ((87, 91, 89), (130, 84, 55), (40, 120, 145)),
        "water": True, "subjects": ["harbor approach", "lighthouse", "warehouse quay",
        "dry dock", "harbor crane", "shipyard frame", "fish market", "seawall surf",
        "harbor skyline", "stone timber copper materials"]},
    "verdant_stair": {
        "title": "Verdant Stair", "palette": ((42, 105, 66), (83, 128, 80), (44, 151, 157)),
        "water": True, "subjects": ["lower river arrival", "basalt stair", "cenote spiral",
        "root bridge", "vine bridge", "tree platform", "water shrine", "fern trail",
        "terrace panorama", "basalt jade vine materials"]},
    "ssarathi_ruins": {
        "title": "Ssarathi Ruins", "palette": ((42, 91, 68), (151, 126, 57), (38, 137, 137)),
        "water": True, "subjects": ["temple causeway", "main temple", "royal vault",
        "water gate", "sunken court", "ritual pool", "sun stela", "ruin arch",
        "flooded-city panorama", "scale stone gold shell materials"]},
    "manymouth_delta": {
        "title": "Manymouth Delta", "palette": ((42, 71, 58), (117, 112, 56), (36, 137, 124)),
        "water": True, "subjects": ["mangrove channel", "stilt village", "boardwalk junction",
        "ferry dock", "hidden dock", "floating market", "reed farm", "flooded portal",
        "delta panorama", "reed wood rope lotus materials"]},
}

DETAIL_PLACEMENTS = {
    "mirrorhold": mirrorhold_placements, "crownwater": crownwater_placements,
    "whitehorn_range": whitehorn_placements, "amethyst_barrens": amethyst_placements,
    "sunmane_steppe": sunmane_placements, "amberwood": amberwood_placements,
    "grey_moors": grey_moors_placements, "westhaven": westhaven_placements,
    "verdant_stair": verdant_placements, "ssarathi_ruins": ssarathi_placements,
    "manymouth_delta": manymouth_placements,
}

INTERIORS = {
    "drowned_crown": {"title": "Drowned Crown", "parent": "crownwater", "subjects":
        ["flooded vestibule", "water galleries", "submerged arch", "shell altar",
         "statue court", "water channel", "collapsed dome", "air pocket",
         "objective hall", "limestone shell brass materials"]},
    "whitehorn_glacier_temple": {"title": "Whitehorn Glacier Temple", "parent": "whitehorn_range", "subjects":
        ["snow entry", "monastery nave", "prayer columns", "ice arch", "glacier altar",
         "mining gallery", "chasm bridge", "votive chamber", "upper sanctuary",
         "ice granite silver materials"]},
    "resonant_vault": {"title": "Resonant Vault", "parent": "amethyst_barrens", "subjects":
        ["sealed approach", "laboratory gallery", "archive aisle", "crystal brazier",
         "experiment table", "lens room", "containment cell", "energy crossing",
         "research hall", "amethyst brass machinery materials"]},
    "amberwood_estate": {"title": "Amberwood Estate", "parent": "amberwood", "subjects":
        ["entry hall", "banquet room", "bedchamber", "root gallery", "statue court",
         "conservatory", "servant passage", "flooded cellar", "upper balcony",
         "oak amber velvet materials"]},
    "grey_moor_barrows": {"title": "Grey Moor Barrows", "parent": "grey_moors", "subjects":
        ["barrow entry", "burial gallery", "carved arch", "ritual altar", "sarcophagus hall",
         "spike trap", "root crypt", "flooded ossuary", "royal tomb",
         "peat stone bone materials"]},
    "ssarathi_royal_archive": {"title": "Ssarathi Royal Archive", "parent": "ssarathi_ruins", "subjects":
        ["water entrance", "reading hall", "scaled mosaic", "water arch", "archive shelves",
         "royal statue", "vault trap", "flooded repository", "central archive",
         "scale stone papyrus materials"]},
    "manymouth_flooded_labyrinth": {"title": "Manymouth Flooded Labyrinth", "parent": "manymouth_delta", "subjects":
        ["hidden entry", "stilt corridor", "boardwalk maze", "flood channel", "smuggler cache",
         "crate workroom", "root chamber", "submerged gate", "labyrinth panorama",
         "reed rope mangrove materials"]},
}


def parse_elm(path: Path) -> dict:
    raw = path.read_bytes()
    if raw[:4] != b"elmf":
        raise ValueError(f"not an ELM map: {path}")
    width, height, tile_offset, height_offset, record_size, count, object_offset = \
        struct.unpack_from("<7i", raw, 4)
    tiles = np.frombuffer(raw, dtype=np.uint8, count=width * height,
                          offset=tile_offset).reshape(height, width).copy()
    heights = np.frombuffer(raw, dtype=np.uint8, count=width * height * 36,
                            offset=height_offset).reshape(height * 6, width * 6).copy()
    objects = []
    for index in range(count):
        offset = object_offset + index * record_size
        name, x, y, z, _, _, rotation = struct.unpack_from("<80s6f", raw, offset)
        objects.append({"asset": name.split(b"\0", 1)[0].decode(), "x": x, "y": y,
                        "z": z, "rotation": rotation})
    return {"width": width, "height": height, "tiles": tiles,
            "heights": heights, "objects": objects,
            "sha256": hashlib.sha256(raw).hexdigest()}


def texture_kit(directory: Path, palette: tuple[tuple[int, int, int], ...]) -> dict[str, bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    size = 512
    yy, xx = np.mgrid[:size, :size]
    grain = ((xx * 17 + yy * 29 + (xx ^ yy) * 5) % 31 - 15).astype(np.int16)
    joints = (xx % 64 < 3) | (yy % 48 < 3)
    base = np.empty((size, size, 4), dtype=np.uint8)
    color = np.asarray(palette[0], dtype=np.int16)
    accent = np.asarray(palette[1], dtype=np.int16)
    rgb = np.where(joints[..., None], accent, color) + grain[..., None]
    base[..., :3] = np.clip(rgb, 0, 255)
    base[..., 3] = 255
    normal = np.zeros_like(base); normal[..., 0] = 128; normal[..., 1] = 128
    normal[..., 2] = np.clip(244 + grain // 3, 0, 255); normal[..., 3] = 255
    orm = np.zeros_like(base); orm[..., 0] = 235
    orm[..., 1] = np.where(joints, 214, 168); orm[..., 2] = 18; orm[..., 3] = 255
    outputs = {}
    for name, pixels in (("region-basecolor.png", base), ("region-normal.png", normal),
                         ("region-orm.png", orm)):
        path = directory / name
        Image.fromarray(pixels, "RGBA").save(path, optimize=True)
        outputs[name] = path.read_bytes()
    return outputs


def terrain_arrays(elm: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[np.ndarray], float, float]:
    steps = 64
    positions = []
    height_values = np.empty((steps + 1, steps + 1), dtype=np.float32)
    for row in range(steps + 1):
        source_y = min(elm["height"] * 6 - 1, round(row * (elm["height"] * 6 - 1) / steps))
        for col in range(steps + 1):
            source_x = min(elm["width"] * 6 - 1, round(col * (elm["width"] * 6 - 1) / steps))
            height_values[row, col] = (int(elm["heights"][source_y, source_x]) & 0x3f) - 11
    for row in range(steps + 1):
        for col in range(steps + 1):
            positions.append(((col / steps - .5) * elm["width"] * 6,
                              float(height_values[row, col]),
                              (.5 - row / steps) * elm["height"] * 6))
    positions = np.asarray(positions, dtype=np.float32)
    normals = np.zeros_like(positions); normals[:, 1] = 1
    uvs = np.asarray([(col / 8, row / 8) for row in range(steps + 1)
                      for col in range(steps + 1)], dtype=np.float32)
    groups = [[], [], []]
    for row in range(steps):
        for col in range(steps):
            a = row * (steps + 1) + col; b = a + 1; c = a + steps + 1; d = c + 1
            tile_y = min(elm["height"] - 1, row * elm["height"] // steps)
            tile_x = min(elm["width"] - 1, col * elm["width"] // steps)
            tile = int(elm["tiles"][tile_y, tile_x])
            group = 2 if tile == 3 else 1 if tile in (2, 6) else 0
            groups[group].extend((a, c, b, b, c, d))
    return positions, normals, uvs, [np.asarray(x, dtype=np.uint32) for x in groups], \
        float(height_values.min()), float(height_values.max())


def landmark_shape(asset: str) -> ShapeMesh:
    """Author a readable production silhouette from the ELM asset role."""
    name = Path(asset).stem
    mesh = ShapeMesh()
    if any(word in name for word in ("bridge", "boardwalk", "causeway", "seawall", "stairs")):
        mesh.box((0, .45, 0), (12, .9, 3), material=0)
        for x in (-5.5, 5.5): mesh.box((x, 2.0, 0), (.45, 3.2, .45), material=1)
    elif any(word in name for word in ("tree", "mangrove", "fern")):
        mesh.cylinder((0, 0, 0), (0, 5, 0), .55, material=0)
        for x, z in ((0, 0), (1.4, .4), (-1.2, -.5)):
            mesh.sphere((x, 5.2, z), (4.2, 3.3, 4.2), material=1, rings=7, sides=14)
    elif any(word in name for word in ("crystal", "geode", "shard", "stormglass")):
        for x, z, height in ((0, 0, 7), (1.6, .5, 4.5), (-1.3, .8, 5.2)):
            mesh.cone((x, 0, z), (x, height, z), 1.25, material=1)
    elif any(word in name for word in ("boat", "canoe", "ferry", "dock", "shipyard", "dry_dock")):
        mesh.box((0, .6, 0), (8, 1.2, 3.4), material=0)
        for x in (-3.2, 3.2): mesh.cylinder((x, 0, -1.4), (x, 3.6, -1.4), .18, material=1)
    elif any(word in name for word in ("tent", "market", "pen", "camp")):
        mesh.cone((0, 0, 0), (0, 5.5, 0), 4.0, material=0, sides=12)
        mesh.cylinder((0, 0, 0), (0, 6.2, 0), .16, material=1)
    elif any(word in name for word in ("arch", "gate", "cave", "crypt", "mine")):
        mesh.box((-2.7, 3, 0), (1.4, 6, 2.2), material=0)
        mesh.box((2.7, 3, 0), (1.4, 6, 2.2), material=0)
        mesh.box((0, 6.1, 0), (6.8, 1.3, 2.2), material=1)
    elif any(word in name for word in ("tower", "lighthouse", "observatory", "temple",
                                        "monastery", "estate", "caravanserai")):
        mesh.box((0, 2.2, 0), (8.5, 4.4, 8.5), material=0)
        mesh.cylinder((0, 4.4, 0), (0, 11.5, 0), 2.8, material=0, sides=16)
        mesh.cone((0, 11.5, 0), (0, 15.2, 0), 3.4, material=1, sides=16)
    elif any(word in name for word in ("shrine", "stela", "waystone", "fountain", "well", "barrow")):
        mesh.box((0, .6, 0), (5.4, 1.2, 5.4), material=0)
        mesh.cylinder((0, 1.2, 0), (0, 5.5, 0), 1.15, material=0, sides=14)
        mesh.sphere((0, 6.0, 0), (2.0, 1.6, 2.0), material=1, rings=7, sides=14)
    else:
        mesh.box((0, 2.4, 0), (7.0, 4.8, 6.0), material=0)
        mesh.cone((0, 4.8, 0), (0, 7.8, 0), 4.5, material=1, sides=12)
    return mesh


def safe_node_name(asset: str) -> str:
    return "Landmark_" + "".join(c if c.isalnum() else "_" for c in Path(asset).stem).strip("_")


def build_region(slug: str, config: dict) -> dict:
    directory = MAP_ROOT / slug
    elm_path = SOURCE_ROOT / f"{slug}.elm"
    elm = parse_elm(elm_path)
    textures = texture_kit(directory / "textures", config["palette"])
    glb = GLB(generator="Eloria Nymara regional production builder")
    ground = glb.material(f"{config['title']} Ground", config["palette"][0],
                          roughness=.88, texture_png=textures["region-basecolor.png"], double_sided=True)
    road = glb.material(f"{config['title']} Routes", config["palette"][1],
                        roughness=.72, texture_png=textures["region-basecolor.png"], double_sided=True)
    water = glb.material(f"{config['title']} Water", config["palette"][2],
                         metallic=.08, roughness=.28, double_sided=True)
    glb.doc["materials"][water]["alphaMode"] = "BLEND"
    glb.doc["materials"][water]["pbrMetallicRoughness"]["baseColorFactor"][3] = .82
    structure = glb.material(f"{config['title']} Structure", config["palette"][0], roughness=.74)
    trim = glb.material(f"{config['title']} Accent", config["palette"][1], metallic=.25,
                        roughness=.42, emissive=tuple(value // 14 for value in config["palette"][2]))
    positions, normals, uvs, groups, minimum, maximum = terrain_arrays(elm)
    terrain_primitives = [glb.primitive(positions, normals, uvs, indices, material)
                          for indices, material in zip(groups, (ground, road, water)) if len(indices)]
    glb.mesh_node("Terrain_ELM_Authority", terrain_primitives)

    # Keep every supplied ELM placement, then add the denser production layout
    # from the deterministic regional composition catalog.  Terrain, routes,
    # water and the arrival datum remain byte-for-byte derived from the ELM.
    placed_objects = list(elm["objects"])
    occupied = {(item["asset"], round(item["x"], 2), round(item["y"], 2))
                for item in placed_objects}
    for asset, x, y, z, rotation in DETAIL_PLACEMENTS[slug]():
        key = (asset, round(x, 2), round(y, 2))
        if key not in occupied:
            placed_objects.append({"asset": asset, "x": x, "y": y, "z": z,
                                   "rotation": rotation})
            occupied.add(key)
    mesh_cache = {}
    node_names = []
    landmark_records = []
    for index, placed in enumerate(placed_objects):
        asset = placed["asset"]
        if "/interactives/" in asset or Path(asset).stem in {"mirror_reed", "crownwater_pearl",
                "deep_lake_clay", "delta_lotus", "glacier_salt", "whitehorn_silverleaf",
                "resonant_crystal", "stormglass_shard", "voltaic_geode", "sunmane_seed",
                "amber_resin", "ghost_orchid", "moor_peat", "mangrove_sap",
                "verdant_venom_bulb", "ssarathi_scale_moss"}:
            continue
        key = Path(asset).stem
        if key not in mesh_cache:
            primitives = []
            for material_index, arrays in enumerate(landmark_shape(asset).arrays()[6]):
                if len(arrays[0]):
                    primitives.append(glb.primitive(*arrays[:4], (structure, trim)[material_index]))
            glb.doc["meshes"].append({"name": key, "primitives": primitives})
            mesh_cache[key] = len(glb.doc["meshes"]) - 1
        node_name = f"{safe_node_name(asset)}_{index:03d}"
        source_x = max(0, min(elm["width"] * 6 - 1, round(placed["x"])))
        source_y = max(0, min(elm["height"] * 6 - 1, round(placed["y"])))
        y = (int(elm["heights"][source_y, source_x]) & 0x3f) - 11 + placed["z"]
        angle = math.radians(-placed["rotation"])
        node = {"name": node_name, "mesh": mesh_cache[key],
                "translation": [placed["x"] - 58.0, y, 58.0 - placed["y"]],
                "rotation": [0.0, math.sin(angle / 2), 0.0, math.cos(angle / 2)]}
        glb.doc["nodes"].append(node)
        glb.doc["scenes"][0]["nodes"].append(len(glb.doc["nodes"]) - 1)
        node_names.append(node_name)
        landmark_records.append({"id": f"landmark-{index:03d}", "name": key.replace("_", " ").title(),
                                 "node": node_name, "position": node["translation"]})
    glb.write(directory / "world.glb")

    checkpoints = []
    radius = 72.0
    for panel, subject in enumerate(config["subjects"], 1):
        angle = math.radians((panel - 1) * 36 - 90)
        checkpoints.append({"panel": panel, "id": f"concept-{panel:02d}", "subject": subject,
            "cameraPosition": [round(math.cos(angle) * radius, 2), 16.0 + panel % 3 * 4,
                               round(math.sin(angle) * radius, 2)],
            "target": [0.0, 4.0, 0.0],
            "evidenceNodes": [record["node"] for record in landmark_records
                              if any(token in record["node"].lower()
                                     for token in subject.replace("-", " ").split())][:3]})
    # Some material/overview panels intentionally use the terrain and full node set.
    for checkpoint in checkpoints:
        if not checkpoint["evidenceNodes"]:
            checkpoint["evidenceNodes"] = ["Terrain_ELM_Authority"]

    manifest = {
        "schemaVersion": "1.0.0", "assetVersion": "0.1.0",
        "asset": {"id": slug, "name": config["title"], "glb": "world.glb", "units": "meters",
                  "coordinateSystem": {"handedness": "right", "upAxis": "Y", "northAxis": "-Z"},
                  "origin": [0, 0, 0],
                  "bounds": {"min": [-96, minimum, -96], "max": [96, maximum + 18, 96]}},
        "source": {"elm": f"../source-elm/{slug}.elm", "sha256": elm["sha256"],
                   "mapEditorCatalog": "../source-elm/map-editor-catalog.json",
                   "placementPolicy": "preserve-source-and-add-deterministic-production-detail"},
        "conceptArt": {"macro": f"../../../concepts/nymara-regions/{slug}_region_concept.png",
                       "detailBoard": "references/00-concept-detail-board.png",
                       "panelGrid": [5, 2], "viewCount": 10,
                       "generator": "OpenAI ImageGen (built-in)", "checkpoints": checkpoints},
        "landmarks": landmark_records,
        "spawnPoints": [{"id": "default", "position": [0, 1, 0], "rotationDegrees": 180}],
        "collision": {"nodeNames": node_names},
        "navigation": {"surfaceNodePrefixes": ["Terrain_"], "navmesh": {"format": "surface-prefix-v1", "polygons": []}},
        "materials": {"baseColor": "textures/region-basecolor.png",
                      "normal": "textures/region-normal.png", "orm": "textures/region-orm.png"},
        "productionStatus": "terrain-landmark-material-pass"
    }
    (directory / "world.json").write_text(json.dumps(manifest, indent=2) + "\n")
    readme = f"""# {config['title']} production map\n\nThis starter package converts the supplied `{slug}.elm` terrain, routes, water mask, and landmark placements to Godot-native GLB. The ten-panel board in `references/00-concept-detail-board.png` is the visual authority for the next modeling pass.\n\n- Source topology SHA-256: `{elm['sha256']}`\n- Concept checkpoints: 10/10\n- Landmark instances: {len(landmark_records)}\n- Texture kit: base color, tangent-space normal, and ORM\n- Current status: terrain, traversal, material language, and landmark silhouettes; final hero geometry and set dressing remain in progress.\n"""
    (directory / "README.md").write_text(readme)
    return {"id": slug, "title": config["title"], "sourceSha256": elm["sha256"],
            "conceptViews": 10, "landmarkInstances": len(landmark_records),
            "terrainHeightRange": [minimum, maximum], "water": config["water"]}


def write_interior_concept(slug: str, config: dict) -> dict:
    directory = MAP_ROOT / "interiors" / slug
    source = SOURCE_ROOT / f"{slug}.elm"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    concept = {"schemaVersion": 1, "id": slug, "name": config["title"],
               "status": "concept-complete-production-queued",
               "parentRegion": config["parent"],
               "source": {"elm": f"../../source-elm/{slug}.elm", "sha256": source_hash},
               "conceptArt": {"culturalReference":
                   f"../../../../concepts/nymara-regions/{config['parent']}_region_concept.png",
                   "detailBoard": "references/00-concept-detail-board.png",
                   "panelGrid": [5, 2], "viewCount": 10, "subjects": config["subjects"]}}
    (directory / "concept.json").write_text(json.dumps(concept, indent=2) + "\n")
    (directory / "README.md").write_text(
        f"# {config['title']} concept package\n\nTen production perspectives are complete. "
        f"The supplied `{slug}.elm` source is preserved and hashed; Godot-native geometry is queued "
        "for the interior production tranche after the exterior terrain/landmark/material pass.\n")
    return {"id": slug, "title": config["title"], "sourceSha256": source_hash,
            "conceptViews": 10, "productionStatus": "queued"}


def main() -> None:
    results = [build_region(slug, config) for slug, config in REGIONS.items()]
    interiors = [write_interior_concept(slug, config) for slug, config in INTERIORS.items()]
    index = {"schemaVersion": 1, "status": "production-started", "regions": results,
             "interiors": interiors,
             "totals": {"maps": len(results) + len(interiors), "productionRegions": len(results),
                        "conceptViews": sum(x["conceptViews"] for x in results + interiors),
                        "landmarkInstances": sum(x["landmarkInstances"] for x in results)}}
    (MAP_ROOT / "production-index.json").write_text(json.dumps(index, indent=2) + "\n")
    concepts = {"schemaVersion": 1, "toolMode": "OpenAI built-in ImageGen",
        "promptPattern": "Preserve the authoritative regional composition and palette; render one borderless 5x2 board with exactly ten distinct, coherent, zoomed environment-design perspectives; no text, labels, logos, frames, or UI; AAA painterly photorealistic game concept art with believable scale and readable traversal.",
        "artDirection": "Original Eloria/Nymara environment design; macro concept supplied as image reference; no existing game art used.",
        "maps": [{"id": slug,
                     "macroReference": f"../../concepts/nymara-regions/{slug}_region_concept.png",
                     "detailBoard": f"{slug}/references/00-concept-detail-board.png",
                     "panelGrid": [5, 2], "subjects": config["subjects"]}
                    for slug, config in REGIONS.items()] +
                   [{"id": slug,
                     "macroReference": f"../../concepts/nymara-regions/{config['parent']}_region_concept.png",
                     "detailBoard": f"interiors/{slug}/references/00-concept-detail-board.png",
                     "panelGrid": [5, 2], "subjects": config["subjects"]}
                    for slug, config in INTERIORS.items()]}
    (MAP_ROOT / "concept-generation-manifest.json").write_text(
        json.dumps(concepts, indent=2) + "\n")
    print(json.dumps(index["totals"], indent=2))


if __name__ == "__main__":
    main()
