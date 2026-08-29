#!/usr/bin/env python3
"""Build the Grey Moors runtime map package.

Outputs, next to this source tree:

    ../world.glb        self-contained glTF 2.0 (geometry, materials, textures)
    ../world.json       GLB world manifest, schema version 1
    ../collision.bin    half-metre walkability grid (EWCG v1)
    ../minimap.webp     minimap rendered from the final geometry
    ../world.glb.validator.json
    ../performance-summary.md

Deterministic: the same seed reproduces the same bytes.

Like the other production regions this passes `only=` to
`register_gltf_materials`, so the package embeds only the textures this region
actually uses. With several regions appending their kits to the shared material
table, a build that embeds all of them grows by roughly ten megabytes of PNG
per kit for no visible gain.
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
from amberwood import terrain as TER

import populate as POP
import region as REG

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SEED = 20260829

ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# The materials this region embeds. Named explicitly rather than derived, so a
# kit added by another region cannot silently enlarge this package.
MATERIALS: frozenset[str] = frozenset({
    # ground
    "grey_heather_moor", "grey_peat_bog", "grey_causeway", "grey_barrow_turf",
    "grey_moor_track", "cliff_rock", "shore_shingle",
    # built and grown
    "grey_moor_granite", "grey_carved_stone", "grey_drystone", "grey_bog_timber",
    "grey_turf_roof", "grey_dead_bark", "grey_moor_scrub",
    # water and light
    "grey_bog_water", "water_sea", "grey_wisp", "grey_votive_flame",
    # small shared pieces the kit reuses rather than duplicating
    "dark_iron", "timber_grey", "lime_plaster", "charred_timber",
})


# --------------------------------------------------------------------------
def build_region(seed: int = SEED, lod: str | None = None,
                 terrain_only: bool = False) -> REG.RegionBuild:
    """Build the region. `lod="far"` produces the reduced second package.

    `terrain_only` stops after the ground is sculpted, painted and meshed. The
    production guide requires the grounding contract to be proved on bare
    terrain before any detail work goes in, and this is how that is run.
    """
    t0 = time.time()
    terrain = REG.build_terrain(seed)
    REG.close_world(terrain)
    REG.apply_built_ground(terrain, seed)
    build = REG.RegionBuild(terrain=terrain)

    # Surfaces are painted before the placement passes, not after: the bog
    # and ground-dressing passes choose their sites by surface class, and if the
    # classes are still unpainted they scatter nothing at all.
    REG.assign_surfaces(terrain, seed)

    if not terrain_only:
        POP.populate_landmarks(build, seed, lod=lod)
        POP.populate_routes(build, seed, lod=lod)
        POP.populate_bog(build, seed, lod=lod)
        if lod is None:
            POP.populate_ground_detail(build, seed)

    POP.build_water(build)

    build.terrain_meshes = terrain.build_meshes(uv_scale=0.28)
    # The backdrop is the distant mountain ring. It comes out of the toolkit in
    # Amberwood's cliff rock, so it is retinted into this region's storm rock -
    # otherwise the horizon is grey while everything in front of it is violet.
    # The backdrop is the distant higher moor closing the horizon. It comes out
    # of the toolkit in Amberwood's cliff rock, which is already the grey this
    # region wants, so unlike Amethyst it is not retinted.
    backdrop = TER.backdrop(terrain, reach=240.0, cell=11.0, seed=seed + 909)
    build.terrain_meshes["Backdrop_Distant"] = backdrop
    build.resolve_names()
    _add_spawns_and_portals(build)
    _add_population_markers(build, seed)
    print(f"[region] built in {time.time() - t0:.1f}s")
    return build


def _add_spawns_and_portals(build: REG.RegionBuild) -> None:
    t = build.terrain
    for spawn_id, key, facing in (
            ("default", "arrival", 0.0),
            ("barrow-court", "great_barrow_court", math.pi),
            ("coast-landing", "coast_landing", math.pi * 0.5)):
        x, z = REG.ANCHORS[key]
        y = float(t.height_at(x, z))
        build.spawns.append({
            "id": spawn_id,
            "position": [round(float(x), 2), round(y + 0.05, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": round(math.degrees(facing), 1),
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True})

    # Edge portals to neighbouring Nymara regions. Destination map ids follow the
    # client registry; the server remains authoritative for the transition.
    # Adjacency is NOT this package's to invent. The server's own
    # `config/eloria/maps.txt` already declares Grey Moors' neighbours, and it
    # gives exactly two: sunmane_steppe on the west edge and westhaven on the
    # east. The server tiles below are that file's own waygate positions,
    # rescaled from the 192-cell grid to this region's 576-cell one the same
    # way Whitehorn Range's were - x3 about the arrival datum, which turns
    # (6, 58) and (110, 58) into (18, 174) and (330, 174).
    for portal_id, name, tile, destination in (
            ("west-waygate", "Sunmane Track", (18, 174),
             "maps/nymara/sunmane_steppe.elm"),
            ("east-waygate", "Westhaven Road", (330, 174),
             "maps/nymara/westhaven.elm")):
        x = (tile[0] - REG.SERVER_ORIGIN[0]) * REG.METRES_PER_TILE
        z = -(tile[1] - REG.SERVER_ORIGIN[1]) * REG.METRES_PER_TILE
        y = float(t.height_at(x, z))
        build.portals.append({
            "id": portal_id, "name": name, "type": "map-transition",
            "position": [round(float(x), 2), round(y + 0.1, 2), round(float(z), 2)],
            "serverTile": [int(tile[0]), int(tile[1])],
            "destinationMap": destination, "radius": 3.5,
            "authority": "server"})

    # Interior entrances. The Grey Moor barrows are already a planned insides
    # map (`source-elm/grey_moor_barrows.elm`, and an interior package under
    # `interiors/grey_moor_barrows/`), so every door targets that map and
    # differs only in which arrival point it asks for. Each door also gets a
    # spawn of the same name on this map, so the return portal on the insides
    # map has somewhere to put the player back.
    for portal_id, name, landmark_id in (
            ("great-barrow-mouth", "The Great Barrow", "grey-great-barrow"),
            ("west-crypt-stair", "The West Crypt", "grey-crypt-west"),
            ("east-crypt-stair", "The East Crypt", "grey-crypt-east"),
            ("south-crypt-stair", "The Fen Crypt", "grey-crypt-south")):
        anchor = next((l for l in build.landmarks if l.get("id") == landmark_id), None)
        if anchor is None:
            continue
        x, y, z = anchor["position"]
        position = [round(float(x), 2), round(float(y) + 0.1, 2), round(float(z), 2)]
        tile = [int(round(x + REG.SERVER_ORIGIN[0])),
                int(round(REG.SERVER_ORIGIN[1] - z))]
        build.portals.append({
            "id": portal_id, "name": name, "type": "interior-entrance",
            "position": position, "serverTile": tile, "landmark": landmark_id,
            "destinationMap": "maps/nymara/grey_moor_barrows.elm",
            "destinationSpawn": portal_id, "radius": 2.5,
            "authority": "server"})
        build.spawns.append({
            "id": portal_id,
            "position": [position[0], round(float(t.height_at(x, z)) + 0.05, 2),
                         position[2]],
            "serverTile": tile,
            "rotationDegrees": 0.0,
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True,
            "note": "return point from the Grey Moor barrows insides map"})


def _add_population_markers(build: REG.RegionBuild, seed: int) -> None:
    """Editor/visual markers only - the server owns actual spawning."""
    rng = np.random.default_rng(seed ^ 0x5EED)
    t = build.terrain

    def marker(collection, entry):
        collection.append(entry)

    # Every name here is a placeholder: the authoritative written descriptions
    # for Nymara were not available to this session, exactly as they were not
    # available to Amberwood's. See `modeling-assumptions.md`.
    npc_sites = [
        ("barrow-warden", "Warden of the Great Barrow", "great_barrow_court"),
        ("stone-reader", "Reader of the Stones", "ring_centre"),
        ("peat-cutter", "Peat Cutter", "peat_centre"),
        ("bog-guide", "Bog Guide", "moor_gate"),
        ("crypt-keeper", "Keeper of the Fen Crypt", "crypt_south"),
        ("coast-watcher", "Coast Watcher", "shrine_coast"),
        ("croft-widow", "Widow of the Last Croft", "croft_coast"),
        ("lamp-tender", "Lamp Tender", "arrival"),
        ("stone-carter", "Stone Carter", "ring_east"),
        ("moor-ranger", "Moor Ranger", "croft_mid"),
    ]
    for npc_id, name, key in npc_sites:
        x, z = REG.ANCHORS[key]
        marker(build.npc_markers, {
            "id": npc_id, "name": name,
            "position": [round(float(x), 2),
                         round(float(t.height_at(x, z)) + 0.05, 2),
                         round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "role": "editor-marker", "authority": "server"})

    creature_zones = [
        ("barrow-wight", "Barrow Wight", "great_barrow", 60.0),
        ("bog-lurker", "Bog Lurker", "shrine_bog", 52.0),
        ("marsh-wisp", "Marsh Wisp", "hanged_oak", 44.0),
        ("moor-hound", "Moor Hound", "ring_west", 56.0),
        ("cairn-shade", "Cairn Shade", "barrow_far_east", 40.0),
    ]
    for creature_id, name, key, radius in creature_zones:
        x, z = REG.ANCHORS[key]
        marker(build.npc_markers, {
            "id": creature_id, "name": name, "kind": "creature-zone",
            "position": [round(float(x), 2),
                         round(float(t.height_at(x, z)) + 0.05, 2),
                         round(float(z), 2)],
            "radius": radius, "role": "editor-marker", "authority": "server"})

    # harvestables: peat is the region's resource, cut out of the bog
    surface = build.terrain.surface
    harvest_cells = np.argwhere(surface == TER.PEAT_BOG)
    if harvest_cells.size:
        picks = rng.choice(len(harvest_cells), size=min(64, len(harvest_cells)),
                           replace=False)
        for index, cell in enumerate(harvest_cells[picks]):
            cz, cx = int(cell[0]), int(cell[1])
            x = float(t.x0 + cx * t.cell)
            z = float(t.z0 + cz * t.cell)
            if not (REG.PLAY_MIN_X <= x <= REG.PLAY_MAX_X
                    and REG.PLAY_MIN_Z <= z <= REG.PLAY_MAX_Z):
                continue
            build.harvestables.append({
                "id": f"grey-peat-bank-{index:03d}", "resource": "cut-peat",
                "position": [round(x, 2), round(float(t.height_at(x, z)), 2),
                             round(z, 2)],
                "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                               int(round(REG.SERVER_ORIGIN[1] - z))],
                "authority": "server"})


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


def export_glb(build: REG.RegionBuild, sets, path: Path) -> tuple[GLTF.GltfBuilder, dict]:
    builder = GLTF.GltfBuilder(
        generator="Eloria Grey Moors builder (original procedural assets)")
    MAT.register_gltf_materials(builder, sets, only=set(MATERIALS))

    # Tangents are intentionally omitted: Godot's glTF importer generates them
    # for normal-mapped materials, and shipping them would add sixteen bytes a
    # vertex to a package already dominated by vertex data.
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

    root = GLTF.Node("GreyMoors")
    root_index = builder.add_node(root)
    groups = {}
    for group_name in ("Terrain", "Water", "Stones", "Structures", "Props",
                       "Boundary"):
        groups[group_name] = builder.add_node(GLTF.Node(f"Group_{group_name}"),
                                              root_index)

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

    kind_group = {
        "stone": "Stones", "rock": "Stones", "tree": "Props",
        "building": "Structures", "landmark": "Structures",
        "interactive": "Structures", "prop": "Props", "scatter": "Props",
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

    # 0.35 m of freeboard left a handful of half-metre collision cells marked
    # walkable where the rendered shoreline had already dropped below the sea,
    # because the collision grid is sampled at 0.5 m and the terrain is
    # interpolated from a 2 m heightfield. 0.55 m clears it.
    walkable = (ground > REG.SEA_LEVEL + 0.55) & (slope < 1.05)
    blockers = np.zeros_like(walkable)
    for placement in build.placements:
        if not placement.collides:
            continue
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        footprint = float(max(abs(low[0]), abs(high[0]), abs(low[2]), abs(high[2]))) \
            * placement.scale
        factor = 0.30 if placement.kind in ("stone", "scatter") else 0.62
        radius = min(max(footprint * factor, 0.40), 11.0)
        px, _, pz = placement.position
        blockers |= (np.hypot(gx - px, gz - pz) < radius)
    walkable &= ~blockers

    surface = ground.copy()
    # An overhead walk surface owns its footprint: the client grounds an actor on
    # the highest walk surface below the ray, so a two-level column cannot be
    # expressed on a flat server grid. Bridge decks therefore take the cell, and
    # the ground under them is not separately walkable.
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
        # A rotated rectangle, not a circle on the smaller half-extent. A bridge
        # deck is long and narrow, so a circle covers only the middle span and
        # the rest of the deck keeps the gully floor's encoded height - which is
        # exactly what COLLISION_SURFACE_MISMATCH catches.
        cos_r = math.cos(placement.rotation_y)
        sin_r = math.sin(placement.rotation_y)
        dx = gx - px
        dz = gz - pz
        # inverse of mesh.rotation_y: local = R(-theta) . world
        local_x = dx * cos_r - dz * sin_r
        local_z = dx * sin_r + dz * cos_r
        # The deck is claimed to its full extent plus half a cell: trimming it
        # back leaves the last metre of each bridge end encoding the gully floor
        # while the ray overhead still finds the deck.
        footprint = ((np.abs(local_x) <= max(half_x * 0.96, 0.4))
                     & (np.abs(local_z) <= max(half_z * 0.96, 0.4)))
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
    saturated = int(((grid == 63) & walkable).sum())

    payload = struct.pack("<4sHHII", b"EWCG", 1, 0, width, height) + grid.tobytes()
    stats = {
        "width": width, "height": height, "cellMetres": COLLISION_CELL,
        "walkableCells": int(walkable.sum()),
        "blockedCells": int((~walkable).sum()),
        "walkableFraction": round(float(walkable.mean()), 4),
        "elevatedDecks": elevated,
        "saturatedCells": saturated,
        "saturatedFraction": round(saturated / max(int(walkable.sum()), 1), 4),
        "rowOrder": "server-tile-y (row 0 is the +Z southern edge)",
        "columnOrder": "server-tile-x (column 0 is the -X western edge)",
    }
    return payload, width, height, stats



def snap_to_walkable(build: REG.RegionBuild, payload: bytes, width: int,
                     height: int) -> list[str]:
    """Move any spawn or portal that landed on a blocked cell onto the nearest
    walkable one.

    An interior door sits on the landmark it belongs to, and a landmark that
    collides blocks its own footprint - so the doorway tile can end up inside
    the disc the door is attached to, and the server will not let a player stand
    in it. Rather than special-case the radius per landmark, every spawn and
    portal is checked against the finished collision grid and nudged out.
    """
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)
    walk = grid > 0
    moved: list[str] = []

    def cell_of(x: float, z: float) -> tuple[int, int]:
        cx = int((x - REG.PLAY_MIN_X) / COLLISION_CELL)
        cz = int((REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE - z) / COLLISION_CELL)
        return cx, cz

    def world_of(cx: int, cz: int) -> tuple[float, float]:
        x = REG.PLAY_MIN_X + (cx + 0.5) * COLLISION_CELL
        z = REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE - (cz + 0.5) * COLLISION_CELL
        return x, z

    for entry in list(build.spawns) + list(build.portals):
        x, y, z = entry["position"]
        cx, cz = cell_of(x, z)
        if not (0 <= cx < width and 0 <= cz < height):
            continue
        if walk[cz, cx]:
            continue
        best = None
        for radius in range(1, 60):
            lo_z, hi_z = max(cz - radius, 0), min(cz + radius + 1, height)
            lo_x, hi_x = max(cx - radius, 0), min(cx + radius + 1, width)
            window = walk[lo_z:hi_z, lo_x:hi_x]
            if not window.any():
                continue
            zs, xs = np.nonzero(window)
            zs, xs = zs + lo_z, xs + lo_x
            best_index = int(np.argmin((xs - cx) ** 2 + (zs - cz) ** 2))
            best = (int(xs[best_index]), int(zs[best_index]))
            break
        if best is None:
            continue
        nx, nz = world_of(*best)
        entry["position"] = [round(nx, 2), round(float(build.terrain.height_at(nx, nz)) + 0.1, 2),
                             round(nz, 2)]
        entry["serverTile"] = [int(round(nx + REG.SERVER_ORIGIN[0])),
                               int(round(REG.SERVER_ORIGIN[1] - nz))]
        distance = math.hypot(nx - x, nz - z)
        moved.append(f"{entry['id']} moved {distance:.1f} m onto walkable ground")
    return moved


# --------------------------------------------------------------------------
def render_minimap(build: REG.RegionBuild, sets, path: Path, size: int = 768) -> dict:
    """Top-down capture of the finished geometry."""
    import preview
    from amberwood import render as RENDER
    scene = preview.scene_from_build(build, sets)
    centre_x = (REG.PLAY_MIN_X + REG.PLAY_MAX_X) * 0.5
    centre_z = (REG.PLAY_MIN_Z + REG.PLAY_MAX_Z) * 0.5
    extent = max(REG.PLAY_MAX_X - REG.PLAY_MIN_X, REG.PLAY_MAX_Z - REG.PLAY_MIN_Z)
    altitude = 900.0
    fov = 2.0 * math.degrees(math.atan((extent * 0.5) / altitude))
    # a cold storm key, matching the region's environment block
    lighting = RENDER.Lighting(sun_direction=(-0.28, 0.92, 0.28),
                               fog_density=0.0, ambient_strength=0.70,
                               shadow_strength=0.40, sun_color=(0.98, 0.92, 1.04))
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
        "renderedFrom": "final geometry (offline rasteriser)",
    }


# --------------------------------------------------------------------------
def write_manifest(build: REG.RegionBuild, stats: dict, collision_stats: dict,
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

    collision_nodes = sorted({p.node for p in build.placements if p.collides})

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "assetVersion": ASSET_VERSION,
        "asset": {
            "id": "grey_moors",
            "name": "Grey Moors",
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
                "note": ("The six-bit field spans -2.0 m to 10.4 m. A low wet "
                         "moor is the one Nymara biome that fits inside that "
                         "band honestly, so the whole walkable surface is "
                         "authored within it and only "
                         f"{collision_stats['saturatedFraction'] * 100:.1f}% "
                         "of walkable cells saturate - those are the shoulders "
                         "of the closing rim. Elsewhere the encoded height is "
                         "the real surface height, and the server has genuine "
                         "elevation rather than a flat plateau."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
            "saturatedCells": collision_stats["saturatedCells"],
        },
        "navigation": {
            "surfaceNodePrefixes": ["Terrain_", "Walk_"],
            "walkableAreas": ["heather-moor", "causeways", "trails",
                              "barrow-turf", "peat-bog", "shore",
                              "boardwalks", "bridges"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every built "
                "walkable surface is named Walk_<...>. The client turns both "
                "into the navigation collision layer the grounding ray tests.",
                "Boardwalk and causeway-bridge decks are walk surfaces, so a "
                "downward grounding ray under one resolves onto the deck above; "
                "the bog pool beneath them is not separately walkable.",
                "Barrow mounds are terrain, not meshes, so a character walks "
                "over a barrow rather than through it. Only the portal "
                "stonework standing in the mound is geometry.",
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
                                 else "stream" if "River" in name else "pool")}
                       for name in build.water_meshes],
            "streams": [{"id": name,
                         "waypoints": [[round(float(p[0]), 1),
                                        round(float(t.height_at(p[0], p[1])), 2),
                                        round(float(p[1]), 1)] for p in points]}
                        for name, points in REG.STREAMS.items()],
        },
        "environment": {
            # Permanent overcast. The concept has no sun in it: the light is a
            # flat bright grey lid, so the directional term is weak and the
            # ambient term carries most of the illumination. Getting this the
            # usual way round - strong sun, low ambient - gives hard shadows
            # the painting does not have and makes the moor read as a desert.
            "sky": {"type": "gradient", "zenith": [0.20, 0.22, 0.26],
                    "horizon": [0.44, 0.46, 0.47]},
            "sun": {"direction": [-0.30, 0.34, 0.62],
                    "color": [0.86, 0.88, 0.94], "energy": 0.44},
            "ambient": {"skyColor": [0.32, 0.34, 0.36],
                        "groundColor": [0.09, 0.09, 0.08], "energy": 0.46},
            # Below 1.0: the region is deliberately drained of colour so the
            # heather, the votive flames and the wisps are the only things in
            # it that read as coloured at all.
            "saturation": 0.86,
            # Overcast, not bright: the first pass had a white lid and heavy
            # haze and the region read as a foggy beach. This is the same light
            # the offline captures use, in `source/views.py`.
            "fog": {"enabled": True, "color": [0.42, 0.45, 0.46],
                    "density": 0.00115, "heightFalloff": 0.0042},
            "goldenHour": {"sun": {"direction": [-0.88, 0.14, 0.44],
                                   "color": [1.18, 0.92, 0.74]},
                           "fog": {"color": [0.54, 0.46, 0.40], "density": 0.0012}},
            "presentation": {
                "groundMist": {"enabled": True, "density": 0.85,
                               "zones": ["bog", "moor-core", "north-fen"]},
                "wisps": {"enabled": True,
                          "zones": ["bog", "wisp-tree", "north-fen"]},
                "votiveGlow": {"enabled": True,
                               "zones": ["barrow-ridge", "causeways"]},
                "drizzle": {"enabled": True, "zones": ["moor-core", "coast"]},
                "ambientAudio": [
                    {"id": "moor-wind", "zone": "moor-core"},
                    {"id": "curlew", "zone": "north-fen"},
                    {"id": "bog-water", "zone": "bog"},
                    {"id": "surf", "zone": "coast"},
                    {"id": "low-chant", "zone": "barrow-ridge"}],
            },
            "zones": [
                {"id": "moor-core", "centre": [60.0, 4.0, -60.0], "radius": 230.0},
                {"id": "barrow-ridge", "centre": [114.0, 9.0, -273.0], "radius": 150.0},
                {"id": "bog", "centre": [48.0, 2.0, -54.0], "radius": 150.0},
                {"id": "north-fen", "centre": [18.0, 3.0, -270.0], "radius": 130.0},
                {"id": "wisp-tree", "centre": [66.0, 4.0, -168.0], "radius": 60.0},
                {"id": "coast", "centre": [-90.0, 1.0, 96.0], "radius": 140.0},
                {"id": "causeways", "centre": [42.0, 4.0, -66.0], "radius": 200.0},
            ],
        },
        "minimap": minimap,
        "lodGroups": [
            {"id": "stones", "strategy": "authored-detail-tiers",
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
            {"id": "generator", "file": "source/build_grey_moors.py",
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
    parser.add_argument("--terrain-only", action="store_true",
                        help="ground only, for proving grounding before detail")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    import preview
    sets = preview.texture_sets()

    build = build_region(args.seed, terrain_only=args.terrain_only)

    t0 = time.time()
    builder, stats = export_glb(build, sets, out / "world.glb")
    print(f"[glb] {stats['glbBytes'] / 1e6:.2f} MB, {stats['nodes']} nodes, "
          f"{stats['uniqueTriangles']} unique tris, "
          f"{stats['instancedTriangles']} instanced tris "
          f"({time.time() - t0:.1f}s)")

    payload, width, height, collision_stats = build_collision(build)
    (out / "collision.bin").write_bytes(payload)
    nudged = snap_to_walkable(build, payload, width, height)
    for line in nudged:
        print(f"[snap] {line}")
    build.notes.extend(nudged)
    print(f"[collision] {width}x{height} cells, "
          f"{collision_stats['walkableFraction'] * 100:.1f}% walkable, "
          f"{collision_stats['saturatedFraction'] * 100:.1f}% saturated")

    minimap = {"file": "minimap.webp"}
    if not args.skip_minimap:
        t0 = time.time()
        minimap = render_minimap(build, sets, out / "minimap.webp")
        print(f"[minimap] rendered in {time.time() - t0:.1f}s")

    used = {name: ts for name, ts in sets.items()
            if name in {MAT.BY_NAME[m].texture for m in MATERIALS if m in MAT.BY_NAME}}
    texture_bytes = sum(sum(len(v) for v in ts.images().values())
                        for ts in used.values())
    stats["embeddedTextureBytes"] = texture_bytes
    stats["textureMemoryBytesUncompressed"] = sum(
        ts.base_color.shape[0] * ts.base_color.shape[1] * 4 * 3 for ts in used.values())
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
        lod_sets = {name: texture_set.reduced() for name, texture_set in sets.items()}
        lod_build = build_region(args.seed, lod="far")
        lod_build.terrain_meshes = lod_build.terrain.build_meshes(uv_scale=0.28)
        _, lod_stats = export_glb(lod_build, lod_sets, out / "world-lod2.glb")
        stats["lod2"] = {
            "glbBytes": lod_stats["glbBytes"],
            "nodes": lod_stats["nodes"],
            "uniqueTriangles": lod_stats["uniqueTriangles"],
            "instancedTriangles": lod_stats["instancedTriangles"],
        }
        print(f"[lod2] {lod_stats['glbBytes'] / 1e6:.2f} MB, "
              f"{lod_stats['instancedTriangles']} instanced tris "
              f"({time.time() - t0:.1f}s)")
        lod_report = validate_gltf.validate(str(out / "world-lod2.glb"))
        (out / "world-lod2.glb.validator.json").write_text(
            json.dumps(lod_report.to_dict(), indent=2) + "\n")
        write_manifest(build, stats, collision_stats, minimap, out / "world.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
