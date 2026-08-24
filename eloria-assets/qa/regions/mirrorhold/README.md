# Mirrorhold regional QA

Mirrorhold now uses an authored composition derived from its regional concept:
an elevated northern observatory citadel, lens-tower crown, terraced civic
descent, and a bridge-linked lower lake district. The central `(58,58)` arrival
plaza and west/east transition corridors remain unobstructed.

The layout includes one observatory, four lens towers, eight civic towers, nine
canal walls, six radial bridges, six fountains, and eight field stations. Nine
cool landmark lights supplement the four transition lights. Custom tile and
height functions provide distinct citadel, road, upland, and lake zones.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts landmark counts, scenery and lighting density, all four
terrain classes, elevation variation, dependencies, and the clear arrival
radius. The concept/overhead composite verifies the intended high-city to
lower-lake hierarchy. Shaded client and map-editor captures remain pending a
GPU-capable session.
