# Four Gates visual QA

- `four_gates_cartography.png` is mip level zero from the generated client DDS.
- `four_gates_overhead.png` is a deterministic ELM overhead render. Gold marks
  gatehouses and bridges, pale marks civic towers, green marks the park belt,
  and the white cross marks the unobstructed `(58,58)` arrival.
- `four_gates_civic_tower_wireframe.png` is an isometric topology view of the
  representative 560-vertex civic tower E3D.
- `four_gates_gatehouse_wireframe.png` is the corresponding view of the refined
  848-vertex monumental gatehouse.
- `four_gates_terrain_sheet.png` shows the full-resolution civic stone,
  highland grass, ceremonial road and water materials used by tile IDs 4-7.

Regenerate after building the asset pack:

```sh
convert build/eloria-data/maps/nymara/four_gates.dds[0] \
  eloria-assets/qa/four-gates/four_gates_cartography.png
python3 eloria-assets/tools/render_map_qa.py \
  build/eloria-data/maps/nymara/four_gates.elm \
  eloria-assets/qa/four-gates/four_gates_overhead.png
python3 eloria-assets/tools/render_e3d_wireframe.py \
  build/eloria-data/3dobjects/nymara/four_gates_civic_tower.e3d \
  eloria-assets/qa/four-gates/four_gates_civic_tower_wireframe.png
python3 eloria-assets/tools/render_e3d_wireframe.py \
  build/eloria-data/3dobjects/nymara/four_gates_gatehouse.e3d \
  eloria-assets/qa/four-gates/four_gates_gatehouse_wireframe.png
convert +append build/eloria-data/3dobjects/tile{4,5,6,7}.png \
  eloria-assets/qa/four-gates/four_gates_terrain_sheet.png
```
