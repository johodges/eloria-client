"""The authored Crownwater region plan.

Coordinates are Godot metres, Y up, north toward -Z. The playable footprint is
the server's 576-cell grid at one metre per tile with the arrival datum at
server (174, 174), which lands on the Godot origin:

    godot_x = server_x - 174        godot_z = 174 - server_y

so the reachable area is x in [-174, 401] and z in [-401, 174]. The terrain is
cut larger than that on every side, and the surplus is drowned or walled so a
player can never walk off the authored world.

Composition follows the aerial concept, which is not a landscape with a lake in
it but a *lagoon with a city in it*: a broad shallow turquoise basin, a single
large crowned island at its centre carrying the domed cathedral complex, a ring
of eight smaller pavilion islets around it, a wider scatter of outer islets, and
stone causeways stitching the whole thing together over open water.

The one structural decision that follows from that reading: **the lagoon floor
is terrain, not a hole.** The client grounds actors by casting a ray down at
every server tile, not only walkable ones, so a region whose middle is water
still needs a continuous surface underneath it. Crownwater's heightfield covers
the entire footprint and simply sits below sea level across most of it. That is
what makes zero grounding misses achievable on a map that is mostly sea.
"""
from __future__ import annotations

import math

import numpy as np

from amberwood import noise as N
from amberwood import terrain as TER

# `Placement` and `RegionBuild` are the toolkit's shared build containers, not
# anything Amberwood-specific, and every region needs them. Re-exported here so
# this module is the whole namespace a Crownwater build script has to import.
# (A toolkit refactor moving them to their own module is in flight in another
# session; `amberwood.region` re-exports them either way, so this import holds.)
from amberwood.region import Placement, RegionBuild  # noqa: F401

# ---------------------------------------------------------------- extents
# Crownwater is authored at 576 m x 576 m, matching Amberwood, so the server map
# is 96x96 ELM tiles (576 height cells) at one metre per tile. The arrival datum
# keeps the same 30%-in-from-the-south-west position Amberwood uses.
SERVER_ORIGIN = (174.0, 174.0)
SERVER_CELLS = 576
METRES_PER_TILE = 1.0

# The composition is written in a 192 m design space and scaled up here, so the
# aerial concept's layout is preserved rather than stretched.
SCALE = 3.0

# Distances between places scale with the region; the places themselves do not.
# A plaza is sized by the buildings around it, a quay by the boats along it.
LOCAL = 1.5

PLAY_MIN_X = -SERVER_ORIGIN[0] * METRES_PER_TILE
PLAY_MAX_X = (SERVER_CELLS - 1 - SERVER_ORIGIN[0]) * METRES_PER_TILE
PLAY_MIN_Z = -(SERVER_CELLS - 1 - SERVER_ORIGIN[1]) * METRES_PER_TILE
PLAY_MAX_Z = SERVER_ORIGIN[1] * METRES_PER_TILE

MARGIN = 30.0
TERRAIN_X0 = PLAY_MIN_X - MARGIN
TERRAIN_Z0 = PLAY_MIN_Z - MARGIN
TERRAIN_SIZE_X = (PLAY_MAX_X - PLAY_MIN_X) + MARGIN * 2.0
TERRAIN_SIZE_Z = (PLAY_MAX_Z - PLAY_MIN_Z) + MARGIN * 2.0

SEA_LEVEL = 0.0
TERRAIN_CELL = 2.0

# Crownwater's built ground is mosaic-paved marble, not Amberwood's cobble. The
# surface-class table is shared, so the region repoints its own entry rather
# than editing the toolkit - the same build-time extension `crownkit.register`
# uses for materials, and for the same reason: three sessions are appending to
# those files right now.
TER.SURFACE_MATERIALS[TER.PAVING] = "crownwater_mosaic"
TER.SURFACE_MATERIALS[TER.SHORE] = "crownwater_sand"

# The lagoon floor datum. Everything starts here and islands are lifted out of
# it, which is the inverse of Amberwood's "land, then cut a sea into it".
LAGOON_FLOOR = -5.0
CHANNEL_FLOOR = -9.5
SHALLOWS = -1.35

# The sunken court's floor. Shallow enough that its tiling and glyph read clearly
# from a boat above it, deep enough that it is unmistakably drowned. At -1.90 it
# was invisible in client capture: even at the lagoon's 0.70 alpha, two metres of
# water washed the mosaic out completely. A metre of clear water is enough to say
# "submerged" and little enough to see through.
SUNKEN_COURT_LEVEL = -1.05

# ------------------------------------------------------------ composition
# The archipelago is centred on the middle of the playable footprint rather than
# on the origin, because the origin is the arrival datum and arriving *inside*
# the cathedral plaza wastes the approach the concept is built around. Placing
# the centre here puts the SW inner-ring islet almost exactly on the origin, so
# a player spawns on the harbour islet with the whole city across the water to
# the north-east - which is the framing of detail-board panel 1.
CENTRE = (38.0, -38.0)

INNER_RADIUS = 54.0
OUTER_RADIUS = 88.0


def _ring(centre, radius, count, phase_degrees=0.0):
    """Evenly spaced points on a ring, in design space."""
    out = []
    for i in range(count):
        angle = math.radians(phase_degrees + 360.0 * i / count)
        out.append((centre[0] + radius * math.cos(angle),
                    centre[1] + radius * math.sin(angle)))
    return out


# Eight pavilion islets. Index 3 (135 degrees) lands on the design origin and is
# the harbour: that is not a coincidence, it is chosen so the arrival datum sits
# on authored ground rather than wherever the ring happened to fall.
_INNER = _ring(CENTRE, INNER_RADIUS, 8)
_OUTER = _ring(CENTRE, OUTER_RADIUS, 8, phase_degrees=22.5)

_INNER_NAMES = ["pavilion_east", "pavilion_southeast", "pavilion_south",
                "harbour_isle", "pavilion_west", "pavilion_northwest",
                "pavilion_north", "pavilion_northeast"]
_OUTER_NAMES = ["outer_east", "outer_southeast", "outer_south", "outer_southwest",
                "outer_west", "outer_northwest", "outer_north", "outer_northeast"]

_DESIGN_ANCHORS: dict[str, tuple[float, float]] = {
    "crown_isle": CENTRE,
    "cathedral": (CENTRE[0], CENTRE[1] - 6.0),
    "crown_plaza": (CENTRE[0], CENTRE[1] + 9.0),
    "crown_quay_south": (CENTRE[0] + 1.0, CENTRE[1] + 27.0),
    "crown_quay_north": (CENTRE[0] - 2.0, CENTRE[1] - 27.0),
    "crown_garden": (CENTRE[0] - 17.0, CENTRE[1] + 4.0),
    "crown_campanile": (CENTRE[0] + 16.0, CENTRE[1] - 12.0),
}
_DESIGN_ANCHORS.update(dict(zip(_INNER_NAMES, _INNER)))
_DESIGN_ANCHORS.update(dict(zip(_OUTER_NAMES, _OUTER)))

# Named places that hang off the ring islets. Each is offset from its islet so
# it reads as a place on an island rather than as the island itself.
_DESIGN_ANCHORS.update({
    # the arrival islet: quay, bollards, moored boats (panels 2, 6 and 10)
    "harbour_quay": (_DESIGN_ANCHORS["harbour_isle"][0] + 9.0,
                     _DESIGN_ANCHORS["harbour_isle"][1] - 7.0),
    "harbour_lamp_walk": (_DESIGN_ANCHORS["harbour_isle"][0] + 2.0,
                          _DESIGN_ANCHORS["harbour_isle"][1] - 11.0),
    "harbour_market": (_DESIGN_ANCHORS["harbour_isle"][0] - 8.0,
                       _DESIGN_ANCHORS["harbour_isle"][1] + 3.0),
    # the garden islet of panel 8: concentric planting beds around a fountain
    "garden_isle": _DESIGN_ANCHORS["pavilion_west"],
    "garden_fountain": (_DESIGN_ANCHORS["pavilion_west"][0],
                        _DESIGN_ANCHORS["pavilion_west"][1]),
    # The sunken court of panel 7, deliberately below the water line. Sited in
    # the shallow gap between the harbour islet and the west pavilion, where the
    # two shelves overlap: it has to be shallow enough to read through the water,
    # and far enough from the harbour that its terrace does not overwrite the
    # quay - which is exactly the bug an earlier placement caused.
    "sunken_court": (CENTRE[0] - 40.0, CENTRE[1] + 12.0),
    "watch_tower": _DESIGN_ANCHORS["outer_northeast"],
    "lighthouse": _DESIGN_ANCHORS["outer_southwest"],
})

ANCHORS: dict[str, tuple[float, float]] = {
    name: (x * SCALE, z * SCALE) for name, (x, z) in _DESIGN_ANCHORS.items()
}

SPAWN = ANCHORS["harbour_isle"]
SPAWN_PLAZA = ANCHORS["crown_plaza"]
SPAWN_GARDEN = ANCHORS["garden_isle"]


def _route(*points) -> np.ndarray:
    return np.asarray([(x * SCALE, z * SCALE) for x, z in points], dtype=np.float64)


def _design(name: str) -> tuple[float, float]:
    return _DESIGN_ANCHORS[name]


# ------------------------------------------------------------- causeways
# Every causeway is a spoke from the crown isle to a pavilion islet, plus a
# partial outer ring. These are the *routes*; the bridge geometry that spans the
# open water between islands is built in populate.py. The terrain only needs to
# know where they land, so it can flatten a landing and mark it as built.
CAUSEWAYS: dict[str, np.ndarray] = {}
CAUSEWAY_ENDS: dict[str, tuple[str, str]] = {}
"""Which two islands each causeway joins.

Kept beside the routes because the population pass needs the *islands*, not just
the polyline: a causeway spans the open water between two island edges, so its
length and its deck level come from the island geometry at each end.
"""


def _causeway(name: str, a: str, b: str) -> None:
    CAUSEWAYS[name] = _route(_design(a), _design(b))
    CAUSEWAY_ENDS[name] = (a, b)


for _name in _INNER_NAMES:
    _causeway(f"spoke_{_name}", "crown_isle", _name)
for _i, _name in enumerate(_INNER_NAMES):
    _next = _INNER_NAMES[(_i + 1) % len(_INNER_NAMES)]
    _causeway(f"ring_{_name}_{_next}", _name, _next)
for _inner_name, _outer_name in (("pavilion_east", "outer_east"),
                                 ("pavilion_southeast", "outer_southeast"),
                                 ("pavilion_south", "outer_south"),
                                 ("pavilion_west", "outer_west"),
                                 ("pavilion_northwest", "outer_northwest"),
                                 ("pavilion_north", "outer_north"),
                                 ("harbour_isle", "outer_southwest"),
                                 ("pavilion_northeast", "outer_northeast")):
    _causeway(f"reach_{_outer_name}", _inner_name, _outer_name)

# The ring of open water between the crown isle and its pavilions. Sized to sit
# outside the crown isle's own radius (30) and inside the pavilion shelves, so
# it separates the centre from the ring without cutting into either.
MOAT_RADIUS = 37.0
MOAT_WIDTH = 8.0


def _ring_route(centre, radius, count) -> np.ndarray:
    """A closed ring as a polyline, in world metres."""
    points = _ring(centre, radius, count)
    points.append(points[0])
    return np.asarray([(x * SCALE, z * SCALE) for x, z in points], dtype=np.float64)


def _approach_route(gap_degrees: float, entry) -> np.ndarray:
    """A navigable channel from open sea into the moat, through a ring gap.

    Aimed at the midpoint between two pavilion islets rather than at an islet,
    so the approach never cuts the ground out from under a pavilion.
    """
    angle = math.radians(gap_degrees)
    direction = (math.cos(angle), math.sin(angle))
    gap = (CENTRE[0] + INNER_RADIUS * direction[0],
           CENTRE[1] + INNER_RADIUS * direction[1])
    mouth = (CENTRE[0] + MOAT_RADIUS * direction[0],
             CENTRE[1] + MOAT_RADIUS * direction[1])
    midway = ((entry[0] + gap[0]) * 0.5, (entry[1] + gap[1]) * 0.5)
    return _route(entry, midway, gap, mouth)


# Clearance from sea level to the underside of a causeway deck. Boats pass under
# these in the concept, so the deck cannot simply skim the water.
CAUSEWAY_CLEARANCE = 3.4


def causeway_deck_level(t, points) -> float:
    """The level a causeway deck runs at, in metres.

    A causeway is flat and level from island to island - it is masonry, not a
    graded road - so a single height describes the whole span. Taken from the
    higher of the two landings so the deck never runs below the ground it meets,
    and floored at a fixed clearance so it always reads as bridging water.
    """
    ends = [float(t.height_at(points[0][0], points[0][1])),
            float(t.height_at(points[-1][0], points[-1][1]))]
    return max(max(ends), SEA_LEVEL + CAUSEWAY_CLEARANCE)


ISLANDS: dict[str, tuple[float, float, float]] = {}
"""name -> (radius, level, shelf_radius, edge) in metres, filled below."""

# name -> (radius, deck level above sea, shelf radius, edge width), all metres.
# The levels are deliberately modest and close together: the concept's drama is
# in its architecture and its water, not in its topography, and a lagoon city on
# tall hills would read as a different painting entirely.
ISLANDS["crown_isle"] = (30.0 * SCALE, 7.6, 46.0 * SCALE, 21.0)
for _name in _INNER_NAMES:
    ISLANDS[_name] = (13.0 * SCALE, 4.4, 22.0 * SCALE, 12.0)
for _name in _OUTER_NAMES:
    ISLANDS[_name] = (9.0 * SCALE, 3.2, 16.0 * SCALE, 9.0)


# Each islet is varied so the ring does not read as eight copies of one disc.
# Resolved once, here, rather than inside `build_terrain`: the population passes
# need the *same* radii and levels the terrain was actually built from, and
# recomputing the jitter in two places is how a pavilion ends up hovering or a
# causeway lands in the water.
ISLAND_GEOM: dict[str, dict] = {}
for _name, (_radius, _level, _shelf, _edge) in ISLANDS.items():
    _j = N.stable_hash(_name) % 1000 / 1000.0
    ISLAND_GEOM[_name] = {
        "centre": ANCHORS[_name],
        "radius": _radius * (0.86 + 0.28 * _j),
        "level": _level * (0.90 + 0.22 * _j),
        "shelf": _shelf * (0.90 + 0.20 * (1.0 - _j)),
        "edge": _edge * (0.85 + 0.35 * _j),
    }


# ---------------------------------------------------------------- terrain
def region_noise(t: TER.Terrain, seed: int, frequency: float = 0.035) -> np.ndarray:
    return N.warped_fbm(t.gx * frequency, t.gz * frequency, warp=0.9, octaves=4,
                        seed=seed)


def _island(t: TER.Terrain, centre: tuple[float, float], radius: float,
            level: float, shelf_radius: float, edge: float, seed: int,
            surface: int = TER.PAVING) -> None:
    """Raise one island out of the lagoon, with a shelving apron around it.

    Islands are **plateaus, not domes.** A dome of the right height has almost no
    usable ground on it: everything but the tip exceeds the walkable slope limit,
    and an archipelago built from domes comes out at 5% walkable. The concept's
    islands are built-up platforms held behind retaining walls at the waterline,
    which is a flat top with a defined edge - so that is what this makes.

    The apron matters as much as the island: it is what turns a platform rising
    out of deep water into something a quay, a beach and a moored boat can sit
    against, and it is what the concept's pale turquoise haloes around every
    islet actually are.
    """
    # the shelf first: a broad shallow apron lifted off the lagoon floor
    t.add_dome(centre, shelf_radius, abs(LAGOON_FLOOR - SHALLOWS), power=1.35,
               noise_seed=seed + 3, noise_amount=0.20)
    # then the island proper, as an absolute flat level with an organic edge
    t.plateau(centre, radius, level, edge=edge, surface=surface,
              seed=seed + 7, irregular=0.26)


def build_terrain(seed: int = 20260828) -> TER.Terrain:
    t = TER.Terrain(TERRAIN_X0, TERRAIN_Z0, TERRAIN_SIZE_X, TERRAIN_SIZE_Z,
                    TERRAIN_CELL)

    # 1. the lagoon floor: a broad shallow basin, not a flat plane
    t.height += LAGOON_FLOOR
    t.base_noise(1.15, 0.0140, seed=seed, octaves=5, warp=1.15)
    t.base_noise(0.42, 0.055, seed=seed + 17, octaves=4)

    # 2. the deep water. The concept is shallow turquoise almost everywhere, with
    #    a darker ring of open water separating the crowned centre from its ring
    #    of pavilions, and two navigable approaches reaching that ring from the
    #    open sea. Routed deliberately *between* the islands: an earlier version
    #    ran a channel straight through the middle and drowned the crown isle.
    t.carve_channel(_ring_route(CENTRE, MOAT_RADIUS, 64),
                    MOAT_WIDTH * SCALE, abs(CHANNEL_FLOOR - LAGOON_FLOOR),
                    bank=2.0, seed=seed + 31)
    for label, gap_degrees, entry in (("southwest", 157.5, (-58.0, 34.0)),
                                      ("southeast", 67.5, (128.0, 46.0))):
        t.carve_channel(_approach_route(gap_degrees, entry),
                        11.0 * SCALE, abs(CHANNEL_FLOOR - LAGOON_FLOOR) * 0.82,
                        bank=2.2, seed=seed + N.stable_hash(label) % 71)

    # 3. the islands
    for name, geom in ISLAND_GEOM.items():
        # Every island's default ground is planted, not paved. Paving whole
        # islands made the aerial read as one continuous white slab: in the
        # concept the pale stone is the *buildings and their plazas*, and the
        # ground between them is green. Paving is therefore applied by the
        # terraces in `apply_built_ground`, where there is actually something
        # built, and nowhere else.
        surface = TER.MEADOW
        _island(t, geom["centre"], geom["radius"], geom["level"],
                geom["shelf"], geom["edge"],
                seed + N.stable_hash(name) % 211, surface=surface)

    # 4. the sunken court of panel 7 sits in its own shallow pan, so the tiled
    #    platform reads through clear water instead of vanishing into the dark.
    t.add_dome(ANCHORS["sunken_court"], 15.0 * SCALE, 2.6, power=1.4)

    # 5. No rim wall. Amberwood closes its world with mountain walls because it
    #    is land; Crownwater's horizon is open water, and a raised rim outside
    #    the playable footprint reads from any elevated camera as a dark slab
    #    floating at the map edge - which is exactly how the first in-client
    #    aerial came back. The world is closed instead by the collision grid:
    #    water is not walkable, and the lagoon floor still grounds every tile,
    #    so nothing reaches a void without a wall being there.

    # a barrier reef just under the surface around the outer edge: it breaks the
    # empty water at the map border without putting walkable land there
    edge = np.minimum.reduce([
        t.gx - t.x0, (t.x0 + t.size_x) - t.gx,
        t.gz - t.z0, (t.z0 + t.size_z) - t.gz])
    reef_band = np.clip(1.0 - np.abs(edge - 58.0) / 40.0, 0.0, 1.0)
    reef_noise = N.fbm(t.gx * 0.035, t.gz * 0.035, octaves=4, seed=seed + 53)
    t.height += reef_band * (reef_noise - 0.42) * 5.2

    t.erode(iterations=10, strength=0.24)
    t.smooth(iterations=2, weight=0.32)
    return t


def apply_built_ground(t: TER.Terrain, seed: int = 20260828) -> None:
    """Quays, plazas and causeway landings - the built part of the surface.

    Deliberately runs after `build_terrain`, so every flattened level is taken
    from the sculpted ground rather than assumed, which is what keeps a plaza
    from hovering when the island noise changes.
    """
    # Causeway landings only. A causeway is a *bridge*, not a road: its deck is
    # built geometry spanning open water, so grading the terrain along its whole
    # length is wrong twice over - it drags the lagoon floor up into a ridge, and
    # on the island end it pulls the quay down toward the water it crosses. An
    # earlier version did exactly that and put the harbour quay 2.5 m under.
    # The terrain gets a short level apron at each end and nothing in between.
    for name, points in CAUSEWAYS.items():
        for end in (points[0], points[-1]):
            level = float(t.height_at(end[0], end[1]))
            if level <= SEA_LEVEL + 0.4:
                continue          # a landing on open water is a pier, not ground
            t.terrace((float(end[0]), float(end[1])), 3.4 * LOCAL, level,
                      surface=TER.PAVING)
        # keep vegetation and props out from under the span without touching height
        for step in np.linspace(0.0, 1.0, 24):
            point = points[0] + (points[-1] - points[0]) * step
            t.mark_blocked_disc((float(point[0]), float(point[1])), 3.2 * LOCAL)

    crown_y = float(t.height_at(*ANCHORS["crown_isle"]))

    # The cathedral precinct is an acropolis, not a building on a lawn. In the
    # concept the palace stands on terraces well above the water; here it sat at
    # island level, 100 m in from a shore that is itself 8 m high, so from any
    # boat you saw a grassy rise with a dome peeping over it - which is not the
    # subject of panel 1. Raising the precinct by 9 m lifts the whole silhouette
    # clear of the island's own horizon. The edge is wide enough (26 m for 9 m
    # of rise, a gradient of 0.35) to stay comfortably walkable.
    t.plateau(ANCHORS["cathedral"], 44.0 * LOCAL, crown_y + 9.0, edge=26.0,
              surface=TER.PAVING, seed=seed + 61, irregular=0.10)
    crown_y = float(t.height_at(*ANCHORS["crown_isle"]))

    t.terrace(ANCHORS["crown_plaza"], 15.0 * LOCAL, crown_y + 0.35,
              surface=TER.PAVING)
    t.rect_terrace(ANCHORS["cathedral"], 13.0 * LOCAL, 11.0 * LOCAL,
                   crown_y + 1.10, 0.0, TER.PAVING)
    t.terrace(ANCHORS["crown_garden"], 9.0 * LOCAL, crown_y - 0.30,
              surface=TER.MEADOW)
    t.terrace(ANCHORS["crown_campanile"], 6.0 * LOCAL, crown_y + 0.60,
              surface=TER.PAVING)

    for quay in ("crown_quay_south", "crown_quay_north"):
        t.rect_terrace(ANCHORS[quay], 11.0 * LOCAL, 4.0 * LOCAL,
                       max(float(t.height_at(*ANCHORS[quay])), 1.15), 0.0,
                       TER.PAVING)

    for name in _INNER_NAMES:
        level = float(t.height_at(*ANCHORS[name]))
        t.terrace(ANCHORS[name], 7.0 * LOCAL, level, surface=TER.PAVING)
    for name in _OUTER_NAMES:
        level = float(t.height_at(*ANCHORS[name]))
        t.terrace(ANCHORS[name], 5.0 * LOCAL, level, surface=TER.PAVING)

    harbour_y = float(t.height_at(*ANCHORS["harbour_isle"]))
    t.rect_terrace(ANCHORS["harbour_quay"], 10.0 * LOCAL, 5.0 * LOCAL,
                   max(harbour_y - 0.55, 1.05), 0.35, TER.PAVING)
    t.rect_terrace(ANCHORS["harbour_lamp_walk"], 12.0 * LOCAL, 3.2 * LOCAL,
                   max(harbour_y - 0.30, 1.20), 0.0, TER.PAVING)
    t.terrace(ANCHORS["harbour_market"], 7.0 * LOCAL, harbour_y, surface=TER.PAVING)

    t.terrace(ANCHORS["garden_fountain"], 8.5 * LOCAL,
              float(t.height_at(*ANCHORS["garden_fountain"])), surface=TER.MEADOW)

    # The sunken court is built ground that happens to be underwater. Its level
    # is authored absolutely rather than read from the terrain, because the whole
    # point of panel 7 is that you can see the tiling through clear water: read
    # from the lagoon floor it lands wherever the noise and the nearest channel
    # happen to put it, which was 8 m down and invisible.
    t.rect_terrace(ANCHORS["sunken_court"], 9.0 * LOCAL, 9.0 * LOCAL,
                   SUNKEN_COURT_LEVEL, 0.0, TER.PAVING)

    t.assign_surface_by_rule(sea_level=SEA_LEVEL)
    t.dither_boundaries(seed=seed + 99, amount=0.5)
