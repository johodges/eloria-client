"""Crownwater placement passes.

Built in the order the guide prescribes - water first, then massing, then
landmarks, then dressing - so each pass can rely on everything coarser than it
already being final. Terrain and water were proven against the runtime grounding
contract before any of this was written.

Two rules run through the whole file:

* **Instance, do not duplicate.** Every causeway of a given length class is one
  mesh placed many times, and the pavilions are one mesh per size. A causeway is
  ~26,000 triangles; authoring twenty-two of them uniquely would cost more than
  the rest of the region put together.
* **Walk surfaces are registered, never assumed.** Only decks, podiums, quay
  aprons and the cathedral stair carry `add_walk`. Anything else marked walkable
  would let the client's downward grounding ray snap an actor onto a dome.
"""
from __future__ import annotations

import math

import numpy as np

from amberwood import mesh as M
from amberwood import noise as N
from amberwood import stonework as SW
from amberwood import terrain as TER

import crownarch as CA
import crownkit as CK
import region as REG


def _heading(dx: float, dz: float) -> float:
    """Rotation about Y that points a mesh's +X axis along (dx, dz).

    `M.rotation_y(theta)` maps +X to (cos theta, 0, -sin theta), so the heading
    is atan2(-dz, dx). Getting this sign wrong mirrors every placement on the
    map and is close to invisible until something reads backwards.
    """
    return math.atan2(-dz, dx)


def _add(build, node: str, mesh_name: str, mesh, position, rotation: float = 0.0,
         scale: float = 1.0, kind: str = "prop", collides: bool = False,
         walk_surface: bool = False, landmark: str | None = None):
    """Register a mesh once and place an instance of it.

    NOTE on `walk_surface`: pass it only for a mesh that is walkable *in its
    entirety*. A `MeshGroup` that declares decks with `add_walk` must NOT set it.
    `RegionBuild.place` renames a walk-surface placement's node to `Walk_...`,
    and the exporter names every child of that container after it - so setting
    the flag on a pavilion makes its dome a walk surface too, and the client's
    grounding ray snaps actors onto the roof. That is exactly what happened
    here: every pavilion grounded 12.8 m up, on top of its own dome.
    """
    if mesh_name not in build.meshes:
        build.meshes[mesh_name] = mesh
    return build.place(REG.Placement(
        node=node, mesh=mesh_name,
        position=(float(position[0]), float(position[1]), float(position[2])),
        rotation_y=rotation, scale=scale, collides=collides,
        walk_surface=walk_surface, kind=kind, landmark=landmark))


# ------------------------------------------------------------------ water
def build_water(build, lod: str | None = None) -> None:
    """The lagoon surface.

    Crownwater is one body of water, not a coast: a single plane at sea level
    clipped to wherever the terrain is actually below it. Cut far outside the
    authored terrain so an aerial or a rooftop view sees water running to the
    horizon rather than the edge of a slab, which is what the concept's
    background is.
    """
    t = build.terrain
    # The plane is clipped per cell, so the cell size is the shoreline's step
    # size: at 6 m every island had a visibly blocky waterline from the air.
    # But it is also a flat quad over 1.5 km square, so halving the cell
    # quadruples its triangles - at 3 m over a 420 m reach it was 480,000
    # triangles, more than half the region's unique geometry, for flat water.
    # 3.5 m over a 260 m reach keeps the waterline clean and costs a fifth of
    # that; the horizon is still well past anything a camera can stand on.
    reach = 260.0
    cell = 3.5 if lod is None else 7.0
    build.water_meshes["Water_Lagoon"] = TER.water_plane(
        t, REG.SEA_LEVEL,
        t.x0 - reach, t.z0 - reach,
        t.x0 + t.size_x + reach, t.z0 + t.size_z + reach,
        material=CK.LAGOON, cell=cell, margin=0.12,
        outside_is_water=True)


# -------------------------------------------------------------- causeways
def populate_causeways(build, seed: int = 0) -> None:
    """Stone causeways stitching the archipelago together.

    Each route runs island centre to island centre; the span itself only covers
    the open water between their edges. Lengths are quantised into a handful of
    classes so a small number of unique meshes can be instanced across all
    twenty-two crossings.
    """
    t = build.terrain
    made: dict[int, str] = {}

    for name, points in REG.CAUSEWAYS.items():
        a_name, b_name = REG.CAUSEWAY_ENDS[name]
        a = REG.ISLAND_GEOM[a_name]
        b = REG.ISLAND_GEOM[b_name]
        ax, az = a["centre"]
        bx, bz = b["centre"]
        dx, dz = bx - ax, bz - az
        centre_distance = math.hypot(dx, dz)
        if centre_distance < 1e-6:
            continue
        ux, uz = dx / centre_distance, dz / centre_distance
        # span only the open water between the two island edges, with a little
        # overlap at each end so the deck sits *on* the landing, not beside it
        start = a["radius"] - 3.0
        end = centre_distance - b["radius"] + 3.0
        span = end - start
        if span < 8.0:
            continue                      # islands already touch; no bridge needed
        mid_t = (start + end) * 0.5
        px, pz = ax + ux * mid_t, az + uz * mid_t

        deck = REG.causeway_deck_level(t, points)
        klass = int(round(span / 12.0))
        length = klass * 12.0
        if length < 12.0:
            continue
        key = f"Causeway_{klass}"
        if key not in made:
            arches = max(2, min(6, int(length // 16)))
            build.meshes[key] = CA.causeway(length, deck_height=6.0,
                                            width=5.4, arches=arches,
                                            seed=seed + klass)
            made[klass] = key
        _add(build, f"Causeway_{name}", key, build.meshes[key],
             (px, deck - 6.0, pz), _heading(dx, dz),
             kind="landmark", collides=False)


# ------------------------------------------------------------- crown isle
def populate_crown_isle(build, seed: int = 0) -> None:
    """The cathedral complex, its plaza, its campanile and its quays."""
    t = build.terrain
    cx, cz = REG.ANCHORS["cathedral"]
    cy = float(t.height_at(cx, cz))

    _add(build, "Landmark_Cathedral", "Cathedral", CA.cathedral(seed=seed),
         (cx, cy, cz), math.pi, kind="landmark", collides=True,
         landmark="crownwater-cathedral")
    build.landmarks.append({
        "id": "crownwater-cathedral", "name": "The Drowned Crown",
        "node": "Landmark_Cathedral", "type": "monument",
        "position": [round(cx, 2), round(cy, 2), round(cz, 2)],
        "serverTile": [int(round(cx + REG.SERVER_ORIGIN[0])),
                       int(round(REG.SERVER_ORIGIN[1] - cz))],
        "note": "placeholder name - see modeling-assumptions.md"})

    bx, bz = REG.ANCHORS["crown_campanile"]
    by = float(t.height_at(bx, bz))
    _add(build, "Landmark_Campanile", "Campanile", CA.campanile(26.0, 4.2, seed),
         (bx, by, bz), 0.0, kind="landmark", collides=True,
         landmark="crownwater-campanile")
    build.landmarks.append({
        "id": "crownwater-campanile", "name": "The Tide Campanile",
        "node": "Landmark_Campanile", "type": "tower",
        "position": [round(bx, 2), round(by, 2), round(bz, 2)],
        "serverTile": [int(round(bx + REG.SERVER_ORIGIN[0])),
                       int(round(REG.SERVER_ORIGIN[1] - bz))],
        "note": "placeholder name - see modeling-assumptions.md"})

    # the compass-rose mosaic of panel 3, laid as inlaid geometry in the plaza
    px, pz = REG.ANCHORS["crown_plaza"]
    py = float(t.height_at(px, pz))
    _add(build, "Walk_CrownPlaza_Rose", "PlazaRose", _compass_rose(11.0),
         (px, py + 0.03, pz), 0.0, kind="landmark", walk_surface=True)

    fountain = SW.fountain(radius=3.4, seed=seed + 5)
    _add(build, "Prop_CrownFountain", "CrownFountain", fountain,
         (px, py + 0.02, pz + 16.0), 0.0, kind="prop", collides=True)

    # statues around the plaza edge
    rng = N.Rng(seed + 31)
    for i in range(8):
        angle = 2.0 * math.pi * i / 8 + 0.2
        sx = px + math.cos(angle) * 19.0
        sz = pz + math.sin(angle) * 19.0
        sy = float(t.height_at(sx, sz))
        if sy < REG.SEA_LEVEL + 0.6:
            continue
        _add(build, f"Prop_CrownStatue_{i}", f"CrownStatue_{i % 3}",
             SW.statue(height=3.1, seed=seed + 40 + i % 3),
             (sx, sy, sz), float(rng.uniform(0, math.tau)),
             kind="prop", collides=True)

    for quay in ("crown_quay_south", "crown_quay_north"):
        _quay_run(build, quay, seed, length=34.0,
                  facing=0.0 if quay.endswith("south") else math.pi)


# ---------------------------------------------------------------- islets
def populate_pavilions(build, seed: int = 0) -> None:
    """A domed pavilion on every inner islet, and a lesser one on the outer ring."""
    t = build.terrain
    for i, name in enumerate(REG._INNER_NAMES):
        if name == "harbour_isle":
            continue                    # the arrival islet is a working harbour
        cx, cz = REG.ANCHORS[name]
        cy = float(t.height_at(cx, cz))
        _add(build, f"Landmark_Pavilion_{name}", "PavilionLarge",
             CA.domed_pavilion(radius=6.4, seed=seed, columns=12),
             (cx, cy, cz), (i * 0.4) % math.tau,
             kind="landmark", collides=True,
             landmark=f"crownwater-pavilion-{name}")
        build.landmarks.append({
            "id": f"crownwater-pavilion-{name}",
            "name": f"{name.replace('_', ' ').title()} Pavilion",
            "node": f"Landmark_Pavilion_{name}", "type": "pavilion",
            "position": [round(cx, 2), round(cy, 2), round(cz, 2)],
            "serverTile": [int(round(cx + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - cz))],
            "note": "placeholder name - see modeling-assumptions.md"})
        _ring_quay(build, name, seed + i)

    for i, name in enumerate(REG._OUTER_NAMES):
        cx, cz = REG.ANCHORS[name]
        cy = float(t.height_at(cx, cz))
        if name == "outer_northeast":
            mesh, key = CA.campanile(19.0, 3.2, seed), "WatchTower"
        elif name == "outer_southwest":
            mesh, key = CA.campanile(23.0, 3.0, seed + 3), "Lighthouse"
        else:
            mesh, key = CA.domed_pavilion(radius=4.2, seed=seed, columns=8), \
                "PavilionSmall"
        _add(build, f"Landmark_Outer_{name}", key, mesh, (cx, cy, cz),
             (i * 0.7) % math.tau, kind="landmark", collides=True)
        _ring_quay(build, name, seed + 50 + i)


def _ring_quay(build, island: str, seed: int) -> None:
    """Four short quay runs around an islet, on the cardinal faces."""
    geom = REG.ISLAND_GEOM[island]
    t = build.terrain
    cx, cz = geom["centre"]
    radius = geom["radius"]
    for k in range(4):
        angle = math.pi * 0.5 * k + 0.35
        qx = cx + math.cos(angle) * (radius - 2.2)
        qz = cz + math.sin(angle) * (radius - 2.2)
        qy = float(t.height_at(qx, qz))
        if qy < REG.SEA_LEVEL + 0.4:
            continue
        _add(build, f"Walk_Quay_{island}_{k}", "QuayShort",
             CA.quay_edge(14.0, height=1.4, seed=seed),
             (qx, qy - 1.4, qz), _heading(-math.sin(angle), math.cos(angle)),
             kind="landmark")


def _quay_run(build, anchor: str, seed: int, length: float,
              facing: float) -> None:
    """A long quay with bollards and a moored boat - panels 2, 6 and 10."""
    t = build.terrain
    qx, qz = REG.ANCHORS[anchor]
    qy = float(t.height_at(qx, qz))
    _add(build, f"Walk_QuayRun_{anchor}", f"QuayRun_{int(length)}",
         CA.quay_edge(length, height=1.5, seed=seed),
         (qx, max(qy - 1.5, REG.SEA_LEVEL - 0.2), qz), facing,
         kind="landmark")
    for k in range(int(length // 7.0)):
        offset = -length * 0.5 + 3.5 + k * 7.0
        bx = qx + math.cos(facing) * offset
        bz = qz - math.sin(facing) * offset
        _add(build, f"Prop_Bollard_{anchor}_{k}", "Bollard", CA.bollard(),
             (bx, max(qy, REG.SEA_LEVEL + 0.05), bz), 0.0, kind="prop")


# --------------------------------------------------------------- harbour
def populate_harbour(build, seed: int = 0) -> None:
    """The arrival islet: quays, lamps, banners, boats and a small market.

    This is where a player lands, so it carries more player-scale detail than
    anywhere else on the map - panels 2, 6 and 10 are all here.
    """
    t = build.terrain
    _quay_run(build, "harbour_quay", seed, length=42.0, facing=0.35)
    _quay_run(build, "harbour_lamp_walk", seed + 1, length=36.0, facing=0.0)

    lx, lz = REG.ANCHORS["harbour_lamp_walk"]
    ly = float(t.height_at(lx, lz))
    for k in range(8):
        offset = -18.0 + k * 5.2
        _add(build, f"Prop_Lamp_Harbour_{k}", "LampPost",
             SW.lamp_post(height=3.4), (lx + offset, ly, lz - 2.4), 0.0,
             kind="prop", collides=True)

    hx, hz = REG.ANCHORS["harbour_quay"]
    hy = float(t.height_at(hx, hz))
    for k in range(4):
        angle = 0.35
        bx = hx + math.cos(angle) * (-14.0 + k * 9.5) - math.sin(angle) * 6.2
        bz = hz - math.sin(angle) * (-14.0 + k * 9.5) - math.cos(angle) * 6.2
        _add(build, f"Prop_Boat_Harbour_{k}", f"Boat_{k % 2}",
             CA.moored_boat(6.0 + (k % 2) * 1.8, seed=seed + k),
             (bx, REG.SEA_LEVEL - 0.18, bz), angle + math.pi * 0.5,
             kind="prop")

    for k in range(4):
        _add(build, f"Prop_Banner_Harbour_{k}", "BannerPole",
             CA.banner_pole(6.8, seed=seed + k),
             # landward of the quay, not on its seaward edge: on the edge the
             # banners stood squarely in the panel-2 sight line and read as
             # four dark slabs across the shot
             (hx - 12.0 + k * 8.0, hy, hz - 11.0), 0.0, kind="prop",
             collides=True)

    mx, mz = REG.ANCHORS["harbour_market"]
    my = float(t.height_at(mx, mz))
    rng = N.Rng(seed + 71)
    for k in range(7):
        angle = 2.0 * math.pi * k / 7
        sx = mx + math.cos(angle) * 7.5
        sz = mz + math.sin(angle) * 7.5
        _add(build, f"Prop_Stall_{k}", f"Stall_{k % 3}",
             _market_stall(seed + k),
             (sx, float(t.height_at(sx, sz)), sz),
             float(rng.uniform(0, math.tau)), kind="prop", collides=True)


def _market_stall(seed: int) -> SW.MeshGroup:
    """A quayside trestle under a canvas awning."""
    out = SW.MeshGroup()
    out.add(M.box((2.6, 0.10, 1.4), center=(0.0, 0.86, 0.0), uv_scale=0.9,
                  material="timber_warm"))
    for sx in (-1.1, 1.1):
        for sz in (-0.55, 0.55):
            out.add(M.box((0.10, 0.86, 0.10), center=(sx, 0.43, sz),
                          uv_scale=0.9, material="timber_dark"))
    for sx in (-1.2, 1.2):
        out.add(M.cylinder(0.06, 0.05, 2.3, 6, uv_scale=0.9,
                           material="timber_dark").translate(sx, 0.0, 0.0))
    out.add(M.box((2.9, 0.06, 1.9), center=(0.0, 2.30, 0.0), uv_scale=1.0,
                  material="canvas_awning"))
    return out


# ---------------------------------------------------------- sunken court
def populate_sunken_court(build, seed: int = 0) -> None:
    """The drowned tiled platform of panel 7.

    Deliberately below the water line and deliberately *not* a walk surface: it
    is scenery seen through clear water, and the lagoon floor under it already
    grounds the tiles it occupies.
    """
    t = build.terrain
    cx, cz = REG.ANCHORS["sunken_court"]
    y = REG.SUNKEN_COURT_LEVEL

    _add(build, "Landmark_SunkenCourt", "SunkenCourt", _compass_rose(13.0),
         (cx, y + 0.06, cz), 0.4, kind="landmark",
         landmark="crownwater-sunken-court")
    build.landmarks.append({
        "id": "crownwater-sunken-court", "name": "The Sunken Court",
        "node": "Landmark_SunkenCourt", "type": "ruin",
        "position": [round(cx, 2), round(y, 2), round(cz, 2)],
        "serverTile": [int(round(cx + REG.SERVER_ORIGIN[0])),
                       int(round(REG.SERVER_ORIGIN[1] - cz))],
        "submerged": True,
        "note": "placeholder name - see modeling-assumptions.md"})

    rng = N.Rng(seed + 91)
    for k in range(9):
        angle = 2.0 * math.pi * k / 9
        px = cx + math.cos(angle) * 15.0
        pz = cz + math.sin(angle) * 15.0
        _add(build, f"Prop_SunkenColumn_{k}", f"SunkenColumn_{k % 3}",
             SW.ruin_fragment(seed=seed + k, scale=1.3),
             (px, float(t.height_at(px, pz)), pz),
             float(rng.uniform(0, math.tau)), kind="prop")


def _compass_rose(radius: float) -> SW.MeshGroup:
    """An inlaid mosaic disc with radiating points - panels 3 and 7.

    Built as flat inlay a few centimetres proud of the paving rather than as a
    texture, so it survives at the grazing angles a player actually sees a plaza
    floor from, and so the same piece can be read underwater in panel 7.
    """
    out = SW.MeshGroup()
    out.add(M.lathe([[0.0, 0.0], [radius, 0.0]], 40, uv_scale=0.35,
                    material=CK.MOSAIC))
    out.add(M.lathe([[radius * 0.92, 0.0], [radius * 0.92, 0.05],
                     [radius, 0.05], [radius, 0.0]], 40, uv_scale=0.5,
                    material=CK.GILT))
    for k in range(8):
        angle = 2.0 * math.pi * k / 8
        length = radius * (0.82 if k % 2 == 0 else 0.52)
        point = M.extrude([[0.0, -radius * 0.09], [length, 0.0],
                           [0.0, radius * 0.09]], 0.04, material=CK.GILT)
        out.add(point.transformed(M.rotation_y(-angle)
                                  @ M.translation(0.0, 0.02, 0.0)))
    return out


# ------------------------------------------------------------- vegetation
def populate_vegetation(build, seed: int = 0, lod: str | None = None) -> None:
    """Palms, hedges and planters - the green in the concept's pale city."""
    t = build.terrain
    rng = N.Rng(seed + 131)
    palm = _palm(seed)
    hedge = _hedge()

    count = 0
    for name, geom in REG.ISLAND_GEOM.items():
        cx, cz = geom["centre"]
        radius = geom["radius"]
        density = 0.55 if name in REG._OUTER_NAMES else 0.32
        attempts = int(radius * radius * 0.0055 * density * 10)
        for _ in range(attempts):
            angle = float(rng.uniform(0, math.tau))
            r = radius * math.sqrt(float(rng.uniform(0.05, 0.94)))
            px = cx + math.cos(angle) * r
            pz = cz + math.sin(angle) * r
            py = float(t.height_at(px, pz))
            if py < REG.SEA_LEVEL + 1.0 or t.blocked_at(px, pz):
                continue
            count += 1
            _add(build, f"Foliage_Palm_{name}_{count}", "Palm", palm,
                 (px, py, pz), float(rng.uniform(0, math.tau)),
                 scale=float(rng.uniform(0.78, 1.32)), kind="tree",
                 collides=True)

    if lod is not None:
        return
    # formal planting beds on the garden islet - panel 8
    gx, gz = REG.ANCHORS["garden_fountain"]
    gy = float(t.height_at(gx, gz))
    _add(build, "Prop_GardenFountain", "GardenFountain",
         SW.fountain(radius=3.0, seed=seed + 7), (gx, gy, gz), 0.0,
         kind="prop", collides=True)
    for ring, count_in_ring in ((7.5, 12), (11.0, 16), (14.5, 20)):
        for k in range(count_in_ring):
            angle = 2.0 * math.pi * k / count_in_ring
            hx = gx + math.cos(angle) * ring
            hz = gz + math.sin(angle) * ring
            hy = float(t.height_at(hx, hz))
            if hy < REG.SEA_LEVEL + 0.8:
                continue
            _add(build, f"Foliage_Hedge_{int(ring)}_{k}", "Hedge", hedge,
                 (hx, hy, hz), _heading(-math.sin(angle), math.cos(angle)),
                 kind="foliage")


def _palm(seed: int) -> SW.MeshGroup:
    """A lagoon palm: a leaning trunk and a crown of fronds."""
    out = SW.MeshGroup()
    height = 6.4
    path = np.asarray([[math.sin(k / 8.0 * 0.6) * 0.9, height * k / 8.0, 0.0]
                       for k in range(9)])
    radii = [0.30 - 0.020 * k for k in range(9)]
    out.add(M.tube(path, radii, segments=7, material="bark_pale"))
    top = path[-1]
    for k in range(9):
        angle = 2.0 * math.pi * k / 9
        frond = M.extrude([[0.0, -0.30], [3.3, -0.10], [3.6, 0.0],
                           [3.3, 0.10], [0.0, 0.30]], 0.05,
                          material="foliage_green")
        tilt = M.rotation_z(math.radians(-26.0 - (k % 3) * 9.0))
        out.add(frond.transformed(
            M.translation(top[0], top[1], top[2]) @ M.rotation_y(-angle) @ tilt))
    return out


def _hedge() -> M.Mesh:
    """A clipped box hedge segment for the formal beds."""
    return M.box((2.6, 0.85, 1.0), center=(0.0, 0.42, 0.0), uv_scale=1.2,
                 material="foliage_green")


# ------------------------------------------------------------------ props
def populate_props(build, seed: int = 0) -> None:
    """Lamps and benches along the causeway landings and plaza edges."""
    t = build.terrain
    rng = N.Rng(seed + 211)
    lamp = SW.lamp_post(height=3.2)
    placed = 0
    for name in REG._INNER_NAMES:
        geom = REG.ISLAND_GEOM[name]
        cx, cz = geom["centre"]
        for k in range(6):
            angle = 2.0 * math.pi * k / 6 + 0.4
            px = cx + math.cos(angle) * (geom["radius"] - 6.0)
            pz = cz + math.sin(angle) * (geom["radius"] - 6.0)
            py = float(t.height_at(px, pz))
            if py < REG.SEA_LEVEL + 0.8:
                continue
            placed += 1
            _add(build, f"Prop_Lamp_{name}_{k}", "LampPostRing", lamp,
                 (px, py, pz), 0.0, kind="prop", collides=True)
    build.notes.append(f"{placed} islet lamp standards placed")


# ------------------------------------------------------------ harvestables
def populate_metadata(build, seed: int = 0) -> None:
    """Interactives and harvestables - editor metadata, server authoritative."""
    t = build.terrain
    rng = N.Rng(seed + 313)

    for interactive_id, name, anchor, kind in (
            ("crownwater-cathedral-doors", "Cathedral Doors", "cathedral", "door"),
            ("crownwater-crown-fountain", "Crown Fountain", "crown_plaza", "fountain"),
            ("crownwater-garden-fountain", "Garden Fountain", "garden_fountain",
             "fountain"),
            ("crownwater-harbour-bell", "Harbour Bell", "harbour_quay", "bell"),
            ("crownwater-sunken-glyph", "Sunken Glyph", "sunken_court", "glyph")):
        x, z = REG.ANCHORS[anchor]
        y = float(t.height_at(x, z))
        build.interactives.append({
            "id": interactive_id, "name": name, "type": kind,
            "position": [round(x, 2), round(y + 0.4, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "authority": "server"})

    for k in range(26):
        island = REG._INNER_NAMES[k % len(REG._INNER_NAMES)]
        geom = REG.ISLAND_GEOM[island]
        angle = float(rng.uniform(0, math.tau))
        r = geom["radius"] * float(rng.uniform(0.2, 0.9))
        x = geom["centre"][0] + math.cos(angle) * r
        z = geom["centre"][1] + math.sin(angle) * r
        y = float(t.height_at(x, z))
        if y < REG.SEA_LEVEL + 0.6:
            continue
        build.harvestables.append({
            "id": f"crownwater-harvest-{k}",
            "resource": ("shellfish" if k % 3 == 0 else
                         "reed" if k % 3 == 1 else "coral"),
            "position": [round(x, 2), round(y, 2), round(z, 2)],
            "serverTile": [int(round(x + REG.SERVER_ORIGIN[0])),
                           int(round(REG.SERVER_ORIGIN[1] - z))],
            "authority": "server"})
