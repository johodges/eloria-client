class_name ExteriorRegionStream
extends Node3D

## One private loader worker, the current region and at most two neighbours.
## Only surveyed reciprocal road collars are displayed simultaneously. The
## server still selects the map and is the sole owner of actors/interactions.
const CONNECTIONS := "res://data/maps/exterior_connections.json"
const PREVIEW_SURFACE_LAYER := 16
var registry: Dictionary = {}
var links: Array = []
var residents: Dictionary = {}
var active_map := ""
var active_root: Node3D
var active_manifest: WorldManifest
var preload_distance := 170.0
var retain_distance := 220.0
var maximum_neighbours := 2
var _thread: Thread
var _pending_map := ""
var _generation := 0
var _pending_generation := 0
var _retry_after: Dictionary = {}
var _last_position := Vector3.ZERO
var _next_update := 0
var events: Array[Dictionary] = []
var last_handoff: Dictionary = {}
var pending_walk: Dictionary = {}
## Retiring trees still occupy their old neighbour slots until their resources
## are released. Do not dispatch another preload while any retirement remains.
## One worker already in flight may finish: the temporary allowance is the
## existing maximum_neighbours trees plus that single worker result, not an
## additional cache of retired maps.
var _retiring: Array[Dictionary] = []
const RETIRE_NODES_PER_FRAME := 64
const RETIRE_BUDGET_USEC := 2000

func configure(maps: Dictionary) -> void:
	registry = maps
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(CONNECTIONS))
	if raw is Dictionary:
		links = raw.get("connections", [])
		preload_distance = float(raw.get("preloadDistance", 170))
		retain_distance = float(raw.get("retainDistance", 220))
		maximum_neighbours = int(raw.get("maximumNeighbours", 2))

func activate(map_id: String, imported: Node3D, manifest: WorldManifest) -> void:
	active_map = MapRegistry.normalize_server_map_id(map_id)
	active_root = imported
	active_manifest = manifest
	_next_update = 0
	_refresh_views()

func update_position(position: Vector3) -> void:
	_last_position = position
	if Time.get_ticks_msec() < _next_update or active_map.is_empty():
		return
	_next_update = Time.get_ticks_msec() + 250
	var candidates := _candidates(position)
	var wanted: Dictionary = {}
	for candidate: Dictionary in candidates:
		if float(candidate.distance) <= retain_distance and wanted.size() < maximum_neighbours:
			wanted[str(candidate.map)] = candidate
	for map_id: String in residents.keys():
		if not wanted.has(map_id):
			_evict(map_id)
	_refresh_views()
	if not _can_dispatch_preload():
		return
	for candidate: Dictionary in candidates:
		var map_id := str(candidate.map)
		if (float(candidate.distance) > preload_distance or residents.has(map_id)
				or not wanted.has(map_id) or Time.get_ticks_msec() < int(_retry_after.get(map_id, 0))):
			continue
		var entry := MapRegistry.resolve(registry, map_id)
		if entry.is_empty():
			continue
		_pending_map = map_id
		_pending_generation = _generation
		_thread = Thread.new()
		var path := ProjectSettings.globalize_path(str(entry.get("manifest", "")))
		var visuals := GlbSceneCache.missing(PackedStringArray(candidate.there.get("visualScenes", [])))
		var error := _thread.start(WorldLoader.prepare_detached.bind(path, MapSceneCache.is_enabled(), visuals))
		if error != OK:
			_thread = null
			_retry_after[map_id] = Time.get_ticks_msec() + 30000
			_record("failed", map_id, {"error": error_string(error)})
		else:
			_record("requested", map_id, {"distance": candidate.distance})
		break

func _process(_delta: float) -> void:
	_drain_retired()
	if _thread == null or _thread.is_alive():
		return
	var builder := _thread.wait_to_finish() as WorldLoader
	_thread = null
	var map_id := _pending_map
	_pending_map = ""
	if builder == null:
		_retry_after[map_id] = Time.get_ticks_msec() + 30000
		return
	var resident := builder.release_world()
	builder.free()
	if resident.root == null:
		_retry_after[map_id] = Time.get_ticks_msec() + 30000
		_record("failed", map_id)
		return
	var imported := resident.root as Node3D
	# Login, teleport, disconnect or a second map change can supersede a load.
	if _pending_generation != _generation or map_id == active_map or not _nearby(map_id):
		_retire(resident, map_id)
		_record("discarded", map_id)
		return
	imported.visible = false
	_set_collision(imported, false)
	add_child(imported)
	residents[map_id] = resident
	MapSceneCache.note_local_digest((resident.manifest as WorldManifest).asset_id(), str(resident.digest))
	_record("ready", map_id, {"load_ms": float(resident.phases.get(&"total", 0)) / 1000.0})
	_refresh_views()

func _nearby(map_id: String) -> bool:
	var count := 0
	for item: Dictionary in _candidates(_last_position):
		if count >= maximum_neighbours:
			break
		if str(item.map) == map_id and float(item.distance) <= retain_distance:
			return true
		count += 1
	return false

func _candidates(position: Vector3) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for link: Dictionary in links:
		var ends: Array = link.ends
		for index: int in 2:
			if str(ends[index].map) != active_map:
				continue
			var here: Dictionary = ends[index]
			var there: Dictionary = ends[1 - index]
			var at := _vector(here.position)
			result.append({"map": str(there.map), "distance": Vector2(position.x - at.x, position.z - at.z).length(),
				"here": here, "there": there, "seamless": bool(link.get("seamless", false))})
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a.distance) < float(b.distance))
	return result

## Transfer already-instantiated nodes. A surveyed join rebases the old world
## and camera into the destination's coordinate frame; nothing moves on screen.
func take_ready(destination: String, loader: WorldLoader, position: Vector3) -> Dictionary:
	last_handoff = {}
	if not residents.has(destination):
		return {}
	var join: Dictionary = {}
	for candidate: Dictionary in _candidates(position):
		if str(candidate.map) == destination:
			join = candidate
			break
	# Render interpolation can trail an authoritative crossing during a slow
	# frame. The surveyed approach, not a tiny radius around the trigger, is
	# the continuous-travel zone.
	var collar := float(join.get("here", {}).get("frame", {}).get("collarDepth", 42))
	var continuous := bool(join.get("seamless", false)) and float(join.get("distance", INF)) < collar
	var resident: Dictionary = residents[destination]
	residents.erase(destination)
	var rebase := Transform3D.IDENTITY
	if continuous:
		rebase = frame_transform(join.here.frame, join.there.frame).affine_inverse()
		var previous := loader.release_world(false)
		var old := previous.root as Node3D
		_set_collision(old, false)
		old.transform = rebase
		residents[active_map] = previous
	else:
		for stale: String in residents.keys():
			_evict(stale)
	var imported := resident.root as Node3D
	_set_view(imported)
	_set_collision(imported, true)
	imported.visible = true
	_generation += 1
	last_handoff = {"from": active_map, "to": destination, "continuous": continuous,
		"rebase": rebase, "root_id": imported.get_instance_id(), "source_distance": join.get("distance", INF)}
	_record("handoff", destination, {"continuous": continuous})
	return {"resident": resident, "continuous": continuous, "rebase": rebase}

func _refresh_views() -> void:
	if not is_instance_valid(active_root):
		return
	_set_view(active_root)
	var visible_borders: Dictionary = {}
	for candidate: Dictionary in _candidates(_last_position):
		var map_id := str(candidate.map)
		if not residents.has(map_id):
			continue
		var imported := residents[map_id].root as Node3D
		if bool(candidate.seamless):
			var identity := str(candidate.there.frame.id)
			imported.transform = frame_transform(candidate.here.frame, candidate.there.frame)
			imported.visible = true
			_set_view(imported, identity)
			_set_collision(imported, false, true, identity)
			visible_borders[str(candidate.here.frame.id)] = true
		else:
			imported.visible = false
			_set_collision(imported, false)
	_set_overflow(active_root, visible_borders)

static func _set_view(imported: Node3D, border := "") -> void:
	var active := imported.get_node_or_null("StreamActive") as Node3D
	if active == null:
		return
	active.visible = border.is_empty()
	for node: Node in imported.get_children():
		if node.has_meta("stream_borders"):
			(node as Node3D).visible = border.is_empty() or border in node.get_meta("stream_borders")
		if str(node.name).begins_with("StreamPreview_"):
			(node as Node3D).visible = str(node.name) == "StreamPreview_" + border

static func frame_transform(here: Dictionary, there: Dictionary) -> Transform3D:
	var outward := Vector3(float(here.outward[0]), 0, float(here.outward[1]))
	var incoming := -Vector3(float(there.outward[0]), 0, float(there.outward[1]))
	var angle := atan2(outward.x, outward.z) - atan2(incoming.x, incoming.z)
	var basis := Basis(Vector3.UP, angle)
	return Transform3D(basis, _vector(here.anchor) - basis * _vector(there.anchor))

static func _vector(raw: Array) -> Vector3:
	return Vector3(float(raw[0]), float(raw[1]), float(raw[2]))

static func _set_collision(imported: Node3D, enabled: bool, preview_enabled := false, border := "") -> void:
	var mode := str(enabled) + ":" + str(preview_enabled) + ":" + border
	if imported.get_meta("stream_physics", "") == mode:
		return
	var has_views := imported.has_node("StreamActive")
	var shared := bool(imported.get_meta("shared_stream_cells", false))
	for node: Node in imported.find_children("*", "CollisionObject3D", true, false):
		var body := node as CollisionObject3D
		if not body.has_meta("stream_collision_layer"):
			body.set_meta("stream_collision_layer", body.collision_layer)
		var original := int(body.get_meta("stream_collision_layer"))
		var view := ""
		var cells: Array = []
		var threshold := false
		var ancestor := body.get_parent()
		while ancestor != null and ancestor != imported:
			if ancestor.has_meta("stream_borders"): cells = ancestor.get_meta("stream_borders")
			if ancestor.has_meta("stream_threshold"): threshold = true
			if str(ancestor.name).begins_with("StreamPreview_"):
				view = str(ancestor.name).trim_prefix("StreamPreview_")
				break
			ancestor = ancestor.get_parent()
		var preview := 0
		if (preview_enabled and (original & WorldLoader.NAVIGATION_SURFACE_LAYER) != 0
				and (border in cells and not threshold if shared else
					(view == border if has_views else not "_StreamOverflow" in str(body.get_parent().name)))):
			preview = PREVIEW_SURFACE_LAYER
		body.collision_layer = (original if shared or view.is_empty() else 0) if enabled else preview
	imported.set_meta("stream_physics", mode)

static func _set_overflow(imported: Node3D, visible_borders: Dictionary) -> void:
	var key := JSON.stringify(visible_borders)
	if imported.get_meta("stream_overflow_visible", "") == key:
		return
	for node: Node in imported.find_children("*_StreamOverflow*", "Node3D", true, false):
		var title := str(node.name)
		var identity := title.get_slice("_StreamOverflow_", 1) if "_StreamOverflow_" in title else ""
		(node as Node3D).visible = not visible_borders.has(identity) if not identity.is_empty() else visible_borders.is_empty()
	imported.set_meta("stream_overflow_visible", key)

func _evict(map_id: String) -> void:
	var resident: Dictionary = residents[map_id]
	residents.erase(map_id)
	_retire(resident, map_id)
	_record("evicted", map_id, {"retiring": _retiring.size()})

func _can_dispatch_preload() -> bool:
	return _thread == null and _retiring.is_empty()

func _retire(resident: Dictionary, map_id: String) -> void:
	var imported := resident.root as Node3D
	imported.visible = false
	_set_collision(imported, false)
	imported.process_mode = Node.PROCESS_MODE_DISABLED
	# Keep the root attached: remove_child/queue_free on the complete tree
	# would unregister all renderer/physics instances in one handoff frame.
	# Prepared visual PackedScenes are released separately after the nodes;
	# dropping their complete dictionary here would merely move the spike.
	_retiring.append({"resident": resident, "map": map_id, "stack": [imported],
		"visual_keys": (resident.get("visuals", {}) as Dictionary).keys(),
		"freed": 0, "released_visuals": 0, "release_usec": 0, "max_slice_usec": 0})

func _drain_retired(max_nodes := RETIRE_NODES_PER_FRAME,
		budget_usec := RETIRE_BUDGET_USEC) -> int:
	var began := Time.get_ticks_usec()
	var freed := 0
	while not _retiring.is_empty() and freed < max_nodes and Time.get_ticks_usec() - began < budget_usec:
		var retired: Dictionary = _retiring[0]
		var stack: Array = retired.stack
		var visual_keys: Array = retired.visual_keys
		if stack.is_empty():
			var visuals: Dictionary = retired.resident.get("visuals", {})
			var release_started := Time.get_ticks_usec()
			visuals.erase(visual_keys.pop_back())
			retired.release_usec += Time.get_ticks_usec() - release_started
			retired.released_visuals += 1
			freed += 1
		else:
			var node: Variant = stack.back()
			if not is_instance_valid(node):
				stack.pop_back()
			elif node.get_child_count() > 0:
				# Walk down only one branch at a time; even descent through a very
				# deep import is covered by the time budget. Last-child removal
				# avoids repeatedly shifting a wide sibling array.
				stack.append(node.get_child(node.get_child_count() - 1))
			else:
				stack.pop_back()
				var release_started := Time.get_ticks_usec()
				node.free()
				retired.release_usec += Time.get_ticks_usec() - release_started
				retired.freed += 1
				freed += 1
		retired.max_slice_usec = maxi(int(retired.max_slice_usec), Time.get_ticks_usec() - began)
		if stack.is_empty() and visual_keys.is_empty():
			_record("retired", str(retired.map), {"nodes": retired.freed,
				"visuals": retired.released_visuals,
				"max_slice_ms": float(retired.max_slice_usec) / 1000.0,
				"release_ms": float(retired.release_usec) / 1000.0})
			_retiring.pop_front()
	return freed

func lighting_manifest(position: Vector3) -> WorldManifest:
	if active_manifest == null:
		return null
	for candidate: Dictionary in _candidates(position):
		if not bool(candidate.seamless) or not residents.has(str(candidate.map)):
			continue
		var here: Dictionary = candidate.here.frame
		var normal := Vector3(float(here.outward[0]), 0, float(here.outward[1]))
		var depth := (position - _vector(here.anchor)).dot(normal)
		var width := float(here.get("blendDistance", 65))
		if depth <= -width:
			continue
		var weight := smoothstep(-width, width, depth)
		var other: WorldManifest = residents[str(candidate.map)].manifest
		var far: Dictionary = other.data.get("environment", {}).duplicate(true)
		# A region's authored sun direction must never turn the shared sun as
		# the player approaches it. Blend its colour/energy and atmosphere only.
		for block: Dictionary in [far, far.get("goldenHour", {})]:
			var sun: Dictionary = block.get("sun", {})
			sun.erase("direction")
			sun.erase("rotationDegrees")
		var blended := WorldManifest.new()
		blended.source_path = active_manifest.source_path
		blended.data = active_manifest.data.duplicate()
		blended.data.environment = _blend(active_manifest.data.get("environment", {}), far, weight)
		return blended
	return active_manifest

static func _blend(a: Variant, b: Variant, weight: float) -> Variant:
	if a is Dictionary and b is Dictionary:
		var result: Dictionary = a.duplicate(true)
		for key: Variant in b:
			result[key] = _blend(a[key], b[key], weight) if a.has(key) else b[key]
		return result
	if a is Array and b is Array and a.size() == b.size():
		var values: Array = []
		for index: int in a.size():
			values.append(_blend(a[index], b[index], weight))
		return values
	if (a is float or a is int) and (b is float or b is int):
		return lerpf(float(a), float(b), weight)
	return a

func clear() -> void:
	_generation += 1
	active_map = ""
	active_root = null
	active_manifest = null
	for map_id: String in residents.keys():
		_evict(map_id)
	_retry_after.clear()
	pending_walk.clear()

func pick_neighbor(space: PhysicsDirectSpaceState3D, origin: Vector3, direction: Vector3, run: bool) -> Variant:
	pending_walk.clear()
	var query := PhysicsRayQueryParameters3D.create(origin, origin + direction * 2000, PREVIEW_SURFACE_LAYER)
	var hit := space.intersect_ray(query)
	if hit.is_empty():
		return null
	var point: Vector3 = hit.position
	var foreground := space.intersect_ray(PhysicsRayQueryParameters3D.create(
		origin, origin + direction * 2000, WorldLoader.NAVIGATION_SURFACE_LAYER))
	if (not foreground.is_empty()
			and not "_StreamOverflow" in str(foreground.collider.get_parent().name)
			and not "_StreamThreshold" in str(foreground.collider.get_parent().name)
			and origin.distance_squared_to(foreground.position) + .01 < origin.distance_squared_to(point)):
		return null
	for candidate: Dictionary in _candidates(_last_position):
		var map_id := str(candidate.map)
		if not bool(candidate.seamless) or not residents.has(map_id):
			continue
		var imported := residents[map_id].root as Node3D
		if not imported.is_ancestor_of(hit.collider):
			continue
		var frame: Dictionary = candidate.here.frame
		var outward := Vector3(float(frame.outward[0]), 0, float(frame.outward[1]))
		var anchor := _vector(frame.anchor)
		if (point - anchor).dot(outward) <= 0:
			continue
		var target_manifest := residents[map_id].manifest as WorldManifest
		var adapter := target_manifest.coordinate_adapter()
		var tile := adapter.godot_to_server(imported.transform.affine_inverse() * point)
		var dimensions: Variant = target_manifest.data.get("coordinateTransform", {}).get("serverCells",
			target_manifest.data.get("asset", {}).get("serverCells", 0))
		var width := int(dimensions[0]) if dimensions is Array else int(dimensions)
		var height := int(dimensions[1]) if dimensions is Array else width
		if tile.x < 0 or tile.y < 0 or (width > 0 and (tile.x >= width or tile.y >= height)):
			return null
		pending_walk = {"map": map_id, "tile": tile, "run": run, "world_point": point}
		# Route through the centre of the surveyed road. The server decides
		# whether the approach and the continuation are walkable.
		return _vector(candidate.here.position)
	return null

func take_continuation(map_id: String) -> Dictionary:
	if pending_walk.get("map", "") != map_id:
		return {}
	var result := pending_walk.duplicate()
	pending_walk.clear()
	return result

func is_idle() -> bool:
	return _thread == null and _retiring.is_empty()

func _record(kind: String, map_id: String, detail := {}) -> void:
	var entry := {"event": kind, "map": map_id, "at_ms": Time.get_ticks_msec()}
	entry.merge(detail)
	events.append(entry)
	if events.size() > 100:
		events.pop_front()
	print("exterior_stream ", JSON.stringify(entry))
