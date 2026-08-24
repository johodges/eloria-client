# Whitehorn Range regional QA

Whitehorn Range now follows the concept's glacial mountain corridor: a northern
monastery overlooks a descending glacier spine crossed by staggered rope
bridges, shrine paths, cairn wayfinding, and distinct cave and mine entrances.

The layout includes one monastery, six glacier modules, five rope bridges, six
shrines, ten cairns, four ice caves, and three mine entrances. Eight cool
landmark lights supplement the four transition lights. Custom terrain separates
snow, rock, roads, and glacier surfaces with substantial mountain relief while
keeping `(58,58)` clear.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependencies, density, lighting, all
four terrain classes, elevation variation, and arrival clearance. Shaded client
and map-editor captures remain pending a GPU-capable session.
