# Grey Moor Barrows QA

The Barrows now use an authored crypt progression with barrow arches,
sarcophagus aisles, marked trap corridors, and a ritual-altar objective chamber.
The central traversal route and `(58,10)` arrival remain clear.

The layout contains 12 crypt floors, 14 crypt walls, six barrow arches, eight
sarcophagi, four spike traps, and one ritual altar. Eight cold crypt lights
supplement the four transition lights. Map identity and transition metadata are
unchanged.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact module counts, dependency resolution, scenery and
lighting density, and the unobstructed arrival radius. Shaded map-editor and
client captures remain pending a GPU-capable session.
