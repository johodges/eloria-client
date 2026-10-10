# Continent v2 section partition

Active map IDs, exact polygons and ownership priority come from `partition-inputs/sections_spec.json`; the recorded
check report has 33 ordinary shared borders. Ravenhead retains both disjoint ownership rings. All editor bases are
byte crops of the hash-pinned `group-terrain` frozen terrain. Its grid is a data parent outside the active catalog.
The original plan and catalog are pinned under `partition-inputs` with their source commit and file hashes.

Run `python godot-client/tools/bootstrap_continent_v2_territory.py --check` to replay immutable crop/frame/plan checks.
The bootstrap does not reset existing authored scenes and preserves gameplay/authority spec fields. Edit those
scenes normally, then run `python godot-client/tools/continent_v2_territories.py` to validate seams and ownership.
Do not re-run the original Meshy conditioning. Source kit libraries are shared by catalog metadata; placements
remain authored content. Original source scene/content/package directories retire after their saved content and
publication move; the three catalog-declared kit folders remain shared libraries without active source editors.

## Server publication

After all active saved scenes are committed, bake every catalog map and publish its client package from that
exact bake. Export collision, crossings and the other shared publication steps before running `publish_server.py`.
Pass one `--bake MAP_ID=BAKE_DIRECTORY` argument for each active catalog entry, plus `--server`, `--stage m4` and
either `--check` or `--apply`. The publisher validates the catalog/frame/content-table map set dynamically; it has
no fixed fifteen-map list. Apply is followed by check using the same inputs.

The generated server overlay carries per-map rows and map-qualified chapter targets, approaches, NPC posts and
register/ferry objects. `landing.json` retains schema `eloria-landing-v1`: each target and cast post includes `map`,
and register/ferry object descriptors are `{map, id}`. The hub is `landfall`; chapter steps 1-6 occur there, step 7
in Warrenmead, step 9 in Reedfall and step 10 in Greenlight. Runtime isle membership comes from the served manifest.
Retired map saves return home; fresh map IDs have no character position migration.

Three authored default spawn markers are conserved. Twelve additional maps use separately hash-bound generated
arrival metadata, validated by `arrivals.py` against the recorded source/frame/ownership contract. Generated
arrivals are outside gameplay marker arrays and do not increase the authored marker total. Marker rename history
and shared kit identities retain pinned historical source names; active ownership uses the new catalog IDs.

The overlay sits beside certified legacy tables. A runtime change to a certified source such as `world.py` needs
the owner's separate certificate-advance kit; publication does not overwrite the immutable legacy authority.
