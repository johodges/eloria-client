extends SceneTree
## Exercises the client-side half of gameplay traversal against the Sunmane
## Steppe package: click-to-move picking, camera rotation and zoom, structural
## collision, coordinate round-tripping, portal approaches and minimap
## position accuracy.
##
## Everything here is what the client itself computes. Movement authorisation
## and map transitions are the server's, and are not exercised.

const PACKAGE := "res://../eloria-assets/maps/nymara-regions/sunmane_steppe/"
const MANIFEST := PACKAGE + "world.json"
const NAVIGATION_LAYER := 8
const WORLD_LAYER := 1
const SCREEN := Vector2i(1280, 720)

var _failures := 0
var _loader: WorldLoader
var _space: PhysicsDirectSpaceState3D
var _adapter: CoordinateAdapter
var _camera: Camera3D

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = SCREEN
	var stage := Node3D.new()
	root.add_child(stage)
	_camera = Camera3D.new()
	_camera.far = 900.0
	_camera.current = true
	stage.add_child(_camera)
	_loader = WorldLoader.new()
	_loader.name = "WorldLoader"
	stage.add_child(_loader)
	_loader.load_world(ProjectSettings.globalize_path(MANIFEST))
	var deadline := Time.get_ticks_msec() + 120000
	while _loader.world_root == null and Time.get_ticks_msec() < deadline:
		await process_frame
	if not _expect(_loader.world_root != null, "world loads"):
		_finish()
		return
	for unused: int in range(6):
		await physics_frame
	_space = stage.get_world_3d().direct_space_state
	_adapter = _loader.coordinate_adapter

	_test_coordinate_round_trip()
	_test_click_to_move()
	await _test_camera_rotation_and_zoom(stage)
	_test_structural_collision()
	_test_world_boundary()
	_test_portal_approaches()
	_test_minimap_accuracy()
	_finish()

# ---------------------------------------------------------------- coordinates
func _test_coordinate_round_trip() -> void:
	var mismatches := 0
	for tile_x in range(0, 117, 4):
		for tile_y in range(0, 117, 4):
			var world := _adapter.server_to_godot(float(tile_x), float(tile_y))
			var back := _adapter.godot_to_server(world)
			if back != Vector2i(tile_x, tile_y):
				mismatches += 1
	_expect(mismatches == 0,
		"server tile -> world -> server tile round-trips exactly (%d mismatches)"
		% mismatches)
	var datum := _adapter.server_to_godot(58.0, 58.0)
	_expect(is_equal_approx(datum.x, 0.0) and is_equal_approx(datum.z, 0.0),
		"arrival datum (58, 58) maps to the world origin")

# --------------------------------------------------------------- click-to-move
func _test_click_to_move() -> void:
	## Reproduces main.gd's picking path: a camera ray into the navigation
	## layer, then the hit point converted to a server tile for MOVE_TO.
	var picked := 0
	var attempted := 0
	var off_map := 0
	for target: Array in [[0.0, 0.0, "crossroads plaza"], [0.0, 25.0, "south gate"],
			[-30.0, -30.0, "clan camp paddock"], [44.0, 36.0, "windmill field"],
			[-52.0, 0.0, "west portal road"], [52.0, 0.0, "east portal road"],
			[0.0, -42.0, "north barrow field"], [-55.0, 46.0, "cove landing"],
			[26.0, 44.0, "stone circle"], [-20.0, -80.0, "northern mesa"],
			[62.0, 22.0, "eastern well"], [18.0, 40.0, "southern paddock"],
			[-24.0, 22.0, "bridge crossing"], [34.0, 30.0, "crop block"]]:
		attempted += 1
		var world_x := float(target[0])
		var world_z := float(target[1])
		# Frame the point the way a player would, then pick through screen centre.
		var ground: Variant = _ground(world_x, world_z)
		if ground == null:
			continue
		var eye := (ground as Vector3) + Vector3(0.0, 18.0, 24.0)
		_camera.look_at_from_position(eye, ground as Vector3, Vector3.UP)
		var centre := Vector2(SCREEN) * 0.5
		var origin := _camera.project_ray_origin(centre)
		var direction := _camera.project_ray_normal(centre)
		var query := PhysicsRayQueryParameters3D.create(origin,
			origin + direction * 2000.0, NAVIGATION_LAYER)
		var hit := _space.intersect_ray(query)
		var position: Variant = hit.get("position")
		if position is Vector3:
			picked += 1
			var tile := _adapter.godot_to_server(position as Vector3)
			if tile.x < 0 or tile.y < 0 or tile.x > 200 or tile.y > 200:
				off_map += 1
				push_warning("pick at %s produced an off-map tile %s" % [
					str(target[2]), tile])
		else:
			push_warning("click-to-move pick missed at " + str(target[2]))
	_expect(picked == attempted,
		"click-to-move picks a walk surface at every representative location (%d/%d)"
		% [picked, attempted])
	_expect(off_map == 0, "every picked point converts to an on-map server tile")

# ------------------------------------------------------------------- camera
func _test_camera_rotation_and_zoom(stage: Node3D) -> void:
	var rig := IsometricCameraController.new()
	var rig_camera := Camera3D.new()
	rig_camera.name = "Camera"
	rig_camera.unique_name_in_owner = true
	rig.add_child(rig_camera)
	rig_camera.owner = rig
	stage.add_child(rig)
	await process_frame
	var focus: Variant = _ground(0.0, 0.0)
	_expect(focus != null, "camera focus point is grounded")
	if focus == null:
		return
	rig.set_focus(focus as Vector3)
	var seen := 0
	var checked := 0
	for pitch in [-15.0, -30.0, -45.0, -60.0, -80.0]:
		for yaw in [0.0, 72.0, 144.0, 216.0, 288.0]:
			for distance in [8.0, 26.0, 60.0, 90.0]:
				rig.pitch_degrees = pitch
				rig.yaw_degrees = yaw
				rig.distance = distance
				rig.set_focus(focus as Vector3)
				checked += 1
				# The ground must remain in front of the camera at every
				# reachable orientation, or the player is inside the terrain.
				var eye := rig_camera.global_position
				var query := PhysicsRayQueryParameters3D.create(eye,
					focus as Vector3, NAVIGATION_LAYER)
				if eye.y > (focus as Vector3).y:
					seen += 1
				elif not _space.intersect_ray(query).is_empty():
					seen += 1
	_expect(seen == checked,
		"camera stays above the focus ground across the rig's whole pitch, yaw "
		+ "and zoom range (%d/%d)" % [seen, checked])
	rig.queue_free()

# ---------------------------------------------------------------- collision
func _test_structural_collision() -> void:
	var declared: Array = _loader.manifest.data["collision"]["nodeNames"]
	_expect(declared.size() >= 100,
		"structural collision is declared for the built environment (%d nodes)"
		% declared.size())
	var bodies := 0
	for node: Node in _loader.world_root.find_children("*", "StaticBody3D", true, false):
		if (node as StaticBody3D).collision_layer == WORLD_LAYER:
			bodies += 1
	_expect(bodies == declared.size(),
		"every declared collision node produced a body (%d of %d)"
		% [bodies, declared.size()])

	# Fan rays through each structure at two heights. A single axis ray is a
	# poor test: it threads a gateway or passes between a tower's legs and
	# reports missing collision where there is none.
	var solid := 0
	var probes := 0
	# `share` is the fraction of fanned rays that must be blocked. Open timber
	# frames - a lookout tower on splayed legs, a rail corral - are meant to be
	# walked under and through, so they only have to present their members.
	for probe: Array in [[0.0, -13.0, 26.0, "great hall", 0.34],
			[0.0, 0.0, 30.0, "palisade ring", 0.34],
			[-42.0, 0.0, 12.0, "west caravanserai", 0.34],
			[42.0, 0.0, 12.0, "east caravanserai", 0.34],
			[44.0, 36.0, 12.0, "windmill", 0.34],
			[-33.0, 30.0, 8.0, "well", 0.10],
			[0.0, -42.0, 10.0, "barrow with archive entrance", 0.34],
			[-30.0, -30.0, 14.0, "clan paddock (open rails)", 0.10],
			[-54.0, -60.0, 10.0, "rider outpost (open frame)", 0.10],
			[-55.0, 46.0, 12.0, "cove landing (open piles)", 0.10]]:
		probes += 1
		var centre: Variant = _ground(float(probe[0]), float(probe[1]))
		if centre == null:
			continue
		var reach := float(probe[2])
		var hits := 0
		var casts := 0
		for height in [0.9, 2.2]:
			var level := (centre as Vector3) + Vector3(0.0, height, 0.0)
			for step in range(12):
				var angle := PI * float(step) / 12.0
				var offset := Vector3(cos(angle) * reach, 0.0, sin(angle) * reach)
				casts += 1
				var query := PhysicsRayQueryParameters3D.create(
					level + offset, level - offset, WORLD_LAYER)
				if not _space.intersect_ray(query).is_empty():
					hits += 1
		if float(hits) >= float(casts) * float(probe[4]):
			solid += 1
		else:
			push_warning("thin structural collision at %s: %d of %d rays blocked"
				% [str(probe[3]), hits, casts])
	_expect(solid == probes,
		"every probed structure presents the collision its form implies (%d/%d)"
		% [solid, probes])

func _test_world_boundary() -> void:
	## The rim must rise well above the playable plateau all the way round, so a
	## player cannot walk off the authored region into empty space.
	var bounds: Dictionary = _loader.manifest.data["asset"]["bounds"]
	var half: float = float((bounds["max"] as Array)[0])
	var datum: Variant = _ground(0.0, 0.0)
	var plateau: float = (datum as Vector3).y if datum != null else 0.0
	var low := 0
	var samples := 0
	var reach := half - 6.0
	var perimeter: Array[Vector2] = []
	for step in range(0, 24):
		var t := -reach + 2.0 * reach * float(step) / 24.0
		perimeter.append(Vector2(t, -reach))
		perimeter.append(Vector2(t, reach))
		perimeter.append(Vector2(-reach, t))
		perimeter.append(Vector2(reach, t))
	for point_xz: Vector2 in perimeter:
		samples += 1
		var point: Variant = _ground(point_xz.x, point_xz.y)
		if point == null:
			continue
		var rim: float = (point as Vector3).y
		# Either raised ground or open water below the shore: both are barriers.
		if rim < plateau + 6.0 and rim > 0.5:
			low += 1
	_expect(low <= samples / 12,
		"the world edge is a raised rim or open water almost all the way round "
		+ "(%d of %d samples were neither)" % [low, samples])

func _test_portal_approaches() -> void:
	## Each portal tile must be reachable ground with clear headroom, so a
	## transition can never drop a player into geometry.
	for entry: Array in [[6, 58, "west walk portal"], [110, 58, "east walk portal"],
			[58, 100, "north interior entrance"]]:
		var flat := _adapter.server_to_godot(float(entry[0]), float(entry[1]))
		var point: Variant = _ground(flat.x, flat.z)
		if not _expect(point != null, "portal ground: " + str(entry[2])):
			continue
		var head := (point as Vector3) + Vector3(0.0, 0.4, 0.0)
		var query := PhysicsRayQueryParameters3D.create(head,
			head + Vector3(0.0, 2.4, 0.0), WORLD_LAYER)
		_expect(_space.intersect_ray(query).is_empty(),
			"portal approach has standing headroom: " + str(entry[2]))

func _test_minimap_accuracy() -> void:
	var minimap: Dictionary = _loader.manifest.data["minimap"]
	var scale: float = float((minimap["transform"] as Dictionary)["pixelX"]["scale"])
	var offset: float = float((minimap["transform"] as Dictionary)["pixelX"]["offset"])
	var size: float = float((minimap["imageSize"] as Array)[0])
	var bounds: Dictionary = _loader.manifest.data["asset"]["bounds"]
	var half: float = float((bounds["max"] as Array)[0])
	_expect(is_equal_approx(scale, size / (half * 2.0)),
		"minimap scale matches the image size and world bounds")
	for check: Array in [[-half, 0.0], [half, size], [0.0, size * 0.5]]:
		_expect(is_equal_approx(float(check[0]) * scale + offset, float(check[1])),
			"minimap maps world %.1f m to pixel %.1f" % [check[0], check[1]])
	# The player marker must land inside the image for every walkable tile.
	var outside := 0
	for tile_x in range(0, 117, 8):
		for tile_y in range(0, 117, 8):
			var world := _adapter.server_to_godot(float(tile_x), float(tile_y))
			var pixel := Vector2(world.x * scale + offset, world.z * scale + offset)
			if pixel.x < 0.0 or pixel.y < 0.0 or pixel.x > size or pixel.y > size:
				outside += 1
	_expect(outside == 0,
		"every server tile maps inside the minimap image (%d outside)" % outside)

# ------------------------------------------------------------------ helpers
func _ground(world_x: float, world_z: float) -> Variant:
	var query := PhysicsRayQueryParameters3D.create(
		Vector3(world_x, 400.0, world_z), Vector3(world_x, -100.0, world_z),
		NAVIGATION_LAYER)
	var hit := _space.intersect_ray(query)
	var position: Variant = hit.get("position")
	return position if position is Vector3 else null

func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	_failures += 1
	push_error("FAIL: " + message)
	return false

func _finish() -> void:
	print("sunmane traversal: ", "PASS" if _failures == 0 else "FAIL")
	quit(_failures)
