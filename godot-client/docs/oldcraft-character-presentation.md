# Oldcraft-inspired character presentation

This pass translates the readable fantasy shape language of the supplied
World of Oldcraft reference into Eloria's existing assets. It does not copy
Oldcraft meshes, textures, UI sprites, or animation data. The reusable cues
are broad heroic silhouettes, oversized readable extremities, matte painted
surfaces, warm-brass/oxblood entry UI, and a strongly lit live hero preview.

## Runtime character contract

Eloria's canonical player rig remains the source of truth:

- Keep the 77 joint names, order, parent hierarchy, rest transforms, and
  inverse bind poses stable.
- Keep gameplay displacement code-owned. Animation root motion remains off.
- Body, skinned hair, and modular garments must bind to the same canonical
  skeleton. Rigid equipment remains on named sockets.
- Do not author scale tracks into shared animation clips. The presentation
  layer uses persistent bone pose scales for chest, limbs, head, hands, and
  feet; scale animation would fight that layer every frame.
- Retain culture-specific silhouettes. Heavy cultures receive more trunk and
  extremity mass, while tall or spectral cultures keep their long-limbed read.
- Require an explicit player-culture profile before applying pose scales.
  Creatures and other NPC rigs remain untouched even when they reuse names
  such as `Head`, `hand_l`, or `thigh_l`.
- Continue using equipment fit variants where a silhouette cannot be reached
  by a uniform fit. Covered body zones should remain hidden to avoid clipping
  and unnecessary overdraw.

`OldcraftActorStyle` applies this contract once after the native skeleton is
loaded. It never changes the rest rig or inverse binds, so rebound equipment
inherits the same silhouette. Its material pass retains authored texture,
tint, transparency, emission, metal masks, and normal textures while
softening plastic-looking highlights with a roughness floor, restrained
dielectric specular, and a bounded normal-map strength.

## Player-selectable character quality

The existing Graphics Quality setting now also controls actor presentation.
Imported Godot scenes provide generated mesh LOD index chains; the runtime
cache shares those meshes, skins, and materials across actors.

| Setting | Mesh selection | Actor shadows | Remote cape cloth |
| --- | --- | --- | --- |
| Low | LOD transitions at 0.35× authored bias | Off | Off |
| Medium | LOD transitions at 0.65× authored bias | Authored setting | Off |
| High | Authored LOD bias | Authored setting | On |

The local player's cape remains available at every tier. Existing crowd rules
remain in force as well: nearby actors animate at full rate, farther visible
actors update at half rate, off-screen animation pauses, and actors outside the
draw radius are hidden. Changing quality is live and does not re-import or
duplicate actor resources.

Packaged clients include the imported actor `PackedScene` resources as well as
the loose source GLBs needed by animation and raw fallbacks. Packaging now
fails before export if any actor scene is missing its generated-LOD import,
preventing Low or Medium from silently shipping as full-detail geometry.

For future authored assets, use the following review targets rather than
adding more runtime modifiers:

- High: 18–22k body triangles plus 3–4k hair, normal map, local shadows.
- Medium: 8–12k body triangles plus 1–2k hair, 30 Hz distant animation.
- Low: 3–6k silhouette-preserving body, simplified or baked hair, 512–1024
  textures, 10–15 Hz distant animation.
- Prefer one material per visible piece and no more than four visible actor
  submissions on High. A future baked crowd representation can target two on
  Medium and one on Low without changing the gameplay actor contract.

## Entry-screen contract

Login and character creation keep Eloria's identity but use the reference's
visual hierarchy:

- dark carved-stone framing (`#1E1E22` / `#333338`),
- brass edging (`#F4C542` / `#B88A3B`),
- oxblood actions (`#8E1B12`, `#B82B1A` on hover),
- warm text (`#F5F0E0`), and
- a cool moonlit preview with a warm key, teal rim, and stone/brass pedestal.

The login remains lightweight procedural UI over Eloria's existing painted
world image. Character creation uses one original 1920×1080 painted stage, one
512×128 four-icon atlas, one live 3D actor, a stone class rail, and a parchment
form. The SubViewport has a transparent background so the actor reads as part
of the painting instead of inside a black box. No extra actors or animated
scenery are created, and the existing viewport gate disables preview rendering
as soon as character creation is hidden. The two UI textures are not referenced
by gameplay scenes.

## Creation class and starter-item contract

Creation offers four open-ended starting callings: Vanguard (`0`), Ranger
(`1`), Arcanist (`2`), and Warden (`3`). The calling is independent of the
selected race and sex. It grants an initial inventory but never restricts
attributes, skills, equipment, or later progression.

The server-owned starter grants are intentionally light enough to leave room
for tutorial rewards: Vanguard gets a militia sword, round shield, guard cape
and Studded Jack; Ranger gets an Amberwood longbow, 20 arrows and Scout Vest;
Arcanist gets an arcane focus wand, Glowline Coat and three mana potions; and
Warden gets a fighting quarterstaff, Furtrim Coat and leaf cape. The fuller
head-to-toe looks shown in the live preview communicate class silhouette only;
the adjacent text names the items actually granted.

The legacy `CREATE_CHAR` payload keeps its original eight appearance bytes in
the original order. Eloria appends one `class_id` byte after them. Updated
servers validate that byte against their own immutable starter-kit table and
select inventory using only the class id; `actor_type` remains a separate
visual choice. A missing ninth byte defaults to Vanguard, which keeps old
clients valid, and legacy servers ignore the trailing byte.

The client class table owns only presentation: label, description, icon key,
and representative equipment visual ids. The server owns the actual item
names and quantities. Switching race rebuilds the same selected loadout on the
new body. Players can temporarily hide class gear to inspect hair and wardrobe
colours without changing the selected class or the items creation will grant.

## Asset-generation decision

No new generated mesh was required for this pass. The existing canonical
bodies and modular equipment can carry the target silhouette through their
shared rig, so no external generation credits were consumed.
