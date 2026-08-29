#!/usr/bin/env python3
"""Build the Westhaven runtime map package.

Outputs, next to this source tree:

    ../world.glb        self-contained glTF 2.0 (geometry, materials, textures)
    ../world.json       GLB world manifest, schema version 1
    ../collision.bin    half-metre walkability grid (EWCG v1)
    ../minimap.webp     minimap rendered from the final geometry
    ../world.glb.validator.json
    ../performance.json

Deterministic: the same seed reproduces the same bytes.

Structured after `crownwater/source/build_crownwater.py`, which is the pattern
every finished region follows: the export, collision, minimap and camera-view
machinery is region-agnostic and identical, and what differs is the population
call list, the metadata, and the material pin. Nothing here belongs in
`_toolkit/` that is not already in it.
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
from amberwood import noise as N
from amberwood import render as RENDER

from amberwood import terrain as TER

import havenkit as HK
import populate as POP
import region as REG

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SEED = 20260829

ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# The combined insides map every door on this region opens onto. One map key
# for all four interiors, per the Eternal Lands convention: see
# `interiors/westhaven_insides/` and `source/interiors.py`.
INSIDES_MAP = "maps/nymara/westhaven_insides.elm"


# --------------------------------------------------------------------------
def register_materials(sets: dict) -> dict:
    """The toolkit's hook for a region that adds its own material recipes.

    `capture_views.py` calls this through `regionpaths.region_material_sets` so
    an offline preview renders the same materials the GLB ships. Without it the
    preview only has the shared table, and Westhaven's terrain - whose paving,
    turf, shingle, rock and water are all its own - came back as one flat sand
    colour with the sea missing entirely.
    """
    return HK.register(sets)


def build_region(seed: int = SEED, lod: str | None = None) -> REG.RegionBuild:
    """Build the region. `lod="far"` produces the reduced second package:
    far-tier vegetation only and no ground clutter, for low-end machines and for
    distant streaming."""
    t0 = time.time()
    terrain = REG.build_terrain(seed)
    REG.apply_built_ground(terrain, seed)
    build = REG.RegionBuild(terrain=terrain)

    POP.build_water(build, lod=lod)
    POP.populate_surf(build, seed, lod=lod)
    POP.populate_seawall(build, seed)
    POP.populate_waterfront(build, seed)
    POP.populate_shipyard(build, seed)
    POP.populate_city(build, seed)
    POP.populate_lighthouses(build, seed)
    POP.populate_upland(build, seed)
    POP.populate_vegetation(build, seed, lod=lod)
    if lod is None:
        POP.populate_props(build, seed)
    POP.populate_metadata(build, seed)

    build.terrain_meshes = terrain.build_meshes(uv_scale=0.28)
    # No landmass backdrop, for Crownwater's reason and one of Westhaven's own.
    # `terrain.backdrop` takes a single `open_side`, and Westhaven is open on
    # two - the sea closes both the south and the west - so any single choice
    # walls one of them off: the first aerial came back with a continent of
    # grey rock standing out of the ocean along the whole western horizon.
    # Nothing is lost by dropping it. The north and east are closed by an 88 m
    # rim, and the highest place a player can stand is the crown terrace at
    # 52 m, 200 m short of it, so there is no viewpoint that sees over the rim
    # to the sky behind it.
    build.resolve_names()
    _add_spawns_and_portals(build)
    _add_population_markers(build, seed)
    print(f"[region] built in {time.time() - t0:.1f}s")
    return build


def _add_spawns_and_portals(build: REG.RegionBuild) -> None:
    t = build.terrain
    # The default spawn is the quayside at the head of the main quay, facing
    # north up the market stair into the city. That is the arrival datum the
    # server map is built around, and it is the framing of detail-board panel 3:
    # the cobbled street climbing away between the warehouses.
    for spawn_id, (x, z), facing in (
            ("default", REG.SPAWN, math.radians(0.0)),
            ("fish-market", REG.SPAWN_MARKET, math.radians(180.0)),
            ("crown-terrace", REG.SPAWN_CROWN, math.radians(180.0)),
            ("lighthouse", REG.SPAWN_LIGHTHOUSE, math.radians(315.0))):
        y = float(t.height_at(x, z))
        build.spawns.append({
            "id": spawn_id,
            "position": [round(float(x), 2), round(y + 0.05, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": round(math.degrees(facing), 1),
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True})

    # Edge portals to the neighbouring Nymara regions. Destination map ids follow
    # the client registry; the server remains authoritative for the transition.
    # Westhaven is a port, so its outward links are split between two land roads
    # over the upland and two sailing berths on the quay - which is what a
    # harbour city's connections actually are.
    for portal_id, name, anchor, destination, kind in (
            ("north-road", "North Road to Amberwood", "upland_chapel",
             "maps/nymara/amberwood.elm", "road"),
            ("east-road", "Coast Road to the Grey Moors", "hill_estate",
             "maps/nymara/grey_moors.elm", "road"),
            ("crownwater-berth", "Crownwater Packet", "west_quay",
             "maps/nymara/crownwater.elm", "berth"),
            ("mirrorhold-berth", "Mirrorhold Packet", "cargo_pier",
             "maps/nymara/mirrorhold.elm", "berth")):
        x, z = REG.ANCHORS[anchor]
        y = float(t.height_at(x, z))
        build.portals.append({
            "id": portal_id, "name": name, "type": "map-transition",
            "transport": kind,
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": destination, "radius": 3.5,
            "authority": "server"})

    # Doors into the insides map. Four doors, one destination map, and a
    # different `destinationSpawn` for each - the Eternal Lands convention the
    # interiors package follows. Each also gets a *spawn* of the same name on
    # this map, so the return portal standing on that arrival has somewhere to
    # land: without it the round trip resolves one way only.
    for door_id, name, anchor, spawn_id, facing in (
            ("custom-house-door", "The Custom House", "custom_house",
             "custom-house-hall", 180.0),
            ("bonded-vaults-door", "The Bonded Vaults", "warehouse_row",
             "bonded-vaults-tunnel", 180.0),
            # `lighthouse_yard`, not `lighthouse`: the tower's gallery is a
            # walk surface 28 m up, so a door on the tower's own centre has the
            # grounding ray snap it onto the gallery instead of the rock.
            ("lamp-rock-door", "The Lamp Rock Light", "lighthouse_yard",
             "lamp-rock-foot", 315.0),
            ("gullstone-door", "The Gullstone Undertow", "gullstone_watch",
             "gullstone-cleft", 0.0)):
        x, z = REG.ANCHORS[anchor]
        y = float(t.height_at(x, z))
        build.portals.append({
            "id": door_id, "name": name, "type": "map-transition",
            "transport": "door",
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": INSIDES_MAP,
            "destinationSpawn": spawn_id,
            "radius": 3.0, "authority": "server"})
        build.spawns.append({
            "id": spawn_id,
            "name": f"Return from {name}",
            "position": [round(x, 2), round(y + 0.05, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": facing,
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True})


def _add_population_markers(build: REG.RegionBuild, seed: int) -> None:
    """Editor/visual markers only - the server owns actual spawning."""
    t = build.terrain
    rng = N.Rng(seed + 777)

    npc_plan = [
        ("westhaven-harbourmaster", "Harbour Master", "custom_house", 5.0),
        ("westhaven-tide-clerk", "Tide Clerk", "custom_house", 7.0),
        ("westhaven-fishwife", "Fishwife", "fish_market", 5.0),
        ("westhaven-fish-crier", "Fish Crier", "fish_market", 8.0),
        ("westhaven-stevedore", "Stevedore", "cargo_pier", 5.0),
        ("westhaven-crane-hand", "Crane Hand", "crane_pier", 4.0),
        ("westhaven-shipwright", "Shipwright", "shipyard", 6.0),
        ("westhaven-caulker", "Caulker", "shipyard_slip", 5.0),
        ("westhaven-ropemaker", "Ropemaker", "ropewalk", 5.0),
        ("westhaven-chandler", "Ship's Chandler", "chandlery", 4.0),
        ("westhaven-gate-serjeant", "Gate Serjeant", "city_gate", 4.0),
        ("westhaven-guild-factor", "Guild Factor", "guild_hall", 5.0),
        ("westhaven-arcade-scribe", "Arcade Scribe", "arcade", 6.0),
        ("westhaven-cathedral-warden", "Warden of the Haven", "cathedral", 8.0),
        ("westhaven-bell-ringer", "Campanile Bell-Ringer", "campanile", 4.0),
        ("westhaven-astronomer", "Dome Astronomer", "brass_dome", 5.0),
        ("westhaven-lightkeeper", "Lightkeeper", "lighthouse", 4.0),
        ("westhaven-mole-watch", "Mole Watchman", "mole_bastion", 4.0),
        ("westhaven-drover", "Upland Drover", "upland_farm", 7.0),
        ("westhaven-chapel-warden", "Chapel Warden", "upland_chapel", 4.0),
    ]
    for npc_id, label, anchor, radius in npc_plan:
        centre = REG.ANCHORS[anchor]
        angle = float(rng.uniform(0, math.pi * 2))
        x = centre[0] + math.cos(angle) * radius
        z = centre[1] + math.sin(angle) * radius
        y = float(t.height_at(x, z))
        build.npc_markers.append({
            "id": npc_id, "name": label, "type": "npc",
            "position": [round(x, 2), round(y, 2), round(z, 2)],
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


def export_glb(build: REG.RegionBuild, sets, path: Path,
               pin: frozenset[str] | None = None) -> tuple[GLTF.GltfBuilder, dict]:
    builder = GLTF.GltfBuilder(
        generator="Eloria Westhaven builder (original procedural assets)")
    # Fail loudly and early if a kit piece introduces a material the pin does
    # not cover. Without this the first sign of trouble is a KeyError from deep
    # inside the GLB writer, naming a merged sub-mesh rather than the piece that
    # actually pulled the material in.
    used = set()
    for item in list(build.meshes.values()):
        for piece in (getattr(item, "all_parts", None) or [item]):
            used.add(piece.material)
    for table in (build.terrain_meshes, build.water_meshes):
        for piece in table.values():
            used.add(piece.material)
    pin = HK.MATERIALS if pin is None else pin
    unpinned = sorted(used - pin)
    if unpinned:
        raise SystemExit(
            "materials used but not in havenkit.MATERIALS: "
            + ", ".join(unpinned))
    # The other direction is not an error but it is not free either: every
    # pinned material embeds its textures whether or not a mesh references it.
    # Amberwood's pin carries six such and pays 2.79 MB for them.
    unused = sorted(pin - used)
    if unused:
        print("[materials] WARNING pinned but unreferenced, costing bytes: "
              + ", ".join(unused))

    # Pinned by name to the materials Westhaven actually uses. Without `only=`
    # the package embeds the whole shared library - about ten megabytes of forest
    # and burnt-country textures this region never references - and, worse, its
    # contents would change whenever another region appends to the shared table.
    MAT.register_gltf_materials(builder, sets, only=pin)

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

    root = GLTF.Node("Westhaven")
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
    # Cells an elevated deck claims. A spawn or a door must never be relocated
    # under one: the cell is walkable, and its *ground* can be dry - the harbour
    # gate's piers stand on land - but what the client's ray finds there is the
    # deck overhead, so anything placed on the ground reads as buried. Recorded
    # on the build so `nudge_onto_walkable` can exclude them.
    deck_mask = np.zeros_like(walkable)
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
        # The deck's real extent, not a symmetric half-extent about its origin.
        # A quay apron sits entirely to one side of its placement point, so
        # mirroring it claimed walkable ground on the water side where there is
        # no deck at all - the ray found the lagoon floor 13 m below.
        x0, x1 = float(low[0]) * placement.scale, float(high[0]) * placement.scale
        z0, z1 = float(low[2]) * placement.scale, float(high[2]) * placement.scale
        inset_x = (x1 - x0) * 0.03
        inset_z = (z1 - z0) * 0.03
        deck_y = py + float(high[1]) * placement.scale
        # An oriented rectangle, not a disc. Amberwood's decks were roughly
        # square, so a circle inscribed in the bounds covered them; Westhaven's
        # causeways are 48 m x 5.4 m, and the inscribed circle covers 2.3 m of
        # a 48 m deck. Everything outside it kept the lagoon floor's height and
        # showed up as collision-versus-surface disagreement along every span.
        angle = float(placement.rotation_y or 0.0)
        c, sn = math.cos(angle), math.sin(angle)
        local_x = c * (gx - px) - sn * (gz - pz)
        local_z = sn * (gx - px) + c * (gz - pz)
        footprint = ((local_x >= x0 + inset_x) & (local_x <= x1 - inset_x)
                     & (local_z >= z0 + inset_z) & (local_z <= z1 - inset_z))
        if not footprint.any():
            continue
        if deck_y > ground.max() + 200.0:
            continue
        elevated += 1
        deck_mask |= footprint
        surface = np.where(footprint, deck_y, surface)
        walkable = np.where(footprint, True, walkable)

    quantised = np.clip(np.round((surface - COLLISION_HEIGHT_ORIGIN)
                                 / COLLISION_HEIGHT_STEP), 1, 63).astype(np.uint8)
    grid = np.where(walkable, quantised, 0).astype(np.uint8)

    build.deck_mask = deck_mask
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


def nudge_onto_walkable(build: REG.RegionBuild, payload: bytes,
                        width: int, height: int) -> list[dict]:
    """Move any spawn or portal that landed on a blocked cell onto a walkable one.

    A landmark that collides blocks its own footprint, and a doorway is attached
    to the landmark - so the natural place to put a door is exactly the place
    the collision grid has just marked unwalkable. The Amethyst Barrens session
    found two of its four doors sitting on blocked tiles this way. Rather than
    hand-tune coordinates that will drift the next time the geometry moves, this
    finds the nearest walkable cell and reports how far it had to go.

    Runs after `build_collision`, because the grid it tests against has to be
    the finished one.
    """
    grid = np.frombuffer(payload, dtype=np.uint8, offset=16).reshape(height, width)
    walkable = grid > 0
    if not walkable.any():
        return []
    # An elevated deck makes its footprint walkable at deck height, so a naive
    # nearest-walkable search can move a portal onto a bridge over open water
    # and then record its Y from the terrain twenty metres below. Candidates are
    # restricted to cells whose *ground* is above the water line, which is what
    # "somewhere to stand" means for a spawn or a door.
    ground_all = build.terrain.height_at(
        REG.PLAY_MIN_X + (np.arange(width)[None, :] + 0.5) * COLLISION_CELL,
        REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE
        - (np.arange(height)[:, None] + 0.5) * COLLISION_CELL)
    walkable = walkable & (ground_all > REG.SEA_LEVEL + 0.35)
    deck_mask = getattr(build, "deck_mask", None)
    if deck_mask is not None and deck_mask.shape == walkable.shape:
        walkable = walkable & ~deck_mask
    if not walkable.any():
        return []
    rows, cols = np.nonzero(walkable)
    cell_x = REG.PLAY_MIN_X + (cols + 0.5) * COLLISION_CELL
    cell_z = REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE - (rows + 0.5) * COLLISION_CELL

    moved = []
    for entry in build.spawns + build.portals:
        x, y, z = entry["position"]
        col = int(np.clip((x - REG.PLAY_MIN_X) / COLLISION_CELL - 0.5, 0, width - 1))
        row = int(np.clip((REG.SERVER_ORIGIN[1] * REG.METRES_PER_TILE - z)
                          / COLLISION_CELL - 0.5, 0, height - 1))
        if walkable[row, col]:
            continue
        distances = np.hypot(cell_x - x, cell_z - z)
        best = int(np.argmin(distances))
        nx, nz = float(cell_x[best]), float(cell_z[best])
        ny = float(build.terrain.height_at(nx, nz))
        offset = round(float(distances[best]), 2)
        entry["position"] = [round(nx, 2), round(ny + (y - _ground_of(build, x, z)), 2),
                             round(nz, 2)]
        entry["serverTile"] = [int(round(nx + REG.SERVER_ORIGIN[0])),
                               int(round(REG.SERVER_ORIGIN[1] - nz))]
        entry["nudgedMetres"] = offset
        moved.append({"id": entry["id"], "metres": offset})
    return moved


def _ground_of(build: REG.RegionBuild, x: float, z: float) -> float:
    return float(build.terrain.height_at(x, z))


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
def write_camera_views(build: REG.RegionBuild, path: Path) -> dict:
    """Emit the Godot capture harness's view table from `source/views.py`.

    The offline renderer and the in-client harness must frame the same shots or
    the comparison sheets compare two different things. `views.py` is the single
    source of truth; this converts its design-space, ground-relative entries
    into the absolute world positions Godot wants, using the terrain that was
    actually built.
    """
    import views as VIEWTABLE

    t = build.terrain

    # Solid world-space boxes the camera must not end up inside or underneath.
    # Blind design-space framings put seven of the first twenty-three cameras
    # under a causeway deck or inside a quay wall: the causeways radiate from
    # the centre along the same diagonals a hand-picked viewpoint tends to fall
    # on. Checking is cheaper and more reliable than guessing.
    boxes = []
    for placement in build.placements:
        if placement.kind not in ("landmark", "building"):
            continue
        item = build.meshes[placement.mesh]
        low, high = item.bounds()
        angle = float(placement.rotation_y or 0.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        corners = []
        for lx in (low[0], high[0]):
            for lz in (low[2], high[2]):
                corners.append((cosine * lx + sine * lz, -sine * lx + cosine * lz))
        xs = [c[0] * placement.scale + placement.position[0] for c in corners]
        zs = [c[1] * placement.scale + placement.position[2] for c in corners]
        boxes.append((min(xs), max(xs), min(zs), max(zs),
                      placement.position[1] + float(low[1]) * placement.scale,
                      placement.position[1] + float(high[1]) * placement.scale))

    # Walk-deck boxes, for cameras that stand on a causeway rather than on ground.
    decks = []
    for placement in build.placements:
        item = build.meshes[placement.mesh]
        bounds = getattr(item, "walk_bounds", lambda: None)()
        if bounds is None:
            continue
        low, high = bounds
        angle = float(placement.rotation_y or 0.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        corners = []
        for lx in (low[0], high[0]):
            for lz in (low[2], high[2]):
                corners.append((cosine * lx + sine * lz, -sine * lx + cosine * lz))
        xs = [c[0] * placement.scale + placement.position[0] for c in corners]
        zs = [c[1] * placement.scale + placement.position[2] for c in corners]
        decks.append((min(xs), max(xs), min(zs), max(zs),
                      placement.position[1] + float(low[1]) * placement.scale,
                      placement.position[1] + float(high[1]) * placement.scale))

    def clear_eye(x, y, z):
        """Lift a camera that sits inside, or directly under, solid geometry."""
        for x0, x1, z0, z1, y0, y1 in boxes:
            if not (x0 - 1.2 <= x <= x1 + 1.2 and z0 - 1.2 <= z <= z1 + 1.2):
                continue
            if y <= y1 + 1.6:
                y = y1 + 2.4
        return y

    entries = []
    for (name, panel, eye_xz, eye_h, target_xz, target_h, fov, _size,
         _radius, mode) in VIEWTABLE.VIEWS:
        ex, ez = eye_xz[0] * REG.SCALE, eye_xz[1] * REG.SCALE
        tx, tz = target_xz[0] * REG.SCALE, target_xz[1] * REG.SCALE
        ey = float(t.height_at(ex, ez)) + eye_h
        ty = float(t.height_at(tx, tz)) + target_h
        # a camera below the waterline sees nothing but the water plane's
        # underside; lift any eye that the terrain put under the lagoon
        if mode == "deck":
            # Stand on a causeway deck the way the client grounds an actor:
            # snap to the highest walk surface under the eye, then add eye
            # height. A ground-relative height cannot express this - the ground
            # under a causeway is sometimes the lagoon floor at -6.6 and
            # sometimes an island shelf at -1.3, and the same declared height
            # therefore lands 1.7 m above the deck in one place and 7 m above it
            # in another. Two attempts at panel 4 failed exactly that way.
            deck = None
            for x0, x1, z0, z1, y0, y1 in decks:
                if x0 <= ex <= x1 and z0 <= ez <= z1:
                    deck = y1 if deck is None else max(deck, y1)
            if deck is None:
                raise SystemExit(
                    f"view {name!r} is mode 'deck' but no walk deck covers "
                    f"({ex:.1f}, {ez:.1f})")
            ey = deck + eye_h
            # The target is snapped to the deck too, so a level look along the
            # span stays level. Measured against the ground it drifts: the
            # terrain under the far end of a causeway is not the terrain under
            # the near end, and the aim tilts by the difference.
            target_deck = None
            for x0, x1, z0, z1, y0, y1 in decks:
                if x0 <= tx <= x1 and z0 <= tz <= z1:
                    target_deck = y1 if target_deck is None else max(target_deck, y1)
            ty = (target_deck if target_deck is not None else deck) + target_h
        elif mode != "submerged":
            ey = max(ey, REG.SEA_LEVEL + 0.6)
            ey = clear_eye(ex, ey, ez)
        entries.append({
            "id": name,
            "panel": panel if isinstance(panel, int) else None,
            "position": [round(ex, 2), round(ey, 2), round(ez, 2)],
            "target": [round(tx, 2), round(ty, 2), round(tz, 2)],
            "fov": float(fov),
            "golden": mode == "golden",
            "note": (VIEWTABLE.PANELS[panel][1]
                     if isinstance(panel, int) else name.replace("-", " ")),
        })
    payload = {"schemaVersion": "1.0.0", "views": entries}
    path.write_text(json.dumps(payload, indent=2) + chr(10), encoding="utf-8")
    return payload


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
            "id": "westhaven",
            "name": "Westhaven",
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
                         "six-bit field cannot express Westhaven's relief; the "
                         "grid is authoritative for walkability, and the Godot "
                         "loader takes elevation from the rendered walk "
                         "surfaces, not from this file."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
        },
        "navigation": {
            "surfaceNodePrefixes": surface_prefixes,
            "walkableAreas": ["paving", "quays", "pier-decks", "mole-deck",
                              "shore", "salt-turf", "ramp-streets", "stairs"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every built "
                "walkable surface is named Walk_<...>. The client turns both "
                "into the navigation collision layer the grounding ray tests.",
                "Pier decks and the harbour mole are walk surfaces, so a "
                "downward grounding ray under one resolves onto the deck "
                "above; the harbour beneath them is water and is not walkable.",
                "The sea floor is terrain and carries the Terrain_ prefix "
                "everywhere, including below sea level. That is deliberate: the "
                "client casts its grounding ray at every server tile, not only "
                "walkable ones, so a region that is 30% open water still needs "
                "a continuous surface underneath it. Those tiles ground "
                "successfully and are marked unwalkable in collision.bin.",
                "The city's terrace risers are retaining walls and are not "
                "walkable; the ramp streets graded between the bands are the "
                "connections, and every terrace is reachable along them.",
            ],
        },
        "landmarks": build.landmarks,
        "interactives": build.interactives,
        "npcMarkers": build.npc_markers,
        "harvestables": build.harvestables,
        "portals": build.portals,
        # Westhaven's routes are graded into the ground, so a waypoint's height
        # is the terrain's, read back from the terrain that was actually built
        # rather than from the height table that asked for it.
        "roads": [{"id": name,
                   "type": "quay" if name == "quayside" else (
                       "track" if REG.ROAD_SURFACE[name] == TER.PATH else "street"),
                   "widthMetres": round(REG.ROAD_WIDTH[name] * REG.SCALE, 1),
                   "waypoints": [[round(float(p[0]), 1),
                                  round(float(t.height_at(p[0], p[1])), 2),
                                  round(float(p[1]), 1)] for p in points]}
                  for name, points in REG.ROADS.items()],
        "water": {
            "seaLevel": REG.SEA_LEVEL,
            "serverCells": REG.SERVER_CELLS,
            "bodies": [{"id": name, "node": name,
                        "type": "harbour" if "Harbour" in name else "sea"}
                       for name in build.water_meshes],
            # No watercourses. The painting has no river in it: Westhaven's
            # water is all sea, and the only fresh water is in cisterns.
            "streams": [],
            "channels": [
                {"id": "harbour-mouth", "type": "navigable",
                 "note": "the gap between the mole head and the shipyard point"},
                {"id": "west-inlet", "type": "navigable",
                 "note": "the sheltered arm under the harbour gate"},
                {"id": "lamp-sound", "type": "navigable",
                 "note": "the deep water between Gullstone and Lamp Rock"}],
            "harbourFloor": REG.LEVEL["harbour_floor"],
            "seaFloor": REG.LEVEL["sea_floor"],
        },
        "environment": {
            # Tuned to the concept: a clear maritime sky, a high sun with a
            # slight westerly bias so the south-facing city front is lit and
            # its terrace risers throw the shadows that make the staircase
            # read, and enough haze to separate the two lighthouse rocks from
            # the mainland behind them without washing the painting's colour
            # out. Westhaven's palette is warmer than Crownwater's: terracotta
            # and salt-bleached stone over green-blue water, not marble over
            # turquoise.
            "sky": {"type": "gradient", "zenith": [0.17, 0.41, 0.72],
                    "horizon": [0.86, 0.88, 0.84], "curve": 0.20,
                    "groundHorizon": [0.52, 0.56, 0.52],
                    "groundBottom": [0.20, 0.26, 0.28],
                    "sunAngleMax": 16.0, "energy": 1.20},
            # `direction` is the direction the light TRAVELS, not the direction
            # of the sun in the sky: the binder does
            # `sun.look_at_from_position(ZERO, direction)`, and a
            # DirectionalLight3D emits along its local -Z, so a +Y component
            # lights the world from underneath. Crownwater's session found this
            # the hard way and the sign is copied from its corrected value.
            # Warmer and lower than the first pass. The concept is a golden
            # afternoon, not noon: its shadows are long enough to model the
            # terrace risers, its stone is cream rather than grey, and its water
            # keeps its colour to the horizon. The first pass was reasoned from
            # "a clear maritime sky" rather than art-directed against the
            # painting, and came back cooler and flatter than the painting is.
            "sun": {"direction": [-0.48, -0.66, 0.58],
                    "color": [1.22, 1.08, 0.88], "energy": 1.22,
                    "indirectEnergy": 1.18, "angularDiameterDegrees": 1.2},
            "ambient": {"color": [0.50, 0.62, 0.74], "energy": 0.46,
                        "skyContribution": 0.70},
            "saturation": 1.34,
            "fog": {"enabled": True, "color": [0.76, 0.80, 0.78],
                    "density": 0.00030, "heightFalloff": 0.0020},
            "variants": {
                "golden-hour": {
                    "sun": {"direction": [-0.84, -0.24, 0.48],
                            "color": [1.54, 1.06, 0.64], "energy": 1.28},
                    "fog": {"enabled": True, "color": [0.80, 0.68, 0.54],
                            "density": 0.0017},
                },
                "sea-fret": {
                    "sun": {"direction": [-0.30, -0.90, 0.32],
                            "color": [0.92, 0.94, 0.98], "energy": 0.72},
                    "fog": {"enabled": True, "color": [0.74, 0.78, 0.80],
                            "density": 0.0034, "heightFalloff": 0.010},
                },
            },
            "water": {
                # One water body, at sea level across the whole map. The
                # harbour reads shallower than the open sea because it *is*:
                # the basin is dredged to -7.5 m and the sea outside the mole
                # falls to -17, so a depth-driven shader gets the concept's
                # two-tone water for free.
                "shallowColor": [0.20, 0.58, 0.60],
                "deepColor": [0.03, 0.16, 0.30],
                "causticsEnabled": True,
                "note": ("Shallow/deep tint and caustics are presentation "
                         "settings for whoever writes the water shader; the "
                         "GLB ships a flat lit plane."),
            },
            "presentation": {
                "gulls": {"enabled": True, "density": 0.8,
                          "zones": ["harbour", "open-sea", "lamp-rock"]},
                "mist": {"enabled": False},
                "spray": {"enabled": True,
                          "zones": ["mole", "gullstone", "lamp-rock"]},
                "bannerWind": {"enabled": True, "strength": 0.62},
                "ambientAudio": [
                    {"id": "harbour-work", "zone": "waterfront"},
                    {"id": "market-crowd", "zone": "lower-town"},
                    {"id": "bells", "zone": "citadel"},
                    {"id": "surf", "zone": "mole"},
                    {"id": "gulls", "zone": "open-sea"}],
            },
            "zones": [
                {"id": "waterfront", "centre": [60.0, 3.4, 8.0], "radius": 230.0},
                {"id": "lower-town", "centre": [30.0, 9.5, -30.0], "radius": 150.0},
                {"id": "citadel", "centre": [60.0, 41.0, -140.0], "radius": 120.0},
                {"id": "upland", "centre": [250.0, 34.0, -150.0], "radius": 240.0},
                {"id": "mole", "centre": [-40.0, 5.2, 30.0], "radius": 140.0},
                {"id": "gullstone", "centre": [-40.0, 20.0, 105.0], "radius": 110.0},
                {"id": "lamp-rock", "centre": [300.0, 18.0, 120.0], "radius": 110.0},
                {"id": "open-sea", "centre": [110.0, 0.0, 160.0], "radius": 420.0},
            ],
        },
        "minimap": minimap,
        "lodGroups": [
            {"id": "vegetation", "strategy": "authored-detail-tiers",
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
            {"id": "generator", "file": "source/build_westhaven.py",
             "role": "reproducible-build", "seed": SEED},
        ],
        "provenance": {
            "assets": "original to Eloria/Nymara; generated by source/amberwood/*",
            "thirdParty": "none",
            "textures": "procedural (numpy + Pillow), no sampled or traced source",
            "geometry": "procedural (numpy), no imported models",
            "license": "same as the Eloria client repository",
        },
        "productionStatus": "production-geometry-materials-population",
        "requiresServerMap": {
            "tiles": 96,
            "metresPerTile": REG.METRES_PER_TILE,
            "arrivalTile": list(REG.SERVER_ORIGIN),
            "note": ("Westhaven needs a 96x96 server map and, unlike the other "
                     "576 m regions, an arrival datum at (174, 250) rather than "
                     "(174, 174). Both are added by "
                     "eloria-server tools/generate_nymara_maps.py on branch "
                     "feature/westhaven-576m-server-map."),
        },
        "knownLimitations": [
            "Place names are invented. No authoritative written description of "
            "Westhaven was available, so every name in this package - "
            "Gullstone, Lamp Rock, the Mariners' Guild, Gullscar Farm - is a "
            "placeholder chosen to fit the concept art, not lore.",
            "The server ELM cannot express water as blocked. "
            "generate_nymara_maps.py's validator rejects any exterior map "
            "containing a zero height, and zero is what blocked means, so the "
            "server map carries Westhaven's elevation only and collision.bin "
            "remains authoritative for walkability. This is true of every "
            "region, not new here.",
            "collision.bin height bytes saturate at 63, which is 10.4 m. "
            "Westhaven's terraces run to 52 m and its ridge to 88, so every "
            "walkable cell above 10.4 m encodes as 63. The client takes "
            "elevation from the rendered walk surfaces, not from this file, "
            "and verify_runtime exempts saturated cells from its cross-check.",
            "The city's terrace risers are deliberately not walkable. Every "
            "terrace is reachable along the graded ramp streets, but a player "
            "cannot climb a retaining wall, and the 202 grounding "
            "discontinuities verify_runtime reports are those risers, the "
            "sea cliffs and the map's north and east rim.",
            "Gullstone island has no bridge or ferry geometry. Its tiles are "
            "grounded and walkable but form an isolated component reachable "
            "only by boat, which the client does not yet model.",
        ],
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
    sets = HK.register(preview.texture_sets())

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

    moved = nudge_onto_walkable(build, payload, width, height)
    for entry in moved:
        print(f"[nudge] {entry['id']} moved {entry['metres']} m onto a walkable cell")
    if not moved:
        print("[nudge] every spawn and portal already stands on a walkable cell")
    collision_stats["nudgedEntries"] = moved

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

    views = write_camera_views(build, out / "camera-views.json")
    print(f"[views] {len(views['views'])} camera framings written")

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
        lod_sets = HK.register(lod_sets)
        lod_build = build_region(args.seed, lod="far")
        lod_build.terrain_meshes = lod_build.terrain.build_meshes(uv_scale=0.28)
        # The reduced package drops the ground-dressing pass, so it references
        # one material fewer than the main one. Pinning it to the full set
        # embedded a texture nothing pointed at - which is precisely the
        # 2.79 MB mistake the guide records Amberwood making.
        lod_pin = HK.MATERIALS - {"undergrowth"}
        _, lod_stats = export_glb(lod_build, lod_sets, out / "world-lod2.glb",
                                  pin=lod_pin)
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

    # Raw measurements go to performance.json, NOT to performance-summary.md.
    # Amberwood's build writes its JSON dump straight into the .md the guide
    # asks for as documentation, so every build clobbers the doc and the package
    # cannot be reproducible and documented at the same time. Here the
    # machine-written numbers and the human-written summary are two files, and
    # the summary quotes the numbers.
    (out / "performance.json").write_text(
        json.dumps(stats, indent=2) + chr(10), encoding="utf-8")
    return 0 if counts["numErrors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
