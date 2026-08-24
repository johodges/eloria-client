# Resonant Vault QA

The Resonant Vault now uses an authored Glasswarden research layout instead of
the shared interior template. A clear arrival route passes brass-walled work
galleries, archive bays, crystal-light stations, and a focal observatory lens.

The layout contains 12 laboratory floors, 14 brass walls, six experiment
tables, six archive shelves, eight crystal braziers, and one observatory lens.
Eight violet resonant lights supplement the four transition lights. The
`(58,10)` entrance, map identity, and transition metadata remain unchanged.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact module counts, minimum scenery and lighting density,
dependency resolution, and a clear arrival radius. Shaded map-editor and client
captures remain pending a GPU-capable session.
