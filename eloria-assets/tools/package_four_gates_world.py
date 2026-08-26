#!/usr/bin/env python3
"""Build the loader-ready Four Gates package from the checked-in art source."""
import json
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


def collision_height(x: float, z: float) -> int:
    """Return the legacy encoded surface height for a source-space point."""
    # The server start is on the authored southern bridge.  Its visible deck
    # spans x=-22..22, z=360..570 and tops out at source Y=34.  Encoding the
    # previous uniform plateau height placed the actor and camera inside it.
    if -22.0 <= x <= 22.0 and 360.0 <= z <= 570.0:
        return 90  # (34 / UNITS_PER_METER + 2.2) / 0.2 == 90.06
    return 81


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw = SOURCE.read_bytes()
    invalid = b'["BLEND","doubleSided"]'
    replacement = b'"BLEND"' + b' ' * (len(invalid) - len(b'"BLEND"'))
    if raw.count(invalid) != 2:
        raise RuntimeError("unexpected Four Gates alphaMode encoding")
    (OUTPUT / "world.glb").write_bytes(raw.replace(invalid, replacement))
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
        "player_starts": [{"id": "default", "position": [0.0, 34.0, 464.4],
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
                payload[row + cx] = collision_height(x, z)
    (OUTPUT / "collision.bin").write_bytes(
        struct.pack("<4sHHII", b"EWCG", 1, 0, SIZE, SIZE) + payload)


if __name__ == "__main__":
    main()
