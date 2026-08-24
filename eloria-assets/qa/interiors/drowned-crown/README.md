# Drowned Crown interior QA

The Drowned Crown is the first authored Nymara interior replacement. Its former
shared three-room placement template is replaced by a ceremonial submerged
processional: a clear arrival vestibule, twin water galleries, a statue court,
and a shell-altar objective chamber.

The layout contains 12 drowned-floor modules, 14 underwater-wall modules, six
submerged arches, eight water channels, four statues, and one focal altar. Eight
additional teal lights supplement the four transition lights. The entrance at
`(58,10)` remains unobstructed and the existing map ID and transition metadata
are unchanged.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
python3 eloria-assets/tools/render_map_qa.py \
  build/eloria-data/maps/nymara/drowned_crown.elm \
  eloria-assets/qa/interiors/drowned-crown/drowned_crown_overhead.png
```

The validator asserts the authored module counts, minimum scenery density,
lighting density, dependency resolution, and clear arrival radius. The overhead
image is a deterministic placement QA view; shaded map-editor and in-client
captures remain pending a GPU-capable session.
