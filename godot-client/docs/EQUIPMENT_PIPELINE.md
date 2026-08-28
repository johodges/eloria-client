# Equipment pipeline

Added 2026-08-28 for Eloria Client.

## What was wrong

Equipment was authored as small primitive blobs in an arbitrary item space and
attached with `BoneAttachment3D` plus an identity transform. Three consequences
followed from that, all of them visible in game:

* **Bone rest bases are not axis aligned.** `hand_r` rests with its local +Y
  along world −X, so a weapon authored blade-up left the grip pointing
  horizontally out of the actor's side. Every one of the fourteen weapons and
  six shields was affected.
* **Nothing was fitted to the body.** Measured against the 1.85 m rig, helmets
  were 0.92 m across a 0.18 m head and amulets 0.41 m across a 0.09 m neck —
  three to five times body scale.
* **Worn armour could not deform.** A cuirass was a rigid child of `spine_02`
  and leg armour a rigid child of `pelvis`, so neither followed the spine or the
  knees. Boots were parented to the pelvis as a single mesh, which parked a pair
  of boots around the actor's hips.

## How it works now

`eloria-assets/tools/equipment_authoring.py` authors equipment against the rest
pose of the committed rig, so the geometry is fitted to the body the runtime
will actually deform.

**Garments** — capes, leg armour, body armour and boots — are lofted as offset
shells around the *measured* body cross sections (`torso_rings`, `limb_rings`)
and skinned to the same 65 joints as the body. They ship as valid skinned glTF
carrying the shared joint hierarchy.

**Props** — weapons, shields, helmets and neck items — are authored in item
space and placed by a socket expressed in *character* space: `+Y` up, `+Z` the
direction the actor faces. Weapon and shield sockets are solved from the
anatomical fist frame (finger axis, grip axis, palm normal) taken from the rig
itself, and hafts and bow risers are additionally solved in the reference idle
pose, because that is the pose players spend their time looking at.

## Runtime contract

`data/actors/equipment.json` is schema 3:

| Field | Meaning |
|---|---|
| `canonicalHeadRestY` | Head bone rest height the assets were authored against |
| `sockets[part]` | Default `bone`, `offset` and `rotationDegrees` in character space |
| `skinRegions[name]` | Bones a garment of that region may bind to |
| `models[part:visual].attach` | `socket` or `skinned` |
| `models[part:visual].socket` | Optional per-model socket override |
| `models[part:visual].skinRegion` | Region for a skinned garment |

`ReplicatedActor3D` resolves a socket as `bone_rest.affine_inverse() *
placement`, which cancels the bone rest basis so the authored numbers stay
readable while the item still rides the bone once a clip plays. A garment is
rebound by replacing its bind poses with `skeleton.get_bone_global_rest(bone)
.affine_inverse() * fit`, which retargets it onto this actor and applies the rig
fit scale in one step.

`rig_fit_scale()` is the ratio between this rig's Head rest height and
`canonicalHeadRestY`. The female rigs are about 3% shorter than the male ones,
and the fit scale carries a single authored asset across every race and both
body variants. It is a uniform scale, not a retarget: the female rigs are not
an exact scaled copy of the male ones — arm and hand joints deviate by up to a
few centimetres — so a skinned garment sits within roughly one to two
centimetres of the body rather than exactly on it. Socket placement is
unaffected, because each socket resolves against that rig's own bone rest.

Parts also declare `hides`, the actor's own skinned wardrobe surfaces a piece
covers. The shells are lofted with clearance, but a bulkier wardrobe would still
poke through armour worn over it, so those surfaces are switched off while the
piece is worn and reference-counted so overlapping parts unwind cleanly.
Enclosing headwear additionally hides the hairstyle; a circlet does not.

## Rebuilding

```sh
python3 eloria-assets/tools/build_native_nymara_glbs.py --only equipment
```

Rewrites the 66 equipment GLBs, the equipment section of
`data/actors/native_asset_catalog.json`, and `data/actors/equipment.json`.
`--only equipment` leaves races, hair and creatures untouched and preserves the
manifest's existing validation set.

Adding a piece means one row in `EQUIPMENT` in `build_native_nymara_glbs.py` and
one entry in `EQUIPMENT_FINISH` in `equipment_authoring.py`. A new *kind* also
needs a branch in `prop_geometry` or `garment_geometry`.

## Checks

* `tests/test_native_glb_assets.py` pins the registry schema, the socket bones,
  the skinned garment set, per-part size envelopes and material coverage.
* `src/dev/model_validation.tscn` dresses each model with a full loadout and
  fails if a socket, a garment, or the fit scale is missing.
