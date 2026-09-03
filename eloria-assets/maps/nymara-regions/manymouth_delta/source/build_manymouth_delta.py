#!/usr/bin/env python3
"""Build the Manymouth Delta runtime map package.

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
from amberwood import noise as N
from amberwood import render as RENDER

from amberwood import terrain as TER

import deltakit as DK
import stiltkit as SK  # noqa: F401  (registers the delta tree species)
import populate as POP
import region as REG

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SEED = 20260829

ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"


def register_materials(sets):
    """Extend the shared texture table with this region's recipes.

    The toolkit's capture and comparison scripts call this if it exists, so an
    offline preview uses the same material table the GLB ships. Without it every
    `manymouth_*` material resolves to index 0 in the preview renderer and the
    captures show bark where the water should be.
    """
    return DK.register(sets)


# --------------------------------------------------------------------------
def walk_surface_at(build: REG.RegionBuild, x: float, z: float) -> float:
    """The height the client's grounding ray would return at (x, z).

    Reproduces `Main._place_actor_on_surface` the same way `build_collision`
    does: the highest walk-deck top whose footprint covers the point, falling
    back to the terrain. Spawns, portals and interactives all have to agree with
    this or `verify_runtime` reports a height mismatch - and it is not something
    a build can guess, because in this region a point is very often covered by
    two or three overlapping decks at different levels (a walkway, the quay it
    joins, and the veranda of the house on the corner).
    """
    best = float(build.terrain.height_at(x, z))
    for placement in build.placements:
        item = build.meshes[placement.mesh]
        walk_bounds = getattr(item, "walk_bounds", lambda: None)()
        if walk_bounds is None:
            if not placement.walk_surface:
                continue
            low, high = item.bounds()
        else:
            low, high = walk_bounds
        px, py, pz = placement.position
        angle = float(placement.rotation_y or 0.0)
        cosine, sine = math.cos(angle), math.sin(angle)
        local_x = cosine * (x - px) - sine * (z - pz)
        local_z = sine * (x - px) + cosine * (z - pz)
        x0, x1 = float(low[0]) * placement.scale, float(high[0]) * placement.scale
        z0, z1 = float(low[2]) * placement.scale, float(high[2]) * placement.scale
        if not (x0 <= local_x <= x1 and z0 <= local_z <= z1):
            continue
        best = max(best, py + float(high[1]) * placement.scale)
    return best


# --------------------------------------------------------------------------
def build_region(seed: int = SEED, lod: str | None = None) -> REG.RegionBuild:
    """Build the region. `lod="far"` produces the reduced second package:
    far-tier vegetation only and no ground clutter, for low-end machines and for
    distant streaming."""
    t0 = time.time()
    terrain = REG.build_terrain(seed)
    REG.apply_built_ground(terrain, seed)
    build = REG.RegionBuild(terrain=terrain)

    POP.build_water(build, lod=lod)
    # The walkway network resolves first and everything else reads its deck
    # levels out of the result. See the note at the top of populate.py.
    network = POP.walkway_network(build, seed)
    POP.populate_arch(build, seed, network)
    POP.populate_cave(build, seed, network)
    POP.populate_temple(build, seed, network)
    POP.populate_stilt_town(build, seed, network)
    POP.populate_villages(build, seed, network)
    POP.populate_deck_study(build, seed, network)
    POP.populate_paddies(build, seed, network)
    POP.populate_mangroves(build, seed, network, lod=lod)
    POP.populate_vegetation(build, seed, network, lod=lod)
    if lod is None:
        POP.populate_props(build, seed, network)
    POP.populate_metadata(build, seed, network)

    build.terrain_meshes = terrain.build_meshes(uv_scale=0.28)
    # No landmass backdrop. Amberwood needs one because its mountain walls have
    # to stand in front of something; the delta's horizon is open water on three
    # sides and its own jungle head on the fourth, and the water plane is
    # already cut far outside the authored terrain to supply the rest.
    build.resolve_names()
    build.network = network
    _add_spawns_and_portals(build, network)
    print(f"[region] built in {time.time() - t0:.1f}s")
    return build


def spawn_point(build: REG.RegionBuild, anchor: str,
                reach: float = 52.0) -> tuple[float, float, float]:
    """A point near `anchor` that is solid ground with nothing decked over it.

    Spawning on a walkway is tempting and wrong. `walk_surface_at` tests a
    deck's bounding rectangle, but `plank_floor` lays real planks with real gaps
    between them and a run ends exactly on its endpoint, so a point the
    rectangle claims is often a point the client's ray falls straight through -
    and the spawn is then declared on a deck the client cannot find. The
    rectangle test is only trustworthy in the negative direction: if no
    rectangle covers a point, no deck triangle does either.

    So this searches outward for a point that is (a) covered by no deck at all,
    (b) dry ground with freeboard, and (c) locally flat, and grounds the spawn
    on the terrain there. Deterministic: a fixed spiral, first good hit wins.
    """
    t = build.terrain
    ax, az = REG.ANCHORS[anchor]
    gradient_z, gradient_x = np.gradient(t.height, t.cell)
    slope_grid = np.hypot(gradient_x, gradient_z)

    def slope_at(x, z):
        cx = int(np.clip((x - t.x0) / t.cell, 0, t.cols - 1))
        cz = int(np.clip((z - t.z0) / t.cell, 0, t.rows - 1))
        return float(slope_grid[cz, cx])

    best = None
    for ring in range(0, 26):
        radius = 2.0 + ring * 2.0
        if radius > reach:
            break
        for step in range(16):
            angle = math.pi * 2.0 * step / 16.0 + ring * 0.19
            x = ax + math.cos(angle) * radius
            z = az + math.sin(angle) * radius
            ground = float(t.height_at(x, z))
            if ground < REG.SEA_LEVEL + 0.55:
                continue
            if slope_at(x, z) > 0.45:
                continue
            if walk_surface_at(build, x, z) > ground + 1e-6:
                continue          # something is decked over it
            neighbours = [float(t.height_at(x + dx, z + dz))
                          for dx, dz in ((1.2, 0), (-1.2, 0), (0, 1.2),
                                         (0, -1.2), (0.85, 0.85), (-0.85, 0.85),
                                         (0.85, -0.85), (-0.85, -0.85))]
            spread = max(neighbours) - min(neighbours)
            if best is None or spread < best[0]:
                best = (spread, x, ground, z)
            if spread < 0.32:
                return x, ground, z
    if best is None:
        ground = float(t.height_at(ax, az))
        return ax, ground, az
    return best[1], best[2], best[3]


def _add_spawns_and_portals(build: REG.RegionBuild, network: dict) -> None:
    t = build.terrain
    levels = network["levels"]
    # The default spawn is the town bar, not the arch: arriving with the ring
    # standing out of the water half a kilometre off is the framing of panel 9,
    # and it is the first thing the region should say.
    for spawn_id, anchor, facing in (
            ("default", "stilt_town", math.radians(38.0)),
            ("arch-stair", "arch_stair", math.radians(-140.0)),
            ("temple-quay", "temple_quay", math.radians(-104.0))):
        x, y, z = spawn_point(build, anchor)
        build.spawns.append({
            "id": spawn_id,
            "position": [round(float(x), 2), round(y + 0.05, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": round(math.degrees(facing), 1),
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True,
            "note": ("grounded on the bar itself, clear of every walkway deck; "
                     "the network is a few metres away"),
        })

    # --- the four doors into the insides map ---------------------------
    # Every door targets the SAME destinationMap and differs only in
    # destinationSpawn, which is the whole point of putting a region's
    # interiors on one map: one load, four arrivals. Each door also gains a
    # region spawn of the same name so the insides map's return portal has
    # somewhere to land - without it a player leaving the Underdeck reappears
    # at the default spawn on the other side of the town.
    #
    # The return spawn is sited by `spawn_point`, not at the door itself: the
    # door is on a deck, and a spawn declared on a deck is a spawn the client's
    # ray may fall straight through between two planks.
    for door_id, name, anchor, facing in (
            ("labyrinth-mouth", "Mouth of the Flooded Labyrinth", "cave_mouth",
             math.radians(20.0)),
            ("underdeck-hatch", "The Underdeck Hatch", "town_quay",
             math.radians(34.0)),
            ("tide-hall-door", "The Tide Hall", "town_hall",
             math.radians(18.0)),
            ("temple-sanctum-door", "The Sanctum Stair", "green_temple",
             math.radians(-104.0)),
            # The fifth door, and the one worth having: the ring standing out
            # of the whirlpool is the top of the Submerged Gate, so going down
            # through it lands under it. Both ends of that transition are
            # geometry that already existed - this only admits that the arch on
            # the surface and the gate below are the same object.
            ("gate-descent", "The Manymouth Arch", "arch_stair",
             math.radians(-140.0))):
        x, y, z = spawn_point(build, anchor)
        build.spawns.append({
            "id": door_id,
            "position": [round(float(x), 2), round(y + 0.05, 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "rotationDegrees": round(math.degrees(facing), 1),
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "grounded": True,
            "note": "return landing for the insides map's exit portal"})
        build.portals.append({
            "id": door_id, "name": name, "type": "map-transition",
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": "manymouth_flooded_labyrinth",
            "destinationSpawn": door_id,
            "radius": 3.5, "authority": "server"})

    # Edge portals to the neighbouring Nymara regions. Destination map ids follow
    # the client registry; the server remains authoritative for the transition.
    # Every land route out of a delta is a boat, so these are landings rather
    # than roads.
    for portal_id, name, anchor, destination in (
            ("north-landing", "Verdant Stair Packet", "north_fishing",
             "maps/nymara/verdant_stair.elm"),
            ("east-landing", "Ssarathi Ruins Packet", "east_watch",
             "maps/nymara/ssarathi_ruins.elm"),
            ("south-landing", "Westhaven Packet", "far_bar",
             "maps/nymara/westhaven.elm"),
            ("west-landing", "Crownwater Packet", "sea_landing",
             "maps/nymara/crownwater.elm")):
        x, z = REG.ANCHORS[anchor]
        y = walk_surface_at(build, x, z)
        build.portals.append({
            "id": portal_id, "name": name, "type": "map-transition",
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": destination, "radius": 3.5,
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
        generator="Eloria Manymouth Delta builder (original procedural assets)")
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
    unpinned = sorted(used - DK.MATERIALS)
    if unpinned:
        raise SystemExit(
            "materials used but not in deltakit.MATERIALS: "
            + ", ".join(unpinned))
    # The other direction is not an error but it is not free either: every
    # pinned material embeds its textures whether or not a mesh references it.
    # Amberwood's pin carries six such and pays 2.79 MB for them.
    unused = sorted(DK.MATERIALS - used)
    if unused:
        print("[materials] WARNING pinned but unreferenced, costing bytes: "
              + ", ".join(unused))

    # Pinned by name to the materials Crownwater actually uses. Without `only=`
    # the package embeds the whole shared library - about ten megabytes of forest
    # and burnt-country textures this region never references - and, worse, its
    # contents would change whenever another region appends to the shared table.
    MAT.register_gltf_materials(builder, sets, only=DK.MATERIALS)

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

    root = GLTF.Node("ManymouthDelta")
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
# Levels an ELM height byte holds: the server masks it with 0x3F, so 1..63.
COLLISION_HEIGHT_LEVELS = 63
# Metres of rise per metre travelled that a walker will not climb. Eternal
# Lands allows two 0.2 m stages across a half-metre tile, which is this.
MAX_WALK_GRADIENT = 1.0


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
    decks = np.zeros_like(walkable)
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
        # square, so a circle inscribed in the bounds covered them; Crownwater's
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
        decks |= footprint
        surface = np.where(footprint, deck_y, surface)
        walkable = np.where(footprint, True, walkable)

    # Steepness has to be part of walkability, not of the height byte. That
    # byte holds 63 steps, and a region with 253 m of relief cannot be encoded
    # finely enough for a two-stage climb limit to mean anything - which is how
    # a mountainside ended up walkable. Measured here on the *composed* surface
    # at the walk grid's own resolution, so a bridge reads as the bridge rather
    # than the gorge under it, unlike the bare-terrain `slope` above.
    rise_z, rise_x = np.gradient(surface, COLLISION_CELL)
    too_steep = np.hypot(rise_x, rise_z) > MAX_WALK_GRADIENT
    # A deck is flat but its rim is a cliff. The package put it there to be
    # walked on, so it keeps its footprint and its own edges do the stopping.
    steep_ground = too_steep & ~decks
    walkable &= ~steep_ground

    # The map's own relief, at the finest step that fits the byte. Clipping to
    # 63 at 0.2 m held 12.4 m and flattened everything above it into one value.
    floor = float(surface[walkable].min()) if walkable.any() else 0.0
    relief = (float(surface[walkable].max()) - floor) if walkable.any() else 0.0
    height_step = max(COLLISION_HEIGHT_STEP,
                      relief / (COLLISION_HEIGHT_LEVELS - 1))
    quantised = np.clip(np.round((surface - floor) / height_step) + 1,
                        1, COLLISION_HEIGHT_LEVELS).astype(np.uint8)
    grid = np.where(walkable, quantised, 0).astype(np.uint8)

    payload = struct.pack("<4sHHII", b"EWCG", 2, 0, width, height) + grid.tobytes()
    # Water cells are not merely blocked: the bed under them is real geometry
    # at a known depth, so a swim or aquatic-form traversal mode can be added
    # without rebuilding the package. Counted and described here rather than
    # encoded, because EWCG v1 has no spare bit and inventing v2 for a flag no
    # client reads yet would be worse. The rule is derivable by any consumer:
    # a zero cell whose terrain sample is below sea level is water, not wall.
    swimmable = (~walkable) & (ground < REG.SEA_LEVEL)

    stats = {
        "width": width, "height": height, "cellMetres": COLLISION_CELL,
        "walkableCells": int(walkable.sum()),
        "swimmableCells": int(swimmable.sum()),
        "swimmableFraction": round(float(swimmable.mean()), 4),
        "meanWaterDepth": round(float((REG.SEA_LEVEL - ground)[swimmable].mean())
                                if swimmable.any() else 0.0, 2),
        "maxWaterDepth": round(float((REG.SEA_LEVEL - ground)[swimmable].max())
                               if swimmable.any() else 0.0, 2),
        "blockedCells": int((~walkable).sum()),
        "walkableFraction": round(float(walkable.mean()), 4),
        "elevatedDecks": elevated,
        "steepCells": int(steep_ground.sum()),
        "reliefMetres": round(relief, 2),
        "heightEncoding": {"origin": round(floor - height_step, 4),
                           "step": round(height_step, 6),
                           "range": [1, COLLISION_HEIGHT_LEVELS],
                           "zeroMeansBlocked": True},
        "rowOrder": "server-tile-y (row 0 is the +Z southern edge)",
        "columnOrder": "server-tile-x (column 0 is the -X western edge)",
    }
    return payload, width, height, stats


# --------------------------------------------------------------------------
## Every Eloria minimap is drawn at this scale. One pixel, one metre.
MINIMAP_PIXELS_PER_METRE = 1.0


def render_minimap(build: REG.RegionBuild, sets, path: Path, size: int = 0) -> dict:
    """Top-down orthographic-ish capture of the finished geometry."""
    import preview
    scene = preview.scene_from_build(build, sets)
    centre_x = (REG.PLAY_MIN_X + REG.PLAY_MAX_X) * 0.5
    centre_z = (REG.PLAY_MIN_Z + REG.PLAY_MAX_Z) * 0.5
    extent = max(REG.PLAY_MAX_X - REG.PLAY_MIN_X, REG.PLAY_MAX_Z - REG.PLAY_MIN_Z)
    if size <= 0:
        size = int(round(extent * MINIMAP_PIXELS_PER_METRE))
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
    # Every Eloria minimap is drawn at one pixel to the metre, so the image's
    # pixel size is the map's own size in metres and no two maps' cartography
    # is drawn at different densities. The old key spellings are written
    # alongside the new ones for one release; at this scale `metresPerPixel`
    # and `pixelsPerMetre` are the same number anyway.
    min_x, min_z = REG.PLAY_MIN_X, REG.PLAY_MIN_Z
    return {
        "image": path.name,
        "imageSize": [size, size],
        "pixelsPerMetre": MINIMAP_PIXELS_PER_METRE,
        "worldMin": [min_x, min_z],
        "worldMax": [min_x + extent, min_z + extent],
        "northAxis": "-Z",
        "orientation": "north-up",
        "projection": "orthographic-top-down",
        "renderedFrom": "final geometry (offline rasteriser)",
        "transform": {
            "pixelX": {"scale": MINIMAP_PIXELS_PER_METRE,
                       "offset": round(-min_x * MINIMAP_PIXELS_PER_METRE, 4)},
            "pixelY": {"scale": MINIMAP_PIXELS_PER_METRE,
                       "offset": round(-min_z * MINIMAP_PIXELS_PER_METRE, 4)},
            "formula": "pixel_x = world_x * scale + offset;"
                       " pixel_y = world_z * scale + offset",
        },
        "note": ("Every Eloria minimap is drawn at one pixel to the metre, so"
                 " the image's pixel size is the map's size in metres."),
        "file": path.name,
        "pixels": size,
        "size": [size, size],
        "metresPerPixel": round(1.0 / MINIMAP_PIXELS_PER_METRE, 6),
        "centre": [min_x + extent * 0.5, min_z + extent * 0.5],
        "northUp": True,
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
                   minimap: dict, path: Path, network: dict) -> dict:
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
            "id": "manymouth_delta",
            "name": "Manymouth Delta",
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
                "note": ("The six-bit height field cannot express the whole "
                         "range from the channel floor to the temple summit, so "
                         "values clamp at 63. The grid is authoritative for "
                         "walkability, and the Godot loader takes elevation "
                         "from the rendered walk surfaces, not from this file."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
            # See traversal-modes.md. Not a second binary and not a format
            # change: a derivable classification of the cells this grid already
            # marks unwalkable, so an aquatic traversal mode has the numbers it
            # needs without this package being rebuilt.
            "swimmable": {
                "rule": ("a cell whose grid value is 0 and whose terrain "
                         "height is below asset.seaLevel is water, not wall"),
                "cells": collision_stats["swimmableCells"],
                "fraction": collision_stats["swimmableFraction"],
                "meanDepthMetres": collision_stats["meanWaterDepth"],
                "maxDepthMetres": collision_stats["maxWaterDepth"],
            },
        },
        "navigation": {
            "surfaceNodePrefixes": surface_prefixes,
            "walkableAreas": ["bars", "sandbars", "walkways", "quays",
                              "landings", "stairs", "temple-stair",
                              "paddy-causeways"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every built "
                "walkable surface is named Walk_<...>. The client turns both "
                "into the navigation collision layer the grounding ray tests.",
                "Walkway decks, quays and landings are walk surfaces, so a "
                "downward grounding ray under one resolves onto the deck "
                "above; the channel beneath them is water and is not walkable. "
                "This region's walkway network IS its road network - there are "
                "no graded roads at all - so a large fraction of the reachable "
                "walkable area is elevated deck rather than ground.",
                "The delta floor is terrain and carries the Terrain_ prefix "
                "everywhere, including below sea level. That is deliberate: the "
                "client casts its grounding ray at every server tile, not only "
                "walkable ones, so a region that is two-thirds water still "
                "needs a continuous surface underneath it. Those tiles ground "
                "successfully and are marked unwalkable in collision.bin.",
                "Water tiles are recorded as swimmable rather than merely "
                "blocked (see collision.swimmable and traversal-modes.md): the "
                "bed height is real everywhere, so a future swim or aquatic "
                "traversal mode has a surface to work against without the "
                "package being rebuilt.",
            ],
        },
        "landmarks": build.landmarks,
        "interactives": build.interactives,
        "npcMarkers": build.npc_markers,
        "harvestables": build.harvestables,
        "portals": build.portals,
        # This region has no roads in the Amberwood sense at all. Its routes
        # are plank walkways on piles over open water, so a waypoint's height
        # comes from the deck, never from the channel floor it crosses.
        "roads": [{"id": f"{a}--{b}", "type": "walkway",
                   "surface": ("bamboo-causeway"
                               if (a, b) in POP.BAMBOO_ROUTES
                               or (b, a) in POP.BAMBOO_ROUTES else "plank"),
                   "waypoints": [
                       [round(float(REG.ANCHORS[a][0]), 1),
                        round(network["levels"].get(a, 0.0), 2),
                        round(float(REG.ANCHORS[a][1]), 1)],
                       [round(float(REG.ANCHORS[b][0]), 1),
                        round(network["levels"].get(b, 0.0), 2),
                        round(float(REG.ANCHORS[b][1]), 1)]]}
                  for a, b in POP.ROUTES],
        "water": {
            "seaLevel": REG.SEA_LEVEL,
            "serverCells": REG.SERVER_CELLS,
            "bodies": [{"id": name, "node": name,
                        "type": "deep-channel" if "Deep" in name else "delta"}
                       for name in build.water_meshes],
            "streams": [],
            # The named distributaries. `deep` ones are dredged to the channel
            # floor and are the routes a boat can actually take across the map.
            "channels": [
                {"id": name, "type": ("navigable" if name in REG.DEEP_ROUTES
                                      else "shallow-braid"),
                 "floor": (REG.CHANNEL_FLOOR if name in REG.DEEP_ROUTES
                           else round(REG.DELTA_FLOOR - 2.5, 2)),
                 "waypoints": [[round(float(p[0]), 1), REG.SEA_LEVEL,
                                round(float(p[1]), 1)]
                               for p in points]}
                for name, points in REG.DISTRIBUTARIES.items()],
            "depths": {
                "barFlat": REG.DELTA_FLOOR,
                "navigableChannel": REG.CHANNEL_FLOOR,
                "openSea": REG.SEA_FLOOR,
                "whirlpool": REG.WHIRL_FLOOR,
            },
        },
        "environment": {
            # Tuned to the concept: a high bright sky, a strong near-vertical
            # sun that drives the turquoise out of shallow water, and very
            # little fog - the painting's distances stay clear and saturated.
            "sky": {"type": "gradient", "zenith": [0.20, 0.46, 0.70],
                    "horizon": [0.86, 0.86, 0.78], "curve": 0.18,
                    "groundHorizon": [0.44, 0.58, 0.52],
                    "groundBottom": [0.14, 0.26, 0.24],
                    "sunAngleMax": 16.0, "energy": 1.14},
            # `direction` is the direction the light TRAVELS, not the direction
            # of the sun in the sky: the binder does
            # `sun.look_at_from_position(ZERO, direction)`, and a
            # DirectionalLight3D emits along its local -Z. A +Y component
            # therefore lights the world from underneath. The first in-client
            # capture of this region came back lit from below and reading as
            # night; Amberwood's manifest still declares +Y and has never been
            # rendered through this path.
            # The aerial is lit late and low from the west-north-west, which
            # is what puts the warm rim on every island and the long glitter
            # across the water. Kept as the default rather than as a variant.
            "sun": {"direction": [0.62, -0.58, 0.53],
                    "color": [1.22, 1.04, 0.82], "energy": 1.12,
                    "indirectEnergy": 1.15, "angularDiameterDegrees": 1.2},
            "ambient": {"color": [0.48, 0.66, 0.68], "energy": 0.56,
                        "skyContribution": 0.75},
            "saturation": 1.34,
            "fog": {"enabled": True, "color": [0.72, 0.80, 0.76],
                    "density": 0.00055, "heightFalloff": 0.0026},
            "variants": {
                "monsoon": {
                    "sun": {"direction": [0.30, -0.86, 0.42],
                            "color": [0.86, 0.90, 0.92], "energy": 0.62},
                    "fog": {"enabled": True, "color": [0.68, 0.74, 0.74],
                            "density": 0.0026},
                },
                "night": {
                    "sun": {"direction": [0.40, -0.72, 0.56],
                            "color": [0.34, 0.46, 0.68], "energy": 0.16},
                    "fog": {"enabled": True, "color": [0.10, 0.18, 0.24],
                            "density": 0.0018},
                },
            },
            "water": {
                "shallowColor": [0.30, 0.80, 0.71],
                "deepColor": [0.03, 0.20, 0.26],
                "causticsEnabled": True,
                "note": ("Shallow/deep tint and caustics are presentation "
                         "settings for whoever writes the water shader; the "
                         "GLB ships a flat lit plane."),
            },
            "presentation": {
                "gulls": {"enabled": True, "density": 0.62,
                          "zones": ["open-delta", "sea-reach"]},
                "mist": {"enabled": True, "density": 0.22,
                         "zones": ["mangrove-reach"]},
                "spray": {"enabled": False},
                "bannerWind": {"enabled": True, "strength": 0.38},
                "ambientAudio": [
                    {"id": "channel-lap", "zone": "open-delta"},
                    {"id": "town-quay", "zone": "stilt-town"},
                    {"id": "insects", "zone": "mangrove-reach"},
                    {"id": "arch-hum", "zone": "the-arch"},
                    {"id": "surf", "zone": "sea-reach"}],
            },
            "zones": [
                {"id": "stilt-town",
                 "centre": [round(REG.ANCHORS["stilt_town"][0], 1), 3.0,
                            round(REG.ANCHORS["stilt_town"][1], 1)],
                 "radius": 96.0},
                {"id": "the-arch",
                 "centre": [round(REG.ANCHORS["great_arch"][0], 1), 2.0,
                            round(REG.ANCHORS["great_arch"][1], 1)],
                 "radius": 78.0},
                {"id": "mangrove-reach",
                 "centre": [round(REG.ANCHORS["mangrove_reach"][0], 1), 1.0,
                            round(REG.ANCHORS["mangrove_reach"][1], 1)],
                 "radius": 120.0},
                {"id": "paddy-country",
                 "centre": [round(REG.ANCHORS["paddy_terraces"][0], 1), 2.0,
                            round(REG.ANCHORS["paddy_terraces"][1], 1)],
                 "radius": 130.0},
                {"id": "temple-rim",
                 "centre": [round(REG.ANCHORS["green_temple"][0], 1), 12.0,
                            round(REG.ANCHORS["green_temple"][1], 1)],
                 "radius": 110.0},
                {"id": "sea-reach",
                 "centre": [round(REG.ANCHORS["sea_landing"][0], 1), 0.0,
                            round(REG.ANCHORS["sea_landing"][1], 1)],
                 "radius": 200.0},
                {"id": "open-delta", "centre": [114.0, 0.0, -114.0],
                 "radius": 420.0},
            ],
            # Traversal modes this region is authored to support but the client
            # does not implement yet. Recorded here rather than in prose alone so
            # whoever builds them has the numbers. See traversal-modes.md.
            "traversal": {
                "walk": {"available": True},
                "swim": {
                    "available": False,
                    "reason": "no client swim state yet",
                    "surfaceLevel": REG.SEA_LEVEL,
                    "authoredFor": True,
                    "note": ("Every water tile has real bed geometry beneath "
                             "it and is flagged swimmable in collision.bin's "
                             "companion mask, so a swim mode needs no rebuild "
                             "of this package."),
                },
                "dive": {
                    "available": False,
                    "authoredFor": True,
                    "maxDepth": REG.WHIRL_FLOOR,
                    "note": ("The whirlpool under the arch, the dredged "
                             "channels and the sunken stelae are modelled below "
                             "the water line and are lit as if seen through "
                             "water."),
                },
            },
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
            {"id": "generator", "file": "source/build_manymouth_delta.py",
             "role": "reproducible-build", "seed": SEED},
        ],
        "provenance": {
            "assets": "original to Eloria/Nymara; generated by _toolkit/amberwood/* plus source/deltakit.py and source/stiltkit.py",
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
    sets = DK.register(preview.texture_sets())

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

    views = write_camera_views(build, out / "camera-views.json")
    print(f"[views] {len(views['views'])} camera framings written")

    manifest = write_manifest(build, stats, collision_stats, minimap,
                              out / "world.json", build.network)
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
        lod_sets = DK.register(lod_sets)
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
