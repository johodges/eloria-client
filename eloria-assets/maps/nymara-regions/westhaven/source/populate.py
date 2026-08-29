"""Westhaven's placement passes.

Everything that stands on the terrain: the mole, the working waterfront, the
shipyard, the city, the two lighthouses, the upland, the planting and the props.
The terrain itself is `region.py`; this is what is built on it.

Written largest-to-smallest in the order the guide prescribes, and each pass is
independent of the ones after it, so the region can be built and validated at
any stage. That matters more than it sounds: the grounding contract was proved
on bare terrain, with every one of these returning early, before any of it was
written.

INSTANCING
----------
Kit pieces are built once into a small pool of variants and placed many times.
`RegionBuild.add_mesh` keys by name, so a name reused is a second node onto the
same mesh and costs no unique triangles. A city of three hundred houses drawn
from twelve variants is 12 meshes and 300 nodes, which is the difference
between a 20 MB package and one nobody can load.
"""
from __future__ import annotations

import math

import numpy as np

from amberwood import architecture as A
from amberwood import mesh as M
from amberwood import noise as N
from amberwood import props as P
from amberwood import stonework as SW
from amberwood import terrain as TER
from amberwood import trees as TR

import havenarch as HA
import havenkit as HK
import region as REG

from region import Placement


def _ground(build, x: float, z: float) -> float:
    return float(build.terrain.height_at(x, z))


def _rand(seed: int, key: str) -> float:
    """Deterministic 0..1. `stable_hash`, never the builtin salted `hash`."""
    return N.stable_hash(f"{seed}:{key}") % 10007 / 10007.0


def _place(build, node: str, mesh_name: str, x: float, z: float,
           y: float | None = None, rotation: float = 0.0, scale: float = 1.0,
           collides: bool = True, kind: str = "prop",
           landmark: str | None = None) -> Placement:
    if y is None:
        y = _ground(build, x, z)
    return build.place(Placement(node=node, mesh=mesh_name,
                                 position=(float(x), float(y), float(z)),
                                 rotation_y=float(rotation), scale=float(scale),
                                 collides=collides, kind=kind,
                                 landmark=landmark))


def _landmark(build, ident: str, name: str, kind: str, node: str,
              x: float, z: float, y: float) -> None:
    build.landmarks.append({
        "id": ident, "name": name, "type": kind, "node": node,
        "position": [round(float(x), 2), round(float(y), 2), round(float(z), 2)],
        "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                       int(round(REG.SERVER_ORIGIN[1] - z))]})


# ------------------------------------------------------------------ water
def build_water(build, lod: str | None = None) -> None:
    """One water surface at sea level, clipped to where the terrain is below it.

    Cut far outside the authored terrain so that a camera on the crown terrace,
    52 m up and looking south, sees water running to a horizon rather than the
    edge of a slab.

    ONE body, not two. The first version had a separate, greener, more opaque
    harbour plane inside the mole, because the painting does show the sheltered
    water reading differently from the open sea. Two blended planes two
    centimetres apart z-fight, and the whole basin came back as a checkerboard.
    The distinction belongs to the water shader, not to the geometry: the
    manifest declares `environment.water.shallowColor` and `deepColor`, and the
    depth that drives them is already in the terrain - the basin is dredged to
    -7.5 m and the sea outside falls to -17.
    """
    t = build.terrain
    # 4.5 m cells over a 240 m reach. The plane is clipped per cell, so the
    # cell size is the shoreline's step size; but it is also a flat quad over
    # 1.1 km square, so halving the cell quadruples its triangles. At 3.5 m the
    # sea alone was 203,000 triangles - more than half the region's geometry,
    # for flat water - and the waterline is not visibly better.
    reach = REG.WATER_MARGIN
    cell = 4.5 if lod is None else 9.0
    build.water_meshes["Water_Sea"] = TER.water_plane(
        t, REG.SEA_LEVEL,
        t.x0 - reach, t.z0 - reach,
        t.x0 + t.size_x + reach, t.z0 + t.size_z + reach,
        material=HK.HARBOUR, cell=cell, margin=0.12,
        outside_is_water=True)


# ----------------------------------------------------------------- seawall
def populate_seawall(build, seed: int = 0) -> None:
    """The harbour mole and its bastion - detail-board panel 8.

    The mole is the piece that makes the harbour a harbour, and it is the one
    structure in the region whose deck is a long walk surface over open water.
    Per the runtime contract that deck owns its footprint on the server grid:
    the harbour beneath it is not separately walkable.
    """
    t = build.terrain
    deck_y = REG.LEVEL["mole"]
    floor_y = REG.LEVEL["harbour_floor"]

    points = REG.MOLE
    # Walk the polyline in fixed-length runs so each section is straight and
    # the joints fall on the bends. A single long box across a bend leaves a
    # wedge of harbour showing through the deck.
    total = 0.0
    lengths = [0.0]
    for i in range(len(points) - 1):
        total += float(np.linalg.norm(points[i + 1] - points[i]))
        lengths.append(total)
    run = 26.0
    count = max(int(round(total / run)), 3)
    build.add_mesh("Mole_Section", HA.mole_section(
        total / count + 1.2, deck_y, floor_y, deck_width=7.0, seed=seed))
    for i in range(count):
        s0 = total * i / count
        s1 = total * (i + 1) / count
        a = _polyline_point(points, lengths, s0)
        b = _polyline_point(points, lengths, s1)
        mid = (a + b) * 0.5
        _place(build, f"Mole_Run_{i:02d}", "Mole_Section",
               mid[0], mid[1], y=deck_y, rotation=_align(a, b),
               collides=False, kind="landmark")

    bastion_x, bastion_z = REG.ANCHORS["mole_bastion"]
    build.add_mesh("Mole_Bastion", HA.bastion(radius=8.0, height=7.0,
                                              deck_y=0.0, seed=seed + 11))
    node = _place(build, "Landmark_Mole_Bastion", "Mole_Bastion",
                  bastion_x, bastion_z, y=deck_y, collides=False,
                  kind="landmark").node
    # Recorded at the bastion platform, not at the mole deck it rises from:
    # the platform is the walk surface the grounding ray finds here, and a
    # landmark whose y is 3 m under its own floor reads as buried.
    _landmark(build, "mole-bastion", "The Gullstone Bastion", "fortification",
              node, bastion_x, bastion_z, deck_y + 3.15)

    # A light at the mole head, which is what marks the harbour mouth.
    head_x, head_z = REG.ANCHORS["mole_head"]
    build.add_mesh("Mole_Light", HA.lighthouse(height=11.0, base_radius=2.2,
                                               seed=seed + 17))
    node = _place(build, "Landmark_Mole_Light", "Mole_Light",
                  head_x, head_z, y=deck_y, collides=False, kind="landmark").node
    _landmark(build, "mole-light", "The Mole Light", "lighthouse",
              node, head_x, head_z, deck_y + 11.0)

    build.add_mesh("Bollard", HA.bollard(seed=seed))
    for i in range(14):
        s = total * (i + 0.5) / 14.0
        p = _polyline_point(points, lengths, s)
        offset = 2.4 * (1 if i % 2 else -1)
        _place(build, f"Prop_Mole_Bollard_{i:02d}", "Bollard",
               p[0] + offset, p[1], y=deck_y, collides=False, kind="prop")


def _align(a: np.ndarray, b: np.ndarray) -> float:
    """The rotation_y that points a piece built along +X from `a` toward `b`.

    Both `mesh.rotation_y` and the GLB writer's quaternion rotate (1, 0, 0) to
    (cos t, 0, -sin t), so aligning +X with the direction (dx, dz) needs
    t = atan2(-dz, dx). The obvious-looking `atan2(dx, dz) - pi/2` happens to be
    correct when dz is zero and is wrong by up to pi everywhere else, which is
    why the mole came out as a chain of planks lying across its own line
    instead of a breakwater running along it.
    """
    return math.atan2(-(b[1] - a[1]), b[0] - a[0])


def _polyline_point(points: np.ndarray, lengths: list[float],
                    s: float) -> np.ndarray:
    """Point at arc length `s` along a polyline."""
    for i in range(len(lengths) - 1):
        if s <= lengths[i + 1] or i == len(lengths) - 2:
            span = max(lengths[i + 1] - lengths[i], 1e-9)
            u = (s - lengths[i]) / span
            return points[i] + (points[i + 1] - points[i]) * u
    return points[-1]


# -------------------------------------------------------------- waterfront
def populate_waterfront(build, seed: int = 0) -> None:
    """Quay, warehouses, cranes, piers, moored ships and the fish market.

    Panels 3, 4, 5, 7 and 10 all live along this run. It is the busiest 400 m
    of the region and the one a player arrives in the middle of.
    """
    quay_y = REG.LEVEL["quay"]

    # -- the quay wall itself, along the whole harbour front ---------------
    build.add_mesh("Quay_Wall", HA.quay_wall(24.0, height=4.2, seed=seed))
    front = REG.QUAYSIDE
    total = 0.0
    lengths = [0.0]
    for i in range(len(front) - 1):
        total += float(np.linalg.norm(front[i + 1] - front[i]))
        lengths.append(total)
    sections = max(int(round(total / 24.0)), 4)
    for i in range(sections):
        a = _polyline_point(front, lengths, total * i / sections)
        b = _polyline_point(front, lengths, total * (i + 1) / sections)
        mid = (a + b) * 0.5
        # pushed out to the water side of the graded apron
        _place(build, f"Quay_Wall_{i:02d}", "Quay_Wall",
               mid[0], mid[1] + 9.0, y=quay_y, rotation=_align(a, b),
               collides=False, kind="landmark")

    build.add_mesh("Bollard", HA.bollard(seed=seed))
    for i in range(26):
        p = _polyline_point(front, lengths, total * (i + 0.5) / 26.0)
        _place(build, f"Prop_Quay_Bollard_{i:02d}", "Bollard",
               p[0], p[1] + 7.4, y=quay_y, collides=False, kind="prop")

    # -- warehouses: the gable-to-the-water range behind the quay ----------
    for v in range(4):
        build.add_mesh(f"Warehouse_{v}", HA.warehouse(
            width=7.4 + v * 0.7, depth=10.5 + v * 0.9, storeys=3 + (v % 2),
            seed=seed + 40 + v))
    row_z = REG.cell(0.0, 4.30)[1] * REG.SCALE
    x0 = REG.cell(1.28, 0.0)[0] * REG.SCALE
    x1 = REG.cell(4.90, 0.0)[0] * REG.SCALE
    count = 17
    for i in range(count):
        x = x0 + (x1 - x0) * (i + 0.5) / count
        z = row_z + (_rand(seed, f"wh{i}") - 0.5) * 8.0
        y = _ground(build, x, z)
        if y < REG.SEA_LEVEL + 1.0:
            continue
        # Leave the market its own frontage. The warehouse row and the fish
        # market are both on the lower-town terrace, so without this the row
        # walks straight through the market and panel 7 is two blank gables.
        if abs(x - REG.ANCHORS["fish_market"][0]) < 30.0:
            continue
        variant = int(_rand(seed, f"whv{i}") * 4) % 4
        node = _place(build, f"Landmark_Warehouse_{i:02d}", f"Warehouse_{variant}",
                      x, z, y=y, rotation=(_rand(seed, f"whr{i}") - 0.5) * 0.16,
                      kind="building").node
        if i % 4 == 0:
            _landmark(build, f"warehouse-{i:02d}", "Harbour Warehouse",
                      "warehouse", node, x, z, y)

    # -- the fish market: an arcade with stalls under it (panel 7) ---------
    fx, fz = REG.ANCHORS["fish_market"]
    build.add_mesh("Market_Arcade", HA.arcade_range(bays=8, span=3.6, height=4.8,
                                                    depth=4.4, seed=seed + 61))
    # The arcade backs onto the warehouse row and opens south toward the quay,
    # with its stalls in front of it. Placed 6 m *south* of the anchor it stood
    # between the camera and its own stalls, and panel 7 came back as two blank
    # warehouse gables with a lane between them.
    node = _place(build, "Landmark_Fish_Market", "Market_Arcade",
                  fx, fz - 13.0, y=REG.LEVEL["lower_town"], rotation=math.pi,
                  collides=False, kind="landmark").node
    _landmark(build, "fish-market", "The Fish Market", "market", node,
              fx, fz, REG.LEVEL["lower_town"])
    for v in range(3):
        build.add_mesh(f"Fish_Stall_{v}", HA.fish_stall(seed=seed + 70 + v))
    for i in range(9):
        x = fx + (i % 5 - 2) * 3.4 + (_rand(seed, f"fs{i}") - 0.5) * 0.8
        z = fz + (i // 5) * 3.6 - 8.0
        _place(build, f"Prop_Fish_Stall_{i:02d}", f"Fish_Stall_{i % 3}",
               x, z, y=REG.LEVEL["lower_town"],
               rotation=(_rand(seed, f"fsr{i}") - 0.5) * 0.3,
               collides=False, kind="prop")

    # -- the piers, with a ship alongside one and a crane on the other -----
    pier_len = 34.0
    build.add_mesh("Pier", HA.pier(pier_len, width=5.4, deck_y=0.0,
                                   floor_y=REG.LEVEL["harbour_floor"] - quay_y,
                                   seed=seed + 81))
    build.add_mesh("Harbour_Crane", HA.harbour_crane(height=9.4, reach=6.8,
                                                     seed=seed + 85))
    build.add_mesh("Gantry", HA.gantry(width=5.6, height=6.4, seed=seed + 89))
    build.add_mesh("Ship_Large", HA.ship_hull(length=26.0, beam=6.8,
                                              seed=seed + 91, masts=2))
    build.add_mesh("Ship_Small", HA.ship_hull(length=17.0, beam=5.0,
                                              seed=seed + 93, masts=1))

    for name, anchor in (("A", "cargo_pier"), ("B", "crane_pier")):
        px, pz = REG.ANCHORS[anchor]
        node = _place(build, f"Landmark_Pier_{name}", "Pier",
                      px, pz - 2.0, y=quay_y, collides=False,
                      kind="landmark").node
        _landmark(build, f"pier-{name.lower()}",
                  "Cargo Pier" if name == "A" else "Crane Pier",
                  "pier", node, px, pz, quay_y)
    cx, cz = REG.ANCHORS["cargo_pier"]
    _place(build, "Landmark_Gantry", "Gantry", cx - 4.6, cz + 9.0, y=quay_y,
           rotation=math.pi * 0.5, collides=False, kind="landmark")
    _place(build, "Ship_At_Cargo_Pier", "Ship_Large",
           cx - 10.5, cz + 16.0, y=REG.SEA_LEVEL,
           rotation=math.pi * 0.5 + 0.04, collides=False, kind="landmark")
    kx, kz = REG.ANCHORS["crane_pier"]
    # On the pier's centreline, not beside it: the deck is 5.4 m wide, so a
    # 3.4 m offset put the crane over open water and 10.9 m above the harbour
    # floor the grounding ray found underneath it.
    node = _place(build, "Landmark_Harbour_Crane", "Harbour_Crane",
                  kx, kz + 12.0, y=quay_y, rotation=math.pi,
                  collides=False, kind="landmark").node
    _landmark(build, "harbour-crane", "The Great Crane", "crane", node,
              kx, kz + 12.0, quay_y)
    _place(build, "Ship_At_Crane_Pier", "Ship_Small",
           kx + 9.5, kz + 20.0, y=REG.SEA_LEVEL,
           rotation=math.pi * 0.5 - 0.06, collides=False, kind="landmark")

    # a few more hulls at anchor in the basin, which is what the aerial shows
    for i, (u, v, rot, big) in enumerate((
            (2.05, 4.95, 0.30, False), (3.05, 5.06, 1.10, True),
            (3.95, 5.14, 2.05, False), (4.55, 4.98, 0.62, True),
            (1.52, 4.86, 2.60, False))):
        x, z = REG._design_to_world(REG.cell(u, v))
        _place(build, f"Ship_Anchored_{i:02d}",
               "Ship_Large" if big else "Ship_Small",
               x, z, y=REG.SEA_LEVEL, rotation=rot, collides=False,
               kind="landmark")

    # -- the harbour gate over the west inlet (panel 1) --------------------
    gx, gz = REG.ANCHORS["harbour_gate"]
    build.add_mesh("Harbour_Gate", HA.gate_arch(span=12.0, height=17.5,
                                                depth=5.4, seed=seed + 101))
    node = _place(build, "Landmark_Harbour_Gate", "Harbour_Gate",
                  gx, gz + 6.0, y=REG.SEA_LEVEL, rotation=math.radians(28.0),
                  collides=False, kind="landmark").node
    _landmark(build, "harbour-gate", "The Harbour Gate", "gate", node,
              gx, gz + 6.0, REG.SEA_LEVEL + 3.4)

    # -- the custom house and the chandlery --------------------------------
    build.add_mesh("Custom_House", HA.town_house(width=9.0, depth=8.0,
                                                 storeys=2, seed=seed + 111,
                                                 jetty=False))
    hx, hz = REG.ANCHORS["custom_house"]
    node = _place(build, "Landmark_Custom_House", "Custom_House", hx, hz,
                  rotation=math.pi, kind="building").node
    _landmark(build, "custom-house", "The Custom House", "civic", node,
              hx, hz, _ground(build, hx, hz))


# ---------------------------------------------------------------- shipyard
def populate_shipyard(build, seed: int = 0) -> None:
    """The yard, the stocks and the hull on them - detail-board panel 6."""
    sx, sz = REG.ANCHORS["shipyard"]
    quay_y = REG.LEVEL["quay"]

    build.add_mesh("Ship_On_Stocks", HA.ship_on_stocks(length=21.0, beam=5.8,
                                                       seed=seed + 121))
    node = _place(build, "Landmark_Shipyard_Hull", "Ship_On_Stocks",
                  sx + 4.0, sz + 9.0, y=quay_y - 0.4,
                  rotation=math.radians(-14.0), collides=False,
                  kind="landmark").node
    _landmark(build, "shipyard", "The Westhaven Yard", "shipyard", node,
              sx, sz, quay_y)

    # the mould loft and the saw shed behind the stocks
    build.add_mesh("Yard_Shed", HA.warehouse(width=9.0, depth=13.0, storeys=1,
                                             seed=seed + 125, hoist=False))
    for i, (dx, dz, rot) in enumerate(((-11.0, -7.0, 0.10),
                                       (2.0, -11.0, -0.06))):
        _place(build, f"Landmark_Yard_Shed_{i}", "Yard_Shed",
               sx + dx, sz + dz, rotation=rot, kind="building")

    # timber stacked to season, which is most of what a yard looks like
    build.add_mesh("Timber_Stack", P.log_pile(length=4.4, rows=4, per_row=6,
                                              seed=seed + 129,
                                              material="timber_warm"))
    for i in range(9):
        x = sx - 16.0 + (i % 3) * 5.2 + (_rand(seed, f"ts{i}") - 0.5) * 1.2
        z = sz + 2.0 + (i // 3) * 4.4
        y = _ground(build, x, z)
        if y < REG.SEA_LEVEL + 0.6:
            continue
        _place(build, f"Prop_Timber_Stack_{i:02d}", "Timber_Stack", x, z, y=y,
               rotation=_rand(seed, f"tsr{i}") * 3.1, kind="prop")

    build.add_mesh("Ropewalk_Shed", HA.arcade_range(bays=10, span=3.2,
                                                    height=3.6, depth=3.4,
                                                    seed=seed + 133,
                                                    upper=False))
    rx, rz = REG.ANCHORS["ropewalk"]
    node = _place(build, "Landmark_Ropewalk", "Ropewalk_Shed", rx, rz,
                  rotation=math.pi, collides=False, kind="landmark").node
    _landmark(build, "ropewalk", "The Ropewalk", "workshop", node, rx, rz,
              _ground(build, rx, rz))


# -------------------------------------------------------------------- city
def populate_city(build, seed: int = 0) -> None:
    """The terraced city: houses, retaining walls, gates, arcades, cathedral,
    campanile and the brass dome of panel 9.
    """
    t = build.terrain

    # -- house variants ----------------------------------------------------
    for v in range(12):
        build.add_mesh(f"Town_House_{v}", HA.town_house(
            width=5.2 + (v % 4) * 0.9, depth=6.4 + (v % 3) * 1.3,
            storeys=2 + (v % 3), seed=seed + 200 + v, jetty=v % 4 != 3))

    # Houses are seeded on a jittered grid and rejected where the ground is not
    # suitable: too steep to build on, below the quay, outside the city
    # polygon, or already claimed by a road corridor. Rejection sampling rather
    # than authored positions, because three hundred hand-placed houses is not
    # a thing anyone should write, and the terrain already encodes where a
    # house can stand.
    masks = REG.land_masks(t, seed)
    gradient_z, gradient_x = np.gradient(t.height, t.cell)
    slope_grid = np.hypot(gradient_x, gradient_z)

    placed = 0
    step = 9.0
    u0, u1 = 0.28, 5.45
    v0, v1 = 0.95, 4.58
    nu = int((u1 - u0) * 24.0 * REG.SCALE / step)
    nv = int((v1 - v0) * 24.0 * REG.SCALE / step)
    for iu in range(nu):
        for iv in range(nv):
            u = u0 + (u1 - u0) * (iu + 0.5) / nu
            v = v0 + (v1 - v0) * (iv + 0.5) / nv
            x, z = REG._design_to_world(REG.cell(u, v))
            key = f"h{iu}:{iv}"
            x += (_rand(seed, key + "x") - 0.5) * step * 0.7
            z += (_rand(seed, key + "z") - 0.5) * step * 0.7
            cx = int(np.clip((x - t.x0) / t.cell, 0, t.cols - 1))
            cz = int(np.clip((z - t.z0) / t.cell, 0, t.rows - 1))
            if not masks["city"][cz, cx]:
                continue
            if slope_grid[cz, cx] > 0.55:
                continue          # a terrace riser, not a building plot
            if t.tree_block[cz, cx]:
                continue          # a road corridor
            y = float(t.height[cz, cx])
            if y < REG.LEVEL["quay"] + 1.0:
                continue
            if _rand(seed, key + "k") > 0.86:
                continue          # courtyards and gaps, so it is not a lattice
            variant = int(_rand(seed, key + "v") * 12) % 12
            # Aligned to the contour, not randomly: a hillside town's houses
            # all face downhill, and that alignment is most of what makes the
            # roofscape read as a town rather than as scattered sheds.
            facing = math.atan2(-gradient_x[cz, cx], -gradient_z[cz, cx])
            _place(build, f"House_{iu:02d}_{iv:02d}", f"Town_House_{variant}",
                   x, z, y=y, rotation=facing + (_rand(seed, key + "r") - 0.5) * 0.28,
                   kind="building")
            placed += 1
    build.notes.append(f"city houses placed: {placed}")

    # -- retaining walls along the terrace risers --------------------------
    build.add_mesh("Retaining_Wall", SW.retaining_wall(22.0, 5.2, seed=seed + 301,
                                                       material="rubble_stone"))
    riser_v = (4.02, 3.36, 2.72, 2.04, 1.40)
    for band, v in enumerate(riser_v):
        z = REG.cell(0.0, v)[1] * REG.SCALE
        for i in range(14):
            u = 0.34 + (5.30 - 0.34) * (i + 0.5) / 14.0
            x = REG.cell(u, 0.0)[0] * REG.SCALE
            cx = int(np.clip((x - t.x0) / t.cell, 0, t.cols - 1))
            cz = int(np.clip((z - t.z0) / t.cell, 0, t.rows - 1))
            if not masks["city"][cz, cx] or t.tree_block[cz, cx]:
                continue
            y = float(t.height[cz, cx])
            _place(build, f"Retaining_{band}_{i:02d}", "Retaining_Wall",
                   x, z + 2.0, y=y - 4.4, collides=False, kind="landmark")

    # -- the city gate -----------------------------------------------------
    gx, gz = REG.ANCHORS["city_gate"]
    build.add_mesh("City_Gate", SW.monumental_gate(seed=seed + 311, span=7.4,
                                                   height=16.0,
                                                   stair_width=12.0,
                                                   stair_height=4.0))
    node = _place(build, "Landmark_City_Gate", "City_Gate", gx, gz,
                  rotation=math.pi, collides=False, kind="landmark").node
    _landmark(build, "city-gate", "The Sea Gate", "gate", node, gx, gz,
              _ground(build, gx, gz))

    # -- the great arcade of the middle city -------------------------------
    ax, az = REG.ANCHORS["arcade"]
    build.add_mesh("Great_Arcade", HA.arcade_range(bays=14, span=3.8, height=5.4,
                                                   depth=5.0, seed=seed + 321))
    node = _place(build, "Landmark_Great_Arcade", "Great_Arcade", ax, az,
                  y=REG.LEVEL["upper_town"], rotation=math.pi,
                  collides=False, kind="landmark").node
    _landmark(build, "great-arcade", "The Long Arcade", "civic", node,
              ax, az, REG.LEVEL["upper_town"])

    # -- the cathedral and the campanile -----------------------------------
    cx, cz = REG.ANCHORS["cathedral"]
    build.add_mesh("Cathedral", HA.cathedral(seed=seed + 331, length=36.0,
                                             width=17.0, height=15.5))
    node = _place(build, "Landmark_Cathedral", "Cathedral", cx, cz,
                  y=REG.LEVEL["citadel"], rotation=math.pi * 0.5,
                  collides=False, kind="landmark").node
    _landmark(build, "cathedral", "The Haven Church", "temple", node,
              cx, cz, REG.LEVEL["citadel"])

    mx, mz = REG.ANCHORS["campanile"]
    build.add_mesh("Campanile", HA.campanile(height=36.0, width=5.4,
                                             seed=seed + 341))
    node = _place(build, "Landmark_Campanile", "Campanile", mx, mz,
                  y=REG.LEVEL["citadel"], collides=False, kind="landmark").node
    _landmark(build, "campanile", "The Bell Tower", "tower", node, mx, mz,
              REG.LEVEL["citadel"])

    # -- the brass dome and its terrace (panel 9) --------------------------
    dx, dz = REG.ANCHORS["brass_dome"]
    build.add_mesh("Domed_Hall", HA.domed_hall(radius=7.2, drum_height=8.4,
                                               seed=seed + 351))
    node = _place(build, "Landmark_Domed_Hall", "Domed_Hall", dx, dz,
                  y=REG.LEVEL["crown"], collides=False, kind="landmark").node
    _landmark(build, "brass-dome", "The Astronomers' Hall", "civic", node,
              dx, dz, REG.LEVEL["crown"])

    # -- the high spire and the guild hall ---------------------------------
    hx, hz = REG.ANCHORS["high_spire"]
    build.add_mesh("High_Spire", A.watchtower(height=30.0, seed=seed + 361,
                                              radius=2.6))
    node = _place(build, "Landmark_High_Spire", "High_Spire", hx, hz,
                  y=REG.LEVEL["upper_town"], kind="landmark").node
    _landmark(build, "high-spire", "The Watch Spire", "tower", node, hx, hz,
              REG.LEVEL["upper_town"])

    gx, gz = REG.ANCHORS["guild_hall"]
    build.add_mesh("Guild_Hall", A.manor(seed=seed + 371, width=17.0, depth=12.0))
    node = _place(build, "Landmark_Guild_Hall", "Guild_Hall", gx, gz,
                  y=REG.LEVEL["lower_town"], rotation=math.pi,
                  kind="building").node
    _landmark(build, "guild-hall", "The Mariners' Guild", "civic", node,
              gx, gz, REG.LEVEL["lower_town"])

    # -- street furniture: lamps along the ramp streets, cisterns in squares
    build.add_mesh("Lamp_Post", SW.lamp_post(height=2.8))
    build.add_mesh("Cistern_Head", HA.cistern_head(seed=seed + 381))
    for name in ("market_climb", "gate_climb", "arcade_walk", "crown_climb",
                 "quayside"):
        points = REG.ROADS[name]
        total = 0.0
        lengths = [0.0]
        for i in range(len(points) - 1):
            total += float(np.linalg.norm(points[i + 1] - points[i]))
            lengths.append(total)
        n = max(int(total / 17.0), 2)
        for i in range(n):
            p = _polyline_point(points, lengths, total * (i + 0.5) / n)
            side = 1 if i % 2 else -1
            x = p[0] + side * REG.ROAD_WIDTH[name] * REG.SCALE * 0.42
            z = p[1] + side * 0.6
            _place(build, f"Prop_Lamp_{name}_{i:02d}", "Lamp_Post", x, z,
                   collides=False, kind="prop")
    for name in ("lower_square", "mid_street", "crown_terrace"):
        x, z = REG.ANCHORS[name]
        _place(build, f"Prop_Cistern_{name}", "Cistern_Head", x + 4.0, z + 3.0,
               kind="prop")


# ------------------------------------------------------------- lighthouses
def populate_lighthouses(build, seed: int = 0) -> None:
    """The great lighthouse on Lamp Rock and the Gullstone watch - panel 2."""
    lx, lz = REG.ANCHORS["lighthouse"]
    ly = max(_ground(build, lx, lz), 12.0)
    build.add_mesh("Great_Lighthouse", HA.lighthouse(height=28.0,
                                                     base_radius=4.6,
                                                     seed=seed + 401))
    node = _place(build, "Landmark_Great_Lighthouse", "Great_Lighthouse",
                  lx, lz, y=ly, collides=False, kind="landmark").node
    _landmark(build, "great-lighthouse", "The Lamp Rock Light", "lighthouse",
              node, lx, lz, ly + 28.0)

    wx, wz = REG.ANCHORS["gullstone_watch"]
    build.add_mesh("Gullstone_Watch", A.watchtower(height=17.0, seed=seed + 411,
                                                   radius=2.4))
    node = _place(build, "Landmark_Gullstone_Watch", "Gullstone_Watch",
                  wx, wz, kind="landmark").node
    _landmark(build, "gullstone-watch", "The Gullstone Watch", "tower", node,
              wx, wz, _ground(build, wx, wz))

    # the sea arch on Gullstone's south shore, from the aerial
    ax, az = REG.ANCHORS["gullstone_arch"]
    build.add_mesh("Sea_Arch", SW.ancient_arch(span=9.0, height=11.5, depth=3.2,
                                               seed=seed + 421))
    node = _place(build, "Landmark_Sea_Arch", "Sea_Arch", ax, az,
                  rotation=math.radians(35.0), collides=False,
                  kind="landmark").node
    _landmark(build, "sea-arch", "The Gullstone Arch", "natural", node,
              ax, az, _ground(build, ax, az))

    # rock clutter on both masses, so they read as broken stone not smooth hills
    for v in range(3):
        build.add_mesh(f"Sea_Boulders_{v}", P.rock_cluster(
            radius=2.6 + v * 0.8, count=5 + v, seed=seed + 430 + v,
            material=HK.SEA_ROCK))
    masks = REG.land_masks(build.terrain, seed)
    t = build.terrain
    for name in ("gullstone", "lamp_rock"):
        mask = masks[name]
        rows, cols = np.nonzero(mask)
        for i in range(0, len(rows), max(len(rows) // 60, 1)):
            cz, cx = int(rows[i]), int(cols[i])
            x = float(t.xs[cx]); z = float(t.zs[cz])
            y = float(t.height[cz, cx])
            if y < REG.SEA_LEVEL + 0.5:
                continue
            if _rand(seed, f"rk{name}{i}") > 0.5:
                continue
            _place(build, f"Rock_{name}_{i:04d}",
                   f"Sea_Boulders_{i % 3}", x, z, y=y - 0.6,
                   rotation=_rand(seed, f"rkr{name}{i}") * 6.2,
                   collides=False, kind="rock")


# ------------------------------------------------------------------ upland
def populate_upland(build, seed: int = 0) -> None:
    """The open country north and east: chapel, farm, hill estate, fences."""
    build.add_mesh("Upland_Chapel", HA.cathedral(seed=seed + 501, length=13.0,
                                                 width=7.0, height=6.0))
    cx, cz = REG.ANCHORS["upland_chapel"]
    node = _place(build, "Landmark_Upland_Chapel", "Upland_Chapel", cx, cz,
                  rotation=math.pi * 0.5, collides=False, kind="landmark").node
    _landmark(build, "upland-chapel", "The Wayside Chapel", "temple", node,
              cx, cz, _ground(build, cx, cz))

    build.add_mesh("Farmstead", A.manor(seed=seed + 511, width=13.0, depth=9.0))
    fx, fz = REG.ANCHORS["upland_farm"]
    node = _place(build, "Landmark_Upland_Farm", "Farmstead", fx, fz,
                  rotation=0.4, kind="building").node
    _landmark(build, "upland-farm", "Gullscar Farm", "settlement", node,
              fx, fz, _ground(build, fx, fz))

    build.add_mesh("Hill_Estate", A.manor(seed=seed + 521, width=19.0, depth=13.0))
    hx, hz = REG.ANCHORS["hill_estate"]
    node = _place(build, "Landmark_Hill_Estate", "Hill_Estate", hx, hz,
                  rotation=math.pi * 1.15, kind="building").node
    _landmark(build, "hill-estate", "The Factor's House", "estate", node,
              hx, hz, _ground(build, hx, hz))

    build.add_mesh("East_Watch", A.watchtower(height=14.0, seed=seed + 531,
                                              radius=2.2))
    ex, ez = REG.ANCHORS["east_watch"]
    node = _place(build, "Landmark_East_Watch", "East_Watch", ex, ez,
                  kind="landmark").node
    _landmark(build, "east-watch", "The East Watch", "tower", node, ex, ez,
              _ground(build, ex, ez))

    # field walls along the upland roads, and a signpost at the crossroads
    build.add_mesh("Field_Fence", P.fence(length=5.0, height=1.05,
                                          seed=seed + 541, style="split"))
    build.add_mesh("Signpost", P.signpost(seed=seed + 545, arms=3))
    sx, sz = REG.ANCHORS["crossroads"]
    _place(build, "Prop_Signpost", "Signpost", sx, sz, kind="prop")
    for name in ("north_road", "east_road"):
        points = REG.ROADS[name]
        total = 0.0
        lengths = [0.0]
        for i in range(len(points) - 1):
            total += float(np.linalg.norm(points[i + 1] - points[i]))
            lengths.append(total)
        n = max(int(total / 11.0), 2)
        for i in range(n):
            s0 = total * (i + 0.2) / n
            a = _polyline_point(points, lengths, s0)
            b = _polyline_point(points, lengths, min(s0 + 5.0, total))
            angle = _align(a, b)
            # the road's normal, so the fences run alongside it, not across
            for side in (-1, 1):
                x = a[0] + side * 6.5 * math.sin(angle)
                z = a[1] + side * 6.5 * math.cos(angle)
                y = _ground(build, x, z)
                if y < REG.SEA_LEVEL + 1.5:
                    continue
                _place(build, f"Prop_Fence_{name}_{i:02d}_{side}", "Field_Fence",
                       x, z, y=y, rotation=-angle, collides=False, kind="prop")


# -------------------------------------------------------------- vegetation
def populate_vegetation(build, seed: int = 0, lod: str | None = None) -> None:
    """Tree belts on the upland, thorn scrub on the headland, no forest.

    Westhaven is not a forest region. The painting has shelter belts along the
    upland field boundaries and pines on the north-west headland, and bare turf
    everywhere else - so the tree pass is a belt-follower, not a scatter.
    """
    t = build.terrain
    masks = REG.land_masks(t, seed)
    # `build_tree` returns (wood, foliage) as two meshes so the bark and the
    # alpha-cut canopy stay on their own materials; both are placed at the same
    # point. Two species: dark pine for the shelter belts and the headland,
    # dark holly for the scrubbier hedge lines along the field walls.
    tiers = ("low",) if lod == "far" else ("high", "mid", "low")
    species = ("dark_pine", "dark_pine", "dark_holly")
    for tier in tiers:
        for v in range(3):
            wood, leaves = TR.build_tree(species[v], seed=seed + 600 + v * 17,
                                         detail=tier)
            build.add_mesh(f"Tree_{tier}_{v}_Wood", wood)
            if leaves.triangle_count:
                build.add_mesh(f"Tree_{tier}_{v}_Canopy", leaves)

    gradient_z, gradient_x = np.gradient(t.height, t.cell)
    slope_grid = np.hypot(gradient_x, gradient_z)

    # The belt field, precomputed over the whole terrain grid rather than
    # sampled per candidate. Calling `fbm` with scalars inside the placement
    # loop is both slow and noisy - the lattice hash overflows int64 on scalar
    # input and numpy warns about it on every one of ten thousand candidates -
    # and the array form is the one the rest of the toolkit uses.
    belt_field = N.fbm(t.gx * 0.004, t.gz * 0.030, octaves=3, seed=seed + 611)

    # belts follow the upland's own contour bands, which is where a farmer puts
    # a shelter belt: across the prevailing wind, along a field edge
    count = 0
    step = 7.0
    for iu in range(int(8.6 * 24.0 * REG.SCALE / step)):
        for iv in range(int(4.6 * 24.0 * REG.SCALE / step)):
            u = -0.3 + iu * step / (24.0 * REG.SCALE)
            v = -0.3 + iv * step / (24.0 * REG.SCALE)
            x, z = REG._design_to_world(REG.cell(u, v))
            key = f"t{iu}:{iv}"
            x += (_rand(seed, key + "x") - 0.5) * step * 0.8
            z += (_rand(seed, key + "z") - 0.5) * step * 0.8
            cx = int(np.clip((x - t.x0) / t.cell, 0, t.cols - 1))
            cz = int(np.clip((z - t.z0) / t.cell, 0, t.rows - 1))
            if not masks["mainland"][cz, cx] or masks["city"][cz, cx]:
                continue
            if t.tree_block[cz, cx]:
                continue
            y = float(t.height[cz, cx])
            if y < REG.SEA_LEVEL + 3.0 or slope_grid[cz, cx] > 1.15:
                continue
            # A belt field rather than uniform scatter: high-frequency noise in
            # one direction and low in the other gives lines of trees along the
            # contour instead of a uniform wood, which is what the painting has.
            if belt_field[cz, cx] < 0.60:
                continue
            if _rand(seed, key + "k") > 0.72:
                continue
            distance = math.hypot(x - REG.SPAWN[0], z - REG.SPAWN[1])
            tier = "low" if lod == "far" else (
                "high" if distance < 130.0 else "mid" if distance < 300.0 else "low")
            variant = int(_rand(seed, key + "v") * 3) % 3
            yaw = _rand(seed, key + "r") * 6.2
            scale = 0.8 + _rand(seed, key + "s") * 0.5
            _place(build, f"Tree_{iu:03d}_{iv:03d}_Wood",
                   f"Tree_{tier}_{variant}_Wood", x, z, y=y - 0.15,
                   rotation=yaw, scale=scale,
                   collides=(tier == "high"), kind="tree")
            canopy = f"Tree_{tier}_{variant}_Canopy"
            if canopy in build.meshes:
                _place(build, f"Tree_{iu:03d}_{iv:03d}_Canopy", canopy,
                       x, z, y=y - 0.15, rotation=yaw, scale=scale,
                       collides=False, kind="foliage")
            count += 1
    build.notes.append(f"trees placed: {count}")

    if lod == "far":
        return
    # ground dressing: thrift and thorn on the turf, weed along the tide line
    build.add_mesh("Scrub", P.undergrowth_patch(radius=1.2, count=5,
                                                seed=seed + 621))
    dressed = 0
    for iu in range(0, int(8.6 * 24.0 * REG.SCALE / 11.0)):
        for iv in range(0, int(7.8 * 24.0 * REG.SCALE / 11.0)):
            u = -0.3 + iu * 11.0 / (24.0 * REG.SCALE)
            v = -0.3 + iv * 11.0 / (24.0 * REG.SCALE)
            x, z = REG._design_to_world(REG.cell(u, v))
            cx = int(np.clip((x - t.x0) / t.cell, 0, t.cols - 1))
            cz = int(np.clip((z - t.z0) / t.cell, 0, t.rows - 1))
            y = float(t.height[cz, cx])
            if y < REG.SEA_LEVEL + 1.0 or t.tree_block[cz, cx]:
                continue
            if t.surface[cz, cx] in (TER.PAVING, TER.PATH):
                continue
            if _rand(seed, f"d{iu}:{iv}") > 0.30:
                continue
            _place(build, f"Scrub_{iu:03d}_{iv:03d}", "Scrub", x, z, y=y,
                   rotation=_rand(seed, f"dr{iu}:{iv}") * 6.2,
                   collides=False, kind="foliage")
            dressed += 1
    build.notes.append(f"ground dressing placed: {dressed}")


# ------------------------------------------------------------------- props
def populate_props(build, seed: int = 0) -> None:
    """Dockside clutter - detail-board panel 10 and the working quay."""
    quay_y = REG.LEVEL["quay"]
    build.add_mesh("Barrel", P.barrel(seed=seed + 701))
    build.add_mesh("Crate", P.crate(size=0.72, seed=seed + 703,
                                    material="timber_grey"))
    build.add_mesh("Sack", P.sack(seed=seed + 705))
    build.add_mesh("Fishing_Gear", P.fishing_gear(seed=seed + 707))
    build.add_mesh("Cart", P.cart(seed=seed + 709))
    build.add_mesh("Rowing_Boat", P.rowing_boat(seed=seed + 711))
    build.add_mesh("Brazier", P.brazier(seed=seed + 713))
    build.add_mesh("Workbench", P.workbench(seed=seed + 715))

    front = REG.QUAYSIDE
    total = 0.0
    lengths = [0.0]
    for i in range(len(front) - 1):
        total += float(np.linalg.norm(front[i + 1] - front[i]))
        lengths.append(total)

    pool = ("Barrel", "Crate", "Sack", "Fishing_Gear", "Cart", "Brazier",
            "Workbench")
    for i in range(96):
        s = total * (i + 0.5) / 96.0
        p = _polyline_point(front, lengths, s)
        x = p[0] + (_rand(seed, f"pq{i}x") - 0.5) * 14.0
        z = p[1] + 1.5 + (_rand(seed, f"pq{i}z")) * 7.0
        y = _ground(build, x, z)
        if abs(y - quay_y) > 1.4:
            continue
        # Keep the scatter out of the chandlery still-life. Panel 10 is a macro
        # of one deliberate arrangement, and a random workbench landing across
        # it is the difference between a composed shot and a junk pile.
        if math.hypot(x - REG.ANCHORS["chandlery"][0],
                      z - REG.ANCHORS["chandlery"][1]) < 7.0:
            continue
        name = pool[int(_rand(seed, f"pq{i}n") * len(pool)) % len(pool)]
        _place(build, f"Prop_Quay_{i:03d}", name, x, z, y=y,
               rotation=_rand(seed, f"pq{i}r") * 6.2, collides=False,
               kind="prop")

    # the chandlery still-life of panel 10: a tight cluster, not a scatter
    cx, cz = REG.ANCHORS["chandlery"]
    for i, (dx, dz, name, rot) in enumerate((
            (0.0, 0.0, "Crate", 0.35), (0.9, 0.4, "Crate", 1.10),
            (-0.8, 0.5, "Barrel", 0.0), (0.3, -0.9, "Fishing_Gear", 2.2),
            (1.6, -0.3, "Sack", 0.8), (-1.5, -0.4, "Barrel", 0.0))):
        _place(build, f"Prop_Chandlery_{i:02d}", name, cx + dx, cz + dz,
               y=quay_y, rotation=rot, collides=False, kind="prop")

    # rowing boats drawn up on the beach and moored along the harbour edge
    for i, (u, v) in enumerate(((6.60, 4.96), (6.80, 4.98), (6.44, 5.00),
                                (1.30, 4.74), (2.60, 4.76), (4.10, 4.78))):
        x, z = REG._design_to_world(REG.cell(u, v))
        y = _ground(build, x, z)
        _place(build, f"Prop_Boat_{i:02d}", "Rowing_Boat", x, z,
               y=max(y, REG.SEA_LEVEL - 0.15),
               rotation=_rand(seed, f"bt{i}") * 6.2, collides=False,
               kind="prop")


# ---------------------------------------------------------------- metadata
def populate_metadata(build, seed: int = 0) -> None:
    """Interactives and harvestables. Editor/visual only; the server spawns."""
    t = build.terrain

    interactive_plan = [
        ("westhaven-harbour-bell", "Harbour Bell", "bell", "main_quay", 3.0),
        ("westhaven-tide-board", "Tide Board", "notice", "custom_house", 4.0),
        ("westhaven-market-scales", "Market Scales", "workstation",
         "fish_market", 3.0),
        # On the quay behind the pier root, not on the pier: an interactive
        # inside the pier's footprint records the terrain height under the deck.
        ("westhaven-crane-winch", "Crane Winch", "workstation", "chandlery", 3.0),
        ("westhaven-yard-forge", "Yard Forge", "forge", "shipyard", 5.0),
        ("westhaven-ropewalk-wheel", "Ropewalk Wheel", "workstation",
         "ropewalk", 3.0),
        ("westhaven-guild-ledger", "Guild Ledger", "notice", "guild_hall", 3.0),
        ("westhaven-lamp-store", "Lamp Store", "container",
         "lighthouse_yard", 3.0),
        ("westhaven-cistern", "Street Cistern", "water", "lower_square", 4.0),
        ("westhaven-chapel-font", "Chapel Font", "shrine", "upland_chapel", 2.5),
    ]
    for ident, label, kind, anchor, radius in interactive_plan:
        centre = REG.ANCHORS[anchor]
        angle = _rand(seed, ident) * math.tau
        x = centre[0] + math.cos(angle) * radius
        z = centre[1] + math.sin(angle) * radius
        y = float(t.height_at(x, z))
        build.interactives.append({
            "id": ident, "name": label, "type": kind,
            "position": [round(x, 2), round(y, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "authority": "server"})

    harvest_plan = [
        ("westhaven-mussel-bed", "Mussel Bed", "shellfish", (6.70, 5.02), 5),
        ("westhaven-crab-pots", "Crab Pots", "shellfish", (5.90, 4.86), 4),
        ("westhaven-kelp-shallows", "Kelp Shallows", "plant", (7.20, 5.20), 6),
        ("westhaven-salt-pans", "Salt Pans", "mineral", (6.20, 4.72), 4),
        ("westhaven-thrift-turf", "Sea Thrift", "plant", (1.10, 1.70), 6),
        ("westhaven-gull-eggs", "Gull Eggs", "forage", (1.80, 6.20), 4),
        ("westhaven-driftwood", "Driftwood", "wood", (2.60, 6.90), 5),
        ("westhaven-limpet-rocks", "Limpet Rocks", "shellfish", (6.50, 6.90), 5),
    ]
    for ident, label, kind, (u, v), nodes in harvest_plan:
        centre = REG._design_to_world(REG.cell(u, v))
        for i in range(nodes):
            angle = _rand(seed, f"{ident}{i}a") * math.tau
            r = 4.0 + _rand(seed, f"{ident}{i}r") * 16.0
            x = centre[0] + math.cos(angle) * r
            z = centre[1] + math.sin(angle) * r
            y = float(t.height_at(x, z))
            build.harvestables.append({
                "id": f"{ident}-{i}", "name": label, "type": kind,
                "position": [round(x, 2), round(y, 2), round(z, 2)],
                "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                               int(round(REG.SERVER_ORIGIN[1] - z))],
                "authority": "server"})
