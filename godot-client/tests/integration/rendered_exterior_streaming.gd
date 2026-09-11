extends "res://tests/integration/rendered_landscape_walk.gd"

## Real-client proof: retain both scene and traveller identities, transport the
## camera rigidly, sample every rendered handoff, and save adjacent frames.
var _last_map := ""
var _last_camera := Transform3D.IDENTITY
var _last_actor_id := 0
var _last_image: Image
var _handoffs: Array = []
var _frame_times: Array = []
var _peak_neighbours := 0
var _peak_static_bytes := 0.0
var _last_frame_time := 0
var _saving_capture := false
var _crossing_images: Array = []

func _run() -> void:
	RenderingServer.frame_post_draw.connect(_measure_frame)
	await super._run()

func _settle(frames: int) -> void:
	await super._settle(frames)
	if _main == null:
		return
	var stream: ExteriorRegionStream = _main.get("exterior_stream")
	for candidate: Dictionary in stream._candidates(_main.get("camera_rig").focus):
		if bool(candidate.seamless) and float(candidate.distance) < 80 and not stream.residents.has(str(candidate.map)):
			_expect(await _wait(func() -> bool: return stream.residents.has(str(candidate.map)), 60),
				"neighbor became resident before crossing")

func _measure_frame() -> void:
	if not is_instance_valid(_main) or _loader == null or _loader.world_root == null:
		return
	var stream: ExteriorRegionStream = _main.get("exterior_stream")
	var map_id: String = _state.get("current_map")
	var rig: IsometricCameraController = _main.get("camera_rig")
	var actor: Variant = _main.get("actor_nodes").get(int(_state.get("local_actor_id")))
	if not is_instance_valid(actor):
		return
	_peak_neighbours = maxi(_peak_neighbours, stream.residents.size())
	_peak_static_bytes = maxf(_peak_static_bytes, Performance.get_monitor(Performance.MEMORY_STATIC))
	if (map_id != _last_map and not _last_map.is_empty()
			and stream.last_handoff.get("from", "") == _last_map
			and stream.last_handoff.get("to", "") == map_id):
		_expect(bool(stream.last_handoff.get("continuous", false)), "surveyed road uses continuous handoff")
		var expected: Transform3D = stream.last_handoff.rebase * _last_camera
		var current := rig.camera.global_transform
		var translation := expected.origin.distance_to(current.origin)
		var rotation := expected.basis.get_rotation_quaternion().angle_to(current.basis.get_rotation_quaternion())
		var item := {"from": _last_map, "to": map_id, "camera_step_metres": translation,
			"handoff_frame_ms": (Time.get_ticks_usec() - _last_frame_time) / 1000.0 if _last_frame_time > 0 else 0,
			"camera_rotation_degrees": rad_to_deg(rotation), "traveller_retained": actor.get_instance_id() == _last_actor_id,
			"scene_reused": _loader.world_root.get_instance_id() == int(stream.last_handoff.root_id),
			"resident_neighbours": stream.residents.size()}
		item["detail"] = str(stream.last_handoff)
		item["camera_before"] = str(_last_camera)
		item["camera_after"] = str(current)
		_handoffs.append(item)
		_expect(translation < 1.5, "camera crosses without a position jump")
		_expect(rotation < .001, "camera direction and zoom survive the handoff")
		_expect(bool(item.traveller_retained), "same traveller node crosses the border")
		_expect(bool(item.scene_reused), "arrival reuses the preloaded scene")
		_expect(not bool(_main.get("fallback_ground").visible), "no fallback ground frame")
		var stem := "crossing-%02d" % _handoffs.size()
		if _last_image != null:
			_crossing_images.append([stem + "-before.png", _last_image])
		_crossing_images.append([stem + "-after.png", root.get_texture().get_image()])
	var near_border := false
	for candidate: Dictionary in stream._candidates(rig.focus):
		if bool(candidate.seamless) and float(candidate.distance) < 8:
			near_border = true
	if near_border:
		_last_image = root.get_texture().get_image()
		if _last_frame_time > 0 and not _saving_capture:
			_frame_times.append((Time.get_ticks_usec() - _last_frame_time) / 1000.0)
	else:
		_last_image = null
	_last_map = map_id
	_last_camera = rig.camera.global_transform
	_last_actor_id = actor.get_instance_id()
	_last_frame_time = Time.get_ticks_usec()

func _write_report() -> void:
	for capture: Array in _crossing_images:
		(capture[1] as Image).save_png(_artifacts.path_join(capture[0]))
	_crossing_images.clear()
	_last_frame_time = 0
	_report["stream_handoffs"] = _handoffs
	_report["border_frame_ms"] = _frame_times
	_report["peak_resident_neighbours"] = _peak_neighbours
	_report["peak_static_bytes"] = _peak_static_bytes
	_report["stream_events"] = _main.get("exterior_stream").events
	super._write_report()

func _capture(name: String) -> void:
	_saving_capture = true
	await super._capture(name)
	_saving_capture = false
	_last_frame_time = 0
