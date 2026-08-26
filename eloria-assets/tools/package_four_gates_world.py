#!/usr/bin/env python3
"""Build the loader-ready Four Gates package from the checked-in art source."""
import json
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "maps" / "four-gates-city" / "four-gates-city.glb"
OUTPUT = ROOT / "nymara-packs" / "nymara-client-assets" / "runtime" / "maps" / "four_gates"
SIZE = 1536
UNITS_PER_METER = 2.15
ORIGIN = (384.0, 384.0, 0.0)


def source_xz(cell_x: int, cell_y: int) -> tuple[float, float]:
    world_x = (cell_x + 0.5) * 0.5
    world_y = (cell_y + 0.5) * 0.5
    return ((world_x - ORIGIN[0]) * UNITS_PER_METER,
            (ORIGIN[1] - world_y) * UNITS_PER_METER)


def walkable(x: float, z: float) -> bool:
    # V1 intentionally exposes the complete authored terrain envelope. A later
    # art pass can replace this conservative grid with detailed blockers.
    return True


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, OUTPUT / "world.glb")
    manifest = {
        "format": "eloria-world", "version": 1, "id": "four_gates",
        "display_name": "Four Gates", "scene": "world.glb",
        "collision": "collision.bin", "collision_width": SIZE,
        "collision_height": SIZE,
        "coordinates": {"units_per_meter": UNITS_PER_METER, "up_axis": "Y",
                        "forward_axis": "-Z", "origin": list(ORIGIN)},
        "bounds": {"minimum": [-750.0, -40.0, -820.0],
                   "maximum": [750.0, 195.0, 750.0]},
        "environment": {"ambient_color": [0.58, 0.63, 0.72],
                        "ambient_intensity": 1.0,
                        "sun_direction": [-0.4, -0.8, -0.3],
                        "sun_color": [1.0, 0.95, 0.85], "sun_intensity": 1.0,
                        "fog_enabled": False},
        "player_starts": [{"id": "default", "position": [0.0, 32.0, 464.4],
                           "rotation_degrees": 180.0}],
        "portals": [
            {"id": "south", "position": [0.0, 30.0, 722.2]},
            {"id": "east", "position": [722.2, 30.0, 0.0]},
            {"id": "north", "position": [0.0, 30.0, -722.2]}],
        "harvestables": [], "npc_markers": [], "spawn_markers": [], "regions": []
    }
    (OUTPUT / "world.json").write_text(json.dumps(manifest, indent=2) + "\n")
    payload = bytearray(SIZE * SIZE)
    for cy in range(SIZE):
        row = cy * SIZE
        for cx in range(SIZE):
            x, z = source_xz(cx, cy)
            if walkable(x, z):
                payload[row + cx] = 81
    (OUTPUT / "collision.bin").write_bytes(
        struct.pack("<4sHHII", b"EWCG", 1, 0, SIZE, SIZE) + payload)


if __name__ == "__main__":
    main()
