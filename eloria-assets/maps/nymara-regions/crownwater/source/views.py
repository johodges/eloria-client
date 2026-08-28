"""Crownwater's camera set and detail-board panel mapping.

Per-region data used by the shared toolkit's `capture_views.py` and
`make_comparison.py`, and - via `camera-views.json`, which the build emits from
this same table - by the in-client capture harness
`godot-client/tests/integration/rendered_crownwater.gd`.

One table, two consumers, so an offline preview and a real client frame are
always the same framing and can be compared honestly.

Coordinates are design-space (x, z) pairs, the same 192 m space `region.py` is
written in, so they scale with the region. Heights are metres **above the local
ground**, not absolute Y - a camera given an absolute height ends up underground
the moment the terrain changes.
"""
from __future__ import annotations

# (id, panel, eye_xz, eye_height, target_xz, target_height, fov, size,
#  shadow_radius, lighting)
VIEWS = [
    ("00-aerial-overview", "aerial", (38, -128), 190.0, (38, -38), 8.0, 46,
     (1400, 900), 200, "day"),

    # --- the ten detail-board panels -----------------------------------
    # off the crown-isle causeway spokes, which lie on x + z = 0 and x = 38:
    # the first framing here put the camera directly under a deck
    # In the moat ring at 112.5 degrees - between the 90 and 135 degree spokes,
    # so clear of every causeway, and inside the ring so the pavilions do not
    # stand between the camera and the cathedral.
    # r = 42 in design space, beyond the crown isle plateau's 22.9 m edge
    # falloff: at r = 35 the camera came out standing on the shelf rather than
    # afloat, because the plateau overwrites the moat where the two overlap.
    # The eye is 15 m up rather than at barge height because the crown isle
    # rises 8 m out of the water: from 3 m the island's own edge occludes the
    # cathedral standing on it, which is not a framing the concept has.
    ("01-crown-approach", 1, (21.9, 0.8), 15.0, (38.0, -44.0), 18.0, 50,
     (1280, 860), 70, "day"),
    ("02-harbour-quay", 2, (16.5, 0.6), 2.6, (8.8, -7.4), 1.1, 55,
     (1180, 800), 26, "day"),
    ("03-crown-plaza", 3, (38.0, -19.0), 1.7, (38.0, -31.0), 2.2, 56,
     (1280, 820), 34, "day"),
    # standing on the spoke deck itself, which is 8 m above a lagoon floor at
    # about -6.6, hence the large ground-relative eye height
    ("04-causeway", 4, (12.4, -12.4), 16.3, (38.0, -44.0), 16.0, 54,
     (1280, 800), 46, "day"),
    ("05-pavilion-islet", 5, (77.0, -23.0), 30.0, (92.0, -38.0), 5.0, 48,
     (1180, 860), 44, "day"),
    # along the walk's own axis (its quay run faces +X), not across it: framed
    # across, the quay's own back wall fills the shot
    ("06-lamp-walk", 6, (-3.5, -10.8), 1.7, (7.0, -10.8), 1.7, 55,
     (1280, 800), 28, "day"),
    # Below the surface. The lagoon plane is nearly opaque by design - that is
    # what makes the water read turquoise - so no camera above it can see the
    # court through it. The concept panel is an underwater view, so the camera
    # goes underwater; `submerged` tells the view emitter not to clamp the eye
    # to sea level. The offline tool treats the mode as ordinary daylight.
    ("07-sunken-court", 7, (-2.0, -29.0), 0.60, (-2.0, -26.0), -1.85, 46,
     (1180, 860), 26, "submerged"),
    ("08-garden-isle", 8, (-27.0, -25.0), 32.0, (-16.0, -38.0), 4.0, 48,
     (1180, 860), 42, "day"),
    ("09-dome-overlook", 9, (52.0, -49.0), 26.0, (38.0, -44.0), 24.0, 52,
     (1400, 820), 60, "day"),
    ("10-bollard-macro", 10, (11.6, -4.0), 1.15, (9.2, -6.4), 0.50, 42,
     (1080, 880), 12, "day"),

    # --- further coverage ----------------------------------------------
    ("11-cathedral-front", None, (38.0, -22.0), 2.0, (38.0, -40.0), 14.0, 52,
     (1280, 880), 46, "day"),
    ("12-cathedral-stair", None, (38.0, -26.0), 1.7, (38.0, -35.0), 6.0, 55,
     (1180, 860), 26, "day"),
    ("13-ring-causeway", None, (64.0, -1.0), 4.0, (78.0, -18.0), 5.0, 54,
     (1280, 800), 46, "day"),
    ("14-harbour-market", None, (-4.0, 4.0), 1.7, (-8.0, -1.0), 1.6, 56,
     (1180, 800), 24, "day"),
    ("15-outer-islet", None, (104.0, 8.0), 4.0, (119.0, -4.0), 4.0, 52,
     (1280, 800), 42, "day"),
    ("16-lighthouse", None, (-32.0, -62.0), 5.0, (-43.0, -72.0), 10.0, 50,
     (1180, 860), 40, "day"),
    ("17-plaza-fountain", None, (38.0, -24.0), 1.7, (38.0, -29.0), 1.4, 55,
     (1180, 820), 20, "day"),
    ("18-water-level", None, (20.0, -18.0), 0.8, (38.0, -40.0), 16.0, 50,
     (1400, 800), 64, "day"),
    ("19-campanile-base", None, (50.0, -44.0), 1.7, (54.0, -50.0), 12.0, 55,
     (1180, 880), 26, "day"),
    ("20-spawn-grounding", None, (2.0, 3.0), 1.7, (10.0, -6.0), 1.7, 58,
     (1180, 800), 28, "day"),

    # --- golden hour ----------------------------------------------------
    ("40-golden-approach", None, (21.9, 0.8), 15.0, (38.0, -44.0), 18.0, 50,
     (1400, 820), 74, "golden"),
    ("41-golden-aerial", None, (38, -122), 170.0, (38, -38), 8.0, 46,
     (1400, 900), 190, "golden"),
]

PANELS = {
    1: ("01-crown-approach",
        "The domed palace complex seen across open water from a barge"),
    2: ("02-harbour-quay",
        "Quayside: brass bollards, mooring rope, a moored boat"),
    3: ("03-crown-plaza",
        "Plaza with compass-rose mosaic, fountain and domed buildings"),
    4: ("04-causeway",
        "Long arched causeway over clear shallow water"),
    5: ("05-pavilion-islet",
        "Islet with domed pavilion, planting and stairs down to the water"),
    6: ("06-lamp-walk",
        "Waterfront walk with lamp standards and banner poles"),
    7: ("07-sunken-court",
        "Submerged tiled platform with an inlaid glyph, seen through water"),
    8: ("08-garden-isle",
        "Garden plaza: central fountain, concentric planting beds, palms"),
    9: ("09-dome-overlook",
        "Rooftop view across a gilt-finialled dome to the city beyond"),
    10: ("10-bollard-macro",
         "Macro: brass bollard and rope on a stone quay edge"),
}
