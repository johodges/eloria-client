extends SceneTree
## An actor faces the way it travels, on every one of the eight directions.
##
## The rendered actor is deliberately a fraction of a tile behind its
## authoritative position, so its facing is the chord from where it is to the
## tile it is crossing to - not the direction the server's command named. That
## chord is only the travel direction while the lag stays where the arrival
## margin puts it. When the client's idea of the server cadence was longer than
## the server's real one, every step covered less ground than the next one
## added, the lag grew without bound, and the body settled tens of degrees
## round from the way it was walking - which is what this pins.

const STEPS := 6

var _failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(640, 400)
	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("LoginPanel") as Control).hide()
	var app_state: Node = root.get_node("/root/AppState")
	app_state.set("authenticated", true)
	var stage: Node3D = main.get_node(
		"GameView/ViewportContainer/Viewport/WorldRoot") as Node3D
	var models: Dictionary = main.get("models") as Dictionary
	var model_config: Dictionary = models.get("luminous_female", {}) as Dictionary
	var adapter := CoordinateAdapter.new({"metresPerTile": 1.0, "walkingHeight": 0.0,
		"serverOrigin": [0.0, 0.0], "invertServerY": true})
	var actor := ReplicatedActor3D.new()
	stage.add_child(actor)
	var dto: Dictionary = {"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"actor_type": 1, "kind": 1, "name": "T", "appearance": {}, "command": 22}
	_expect(actor.configure(dto, adapter, model_config,
		main.call("_animation_for_model", model_config), {}).is_empty(),
		"the actor builds without errors")
	actor.apply_server_state(dto, adapter, true)

	# The server's walking pace, per tile. The client assumes it until it has
	# measured one, and its own default has to agree or the actor never catches
	# up. A diagonal step crosses 1.41 tiles and the server holds it for 1.41
	# paces, so each leg below is sent at the rate its own steps travel.
	var cadence: float = actor.initial_server_interval
	# What the body covers the ground at while it is crossing a step, on each
	# leg. A diagonal step is 1.41 tiles sent 1.41 paces apart, so it has to
	# render at the same metres per second as a straight one - handing every
	# step shape the one interval is what made the walk speed up and slow down
	# along a zigzagging path. A leg whose step has already finished when the
	# next one is due reads as zero here, which is the same fault seen from the
	# other end: the body arrives early and stands still until the server
	# catches up with it.
	var leg_speeds: Array[float] = []
	# Command, server dx, dy. Each leg turns off the last one, so the first
	# step of a leg is a real turn and the rest are straight.
	for leg: Array in [[22, 1, 0], [21, 1, 1], [20, 0, 1], [27, -1, 1],
			[26, -1, 0], [25, -1, -1], [24, 0, -1], [23, 1, -1]]:
		for step: int in range(STEPS):
			dto["x"] = int(dto["x"]) + int(leg[1])
			dto["y"] = int(dto["y"]) + int(leg[2])
			dto["command"] = int(leg[0])
			actor.apply_server_state(dto, adapter)
			await create_timer(cadence * Vector2(
				float(leg[1]), float(leg[2])).length()).timeout
		var want: float = adapter.direction_to_godot(
			Vector2i(int(leg[1]), int(leg[2])))
		var error_degrees: float = absf(rad_to_deg(
			wrapf(actor.rotation.y - want, -PI, PI)))
		_expect(error_degrees < 1.0,
			"facing settles on the travel direction for command %d (off by %.2f deg)"
				% [int(leg[0]), error_degrees])
		# A quarter tile is where the arrival margin puts it. Anything that
		# keeps growing is the failure this test exists for.
		_expect(actor.global_position.distance_to(actor.server_target) < 0.6,
			"command %d leaves the actor within a tile of its own position (%.2f m)"
				% [int(leg[0]), actor.global_position.distance_to(actor.server_target)])
		var crossing_speed: float = 0.0
		if actor._segment_duration > 0.0:
			crossing_speed = (actor._segment_start.distance_to(
				actor.server_target) / actor._segment_duration)
		leg_speeds.append(crossing_speed)

	var slowest: float = leg_speeds.min()
	var fastest: float = leg_speeds.max()
	_expect(fastest <= slowest * 1.05,
		"all eight directions are walked at one speed (%.2f - %.2f m/s)"
			% [slowest, fastest])

	# A redirect mid-path - clicking a new spot while a path still runs - must turn
	# the body to the new heading at once, since the facing is taken fresh from
	# each step rather than averaged over a window that would drag the old one in.
	# Walk east, reverse west.
	actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"command": 22}, adapter, true)
	var rx := 0
	for _east: int in range(6):
		rx += 1
		actor.apply_server_state({"actor_id": 7, "x": rx, "y": 0, "rotation": 0,
			"command": 22}, adapter)
		await create_timer(cadence).timeout
	var west: float = adapter.direction_to_godot(Vector2i(-1, 0))
	var redirect_settle := -1
	for s: int in range(6):
		rx -= 1
		actor.apply_server_state({"actor_id": 7, "x": rx, "y": 0, "rotation": 0,
			"command": 26}, adapter)
		await create_timer(cadence).timeout
		if redirect_settle < 0 and absf(rad_to_deg(
				wrapf(actor.rotation.y - west, -PI, PI))) < 10.0:
			redirect_settle = s + 1
	_expect(redirect_settle >= 0 and redirect_settle <= 2,
		"a mid-path redirect faces the new heading at once (took %d steps)"
			% redirect_settle)

	# The walk clip turns the body ~23 deg off its travel; the model correction
	# eases in as the walk clip blends in and turns the visual root back, so the
	# body a player sees faces the way it walks. It rides on the NativeModel node,
	# and is absent for the resting idle, so the two must differ by the correction.
	var native_model: Node3D = actor.get_node_or_null("NativeModel") as Node3D
	actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"command": 22}, adapter, true)
	actor.play_action(&"idle")
	for _settle: int in range(3):
		await create_timer(cadence).timeout
	var idle_model_yaw: float = native_model.rotation.y
	var wx := 0
	for _w: int in range(5):
		wx += 1
		actor.apply_server_state({"actor_id": 7, "x": wx, "y": 0, "rotation": 0,
			"command": 22}, adapter)
		await create_timer(cadence).timeout
	var walk_correction: float = absf(rad_to_deg(
		wrapf(native_model.rotation.y - idle_model_yaw, -PI, PI)))
	_expect(walk_correction > 15.0,
		"walking turns the model back onto its travel (%.1f deg from idle)"
			% walk_correction)

	# A creature turned to face the player it is attacking must stay turned.
	# The turn is an actor command and carries no rotation field, so the
	# rotation on the packet is still the one the actor spawned with. Reading
	# it for the attack commands that follow snapped the body back to its
	# spawn facing on every swing - a wolf hitting a player it faced away from.
	actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"command": 22}, adapter, true)
	for _still: int in range(3):
		await create_timer(cadence).timeout
	# CMD_TURN_W, then enter combat and two swings from the same tile.
	for standing_command: int in [44, 18, 46, 46]:
		actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
			"command": standing_command}, adapter)
		await create_timer(cadence).timeout
	var faced_west: float = absf(rad_to_deg(wrapf(
		actor.rotation.y - adapter.direction_to_godot(Vector2i(-1, 0)), -PI, PI)))
	_expect(faced_west < 1.0,
		"an actor keeps the facing it was turned to while it attacks (off by %.1f deg)"
			% faced_west)

	# And the same round as it really arrives. The server queues a creature's
	# turn and the swing behind it into one flush, so the client decodes both
	# in one read and renders the single state they reduce to - the turn is
	# never a frame of its own. Every aggressor in a multi-combat swings on
	# this shape, which is why a crowd of them all faced away at once.
	# Reset it facing west, so the eastward turn in the burst has somewhere to
	# turn from and a dropped one leaves the body pointing the wrong way.
	actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"command": 26}, adapter, true)
	for _still_again: int in range(3):
		await create_timer(cadence).timeout
	var burst: Dictionary = {"actor_id": 7, "x": 0, "y": 0, "rotation": 0}
	for burst_command: int in [40, 18]:
		burst = ActorReducer.apply_command(burst, burst_command)
	actor.apply_server_state(burst, adapter)
	for _round: int in range(3):
		burst = ActorReducer.apply_command(burst, 46)
		actor.apply_server_state(burst, adapter)
		await create_timer(cadence).timeout
	var faced_east: float = absf(rad_to_deg(wrapf(
		actor.rotation.y - adapter.direction_to_godot(Vector2i(1, 0)), -PI, PI)))
	_expect(faced_east < 1.0,
		"a turn coalesced into one frame with the swing behind it still turns the actor (off by %.1f deg)"
			% faced_east)

	print("actor facing tests: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _expect(value: bool, label: String) -> void:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
