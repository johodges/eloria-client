"""Assemble the schema 1.x `world.json` companion manifest.

Field names follow `godot-client/schemas/world-manifest-1.schema.json` and the
conventions the Four Gates package established, so the same `WorldLoader`
consumes this package with no client change.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import terrain

# The client registry maps this region at one metre per tile with the server
# arrival datum (58, 58) at the Godot origin.
METRES_PER_TILE = 1.0
SERVER_ORIGIN = (58.0, 58.0)


def server_to_world(tile_x: float, tile_y: float) -> tuple[float, float]:
    """Mirror `CoordinateAdapter.server_to_godot` for authoring-time placement."""
    return ((tile_x - SERVER_ORIGIN[0]) * METRES_PER_TILE,
            -(tile_y - SERVER_ORIGIN[1]) * METRES_PER_TILE)


def world_to_server(world_x: float, world_z: float) -> tuple[int, int]:
    return (round(world_x / METRES_PER_TILE + SERVER_ORIGIN[0]),
            round(-world_z / METRES_PER_TILE + SERVER_ORIGIN[1]))


def build(builder, landform: terrain.Landform, statistics: dict) -> dict:
    half = terrain.HALF_EXTENT
    lowest = float(landform.height.min())
    highest = float(landform.height.max())
    datum_height = landform.height_at(0.0, 0.0)

    spawn_points = []
    for identifier, tile, facing, note in (
            ("arrival-datum", (58, 58), [0, 0, -1],
             "ceremonial crossroads at the shared market"),
            ("west-caravanserai", (6, 58), [1, 0, 0], "arrival from Amethyst Barrens"),
            ("east-caravanserai", (110, 58), [-1, 0, 0], "departure toward Amberwood"),
            ("north-barrowfield", (58, 100), [0, 0, 1],
             "Ssarathi Royal Archive entrance approach")):
        world_x, world_z = server_to_world(*tile)
        spawn_points.append({
            "id": identifier,
            "node": "Terrain_Chunk_%02d_%02d" % _chunk_of(world_x, world_z),
            "serverTile": list(tile),
            "position": [round(world_x, 3), round(landform.height_at(world_x, world_z), 3),
                         round(world_z, 3)],
            "facing": facing,
            "groundedBy": "navigation-surface-raycast",
            "note": note})

    manifest = {
        "schemaVersion": "1.1.0",
        "assetVersion": "1.0.0",
        "asset": {
            "id": "sunmane_steppe",
            "name": "Sunmane Steppe",
            "glb": "world.glb",
            "units": "meters",
            "coordinateSystem": {"handedness": "right", "upAxis": "Y", "northAxis": "-Z"},
            "origin": [0, 0, 0],
            "bounds": {
                "min": [-half, round(lowest - 1.0, 2), -half],
                "max": [half, round(highest + 1.0, 2), half]},
            "regionSpanMeters": half * 2.0,
            "seaLevel": terrain.SEA_LEVEL,
        },
        "coordinateTransform": {
            "metresPerTile": METRES_PER_TILE,
            "serverOrigin": list(SERVER_ORIGIN),
            "origin": [0.0, 0.0, 0.0],
            # Fallback height only, used if a grounding raycast ever misses.
            # It is set to the arrival plateau so a miss can never drop an actor
            # below the landform.
            "walkingHeight": round(datum_height, 3),
            "invertServerY": True,
            # Server tiles are non-negative, so with the datum at (58, 58) the
            # addressable band is Godot X -58..133 and Z -133..58. The map is
            # wider than that on purpose: everything outside it is coastal
            # scenery and rim highland that a player can see but never stand
            # on, which is exactly what makes it a natural world boundary.
            "addressableWorldBounds": {"min": [-58.0, -133.0],
                                       "max": [133.0, 58.0]},
        },
        "spawnPoints": spawn_points,
        "collision": {"nodeNames": sorted(set(builder.collision_nodes))},
        "navigation": {
            "surfaceNodePrefixes": ["Terrain_"],
            "walkableAreas": [terrain.CLASS_NAMES[c] for c in
                              (terrain.CLASS_CLEARING, terrain.CLASS_STEPPE,
                               terrain.CLASS_ROAD, terrain.CLASS_DRY_GRASS,
                               terrain.CLASS_SAND)],
            "navmesh": {"format": "surface-prefix-v1", "agentRadius": 0.55,
                        "agentHeight": 1.9, "maxSlopeDegrees": 42, "polygons": []},
            "note": ("Every terrain chunk carries the Terrain_ prefix, so the "
                     "navigation-surface layer covers the whole landform "
                     "including the shallow shelf. A grounding raycast can "
                     "therefore never miss and fall back to walkingHeight."),
        },
        "landmarks": builder.landmarks,
        "interactives": builder.interactives,
        "terrain": {
            "cellMeters": terrain.CELL,
            "chunkGrid": [8, 8],
            "classes": {terrain.CLASS_NAMES[k]: list(v)
                        for k, v in terrain.CLASS_TINT.items()},
            "lowestElevation": round(lowest, 2),
            "highestElevation": round(highest, 2),
            "worldEdgeBarrier": "raised ridge ring beyond 88 m plus open sea to the west",
        },
        "materials": {
            "strategy": "shared-tileable-pbr-families-with-world-scale-uvs",
            "channelPacking": {"orm": "R=occlusion,G=roughness,B=metallic"},
            "families": {name: {"uvScaleMeters": scale} for name, scale
                         in sorted(__import__("shapes").UV_SCALE.items())},
            "embedded": True,
        },
        "environment": {
            "profile": "warm-daylight",
            "sky": {
                "topColor": "#2a6ec4", "horizonColor": "#b7c8cf",
                "groundHorizonColor": "#b09a72", "groundBottomColor": "#6b5a3e",
                "curve": 0.15, "sunAngleMax": 11.0, "energy": 1.0},
            "ambient": {"color": "#c9c6b6", "skyContribution": 0.42, "energy": 0.52},
            "sun": {"rotationDegrees": [-48, 132, 0], "color": "#fff0d2",
                    "energy": 1.25, "indirectEnergy": 0.9, "shadows": True},
            "fog": {"enabled": True, "color": "#d6c8ab", "density": 0.0009,
                    "skyAffect": 0.16, "aerialPerspective": 0.06},
            "tonemap": {"mode": "filmic", "exposure": 0.92, "white": 2.6},
            "water": {"seaLevel": terrain.SEA_LEVEL,
                      "shallowColor": "#2f9aa6", "deepColor": "#0d5866",
                      "node": "Water_Sea", "waterholeNode": "Water_Waterholes"},
            "variants": {
                "golden-hour": {
                    "sky": {"topColor": "#2f6ba8", "horizonColor": "#e7bf88",
                            "groundHorizonColor": "#a4834f",
                            "groundBottomColor": "#5b4830",
                            "curve": 0.20, "sunAngleMax": 14.0, "energy": 1.0},
                    "ambient": {"color": "#e6c49a", "skyContribution": 0.40, "energy": 0.66},
                    "sun": {"rotationDegrees": [-13, 152, 0], "color": "#ffcf96",
                            "energy": 2.0, "indirectEnergy": 1.0, "shadows": True},
                    "fog": {"enabled": True, "color": "#e6bd8c", "density": 0.0019,
                            "skyAffect": 0.28, "aerialPerspective": 0.10},
                    "tonemap": {"mode": "filmic", "exposure": 1.12, "white": 2.2}}},
        },
        "lighting": {
            "markers": getattr(builder, "lights", []),
            "note": ("Warm landmark and transition light markers are emitted as "
                     "named empty nodes so a client lighting pass can bind them "
                     "without the package depending on a glTF light extension."),
        },
        "minimap": {
            "image": "minimap.webp",
            "fullMapImage": "full-map.webp",
            "previewImage": "minimap-preview.webp",
            "projection": "orthographic-top-down",
            "renderedFrom": "world.glb",
            "generator": ("godot-client/tests/integration/sunmane_minimap.gd, "
                          "rendered through the client's own WorldLoader"),
            "northAxis": "-Z",
            "imageSize": [1024, 1024],
            "worldMin": [-half, -half],
            "worldMax": [half, half],
            "pixelsPerMetre": round(1024.0 / (half * 2.0), 6),
            # Image +X is world +X and image +Y (downward) is world +Z, so north
            # (-Z) is at the top of the picture.
            "transform": {
                "pixelX": {"scale": round(1024.0 / (half * 2.0), 6),
                           "offset": round(half * 1024.0 / (half * 2.0), 4)},
                "pixelY": {"scale": round(1024.0 / (half * 2.0), 6),
                           "offset": round(half * 1024.0 / (half * 2.0), 4)},
                "formula": ("pixel_x = world_x * scale + offset; "
                            "pixel_y = world_z * scale + offset"),
            },
        },
        **getattr(builder, "population", {}),
        "provenance": {
            "generator": "eloria-assets/tools/sunmane/build.py",
            "conceptArt": {
                "aerial": "references/01-aerial-overview.png",
                "detailBoard": "references/00-concept-detail-board.png"},
            "writtenDescription": [
                "eloria-assets/qa/regions/sunmane-steppe/README.md",
                "eloria-assets/NYMARA_ASSET_MANIFEST.md"],
            "sourceConnections": "../source-elm/regions-connections.json",
            "license": "Original Eloria project work, CC-BY-4.0",
            "thirdPartyAssets": "none",
        },
        "statistics": statistics,
    }
    return manifest


def _chunk_of(world_x: float, world_z: float) -> tuple[int, int]:
    span = terrain.HALF_EXTENT * 2.0 / 8.0
    chunk_x = min(7, max(0, int((world_x + terrain.HALF_EXTENT) / span)))
    chunk_z = min(7, max(0, int((world_z + terrain.HALF_EXTENT) / span)))
    return chunk_x, chunk_z
