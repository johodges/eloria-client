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
    # The gate undercroft stair opens east out of the Great Arch's base masonry
    # onto a pocket of level ground; a road routed to the door itself ends inside
    # the masonry, and every earlier publication reached the served tile only
    # over a bridge deck the raised road profile built 14 m above the arch. The
    # pin stands seven metres clear of the arch so the road goes round it.
    ('amberwood', 'gate-undercroft-stair'): (616.5, 589.5),
}
# (region, portal source map, portal target map) -> global XZ metres of dry
# ground where the discovery branch to a server-only portal is routed to; the
# branch then runs straight from there to the portal itself, a deck where the
# ground is water, and approaches from that side of the portal. The Amber Gate
# estate door opens west out of the Great Arch's base onto the stream the arch
# spans, 3 m from the undercroft stair that opens east: too close to tell the
# two apart by distance, so its branch is pinned to the dry court west of the
# stream and reaches the door over the water.
# A map pair may hold several pins (one per entrance): each serves the portal
# within MAXIMUM_DOOR_DISTANCE_METRES of it. The Sunmane camp's furniture is
# one solid at the router's 2 m cells and margins, so a branch routed straight
# to a secret marker threads whatever stands between its nearest road station
# and the marker: the banner-focus branch crossed the round tent for 15 m and
# the windmill, the spring branch (routed from the banner-focus branch's end)
# the windmill, the banner shrine and two standing stones. Pinned to the
# pocket north of the animal pen and to the open ground north of the spring,
# their routed parts cross nothing and the straight runs only the markers'
# own boxes (the banner focus stands at the pen's box edge).
SERVER_ROAD_ENDS = {
    ('amberwood', 'amberwood', 'amberwood_estate'): (600., 590.),
    ('sunmane_steppe', 'sunmane_steppe', 'sunmane_steppe_secrets'): [(1216., 732.), (1196., 760.)],
}
SERVER_ROAD_END_LEG_METRES = 2.   # a pin closer than this to its portal is the road's end itself
MINIMUM_DRY_METRES = .8
MAXIMUM_DOOR_DISTANCE_METRES = 12.


def prepare_door_approaches(world, content):
    """Validate and expose the pinned road ends before door roads are routed."""
    def validated(region, label, x, z):
        if int(world.owner_at(x, z)) != world.ids.index(region):
            raise ValueError(f'{region}:{label}: authored door road end lies outside its territory')
        height = float(world.height_at(x, z))
        if height < MINIMUM_DRY_METRES:
            raise ValueError(f'{region}:{label}: authored door road end is not dry ground ({height:.2f} m)')
        ix = int(round((x - world.x0) / (world.x[1] - world.x[0])))
        iz = int(round((z - world.z0) / (world.z[1] - world.z[0])))
        if world.water['mask'][iz, ix]:
            raise ValueError(f'{region}:{label}: authored door road end stands in water')
        return np.array([x, z], dtype=float)
    ends = {}
    for (region, portal), (x, z) in ROAD_ENDS.items():
        if region in world.ids:
            ends[(region, portal)] = validated(region, portal, x, z)
    server_ends = {}
    for (region, source, target), pins in SERVER_ROAD_ENDS.items():
        if region in world.ids:
            pins = [pins] if not isinstance(pins, list) else pins
            server_ends[(region, source, target)] = [validated(region, f'{source}->{target}', x, z) for x, z in pins]
    content.door_road_ends = ends
    content.server_road_ends = server_ends
    world.door_approaches = {'roadEnds': {f'{region}:{portal}': point.tolist() for (region, portal), point in ends.items()},
                             'serverRoadEnds': {f'{region}:{source}->{target}': [point.tolist() for point in points] for (region, source, target), points in server_ends.items()},
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


def server_road_end(content, region, point, source, target):
    """The pinned dry ground a server-only portal's branch is routed to, or None.

    A map can have several entrances from the same territory; the pin serves
    the portal within its reach and the others keep the default handling.
    """
    pins = getattr(content, 'server_road_ends', {}).get((region, source, target))
    if pins is None:
        return None
    pins = [pins] if isinstance(pins, np.ndarray) else list(pins)
    point = np.asarray(point, dtype=float)
    within = [pin for pin in pins if np.linalg.norm(pin - point) <= MAXIMUM_DOOR_DISTANCE_METRES]
    if not within:
        return None
    return min(within, key=lambda pin: np.linalg.norm(pin - point))


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
