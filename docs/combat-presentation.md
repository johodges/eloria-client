# Combat, spellcasting and archery presentation

Run `godot --path godot-client res://src/dev/combat_showcase.tscn` for an offline,
looping review on production player rigs. Space pauses and R restarts. The
showcase includes channeling, aggressive casting, a defensive ward, healing,
bow draw/hold/release, and alternating sword cuts.

## Animation and event integration

`data/animations/luminous.json` exposes `cast_channel_enter`, `cast_channel`,
`cast_aggressive`, `cast_defensive`, `heal`, `cast_exit`, `ranged_draw`,
`ranged_hold`, `ranged_attack`, `attack_primary`, `attack_secondary`, and `defend`.
The existing `cast` action remains an alias for aggressive casting.

`CombatAnimationLibrary` composes and retimes the existing native skeletal
poses into ten additional clips. Faster releases follow deliberate anticipation,
then recover to idle or combat idle. Channeling and bow hold loop. Draw enters
hold automatically; movement and death can interrupt. Spell result packets
start channeling while choosing a target, then release the appropriate action.
Remote casters use the existing special-effect ids; harvest effects do not
trigger casting. Damage, hit/miss decisions and cast timing remain server-owned.

The importer supplies a bone-rest RESET animation and deterministic blending.
This removes inherited root rotation during crossfades. Cache signatures include
bone rests so differently proportioned rigs do not share an incorrect reset.
Actor command sequences distinguish a new strike from a health/equipment update
that merely restates the previous command.

## Assets and visual effects

The original `amberwood_ranger_bow.glb`, `sunmane_ranger_bow.glb`, and
`ranger_arrow.glb` use faceted yew, leather wrapping, brass collars, antler tips,
a steel broadhead and teal fletching. Regenerate them with:

```sh
python eloria-assets/tools/build_ranger_assets.py
```

The bow grip is at its origin, limbs run along Y, and +Z points toward the
drawing hand. The arrow origin is the nock and its point is at -Z. Bow visuals
64–67 use the two-hand attachment mode; the existing Amberwood and Sunmane
equipment entries 164/165 use the animated bow presentation too. These bows
are outside the one-handed/off-hand visual bank.

Both hands drive the bow: the grip stays in the left palm, the string and arrow
nock follow the right fingers, limbs flex under tension and the string recoils
on release. Props load lazily. Projectile flight uses the same arrow mesh from
the nock, with a shallow arc, distance-dependent duration, and a tapered trail.
Ground shots land near the surface rather than at chest height.

Action effects follow animation time and posed hands. Sword trails follow the
actual equipped blade. Healing uses rising green/gold motes, wards use thin blue
seals, and offensive spells use hand sparks and contrasting impact particles.
World effects distinguish healing, wards, poison and offensive impacts using the
server's current effect mapping. Effects are world-depth-tested, cast no shadows,
and respect Graphics → particles; bow geometry remains visible when effects are
disabled. No additional textures or third-party assets are required.

## Verification

```sh
godot --headless --path godot-client --script res://tests/test_combat_presentation.gd
godot --headless --path godot-client --script res://tests/test_animation_looping.gd
godot --headless --path godot-client --script res://tests/test_animation_gate.gd
python godot-client/tests/test_held_props.py -v
godot --path godot-client --rendering-method gl_compatibility --script res://tests/integration/rendered_combat_showcase.gd
godot --path godot-client --rendering-method gl_compatibility --script res://tests/integration/rendered_world_effects.gd
```

The combat test exercises all 16 creation rigs, transition recovery, interruption,
full-draw arrow clearance, bow alignment after crossfades, nock attachment,
command replay, spell-result and aim packets, and grounded projectile endpoints.
The showcase capture writes `godot-client/test-artifacts/combat/combat-showcase.png`.
The existing world-effects integration exercises the production main scene and
real reduced packet fixtures. CI runs the new headless combat test.

Local validation also found an existing failure in `test_protocol.gd`: its
locomotion assertion requires walk/run facing offsets above 15 degrees while
the existing checked-in map sets both to zero. This change preserves those
locomotion settings.
