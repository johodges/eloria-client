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

Login and character creation keep Eloria's identity and existing background,
but use the reference's visual hierarchy:

- dark carved-stone framing (`#1E1E22` / `#333338`),
- brass edging (`#F4C542` / `#B88A3B`),
- oxblood actions (`#8E1B12`, `#B82B1A` on hover),
- warm text (`#F5F0E0`), and
- a cool moonlit preview with a warm key, teal rim, and stone/brass pedestal.

The login remains lightweight procedural UI over Eloria's existing painted
world image. Character creation keeps one live 3D actor and a procedural stage;
it does not add extra animated scenery or texture residency to gameplay.

## Asset-generation decision

No new generated mesh was required for this pass. The existing canonical
bodies and modular equipment can carry the target silhouette through their
shared rig, so no external generation credits were consumed.
