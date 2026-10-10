# Continent v2 section partition

Active map IDs, exact polygons and ownership priority come from `partition-inputs/sections_spec.json`; the recorded
check report has 33 ordinary shared borders. Ravenhead retains both disjoint ownership rings. All editor bases are
byte crops of the hash-pinned `group-terrain` frozen terrain. Its grid is a data parent outside the active catalog.
The original plan and catalog are pinned under `partition-inputs` with their source commit and file hashes.

Run `python godot-client/tools/bootstrap_continent_v2_territory.py --check` to replay immutable crop/frame/plan checks.
The bootstrap does not reset existing authored scenes and preserves gameplay/authority spec fields. Edit those
scenes normally, then run `python godot-client/tools/continent_v2_territories.py` to validate seams and ownership.
Do not re-run the original Meshy conditioning. Source kit libraries are shared by catalog metadata; placements
remain authored content. Original three source editors/packages are staged historical inputs until migration
removes their physical directories; they have no active catalog references.
