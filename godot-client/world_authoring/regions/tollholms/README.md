# The Tollholms (`tollholms`), continent v2

The second map (D2a): the SE islet with the village Tollholm, Ringholm (the east islet east of x 2437) and the outer
east pier (the Toll Tower N11, B15 and the N14 ferry berth); its north-east edge follows the midline of the strait
to the mainland.

- `tollholms.tscn`: the authored territory scene. Its first bootstrap wrote the frame, the ownership sha, the
  territory hub and the other markers, and the seam moles `Terrain/Patches/seam-mole-knob` and
  `Terrain/Patches/seam-mole-pier`; from here on it is the editor's. On this branch the editor reads the v2 catalog
  (`world_authoring/continent-v2/territories.json`), which lists the three island-group maps.
- `../../continent-v2/viewer/tollholms_view.tscn`: the scene with a sky, a sun and the sea;
  `../../continent-v2/viewer/isles_view.tscn` shows the three territories together.
- `base-heights.f32le`, `base-colors.rgba8`: a byte crop of sw_isle's base (rows 115-1120, columns 1039-1445 of its
  1446 x 1259 grid; `terrain-provenance.json`). sw_isle's grid covers the whole island group, so the vertices this
  territory shares with sw_isle hold the same bytes on both sides. Never edit these files: this territory's own
  terrain fixes go in its sculpt layer, patches and paths. The sculpt tool locks 4 m inside the ownership polygon
  and fades over 4 more, so nothing it writes reaches a shared vertex.
- `region-authoring-spec.json`: frame and server address (origin (367, 949), 1902 tiles).
- `assets/prototypes/`, `assets/textures/`: the territory kit the Territories palette offers here, written by
  `eloria-assets/maps/continent-v2/tollholms/source/prepare_meshy_kit.py` (`--check` verifies it): 105 pieces copied
  byte for byte from sw_isle's prepared kit (village, fishers, farms, the tower pier's N11/N13/N14/N12 pieces, trees,
  ground cover, coast and rock), and the Tollholms landmarks O1 (Ringholm watch tower), O2 (Tollholm boathouse) and
  O3 (Spindle Hill beacon, prepared for the summit path and not placed until it is built). One piece is lightened
  from a shared one by `lighten_kit.py` (Blender; recorded in `lighten-kit.json`): `kit-vineyard-rows-1-light`,
  the vineyard row at 2,212 of its 4,432 triangles, same material, textures, size and origin, which every vineyard
  here is laid with (owner, 2026-10-03).

Ownership polygon (continent metres): (2437, 6453), (2517, 6499), (2637, 6511), (2717, 6547), (2797, 6627), (2877,
6713), (2957, 6797), (3037, 6863), (3161, 6959), (3161, 8343), (2437, 8343). The seams with sw_isle are listed in
the v2 plan (`eloria-assets/maps/continent-v2/_continent_v2/continent-v2-plan.json`, `seams`): decks never cross a
border; the walk crosses on open land seams or on seam moles, rectangular Set patches declared identically in both
scenes. `godot-client/tools/continent_v2_territories.py` (and `godot-client/tests/test_continent_v2_territories.py`)
checks that the shared vertices keep the same base bytes, no sculpt delta and the same patches on both sides, that
the polygons do not overlap and that no island land is left unowned.

The bootstrap writes this README only when it is missing; it is maintained by hand.
