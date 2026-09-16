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

The module also holds the authored waypoints a road passes on its way: a door
road's (hub -> waypoint -> ... -> door end) and a seam road's (hub -> waypoint
-> ... -> crossing terminal). Both are routed in legs by ``route_in_legs``, so
a mountain pass climbs the switchback its valley suggests instead of taking the
router's shortest line. Waypoints obey the same rules as a pinned end: dry
ground, out of the water, inside the territory whose hub the road leaves.
"""
from __future__ import annotations
import numpy as np
import landscape as L

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
# own boxes (the banner focus stands at the pen's box edge). The mill-cache
# branch (307) took the new banner line as its nearest station and looped
# west through the pen, the spring and two tents (86 m): pinned to the pen 02
# margin north-east of the windmill it comes through the same pocket; its
# marker stands inside the windmill's box and 4 m inside round tent 06's
# footprint, which no pin avoids.
SERVER_ROAD_ENDS = {
    ('amberwood', 'amberwood', 'amberwood_estate'): (600., 590.),
    ('sunmane_steppe', 'sunmane_steppe', 'sunmane_steppe_secrets'): [(1216., 732.), (1196., 760.), (1232., 734.)],
}
SERVER_ROAD_END_LEG_METRES = 2.   # a pin closer than this to its portal is the road's end itself
# (region, portal id) -> authored waypoints in continent metres: the door road is
# routed hub -> waypoint -> ... -> door end in legs, so a designed climb passes
# its overlook, refuge or shrine instead of taking the router's shortest line.
DOOR_ROAD_WAYPOINTS = {
}
# The same for a retained territory, in its source (library) metres: the plan's
# retained transform (translation and squeeze) carries them where the layout stands.
RETAINED_DOOR_ROAD_WAYPOINTS = {
    # Whitehorn Range (the legacy relief under its retained transform): the climbs
    # the old map's valley suggests, from the gate court at the south seams.
    ('whitehorn_range', 'whitehorn-glacier-temple-door'): [(70., 40.), (88., -58.), (76., -192.)],     # lower camp, bridge watch, temple rest
    ('whitehorn_range', 'whitehorn-mine-adit'): [(176., 18.), (237., -26.), (200., -120.)],           # high overlook, east camp, mine yard
    ('whitehorn_range', 'snowline-cell-door'): [(237., -26.), (251., -102.)],                          # east camp, the east valley
    ('whitehorn_range', 'whitehorn-ice-cave-mouth'): [(-93., -38.)],                                  # the old west pass station
    ('whitehorn_range', 'west-watch-cave-mouth'): [(-93., -38.), (-81., -96.)],                       # west pass station, the west valley
    ('whitehorn_range', 'whitehorn-barrow-door'): [(-93., -38.), (-81., -96.), (-85., -150.)],        # ... and past the watch cave
}
# (region, connection id) -> authored waypoints in continent metres for a seam
# road: the road from that territory's hub to its side of a border crossing is
# routed hub -> waypoint -> ... -> crossing terminal in legs, so a pass climbs
# its authored switchback instead of the router's shortest line. A connection id
# is the crossing's own id, the two region ids sorted and joined by '--' (as in
# 'grey_moors--whitehorn_range'), and each of the two sides of a crossing is
# authored separately under its own region: the mountain side takes the climb
# while the other side stays a straight run to the terminal.
SEAM_ROAD_WAYPOINTS = {
    # The Moors pass: four legs of switchback on the west face of the Whitehorn massif, from the shoulder
    # above the watch cave down to the crossing at its foot, 361 m of road for 107 m of fall (grades 0.11 to
    # 0.46 between waypoints on the plan's own ground).
    ('whitehorn_range', 'grey_moors--whitehorn_range'): [
        (371., 302.), (412., 364.), (349., 281.), (411., 377.), (364., 327.)],
    # The east pass: out of the gate court south-east down the tail, then two hairpins round the east flank
    # onto the Barrens' floor, 377 m for 84 m of descent (grades 0.13 to 0.38). Leg 2 crosses the Hornwater
    # at about (629, 418), where the ravine the river cuts is three metres deep.
    ('whitehorn_range', 'amethyst_barrens--whitehorn_range'): [
        (556., 394.), (614., 406.), (668., 448.), (694., 433.), (692., 377.), (760., 419.), (786., 340.)],
    # The Amberwood crossing: out of the gate court north-east over the 173 m shelf, NORTH of the village
    # strip, down the Hornwater's west scarp beside the east pass's own descent, across the river, down the
    # tail's EAST bank, back over the river at the saddle and west along the tail's southern bench to the
    # crossing's lip.
    #
    # This one is not scenery. The crossing at (531, 436) is 52 m from the gate court and 103 m above the
    # Amberwood roads at (516, 444), and world_layout.corridor_grade reconciles the whole connected road
    # network at 0.318 m per metre along an axis, writing the midpoint of its lower and upper envelopes. A
    # direct seam road put those Amberwood roads 124 m of corridor from the court, so the court's upper
    # envelope was 69.2 + 0.318 x 124 = 108.6 m against its own 172.8 m target and it composed at 126.1 m
    # (design O2). Authored length is what buys the head back.
    #
    # Design O3 bought it with six legs east of the court -- and ran them straight through the village on the
    # south-east slope, which settle_roads then cut to the road's own descending profile: the high overlook
    # 179.8 -> 134.9 m, the ram pit 143.2 -> 99.4, the snowline stones 173.4 -> 139.5, Structure_watch_01
    # 175.7 -> 142.7. Four of its six waypoints stood inside a village footprint. These eight legs buy the
    # same length (336 m of authored line, against O3's 179) on ground that holds nothing: the nearest
    # village footprint is 26.6 m from the line and the nearest graded road cell 17-27 m from each of the
    # four placements, which is outside road_shoulder_field's 24 m band. Replaying corridor_grade over this
    # route before the bake leaves the gate court at the same 154.1 m O3 gave it.
    #
    # Every waypoint is inside Whitehorn on dry ground of 108-175 m; the legs fall at 0.01 to 0.71 on the
    # plan's ground and the steepest 10 m window on the line, 1.56, is the Hornwater's own west scarp at
    # (583, 343), which the east pass descends beside it. The two river crossings are shallow: the northern
    # one is the east pass's own, and the southern one is the saddle at (630, 456) where the ravine is about
    # three metres deep. The crossing station itself did not move -- the ownership raster offers 27 safe
    # stations and every one of them lies on the z 422-436 line at x 397-533 (design O3 section 4).
    #
    # (558, 450) is the last leg's pin and it is not decoration. Without it the router's own A* took the
    # 51 m run from (574, 464) to the crossing terminal in a northward arc through (570, 437), 16 m from
    # Secret_horn_ram_pit's 4.5 m footprint and inside road_shoulder_field's 24 m band, and the first O4
    # bake composed the ram pit at 121.2 m against design O2's 143.2 while the other three village
    # placements came back within 2 m. Pinned, the approach stays south of the saddle and the whole line
    # keeps 33.2 m from that footprint. Measure a candidate against the ROUTED road, not the authored
    # polyline: the straight line here is 27.3 m clear where the route was 16.
    ('whitehorn_range', 'amberwood--whitehorn_range'): [
        (556., 350.), (596., 340.), (628., 384.), (648., 420.), (640., 452.), (604., 464.), (574., 464.),
        (558., 450.)],
}
# The same for a retained territory, in its source (library) metres, carried
# where the layout stands by the plan's retained transform (as the retained door
# road waypoints above). The plan phase authors the two Whitehorn passes here,
# in this frame, since the range keeps its legacy relief under such a transform:
#   ('whitehorn_range', 'grey_moors--whitehorn_range')        the Moors pass,
#       authored as a switchback climb; and
#   ('whitehorn_range', 'amethyst_barrens--whitehorn_range')  the east pass.
RETAINED_SEAM_ROAD_WAYPOINTS = {
}
MINIMUM_DRY_METRES = .8
MAXIMUM_DOOR_DISTANCE_METRES = 12.


def prepare_door_approaches(world, content):
    """Validate and expose the pinned road ends and the authored door and seam waypoints before the roads are routed."""
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
    def waypoints_of(authored, retained):
        """Authored road waypoints in order, from the continent frame and from a retained source frame.

        The key's second field (a portal id for a door road, a connection id
        for a seam road) names the road in every refusal.
        """
        prepared = {}
        for (region, road), points in authored.items():
            if region in world.ids:
                prepared[(region, road)] = [validated(region, f'{road} waypoint {index}', x, z) for index, (x, z) in enumerate(points)]
        for (region, road), points in retained.items():
            if region not in world.ids:
                continue
            transform = getattr(world, 'plan', {}).get('retained_transforms', {}).get(region)
            if transform is None:
                raise ValueError(f"{region}:{road}: source-frame waypoints need the territory's retained transform")
            mapped = L.retained_map_xz(transform, points)
            prepared[(region, road)] = [validated(region, f'{road} waypoint {index}', x, z) for index, (x, z) in enumerate(mapped)]
        return prepared
    waypoints = waypoints_of(DOOR_ROAD_WAYPOINTS, RETAINED_DOOR_ROAD_WAYPOINTS)
    seam_waypoints = waypoints_of(SEAM_ROAD_WAYPOINTS, RETAINED_SEAM_ROAD_WAYPOINTS)
    content.door_road_ends = ends
    content.server_road_ends = server_ends
    content.door_road_waypoints = waypoints
    content.seam_road_waypoints = seam_waypoints
    world.door_approaches = {'roadEnds': {f'{region}:{portal}': point.tolist() for (region, portal), point in ends.items()},
                             'serverRoadEnds': {f'{region}:{source}->{target}': [point.tolist() for point in points] for (region, source, target), points in server_ends.items()},
                             'waypoints': {f'{region}:{portal}': [point.tolist() for point in points] for (region, portal), points in waypoints.items()},
                             'seamWaypoints': {f'{region}:{connection}': [point.tolist() for point in points] for (region, connection), points in seam_waypoints.items()},
                             'policy': 'A door inside a retained pavilion gets its road on the pavilion\'s open side; the retained floor carries the last metres.'}
    return world.door_approaches


def door_road_waypoints(content, region, portal):
    """The authored waypoints a door road passes on its way from the hub, in order (none for most doors)."""
    return list(getattr(content, 'door_road_waypoints', {}).get((region, portal), []))


def seam_road_waypoints(content, region, connection_id):
    """The authored waypoints a seam road passes between the hub and the crossing terminal, in order.

    Empty for every seam but an authored pass, where the road is then routed in
    legs through them: the pass climbs its switchback instead of the router's
    shortest line to the border.
    """
    return list(getattr(content, 'seam_road_waypoints', {}).get((region, connection_id), []))


def route_in_legs(world, legs, region, own=None):
    """One road alignment routed through its authored waypoints: hub -> waypoint -> ... -> end.

    Every leg but the last drops its final station, which is the next leg's
    first, so the joints are not stations twice over. ``own`` (the retained
    solids the road may cross because they hold its start, from
    ``world.solids_at_ends``) applies to the first leg only, as it did when the
    road was one call; the later legs let the router take the solids of their
    own two ends. With two stations and no waypoints this is exactly
    ``world.route(legs[0], legs[1], region=region, own=own)``.
    """
    legs = list(legs)
    parts = []
    for index, (a, b) in enumerate(zip(legs, legs[1:])):
        leg = world.route(a, b, region=region, own=own if index == 0 else None)
        parts.append(leg[:-1] if index < len(legs) - 2 else leg)
    return np.vstack(parts)


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
