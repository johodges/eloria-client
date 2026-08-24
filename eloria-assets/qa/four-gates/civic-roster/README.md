# Four Gates civic roster QA

This stage completes the role-specific Luminous NPC silhouettes for Four Gates.
It adds the female official and merchant variants and both-gender scholars,
lake priests, and civilians while preserving actor IDs 300 through 313.

The composite is ordered left-to-right: official F, merchant F, scholar F,
scholar M, lake priest F, lake priest M, civilian F, civilian M. Scholars use
tablet cases and document rolls, priests use mirrored chest medallions and a
two-pronged lake crown, and civilians use utility belts and a side pouch.

```sh
python3 eloria-assets/tools/generate_nymara_complete.py build/eloria-data
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```

All fourteen Luminous actor definitions are now covered by exact-path and
topology-floor validation. Shaded in-client captures remain pending a
GPU-capable client session.
