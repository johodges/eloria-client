"""Crownwater placement passes.

Built in the order the guide prescribes - water first, then massing, then
landmarks, then dressing - so that each pass can rely on everything coarser than
it already being final. Terrain and water are proven against the runtime
grounding contract before any of the later passes are written.
"""
from __future__ import annotations

import math

import numpy as np

from amberwood import mesh as M
from amberwood import noise as N
from amberwood import terrain as TER

import region as REG


# ------------------------------------------------------------------ water
def build_water(build) -> None:
    """The lagoon surface.

    Crownwater is one body of water, not a coast: a single plane at sea level
    clipped to wherever the terrain is actually below it. It is deliberately cut
    far outside the authored terrain so that an aerial or a rooftop view sees
    water running to the horizon rather than the edge of a slab, which is what
    the concept's background is.
    """
    t = build.terrain
    lagoon = TER.water_plane(
        t, REG.SEA_LEVEL,
        t.x0 - 420.0, t.z0 - 420.0,
        t.x0 + t.size_x + 420.0, t.z0 + t.size_z + 420.0,
        material="water_sea", cell=6.0, margin=0.15,
        outside_is_water=True)
    build.water_meshes["Water_Lagoon"] = lagoon
