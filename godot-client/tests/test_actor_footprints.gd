extends SceneTree
## Actors that stand on more than one tile.
##
## The client does no collision of its own - the server reserves the ground
## and this only has to draw the actor on it. Which makes one thing the whole
## point: the tile an actor reports is the anchor of its box, and for an
## even-sized box the anchor is not the middle. Getting that wrong puts a
## two-by-two creature half a tile up and left of the ground it holds, which
## reads as the model being subtly misaligned rather than as a bug in the
## arithmetic below.

const P := preload("res://src/network/protocol.gd")

var _failures := 0

func _init() -> void:
	_decoding()
	_centring()
	_selection()
	print("actor footprints: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

# --- the packet -------------------------------------------------------------

func _footprint_payload(rows: Array) -> PackedByteArray:
	var payload := PackedByteArray()
	payload.append(rows.size() & 0xFF)
	payload.append((rows.size() >> 8) & 0xFF)
	for row: Variant in rows:
		var entry: Array = row as Array
		payload.append(int(entry[0]) & 0xFF)
		payload.append((int(entry[0]) >> 8) & 0xFF)
		payload.append(int(entry[1]))
		payload.append(int(entry[2]))
	return payload

func _decoding() -> void:
	var decoded: Dictionary = P.decode_actor_footprints(
		_footprint_payload([[400, 2, 2], [512, 3, 3], [900, 4, 2]]))
	_expect(decoded.get("type") == "actor_footprints",
		"a footprint table decodes")
	var sizes: Dictionary = decoded.get("footprints", {}) as Dictionary
	_expect(sizes.size() == 3, "every listed type survives the decode")
	_expect(sizes.get(400) == Vector2i(2, 2), "a square footprint decodes")
	_expect(sizes.get(900) == Vector2i(4, 2),
		"a rectangle keeps its two axes the right way round")
	_expect(int((sizes.get(512) as Vector2i).x) == 3, "an actor type above 255 decodes")

	# An empty table is a legitimate answer: it means this profile authors no
	# creature larger than one tile.
	var empty: Dictionary = P.decode_actor_footprints(_footprint_payload([]))
	_expect(empty.get("type") == "actor_footprints"
		and (empty.get("footprints") as Dictionary).is_empty(),
		"an empty table is stated rather than refused")

	var truncated := _footprint_payload([[400, 2, 2]])
	truncated.resize(truncated.size() - 1)
	_expect(P.decode_actor_footprints(truncated).get("type") == "invalid",
		"a truncated table is refused rather than half read")
	_expect(P.decode_actor_footprints(PackedByteArray()).get("type") == "invalid",
		"an empty payload is refused")
	var zero := _footprint_payload([[400, 0, 2]])
	_expect(P.decode_actor_footprints(zero).get("type") == "invalid",
		"a zero-width footprint is refused")

	_expect(P.ServerMessage.ELORIA_ACTOR_FOOTPRINTS == 246,
		"the packet keeps the number the server sends it on")
	_expect(P.CLIENT_CAPABILITIES.has("actor_footprints_v1"),
		"the capability is advertised, or the server never sends the table")

# --- where the model goes ---------------------------------------------------

func _centring() -> void:
	# One metre per tile, no offset: server (x, y) maps to Godot (x, -y), so a
	# tile centre lands on the half.
	var adapter := CoordinateAdapter.new({"metresPerTile": 1.0, "walkingHeight": 0.0})

	var single: Vector3 = adapter.footprint_center(10, 10, Vector2i.ONE)
	_expect(single.is_equal_approx(adapter.tile_center(10, 10)),
		"a single tile is drawn exactly where it always was")

	# 3x3 spans 9..11 on both axes, whose middle is the anchor's own centre.
	var odd: Vector3 = adapter.footprint_center(10, 10, Vector2i(3, 3))
	_expect(odd.is_equal_approx(adapter.tile_center(10, 10)),
		"an odd footprint is centred on its anchor already")

	# 2x2 spans 10..11, whose middle is the corner between them - half a tile
	# further on each axis than the anchor's centre.
	var even: Vector3 = adapter.footprint_center(10, 10, Vector2i(2, 2))
	var anchor: Vector3 = adapter.tile_center(10, 10)
	_expect(is_equal_approx(even.x - anchor.x, 0.5),
		"an even footprint shifts half a tile east")
	_expect(is_equal_approx(even.z - anchor.z, -0.5),
		"an even footprint shifts half a tile north, in Godot's -Z")

	var rectangle: Vector3 = adapter.footprint_center(10, 10, Vector2i(4, 3))
	_expect(is_equal_approx(rectangle.x - anchor.x, 0.5)
		and is_equal_approx(rectangle.z - anchor.z, 0.0),
		"a rectangle shifts only on the axis whose extent is even")

	# The centre of the box the server reserved, derived independently from
	# the same bounds rule the server uses, for every size it can send.
	for width: int in range(1, 11):
		for depth: int in range(1, 11):
			var back_x: int = (width - 1) / 2
			var back_y: int = (depth - 1) / 2
			var min_x: int = 20 - back_x
			var max_x: int = 20 + width / 2
			var min_y: int = 30 - back_y
			var max_y: int = 30 + depth / 2
			var expected: Vector3 = adapter.server_to_godot(
				(float(min_x) + float(max_x) + 1.0) * 0.5,
				(float(min_y) + float(max_y) + 1.0) * 0.5)
			var actual: Vector3 = adapter.footprint_center(
				20, 30, Vector2i(width, depth))
			if not actual.is_equal_approx(expected):
				_expect(false, "%dx%d is centred on its reserved box" % [width, depth])
				return
	_expect(true, "every footprint from 1x1 to 10x10 is centred on its box")

# --- the click target -------------------------------------------------------

func _selection() -> void:
	var actor := ReplicatedActor3D.new()
	var adapter := CoordinateAdapter.new({"metresPerTile": 1.0, "walkingHeight": 0.0})
	root.add_child(actor)
	actor.configure({"actor_id": 1, "x": 10, "y": 10, "rotation": 0,
		"actor_type": 400, "kind": 1, "name": "Giant", "health": 10,
		"max_health": 10, "footprint": Vector2i(3, 3)}, adapter, {}, {})
	var shape: CollisionShape3D = actor.get_node_or_null(
		"SelectionCollision") as CollisionShape3D
	_expect(shape != null, "the actor has a click target")
	if shape != null:
		var capsule: CapsuleShape3D = shape.shape as CapsuleShape3D
		_expect(is_equal_approx(capsule.radius,
			ReplicatedActor3D.SELECTION_RADIUS * 3.0),
			"a three-tile creature is clickable across its body")

	# The table is a login packet and can land after an actor is built, so an
	# actor must take a corrected size rather than keep the one it started at.
	actor.set_footprint(Vector2i(1, 1))
	if shape != null:
		_expect(is_equal_approx((shape.shape as CapsuleShape3D).radius,
			ReplicatedActor3D.SELECTION_RADIUS),
			"a later correction resizes the click target")
	actor.queue_free()

func _expect(value: bool, label: String) -> bool:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
	return value
