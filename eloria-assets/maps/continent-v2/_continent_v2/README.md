# Continent v2 plan

`continent-v2-plan.json` is the macro plan of continent v2, rebuilt from the Meshy model at 8,000 m east-west. It holds the frame, the vertical curve, the source digests, the territories (the island group's three maps so far: `sw_isle`, `tollholms` and `gull_skerries`), their seams, the owner-approved routes and decks (with the territory each stretch lies in), the island water, the landmarks and the owner's decisions.

Nothing in the twelve-territory pipeline reads it: `landscape.py`, `ownership_contract.py` and the editor hard-code `nymara-regions/_continent/diagonal-plan.json`. It is written by `godot-client/tools/bootstrap_continent_v2_territory.py`.
