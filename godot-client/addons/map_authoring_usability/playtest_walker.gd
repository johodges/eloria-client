@tool
extends RefCounted
## Play-test walking inside the editor: a stand-in character that walks the
## open territory the way the server would move a player.
##
## Routes come from the territory's published walk grid (collision.bin, half-
## metre cells), so the walker goes exactly where the served map lets a player
## go. A territory with no published grid falls back to the live suggestion
## from the walkability overlay (1 m tiles, terrain heights). Like the server,
## a step may climb or drop at most 0.4 m (max_walk_height_change 2 x 0.2 m),
## diagonals may not cut corners, and each step takes 250 ms
## (player_move_interval_ms).
##
## The search runs on a window around the start and goal, then, when that finds
## nothing, on the whole territory. A search wider than its cell cap runs on
## 2x2 (or 3x3) blocks that are walkable only when all their cells are, so it
## never crosses a thin wall but can miss a gap narrower than a block; the
## route message says when that happened.
## The walker and its route are editor-only helpers and are never saved.

const Walkability := preload("res://addons/map_authoring_usability/walkability_overlay.gd")
const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const NODE_NAME := "__MapAuthoringPlaytest"
const STEP_SECONDS := 0.25
const MAX_CLIMB := 0.4
## The server's step length; the climb allowance scales with the searched cell.
const SERVER_CELL := 0.5
const WINDOW_MARGIN := 48.0
const MAX_WINDOW_CELLS := 640
## The whole-territory retry samples at most this many cells a side (a 792 m
## territory is searched on 1 m cells, which still finds any 1 m gap).
const MAX_TERRITORY_CELLS := 800
const SNAP_RADIUS := 3.0
const BODY_COLOR := Color(1.0, 0.78, 0.18)
const ROUTE_COLOR := Color(1.0, 0.9, 0.35, 0.95)

var active := false
var last_message := ""
## "published" or "live" once a grid is loaded.
var source := ""
## Steps of the current route and the sampling stride it was found at.
var steps := 0
var stride := 1

var _root: Node3D
var _grid: Dictionary = {}
var _node: Node3D
var _body: Node3D
var _line: MeshInstance3D
var _goal_ring: MeshInstance3D
var _route := PackedVector3Array()
var _progress := 0.0
var _position := Vector3.INF
var _facing := Vector3.FORWARD
var _pooled := {}


## Loads the walk grid and shows usage. Returns false when there is nothing to
## walk on.
func start(root: Node3D) -> bool:
	stop()
	if root == null or Probe.region_terrain(root) == null:
		last_message = "Play test needs a region territory with terrain."
		return false
	_root = root
	_grid = load_grid(root)
	if _grid.has("error"):
		last_message = String(_grid.error)
		_grid = {}
		_root = null
		return false
	source = String(_grid.source)
	active = true
	_build_nodes()
	last_message = "Play test on the %s grid: click the ground to place the walker." % (
		"published" if source == "published" else "live (unpublished)")
	return true


func stop() -> void:
	active = false
	_route = PackedVector3Array()
	_position = Vector3.INF
	steps = 0
	if _node != null and is_instance_valid(_node):
		if _node.get_parent() != null:
			_node.get_parent().remove_child(_node)
		_node.queue_free()
	_node = null
	_body = null
	_line = null
	_goal_ring = null
	_root = null
	_grid = {}
	_pooled = {}


func is_placed() -> bool:
	return _position.is_finite()


func is_walking() -> bool:
	return _route.size() >= 2 and _progress < float(_route.size() - 1)


## The walker's territory-local position (INF before it is placed).
func position() -> Vector3:
	return _position


func route() -> PackedVector3Array:
	return _route


func node() -> Node3D:
	return _node


func hint_lines() -> PackedStringArray:
	var lines := PackedStringArray()
	if not active:
		return lines
	lines.append("Play test (%s grid)" % source)
	lines.append(last_message)
	lines.append("Click: walk there   Shift+click: place   F: centre on walker   Esc/right-click: stop")
	return lines


## Viewport input while play testing. Returns true when consumed.
func handle_input(camera: Camera3D, event: InputEvent) -> bool:
	if not active:
		return false
	if event is InputEventKey and event.pressed and not event.echo:
		if (event as InputEventKey).keycode == KEY_ESCAPE:
			stop()
			last_message = "Play test ended."
			return true
		return false
	if not event is InputEventMouseButton or not event.pressed:
		return false
	var button := event as InputEventMouseButton
	if button.button_index == MOUSE_BUTTON_RIGHT:
		stop()
		last_message = "Play test ended."
		return true
	if button.button_index != MOUSE_BUTTON_LEFT or button.alt_pressed or button.ctrl_pressed:
		return false
	var origin := camera.project_ray_origin(button.position)
	var direction := camera.project_ray_normal(button.position)
	var hit: Variant = Probe.ray_hit(_root, origin, direction, 4096.0)
	if not hit is Vector3:
		last_message = "Click the ground."
		return true
	var local := _root.global_transform.affine_inverse() * (hit as Vector3)
	if button.shift_pressed or not is_placed():
		place(local)
	else:
		walk_to(local)
	return true


## Puts the walker on the nearest walkable cell within SNAP_RADIUS of `local`.
func place(local: Vector3) -> bool:
	var cell: Variant = nearest_walkable(local, SNAP_RADIUS)
	if cell == null:
		last_message = "Not walkable here (nothing walkable within %.0f m)." % SNAP_RADIUS
		return false
	_route = PackedVector3Array()
	_progress = 0.0
	steps = 0
	_position = cell_point(cell as Vector2i)
	_update_nodes()
	last_message = "Walker placed at %s. Click somewhere to walk there." % _describe(_position)
	return true


## Finds a route from the walker to `local` and starts walking it.
func walk_to(local: Vector3) -> bool:
	if not is_placed():
		return place(local)
	var goal: Variant = nearest_walkable(local, SNAP_RADIUS)
	if goal == null:
		last_message = "That spot is not walkable (nothing walkable within %.0f m)." % SNAP_RADIUS
		return false
	var found := find_route(_position, cell_point(goal as Vector2i))
	if found.size() < 2:
		_route = PackedVector3Array()
		_update_nodes()
		return false
	_route = found
	_progress = 0.0
	_update_nodes()
	return true


## Moves the walker along its route; call every frame.
func advance(delta: float) -> void:
	if not active or not is_walking():
		return
	_progress = minf(_progress + delta / (STEP_SECONDS * float(stride)), float(_route.size() - 1))
	var index := mini(floori(_progress), _route.size() - 2)
	var t := _progress - float(index)
	var from := _route[index]
	var to := _route[index + 1]
	_position = from.lerp(to, t)
	var flat := Vector3(to.x - from.x, 0.0, to.z - from.z)
	if flat.length_squared() > 0.0001:
		_facing = flat.normalized()
	if not is_walking():
		last_message = "Arrived: %d steps, %.1f s of walking." % [steps, float(steps) * STEP_SECONDS]
	_update_body()


# Grid ----------------------------------------------------------------------

## The walk grid in one shape for both sources:
## {source, codes (walkable when > 0), width, rows, cell, x0, z_start, row_sign,
##  height_origin, height_step} for published; live adds nothing but uses
## terrain heights (height_step NAN).
static func load_grid(root: Node3D) -> Dictionary:
	var published := Walkability.published_grid(root)
	if not published.has("error"):
		return {"source": "published", "codes": published.bytes, "width": published.width,
			"rows": published.rows, "cell": published.cell, "x0": published.x0,
			"z_start": published.z1, "row_sign": -1.0,
			"height_origin": published.get("height_origin", NAN),
			"height_step": published.get("height_step", NAN)}
	var live := Walkability.compute_live(root)
	if live.has("error"):
		return {"error": "No walk grid: %s" % String(live.error)}
	var classes: PackedByteArray = live.classes
	var owned: PackedByteArray = (live.owned as Image).get_data()
	var codes := PackedByteArray()
	codes.resize(classes.size())
	for index in classes.size():
		var value := classes[index]
		if (value == Walkability.Tile.WALKABLE or value == Walkability.Tile.DECK) and \
				owned[index * 4 + 3] > 127:
			codes[index] = 1
	return {"source": "live", "codes": codes, "width": live.width, "rows": live.rows,
		"cell": live.tile, "x0": live.x0, "z_start": live.z0, "row_sign": 1.0,
		"height_origin": NAN, "height_step": NAN, "root": root}


func grid() -> Dictionary:
	return _grid


## The grid cell under a territory-local point, or (-1, -1) outside the grid.
func cell_of(local: Vector3) -> Vector2i:
	var cell := float(_grid.cell)
	var column := floori((local.x - float(_grid.x0)) / cell)
	var row := floori(float(_grid.row_sign) * (local.z - float(_grid.z_start)) / cell)
	if column < 0 or row < 0 or column >= int(_grid.width) or row >= int(_grid.rows):
		return Vector2i(-1, -1)
	return Vector2i(column, row)


func is_walkable(cell: Vector2i) -> bool:
	if cell.x < 0 or cell.y < 0 or cell.x >= int(_grid.width) or cell.y >= int(_grid.rows):
		return false
	return (_grid.codes as PackedByteArray)[cell.y * int(_grid.width) + cell.x] > 0


## The server's height of a walkable cell (territory-local metres), or NAN.
func cell_height(cell: Vector2i) -> float:
	if not is_walkable(cell):
		return NAN
	var step := float(_grid.height_step)
	if not is_nan(step):
		var code := (_grid.codes as PackedByteArray)[cell.y * int(_grid.width) + cell.x]
		return float(_grid.height_origin) + float(code) * step
	return _terrain_height(_cell_centre(cell))


## A walkable cell's centre on the ground the walker stands on. Where the grid
## height matches the terrain (within a code step) the smooth terrain is used;
## elsewhere (bridge decks, floors) the grid height.
func cell_point(cell: Vector2i) -> Vector3:
	var centre := _cell_centre(cell)
	var served := cell_height(cell)
	var ground := _terrain_height(centre)
	var tolerance := maxf(float(_grid.height_step) * 1.5, 0.45) \
		if not is_nan(float(_grid.height_step)) else INF
	var y := ground if not is_nan(ground) and (is_nan(served) or absf(served - ground) <= tolerance) \
		else served
	return Vector3(centre.x, y if not is_nan(y) else 0.0, centre.y)


func nearest_walkable(local: Vector3, radius: float) -> Variant:
	var centre := cell_of(local)
	if centre.x < 0:
		return null
	if is_walkable(centre):
		return centre
	var reach := ceili(radius / float(_grid.cell))
	var best: Variant = null
	var best_distance := INF
	for dy in range(-reach, reach + 1):
		for dx in range(-reach, reach + 1):
			var cell := centre + Vector2i(dx, dy)
			if not is_walkable(cell):
				continue
			var distance := float(dx * dx + dy * dy)
			if distance < best_distance:
				best_distance = distance
				best = cell
	return best


## A route between two territory-local points as ground points, one per step;
## empty (with last_message saying why) when there is none. The search first
## covers a window around both points, then the whole territory.
func find_route(from_local: Vector3, to_local: Vector3) -> PackedVector3Array:
	var start := cell_of(from_local)
	var goal := cell_of(to_local)
	if not is_walkable(start) or not is_walkable(goal):
		last_message = "Start or goal is not walkable."
		return PackedVector3Array()
	var margin := ceili(WINDOW_MARGIN / float(_grid.cell))
	var low := Vector2i(maxi(mini(start.x, goal.x) - margin, 0),
		maxi(mini(start.y, goal.y) - margin, 0))
	var high := Vector2i(mini(maxi(start.x, goal.x) + margin, int(_grid.width) - 1),
		mini(maxi(start.y, goal.y) + margin, int(_grid.rows) - 1))
	var result := _search(start, goal, low, high, MAX_WINDOW_CELLS)
	var whole := low == Vector2i.ZERO and high == Vector2i(int(_grid.width) - 1, int(_grid.rows) - 1)
	if result.is_empty() and not whole and not last_message.begins_with("Start or goal"):
		result = _search(start, goal, Vector2i.ZERO,
			Vector2i(int(_grid.width) - 1, int(_grid.rows) - 1), MAX_TERRITORY_CELLS)
	return result


func _search(start: Vector2i, goal: Vector2i, low: Vector2i, high: Vector2i,
		cap: int) -> PackedVector3Array:
	var result := PackedVector3Array()
	var span := maxi(high.x - low.x + 1, high.y - low.y + 1)
	stride = maxi(1, ceili(float(span) / float(cap)))
	var grid := _search_grid(stride)
	var grid_width := int(grid.width)
	var low_c := Vector2i(low.x / stride, low.y / stride)
	var high_c := Vector2i(mini(high.x / stride, grid_width - 1),
		mini(high.y / stride, int(grid.rows) - 1))
	var size := high_c - low_c + Vector2i.ONE
	var centre := Vector2i(stride / 2, stride / 2)
	var heights := PackedFloat32Array()
	heights.resize(size.x * size.y)
	var astar := AStarGrid2D.new()
	astar.region = Rect2i(Vector2i.ZERO, size)
	astar.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	astar.default_compute_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	astar.default_estimate_heuristic = AStarGrid2D.HEURISTIC_OCTILE
	astar.update()
	var codes: PackedByteArray = grid.codes
	var coded := not is_nan(float(_grid.height_step))
	var origin := float(_grid.height_origin)
	var step := float(_grid.height_step)
	for gy in size.y:
		var base := (low_c.y + gy) * grid_width + low_c.x
		for gx in size.x:
			var code := codes[base + gx]
			if code == 0:
				heights[gy * size.x + gx] = NAN
				astar.set_point_solid(Vector2i(gx, gy))
			elif coded:
				heights[gy * size.x + gx] = origin + float(code) * step
			else:
				heights[gy * size.x + gx] = _terrain_height(_cell_centre(
					(low_c + Vector2i(gx, gy)) * stride + centre))
	# A step the server refuses (too high a climb or drop) is removed by making
	# the lower cell of the pair solid: nothing can then reach the upper cell
	# across that edge, while the upper cell (a deck rim) keeps its full width.
	# Diagonal neighbours are a longer step apart, so a slope the grade rule
	# allows is not mistaken for a ledge there.
	# Codes round each end by up to half a step, so a legal slope can differ
	# by one code more than its true height change.
	var tolerance := step if coded else 0.05
	var climb := MAX_CLIMB * float(stride) * float(_grid.cell) / SERVER_CELL + tolerance
	var diagonal_climb := climb * sqrt(2.0)
	for gy in size.y:
		var row_index := gy * size.x
		for gx in size.x:
			var here := heights[row_index + gx]
			if is_nan(here):
				continue
			if gx + 1 < size.x:
				_mark_ledge(astar, heights, size, gx, gy, gx + 1, gy, here, climb)
			if gy + 1 < size.y:
				_mark_ledge(astar, heights, size, gx, gy, gx, gy + 1, here, climb)
				if gx + 1 < size.x:
					_mark_ledge(astar, heights, size, gx, gy, gx + 1, gy + 1, here, diagonal_climb)
				if gx > 0:
					_mark_ledge(astar, heights, size, gx, gy, gx - 1, gy + 1, here, diagonal_climb)
	var from := _open_near(astar, start / stride - low_c, size)
	var to := _open_near(astar, goal / stride - low_c, size)
	if from.x < 0 or to.x < 0:
		last_message = "Start or goal sits on a ledge the server would not step off."
		return result
	var path := astar.get_id_path(from, to)
	var metres := float(stride) * float(_grid.cell)
	if path.is_empty():
		last_message = "No walkable route: the goal is fenced, walled or cut off from the walker (searched %.0f x %.0f m%s)." % [
			float(size.x) * metres, float(size.y) * metres,
			" on %.1f m cells" % metres if stride > 1 else ""]
		steps = 0
		return result
	for point in path:
		result.append(cell_point((low_c + point) * stride + centre))
	steps = (path.size() - 1) * stride
	last_message = "Walking %d steps (%.1f s, %.0f m)%s." % [steps, float(steps) * STEP_SECONDS,
		_length(result), "; searched on %.1f m cells" % metres if stride > 1 else ""]
	return result


## The grid searched at `sample` cells per side: the walk grid itself, or a
## coarser one where a cell is walkable only when every fine cell in it is, so
## a coarse search never slips through a wall one cell thick. Cached per play
## test.
func _search_grid(sample: int) -> Dictionary:
	if sample <= 1:
		return {"codes": _grid.codes, "width": int(_grid.width), "rows": int(_grid.rows)}
	if _pooled.has(sample):
		return _pooled[sample]
	var width := int(_grid.width)
	var coarse_width := width / sample
	var coarse_rows := int(_grid.rows) / sample
	var codes: PackedByteArray = _grid.codes
	var pooled := PackedByteArray()
	pooled.resize(coarse_width * coarse_rows)
	var centre := sample / 2
	for cy in coarse_rows:
		var top := cy * sample * width
		for cx in coarse_width:
			var corner := top + cx * sample
			var open := true
			if sample == 2:
				open = codes[corner] > 0 and codes[corner + 1] > 0 and \
					codes[corner + width] > 0 and codes[corner + width + 1] > 0
			else:
				for oy in sample:
					var row_start := corner + oy * width
					for ox in sample:
						if codes[row_start + ox] == 0:
							open = false
							break
					if not open:
						break
			if open:
				pooled[cy * coarse_width + cx] = codes[corner + centre * width + centre]
	var result := {"codes": pooled, "width": coarse_width, "rows": coarse_rows}
	_pooled[sample] = result
	return result


static func _mark_ledge(astar: AStarGrid2D, heights: PackedFloat32Array, size: Vector2i,
		gx: int, gy: int, nx: int, ny: int, here: float, limit: float) -> void:
	var there := heights[ny * size.x + nx]
	if is_nan(there) or absf(there - here) <= limit:
		return
	if there < here:
		astar.set_point_solid(Vector2i(nx, ny))
	else:
		astar.set_point_solid(Vector2i(gx, gy))


static func _open_near(astar: AStarGrid2D, cell: Vector2i, size: Vector2i) -> Vector2i:
	for radius in 4:
		for dy in range(-radius, radius + 1):
			for dx in range(-radius, radius + 1):
				if maxi(absi(dx), absi(dy)) != radius:
					continue
				var probe := cell + Vector2i(dx, dy)
				if probe.x >= 0 and probe.y >= 0 and probe.x < size.x and probe.y < size.y and \
						not astar.is_point_solid(probe):
					return probe
	return Vector2i(-1, -1)


func _cell_centre(cell: Vector2i) -> Vector2:
	var size := float(_grid.cell)
	return Vector2(float(_grid.x0) + (float(cell.x) + 0.5) * size,
		float(_grid.z_start) + float(_grid.row_sign) * (float(cell.y) + 0.5) * size)


func _terrain_height(point: Vector2) -> float:
	var root: Node3D = _root if _root != null else _grid.get("root") as Node3D
	if root == null:
		return NAN
	var world := root.global_transform * Vector3(point.x, 0.0, point.y)
	var height := Probe.height_at(root, world)
	if is_nan(height):
		return NAN
	return (root.global_transform.affine_inverse() * Vector3(world.x, height, world.z)).y


static func _length(points: PackedVector3Array) -> float:
	var total := 0.0
	for index in range(1, points.size()):
		total += points[index - 1].distance_to(points[index])
	return total


func _describe(local: Vector3) -> String:
	var info := Probe.describe_point(_root, _root.global_transform * local)
	if bool(info.get("has_tile", false)):
		var tile: Vector2i = info.tile
		return "tile %d, %d" % [tile.x, tile.y]
	return "%.1f, %.1f" % [local.x, local.z]


# Nodes ---------------------------------------------------------------------

func _build_nodes() -> void:
	_node = Node3D.new()
	_node.name = NODE_NAME
	var material := StandardMaterial3D.new()
	material.albedo_color = BODY_COLOR
	material.emission_enabled = true
	material.emission = BODY_COLOR * 0.35
	_body = Node3D.new()
	_body.name = "Walker"
	var capsule := CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.8
	capsule.material = material
	var body_mesh := MeshInstance3D.new()
	body_mesh.mesh = capsule
	body_mesh.position = Vector3(0.0, 0.9, 0.0)
	_body.add_child(body_mesh)
	var nose := MeshInstance3D.new()
	var box := BoxMesh.new()
	box.size = Vector3(0.18, 0.18, 0.4)
	box.material = material
	nose.mesh = box
	nose.position = Vector3(0.0, 1.45, -0.38)
	_body.add_child(nose)
	_body.visible = false
	_node.add_child(_body)
	var line_material := StandardMaterial3D.new()
	line_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	line_material.vertex_color_use_as_albedo = true
	line_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	line_material.no_depth_test = true
	_line = MeshInstance3D.new()
	_line.name = "Route"
	_line.mesh = ImmediateMesh.new()
	_line.material_override = line_material
	_line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_node.add_child(_line)
	_goal_ring = MeshInstance3D.new()
	_goal_ring.name = "Goal"
	var torus := TorusMesh.new()
	torus.inner_radius = 0.45
	torus.outer_radius = 0.6
	torus.material = line_material
	_goal_ring.mesh = torus
	_goal_ring.visible = false
	_node.add_child(_goal_ring)
	_root.add_child(_node, false, Node.INTERNAL_MODE_BACK)
	_node.transform = Transform3D.IDENTITY


func _update_nodes() -> void:
	if _node == null:
		return
	var mesh := _line.mesh as ImmediateMesh
	mesh.clear_surfaces()
	if _route.size() >= 2:
		mesh.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
		for point in _route:
			mesh.surface_set_color(ROUTE_COLOR)
			mesh.surface_add_vertex(point + Vector3(0.0, 0.12, 0.0))
		mesh.surface_end()
		_goal_ring.visible = true
		_goal_ring.position = _route[_route.size() - 1] + Vector3(0.0, 0.08, 0.0)
	else:
		_goal_ring.visible = false
	_update_body()


func _update_body() -> void:
	if _body == null:
		return
	_body.visible = is_placed()
	if is_placed():
		_body.transform = Transform3D(Basis.looking_at(_facing, Vector3.UP), _position)
