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

	# The server's walking pace. The client assumes it until it has measured
	# one, and its own default has to agree or the actor never catches up.
	var cadence: float = actor.initial_server_interval
	# Command, server dx, dy. Each leg turns off the last one, so the first
	# step of a leg is a real turn and the rest are straight.
	for leg: Array in [[22, 1, 0], [21, 1, 1], [20, 0, 1], [27, -1, 1],
			[26, -1, 0], [25, -1, -1], [24, 0, -1], [23, 1, -1]]:
		for step: int in range(STEPS):
			dto["x"] = int(dto["x"]) + int(leg[1])
			dto["y"] = int(dto["y"]) + int(leg[2])
			dto["command"] = int(leg[0])
			actor.apply_server_state(dto, adapter)
			await create_timer(cadence).timeout
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

	# A straight line the player asked for that is not one of the eight tile
	# directions. The server walks it as a zigzag - here two east steps then one
	# northeast, a heading of atan(1/3) north of east - naming each step's own
	# 8-way command. Facing each step alone swung the body up to 23 degrees to
	# either side of that line; the body must instead point along the line it is
	# walking, because the net of the last few steps is that line.
	actor.apply_server_state({"actor_id": 7, "x": 0, "y": 0, "rotation": 0,
		"command": 22}, adapter, true)
	var zx := 0
	var zy := 0
	var worst_offaxis := 0.0
	var offaxis_heading: float = adapter.direction_to_godot(Vector2i(3, 1))
	for step: int in range(24):
		var diagonal: bool = step % 3 == 2
		zx += 1
		zy += 1 if diagonal else 0
		actor.apply_server_state({"actor_id": 7, "x": zx, "y": zy, "rotation": 0,
			"command": 21 if diagonal else 22}, adapter)
		await create_timer(cadence).timeout
		if step >= 6:
			worst_offaxis = maxf(worst_offaxis, absf(rad_to_deg(
				wrapf(actor.rotation.y - offaxis_heading, -PI, PI))))
	_expect(worst_offaxis < 6.0,
		"body points along an off-axis straight line, not at each zigzag step (worst %.1f deg)"
			% worst_offaxis)

	print("actor facing tests: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _expect(value: bool, label: String) -> void:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
