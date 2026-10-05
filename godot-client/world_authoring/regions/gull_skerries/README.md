# The Gull Skerries (`gull_skerries`), continent v2

The third map (D2c): the south tip, its two islets and the west cliff strip, which no window that holds the SE islet
can reach.

- `gull_skerries.tscn`: the authored territory scene. Its first bootstrap wrote the frame, the ownership sha, the
  territory hub and the other markers; from here on it is the editor's. On this branch the editor reads the v2
  catalog (`world_authoring/continent-v2/territories.json`), which lists the three island-group maps.
- `../../continent-v2/viewer/gull_skerries_view.tscn`: the scene with a sky, a sun and the sea;
  `../../continent-v2/viewer/isles_view.tscn` shows the three territories together.
- `base-heights.f32le`, `base-colors.rgba8`: a byte crop of sw_isle's base (rows 439-1258, columns 0-611 of its 1446
  x 1259 grid; `terrain-provenance.json`). sw_isle's grid covers the whole island group, so the vertices this
  territory shares with sw_isle hold the same bytes on both sides. Never edit these files: this territory's own
  terrain fixes go in its sculpt layer, patches and paths. The sculpt tool locks 4 m inside the ownership polygon
  and fades over 4 more, so nothing it writes reaches a shared vertex.
- `region-authoring-spec.json`: frame and server address (origin (571, 779), 1560 tiles).
- `assets/prototypes/`, `assets/textures/`: the territory kit the Territories palette offers here, written by
  `eloria-assets/maps/continent-v2/gull_skerries/source/prepare_meshy_kit.py` (`--check` verifies it): 46 nature
  and coast pieces copied byte for byte from sw_isle's prepared kit (trees, ground cover, cliff-foot rock, sea
  stacks, beach wrack, and the N18 cliff face and N19 corner), so the placements the D2b window shift handed over
  from sw_isle keep their exact models.

Ownership polygon (continent metres): (329, 7101), (399, 7101), (399, 8259), (1461, 8259), (1461, 8651), (329,
8651). The seams with sw_isle are listed in the v2 plan
(`eloria-assets/maps/continent-v2/_continent_v2/continent-v2-plan.json`, `seams`): decks never cross a border; the
walk crosses on open land seams or on seam moles, rectangular Set patches declared identically in both scenes.
`godot-client/tools/continent_v2_territories.py` (and `godot-client/tests/test_continent_v2_territories.py`) checks
that the shared vertices keep the same base bytes, no sculpt delta and the same patches on both sides, that the
polygons do not overlap and that no island land is left unowned.

The bootstrap writes this README only when it is missing; it is maintained by hand.
