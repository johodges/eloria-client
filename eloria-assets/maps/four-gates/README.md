# Four Gates

Four Gates is a 396 × 396 metre inhabited civic island. Its native gatehouses,
shops, temple and crystal monument retain their dimensions. Streets, plots,
shore roads and building parcels were replanned around those landmarks.

The server map remains `four_gates`. One tile is one metre, with server origin
`[198, 198]`; +Y is up and −Z is north. Arrival is tile `[198, 143]`. The civic
plateau is Y31, causeway decks Y23 and surrounding water Y19. The formal wall
follows radius120; working shores and two practice yards occupy the outer land.

North connects to Mirrorhold and west to Crownwater through surveyed shared
causeways with seven metre carriageways. East to Sunmane Steppe and south to
Ssarathi Ruins retain ordinary transitions; those neighbours are not yet surveyed.
All six named interiors, fourteen secrets, eight tutorial resource types and two
35×35 practice areas with existing40/60 caps remain available.

## Reproduce

From the client root:

```powershell
python eloria-assets/maps/four-gates/source/rebuild_landscape.py --rebuild-interiors
```

The wrapper exports main and LOD scenes, raw half-metre collision and a minimap
from final geometry; refines heights; opens exposed walking meshes; stamps solid
landmarks; applies the actor-centre support guard; synchronizes six room doors;
rebuilds shared secrets; and verifies the exterior. `--rebuild-interiors` also
regenerates the six native rooms. `--skip-build`, `--skip-interiors` and
`--skip-secrets` support focused maintenance passes.

`source/landscape_plan.py` owns terrain, roads, parcels, content posts and combat
yards. `source/build_four_gates.py` composes the existing art kits using shared
`RegionBuild`. `source/native_adapter.py` translates native materials and fields
into the shared exporter. `source/migrate_compact_server.py` produces a report by
default; the rollout coordinator owns server writes. Served markers are restored
through shared `contentposts`. Texture caches are disposable and ignored.

## Checks and evidence

`runtime-validation.json` records grounding and manifest checks. Artifacts under
`work-output/coastal-rollout/four-gates` hold actual `World.find_path` proofs,
complete practice-yard audits, frozen baseline scenes, matched gameplay-camera
images and the annotated review. The elevated Sanctuary beacon is intentionally
above ground and produces an expected landmark warning.

```powershell
python eloria-assets/tools/four_gates/test_geometry.py
```

Native regressions cover outward winding, ground normals, complete material
quads and noncollapsed box/cylinder UVs.
