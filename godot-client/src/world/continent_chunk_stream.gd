class_name ContinentChunkStream
extends Node3D

## A named territory owns metadata; only the selected independent GLBs occupy
## renderer/physics memory. Coordinates in every cell remain territory-local.
## This root itself transfers during exterior adoption, retaining loaded cells.
const DEFAULT_PRELOAD_DISTANCE := 240.0
const DEFAULT_RETAIN_DISTANCE := 320.0
const DEFAULT_MAXIMUM_CHUNKS := 64
const DEFAULT_RESIDENT_BYTES := 268435456
const RETIRE_NODES_PER_FRAME := 64
const RETIRE_BUDGET_USEC := 2000

signal cell_ready(identity: String, imported: Node3D)
signal cell_retiring(identity: String, imported: Node3D)

var territory: WorldManifest
var cells: Dictionary = {}
var entries: Array[Dictionary] = []
var preload_distance := DEFAULT_PRELOAD_DISTANCE
var retain_distance := DEFAULT_RETAIN_DISTANCE
var maximum_chunks := DEFAULT_MAXIMUM_CHUNKS
var maximum_resident_bytes := DEFAULT_RESIDENT_BYTES
var resident_bytes := 0
var focus := Vector3.ZERO
var has_focus := false
## First authoritative/preload position, retained for cold-arrival diagnostics.
var initial_focus := Vector3.INF
var events: Array[Dictionary] = []
var revision := 0
var _cache_enabled := true
var _thread: Thread
var _pending: Dictionary = {}
var _paused := false
var _retry_after: Dictionary = {}
var _retiring: Array[Dictionary] = []
var _next_update := 0
var _physics_enabled := true
var _preview_enabled := false
## Import workers whose owner left the tree or re-primed before they finished.
## A worker may be waiting on rendering-server commands that only the main
## thread services, so joining it synchronously deadlocks the client; the
## exterior stream reaps these once they report finished.
static var _orphans: Array[Dictionary] = []

static func _orphan(thread: Thread, entry: Dictionary) -> void:
	_orphans.append({"thread": thread, "entry": entry})

static func orphans_pending() -> int:
	return _orphans.size()

static func reap_orphans() -> int:
	var remaining: Array[Dictionary] = []
	for orphan: Dictionary in _orphans:
		var thread := orphan.thread as Thread
		if thread.is_alive():
			remaining.append(orphan)
			continue
		var builder := thread.wait_to_finish() as WorldLoader
		if builder != null:
			var resident := builder.release_world()
			builder.free()
			if resident.root != null:
				(resident.root as Node).queue_free()
	_orphans = remaining
	return _orphans.size()

func _release_worker(position: Vector3, install_if_near: bool) -> void:
	if _thread == null:
		return
	var pending := _pending
	_pending = {}
	if _thread.is_alive():
		# Never block the main thread on a live import.
		_orphan(_thread, pending)
		_thread = null
		_record("orphaned", str(pending.get("id", "")))
		return
	var builder := _thread.wait_to_finish() as WorldLoader
	_thread = null
	if install_if_near and bounds_distance(position, pending.bounds) <= preload_distance:
		_install(pending, builder)
	else:
		_discard_builder(pending, builder)

func configure(source: WorldManifest, cache_enabled: bool) -> void:
	territory = source
	_cache_enabled = cache_enabled
	set_meta("shared_stream_cells", true)
	var config: Dictionary = source.data.streamingChunks
	preload_distance = maxf(0, float(config.get("preloadDistance", DEFAULT_PRELOAD_DISTANCE)))
	retain_distance = maxf(preload_distance, float(config.get("retainDistance", DEFAULT_RETAIN_DISTANCE)))
	maximum_chunks = maxi(1, int(config.get("maximumLoadedChunks", DEFAULT_MAXIMUM_CHUNKS)))
	maximum_resident_bytes = maxi(1, int(config.get("maximumResidentBytes", DEFAULT_RESIDENT_BYTES)))
	for value: Dictionary in config.chunks:
		var entry := value.duplicate(true)
		entry.path = source.source_path.get_base_dir().path_join(str(entry.manifest))
		# Exporters should provide decoded geometry/texture/collision estimates.
		# The fallback deliberately exceeds packed file size; this is accounting,
		# not a claim that GPU/driver allocations can be measured from a manifest.
		entry.estimatedResidentBytes = maxi(1, int(entry.get("estimatedResidentBytes",
			maxi(1048576, int(entry.get("byteLength", 1048576)) * 12))))
		entries.append(entry)

static func bounds_distance(position: Vector3, bounds: Dictionary) -> float:
	var lower: Array = bounds.min
	var upper: Array = bounds.max
	var dx := maxf(float(lower[0]) - position.x, maxf(0, position.x - float(upper[0])))
	var dz := maxf(float(lower[2]) - position.z, maxf(0, position.z - float(upper[2])))
	return Vector2(dx, dz).length()

static func incremental_cost(entry: Dictionary, shared: Dictionary) -> int:
	# Decoded textures are pooled by content hash. Count each hash once across
	# the prospective resident set, while keeping legacy all-in estimates valid.
	if not entry.has("geometryResidentBytes"):
		return int(entry.estimatedResidentBytes)
	var cost := maxi(1, int(entry.geometryResidentBytes))
	for identity: String in entry.get("sharedResourceResidentBytes", {}):
		var bytes := maxi(0, int(entry.sharedResourceResidentBytes[identity]))
		var previous := int(shared.get(identity, 0))
		cost += maxi(0, bytes - previous)
		shared[identity] = maxi(previous, bytes)
	return cost

func selection(position: Vector3, retain := false) -> Array[Dictionary]:
	var candidates: Array[Dictionary] = []
	for entry: Dictionary in entries:
		var distance := bounds_distance(position, entry.bounds)
		var limit := retain_distance if retain and cells.has(str(entry.id)) else preload_distance
		if distance <= limit:
			var candidate := entry.duplicate()
			candidate.distance = distance
			candidates.append(candidate)
	candidates.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.id) < str(b.id) if is_equal_approx(a.distance, b.distance) else a.distance < b.distance)
	var selected: Array[Dictionary] = []
	var estimated := 0
	var shared: Dictionary = {}
	for candidate: Dictionary in candidates:
		var cost := incremental_cost(candidate, shared)
		# Never substitute a farther cheap cell for the nearest terrain. Allow
		# one oversize cell so a low budget cannot remove the arrival surface.
		if selected.size() >= maximum_chunks or (not selected.is_empty() and estimated + cost > maximum_resident_bytes):
			break
		selected.append(candidate)
		estimated += cost
	return selected

## Called before the first actor grounding, with the server's actual arrival.
## No default-spawn cells are read when the client is waiting for that packet.
func prime(position: Vector3) -> void:
	if has_focus:
		return
	focus = position
	has_focus = true
	if not initial_focus.is_finite():
		initial_focus = position
	for entry: Dictionary in selection(position):
		if cells.has(str(entry.id)):
			continue
		var builder := WorldLoader.prepare_detached(str(entry.path), _cache_enabled)
		_install(entry, builder)

func ensure_position(position: Vector3) -> bool:
	if not has_focus:
		prime(position)
		return true
	for resident: Dictionary in cells.values():
		if bounds_distance(position, resident.entry.bounds) <= .01:
			return false
	var wanted := selection(position)
	if wanted.is_empty():
		return false
	# Same-territory teleports do not necessarily create a new map root. Ground
	# the actual destination before constructing the actor there. The ordinary
	# 240m lead keeps this synchronous fallback off the continuous walk path.
	focus = position
	_release_worker(position, true)
	var keep: Dictionary = {}
	for entry: Dictionary in wanted:
		keep[str(entry.id)] = true
	for identity: String in cells.keys():
		if not keep.has(identity):
			_retire_cell(identity)
	has_focus = false
	prime(position)
	_record("arrival_reprime", "")
	return true

func update_focus(position: Vector3) -> void:
	if not has_focus or _paused:
		return
	focus = position
	if Time.get_ticks_msec() < _next_update:
		return
	_next_update = Time.get_ticks_msec() + 250
	var selected := selection(position, true)
	var wanted: Dictionary = {}
	for entry: Dictionary in selected:
		wanted[str(entry.id)] = true
	for identity: String in cells.keys():
		if not wanted.has(identity):
			_retire_cell(identity)
	if _thread != null or not _retiring.is_empty():
		return
	for entry: Dictionary in selected:
		if cells.has(str(entry.id)) or float(entry.distance) > preload_distance:
			continue
		if Time.get_ticks_msec() < int(_retry_after.get(str(entry.id), 0)):
			continue
		_pending = entry
		_thread = Thread.new()
		var error := _thread.start(WorldLoader.prepare_detached.bind(str(entry.path), _cache_enabled))
		if error != OK:
			_thread = null
			_failed(entry, error_string(error))
		else:
			_record("requested", str(entry.id))
		break

func _process(_delta: float) -> void:
	poll_pending()
	_drain_retired()
	if has_focus and not _paused:
		update_focus(focus)

func poll_pending() -> void:
	if _thread == null or _thread.is_alive():
		return
	var builder := _thread.wait_to_finish() as WorldLoader
	_thread = null
	var entry := _pending
	_pending = {}
	if _paused or bounds_distance(focus, entry.bounds) > retain_distance:
		_discard_builder(entry, builder)
	else:
		_install(entry, builder)

func _install(entry: Dictionary, builder: WorldLoader) -> void:
	if builder == null:
		_failed(entry, "builder_missing")
		return
	var resident := builder.release_world()
	builder.free()
	var imported := resident.root as Node3D
	if imported == null:
		_failed(entry, "chunk_import_failed")
		return
	if not str(entry.get("packageDigest", "")).is_empty() and str(entry.packageDigest) != str(resident.digest):
		imported.free()
		_failed(entry, "chunk_package_digest_mismatch")
		return
	imported.set_meta("continent_chunk_id", str(entry.id))
	ExteriorRegionStream._set_collision(imported, _physics_enabled, _preview_enabled, "", true)
	add_child(imported)
	resident.entry = entry
	cells[str(entry.id)] = resident
	_update_resident_bytes()
	_changed()
	_record("ready", str(entry.id))
	cell_ready.emit(str(entry.id), imported)

func set_physics_mode(enabled: bool, preview: bool) -> void:
	_physics_enabled = enabled
	_preview_enabled = preview

func pause_streaming() -> void:
	_paused = true

func can_retire() -> bool:
	poll_pending()
	return _thread == null

func _retire_cell(identity: String) -> void:
	var resident: Dictionary = cells[identity]
	cells.erase(identity)
	var imported := resident.root as Node3D
	cell_retiring.emit(identity, imported)
	imported.visible = false
	ExteriorRegionStream._set_collision(imported, false)
	_retiring.append({"root": imported, "stack": [imported], "entry": resident.entry})
	_changed()
	_record("evicted", identity)

func _discard_builder(entry: Dictionary, builder: WorldLoader) -> void:
	if builder == null:
		return
	var resident := builder.release_world()
	builder.free()
	if resident.root != null:
		var imported := resident.root as Node3D
		imported.visible = false
		add_child(imported)
		_retiring.append({"root": imported, "stack": [imported], "entry": entry})
		_update_resident_bytes()
	_record("discarded", str(entry.id))

func _drain_retired() -> void:
	var began := Time.get_ticks_usec()
	var freed := 0
	while not _retiring.is_empty() and freed < RETIRE_NODES_PER_FRAME and Time.get_ticks_usec() - began < RETIRE_BUDGET_USEC:
		var retired: Dictionary = _retiring[0]
		var stack: Array = retired.stack
		var node: Node = stack.back()
		if node.get_child_count() > 0:
			stack.append(node.get_child(node.get_child_count() - 1))
		else:
			stack.pop_back()
			node.free()
			freed += 1
		if stack.is_empty():
			_retiring.pop_front()
			_update_resident_bytes()

func _update_resident_bytes() -> void:
	resident_bytes = 0
	var shared: Dictionary = {}
	for resident: Dictionary in cells.values():
		resident_bytes += incremental_cost(resident.entry, shared)
	# Hidden retirement nodes still hold materials and textures until freed.
	for retired: Dictionary in _retiring:
		resident_bytes += incremental_cost(retired.entry, shared)

func _changed() -> void:
	revision += 1
	# Existing exterior collision/view caches must see newly attached cells.
	if has_meta("stream_physics"):
		remove_meta("stream_physics")

func _failed(entry: Dictionary, reason: String) -> void:
	_retry_after[str(entry.id)] = Time.get_ticks_msec() + 30000
	_record("failed", str(entry.id), {"reason": reason})

func _record(kind: String, identity: String, details := {}) -> void:
	var event := {"event": kind, "chunk": identity, "resident_bytes": resident_bytes}
	event.merge(details)
	events.append(event)
	if events.size() > 100:
		events.pop_front()
	print("continent_chunk ", JSON.stringify(event))

func _exit_tree() -> void:
	_paused = true
	# Normal exterior retirement polls completion before freeing any descendant.
	# A map change or disconnect can still free this root while an import is
	# live; that worker is orphaned and reaped later, never joined here.
	if _thread != null:
		if _thread.is_alive():
			_orphan(_thread, _pending)
			_record("orphaned", str(_pending.get("id", "")))
		else:
			var builder := _thread.wait_to_finish() as WorldLoader
			if builder != null:
				builder.free()
		_thread = null
		_pending = {}

func _enter_tree() -> void:
	_paused = false
