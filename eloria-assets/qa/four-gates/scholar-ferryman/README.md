# Four Gates scholar and ferryman comparison pass

This milestone separates the Luminous scholar and ferryman from the shared
humanoid silhouette before the remaining civic cast is converted.

| Actor types | Role | Runtime budget | Distinct equipment |
| --- | --- | --- | --- |
| 303, 310 | Ferryman | 2,834 vertices / 5,300 faces | hood, layered travel robe, shoulder wrap, double belt, two bags, pole and modeled lantern |
| 304, 311 | Scholar | 3,138 vertices / 5,528 faces | split robes, mantle, scroll case, pouches, open book and cyan focus |

Both roles use dedicated idle animation paths. The scholar holds and reads the
book; the ferryman steadies the lantern pole. Existing actor and bone IDs are
unchanged. The PNG files in this directory are topology diagnostics, not a
substitute for the required in-client comparison capture.

Validation commands:

```bash
python3 eloria-assets/tools/generate_all_assets.py --dry-run --jobs 4 build/eloria-data
python3 eloria-assets/tools/generate_all_assets.py --jobs 4 build/eloria-data
python3 eloria-assets/tools/check_provenance.py
python3 eloria-assets/tools/validate_generated_assets.py build/eloria-data
```
