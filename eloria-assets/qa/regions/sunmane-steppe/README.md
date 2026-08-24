# Sunmane Steppe regional QA

Sunmane Steppe now follows the concept's broad caravan grassland: four Orun
clan camps surround a shared seasonal market and ceremonial crossroads, with
caravanserais guarding the travel axes and windmills, wells, animal pens,
banner shrines, and burial mounds establishing the wider pastoral landscape.

The layout includes twelve round tents, four market structures, eight banner
shrines, four caravanserais, six windmills, four wells, six animal pens, and six
burial mounds. Eight warm landmark lights supplement the four transition
lights. Dedicated terrain separates clan clearings, open steppe, caravan roads,
and dry grass while preserving the clear `(58,58)` arrival datum.

```sh
python3 eloria-assets/tools/generate_all_assets.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

Validation asserts exact landmark counts, dependency resolution, scenery and
lighting density, all four terrain classes, elevation variation, and arrival
clearance. The committed QA set includes the regional overhead, concept
comparison, and representative landmark topology. Shaded client and map-editor
captures remain pending a GPU-capable session.
