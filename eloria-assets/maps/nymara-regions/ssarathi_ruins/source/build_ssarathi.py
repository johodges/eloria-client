#!/usr/bin/env python3
"""Build the Ssarathi Ruins runtime map package.

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

import ssaratharch as A  # noqa: F401  (kit pieces reach the build via populate)
import ssarathikit as SK
import populate as POP
import region as REG

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
SEED = 20260829

ASSET_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------
def register_materials(sets: dict) -> dict:
    """Toolkit hook: add this region's materials to a shared texture set.

    `capture_views.py` and any other toolkit consumer call this so an offline
    capture renders in the region's own materials rather than in fallback grey.
    Idempotent, like `ssarathikit.register` itself.
    """
    return SK.register(sets)


def build_region(seed: int = SEED, lod: str | None = None) -> REG.RegionBuild:
    """Build the region. `lod="far"` produces the reduced second package:
    far-tier vegetation only and no ground clutter, for low-end machines and for
    distant streaming."""
    t0 = time.time()
    terrain = REG.build_terrain(seed)
    REG.apply_built_ground(terrain, seed)
    build = REG.RegionBuild(terrain=terrain)

    POP.build_water(build, lod=lod)
    POP.populate_bridges(build, seed)
    POP.populate_causeways(build, seed)
    POP.populate_temple(build, seed)
    POP.populate_courts(build, seed)
    POP.populate_landmarks(build, seed)
    POP.populate_quarters(build, seed)
    POP.populate_ruin_blocks(build, seed)
    POP.populate_vegetation(build, seed, lod=lod)
    if lod is None:
        POP.populate_props(build, seed)
    POP.populate_metadata(build, seed)

    build.terrain_meshes = terrain.build_meshes(uv_scale=0.30)
    # No backdrop. Amberwood needs one because its mountain walls have to stand
    # in front of something. Ssarathi is a closed basin: its own jungle-clad
    # valley walls rise above every sightline out of the bowl, so there is
    # nothing for a backdrop to fill and one would only ever be seen clipping
    # through the rim from the temple summit.
    build.resolve_names()
    _collect_landmarks(build)
    _add_spawns_and_portals(build)
    _add_population_markers(build, seed)
    print(f"[region] built in {time.time() - t0:.1f}s")
    return build


# Display names and types for every placement that declares a landmark id.
# Every one of these names is invented - no authoritative written Ssarathi
# region description exists in the repository. See modeling-assumptions.md.
LANDMARK_INFO: dict[str, tuple[str, str]] = {
    "great-temple": ("Temple of the Coiled Sun", "monument"),
    "channel-bridge": ("The Coil Bridge", "bridge"),
    "sun-vault": ("The Sun Vault", "gate"),
    "sun-stela": ("The Sun Stela", "monument"),
    "root-arch": ("The Strangled Arch", "ruin"),
    "south-water-gate": ("South Water Gate", "gate"),
    "serpent-gate": ("The Serpent Pair", "monument"),
    "lily_court": ("The Lily Court", "court"),
    "ritual_plaza": ("The Ritual Plaza", "court"),
    "west-shrine": ("West Marchstone Shrine", "shrine"),
    "east-shrine": ("East Marchstone Shrine", "shrine"),
    "south-shrine": ("South Marchstone Shrine", "shrine"),
    "north-falls": ("The Greater Fall", "waterfall"),
    "east-falls": ("The Lesser Fall", "waterfall"),
}


def _collect_landmarks(build: REG.RegionBuild) -> None:
    """Build the manifest's landmark list from the placements themselves.

    Derived rather than hand-listed beside each `_add`, so a landmark cannot be
    recorded in the manifest at a position the mesh is not actually at - which
    is exactly the class of defect this region's *placeholder* package shipped,
    where a third of the landmarks named other regions entirely.

    Runs after `resolve_names`, so a node renamed to `Walk_...` is recorded
    under the name the GLB actually uses.
    """
    t = build.terrain
    for placement in build.placements:
        if not placement.landmark:
            continue
        x, y, z = placement.position
        name, kind = LANDMARK_INFO.get(
            placement.landmark,
            (placement.landmark.replace("-", " ").replace("_", " ").title(),
             "structure"))
        build.landmarks.append({
            "id": placement.landmark,
            "name": name,
            "node": placement.node,
            "type": kind,
            "position": [round(float(x), 2), round(float(y), 2), round(float(z), 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "surface": TER.SURFACE_NAMES[int(t.surface_at(x, z))],
            "note": "placeholder name - see modeling-assumptions.md"})
    build.landmarks.sort(key=lambda entry: entry["id"])


def _add_spawns_and_portals(build: REG.RegionBuild) -> None:
    t = build.terrain
    # The default spawn is the harbour islet, not the cathedral plaza. Arriving
    # on the far side of the water is the whole framing of detail-board panel 1:
    # you arrive on a quay with the temple visible up the axis, which is the
    # framing of detail-board panel 1.
    for spawn_id, (x, z), facing in (
            ("default", REG.SPAWN, math.radians(-52.0)),
            ("great-causeway", REG.SPAWN_CAUSEWAY, math.pi),
            ("temple-terrace", REG.SPAWN_TEMPLE, math.pi)):
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
    # follow the client registry; the server remains authoritative for the
    # transition. Ssarathi's are the four outlying platforms at the ends of the
    # street network, where a causeway runs out toward the valley wall.
    for portal_id, name, anchor, destination in (
            ("north-stair", "Verdant Stair Road", "north_terrace",
             "maps/nymara/verdant_stair.elm"),
            ("east-causeway", "Manymouth Delta Causeway", "east_shrine",
             "maps/nymara/manymouth_delta.elm"),
            ("west-causeway", "Grey Moors Track", "west_shrine",
             "maps/nymara/grey_moors.elm"),
            ("south-gate", "Westhaven Road", "south_shrine",
             "maps/nymara/westhaven.elm")):
        x, z = REG.ANCHORS[anchor]
        y = float(t.height_at(x, z))
        build.portals.append({
            "id": portal_id, "name": name, "type": "map-transition",
            "position": [round(x, 2), round(y + 0.1, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "destinationMap": destination, "radius": 3.5,
            "authority": "server"})


def _add_population_markers(build: REG.RegionBuild, seed: int) -> None:
    """Editor/visual markers only - the server owns actual spawning."""
    t = build.terrain
    rng = N.Rng(seed + 777)

    npc_plan = [
        ("ssarathi-gate-warden", "Warden of the Water Gate", "south_gate", 7.0),
        ("ssarathi-causeway-guide", "Causeway Guide", "causeway_mid", 6.0),
        ("ssarathi-vault-keeper", "Keeper of the Sun Vault", "vault_door", 5.0),
        ("ssarathi-temple-hierophant", "Temple Hierophant", "temple_terrace", 7.0),
        ("ssarathi-stela-reader", "Stela Reader", "sun_stela", 5.0),
        ("ssarathi-market-trader", "Basin Trader", "market", 8.0),
        ("ssarathi-dock-poler", "Punt Poler", "east_dock", 5.0),
        ("ssarathi-west-poler", "West Landing Poler", "west_dock", 5.0),
        ("ssarathi-lily-tender", "Lily Court Tender", "lily_court", 7.0),
        ("ssarathi-pool-adept", "Ritual Pool Adept", "ritual_plaza", 8.0),
        ("ssarathi-drowned-scavenger", "Drowned Quarter Scavenger",
         "drowned_quarter", 12.0),
        ("ssarathi-arch-hermit", "Hermit of the Root Arch", "root_arch", 6.0),
        ("ssarathi-arrival-steward", "Arrival Quay Steward", "arrival_quay", 5.0),
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


def export_glb(build: REG.RegionBuild, sets, path: Path) -> tuple[GLTF.GltfBuilder, dict]:
    builder = GLTF.GltfBuilder(
        generator="Eloria Ssarathi Ruins builder (original procedural assets)")
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
    unpinned = sorted(used - SK.MATERIALS)
    if unpinned:
        raise SystemExit(
            "materials used but not in ssarathikit.MATERIALS: "
            + ", ".join(unpinned))
    # The other direction is not an error but it is not free either: every
    # pinned material embeds its textures whether or not a mesh references it.
    # Amberwood's pin carries six such and pays 2.79 MB for them.
    unused = sorted(SK.MATERIALS - used)
    if unused:
        print("[materials] WARNING pinned but unreferenced, costing bytes: "
              + ", ".join(unused))

    # Pinned by name to the materials Ssarathi Ruins actually uses. Without `only=`
    # the package embeds the whole shared library - about ten megabytes of forest
    # and burnt-country textures this region never references - and, worse, its
    # contents would change whenever another region appends to the shared table.
    MAT.register_gltf_materials(builder, sets, only=SK.MATERIALS)

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

    root = GLTF.Node("Ssarathi Ruins")
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

    # A flooded region's walkability threshold is the waterline, not a shore
    # margin: Ssarathi's causeways stand 1.8 m out of the water and its fringe
    # ground is barely above it, so anything above the surface is walkable and
    # anything below it is not.
    walkable = (ground > REG.WATER_LEVEL + 0.20) & (slope < 1.05)
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
        # The deck's real extent, not a symmetric half-extent about its origin.
        # A quay apron sits entirely to one side of its placement point, so
        # mirroring it claimed walkable ground on the water side where there is
        # no deck at all - the ray found the basin floor far below.
        x0, x1 = float(low[0]) * placement.scale, float(high[0]) * placement.scale
        z0, z1 = float(low[2]) * placement.scale, float(high[2]) * placement.scale
        inset_x = (x1 - x0) * 0.03
        inset_z = (z1 - z0) * 0.03
        deck_y = py + float(high[1]) * placement.scale
        # An oriented rectangle, not a disc. Amberwood's decks were roughly
        # square, so a circle inscribed in the bounds covered them; Ssarathi Ruins's
        # causeways are 48 m x 5.4 m, and the inscribed circle covers 2.3 m of
        # a 48 m deck. Everything outside it kept the basin floor's height and
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
        # underside; lift any eye that the terrain put under the basin
        if mode == "deck":
            # Stand on a causeway deck the way the client grounds an actor:
            # snap to the highest walk surface under the eye, then add eye
            # height. A ground-relative height cannot express this - the ground
            # under a causeway is sometimes the channel floor and
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
            ey = max(ey, REG.WATER_LEVEL + 0.6)
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
            "id": "ssarathi_ruins",
            "name": "Ssarathi Ruins",
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
            "seaLevel": REG.WATER_LEVEL,
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
                "note": ("Heights above the encodable range clamp to 63 because the legacy "
                         "six-bit field cannot express Ssarathi Ruins's relief; the "
                         "grid is authoritative for walkability, and the Godot "
                         "loader takes elevation from the rendered walk "
                         "surfaces, not from this file."),
            },
            "walkableCells": collision_stats["walkableCells"],
            "walkableFraction": collision_stats["walkableFraction"],
        },
        "navigation": {
            "surfaceNodePrefixes": surface_prefixes,
            "walkableAreas": ["jade-paving", "moss-stone", "jungle-floor",
                              "causeways", "bridge-decks", "docks", "stairs",
                              "temple-tiers"],
            "agentRadius": 0.55,
            "agentHeight": 1.9,
            "maxSlopeDegrees": 40,
            "navmesh": {"format": "surface-prefix-v1", "polygons": []},
            "notes": [
                "Every terrain sub-mesh is named Terrain_<class>; every built "
                "walkable surface is named Walk_<...>. The client turns both "
                "into the navigation collision layer the grounding ray tests.",
                "Ssarathi's causeways are stone embankments, so they are "
                "terrain, not decks. The only Walk_ geometry in the region is "
                "the channel bridges, the timber docks, the temple stair and "
                "summit, the vault threshold, the stela plinth and the shrine "
                "steps. Those own their server cell: the water beneath a "
                "bridge is not separately walkable.",
                "The basin floor is terrain and carries the Terrain_ prefix "
                "everywhere, including below sea level. That is deliberate: the "
                "client casts its grounding ray at every server tile, not only "
                "walkable ones, so a region that is mostly water still needs a "
                "continuous surface underneath it. Those tiles ground "
                "successfully and are marked unwalkable in collision.bin.",
            ],
        },
        "landmarks": build.landmarks,
        "interactives": build.interactives,
        "npcMarkers": build.npc_markers,
        "harvestables": build.harvestables,
        "portals": build.portals,
        # Ssarathi's routes are stone embankments carrying paved surface,
        # not graded earth roads, so they are typed as causeways. Waypoint
        # heights are sampled from the built terrain rather than assumed,
        # because a route dips to the channel floor where a bridge crosses it
        # and the bridge deck is what a traveller is actually on there.
        "roads": [{"id": name, "type": "causeway",
                   "waypoints": [[round(float(p[0]), 1),
                                  round(max(float(t.height_at(p[0], p[1])),
                                            REG.DECK), 2),
                                  round(float(p[1]), 1)] for p in points]}
                  for name, points in REG.street_routes().items()],
        "water": {
            "seaLevel": REG.WATER_LEVEL,
            "serverCells": REG.SERVER_CELLS,
            "bodies": [{"id": name, "node": name,
                        "type": "basin" if "Basin" in name else "pool"}
                       for name in build.water_meshes],
            # One body of standing water. The three carved watercourses are
            # part of that same surface, not separate bodies - they are deeper
            # cuts in the same basin - so they are declared as channels.
            "streams": [],
            "channels": [{"id": name, "type": "navigable",
                          "floor": REG.CHANNEL_FLOOR,
                          "note": "carved watercourse, bridged where a street crosses"}
                         for name in REG.CHANNELS],
            "bridges": [{"id": span["name"], "street": span["street"],
                         "channel": span["channel"],
                         "deck": round(span["deck"], 2),
                         "centre": [round(span["centre"][0], 1), 0.0,
                                    round(span["centre"][1], 1)]}
                        for span in REG.bridge_spans()],
        },
        "environment": {
            # Tuned to the concept: a hot high sun through humid air over a
            # green basin. Unlike Crownwater's clear lagoon light this carries
            # real fog - the painting's distances go milky and green-blue, and
            # the far side of the basin is visibly hazier than the near.
            "sky": {"type": "gradient", "zenith": [0.24, 0.48, 0.70],
                    "horizon": [0.80, 0.86, 0.80], "curve": 0.20,
                    "groundHorizon": [0.40, 0.50, 0.38],
                    "groundBottom": [0.14, 0.20, 0.14],
                    "sunAngleMax": 18.0, "energy": 0.80},
            # `direction` is the direction the light TRAVELS, not the direction
            # of the sun in the sky: the binder does
            # `sun.look_at_from_position(ZERO, direction)`, and a
            # DirectionalLight3D emits along its local -Z. A +Y component
            # therefore lights the world from underneath. Amberwood's manifest
            # still declares +Y and has never been rendered through this path.
            # Tuned against real client frames, not guessed. At energy 1.12
            # with the sun almost straight down the region rendered dim and
            # blue-grey in Godot while the offline preview looked bright: a
            # near-vertical key gives vertical faces nothing, and the flat
            # default tonemap below was crushing what was left. This is
            # oblique enough to model the masonry and strong enough to carry
            # the basin.
            "sun": {"direction": [-0.38, -0.76, 0.52],
                    "color": [1.20, 1.13, 0.95], "energy": 2.35,
                    "indirectEnergy": 1.35, "angularDiameterDegrees": 1.1},
            # Strong indirect and a green-lifted ambient: a jungle basin's
            # shadows are filled by light bounced off leaves and off the water,
            # and a neutral ambient made the ruins read as grey stone.
            # skyContribution 0.45, not 0.70: the binder blends the declared
            # colour against the sky, and at 0.70 the blue sky drowned the
            # green bounce this region's shadows need.
            "ambient": {"color": [0.54, 0.66, 0.56], "energy": 0.42,
                        "skyContribution": 0.35},
            "saturation": 1.30,
            "fog": {"enabled": True, "color": [0.66, 0.78, 0.70],
                    "density": 0.00011, "heightFalloff": 0.0040,
                    "skyAffect": 0.04, "aerialPerspective": 0.10},
            # Declared explicitly. Without a tonemap block the binder leaves
            # Godot's linear default at exposure 1.0, which is what made the
            # first in-client captures read as an overcast evening. Amberwood,
            # Mirrorhold, Whitehorn, Amethyst and Crownwater all omit it too
            # and none of them has been checked through this path.
            "tonemap": {"mode": "filmic", "exposure": 1.05, "white": 6.0},
            "variants": {
                "golden-hour": {
                    "sun": {"direction": [-0.78, -0.30, 0.55],
                            "color": [1.50, 1.08, 0.68], "energy": 1.70},
                    "ambient": {"color": [0.62, 0.56, 0.46], "energy": 0.90,
                                "skyContribution": 0.40},
                    "fog": {"enabled": True, "color": [0.80, 0.70, 0.52],
                            "density": 0.0018, "aerialPerspective": 0.45},
                    "tonemap": {"mode": "filmic", "exposure": 1.28,
                                "white": 6.0},
                },
            },
            "water": {
                "shallowColor": [0.30, 0.72, 0.66],
                "deepColor": [0.06, 0.26, 0.30],
                "causticsEnabled": True,
                "note": ("Shallow/deep tint and caustics are presentation "
                         "settings for whoever writes the water shader; the "
                         "GLB ships a flat lit plane. Ssarathi's water is "
                         "shallow over most of its area, so the shallow tint "
                         "is what will actually be seen."),
            },
            "presentation": {
                "insects": {"enabled": True, "density": 0.7,
                            "zones": ["basin", "jungle-rim"]},
                "mist": {"enabled": True, "density": 0.35,
                         "zones": ["north-falls", "basin"]},
                "spray": {"enabled": True, "zones": ["north-falls", "east-falls"]},
                "birds": {"enabled": True, "density": 0.4, "zones": ["jungle-rim"]},
                "bannerWind": {"enabled": True, "strength": 0.30},
                "ambientAudio": [
                    {"id": "water-lap", "zone": "basin"},
                    {"id": "jungle-canopy", "zone": "jungle-rim"},
                    {"id": "falls", "zone": "north-falls"},
                    {"id": "market", "zone": "market"}],
                "note": ("Declared, not implemented: no particle systems ship "
                         "in the GLB."),
            },
            "zones": [
                {"id": "temple", "centre": [round(REG.ANCHORS["temple"][0], 1), 16.0,
                                            round(REG.ANCHORS["temple"][1], 1)],
                 "radius": 90.0},
                {"id": "basin", "centre": [90.0, 0.0, -90.0], "radius": 300.0},
                {"id": "jungle-rim", "centre": [90.0, 12.0, -90.0], "radius": 420.0},
                {"id": "market", "centre": [round(REG.ANCHORS["market"][0], 1), 2.0,
                                            round(REG.ANCHORS["market"][1], 1)],
                 "radius": 46.0},
                {"id": "north-falls",
                 "centre": [round(REG.ANCHORS["north_falls"][0], 1), 4.0,
                            round(REG.ANCHORS["north_falls"][1], 1)],
                 "radius": 70.0},
                {"id": "east-falls",
                 "centre": [round(REG.ANCHORS["east_falls"][0], 1), 4.0,
                            round(REG.ANCHORS["east_falls"][1], 1)],
                 "radius": 55.0},
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
             "role": "authoritative-player-scale",
             "note": ("The full ten-panel board. The truncated 786,444-byte "
                      "copy every region package shipped was replaced with the "
                      "intact 1983x793 board supplied for this build.")},
            {"id": "generator", "file": "source/build_ssarathi.py",
             "role": "reproducible-build", "seed": SEED},
        ],
        "provenance": {
            "assets": "original to Eloria/Nymara; generated by _toolkit/ and this region source",
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
    sets = SK.register(preview.texture_sets())

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
        lod_sets = SK.register(lod_sets)
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
