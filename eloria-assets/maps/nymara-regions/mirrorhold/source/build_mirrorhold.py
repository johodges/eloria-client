#!/usr/bin/env python3
"""Build the Mirrorhold runtime map package.

Outputs, next to this source tree:

    ../world.glb        self-contained glTF 2.0 (geometry, materials, textures)
    ../world.json       GLB world manifest, schema version 1
    ../collision.bin    half-metre walkability grid (EWCG v1)
    ../minimap.webp     minimap rendered from the final geometry
    ../world.glb.validator.json
    ../performance-summary.md

Deterministic: the same seed reproduces the same bytes.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

# The authoring toolkit is shared by every region and lives one level up, in
# `maps/nymara-regions/_toolkit/`. It must be on the path before the toolkit
# modules below are imported.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_toolkit"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import validate_gltf

from amberwood import gltf as GLTF
from amberwood import materials as MAT
from amberwood import mesh as M
import populate as POP
import region as REG
from amberwood import render as RENDER
from amberwood import terrain as TER

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SEED = 20260828

# The materials Mirrorhold embeds, pinned. The shared table grows as other
# regions add recipes to it, and without this every one of those would be
# embedded here too - about ten megabytes of images nothing references, and a
# different world.glb for a change that has nothing to do with Mirrorhold.
MATERIALS = frozenset({
    # Exactly what Mirrorhold embeds. Pinned by name so recipes added for
    # other regions never enlarge this package, and verified against the
    # build's actual usage rather than guessed.
    'pale_ashlar', 'ashlar', 'veined_marble', 'cobble_paving', 'rubble_stone',
    'cliff_rock', 'slate_roof', 'gilt_brass', 'dark_iron', 'blue_crystal',
    'snow_pack', 'glacier_ice', 'alpine_turf', 'shore_shingle',
    'mirror_glass',
    'timber_warm', 'timber_grey', 'timber_dark', 'carved_wood', 'woven_cloth',
    'bark_dark', 'foliage_green',
    # the braziers' coals: fire is warm even here
    'amber_resin',
    'water_lake', 'water_stream', 'water_pool',
})

ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------
def build_region(seed: int = SEED, lod: str | None = None) -> REG.RegionBuild:
    """Build the region. `lod="far"` produces the reduced second package."""
    t0 = time.time()
    terrain = REG.build_terrain(seed)
    REG.apply_built_ground(terrain, seed)
    build = REG.RegionBuild(terrain=terrain)

    POP.populate_citadel(build, seed)
    POP.populate_city(build, seed)
    POP.populate_lake(build, seed)
    POP.populate_outlands(build, seed)
    POP.populate_vegetation(build, seed, lod=lod)
    if lod is None:
        POP.populate_dressing(build, seed)
    POP.populate_interactives(build, seed)
    POP.build_water(build)

    build.terrain_meshes = terrain.build_meshes(uv_scale=0.28,
                                                materials=REG.SURFACE_MATERIALS)
    build.terrain_meshes["Backdrop_Distant"] = TER.backdrop(
        terrain, reach=300.0, cell=11.0, seed=seed + 909,
        material="cliff_rock", open_side=None, clip_interior=True)
    build.resolve_names()
    _add_spawns_and_portals(build)
    _add_population_markers(build, seed)
    print(f"[region] built in {time.time() - t0:.1f}s")
    return build


def _add_spawns_and_portals(build: REG.RegionBuild) -> None:
    t = build.terrain
    for spawn_id, (x, z), facing in (
            ("default", REG.SPAWN, 0.0),
            ("harbour", REG.SPAWN_HARBOUR, math.pi * 0.5),
            ("citadel-gate", REG.SPAWN_CITADEL, math.pi)):
        y = float(t.height_at(x, z))
        build.spawns.append({
            "id": spawn_id,
            "position": [round(float(x), 2), round(y + 0.05, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": round(math.degrees(facing), 1),
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True})

    # Edge portals to the neighbouring Nymara regions. Destination map ids
    # follow the client registry; the server owns the actual transition.
    for portal_id, name, (x, z), destination in (
            ("north-pass", "Whitehorn Pass", (54.0 * REG.SCALE, -128.0 * REG.SCALE),
             "maps/nymara/whitehorn_range.elm"),
            ("south-road", "Westhaven Road", (40.0 * REG.SCALE, 56.0 * REG.SCALE),
             "maps/nymara/westhaven.elm"),
            ("east-road", "Amethyst Barrens Road", (130.0 * REG.SCALE, -20.0 * REG.SCALE),
             "maps/nymara/amethyst_barrens.elm"),
            ("west-gorge", "Crownwater Gorge", (-52.0 * REG.SCALE, 4.0 * REG.SCALE),
             "maps/nymara/crownwater.elm")):
        y = float(t.height_at(x, z))
        build.portals.append({
            "id": portal_id, "name": name, "type": "map-transition",
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": destination, "radius": 3.5,
            "authority": "server"})

    # Interior entrances sit on the landmark they belong to.
    for portal_id, name, landmark_id, destination, spawn in (
            ("drowned-crown-stair", "The Drowned Crown", "ring",
             "maps/nymara/drowned_crown.elm", "default"),
            ("resonant-vault-door", "The Resonant Vault", "orrery",
             "maps/nymara/resonant_vault.elm", "default")):
        anchor = next((l for l in build.landmarks if l.get("id") == landmark_id), None)
        if anchor is None:
            continue
        x, y, z = anchor["position"]
        build.portals.append({
            "id": portal_id, "name": name, "type": "interior-entrance",
            "position": [round(float(x), 2), round(float(y) + 0.1, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "landmark": landmark_id,
            "destinationMap": destination, "destinationSpawn": spawn, "radius": 2.5,
            "authority": "server"})


def _add_population_markers(build: REG.RegionBuild, seed: int) -> None:
    """Editor/visual markers only - the server owns actual spawning.

    Every name here is a placeholder: no authoritative written description of
    Mirrorhold was available to this build. See modeling-assumptions.md.
    """
    t = build.terrain

    npc_plan = [
        ("mirrorhold-warden", "Warden of the Gate", ANCHOR("citadel_gate"), 4.0),
        ("lens-keeper", "Keeper of the Lens", ANCHOR("orrery"), 4.0),
        ("court-steward", "Court Steward", ANCHOR("citadel"), 6.0),
        ("plaza-crier", "Plaza Crier", ANCHOR("fountain_plaza"), 5.0),
        ("canal-reeve", "Canal Reeve", ANCHOR("canal_district"), 5.0),
        ("harbour-master", "Harbour Master", ANCHOR("harbour"), 5.0),
        ("ring-ferryman", "Ring Ferryman", ANCHOR("ring"), 4.0),
        ("town-factor", "Cliff-town Factor", ANCHOR("cliff_town"), 5.0),
        ("aqueduct-wright", "Aqueduct Wright", ANCHOR("aqueduct"), 4.0),
        ("overlook-sentry", "Overlook Sentry", ANCHOR("terrace_overlook"), 4.0),
        ("shore-trader", "Shore Trader", ANCHOR("spawn_road"), 5.0),
        ("south-watchman", "South Watchman", ANCHOR("south_watch"), 4.0),
    ]
    for npc_id, label, (x, z), radius in npc_plan:
        y = float(t.height_at(x, z))
        build.npc_markers.append({
            "id": npc_id, "label": label,
            "position": [round(x, 2), round(y + 0.05, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "wanderRadius": radius, "authority": "server"})

    creature_plan = [
        ("glacier-drake", "Glacier Drake", ANCHOR("glacier_east"), 26.0),
        ("ice-warden", "Ice Warden", ANCHOR("glacier_west"), 24.0),
        ("crag-goat", "Crag Goat", ANCHOR("peak_west"), 30.0),
        ("mirror-carp", "Mirror Carp", ANCHOR("lake"), 34.0),
        ("scree-lurker", "Scree Lurker", ANCHOR("peak_east"), 26.0),
        ("snow-hare", "Snow Hare", ANCHOR("upper_falls"), 20.0),
    ]
    for group_id, label, (x, z), radius in creature_plan:
        y = float(t.height_at(x, z))
        build.npc_markers.append({
            "id": group_id, "label": label, "kind": "creature-group",
            "position": [round(x, 2), round(y + 0.05, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "wanderRadius": radius, "authority": "server"})

    # Harvestables are scattered deterministically over the surfaces that
    # plausibly carry them, then recorded as metadata only.
    rng = REG.N.Rng(seed + 777)
    harvest_plan = [
        ("mirrorhold-lens-quartz", "Lens Quartz", TER.ROCK, 10),
        ("mirrorhold-glacier-rime", "Glacier Rime", TER.ICE, 8),
        ("mirrorhold-alpine-herb", "Alpine Herb", TER.TURF, 12),
        ("mirrorhold-shore-reed", "Shore Reed", TER.SHORE, 8),
    ]
    for item_id, label, surface, count in harvest_plan:
        placed = 0
        attempts = 0
        while placed < count and attempts < count * 400:
            attempts += 1
            x = rng.uniform(REG.PLAY_MIN_X + 20.0, REG.PLAY_MAX_X - 20.0)
            z = rng.uniform(REG.PLAY_MIN_Z + 20.0, REG.PLAY_MAX_Z - 20.0)
            if int(t.surface_at(x, z)) != surface:
                continue
            y = float(t.height_at(x, z))
            build.harvestables.append({
                "id": f"{item_id}-{placed:02d}", "item": item_id, "label": label,
                "position": [round(x, 2), round(y + 0.05, 2), round(z, 2)],
                "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                               int(round(REG.SERVER_ORIGIN[1] - z))],
                "authority": "server"})
            placed += 1


def ANCHOR(name: str):
    return REG.ANCHORS[name]


def _split_group(key: str, item) -> tuple[dict[str, M.Mesh], dict[str, M.Mesh]]:
    """Split a landmark into per-material meshes, keeping walkable decks apart."""
    if not hasattr(item, "parts"):
        return {key: item}, {}
    solid = {f"{key}__{material}": piece
             for material, piece in item.by_material(False).items()}
    walk = {f"{key}__walk__{material}": piece
            for material, piece in item.by_material(True).items()}
    return solid, walk


def export_glb(build: REG.RegionBuild, sets, path: Path) -> tuple[GLTF.GltfBuilder, dict]:
    builder = GLTF.GltfBuilder(
        generator="Eloria Mirrorhold builder (original procedural assets)")
    MAT.register_gltf_materials(builder, sets, only=MATERIALS)

    # Tangents are intentionally omitted: Godot's glTF importer generates them
    # for normal-mapped materials, and shipping them would add sixteen bytes a
    # vertex to a package that is already dominated by vertex data.
    def prepare(piece: M.Mesh) -> M.Mesh:
        piece.sanitise_normals()
        piece.drop_degenerate()
        piece.weld(1e-4)
        return piece

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

    root = GLTF.Node("Mirrorhold")
    root_index = builder.add_node(root)
    groups = {}
    for group_name in ("Terrain", "Water", "Forest", "Structures", "Props",
                       "Boundary"):
        groups[group_name] = builder.add_node(GLTF.Node(f"Group_{group_name}"),
                                              root_index)

    # -- terrain and water ------------------------------------------------
    for name, piece in build.terrain_meshes.items():
        if piece.triangle_count == 0:
            continue
        builder.add_mesh(name, prepare(piece), with_tangents=False)
        parent = groups["Boundary"] if name.startswith("Backdrop") else groups["Terrain"]
        builder.add_node(GLTF.Node(name, mesh=name), parent)
    for name, piece in build.water_meshes.items():
        if piece.triangle_count == 0:
            continue
        builder.add_mesh(name, prepare(piece), with_tangents=False)
        builder.add_node(GLTF.Node(name, mesh=name), groups["Water"])

    # -- placements --------------------------------------------------------
    kind_group = {
        "tree": "Forest", "foliage": "Forest", "undergrowth": "Forest",
        "leafdrift": "Forest", "mushrooms": "Forest", "fallenlog": "Forest",
        "stump": "Forest", "rock": "Forest",
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
COLLISION_CELL = 0.5
COLLISION_HEIGHT_STEP = 0.2
COLLISION_HEIGHT_ORIGIN = -2.2


def build_collision(build: REG.RegionBuild) -> tuple[bytes, int, int, dict]:
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

    walkable = (ground > REG.SEA_LEVEL + 0.35) & (slope < 1.05)
    # solid structures block their footprint
    blockers = np.zeros_like(walkable)
    for placement in build.placements:
        if not placement.collides:
            continue
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        # trees block only their trunk, not the spread of their canopy
        footprint = float(max(abs(low[0]), abs(high[0]), abs(low[2]), abs(high[2]))) \
            * placement.scale
        factor = 0.16 if placement.kind in ("tree", "foliage") else 0.62
        radius = min(max(footprint * factor, 0.40), 11.0)
        px, _, pz = placement.position
        blockers |= (np.hypot(gx - px, gz - pz) < radius)
    walkable &= ~blockers

    surface = ground.copy()
    # An overhead walk surface owns its footprint: the client grounds an actor
    # on the highest walk surface below the ray, so a two-level column cannot be
    # expressed on a flat server grid. Bridges, decks and platforms therefore
    # take the cell, and the ground under them is not separately walkable.
    elevated = 0
    for placement in build.placements:
        item = build.meshes[placement.mesh]
        walk_bounds = getattr(item, "walk_bounds", lambda: None)()
        if walk_bounds is None and not placement.walk_surface:
            continue
        if walk_bounds is None:
            low, high = item.bounds()
        else:
            low, high = walk_bounds
        px, py, pz = placement.position
        half_x = float(max(abs(low[0]), abs(high[0]))) * placement.scale
        half_z = float(max(abs(low[2]), abs(high[2]))) * placement.scale
        deck_y = py + float(high[1]) * placement.scale
        radius = max(min(half_x, half_z) * 0.85, 0.4)
        footprint = np.hypot(gx - px, gz - pz) < radius
        if not footprint.any():
            continue
        if deck_y > ground.max() + 200.0:
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
def render_minimap(build: REG.RegionBuild, sets, path: Path, size: int = 768) -> dict:
    """Top-down orthographic-ish capture of the finished geometry."""
    import preview
    scene = preview.scene_from_build(build, sets)
    centre_x = (REG.PLAY_MIN_X + REG.PLAY_MAX_X) * 0.5
    centre_z = (REG.PLAY_MIN_Z + REG.PLAY_MAX_Z) * 0.5
    extent = max(REG.PLAY_MAX_X - REG.PLAY_MIN_X, REG.PLAY_MAX_Z - REG.PLAY_MIN_Z)
    altitude = 900.0
    fov = 2.0 * math.degrees(math.atan((extent * 0.5) / altitude))
    lighting = RENDER.Lighting(sun_direction=(-0.30, 0.90, 0.32),
                               fog_density=0.0, ambient_strength=0.72,
                               shadow_strength=0.35, sun_color=(1.10, 0.96, 0.74))
    image = scene.render(eye=(centre_x, altitude, centre_z + 0.01),
                         target=(centre_x, 0.0, centre_z),
                         width=size, height=size, fov=fov, lighting=lighting,
                         shadows=True, shadow_size=2048,
                         shadow_center=(centre_x, 20.0, centre_z),
                         shadow_radius=extent * 0.62, near=200.0, far=1400.0)
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
def write_manifest(build: REG.RegionBuild, stats: dict, collision_stats: dict,
                   minimap: dict, path: Path) -> dict:
    t = build.terrain
    lows = []
    highs = []
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

    surface_prefixes = ["Terrain_", "Walk_"]
    collision_nodes = sorted({p.node for p in build.placements if p.collides})

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "assetVersion": ASSET_VERSION,
        "asset": {
            "id": "mirrorhold",
            "name": "Mirrorhold",
            "glb": "world.glb",
            "units": "meters",
            "coordinateSystem": {"handedness": "right", "upAxis": "Y",
                                 "northAxis": "-Z"},
            "origin": [0, 0, 0],
            "bounds": {"min": [round(float(v), 2) for v in bounds_min],
                       "max": [round(float(v), 2) for v in bounds_max]},
            "playableBounds": {
                "min": [REG.PLAY_MIN_X, round(float(t.height.min()), 2), REG.PLAY_MIN_Z],
                "max": [REG.PLAY_MAX_X, round(float(t.height.max()), 2), REG.PLAY_MAX_Z]},
            "seaLevel": REG.SEA_LEVEL,
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
                         "six-bit field cannot express Mirrorhold's relief; the "
                         "grid is authoritative for walkability, and the Godot "
                         "loader takes elevation from the rendered walk "
                         "surfaces, not from this file."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
        },
        "navigation": {
            "surfaceNodePrefixes": surface_prefixes,
            "walkableAreas": ["forest-floor", "trails", "paving", "shore", "meadow",
                              "bridges", "canopy-platforms", "docks", "stairs"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every built "
                "walkable surface is named Walk_<...>. The client turns both "
                "into the navigation collision layer the grounding ray tests.",
                "Bridges and canopy platforms are walk surfaces, so a downward "
                "grounding ray under one resolves onto the deck above; the "
                "terrain beneath them is water or ravine and is not walkable.",
            ],
        },
        "landmarks": build.landmarks,
        "interactives": build.interactives,
        "npcMarkers": build.npc_markers,
        "harvestables": build.harvestables,
        "portals": build.portals,
        "roads": [{"id": name,
                   "waypoints": [[round(float(p[0]), 1),
                                  round(float(t.height_at(p[0], p[1])), 2),
                                  round(float(p[1]), 1)] for p in points]}
                  for name, points in REG.ROUTES.items()],
        "water": {
            "seaLevel": REG.SEA_LEVEL,
            "serverCells": REG.SERVER_CELLS,
            "bodies": [{"id": name, "node": name,
                        "type": ("sea" if "Sea" in name
                                 else "waterfall" if "Falls" in name
                                 else "stream" if "Stream" in name else "pool")}
                       for name in build.water_meshes],
            "streams": [{"id": name,
                         "waypoints": [[round(float(p[0]), 1),
                                        round(float(t.height_at(p[0], p[1])), 2),
                                        round(float(p[1]), 1)] for p in points]}
                        for name, points in REG.STREAMS.items()],
        },
        # The authored extents, in the frame everything else in this manifest
        # uses. The playable footprint is the server grid; the terrain is cut
        # larger so no reachable tile is ever off the mesh.
        "bounds": {
            "playable": {
                "min": [round(float(REG.PLAY_MIN_X), 2), round(float(bounds_min[1]), 2),
                        round(float(REG.PLAY_MIN_Z), 2)],
                "max": [round(float(REG.PLAY_MAX_X), 2), round(float(bounds_max[1]), 2),
                        round(float(REG.PLAY_MAX_Z), 2)],
            },
            "terrain": {
                "min": [round(float(REG.TERRAIN_X0), 2), round(float(bounds_min[1]), 2),
                        round(float(REG.TERRAIN_Z0), 2)],
                "max": [round(float(REG.TERRAIN_X0 + REG.TERRAIN_SIZE_X), 2),
                        round(float(bounds_max[1]), 2),
                        round(float(REG.TERRAIN_Z0 + REG.TERRAIN_SIZE_Z), 2)],
            },
            "waterLevel": REG.LAKE_LEVEL,
            "metresPerServerTile": REG.METRES_PER_TILE,
            "serverCells": REG.SERVER_CELLS,
        },
        "environment": {
            "sky": {"type": "gradient", "zenith": [0.15, 0.25, 0.42],
                    "horizon": [0.58, 0.56, 0.50]},
            "sun": {"direction": [-0.46, 0.50, 0.73],
                    "color": [1.22, 0.94, 0.60], "energy": 1.15},
            "ambient": {"skyColor": [0.22, 0.30, 0.42],
                        "groundColor": [0.08, 0.06, 0.04], "energy": 0.30},
            "saturation": 1.30,
            "fog": {"enabled": True, "color": [0.38, 0.37, 0.35],
                    "density": 0.0007, "heightFalloff": 0.003},
            "goldenHour": {"sun": {"direction": [-0.82, 0.20, 0.53],
                                   "color": [1.55, 0.94, 0.52]},
                           "fog": {"color": [0.62, 0.50, 0.38], "density": 0.0022}},
            "presentation": {
                "fallingLeaves": {"enabled": True, "density": 0.6,
                                  "zones": ["forest-core", "settlement"]},
                "mist": {"enabled": True, "zones": ["mill-pool", "ravine", "coast"]},
                "chimneySmoke": {"enabled": True,
                                 "nodes": ["Landmark_MootHall", "Building_Lodge_00",
                                           "Building_Lodge_02", "Landmark_CharcoalKiln_0"]},
                "waterSpray": {"enabled": True, "nodes": ["Water_Falls"]},
                "ambientAudio": [
                    {"id": "forest-day", "zone": "forest-core"},
                    {"id": "surf", "zone": "coast"},
                    {"id": "settlement", "zone": "settlement"},
                    {"id": "wind-barren", "zone": "transition"}],
            },
            "zones": [
                {"id": "forest-core", "centre": [20.0, 32.0, -116.0], "radius": 124.0},
                {"id": "coast", "centre": [-60.0, 4.0, 0.0], "radius": 104.0},
                {"id": "settlement", "centre": [16.0, 32.0, -112.0], "radius": 60.0},
                {"id": "transition", "centre": [216.0, 20.0, -40.0], "radius": 92.0},
            ],
        },
        "minimap": minimap,
        "lodGroups": [
            {"id": "forest", "strategy": "authored-detail-tiers",
             "levels": [{"id": "near", "suffix": "_high"},
                        {"id": "mid", "suffix": "_mid"},
                        {"id": "far", "suffix": "_low"}]}],
        "performance": stats,
        "sources": [
            {"id": "aerial-concept",
             "file": "references/01-concept-aerial-overview.png",
             "role": "authoritative-composition"},
            {"id": "detail-board",
             "file": "references/00-concept-detail-board.png",
             "role": "authoritative-player-scale"},
            {"id": "generator", "file": "source/build_mirrorhold.py",
             "role": "reproducible-build", "seed": SEED},
        ],
        "provenance": {
            "assets": "original to Eloria/Nymara; generated by _toolkit/amberwood/*",
            "thirdParty": "none",
            "textures": "procedural (numpy + Pillow), no sampled or traced source",
            "geometry": "procedural (numpy), no imported models",
            "license": "same as the Eloria client repository",
        },
        "productionStatus": "production-geometry-materials-population",
        "knownLimitations": [],
    }
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PACKAGE))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--skip-minimap", action="store_true")
    parser.add_argument("--skip-lod2", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    import preview
    sets = preview.texture_sets()

    build = build_region(args.seed)

    t0 = time.time()
    builder, stats = export_glb(build, sets, out / "world.glb")
    print(f"[glb] {stats['glbBytes'] / 1e6:.2f} MB, {stats['nodes']} nodes, "
          f"{stats['uniqueTriangles']} unique tris, "
          f"{stats['instancedTriangles']} instanced tris "
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

    texture_bytes = sum(sum(len(v) for v in ts.images().values()) for ts in sets.values())
    stats["embeddedTextureBytes"] = texture_bytes
    stats["textureMemoryBytesUncompressed"] = sum(
        ts.base_color.shape[0] * ts.base_color.shape[1] * 4 * 3 for ts in sets.values())
    stats["placements"] = len(build.placements)
    stats["collision"] = collision_stats
    stats["notes"] = build.notes

    manifest = write_manifest(build, stats, collision_stats, minimap,
                              out / "world.json")
    print(f"[manifest] {len(manifest['landmarks'])} landmarks, "
          f"{len(manifest['interactives'])} interactives, "
          f"{len(manifest['harvestables'])} harvestables, "
          f"{len(manifest['portals'])} portals")

    report = validate_gltf.validate(str(out / "world.glb"))
    payload = report.to_dict()
    (out / "world.glb.validator.json").write_text(json.dumps(payload, indent=2) + "\n")
    counts = payload["issues"]
    print(f"[validate] errors={counts['numErrors']} warnings={counts['numWarnings']} "
          f"infos={counts['numInfos']}")
    for message in report.messages:
        if message["severity"] <= 1:
            print("   ", message["code"], message["message"], message["pointer"])

    if not args.skip_lod2:
        t0 = time.time()
        # the reduced package also drops texture resolution, which is where
        # most of a self-contained GLB's bytes actually are
        lod_sets = {name: texture_set.reduced()
                    for name, texture_set in sets.items()}
        lod_build = build_region(args.seed, lod="far")
        lod_build.terrain_meshes = lod_build.terrain.build_meshes(uv_scale=0.28)
        _, lod_stats = export_glb(lod_build, lod_sets, out / "world-lod2.glb")
        stats["lod2"] = {
            "glbBytes": lod_stats["glbBytes"],
            "nodes": lod_stats["nodes"],
            "uniqueTriangles": lod_stats["uniqueTriangles"],
            "instancedTriangles": lod_stats["instancedTriangles"],
            "sizeReductionPercent": round(
                100.0 * (1.0 - lod_stats["glbBytes"] / stats["glbBytes"]), 1),
            "triangleReductionPercent": round(
                100.0 * (1.0 - lod_stats["instancedTriangles"]
                         / stats["instancedTriangles"]), 1),
        }
        report_lod = validate_gltf.validate(str(out / "world-lod2.glb")).to_dict()
        (out / "world-lod2.glb.validator.json").write_text(
            json.dumps(report_lod, indent=2) + "\n")
        print(f"[lod2] {lod_stats['glbBytes'] / 1e6:.2f} MB, "
              f"{lod_stats['instancedTriangles']} instanced tris, "
              f"{stats['lod2']['triangleReductionPercent']}% fewer "
              f"({time.time() - t0:.1f}s)")
        manifest["lodGroups"].append({
            "id": "package-lod2", "glb": "world-lod2.glb",
            "strategy": "reduced-package",
            "notes": "Far-tier vegetation only, no ground clutter."})
        (out / "world.json").write_text(json.dumps(manifest, indent=2) + "\n")

    (out / "performance-summary.md").write_text(
        "# Mirrorhold performance summary\n\n```json\n"
        + json.dumps(stats, indent=2) + "\n```\n", encoding="utf-8")
    return 0 if counts["numErrors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
