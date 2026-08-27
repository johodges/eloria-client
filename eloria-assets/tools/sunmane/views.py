#!/usr/bin/env python3
"""Derive client camera framings from the exported landmark positions.

Each panel of the concept detail board gets a camera placed relative to the
landmark it depicts, using the client's own isometric rig convention (pitch,
yaw and orbit distance) so every capture is a framing a player can actually
reach with the in-game camera.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import terrain                                          # noqa: E402

PACKAGE = Path(__file__).resolve().parents[2] / "maps" / "nymara-regions" / "sunmane_steppe"

# Explicit camera framings, given as ground-relative eye and aim points so they
# stay correct if the landform is resculpted:
#   id, (eye x, eye z, eye height), (aim x, aim z, aim height), fov, note
PLACED = [
    ("p01-caravan-road", (14.0, 70.0, 4.6), (5.0, 38.0, 3.0), 50.0,
     "caravan road with the encampment on the skyline"),
    ("p03-seasonal-market", (0.0, 20.0, 5.6), (0.0, 1.0, 3.4), 55.0,
     "seasonal market with the great hall behind"),
    ("p05-caravanserai-gate", (-6.0, 40.0, 4.4), (-1.0, 25.5, 3.6), 48.0,
     "fortified gate bay and palisade from the road"),
    ("p07-well-and-pens", (-27.0, 22.0, 4.2), (-33.5, 29.5, 1.6), 48.0,
     "well, trough and horse paddocks"),
    ("p10-market-props", (5.0, 12.5, 2.4), (8.5, 7.6, 1.4), 42.0,
     "player-scale market goods and prop language"),
    ("p02-round-tent-camp", (-25.0, -35.0, 4.0), (-33.5, -44.5, 2.2), 48.0,
     "Orun round-tent camp"),
    ("great-hall", (0.0, 26.0, 12.0), (0.0, -12.0, 7.0), 50.0,
     "the monumental central hall over the crossroads"),
]

# id, target landmark id (or explicit target), pitch, yaw, distance, fov, note
VIEWS = [
    ("aerial-overview", (2.0, 8.0, -4.0), -38.0, 208.0, 148.0, 48.0,
     "matches the aerial overview reference"),
    ("p01-caravan-road", (2.0, 8.6, 40.0), -13.0, 6.0, 34.0, 50.0,
     "caravan road toward the encampment"),
    ("p02-round-tent-camp", "Landmark_orun_round_tent_01", -13.0, 37.0, 14.0, 48.0,
     "round-tent camp"),
    ("p03-seasonal-market", (0.0, 10.5, 3.0), -12.0, 0.0, 26.0, 55.0,
     "seasonal market with the hall behind"),
    ("p04-banner-shrine", "Landmark_orun_banner_shrine_00", -11.0, 37.0, 15.0, 46.0,
     "clan banner shrine"),
    ("p05-caravanserai-gate", "Gate_South", -13.0, 0.0, 27.0, 50.0,
     "fortified gate bay"),
    ("p06-windmill", "Landmark_sunmane_windmill_00", -12.0, 96.0, 26.0, 50.0,
     "windmill over the crop block"),
    ("p07-well-and-pens", "Landmark_sunmane_well_01", -13.0, 118.0, 17.0, 48.0,
     "well and horse paddocks"),
    ("p08-standing-stones", (-44.0, 10.0, -18.0), -10.0, 142.0, 22.0, 46.0,
     "standing stone circle"),
    ("p09-steppe-overlook", (0.0, 9.5, -4.0), -15.0, 212.0, 88.0, 55.0,
     "rider's overlook above the encampment"),
    ("p10-market-props", (8.5, 10.2, 8.0), -14.0, 172.0, 11.0, 42.0,
     "player-scale market goods and prop language"),
    ("great-hall", "Landmark_sunmane_great_hall", -15.0, 178.0, 44.0, 50.0,
     "the monumental central hall"),
    ("gate-north", "Gate_North", -18.0, 180.0, 24.0, 50.0, "north gate approach"),
    ("caravanserai-west", "Landmark_sunmane_caravanserai_00", -19.0, 95.0, 30.0, 52.0,
     "west travel-axis caravanserai"),
    ("coast-southwest", "Landmark_sunmane_landing_00", -18.0, 40.0, 40.0, 55.0,
     "cove landing and rugged coastline"),
    ("mesa-north", (-20.0, 14.0, -66.0), -14.0, 355.0, 46.0, 55.0,
     "flat-topped mesas along the north"),
    ("burial-field", "Landmark_sunmane_burial_mound_00", -19.0, 175.0, 26.0, 50.0,
     "barrow field and archive entrance"),
    ("animal-pens", "Landmark_sunmane_animal_pen_00", -20.0, 220.0, 26.0, 52.0,
     "horse paddocks and grazing ground"),
    ("outpost-ridge", "Landmark_sunmane_outpost_02", -17.0, 230.0, 26.0, 50.0,
     "remote rider outpost"),
    ("gameplay-default", "Landmark_orun_seasonal_market_02", -60.0, 0.0, 26.0, 50.0,
     "the client's default isometric gameplay framing"),
    ("gameplay-zoomed-out", (0.0, 8.0, 0.0), -60.0, 0.0, 90.0, 50.0,
     "maximum client zoom-out over the encampment"),
]

GOLDEN = ["p08-standing-stones", "p09-steppe-overlook", "aerial-overview",
          "p01-caravan-road"]


def camera_position(target, pitch_degrees: float, yaw_degrees: float,
                    distance: float):
    """Mirror the client's isometric rig: orbit `target` at pitch/yaw/distance."""
    pitch = math.radians(pitch_degrees)
    yaw = math.radians(yaw_degrees)
    horizontal = math.cos(pitch) * distance
    return (target[0] + math.sin(yaw) * horizontal,
            target[1] - math.sin(pitch) * distance,
            target[2] + math.cos(yaw) * horizontal)


def resolve(manifest: dict, landform) -> list[dict]:
    positions = {entry["id"]: entry["position"] for entry in manifest["landmarks"]}
    resolved = []
    placed_ids = set()
    for identifier, eye, aim, fov, note in PLACED:
        placed_ids.add(identifier)
        resolved.append({
            "id": identifier,
            "position": [round(eye[0], 2),
                         round(landform.height_at(eye[0], eye[1]) + eye[2], 2),
                         round(eye[1], 2)],
            "target": [round(aim[0], 2),
                       round(landform.height_at(aim[0], aim[1]) + aim[2], 2),
                       round(aim[1], 2)],
            "fov": fov, "framing": "placed", "note": note,
            "golden": identifier in GOLDEN})
    for identifier, target, pitch, yaw, distance, fov, note in VIEWS:
        if identifier in placed_ids:
            continue
        if isinstance(target, str):
            found = positions.get(target)
            if found is None:
                raise KeyError("unknown landmark for view %s: %s" % (identifier, target))
            point = (found[0], found[1] + 2.4, found[2])
        else:
            point = target
        resolved.append({
            "id": identifier, "target": [round(v, 2) for v in point],
            "position": [round(v, 2) for v in camera_position(point, pitch, yaw, distance)],
            "fov": fov, "pitchDegrees": pitch, "yawDegrees": yaw,
            "distance": distance, "note": note,
            "golden": identifier in GOLDEN})
    return resolved


def main() -> int:
    manifest = json.loads((PACKAGE / "world.json").read_text())
    import settlement
    layout = settlement.compose_layout(None)
    landform = terrain.build(pads=layout.pads())
    views = resolve(manifest, landform)
    views.sort(key=lambda entry: entry["id"])
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else PACKAGE / "camera-views.json"
    destination.write_text(json.dumps({"schemaVersion": 1, "views": views}, indent=2) + "\n")
    print("wrote %d views to %s" % (len(views), destination))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
