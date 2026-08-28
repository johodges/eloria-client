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

## The generic tier

The protocol's appearance bytes carry the original wearable ids, and the
craftable economy is built almost entirely on them: 168 of the 388
manufacturing outputs are wearable or wieldable. Only the culture pieces had
geometry, so an iron sword or a pair of leather boots drew nothing at all.
`client_serv.h` defines 160 wearable and wieldable ids; the generic tier claims
155 of them across seven parts. The five unmapped ids are the `*_NONE`
sentinels — `WEAPON_NONE`, `SHIELD_NONE`, `CAPE_NONE`, `HELMET_NONE` and
`NECK_NONE` — which mean "wearing nothing" and must stay unmapped.

One authored mesh serves a whole material ladder. A model entry carries a
`tint` — base, trim and detail as RGB — that the runtime applies to the shared
scene, so iron, steel, titanium and bronze helms are one GLB under four tints.
That is 43 meshes for 155 ids rather than 155 assets. The runtime picks the tint
slot from the material's name suffix (`Base`, `Trim`, `Detail`) rather than the
surface index, because a piece that uses no trim geometry would otherwise shift
its detail colour onto the trim.

`GENERIC_EQUIPMENT` in `equipment_authoring.py` is the catalogue: one
`GenericPiece` per mesh, listing the legacy ids it serves with a name and a
colour pair each. `IRON`/`STEEL`/`TITANIUM`/`BRONZE`/`WOOD`/`LEATHER`/`FUR` and
the `DYES` table are shared, so a steel helm and steel greaves read as the same
alloy.

### Aliases and NPC looks

The registry previously aliased weapon 11, shield 5 and cape 11 to Four Gates
guard gear, because the legacy tier had no models. Those ids are `STAFF_4`,
`SHIELD_BRONZE` and `CAPE_GOLD`; with the generic tier authored, an alias would
hijack three ids any actor can legitimately wear. The alias table is empty, and
bespoke NPC gear comes from `npcLooks` in `models.json`, which names native ids
and is applied *after* the server's appearance bytes so an authored look wins.

Because parts 4, 5 and 6 now resolve for every legacy value, every actor is
clothed by default — appearance byte 0 is a black shirt, not "no shirt". The
body's own wardrobe surfaces are hidden underneath by `hides`.

## Rebuilding

```sh
python3 eloria-assets/tools/build_native_nymara_glbs.py --only equipment
```

Rewrites the 66 equipment GLBs, the equipment section of
`data/actors/native_asset_catalog.json`, and `data/actors/equipment.json`.
`--only equipment` leaves races, hair and creatures untouched and preserves the
manifest's existing validation set. It writes both tiers: the 66 culture pieces
and the 43 generic meshes.

Adding a piece means one row in `EQUIPMENT` in `build_native_nymara_glbs.py` and
one entry in `EQUIPMENT_FINISH` in `equipment_authoring.py`. A new *kind* also
needs a branch in `prop_geometry` or `garment_geometry`.

## Colour space

Palettes are authored as sRGB byte triples, but glTF defines `baseColorFactor`
and `emissiveFactor` as linear and Godot's importer converts them to sRGB on the
way into `albedo_color`. Writing the bytes raw therefore landed every untextured
surface about forty percent bright — iron plate rendered as near-white.
`srgb_to_linear()` converts on the way out, so an authored byte survives the
round trip unchanged, and a `tint` is passed straight into `albedo_color`
because both ends now mean sRGB.

The equipment and creature libraries carry the fix. The race and hair GLBs do
not yet: they are 41 MB and were left out of this change, so their two
untextured `Integrated Feature` and `Integrated Accent` materials still render
bright. Rebuilding with

```sh
python3 eloria-assets/tools/build_native_nymara_glbs.py
```

picks it up; every other surface on those models is textured with a white
factor and is unaffected either way.

## Checks

* `tests/test_native_glb_assets.py` pins the registry schema, the socket bones,
  the skinned garment set, per-part size envelopes and material coverage.
* `src/dev/model_validation.tscn` dresses each model with a full loadout and
  fails if a socket, a garment, or the fit scale is missing.
