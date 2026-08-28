#!/usr/bin/env python3
"""Build the Whitehorn Range runtime package.

Writes `world.glb`, `world.json`, `collision.bin`, `minimap.webp`, the glTF
validator report and the performance summary, one directory up.

Deterministic for a given seed: the same source reproduces the same bytes.

    python3 build_whitehorn.py
    python3 ../../_toolkit/verify_runtime.py --package ..
    python3 ../../_toolkit/validate_gltf.py ../world.glb
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
sys.path.insert(0, str(PACKAGE.parent / "_toolkit"))
sys.path.insert(0, str(HERE))

from amberwood import gltf as GLTF          # noqa: E402
from amberwood import materials as MAT      # noqa: E402
from amberwood import mesh as M             # noqa: E402
from amberwood import terrain as TER        # noqa: E402
from regionbuild import RegionBuild         # noqa: E402
import validate_gltf                        # noqa: E402

import region as REG                        # noqa: E402

SEED = 20260828
ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# The materials Whitehorn embeds, pinned by name. The shared table grows as
# other regions add recipes; without this pin every one of those would be
# embedded here too - megabytes of images nothing references, and a different
# world.glb for a change that has nothing to do with Whitehorn.
#
# Whitehorn reuses the shared alpine recipes rather than duplicating them.
# `snow_pack`, `glacier_ice`, `veined_marble`, `pale_ashlar`, `blue_crystal`,
# `gilt_brass`, `slate_roof` and `alpine_turf` were added to the toolkit by the
# Mirrorhold build; reusing them by name is the intended contract.
#
# This set is exactly the materials the build emits - verified against the
# meshes it actually produces, not guessed. An unused name would embed a
# texture nothing references; a missing one is a hard error at export.
MATERIALS = frozenset({
    'snow_pack', 'glacier_ice', 'veined_marble', 'pale_ashlar',
    'blue_crystal', 'gilt_brass', 'alpine_turf',
    'cliff_rock', 'rubble_stone', 'packed_earth', 'ashlar',
    'timber_grey', 'timber_dark', 'dark_iron', 'woven_cloth',
    'bark_dark', 'foliage_green', 'amber_resin',
})

COLLISION_CELL = 0.5
COLLISION_HEIGHT_STEP = 0.2
COLLISION_HEIGHT_ORIGIN = -2.2


# --------------------------------------------------------------------------
def build_region(seed: int = SEED, lod: str | None = None) -> RegionBuild:
    """Terrain, then population. Terrain must stand on its own first."""
    terrain = REG.build_terrain(seed)
    REG.apply_built_ground(terrain, seed)
    REG.assign_surfaces(terrain, seed)

    build = RegionBuild(terrain=terrain)
    build.terrain_meshes = terrain.build_meshes(
        uv_scale=0.30, materials=REG.SURFACE_MATERIALS)

    import populate
    populate.populate(build, seed, lod=lod)

    _add_spawns(build)
    return build


def _add_spawns(build: RegionBuild) -> None:
    t = build.terrain
    for ident, name, position in (
            ("whitehorn-arrival", "Whitehorn Arrival", REG.SPAWN),
            ("whitehorn-temple", "Glacier Temple Forecourt", REG.SPAWN_TEMPLE),
            ("whitehorn-mine", "Mine Yard", REG.SPAWN_MINE)):
        x, z = position
        build.spawns.append({
            "id": ident,
            "name": name,
            "position": [round(float(x), 2),
                         round(float(t.height_at(x, z)), 2),
                         round(float(z), 2)],
            "rotationY": 0.0,
            "authority": "server",
        })


# --------------------------------------------------------------------------
def _split_group(key: str, item) -> tuple[dict[str, M.Mesh], dict[str, M.Mesh]]:
    """Split a landmark into per-material meshes, keeping walkable decks apart."""
    if not hasattr(item, "parts"):
        return {key: item}, {}
    solid = {f"{key}__{material}": piece
             for material, piece in item.by_material(False).items()}
    walk = {f"{key}__walk__{material}": piece
            for material, piece in item.by_material(True).items()}
    return solid, walk


def export_glb(build: RegionBuild, sets, path: Path) -> tuple[GLTF.GltfBuilder, dict]:
    builder = GLTF.GltfBuilder(
        generator="Eloria Whitehorn Range builder (original procedural assets)")
    MAT.register_gltf_materials(builder, sets, only=MATERIALS)

    # Tangents are intentionally omitted: Godot's glTF importer generates them
    # for normal-mapped materials, and shipping them costs sixteen bytes a
    # vertex in a package already dominated by vertex data.
    def prepare(piece: M.Mesh) -> M.Mesh:
        piece.sanitise_normals()
        piece.drop_degenerate()
        piece.weld(1e-4)
        return piece

    # Every mesh a placement references, registered once and instanced by node.
    exported: dict[str, tuple[list[str], list[str]]] = {}
    for key, item in build.meshes.items():
        solid, walk = _split_group(key, item)
        solid_names, walk_names = [], []
        for name, piece in solid.items():
            if piece.triangle_count == 0:
                continue
            builder.add_mesh(name, prepare(piece), with_tangents=False)
            solid_names.append(name)
        for name, piece in walk.items():
            if piece.triangle_count == 0:
                continue
            builder.add_mesh(name, prepare(piece), with_tangents=False)
            walk_names.append(name)
        exported[key] = (solid_names, walk_names)

    root_index = builder.add_node(GLTF.Node("WhitehornRange"))
    # Group nodes are created on first use. Emitting the full set up front
    # leaves childless nodes in the GLB, which the validator reports as
    # NODE_EMPTY and which serve no purpose in the scene tree.
    _groups: dict[str, int] = {}

    def groups_get(name: str) -> int:
        if name not in _groups:
            _groups[name] = builder.add_node(
                GLTF.Node(f"Group_{name}"), root_index)
        return _groups[name]

    class _Groups:
        def __getitem__(self, name: str) -> int:
            return groups_get(name)

    groups = _Groups()

    for name, piece in build.terrain_meshes.items():
        if piece.triangle_count == 0:
            continue
        builder.add_mesh(name, prepare(piece), with_tangents=False)
        parent = groups["Boundary"] if name.startswith("Backdrop") \
            else groups["Terrain"]
        builder.add_node(GLTF.Node(name, mesh=name), parent)
    for name, piece in build.water_meshes.items():
        if piece.triangle_count == 0:
            continue
        builder.add_mesh(name, prepare(piece), with_tangents=False)
        builder.add_node(GLTF.Node(name, mesh=name), groups["Ice"])

    kind_group = {
        "tree": "Props", "foliage": "Props", "rock": "Props",
        "building": "Structures", "landmark": "Structures",
        "interactive": "Structures", "prop": "Props",
    }
    used_names: set[str] = set()

    def unique(name: str) -> str:
        if name not in used_names:
            used_names.add(name)
            return name
        suffix = 2
        while f"{name}_{suffix}" in used_names:
            suffix += 1
        used_names.add(f"{name}_{suffix}")
        return f"{name}_{suffix}"

    for placement in build.placements:
        solid_names, walk_names = exported.get(placement.mesh, ([], []))
        if not solid_names and not walk_names:
            continue
        parent = groups[kind_group.get(placement.kind, "Props")]
        node_name = unique(placement.node)
        placement.node = node_name
        scale = (placement.scale, placement.scale, placement.scale)
        if len(solid_names) == 1 and not walk_names:
            builder.add_node(GLTF.Node(node_name, mesh=solid_names[0],
                                       translation=placement.position,
                                       rotation_y=placement.rotation_y,
                                       scale=scale), parent)
            continue
        container = builder.add_node(
            GLTF.Node(node_name, translation=placement.position,
                      rotation_y=placement.rotation_y, scale=scale), parent)
        for piece_name in solid_names:
            material = piece_name.split("__")[-1]
            builder.add_node(GLTF.Node(unique(f"{node_name}__{material}"),
                                       mesh=piece_name), container)
        for piece_name in walk_names:
            material = piece_name.split("__")[-1]
            # the navigation prefix has to be on the node the client sees
            builder.add_node(GLTF.Node(unique(f"Walk_{node_name}__{material}"),
                                       mesh=piece_name), container)

    size = builder.write_glb(str(path))
    stats = builder.statistics()
    stats["glbBytes"] = size
    stats["instancedTriangles"] = builder.instanced_triangles()
    return builder, stats


# --------------------------------------------------------------------------
def build_collision(build: RegionBuild) -> tuple[bytes, int, int, dict]:
    """Half-metre walkability grid over the server footprint (EWCG version 1)."""
    t = build.terrain
    width = int(round((REG.PLAY_MAX_X - REG.PLAY_MIN_X + REG.METRES_PER_TILE)
                      / COLLISION_CELL))
    height = int(round((REG.PLAY_MAX_Z - REG.PLAY_MIN_Z + REG.METRES_PER_TILE)
                       / COLLISION_CELL))
    width -= width % 6
    height -= height % 6

    # Rows are indexed by server tile Y, which runs north to south, so row 0 is
    # the +Z (southern) edge. Writing the grid the other way round silently
    # mirrors every walkability decision about the map.
    xs = REG.PLAY_MIN_X + (np.arange(width) + 0.5) * COLLISION_CELL
    zs = REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE \
        - (np.arange(height) + 0.5) * COLLISION_CELL
    gx, gz = np.meshgrid(xs, zs)
    ground = t.height_at(gx, gz)

    gradient_z, gradient_x = np.gradient(t.height, t.cell)
    slope_grid = np.hypot(gradient_x, gradient_z)
    cx = np.clip(((gx - t.x0) / t.cell).astype(int), 0, t.cols - 1)
    cz = np.clip(((gz - t.z0) / t.cell).astype(int), 0, t.rows - 1)
    slope = slope_grid[cz, cx]

    # Whitehorn has no sea, so walkability is mostly a slope question. The
    # glacier surface is walkable; the gorge walls and the ranges that close
    # the world are not.
    walkable = slope < 1.05

    # The gorge floor is excluded deliberately. It sits 22 m below the valley
    # datum, which is past what the legacy six-bit height field can encode -
    # those cells quantised to the floor of the range and then disagreed with
    # the rendered surface. More importantly it is a chasm: the two rope
    # bridges exist precisely because it is not something a player walks
    # across, so marking its bed unwalkable states the design rather than
    # working around the encoding.
    walkable &= ground > (REG.VALLEY_FLOOR - 10.0)

    blockers = np.zeros_like(walkable)
    for placement in build.placements:
        if not placement.collides:
            continue
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        footprint = float(max(abs(low[0]), abs(high[0]),
                              abs(low[2]), abs(high[2]))) * placement.scale
        factor = 0.16 if placement.kind in ("tree", "foliage") else 0.62
        radius = min(max(footprint * factor, 0.40), 11.0)
        px, _, pz = placement.position
        blockers |= (np.hypot(gx - px, gz - pz) < radius)
    walkable &= ~blockers

    surface = ground.copy()
    # An overhead walk surface owns its footprint: the client grounds an actor
    # on the first walk surface below the ray, so a two-level column cannot be
    # expressed on a flat server grid. The rope bridges therefore take their
    # cells, and the gorge floor beneath them is not separately walkable.
    elevated = 0
    for placement in build.placements:
        item = build.meshes[placement.mesh]
        walk_bounds = getattr(item, "walk_bounds", lambda: None)()
        if walk_bounds is None and not placement.walk_surface:
            continue
        low, high = walk_bounds if walk_bounds is not None else item.bounds()
        px, py, pz = placement.position
        half_x = float(max(abs(low[0]), abs(high[0]))) * placement.scale
        half_z = float(max(abs(low[2]), abs(high[2]))) * placement.scale
        deck_y = py + float(high[1]) * placement.scale
        radius = max(min(half_x, half_z) * 0.85, 0.4)
        footprint = np.hypot(gx - px, gz - pz) < radius
        if not footprint.any():
            continue
        elevated += 1
        surface = np.where(footprint, deck_y, surface)
        walkable = np.where(footprint, True, walkable)

    quantised = np.clip(np.round((surface - COLLISION_HEIGHT_ORIGIN)
                                 / COLLISION_HEIGHT_STEP), 1, 63).astype(np.uint8)
    grid = np.where(walkable, quantised, 0).astype(np.uint8)

    payload = struct.pack("<4sHHII", b"EWCG", 1, 0, width, height) + grid.tobytes()
    stats = {
        "width": width, "height": height, "cellMetres": COLLISION_CELL,
        "walkableCells": int(walkable.sum()),
        "blockedCells": int((~walkable).sum()),
        "walkableFraction": round(float(walkable.mean()), 4),
        "elevatedDecks": elevated,
        "rowOrder": "server-tile-y (row 0 is the +Z southern edge)",
        "columnOrder": "server-tile-x (column 0 is the -X western edge)",
    }
    return payload, width, height, stats


# --------------------------------------------------------------------------
def render_minimap(build: RegionBuild, sets, path: Path, size: int = 768) -> dict:
    """Top-down capture of the finished geometry, not a hand-drawn map."""
    import math

    import preview
    from amberwood import render as RENDER

    scene = preview.scene_from_build(build, sets)
    centre_x = (REG.PLAY_MIN_X + REG.PLAY_MAX_X) * 0.5
    centre_z = (REG.PLAY_MIN_Z + REG.PLAY_MAX_Z) * 0.5
    extent = max(REG.PLAY_MAX_X - REG.PLAY_MIN_X,
                 REG.PLAY_MAX_Z - REG.PLAY_MIN_Z)
    altitude = 1100.0
    fov = 2.0 * math.degrees(math.atan((extent * 0.5) / altitude))
    # Cold, near-shadowless light: a snow region under the warm preset reads
    # as sand, and heavy shadow on a white subject hides the relief rather
    # than describing it.
    lighting = RENDER.Lighting(sun_direction=(-0.28, 0.92, 0.28),
                               fog_density=0.0, ambient_strength=0.78,
                               shadow_strength=0.42,
                               sun_color=(1.02, 1.04, 1.10),
                               sky_color=(0.42, 0.50, 0.64),
                               saturation=0.94, exposure=1.0)
    image = scene.render(eye=(centre_x, altitude, centre_z + 0.01),
                         target=(centre_x, 0.0, centre_z),
                         width=size, height=size, fov=fov, lighting=lighting,
                         shadows=True, shadow_size=2048,
                         shadow_center=(centre_x, 40.0, centre_z),
                         shadow_radius=extent * 0.62, near=240.0, far=1700.0)
    image.save(path, "WEBP", quality=88, method=5)
    return {
        "file": path.name,
        "pixels": size,
        "metresPerPixel": round(extent / size, 4),
        "worldMin": [REG.PLAY_MIN_X, REG.PLAY_MIN_Z],
        "worldMax": [REG.PLAY_MIN_X + extent, REG.PLAY_MIN_Z + extent],
        "northAxis": "-Z",
        "orientation": "north-up",
    }


# --------------------------------------------------------------------------
def write_manifest(build: RegionBuild, stats: dict, collision_stats: dict,
                   minimap: dict, path: Path) -> dict:
    t = build.terrain
    lows, highs = [], []
    for piece in list(build.terrain_meshes.values()) + list(build.water_meshes.values()):
        if piece.triangle_count:
            low, high = piece.bounds()
            lows.append(low)
            highs.append(high)
    for placement in build.placements:
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        offset = np.asarray(placement.position)
        lows.append(low * placement.scale + offset)
        highs.append(high * placement.scale + offset)
    bounds_min = np.vstack(lows).min(axis=0)
    bounds_max = np.vstack(highs).max(axis=0)

    build.resolve_names()
    collision_nodes = sorted({p.node for p in build.placements if p.collides})

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "assetVersion": ASSET_VERSION,
        "asset": {
            "id": "whitehorn_range",
            "name": "Whitehorn Range",
            "glb": "world.glb",
            "units": "meters",
            "coordinateSystem": {"handedness": "right", "upAxis": "Y",
                                 "northAxis": "-Z"},
            "origin": [0, 0, 0],
            "bounds": {"min": [round(float(v), 2) for v in bounds_min],
                       "max": [round(float(v), 2) for v in bounds_max]},
            "playableBounds": {
                "min": [REG.PLAY_MIN_X, round(float(t.height.min()), 2),
                        REG.PLAY_MIN_Z],
                "max": [REG.PLAY_MAX_X, round(float(t.height.max()), 2),
                        REG.PLAY_MAX_Z]},
            "seaLevel": None,
            "valleyFloor": REG.VALLEY_FLOOR,
            "serverCells": REG.SERVER_CELLS,
        },
        "coordinateTransform": {
            "metresPerTile": REG.METRES_PER_TILE,
            "serverOrigin": list(REG.SERVER_ORIGIN),
            "origin": [0.0, 0.0, 0.0],
            "walkingHeight": round(float(t.height_at(*REG.SPAWN)), 2),
            "invertServerY": True,
        },
        "spawnPoints": build.spawns,
        "collision": {
            "nodeNames": collision_nodes,
            "binary": "collision.bin",
            "format": "EWCG-v1",
            "cellMetres": COLLISION_CELL,
            "width": collision_stats["width"],
            "height": collision_stats["height"],
            "heightEncoding": {
                "origin": COLLISION_HEIGHT_ORIGIN,
                "step": COLLISION_HEIGHT_STEP,
                "range": [1, 63],
                "zeroMeansBlocked": True,
                "note": ("Heights above 10.4 m clamp to 63 because the legacy "
                         "six-bit field cannot express Whitehorn's relief; the "
                         "grid is authoritative for walkability, and the Godot "
                         "loader takes elevation from the rendered walk "
                         "surfaces, not from this file."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
        },
        "navigation": {
            "surfaceNodePrefixes": ["Terrain_", "Walk_"],
            "walkableAreas": ["snow", "ice", "rock", "trails", "paving",
                              "marble", "alpine-turf", "bridges", "stairs"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every "
                "authored walkable deck is named Walk_<name>. Structural "
                "geometry is deliberately not a walk surface, so the "
                "grounding ray never snaps an actor onto a roof, a gantry or "
                "the top of an arch.",
            ],
        },
        "landmarks": build.landmarks,
        "interactives": build.interactives,
        "npcMarkers": build.npc_markers,
        "harvestables": build.harvestables,
        "portals": build.portals,
        "roads": [],
        "water": [],
        "environment": {
            "biome": "alpine-glacial",
            "snowLine": REG.SNOW_LINE,
            "notes": ["Whitehorn has no sea and no standing water; the "
                      "watercourses are frozen or dry meltwater beds."],
        },
        "minimap": minimap,
        "lodGroups": [],
        "performance": stats,
        "sources": {
            "concept": "eloria-assets/concepts/nymara-regions/"
                       "whitehorn_range_region_concept.png",
            "detailBoard": "references/00-concept-detail-board.png",
            "build": "source/build_whitehorn.py",
        },
        "provenance": {
            "generator": "Eloria Whitehorn Range builder",
            "seed": SEED,
            "toolkit": "maps/nymara-regions/_toolkit",
            "deterministic": True,
            "assets": "All geometry and textures generated procedurally; no "
                      "third-party models or images.",
        },
        "productionStatus": "production-geometry-materials-population",
        "knownLimitations": build.notes,
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PACKAGE))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--skip-minimap", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    import preview
    sets = preview.texture_sets()

    t0 = time.time()
    build = build_region(args.seed)
    print(f"[region] built in {time.time() - t0:.1f}s  "
          f"height {build.terrain.height.min():.1f} .. "
          f"{build.terrain.height.max():.1f} m")

    t0 = time.time()
    builder, stats = export_glb(build, sets, out / "world.glb")
    print(f"[glb] {stats['glbBytes'] / 1e6:.2f} MB, {stats['nodes']} nodes, "
          f"{stats['uniqueTriangles']} unique tris "
          f"({time.time() - t0:.1f}s)")

    payload, width, height, collision_stats = build_collision(build)
    (out / "collision.bin").write_bytes(payload)
    print(f"[collision] {width}x{height} cells, "
          f"{collision_stats['walkableFraction'] * 100:.1f}% walkable")

    minimap = {"file": "minimap.webp"}
    if not args.skip_minimap:
        t0 = time.time()
        minimap = render_minimap(build, sets, out / "minimap.webp")
        print(f"[minimap] rendered in {time.time() - t0:.1f}s")

    texture_bytes = sum(sum(len(v) for v in ts.images().values())
                        for name, ts in sets.items() if name in MATERIALS)
    stats["embeddedTextureBytes"] = texture_bytes
    stats["placements"] = len(build.placements)
    stats["collision"] = collision_stats
    stats["trianglesPerSquareMetre"] = round(
        stats["instancedTriangles"] / float(REG.SERVER_CELLS ** 2), 2)

    manifest = write_manifest(build, stats, collision_stats, minimap,
                              out / "world.json")
    print(f"[manifest] {len(manifest['landmarks'])} landmarks, "
          f"{len(manifest['spawnPoints'])} spawns")

    report = validate_gltf.validate(str(out / "world.glb"))
    payload = report.to_dict()
    (out / "world.glb.validator.json").write_text(
        json.dumps(payload, indent=2) + "\n")
    counts = payload["issues"]
    print(f"[validate] errors={counts['numErrors']} "
          f"warnings={counts['numWarnings']} infos={counts['numInfos']}")
    for message in report.messages:
        if message["severity"] <= 1:
            print("   ", message["code"], message["message"], message["pointer"])

    (out / "performance-summary.md").write_text(
        "# Whitehorn Range performance summary\n\n```json\n"
        + json.dumps(stats, indent=2) + "\n```\n", encoding="utf-8")
    return 0 if counts["numErrors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
