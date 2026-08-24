# Four Gates fauna and harvesting QA

`four_gates_fauna_wireframes.png` shows, clockwise from upper left:

1. Mirrorfin otter — 728 vertices / 1,384 faces
2. Reedhorn stag — 928 vertices / 1,768 faces
3. Lakeglass drake — 780 vertices / 1,496 faces
4. Gate turtle — 780 vertices / 1,504 faces

`four_gates_harvestable_wireframes.png` shows resonant crystal, stormglass
shard, mirror reed and sunmane seed. Their runtime E3D meshes contain 160,
160, 164 and 180 vertices respectively. The adjacent material sheet shows the
complete 256px textures used by those nodes.

Regenerate after building the complete data pack:

```sh
for name in mirrorfin_otter reedhorn_stag gate_turtle lakeglass_drake; do
  python3 eloria-assets/tools/render_cal3d_wireframe.py \
    "build/eloria-data/actors/nymara/creatures/$name.xmf" \
    "eloria-assets/qa/four-gates/fauna/${name}_wireframe.png"
done
for name in resonant_crystal stormglass_shard mirror_reed sunmane_seed; do
  python3 eloria-assets/tools/render_e3d_wireframe.py \
    "build/eloria-data/3dobjects/nymara/$name.e3d" \
    "eloria-assets/qa/four-gates/fauna/${name}_wireframe.png"
done
```
