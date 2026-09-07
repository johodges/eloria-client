"""Civic waterfront pieces with material choices supplied by each region."""
from __future__ import annotations
import math
import numpy as np
from . import mesh as M
from . import stonework as SW


def arcaded_causeway(length, near, far, width=5.4, arches=3, foot=-16.0,
                     stone="ashlar", paving="cobble_paving", trim="pale_ashlar"):
    """A surveyed sloping deck on real arches, aligned along local +X.

    The deck top is exactly near/far at its ends. Arch slices share edges
    rather than overlapping boxes, and all masonry finishes below the deck.
    Piers are vertical after shearing and extend below the lagoon bed.
    """
    if length <= 0 or width <= 1 or arches < 1 or foot >= min(near, far) - 1:
        raise ValueError("causeway needs positive dimensions and a foot below its deck")
    out = SW.MeshGroup()
    level = (near + far) / 2
    top, bottom = level, level - 0.5
    x0, x1, z0, z1 = -length/2, length/2, -width/2, width/2
    out.add_walk(M.quad([(x0,top,z0),(x0,top,z1),(x1,top,z1),(x1,top,z0)],
                         uv_scale=0.5, material=paving))
    for face in [
        [(x0,bottom,z0),(x0,top,z0),(x1,top,z0),(x1,bottom,z0)],
        [(x1,bottom,z1),(x1,top,z1),(x0,top,z1),(x0,bottom,z1)],
        [(x0,bottom,z1),(x0,top,z1),(x0,top,z0),(x0,bottom,z0)],
        [(x1,bottom,z0),(x1,top,z0),(x1,top,z1),(x1,bottom,z1)],
        [(x0,bottom,z1),(x0,bottom,z0),(x1,bottom,z0),(x1,bottom,z1)]]:
        out.add(M.quad(face, uv_scale=0.6, material=stone))
    span = length / arches
    pier_width = min(1.5, span * 0.18)
    for i in range(arches + 1):
        x = x0 + span*i
        # End piers stay inside the deck footprint, leaving a flush landing.
        w = pier_width if 0 < i < arches else pier_width/2
        cx = x if 0 < i < arches else x + (w/2 if i == 0 else -w/2)
        out.add(M.box((w, bottom-foot-0.04, width),
                      center=(cx,(bottom+foot-0.04)/2,0), material=stone))
    for i in range(arches):
        left = x0 + span*i + pier_width/2
        right = x0 + span*(i+1) - pier_width/2
        xs = np.linspace(left, right, 25)
        u = np.linspace(-1, 1, 25)
        underside = bottom - 0.6 - min(4.0, span*0.34) * (1-np.sqrt(1-u*u))
        for a,b,ya,yb in zip(xs,xs[1:],underside,underside[1:]):
            for sign in (-1,1):
                face = [(a,ya,sign*width/2),(b,yb,sign*width/2),
                        (b,bottom-0.04,sign*width/2),(a,bottom-0.04,sign*width/2)]
                out.add(M.quad(face if sign > 0 else list(reversed(face)),
                               uv_scale=0.6, material=stone))
            out.add(M.quad([(a,ya,-width/2),(b,yb,-width/2),
                            (b,yb,width/2),(a,ya,width/2)],
                           uv_scale=0.6, material=stone))
    for sign in (-1,1):
        out.add(SW.balustrade(length, 0.85, material=trim)
                .translate(0,top,sign*(width/2+0.29)))
    shear = np.eye(4)
    shear[1,0] = (far-near)/length
    return out.transformed(shear)


def market_shelter(width=14.0, depth=5.0, stone="pale_ashlar",
                   timber="timber_dark", roof="slate_roof"):
    """Open civic market roof; the region supplies its single ground surface."""
    out = SW.MeshGroup()
    for x in (-width/2,0,width/2):
        for z in (-depth/2,depth/2):
            out.add(SW.column(3.2, radius=0.19, material=stone).translate(x,0,z))
    for z in (-depth/2,depth/2):
        out.add(M.box((width+0.8,0.24,0.24),center=(0,4.05,z),material=timber))
    out.add(pitched_canopy(width+1.6,depth+1.4,4.08,5.05,roof,timber))
    return out


def pitched_canopy(width, depth, eave, ridge, roof, lining="timber_dark", thickness=0.12):
    """Closed thin roof with distinct upper and underside skins."""
    if min(width,depth,thickness) <= 0 or ridge <= eave:
        raise ValueError("pitched roof needs positive dimensions and a raised ridge")
    out = SW.MeshGroup()
    for sign in (-1,1):
        top = np.array([[-width/2,eave,sign*depth/2],
                        [width/2,eave,sign*depth/2],
                        [width/2,ridge,0],[-width/2,ridge,0]],dtype=float)
        if sign < 0:
            top = top[::-1]
        lower = top - (0,thickness,0)
        out.add(M.quad(top,uv_scale=0.7,material=roof))
        out.add(M.quad(lower[::-1],uv_scale=0.7,material=lining))
        for i,j in ((0,1),(1,2),(3,0)):
            out.add(M.quad([top[i],lower[i],lower[j],top[j]],
                           uv_scale=0.7,material=roof))
    return out
