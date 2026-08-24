# Four Gates visual QA

- `four_gates_cartography.png` is mip level zero from the generated client DDS.
- `four_gates_overhead.png` is a deterministic ELM overhead render. Gold marks
  gatehouses and bridges, pale marks civic towers, green marks the park belt,
  and the white cross marks the unobstructed `(58,58)` arrival.

Regenerate after building the asset pack:

```sh
convert build/eloria-data/maps/nymara/four_gates.dds[0] \
  eloria-assets/qa/four-gates/four_gates_cartography.png
python3 eloria-assets/tools/render_map_qa.py \
  build/eloria-data/maps/nymara/four_gates.elm \
  eloria-assets/qa/four-gates/four_gates_overhead.png
```
