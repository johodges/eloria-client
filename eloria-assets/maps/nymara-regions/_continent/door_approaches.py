"""Authored road ends for doors that a retained structure encloses.

Door roads are routed from each territory's hub straight to the doorway. That
is right for a door in a wall that faces open ground, and wrong for the Shrine
of the Nine Lost in Verdant Stair: its door stands on the terrace of the South
Quay pavilion, whose west side is the pavilion's jade wall and whose only open
side is the north. The routed road arrived from the west, its last two
stations wet under the quay, so the bridge builder raised a nine-metre deck
that ends against the wall, while the served door tile (the terrace's north
edge) is reached from the north across plain ground.

A pin here ends the door road on the open side of such a pavilion; the retained
walking floor carries the last metres to the door and no deck is built. The
pinned end must be dry ground inside the door's own territory.
"""
from __future__ import annotations
import numpy as np

# (region, portal id) -> global XZ metres where the door road ends.
ROAD_ENDS = {
    ('verdant_stair', 'nine-lost-door'): (1206.5, 1175.5),   # north threshold of the South Quay pavilion
}
MINIMUM_DRY_METRES = .8
MAXIMUM_DOOR_DISTANCE_METRES = 12.


def prepare_door_approaches(world, content):
    """Validate and expose the pinned road ends before door roads are routed."""
    ends = {}
    for (region, portal), (x, z) in ROAD_ENDS.items():
        if region not in world.ids:
            continue
        if int(world.owner_at(x, z)) != world.ids.index(region):
            raise ValueError(f'{region}:{portal}: authored door road end lies outside its territory')
        height = float(world.height_at(x, z))
        if height < MINIMUM_DRY_METRES:
            raise ValueError(f'{region}:{portal}: authored door road end is not dry ground ({height:.2f} m)')
        ix = int(round((x - world.x0) / (world.x[1] - world.x[0])))
        iz = int(round((z - world.z0) / (world.z[1] - world.z[0])))
        if world.water['mask'][iz, ix]:
            raise ValueError(f'{region}:{portal}: authored door road end stands in water')
        ends[(region, portal)] = np.array([x, z], dtype=float)
    content.door_road_ends = ends
    world.door_approaches = {'roadEnds': {f'{region}:{portal}': point.tolist() for (region, portal), point in ends.items()},
                             'policy': 'A door inside a retained pavilion gets its road on the pavilion\'s open side; the retained floor carries the last metres.'}
    return world.door_approaches


def door_road_end(content, region, portal, door_point):
    """Where the road to this door ends: the pin if one exists, else the door itself."""
    pinned = getattr(content, 'door_road_ends', {}).get((region, portal))
    if pinned is None:
        return np.asarray(door_point, dtype=float)
    if np.linalg.norm(pinned - np.asarray(door_point, dtype=float)) > MAXIMUM_DOOR_DISTANCE_METRES:
        raise ValueError(f'{region}:{portal}: authored door road end is further than {MAXIMUM_DOOR_DISTANCE_METRES} m from the door')
    return pinned


def door_road_end_near(content, region, point):
    """A server-declared destination beside a pinned door shares the door's road end.

    The server profile names the same shrine door as an instance portal, and
    the discovery branch would otherwise run its own last metres onto the wet
    threshold and seed a deck there.
    """
    point = np.asarray(point, dtype=float)
    for (pinned_region, _), pinned in getattr(content, 'door_road_ends', {}).items():
        if pinned_region == region and np.linalg.norm(pinned - point) <= MAXIMUM_DOOR_DISTANCE_METRES:
            return pinned
    return point
