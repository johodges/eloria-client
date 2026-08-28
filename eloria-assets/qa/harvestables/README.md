# Harvestable QA

`harvestable-contact-sheet.png` renders every model in the harvestable
catalogue from a fixed three-quarter camera, tinted with each resource's own
material accent, so the roster can be checked for silhouette variety and for
fidelity against the regional landmark kit in one look.

Regenerate after any change to `eloria-assets/tools/harvestables.py`:

```sh
python3 eloria-assets/nymara-packs/nymara-client-assets/generate_nymara_pack.py
python3 eloria-assets/tools/render_harvestable_sheet.py \
  eloria-assets/nymara-packs/nymara-client-assets/runtime \
  --output eloria-assets/qa/harvestables/harvestable-contact-sheet.png
```

The functional checks live in `eloria-assets/tools/validate_harvestables.py`,
which runs as part of the data pack's validation stage. The audit that produced
this layer is `docs/harvestable-audit.md`.
