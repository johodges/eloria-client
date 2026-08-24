# Manymouth Delta regional QA

Manymouth Delta now follows the concept's sprawling wetland settlement. Stilt
house clusters and market platforms occupy the stable islands, linked by
boardwalks and ferry docks across a branching main channel and distributaries.
Hidden docks, flooded caves, and mangrove belts establish smuggling and
exploration routes around the inhabited core.

The layout includes eleven stilt houses, ten boardwalks, five ferry docks, four
hidden docks, twelve mangroves, six market stalls, and four flooded caves.
Eight green landmark lights supplement the four transition lights. Dedicated
terrain separates wetland islands, raised walkways, river channels, and delta
ground while preserving the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, channel depth, and arrival
clearance. This completes authored placement and terrain logic for all twelve
Nymara exterior regions. Shaded client and map-editor captures remain pending a
GPU-capable session.
