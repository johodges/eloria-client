"""Whitehorn's camera set and detail-board panel mapping.

Per-region data used by the shared toolkit's `capture_views.py` and
`make_comparison.py`. Coordinates are design-space (x, z) pairs; heights are
metres above the local ground, not absolute Y, so a change to the terrain
moves the cameras with it instead of burying them.

Tuple layout, matching capture_views:
    (name, panel, eye_xz, eye_height, target_xz, target_height,
     fov, size, clearance_radius, lighting_mode)

`panel` is the detail-board panel this view answers, or None for a view that
exists only to check the build. Panel numbering follows the ten-panel board,
left to right, top row then bottom.
"""
from __future__ import annotations

VIEWS = [
    # -- the aerial, against the region concept --------------------------
    ("00-aerial-overview", "aerial", (38, 132), 150.0, (38, -48), 0.0, 44,
     (1400, 900), 190, "day"),

    # -- the ten detail-board panels -------------------------------------
    # 1: the approach - cairn-lined road climbing north toward the blue temple
    ("01-approach-road", 1, (4.0, 22.0), 1.7, (12.0, -2.0), 3.0, 60,
     (1180, 760), 40, "day"),
    # 2: the temple facade, its glowing arch, statues, braziers and inlay
    ("02-glacier-temple", 2, (34.0, -84.0), 2.4, (34.0, -101.0), 9.0, 52,
     (1180, 900), 34, "day"),
    # 3: the rope bridge over the gorge
    ("03-rope-bridge", 3, (17.0, -13.0), 2.6, (17.0, -30.0), 5.0, 56,
     (1180, 780), 34, "day"),
    # 4: the statue shrine in its arched alcove
    ("04-gate-shrine", 4, (-11.0, 42.0), 2.2, (-11.0, 34.0), 3.4, 55,
     (1080, 920), 24, "day"),
    # 5: the cairn field on the western ridge
    ("05-cairn-ridge", 5, (-20.0, -58.0), 2.0, (-30.0, -69.0), 1.6, 58,
     (1180, 780), 30, "day"),
    # 6: the ice cave mouth
    ("06-ice-cave", 6, (-30.0, -6.0), 2.4, (-38.0, -15.0), 3.4, 56,
     (1180, 800), 26, "day"),
    # 7: the mine portal, its rails and spoil heaps
    ("07-mine-portal", 7, (89.0, -39.0), 2.4, (96.0, -46.0), 3.2, 55,
     (1180, 800), 28, "day"),
    # 8: the frozen cascade and the waystones at its foot
    ("08-frozen-cascade", 8, (26.0, -44.0), 3.0, (26.0, -58.0), 9.0, 54,
     (1180, 900), 34, "day"),
    # 9: the cairn stair and the panorama beyond it
    ("09-high-overlook", 9, (74.0, 12.0), 4.0, (34.0, -60.0), 30.0, 50,
     (1400, 800), 120, "day"),
    # 10: a material study - rope, brass, ice and dressed stone together
    ("10-material-study", 10, (17.0, -21.4), 1.2, (17.0, -25.0), 0.9, 40,
     (1080, 880), 14, "day"),

    # -- views that exist to check the build, not to match a panel -------
    ("11-spawn-grounding", None, (-6.0, 8.0), 1.7, (6.0, -6.0), 1.6, 58,
     (1180, 780), 30, "day"),
    ("12-gorge-edge", None, (30.0, -16.0), 2.4, (10.0, -26.0), -6.0, 56,
     (1280, 780), 34, "day"),
    ("13-upper-bridge", None, (62.0, -22.0), 3.0, (62.0, -38.0), 6.0, 54,
     (1180, 780), 32, "day"),
    ("14-temple-forecourt", None, (34.0, -78.0), 2.6, (34.0, -92.0), 4.0, 56,
     (1180, 800), 30, "day"),
    ("15-glacier-snout", None, (16.0, 16.0), 3.0, (18.0, -4.0), 2.0, 55,
     (1280, 780), 36, "day"),
    ("16-glacier-head", None, (34.0, -92.0), 6.0, (34.0, -114.0), 20.0, 52,
     (1280, 820), 44, "day"),
    ("17-mine-yard", None, (110.0, -14.0), 3.4, (92.0, -40.0), 3.0, 54,
     (1280, 780), 40, "day"),
    ("18-south-gate", None, (-4.0, 40.0), 2.4, (-4.0, 27.0), 4.0, 55,
     (1080, 820), 26, "day"),
    ("19-pine-shelf", None, (-14.0, 26.0), 3.0, (-27.0, 17.0), 2.0, 55,
     (1280, 780), 34, "day"),
    ("20-north-shrine", None, (16.0, -112.0), 2.4, (9.0, -120.0), 3.0, 55,
     (1080, 820), 26, "day"),
    ("21-west-watch", None, (-36.0, -36.0), 3.0, (-44.0, -45.0), 3.0, 55,
     (1180, 780), 28, "day"),
    ("22-east-camp", None, (98.0, -2.0), 3.0, (110.0, -7.0), 2.0, 55,
     (1280, 780), 32, "day"),
    ("23-snow-line", None, (52.0, -20.0), 4.0, (44.0, -52.0), 14.0, 54,
     (1280, 780), 50, "day"),

    # -- late light, to check the ice and brass read in warm light -------
    ("40-golden-temple", None, (34.0, -76.0), 5.0, (34.0, -101.0), 10.0, 50,
     (1400, 820), 44, "golden"),
    ("41-golden-glacier", None, (10.0, -20.0), 8.0, (30.0, -62.0), 16.0, 50,
     (1400, 820), 60, "golden"),
]

PANELS = {
    1: ("01-approach-road", "Cairn-lined approach road climbing to the pass"),
    2: ("02-glacier-temple", "Glacier temple facade, glowing arch and braziers"),
    3: ("03-rope-bridge", "Rope-and-plank bridge over the gorge"),
    4: ("04-gate-shrine", "Statue shrine in an arched alcove"),
    5: ("05-cairn-ridge", "Cairn field on a snowy ridge"),
    6: ("06-ice-cave", "Ice cave mouth in blue glacier ice"),
    7: ("07-mine-portal", "Timber-framed mine entrance with rails"),
    8: ("08-frozen-cascade", "Frozen waterfall with waystones at its foot"),
    9: ("09-high-overlook", "High overlook across the range"),
    10: ("10-material-study", "Material study: rope, brass, ice, dressed stone"),
}


# Alpine daylight. The toolkit's defaults are tuned for Amberwood's warm
# autumn forest - a 1.22/0.94/0.60 sun at saturation 1.30 - which renders a
# snow region as brown ground under a sodium lamp. Snow is a high-albedo,
# low-saturation subject lit largely by sky bounce, so the sun cools and
# dims, the sky term rises, and saturation comes down. Fog stays thin and
# cold to keep the far ridges legible rather than hazing them out.
DAY_LIGHTING = {
    "sun_direction": (-0.38, 0.62, 0.68),
    "sun_color": (1.06, 1.06, 1.10),
    "sky_color": (0.40, 0.48, 0.62),
    "ground_color": (0.30, 0.34, 0.40),
    "fog_color": (0.62, 0.68, 0.76),
    "fog_density": 0.00048,
    "fog_height_falloff": 0.0026,
    "ambient_strength": 0.52,
    "shadow_strength": 0.66,
    "exposure": 1.02,
    "saturation": 0.92,
    "sky_zenith": (0.24, 0.38, 0.62),
    "sky_horizon": (0.72, 0.78, 0.86),
}

# Late light on the ice: warm sun, but the snow still bounces cold sky into
# the shadows, so the ambient stays blue rather than going orange with it.
GOLDEN_LIGHTING = {
    "sun_direction": (-0.80, 0.24, 0.52),
    "sun_color": (1.44, 1.02, 0.66),
    "sky_color": (0.34, 0.40, 0.56),
    "ground_color": (0.24, 0.26, 0.34),
    "fog_color": (0.68, 0.62, 0.62),
    "fog_density": 0.0011,
    "ambient_strength": 0.42,
    "shadow_strength": 0.74,
    "exposure": 1.05,
    "saturation": 1.06,
    "sky_zenith": (0.22, 0.30, 0.52),
    "sky_horizon": (0.88, 0.72, 0.56),
}
