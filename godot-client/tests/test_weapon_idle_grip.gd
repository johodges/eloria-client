extends SceneTree
## A held weapon has two grips: the registry socket, the fist every swing and
## the combat idle close round it, and an idle socket the standing idle lays it
## down along the leg in (or stands it upright beside it). WeaponCarryPose
## blends between them by action, over the crossfade the clip itself was given;
## walking and running keep pointing it ahead, turning the wrist no further
## than that needs.

var failures := 0
var checks := 0
## Vertices of each held piece's meshes, in the piece's own space, by scene.
var _vertices := {}

func _init() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func run() -> void:
	var models: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/models.json"))
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/equipment.json"))
	_check_registry(equipment)
	var adapter := CoordinateAdapter.new({"walkingHeight": 0.0})
	var first := true
	for option: Dictionary in models.creationOptions:
		var model: Dictionary = models.models[option.model]
		var animations: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(model.animationMap))
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var errors := actor.configure({"actor_id": 902, "x": 0, "y": 0, "rotation": 0,
			"appearance": {}, "equipment_visuals": {0: 114, 1: 160}}, adapter, model, animations, equipment)
		check(errors.is_empty(), "%s: %s" % [option.model, errors])
		actor.set_physics_process(false)
		actor.animation_player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		var name := str(option.model)
		var carry := actor._weapon_carry
		check(carry != null and carry.active, name + ": a held weapon enables the grip blend")
		var props := _props(actor)
		check(props.size() == 2, name + ": both hands hold a weapon")

		# Standing: both weapons already in their idle grip, with no swing in.
		check(is_equal_approx(float(carry.get("_idle_weight")), 1.0), name + ": an actor arrives at ease")
		for prop: Node3D in props:
			check(prop.has_meta(&"idle_grip") and prop.has_meta(&"fighting_grip"),
				name + ": a sword carries both grips")
			check(prop.transform.is_equal_approx(prop.get_meta(&"idle_grip")),
				name + ": idle holds the sword in its idle grip")
		# Every weapon closes the same fist; a sword is held there by its
		# origin, so its fighting grip names the fist of each hand.
		var fists: Array[Vector3] = []
		for prop: Node3D in props:
			fists.append((prop.get_meta(&"fighting_grip") as Transform3D).origin)
		await _settle(actor)
		# The open hand of the idle hangs palm to the thigh -- which is also
		# what tells _palm which way each hand bone's X runs.
		for part: int in [0, 1]:
			var palm := _palm(actor, part)
			check(palm.x * (1.0 if part == 0 else -1.0) < -0.7,
				"%s: hand %d idles palm to the thigh (%s)" % [name, part, palm])
		# Laid down along the leg on each side, the flat to it, the tip a
		# little ahead -- and the off hand the mirror image of the sword hand,
		# not swung away from the thigh the idle rests that hand on.
		var blades: Array[Vector3] = []
		for part: int in [0, 1]:
			var blade := _actor_direction(actor, props[part].global_basis.y)
			var flat := _actor_direction(actor, props[part].global_basis.z)
			var outward := blade.x if part == 0 else -blade.x
			blades.append(blade)
			check(blade.y < -0.9, "%s: hand %d hangs its blade down (%s)" % [name, part, blade])
			check(blade.z < 0.0 and outward > -0.05,
				"%s: hand %d leans its tip ahead and out from the leg, not across it (%s)" % [name, part, blade])
			check(absf(flat.x) > 0.8, "%s: hand %d lays the flat to the leg (%s)" % [name, part, flat])
		var mirrored := Vector3(-blades[0].x, blades[0].y, blades[0].z)
		check(rad_to_deg(blades[1].angle_to(mirrored)) < 8.0,
			"%s: the off-hand sword hangs the mirror image of the other (%.1f degrees apart)"
				% [name, rad_to_deg(blades[1].angle_to(mirrored))])
		_check_arm_held_out(actor, carry, equipment, name)

		# Squaring up blends to the fighting grip over the clip's own
		# crossfade, turning about the fist so the hilt never leaves the hand.
		actor.play_action(&"combat_idle")
		check(is_equal_approx(actor.action_crossfade_seconds, actor.action_blend_seconds),
			name + ": the combat idle fades in over the action blend")
		actor.animation_player.advance(0.01)
		carry.call("_process_modification_with_delta", actor.action_crossfade_seconds * 0.5)
		check(is_equal_approx(float(carry.get("_idle_weight")), 0.5),
			name + ": the grip eases out over the crossfade")
		for part: int in [0, 1]:
			_check_half_way(props[part], fists[part], "%s: sword in hand %d" % [name, part])
		_step(actor, carry, actor.action_crossfade_seconds)
		for action: StringName in [&"combat_idle", &"attack_primary", &"attack_secondary", &"cast_aggressive"]:
			actor.play_action(action, true)
			_step(actor, carry, 1.0 / 120.0)
			check(is_zero_approx(float(carry.get("_idle_weight"))), name + ": fights in the fist: " + action)
			for prop: Node3D in props:
				check(prop.transform.is_equal_approx(prop.get_meta(&"fighting_grip")),
					"%s: %s holds the fighting grip" % [name, action])
		for action: StringName in [&"turn", &"idle"]:
			actor.play_action(action, true)
			_step(actor, carry, 1.0 / 120.0)
			for prop: Node3D in props:
				check(prop.transform.is_equal_approx(prop.get_meta(&"idle_grip")),
					"%s: %s lays the sword back in the idle grip" % [name, action])

		await _check_first_swing(actor, carry, name)
		await _check_emotes(actor, carry, name)

		# A sword is held at its origin in both grips, so only a turn shows
		# between them. The quarterstaff is fought with a hand's width up from
		# its origin and planted held near its middle: half way, the fist is
		# half way along the slide between the two holds, still on the staff.
		actor.apply_equipment_visuals({0: 163})
		var staff: Node3D = _props(actor)[0]
		check(staff.transform.is_equal_approx(staff.get_meta(&"idle_grip")),
			name + ": a staff taken up at ease is planted")
		actor.play_action(&"combat_idle")
		actor.animation_player.advance(0.01)
		carry.call("_process_modification_with_delta", actor.action_crossfade_seconds * 0.5)
		_check_half_way(staff, fists[0], name + ": quarterstaff", 0.05)
		actor.play_action(&"idle", true)
		_step(actor, carry, 0.2)
		await _check_planted(actor, staff, fists[0], name + ": quarterstaff")
		# Back from a swing, it is set down once the idle has the hand back
		# where it holds it, not while the recovery is still bringing it there.
		actor.play_action(&"attack_primary", true)
		_step(actor, carry, actor.animation_player.current_animation_length + 0.05)
		check(actor.current_action == &"idle", name + ": the swing hands back to the idle")
		_step(actor, carry, 0.3)
		await _check_planted(actor, staff, fists[0], name + ": quarterstaff after a swing")
		await _check_drawn_at_spawn(model, animations, equipment, adapter, name)

		# A weapon taken up while another is held joins the blend where it
		# stands: half way into a stride, the spear that replaces the sword
		# is half way between its grips too, and the off-hand sword kept.
		actor.apply_equipment_visuals({0: 114, 1: 160})
		actor.play_action(&"walk")
		actor.animation_player.advance(0.01)
		carry.call("_process_modification_with_delta", actor.action_crossfade_seconds * 0.5)
		check(is_equal_approx(float(carry.get("_idle_weight")), 0.5), name + ": a stride eases the grip out")
		actor.apply_equipment_visuals({0: 134, 1: 160})
		check(is_equal_approx(float(carry.get("_idle_weight")), 0.5),
			name + ": changing weapons keeps the blend where it was")
		var swapped := _props(actor)
		_check_half_way(swapped[0], fists[0], name + ": spear taken up mid-stride", 0.05)
		_check_half_way(swapped[1], fists[1], name + ": off-hand sword kept mid-stride")
		_step(actor, carry, actor.action_crossfade_seconds)
		check(swapped[0].transform.is_equal_approx(swapped[0].get_meta(&"fighting_grip")),
			name + ": the spear finishes the blend in its fighting grip")

		# Into empty hands a weapon is drawn in the grip of the moment.
		actor.apply_equipment_visuals({})
		actor.apply_equipment_visuals({0: 115})
		var drawn: Node3D = _props(actor)[0]
		check(drawn.transform.is_equal_approx(drawn.get_meta(&"fighting_grip")),
			name + ": a weapon drawn while walking is not snapped to the idle grip")
		actor.play_action(&"idle", true)
		actor.animation_player.advance(0.01)
		actor.apply_equipment_visuals({})
		actor.apply_equipment_visuals({0: 115})
		drawn = _props(actor)[0]
		check(drawn.transform.is_equal_approx(drawn.get_meta(&"idle_grip")),
			name + ": a weapon drawn while standing is drawn at ease")

		# Walking and running still aim the weapon ahead through the fighting
		# grip, exactly as before the idle grip existed -- by turning each
		# wrist only as far as that takes, so the hand hangs as the stride has
		# it: never palm down with the fingers laid out flat over the hilt.
		actor.apply_equipment_visuals({0: 114, 1: 160})
		props = _props(actor)
		for action: StringName in [&"walk", &"run"]:
			actor.play_action(action, true)
			actor._advance_facing_offset(1.0)
			_step(actor, carry, 1.0 / 120.0)
			check(is_equal_approx(float(carry.get("_weight")), 1.0) and
				is_zero_approx(float(carry.get("_idle_weight"))), name + ": " + action + " carries in the fist")
			for phase: float in [0.0, 0.25, 0.5, 0.75]:
				actor.animation_player.seek(actor.animation_player.current_animation_length * phase, true)
				await _settle(actor)
				for part: int in [0, 1]:
					_check_carried_hand(actor, props[part], part, fists[part],
						"%s %s %.2f: hand %d" % [name, action, phase, part])

		await _check_paused(actor, carry, name)

		# A shield keeps its own socket, and the ranged bow, whose registry
		# prop is hidden behind the drawn one, has no idle grip at all.
		actor.apply_equipment_visuals({0: 114, 1: 106})
		check((carry.get("_hands") as Array).size() == 1, name + ": a shield is not blended")
		var shield: Node3D = (actor._equipment_nodes[1][0] as Node).get_child(0)
		check(not shield.has_meta(&"idle_grip"), name + ": a shield has no idle grip")
		actor.apply_equipment_visuals({0: 164})
		var bow: Node3D = (actor._equipment_nodes[0][0] as Node).get_child(0)
		check(not bow.has_meta(&"idle_grip"), name + ": the ranged bow leaves its idle to the bow")
		if first:
			first = false
			await _check_every_idle_socket(actor, equipment, name)
		actor.queue_free()
		await process_frame
	print("weapon idle grip tests: ", ("PASS (%d checks)" % checks) if failures == 0 else "FAIL (%d of %d)" % [failures, checks])
	NativeAnimationImporter.clear()
	quit(0 if failures == 0 else 1)

## Every weapon a hand can hold has an idle grip on the same bone as its
## fighting grip, except the bows whose ranged presentation stands in for them;
## a planted or leant one says so, and only an off-hand one holds its arm out.
func _check_registry(equipment: Dictionary) -> void:
	var checked := 0
	for key: String in equipment.models:
		var model: Dictionary = equipment.models[key]
		var part := int(key.get_slice(":", 0))
		var visual := int(key.get_slice(":", 1))
		if model.get("attach", "") != "socket" or part > 1 or (part == 1 and visual < 160):
			continue
		var socket: Dictionary = model.get("socket", {})
		if model.has("rangedAnimationScene"):
			check(not model.has("idleSocket"), key + ": a ranged bow has no idle grip")
			continue
		var idle: Dictionary = model.get("idleSocket", {})
		check(not idle.is_empty(), key + " has an idle grip")
		check(str(idle.get("bone", "")) == str(socket.get("bone", "")) and
			str(socket.get("bone", "")) == ("hand_r" if part == 0 else "hand_l"),
			key + " holds both grips in the same hand")
		check(str(idle.get("style", "")) in ["hang", "lean", "plant", "upright", "bow"],
			key + " says how it rests (%s)" % idle.get("style", ""))
		var spread := float(idle.get("armSpread", 0.0))
		check(spread >= 0.0 and spread <= 12.0 and (part == 1 or spread == 0.0),
			key + " holds its arm out only in the off hand, and not far (%.1f)" % spread)
		checked += 1
	check(checked > 100, "every held weapon was checked (%d)" % checked)

## Holding a weapon in the off hand, the idle's arm is held out from the
## thigh the clip rests that hand on, by the spread its idle socket names:
## turned at the shoulder, the hand carried out with it.
func _check_arm_held_out(actor: ReplicatedActor3D, carry: SkeletonModifier3D,
		equipment: Dictionary, name: String) -> void:
	var spread := float((equipment.models["1:160"].get("idleSocket", {}) as Dictionary).get("armSpread", 0.0))
	var skeleton := actor.get_skeleton()
	var shoulder := skeleton.find_bone("upperarm_l")
	var hand := skeleton.find_bone("hand_l")
	actor.animation_player.advance(0.0)
	var at := skeleton.get_bone_global_pose(shoulder).origin
	var hung := skeleton.get_bone_global_pose(hand).origin - at
	var right := skeleton.get_bone_global_pose(skeleton.find_bone("upperarm_r")).origin
	carry.call("_process_modification_with_delta", 0.0)
	var held := skeleton.get_bone_global_pose(hand).origin - at
	check(absf(rad_to_deg(hung.angle_to(held)) - spread) < 0.5,
		"%s: the off hand's arm is held %.1f degrees out at ease (%.1f)" % [name, spread, rad_to_deg(hung.angle_to(held))])
	var out := at - right
	out.y = 0.0
	check(spread == 0.0 or held.dot(out.normalized()) > hung.dot(out.normalized()) + 0.01,
		name + ": held out away from the body, not across it")

## A swing restarted from idle - every fresh strike - has no crossfade, and the
## weapon is in the fist from its first frame; a swing that does fade in takes
## the fist over that fade, not over the longer action blend.
func _check_first_swing(actor: ReplicatedActor3D, carry: SkeletonModifier3D, name: String) -> void:
	var props := _props(actor)
	for action: StringName in [&"attack_primary", &"attack_secondary", &"pain"]:
		actor.play_action(&"idle", true)
		_step(actor, carry, 0.2)
		check(is_equal_approx(float(carry.get("_idle_weight")), 1.0), name + ": at ease before " + action)
		actor.play_action(action, true)
		check(is_zero_approx(actor.action_crossfade_seconds), name + ": a restarted " + action + " does not fade in")
		_step(actor, carry, 1.0 / 120.0)
		check(is_zero_approx(float(carry.get("_idle_weight"))),
			name + ": " + action + " from idle is in the fist on its first frame")
		for prop: Node3D in props:
			check(prop.transform.is_equal_approx(prop.get_meta(&"fighting_grip")),
				"%s: %s from idle swings from the fighting grip, not the resting one" % [name, action])
	actor.play_action(&"idle", true)
	_step(actor, carry, 0.2)
	actor.play_action(&"attack_primary")
	var fade := actor.action_crossfade_seconds
	check(fade > 0.0 and fade < actor.action_blend_seconds,
		"%s: a swing that fades in fades in faster than the action blend (%.3f)" % [name, fade])
	_step(actor, carry, fade * 0.5)
	check(absf(float(carry.get("_idle_weight")) - 0.5) < 0.02, name + ": the grip follows the swing's own crossfade")
	_step(actor, carry, fade * 0.5)
	check(is_zero_approx(float(carry.get("_idle_weight"))), name + ": and is in the fist when it ends")
	actor.play_action(&"idle", true)
	_step(actor, carry, 0.2)

## The idles and emotes that keep the hand hanging where the idle has it hold
## the weapon at ease too: a nod no longer lifts a hanging sword into a lance.
## And a reel that drops the hand lower than the idle ever does lifts the
## blade about the fist rather than putting it through the floor.
func _check_emotes(actor: ReplicatedActor3D, carry: SkeletonModifier3D, name: String) -> void:
	var props := _props(actor)
	var at_ease := actor.resolver.at_ease_actions
	for action: StringName in [&"alternate_idle", &"emote_agree", &"emote_nod", &"emote_reel"]:
		check(at_ease.has(String(action)), name + ": " + action + " is at ease in the action map")
		actor.play_action(action)
		_step(actor, carry, actor.action_crossfade_seconds + 0.02)
		check(is_equal_approx(float(carry.get("_idle_weight")), 1.0), name + ": " + action + " holds the weapon at ease")
		var length := actor.animation_player.current_animation_length
		for phase: float in [0.15, 0.45, 0.75]:
			actor.animation_player.seek(length * phase, true)
			await _settle(actor)
			var blade := _actor_direction(actor, props[0].global_basis.y)
			check(blade.y < -0.5 and blade.dot(Vector3.FORWARD) < 0.8,
				"%s %s %.2f: the sword hangs, not pointed ahead like a lance (%s)" % [name, action, phase, blade])
			for prop: Node3D in props:
				check(_lowest(actor, prop) > -0.003,
					"%s %s %.2f: kept out of the floor (%.3f)" % [name, action, phase, _lowest(actor, prop)])
	actor.play_action(&"emote_cheer")
	_step(actor, carry, actor.action_crossfade_seconds + 0.02)
	check(is_zero_approx(float(carry.get("_idle_weight"))), name + ": a cheer closes the fist")
	actor.play_action(&"idle", true)
	_step(actor, carry, 0.2)

## A planted piece keeps its butt where it was set down through the whole
## idle loop, the haft turning about it to follow the fist and sliding through
## the hand: the wrist's few degrees of sway are no longer levered down the
## length of the haft into a butt that skates across the floor.
func _check_planted(actor: ReplicatedActor3D, prop: Node3D, fist_in_hand: Vector3,
		label: String) -> void:
	await _settle(actor)
	var bounds := _bounds(prop)
	var butts: Array[Vector3] = []
	var fists: Array[Vector3] = []
	var length := actor.animation_player.current_animation_length
	for phase: float in [0.0, 0.2, 0.4, 0.6, 0.8]:
		actor.animation_player.seek(length * phase, true)
		await _settle(actor)
		var to_actor := actor.global_transform.affine_inverse() * prop.global_transform
		var low := to_actor * Vector3(0.0, bounds.position.y, 0.0)
		var high := to_actor * Vector3(0.0, bounds.end.y, 0.0)
		butts.append(low if low.y < high.y else high)
		var hand := actor.global_transform.affine_inverse() * (prop.get_parent() as Node3D).global_transform
		var fist := hand * fist_in_hand
		fists.append(fist)
		var axis := (high - low).normalized()
		var off := (fist - low) - axis * axis.dot(fist - low)
		check(off.length() < 0.012, "%s %.1f: the fist stays on the haft (%.4f m off)" % [label, phase, off.length()])
	var slid := 0.0
	var swayed := 0.0
	for index: int in butts.size():
		slid = maxf(slid, butts[index].distance_to(butts[0]))
		swayed = maxf(swayed, fists[index].distance_to(fists[0]))
	check(slid < 0.003, "%s: the butt stays where it was set down (%.4f m)" % [label, slid])
	check(swayed > slid, "%s: while the fist moves with the idle (%.4f m)" % [label, swayed])
	check(butts[0].y > -0.003 and butts[0].y < 0.04, "%s: stood on the floor (%.3f)" % [label, butts[0].y])

## A planted or leant piece an actor is built holding is set down where the
## idle puts it, not where the first frames find the hand: a new actor can be
## blended before its clip has posed it, and a staff set down then stood on a
## point at shoulder height.
func _check_drawn_at_spawn(model: Dictionary, animations: Dictionary, equipment: Dictionary,
		adapter: CoordinateAdapter, name: String) -> void:
	for visual: int in [163, 144]:
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		actor.configure({"actor_id": 903, "x": 0, "y": 0, "rotation": 0,
			"appearance": {}, "equipment_visuals": {0: visual}}, adapter, model, animations, equipment)
		actor.set_physics_process(false)
		await create_timer(0.4).timeout
		var prop: Node3D = _props(actor)[0]
		var bounds := _bounds(prop)
		var to_actor := actor.global_transform.affine_inverse() * prop.global_transform
		var low := to_actor * Vector3(0.0, bounds.position.y, 0.0)
		var high := to_actor * Vector3(0.0, bounds.end.y, 0.0)
		var floor_end := low if low.y < high.y else high
		var other_end := high if low.y < high.y else low
		var rise := (other_end - floor_end).normalized().y
		var lowest := _lowest(actor, prop)
		check(lowest > -0.003 and lowest < 0.04,
			"%s 0:%d: built holding it, it rests its end on the floor (%.3f)" % [name, visual, lowest])
		check(rise > (0.9 if visual == 163 else 0.3) and rise < (1.01 if visual == 163 else 0.95),
			"%s 0:%d: stood (or leant) the way the idle holds it (%.2f)" % [name, visual, rise])
		actor.queue_free()
		await process_frame

## Off screen nothing is blended. An actor whose action changed meanwhile comes
## back in the grip the new action asks for at once, rather than seen easing
## into it late.
func _check_paused(actor: ReplicatedActor3D, carry: SkeletonModifier3D, name: String) -> void:
	actor.apply_equipment_visuals({0: 114, 1: 160})
	var props := _props(actor)
	actor.play_action(&"idle", true)
	_step(actor, carry, 0.2)
	var gate := AnimationGate.new()
	actor.set_animation_tier(AnimationGate.Tier.PAUSED, gate)
	check(not carry.active, name + ": a paused actor does not blend its grip")
	var before := props[0].transform
	actor.play_action(&"combat_idle")
	await process_frame
	await process_frame
	check(props[0].transform.is_equal_approx(before), name + ": paused grips stay put")
	actor.set_animation_tier(AnimationGate.Tier.FULL, gate)
	check(carry.active, name + ": the blend resumes on screen")
	check(is_zero_approx(float(carry.get("_idle_weight"))), name + ": back on screen in the new action's grip")
	for prop: Node3D in props:
		check(prop.transform.is_equal_approx(prop.get_meta(&"fighting_grip")),
			name + ": without easing across from where it was left")
	actor.play_action(&"idle", true)
	_step(actor, carry, 0.2)

## Every idle socket in the registry, on one body, at three points of the idle:
## nothing at ease goes into the floor, and a planted piece stands on it.
func _check_every_idle_socket(actor: ReplicatedActor3D, equipment: Dictionary, name: String) -> void:
	var checked := 0
	for key: String in equipment.models:
		var model: Dictionary = equipment.models[key]
		if not model.has("idleSocket"):
			continue
		var part := int(key.get_slice(":", 0))
		var visual := int(key.get_slice(":", 1))
		actor.apply_equipment_visuals({part: visual})
		actor.play_action(&"idle", true)
		var props := _props(actor)
		if props.is_empty():
			check(false, "%s: %s draws nothing" % [name, key])
			continue
		var prop := props[0]
		var style := str((model.idleSocket as Dictionary).get("style", ""))
		var length := actor.animation_player.current_animation_length
		for phase: float in [0.0, 1.0 / 3.0, 2.0 / 3.0]:
			actor.animation_player.seek(length * phase, true)
			await _settle(actor)
			var lowest := _lowest(actor, prop)
			check(lowest > -0.003, "%s %s %s %.2f: at ease clear of the floor (%.3f)" % [name, key, style, phase, lowest])
			if style == "plant":
				check(lowest < 0.05, "%s %s %.2f: planted on the floor (%.3f)" % [name, key, phase, lowest])
		checked += 1
	check(checked > 100, "%s: every idle socket was stood in (%d)" % [name, checked])
	actor.apply_equipment_visuals({0: 114, 1: 160})

## Half way between its grips a piece is turned half way from one to the
## other, and the fist still closes on its length, at a point between where
## each grip holds it. `slide` is the least the two holds must differ by, in
## metres, for a piece whose blend has to slide it through the hand.
func _check_half_way(prop: Node3D, fist: Vector3, label: String, slide := 0.0) -> void:
	var fighting: Transform3D = prop.get_meta(&"fighting_grip")
	var idle: Transform3D = prop.get_meta(&"idle_grip")
	var size := fighting.basis.get_scale().x
	var turned := prop.transform.basis.get_rotation_quaternion()
	var from := fighting.basis.get_rotation_quaternion()
	var to := idle.basis.get_rotation_quaternion()
	var whole := from.angle_to(to)
	check(absf(turned.angle_to(from) - whole * 0.5) < 0.01 and absf(turned.angle_to(to) - whole * 0.5) < 0.01,
		"%s: half way, it is turned half way between its grips" % label)
	var held := prop.transform.affine_inverse() * fist
	var off := Vector2(held.x, held.z).length() * size
	check(off < 0.005, "%s: half way, the fist still closes on its length (%.4f m off)" % [label, off])
	var fighting_hold := (fighting.affine_inverse() * fist).y
	var idle_hold := (idle.affine_inverse() * fist).y
	check(held.y >= minf(fighting_hold, idle_hold) - 0.001 and held.y <= maxf(fighting_hold, idle_hold) + 0.001,
		"%s: half way, the fist is between its two holds (%.3f in %.3f..%.3f)" % [label, held.y, fighting_hold, idle_hold])
	check(absf(idle_hold - fighting_hold) * size >= slide,
		"%s: the two grips hold it %.3f m apart" % [label, absf(idle_hold - fighting_hold) * size])

## A hand carrying its weapon through a stride: the piece points ahead in its
## fighting grip, the wrist has turned only as far as that takes -- no twist
## about the piece's length -- and so the hand still hangs the way the clip
## swings it, not palm down with the fingers flat out to the side, with the
## piece's length through the fist.
func _check_carried_hand(actor: ReplicatedActor3D, prop: Node3D, part: int, fist: Vector3,
		label: String) -> void:
	check(prop.transform.is_equal_approx(prop.get_meta(&"fighting_grip")), label + " is in its fighting grip")
	var forward := -actor.global_basis.z.normalized()
	check(prop.global_basis.y.normalized().dot(forward) > 0.98, label + " points forward")
	var palm := _palm(actor, part)
	check(palm.y > -0.5, "%s does not turn its palm to the floor (%s)" % [label, palm])
	var hand := (prop.get_parent() as Node3D).global_basis
	var fingers := _actor_direction(actor, hand.y)
	var outward := fingers.x if part == 0 else -fingers.x
	check(not (absf(fingers.y) < 0.5 and outward > 0.5),
		"%s does not lay its fingers out flat to the side (%s)" % [label, fingers])
	# The skeleton has put the clip's own pose back by now; the attachment
	# keeps the wrist the carry turned.
	var skeleton := actor.get_skeleton()
	var bone := skeleton.find_bone("hand_r" if part == 0 else "hand_l")
	var animated := (skeleton.global_basis * skeleton.get_bone_global_pose(bone).basis).orthonormalized()
	var turn := animated.get_rotation_quaternion().angle_to(hand.orthonormalized().get_rotation_quaternion())
	var swing := (animated * prop.transform.basis.orthonormalized() * Vector3.UP).angle_to(prop.global_basis.y)
	check(absf(turn - swing) < deg_to_rad(1.0),
		"%s turns the wrist no further than the blade needs (%.1f for %.1f degrees)" % [label, rad_to_deg(turn), rad_to_deg(swing)])
	var held := prop.transform.affine_inverse() * fist
	check(Vector2(held.x, held.z).length() * prop.transform.basis.get_scale().x < 0.02,
		label + " keeps the fist on the hilt")

## Which way the palm of a hand faces, in actor space. The hand bones are
## mirror images: X leaves the back of the right hand and the palm of the
## left (import_generated_weapons._mirror). The idle check above holds this
## to the clip, which hangs both hands palm to the thigh.
func _palm(actor: ReplicatedActor3D, part: int) -> Vector3:
	var skeleton := actor.get_skeleton()
	var basis := skeleton.global_basis * skeleton.get_bone_global_pose(
		skeleton.find_bone("hand_r" if part == 0 else "hand_l")).basis
	for attachment: Node in actor._equipment_nodes.get(part, []):
		if attachment is BoneAttachment3D:
			basis = (attachment as Node3D).global_basis
	return _actor_direction(actor, basis.x) * (-1.0 if part == 0 else 1.0)

func _props(actor: ReplicatedActor3D) -> Array[Node3D]:
	var props: Array[Node3D] = []
	for part: int in [0, 1]:
		for attachment: Node in actor._equipment_nodes.get(part, []):
			if attachment is BoneAttachment3D and attachment.get_child_count() > 0:
				props.append(attachment.get_child(0) as Node3D)
	return props

## Runs the clip and the grip blend forward together, a frame at a time, the
## way the skeleton steps them: the clip's pose first, then the modifier.
func _step(actor: ReplicatedActor3D, carry: SkeletonModifier3D, seconds: float) -> void:
	var frames := maxi(1, ceili(seconds * 120.0 - 0.001))
	for frame: int in frames:
		actor.animation_player.advance(seconds / frames)
		carry.call("_process_modification_with_delta", seconds / frames)

## Lets the skeleton and its attachments catch up with the pose.
func _settle(actor: ReplicatedActor3D) -> void:
	actor.animation_player.advance(0.0)
	await process_frame
	await process_frame

func _actor_direction(actor: ReplicatedActor3D, direction: Vector3) -> Vector3:
	return (actor.global_basis.orthonormalized().inverse() * direction).normalized()

## The box a held piece's meshes fill, in its own space.
func _bounds(prop: Node3D) -> AABB:
	var bounds := AABB()
	var first := true
	for node: Node in prop.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		var box := (prop.global_transform.affine_inverse() * mesh.global_transform) * mesh.get_aabb()
		bounds = box if first else bounds.merge(box)
		first = false
	return bounds

## The height of a held piece's lowest vertex above the actor's floor.
func _lowest(actor: ReplicatedActor3D, prop: Node3D) -> float:
	var lowest := INF
	var to_actor := actor.global_transform.affine_inverse()
	for node: Node in prop.find_children("*", "MeshInstance3D", true, false):
		var mesh := node as MeshInstance3D
		if mesh.mesh == null:
			continue
		var key := mesh.mesh.get_instance_id()
		if not _vertices.has(key):
			var points := PackedVector3Array()
			for surface: int in mesh.mesh.get_surface_count():
				points.append_array(mesh.mesh.surface_get_arrays(surface)[Mesh.ARRAY_VERTEX])
			_vertices[key] = points
		var placed := to_actor * mesh.global_transform
		for vertex: Vector3 in (_vertices[key] as PackedVector3Array):
			lowest = minf(lowest, (placed * vertex).y)
	return lowest
