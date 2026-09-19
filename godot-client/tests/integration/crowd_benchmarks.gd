extends SceneTree
## Controlled native-actor crowd benchmark.
##
## This is deliberately separate from client_benchmarks.gd. That instrument
## keeps its historical hundred-creature result stable; this one varies actor
## composition, visibility, activity and presentation features.

const BENCHMARK_MAIN_PATH := "res://tests/integration/crowd_benchmark_main.tscn"
const MODELS := "res://data/actors/models.json"
const FIRST_ACTOR_ID := 14000
const COUNTS := [100, 200, 300, 500]
const FULL_KIT_A := {0: 114, 1: 106, 2: 0, 3: 117, 4: 171, 5: 184, 6: 192}
const FULL_KIT_B := {0: 164, 1: 111, 2: 1, 3: 109, 4: 172, 5: 185, 6: 193}
const DEFAULT_SAMPLE_MSEC := 2500
const DEFAULT_WARMUP_MSEC := 1000
const DEFAULT_CADENCE_MSEC := 100
const MAX_SPAWN_MSEC := 300000
const MAX_READINESS_MSEC := 60000
const MIN_SAMPLE_FRAMES := 60

var _failures := 0
var _headless := false
var _artifacts := ""
var _main: Control
var _app_state: Node
var _adapter: CoordinateAdapter
var _creatures: Array = []
var _report: Dictionary = {}
var _cell_index := 0
var _capture_enabled := false
var _driver_usec := 0
var _driver_command_usec := 0
var _driver_packets := 0
var _driver_commands := 0
var _driver_state_updates := 0
var _driver_flushes := 0
var _driver_combat_events := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	_headless = DisplayServer.get_name() == "headless"
	OS.low_processor_usage_mode_sleep_usec = 1
	Engine.max_fps = 0
	root.size = Vector2i(1280, 720)
	_artifacts = OS.get_environment("ELORIA_CROWD_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/native-crowd")
	_expect(DirAccess.make_dir_recursive_absolute(_artifacts) == OK,
		"artifact directory is writable")
	_capture_enabled = not _headless and OS.get_environment(
		"ELORIA_CROWD_CAPTURE").strip_edges() == "1"
	_creatures = _creature_actor_types()
	_report = {
		"schemaVersion": 1,
		"label": OS.get_environment("ELORIA_CROWD_LABEL"),
		"runId": _environment_or("ELORIA_CROWD_RUN_ID", "manual"),
		"profile": _environment_or("ELORIA_CROWD_PROFILE", "primary"),
		"display": DisplayServer.get_name(),
		"headless": _headless,
		"requestedRenderingMethod": _environment_or("ELORIA_CROWD_RENDERER",
			str(ProjectSettings.get_setting("rendering/renderer/rendering_method"))),
		"actualRenderingMethod": RenderingServer.get_current_rendering_method(),
		"renderingDevice": RenderingServer.get_video_adapter_name(),
		"commit": OS.get_environment("ELORIA_CROWD_COMMIT"),
		"sourceHash": OS.get_environment("ELORIA_CROWD_SOURCE_HASH"),
		"dirty": OS.get_environment("ELORIA_CROWD_DIRTY") == "1",
		"trial": _environment_int("ELORIA_CROWD_TRIAL", 1, 1),
		"nativeBackend": _environment_or("ELORIA_CROWD_NATIVE_BACKEND", "current"),
		"godot": Engine.get_version_info(),
		"viewport": [root.size.x, root.size.y],
		"sharedMachine": true,
		"interferenceLabel": _environment_or("ELORIA_CROWD_INTERFERENCE",
			"shared host; unrelated Godot jobs may be present"),
		"process": {"pid": OS.get_process_id(), "requestedAffinityMask": 15,
			"requestedWorkerThreads": 2,
			"runnerMetadata": OS.get_environment("ELORIA_CROWD_PROCESS_METADATA")},
		"measurement": {
			"sampleMilliseconds": _environment_int(
				"ELORIA_CROWD_SAMPLE_MSEC", DEFAULT_SAMPLE_MSEC, 250),
			"warmupMilliseconds": _environment_int(
				"ELORIA_CROWD_WARMUP_MSEC", DEFAULT_WARMUP_MSEC, 100),
			"cadenceMilliseconds": _environment_int(
				"ELORIA_CROWD_CADENCE_MSEC", DEFAULT_CADENCE_MSEC, 25),
			"windowWallTimeAuthoritative": false,
			"headlessRenderMetricsAvailable": false,
		},
		"cells": [],
		"failures": [],
		"unixTime": int(Time.get_unix_time_from_system()),
	}
	var user_data := OS.get_user_data_dir().replace("\\", "/")
	var expected_user_root := OS.get_environment("ELORIA_CROWD_USER_ROOT").replace("\\", "/")
	_report["userDataDirectory"] = user_data
	if not _expect(not expected_user_root.is_empty()
			and (user_data == expected_user_root
				or user_data.begins_with(expected_user_root + "/")),
			"Godot user data stays inside the benchmark worktree"):
		_finish()
		return
	if not _expect(not _creatures.is_empty(),
			"creature fixture resolves at least one real native model"):
		_finish()
		return
	_report["creatureTypes"] = _creatures.duplicate(true)
	await _set_up_main()
	if _main == null:
		_finish()
		return
	Engine.max_fps = 0
	_expect(Engine.max_fps == 0, "benchmark frame loop remains uncapped after Main setup")
	await _prewarm_population()
	var cells := profile_cells(str(_report["profile"]))
	cells = _filter_cells(cells)
	_expect(not cells.is_empty(), "profile and filters select at least one cell")
	_report["plannedCells"] = cells.duplicate(true)
	for raw_cell: Variant in cells:
		await _run_cell(raw_cell as Dictionary)
	if str(_report["profile"]) in ["stress", "all"]:
		_report["packetBursts"] = _measure_packet_bursts()
	await _tear_down_main()
	_finish()


static func profile_cells(profile: String) -> Array:
	var primary := {
		"id": "acceptance-mixed300",
		"count": 300,
		"population": "mixed",
		"activity": "third_active",
		"visibility": "half300",
		"features": "full",
		"network": "normal_burst",
	}
	if profile == "primary":
		return [primary]
	var cells: Array = []
	if profile in ["matrix", "all"]:
		for count: int in COUNTS:
			for activity: String in ["idle", "third_active", "all_move", "all_combat"]:
				cells.append({
					"id": "matrix-%d-%s" % [count, activity],
					"count": count, "population": "mixed", "activity": activity,
					"visibility": "half300" if count == 300 else "frustum_half",
					"features": "full", "network": "normal_burst",
				})
	if profile in ["features", "all"]:
		for feature: String in ["full", "bare", "no_cape", "no_effects",
				"no_overhead", "no_ground", "no_animation"]:
			cells.append({
				"id": "features-300-" + feature,
				"count": 300, "population": "humanoid", "activity": "third_active",
				"visibility": "half300", "features": feature,
				"network": "normal_burst",
			})
	if profile in ["stress", "all"]:
		for network: String in ["normal_burst", "asynchronous",
				"folded_turn_attack", "protocol_health_buffs",
				"protocol_unchanged_gear", "protocol_changed_gear_lifecycle"]:
			cells.append({
				"id": "stress-500-" + network,
				"count": 500, "population": "mixed", "activity": "third_active",
				"visibility": "range_bands", "features": "full", "network": network,
			})
	if profile == "custom":
		var counts := _csv_ints_static(OS.get_environment("ELORIA_CROWD_COUNTS"), [300])
		var populations := _csv_static(OS.get_environment("ELORIA_CROWD_POPULATIONS"), ["mixed"])
		var activities := _csv_static(OS.get_environment("ELORIA_CROWD_ACTIVITIES"), ["third_active"])
		var visibilities := _csv_static(OS.get_environment("ELORIA_CROWD_VISIBILITIES"), ["half300"])
		var features := _csv_static(OS.get_environment("ELORIA_CROWD_FEATURES"), ["full"])
		var networks := _csv_static(OS.get_environment("ELORIA_CROWD_NETWORKS"), ["normal_burst"])
		for count: int in counts:
			for population: String in populations:
				for activity: String in activities:
					for visibility: String in visibilities:
						for feature: String in features:
							for network: String in networks:
								cells.append({
									"id": "custom-%d-%s-%s-%s-%s-%s" % [count,
										population, activity, visibility, feature, network],
									"count": count, "population": population,
									"activity": activity, "visibility": visibility,
									"features": feature, "network": network,
								})
	if profile not in ["matrix", "features", "stress", "all", "custom"]:
		return []
	return cells


func _filter_cells(cells: Array) -> Array:
	var filters := {
		"count": _csv_ints(OS.get_environment("ELORIA_CROWD_COUNTS")),
		"population": _csv(OS.get_environment("ELORIA_CROWD_POPULATIONS")),
		"activity": _csv(OS.get_environment("ELORIA_CROWD_ACTIVITIES")),
		"visibility": _csv(OS.get_environment("ELORIA_CROWD_VISIBILITIES")),
		"features": _csv(OS.get_environment("ELORIA_CROWD_FEATURES")),
		"network": _csv(OS.get_environment("ELORIA_CROWD_NETWORKS")),
	}
	var out: Array = []
	for raw: Variant in cells:
		var cell := raw as Dictionary
		var keep := true
		for key: String in filters:
			var allowed: Array = filters[key]
			if allowed.is_empty():
				continue
			keep = keep and (int(cell[key]) in allowed if key == "count"
				else str(cell[key]) in allowed)
		if keep:
			out.append(cell)
	return out


func _set_up_main() -> void:
	var benchmark_scene := load(BENCHMARK_MAIN_PATH) as PackedScene
	if not _expect(benchmark_scene != null, "benchmark Main scene loads"):
		return
	_main = benchmark_scene.instantiate() as Control
	root.add_child(_main)
	await process_frame
	_app_state = root.get_node_or_null("/root/AppState")
	if not _expect(_app_state != null, "AppState is available"):
		_main = null
		return
	var native_active := bool(_app_state.call("native_crowd_reducer_active")) \
		if _app_state.has_method("native_crowd_reducer_active") else false
	_report["nativeBackendActive"] = native_active
	if str(_report["nativeBackend"]) == "native":
		_expect(native_active, "requested native crowd reducer is active")
	elif str(_report["nativeBackend"]) == "gdscript":
		_expect(not native_active, "requested GDScript crowd reducer is active")
	_app_state.set("authenticated", true)
	(_main.get("login_panel") as Control).hide()
	(_main.get("creation_panel") as Control).hide()
	(_main.get("game_view") as Control).show()
	var map_id := _environment_or("ELORIA_CROWD_MAP", "four_gates")
	if map_id != "none":
		_app_state.set("current_map", map_id)
		_main.call("_load_server_map")
		var loader := _main.get("world_loader") as WorldLoader
		var deadline := Time.get_ticks_msec() + MAX_SPAWN_MSEC
		while loader.world_root == null and Time.get_ticks_msec() < deadline:
			await process_frame
		_expect(loader.world_root != null, "benchmark map loads")
	_report["map"] = map_id
	_adapter = _main.get("adapter") as CoordinateAdapter
	_report["worldReadiness"] = await _wait_for_world_readiness("initial map", 1500)
	var viewport := _world_viewport()
	RenderingServer.viewport_set_measure_render_time(root.get_viewport_rid(), true)
	if viewport != null:
		RenderingServer.viewport_set_measure_render_time(viewport.get_viewport_rid(), true)
	await _settle_frames(8)


func _tear_down_main() -> void:
	if _main == null:
		return
	_app_state.set("actors", {})
	_main.call("_sync_world")
	await _drain_streaming_before_teardown()
	_main.call("_clear_world_presentation")
	await _settle_frames(2)
	_main.queue_free()
	await _settle_frames(4)
	NativeAnimationImporter.clear()
	GlbSceneCache.clear()


func _prewarm_population() -> void:
	var records := _make_records(2, "mixed", "full")
	_app_state.set("local_actor_id", FIRST_ACTOR_ID)
	_app_state.set("actors", records)
	_app_state.call("mark_all_actors_changed")
	await _spawn_all(2)
	_app_state.set("actors", {})
	_main.call("_sync_world")
	await _settle_frames(6)
	_main.call("benchmark_reset_frame")
	_report["prewarmed"] = {
		"models": GlbSceneCache.cached_scene_count(),
		"animationLibraries": NativeAnimationImporter.cached_library_count(),
		"includes": ["one equipped luminous humanoid", "one creature"],
	}


func _run_cell(spec: Dictionary) -> void:
	_cell_index += 1
	var count := int(spec["count"])
	var before := _memory_sample()
	var records := _make_records(count, str(spec["population"]), str(spec["features"]))
	_app_state.set("local_actor_id", FIRST_ACTOR_ID)
	_app_state.set("actors", records)
	_app_state.call("mark_all_actors_changed")
	_main.set("benchmark_ground_enabled", str(spec["features"]) != "no_ground")
	_main.set("benchmark_overhead_enabled", str(spec["features"]) != "no_overhead")
	_main.set("benchmark_animation_enabled", str(spec["features"]) != "no_animation")
	_main.set("_effects_enabled", str(spec["features"]) != "no_effects")
	var spawn_started := Time.get_ticks_usec()
	var spawn := await _spawn_all(count)
	spawn["milliseconds"] = _round(float(Time.get_ticks_usec() - spawn_started) / 1000.0)
	var nodes := _main.get("actor_nodes") as Dictionary
	_apply_feature_switches(nodes, str(spec["features"]))
	await _place_population(nodes, records, str(spec["visibility"]))
	var selected_actor_id := FIRST_ACTOR_ID + mini(1, count - 1)
	_app_state.set("selected_actor_id", selected_actor_id)
	_main.call("_sync_selection")
	_main.call("_sync_overhead_health")
	var expected_visible := count / 2 if str(spec["visibility"]) in [
		"half300", "frustum_half", "range_bands"] else count
	var census := _census(nodes)
	var grounding := _grounding_census(nodes)
	_expect(int(census["total"]) == count,
		"%s has exactly %d actor nodes" % [spec["id"], count])
	_expect(int(census["frustumAndDrawVisible"]) == expected_visible,
		"%s has exactly %d camera-visible actors (got %d)" % [spec["id"],
			expected_visible, census["frustumAndDrawVisible"]])
	_expect(int(census["heightSynchronized"]) == count,
		"%s has %d finite grounded actor heights (got %d)" % [spec["id"],
			count, census["heightSynchronized"]])
	if str(spec["features"]) == "no_overhead":
		_expect(int(census["visibleNameplates"]) == 0
			and int(census["visibleHealthBars"]) == 0,
			"%s keeps both nameplates and health bars disabled" % spec["id"])
	if str(_report["map"]) != "none" and str(spec["features"]) != "no_ground":
		_expect(int(grounding["surfaceMatches"]) == count,
			"%s places all %d actors on sampled world surfaces (got %d, %d misses)" % [
				spec["id"], count, grounding["surfaceMatches"], grounding["surfaceMisses"]])
	var readiness := await _wait_for_world_readiness(str(spec["id"]) + " fixture", 500)
	var active_ids := _active_ids(nodes, str(spec["activity"]))
	var workload := _workload_plan(active_ids, str(spec["activity"]))
	if count == 300 and str(spec["activity"]) == "third_active":
		_expect(active_ids.size() == 100,
			"%s has exactly 100 workload-active actors" % spec["id"])
		_expect(int(workload["moving"]) == 50 and int(workload["fighting"]) == 50,
			"%s splits the 100 active actors into 50 moving and 50 fighting" % spec["id"])
	var diagnostics := _actor_diagnostics(nodes, spec)
	if str(spec["features"]) == "full":
		_expect(int(diagnostics["fullyEquippedHumanoids"]) == int(census["humanoids"]),
			"%s equips every humanoid with the declared seven-part kit" % spec["id"])
	var spawned_memory := _memory_sample()
	var initial_equipment := _equipment_snapshot(active_ids)
	var protocol_errors_before := (_app_state.get("recent_protocol_errors") as Array).size()
	await _prime_activity(spec, active_ids)
	await _warm_for(spec, active_ids)
	var sample := await _sample_cell(spec, active_ids)
	sample["workloadValidation"] = _validate_executed_workload(spec, workload, sample)
	if str(spec["features"]) == "no_effects":
		var effect_summary := (sample["summary"] as Dictionary).get(
			"transientWorldEffects", {}) as Dictionary
		_expect(int(effect_summary.get("max", -1)) == 0,
			"%s spawns no WorldEffect3D nodes" % spec["id"])
	if str(spec["features"]) == "no_animation":
		_expect(int((sample["activityObserved"] as Dictionary).get(
			"activeAnimationPlayers", -1)) == 0,
			"%s keeps every AnimationPlayer inactive during the sample" % spec["id"])
	var network_integrity := _network_integrity(spec, active_ids,
		initial_equipment, protocol_errors_before)
	var census_after := _census(nodes)
	var visibility_span := await _validate_visibility_span(spec, active_ids,
		expected_visible)
	_expect(int(census_after["frustumAndDrawVisible"]) == expected_visible,
		"%s preserves %d camera-visible actors after the timed workload" % [
			spec["id"], expected_visible])
	if _capture_enabled and count == 300 and str(spec["activity"]) != "idle" \
			and str(spec["features"]) == "full":
		await _capture_cell(str(spec["id"]) + "-active.png")
		await _settle_milliseconds(1500)
		await _capture_cell(str(spec["id"]) + "-settled.png")
	var despawn_started := Time.get_ticks_usec()
	_app_state.set("actors", {})
	_main.call("_sync_world")
	await _settle_frames(8)
	var despawn_msec := _round(float(Time.get_ticks_usec() - despawn_started) / 1000.0)
	var after := _memory_sample()
	var result := spec.duplicate(true)
	result["spawn"] = spawn
	result["fixture"] = {"before": census, "after": census_after,
		"grounding": grounding,
		"visibilityValidation": visibility_span}
	result["resourceReadiness"] = readiness
	result["diagnostics"] = diagnostics
	result["networkIntegrity"] = network_integrity
	result["selectedActorId"] = selected_actor_id
	result["plannedActive"] = active_ids.size()
	result["plannedWorkload"] = workload
	result["sample"] = sample
	result["despawnMilliseconds"] = despawn_msec
	result["memory"] = {
		"before": before, "spawned": spawned_memory, "afterDespawn": after,
		"spawnDelta": _memory_delta(before, spawned_memory),
		"retainedAfterDespawnIncludingHarnessTelemetry": _memory_delta(before, after),
	}
	(_report["cells"] as Array).append(result)
	print("crowd cell ", spec["id"], ": ", count, " actors, ",
		census["frustumAndDrawVisible"], " visible, ", active_ids.size(), " active")


func _validate_executed_workload(spec: Dictionary, workload: Dictionary,
		sample: Dictionary) -> Dictionary:
	var raw := sample.get("raw", {}) as Dictionary
	var commands := int(_sum_numeric(raw.get("commandsPerFrame", []) as Array))
	var observed := sample.get("activityObserved", {}) as Dictionary
	var physics_processing := int(observed.get("physicsProcessing", 0))
	var actions := observed.get("actions", {}) as Dictionary
	var non_idle_actions := 0
	for action: Variant in actions:
		if str(action) != "idle":
			non_idle_actions += int(actions[action])
	var planned_active := int(workload.get("active", 0))
	var planned_moving := int(workload.get("moving", 0))
	if planned_active > 0:
		_expect(commands > 0, "%s executed actor commands during the sample" % spec["id"])
		_expect(non_idle_actions >= planned_active,
			"%s shows all %d workload actors in non-idle actions (got %d)" % [
				spec["id"], planned_active, non_idle_actions])
	if planned_moving > 0:
		_expect(physics_processing >= planned_moving,
			"%s shows all %d moving actors processing physics (got %d)" % [
				spec["id"], planned_moving, physics_processing])
	var passed := commands > 0 and non_idle_actions >= planned_active \
		and physics_processing >= planned_moving if planned_active > 0 else commands == 0
	return {
		"commands": commands,
		"nonIdleActions": non_idle_actions,
		"physicsProcessing": physics_processing,
		"plannedActive": planned_active,
		"plannedMoving": planned_moving,
		"passed": passed,
	}
func _validate_visibility_span(spec: Dictionary, active_ids: Array[int],
		expected: int) -> Dictionary:
	var minimum := 1 << 30
	var maximum := -1
	var values: Array[int] = []
	for _index: int in range(10):
		await process_frame
		var current := int(_census(_main.get("actor_nodes") as Dictionary)[
			"frustumAndDrawVisible"])
		values.append(current)
		minimum = mini(minimum, current)
		maximum = maxi(maximum, current)
	_expect(minimum == expected and maximum == expected,
		"%s visibility stays exactly %d during an untimed validation span (got %d-%d)" % [
			spec["id"], expected, minimum, maximum])
	return {"samples": values, "min": minimum, "max": maximum}


func _make_records(count: int, population: String, features: String) -> Dictionary:
	var records: Dictionary = {}
	var centre := Vector2i(roundi(_adapter.server_origin.x), roundi(_adapter.server_origin.y))
	for index: int in range(count):
		# The local actor is always a real equipped humanoid, including a
		# creature-heavy diagnostic. It remains inside the requested total.
		var humanoid := index == 0 or population == "humanoid" \
			or (population == "mixed" and index % 2 == 0)
		var actor_type := 1
		var name := "Equipped humanoid"
		var kind := 1
		if not humanoid:
			var pick: Dictionary = _creatures[index % _creatures.size()] as Dictionary
			actor_type = int(pick["actorType"])
			name = str(pick["model"])
			kind = 5
		var equipment := {}
		if humanoid and features != "bare":
			equipment = _equipment_for(index, features)
		var id := FIRST_ACTOR_ID + index
		records[id] = {
			"actor_id": id, "x": centre.x, "y": centre.y,
			"rotation": (index * 977) % 65536, "actor_type": actor_type,
			"kind": kind, "name": name, "health": 80, "max_health": 100,
			"alive": true, "appearance": {}, "equipment_visuals": equipment,
			"equipment_fallback_parts": [],
		}
	return records


func _equipment_for(index: int, features: String) -> Dictionary:
	var kit: Dictionary = (FULL_KIT_A if index % 4 < 2 else FULL_KIT_B).duplicate()
	if features == "no_cape":
		kit.erase(2)
	return kit


func _spawn_all(count: int) -> Dictionary:
	var nodes := _main.get("actor_nodes") as Dictionary
	var passes := 0
	var deadline := Time.get_ticks_msec() + MAX_SPAWN_MSEC
	while nodes.size() < count and Time.get_ticks_msec() < deadline:
		_main.call("_sync_world", _app_state.call("take_changed_actors"))
		passes += 1
		await process_frame
		nodes = _main.get("actor_nodes") as Dictionary
	_expect(nodes.size() == count,
		"spawn completes before timeout (%d of %d)" % [nodes.size(), count])
	return {"passes": passes, "spawned": nodes.size(), "timeoutMilliseconds": MAX_SPAWN_MSEC}


func _apply_feature_switches(nodes: Dictionary, features: String) -> void:
	for value: Variant in nodes.values():
		if not is_instance_valid(value):
			continue
		var actor := value as ReplicatedActor3D
		actor.set_combat_effects_enabled(features != "no_effects")
		if features == "no_overhead":
			actor.set_nameplate_visible(false)
			actor.set_health_visible(false)


func _place_population(nodes: Dictionary, records: Dictionary,
		visibility: String) -> void:
	var local := nodes.get(FIRST_ACTOR_ID) as ReplicatedActor3D
	if not _expect(local != null, "the local player is included in the population"):
		return
	_main.call("_update_local_actor_follow")
	await _settle_frames(3)
	var camera := _main.get("gameplay_camera") as Camera3D
	var rig := _main.get("camera_rig") as Node3D
	if visibility == "zoom":
		rig.set("distance", 70.0)
		rig.call("_update_camera")
	else:
		rig.set("distance", 26.0)
		rig.call("_update_camera")
	await _settle_frames(2)
	var count := nodes.size()
	var wanted := count if visibility in ["concentrated", "zoom"] else count / 2
	var ids: Array = nodes.keys()
	ids.sort()
	var ground_y := local.global_position.y
	var occupied_tiles: Dictionary = {}
	for index: int in range(ids.size()):
		var actor := nodes[ids[index]] as ReplicatedActor3D
		var point := local.global_position
		if index < wanted:
			point = _visible_ground_point(camera, index, wanted, ground_y)
		elif visibility == "range_bands" and index >= wanted + (count - wanted) / 2:
			point = _beyond_draw_point(camera, local.global_position,
				index - wanted, count - wanted, ground_y)
		else:
			point = _outside_frustum_point(camera, local.global_position,
				index - wanted, count - wanted, ground_y)
		if count > 300:
			point = _unique_fixture_point(camera, local.global_position, actor, point,
				index < wanted, occupied_tiles)
		else:
			occupied_tiles[_adapter.godot_to_server(point)] = true
		_set_actor_position(actor, records, point)
	_expect(occupied_tiles.size() == count,
		"%s placement assigns one canonical server tile per actor (got %d of %d)" % [
			visibility, occupied_tiles.size(), count])
	await physics_frame
	await process_frame
	_main.set("_animation_gate_refresh_msec", 0)
	_main.call("_update_animation_gate", 0.0)
	_app_state.set("actors", records)
	await _settle_frames(2)


func _unique_fixture_point(camera: Camera3D, local_position: Vector3,
		actor: ReplicatedActor3D, intended: Vector3, expected_visible: bool,
		occupied: Dictionary) -> Vector3:
	var base_tile := _adapter.godot_to_server(intended)
	if not occupied.has(base_tile):
		occupied[base_tile] = true
		return intended
	# Screen-ray samples become denser in world space near the lower edge of an
	# isometric camera. Resolve any duplicate deterministically to the closest
	# free protocol tile that preserves the intended frustum/draw classification.
	# This keeps every actor on a real server coordinate without stacking or
	# silently moving an off-screen actor into the measured visible population.
	for radius: int in range(1, 65):
		for offset_y: int in range(-radius, radius + 1):
			for offset_x: int in range(-radius, radius + 1):
				if maxi(absi(offset_x), absi(offset_y)) != radius:
					continue
				var tile := base_tile + Vector2i(offset_x, offset_y)
				if occupied.has(tile):
					continue
				var candidate := _adapter.tile_center(tile.x, tile.y)
				candidate.y = intended.y
				if _point_camera_visible(camera, local_position, candidate,
						actor.view_radius()) != expected_visible:
					continue
				occupied[tile] = true
				return candidate
	_expect(false, "fixture could not reserve a unique tile with the requested visibility")
	return intended


func _point_camera_visible(camera: Camera3D, local_position: Vector3,
		point: Vector3, radius: float) -> bool:
	if local_position.distance_to(point) > 80.0:
		return false
	var anchor := point + Vector3.UP
	for plane: Plane in camera.get_frustum():
		if plane.distance_to(anchor) > radius:
			return false
	return true


func _visible_ground_point(camera: Camera3D, index: int, total: int,
		ground_y: float) -> Vector3:
	if index == 0:
		var local := (_main.get("actor_nodes") as Dictionary).get(
			FIRST_ACTOR_ID) as Node3D
		return local.global_position
	var near_count := maxi(1, total / 2)
	var local_index := index - 1 if index < near_count else index - near_count
	var local_total := maxi(1, near_count - 1 if index < near_count else total - near_count)
	var columns := 15
	var rows := ceili(float(local_total) / float(columns))
	var column := local_index % columns
	var row := local_index / columns
	var x := lerpf(0.12, 0.88, (float(column) + 0.5) / float(columns))
	# Lower screen rays land close to the player; upper-middle rays land in the
	# 45-80 m animation band while remaining inside the gameplay frustum.
	var y_low := 0.62 if index < near_count else 0.30
	var y_high := 0.86 if index < near_count else 0.48
	var y := lerpf(y_low, y_high, (float(row) + 0.5) / float(maxi(1, rows)))
	var viewport_size := camera.get_viewport().get_visible_rect().size
	var screen := Vector2(viewport_size.x * x, viewport_size.y * y)
	var origin := camera.project_ray_origin(screen)
	var direction := camera.project_ray_normal(screen)
	if absf(direction.y) < 0.00001:
		return origin + direction * 20.0
	var distance := (ground_y - origin.y) / direction.y
	return origin + direction * maxf(distance, 1.0)


func _outside_frustum_point(camera: Camera3D, local_position: Vector3,
		index: int, total: int, ground_y: float) -> Vector3:
	var toward := local_position - camera.global_position
	toward.y = 0.0
	toward = toward.normalized()
	var right := Vector3.UP.cross(toward).normalized()
	var row := index / 20
	var column := index % 20
	return Vector3(local_position.x, ground_y, local_position.z) \
		- toward * (30.0 + float(row) * 2.0) \
		+ right * (float(column) - 9.5) * 1.5


func _beyond_draw_point(camera: Camera3D, local_position: Vector3,
		index: int, _total: int, ground_y: float) -> Vector3:
	var toward := local_position - camera.global_position
	toward.y = 0.0
	toward = toward.normalized()
	var right := Vector3.UP.cross(toward).normalized()
	var row := index / 20
	return Vector3(local_position.x, ground_y, local_position.z) \
		+ toward * (92.0 + float(row) * 2.5) \
		+ right * (float(index % 20) - 9.5) * 1.4


func _set_actor_position(actor: ReplicatedActor3D, records: Dictionary,
		point: Vector3) -> void:
	var tile := _adapter.godot_to_server(point)
	var dto := (records[actor.actor_id] as Dictionary).duplicate(false)
	dto["x"] = tile.x
	dto["y"] = tile.y
	records[actor.actor_id] = dto
	actor.apply_server_state(dto, _adapter, true)
	_main.call("_place_actor_on_surface", actor, true, _adapter.fallback_height())


func _camera_visible(camera: Camera3D, actor: ReplicatedActor3D) -> bool:
	if not _frustum_intersects(camera, actor):
		return false
	var local := (_main.get("actor_nodes") as Dictionary).get(FIRST_ACTOR_ID) as Node3D
	return local == null or local.global_position.distance_to(actor.global_position) <= 80.0


func _frustum_intersects(camera: Camera3D, actor: ReplicatedActor3D) -> bool:
	var anchor := actor.global_position + Vector3.UP
	var radius := actor.view_radius()
	for plane: Plane in camera.get_frustum():
		if plane.distance_to(anchor) > radius:
			return false
	return true


func _active_ids(nodes: Dictionary, activity: String) -> Array[int]:
	var wanted := 0
	match activity:
		"move25": wanted = nodes.size() / 4
		"third_active", "sync_burst", "asynchronous": wanted = nodes.size() / 3
		"all_move", "all_combat": wanted = nodes.size()
	var ids: Array = nodes.keys()
	ids.sort()
	var active: Array[int] = []
	if wanted >= ids.size():
		for id: Variant in ids:
			active.append(int(id))
		return active
	# Keep the local player in the total but out of the moving subset: the
	# gameplay camera follows it, which would move the visibility fixture too.
	for index: int in range(1, mini(wanted + 1, ids.size())):
		active.append(int(ids[index]))
	return active


func _workload_plan(active_ids: Array[int], activity: String) -> Dictionary:
	var moving := active_ids.size()
	var fighting := 0
	if activity == "third_active":
		moving = active_ids.size() / 2
		fighting = active_ids.size() - moving
	elif activity == "all_combat":
		moving = 0
		fighting = active_ids.size()
	return {"active": active_ids.size(), "moving": moving, "fighting": fighting,
		"fixtureDistribution": "lowest sorted remote ids; primary active set is inside the visible fixture"}


func _equipment_snapshot(ids: Array[int]) -> Dictionary:
	var snapshot: Dictionary = {}
	var actors := _app_state.get("actors") as Dictionary
	for id: int in ids:
		var record := actors.get(id, {}) as Dictionary
		snapshot[id] = (record.get("equipment_visuals", {}) as Dictionary).duplicate()
	return snapshot


func _network_integrity(spec: Dictionary, ids: Array[int],
		initial_equipment: Dictionary, errors_before: int) -> Dictionary:
	var errors_after := (_app_state.get("recent_protocol_errors") as Array).size()
	var unchanged_gear_mismatches := 0
	if str(spec["network"]) == "protocol_unchanged_gear":
		var current := _app_state.get("actors") as Dictionary
		for id: int in ids:
			var record := current.get(id, {}) as Dictionary
			if (record.get("equipment_visuals", {}) as Dictionary) != \
					(initial_equipment.get(id, {}) as Dictionary):
				unchanged_gear_mismatches += 1
	_expect(errors_after == errors_before,
		"%s adds no protocol decode errors" % spec["id"])
	_expect(unchanged_gear_mismatches == 0,
		"%s unchanged-gear packets preserve equipment identity" % spec["id"])
	return {"protocolErrorsBefore": errors_before, "protocolErrorsAfter": errors_after,
		"unchangedGearMismatches": unchanged_gear_mismatches}


func _prime_activity(spec: Dictionary, active_ids: Array[int]) -> void:
	if active_ids.is_empty():
		return
	if str(spec["activity"]) in ["all_combat", "third_active"]:
		var workload := _workload_plan(active_ids, str(spec["activity"]))
		var fighting: Array[int] = active_ids.slice(int(workload["moving"]))
		_send_actor_commands(fighting, 18)
		_flush_changed()
		_drive_combat_visuals(fighting, 0, str(spec["features"]) != "no_effects")
	await process_frame


func _warm_for(spec: Dictionary, active_ids: Array[int]) -> void:
	var duration := int((_report["measurement"] as Dictionary)["warmupMilliseconds"])
	var cadence := _driver_cadence(spec)
	var started := Time.get_ticks_msec()
	var next_tick := started
	var tick := 0
	while Time.get_ticks_msec() - started < duration:
		var now := Time.get_ticks_msec()
		while now >= next_tick:
			_drive_tick(spec, active_ids, tick)
			tick += 1
			next_tick += cadence
		await process_frame


func _sample_cell(spec: Dictionary, active_ids: Array[int]) -> Dictionary:
	var duration := int((_report["measurement"] as Dictionary)["sampleMilliseconds"])
	var hard_limit := maxi(duration * 4, 120000)
	var cadence := _driver_cadence(spec)
	var raw: Dictionary = {
		"wallMilliseconds": [], "presentMilliseconds": [], "groundMilliseconds": [],
		"overheadMilliseconds": [], "animationGateMilliseconds": [],
		"syncWorldMilliseconds": [], "rootRenderCpuMilliseconds": [],
		"rootRenderGpuMilliseconds": [], "worldRenderCpuMilliseconds": [],
		"worldRenderGpuMilliseconds": [], "drawCalls": [], "primitives": [],
		"packetDispatchInclusiveMilliseconds": [], "commandOnlyReduceMilliseconds": [],
		"packetsPerFrame": [], "sceneNodes": [], "resourceObjects": [],
		"transientWorldEffects": [], "commandsPerFrame": [],
		"stateUpdatesPerFrame": [], "flushesPerFrame": [],
		"combatPresentationEventsPerFrame": [],
	}
	var calls: Dictionary = {}
	var resources_before := _resource_readiness_snapshot()
	var started := Time.get_ticks_msec()
	var next_tick := started
	var tick := 0
	while Time.get_ticks_msec() - started < duration \
			or (raw["wallMilliseconds"] as Array).size() < MIN_SAMPLE_FRAMES:
		if Time.get_ticks_msec() - started >= hard_limit:
			break
		_main.call("benchmark_reset_frame")
		_driver_usec = 0
		_driver_command_usec = 0
		_driver_packets = 0
		_driver_commands = 0
		_driver_state_updates = 0
		_driver_flushes = 0
		_driver_combat_events = 0
		var frame_started := Time.get_ticks_usec()
		var now := Time.get_ticks_msec()
		while now >= next_tick:
			_drive_tick(spec, active_ids, tick)
			tick += 1
			next_tick += cadence
		await process_frame
		(raw["wallMilliseconds"] as Array).append(
			float(Time.get_ticks_usec() - frame_started) / 1000.0)
		var measured: Dictionary = _main.call("benchmark_take_frame") as Dictionary
		var usec: Dictionary = measured.get("microseconds", {}) as Dictionary
		var frame_calls: Dictionary = measured.get("calls", {}) as Dictionary
		(raw["presentMilliseconds"] as Array).append(
			float(usec.get("present_excluding_ground", 0)) / 1000.0)
		(raw["groundMilliseconds"] as Array).append(float(usec.get("ground", 0)) / 1000.0)
		(raw["overheadMilliseconds"] as Array).append(float(usec.get("overhead", 0)) / 1000.0)
		(raw["animationGateMilliseconds"] as Array).append(
			float(usec.get("animation_gate", 0)) / 1000.0)
		(raw["syncWorldMilliseconds"] as Array).append(
			float(usec.get("sync_world_inclusive", 0)) / 1000.0)
		(raw["packetDispatchInclusiveMilliseconds"] as Array).append(
			float(_driver_usec) / 1000.0)
		(raw["commandOnlyReduceMilliseconds"] as Array).append(
			float(_driver_command_usec) / 1000.0)
		(raw["packetsPerFrame"] as Array).append(_driver_packets)
		(raw["commandsPerFrame"] as Array).append(_driver_commands)
		(raw["stateUpdatesPerFrame"] as Array).append(_driver_state_updates)
		(raw["flushesPerFrame"] as Array).append(_driver_flushes)
		(raw["combatPresentationEventsPerFrame"] as Array).append(
			_driver_combat_events)
		(raw["sceneNodes"] as Array).append(int(
			Performance.get_monitor(Performance.OBJECT_NODE_COUNT)))
		(raw["resourceObjects"] as Array).append(int(
			Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)))
		(raw["transientWorldEffects"] as Array).append(_live_world_effect_count())
		for key: Variant in frame_calls:
			calls[key] = int(calls.get(key, 0)) + int(frame_calls[key])
		_append_render_sample(raw)
	var summary: Dictionary = {}
	for key: String in raw:
		summary[key] = _distribution(raw[key] as Array)
	var sampled_frames := (raw["wallMilliseconds"] as Array).size()
	var sufficient_samples := sampled_frames >= MIN_SAMPLE_FRAMES
	_expect(sufficient_samples, "%s records at least %d timed frames before the %d ms hard bound" % [
		spec["id"], MIN_SAMPLE_FRAMES, hard_limit])
	var packet_bearing: Dictionary = {}
	for key: String in ["wallMilliseconds", "presentMilliseconds",
			"groundMilliseconds", "packetDispatchInclusiveMilliseconds",
			"commandOnlyReduceMilliseconds",
			"syncWorldMilliseconds"]:
		var selected: Array = []
		for index: int in range((raw["packetsPerFrame"] as Array).size()):
			if int((raw["packetsPerFrame"] as Array)[index]) > 0:
				selected.append((raw[key] as Array)[index])
		packet_bearing[key] = _distribution(selected)
	var elapsed_seconds := maxf(0.001,
		float(Time.get_ticks_msec() - started) / 1000.0)
	return {
		"elapsedMilliseconds": Time.get_ticks_msec() - started,
		"requestedMilliseconds": duration, "hardLimitMilliseconds": hard_limit,
		"sampleSufficiency": {
			"sufficient": sufficient_samples,
			"minimumFrames": MIN_SAMPLE_FRAMES,
			"actualFrames": sampled_frames,
			"reason": null if sufficient_samples else (
				"hard time bound reached before minimum frame count"),
		},
		"driverCadenceMilliseconds": cadence,
		"frames": sampled_frames,
		"cadenceTicks": tick,
		"wallMetric": "scene-tree CPU proxy" if _headless else "diagnostic compositor-paced wall",
		"percentileCaveat": ("uncapped headless all-frame percentiles dilute "
			+ "10 Hz packet frames; use packetBearingSummary and maxima") if _headless else (
			"window wall percentiles are compositor paced and non-authoritative"),
		"rendererMetric": "unavailable under headless" if _headless else "RenderingServer viewport timers",
		"rendererSampling": ("viewport measured times are sampled after process_frame; "
			+ "the asynchronous API may describe a previously submitted frame"),
		"summary": summary, "packetBearingSummary": packet_bearing,
		"rates": {
			"packetsPerSecond": _round(_sum_numeric(raw["packetsPerFrame"] as Array) / elapsed_seconds),
			"actorCommandsPerSecond": _round(_sum_numeric(raw["commandsPerFrame"] as Array) / elapsed_seconds),
			"stateUpdatesPerSecond": _round(_sum_numeric(raw["stateUpdatesPerFrame"] as Array) / elapsed_seconds),
			"flushesPerSecond": _round(_sum_numeric(raw["flushesPerFrame"] as Array) / elapsed_seconds),
			"combatPresentationEventsPerSecond": _round(_sum_numeric(
				raw["combatPresentationEventsPerFrame"] as Array) / elapsed_seconds),
		},
		"calls": calls, "raw": raw,
		"resourcesBefore": resources_before,
		"resourcesAfter": _resource_readiness_snapshot(),
		"resourceVariationIncludesDeclaredCombatEffects": true,
		"activityObserved": _activity_census(_main.get("actor_nodes") as Dictionary),
	}


func _drive_tick(spec: Dictionary, active_ids: Array[int], tick: int) -> void:
	if active_ids.is_empty():
		return
	var activity := str(spec["activity"])
	var network := str(spec["network"])
	var combat_interval := 40 if network == "asynchronous" else 4
	var mutation_interval := 50 if network == "asynchronous" else 5
	var move_count := active_ids.size()
	if activity == "third_active":
		move_count = active_ids.size() / 2
	var moving: Array[int] = []
	var fighting: Array[int] = []
	if activity != "all_combat":
		for index: int in range(move_count):
			moving.append(active_ids[index])
	if activity == "third_active":
		for index: int in range(move_count, active_ids.size()):
			fighting.append(active_ids[index])
	elif activity == "all_combat":
		for id: int in active_ids:
			fighting.append(id)
	if not moving.is_empty():
		if network == "asynchronous":
			# Each group gets its own alternating sequence. Using tick parity here
			# makes a group seen every tenth tick move forever in one direction.
			var command := 22 if int(tick / 10) % 2 == 0 else 26
			var batch: Array[int] = []
			for index: int in range(moving.size()):
				if index % 10 == tick % 10:
					batch.append(moving[index])
			_send_actor_commands(batch, command)
		else:
			var command := 22 if tick % 2 == 0 else 26
			_send_actor_commands(moving, command)
	if not fighting.is_empty() and tick % combat_interval == 0:
		if network == "folded_turn_attack":
			_send_actor_commands(fighting, 38 + (tick / 4) % 8)
		_send_actor_commands(fighting, 46)
	if network in ["protocol_health_buffs", "protocol_unchanged_gear",
			"protocol_changed_gear_lifecycle"] and tick % mutation_interval == 0:
		_send_network_variant_packets(active_ids, network, tick)
	_flush_changed()
	# Presentation events follow the state flush, as they do after packet
	# reduction. Applying them before the fresh attack command would overwrite
	# the spell or bow action and benchmark a state that is never drawn.
	if not fighting.is_empty() and tick % combat_interval == 0:
		_drive_combat_visuals(fighting, tick,
			str(spec["features"]) != "no_effects")


func _driver_cadence(spec: Dictionary) -> int:
	var cadence := int((_report["measurement"] as Dictionary)["cadenceMilliseconds"])
	return maxi(1, cadence / 10) if str(spec["network"]) == "asynchronous" else cadence


func _send_actor_commands(ids: Array, command: int) -> void:
	if ids.is_empty():
		return
	var payload := PackedByteArray()
	for id: int in ids:
		payload.append(id & 0xff)
		payload.append((id >> 8) & 0xff)
		payload.append(command & 0xff)
	var dispatch_before := _driver_usec
	_send_packet(EloriaProtocol.ServerMessage.ADD_ACTOR_COMMAND, payload, ids.size())
	_driver_command_usec += _driver_usec - dispatch_before
	_driver_commands += ids.size()


func _drive_combat_visuals(ids: Array, tick: int, effects: bool) -> void:
	for index: int in range(ids.size()):
		var actor_value: Variant = (_main.get("actor_nodes") as Dictionary).get(ids[index])
		if not is_instance_valid(actor_value):
			continue
		var actor := actor_value as ReplicatedActor3D
		actor.set_combat_effects_enabled(effects)
		match index % 4:
			0:
				# The real handler creates WorldEffect3D and drives the source actor's
				# spell presentation from the same payload shape as the server event.
				var payload := PackedByteArray([tick % 6])
				_append_u16(payload, int(ids[index]))
				_append_u16(payload, int(ids[(index + 1) % ids.size()]))
				payload.append(10)
				_send_packet(EloriaProtocol.ServerMessage.SEND_SPECIAL_EFFECT,
					payload, 1)
				_driver_combat_events += 1
			1:
				var payload := PackedByteArray()
				_append_u16(payload, int(ids[index]))
				payload.append_array("ranged_draw".to_utf8_buffer())
				payload.append(0)
				_send_packet(EloriaProtocol.ServerMessage.ADD_ACTOR_ANIMATION,
					payload, 1)
				_driver_combat_events += 1


func _send_network_variant_packets(ids: Array, network: String, tick: int) -> void:
	var actors := _app_state.get("actors") as Dictionary
	for index: int in range(ids.size()):
		var id := int(ids[index])
		if not actors.has(id):
			continue
		var record := actors[id] as Dictionary
		if network == "protocol_health_buffs":
			var health_payload := PackedByteArray()
			_append_u16(health_payload, id)
			_append_u16(health_payload, 1)
			_send_packet(EloriaProtocol.ServerMessage.GET_ACTOR_DAMAGE \
				if tick % 10 == 0 else EloriaProtocol.ServerMessage.GET_ACTOR_HEAL,
				health_payload, 1)
			var buff_payload := PackedByteArray()
			_append_u16(buff_payload, id)
			var buffs := EloriaProtocol.ACTOR_BUFF_DOUBLE_SPEED \
				if (tick + index) % 3 == 0 else 0
			for shift: int in [0, 8, 16, 24]:
				buff_payload.append((buffs >> shift) & 0xff)
			_send_packet(EloriaProtocol.ServerMessage.SEND_BUFFS, buff_payload, 1)
		elif int(record.get("kind", 0)) == 1:
			var part := 6
			if network == "protocol_changed_gear_lifecycle" and tick % 10 == 0:
				var unwear := PackedByteArray()
				_append_u16(unwear, id)
				unwear.append(part)
				_send_packet(EloriaProtocol.ServerMessage.ACTOR_UNWEAR_ITEM,
					unwear, 1)
			else:
				var current_visuals := record.get("equipment_visuals", {}) as Dictionary
				var visual_id := int(current_visuals.get(part,
					(_equipment_for(id - FIRST_ACTOR_ID, "full") as Dictionary).get(part, 0)))
				var wear := PackedByteArray()
				_append_u16(wear, id)
				wear.append(part)
				wear.append(visual_id)
				_send_packet(EloriaProtocol.ServerMessage.ACTOR_WEAR_ITEM, wear, 1)


func _send_packet(command: int, payload: PackedByteArray, updates: int) -> void:
	var started := Time.get_ticks_usec()
	_app_state.call("_on_packet", command, payload)
	_driver_usec += Time.get_ticks_usec() - started
	_driver_packets += 1
	_driver_state_updates += updates


func _append_u16(payload: PackedByteArray, value: int) -> void:
	payload.append(value & 0xff)
	payload.append((value >> 8) & 0xff)


func _flush_changed() -> void:
	var changed := _app_state.call("take_changed_actors") as Dictionary
	if changed.is_empty():
		return
	_main.call("_sync_world", changed)
	_driver_flushes += 1


func _append_render_sample(raw: Dictionary) -> void:
	if _headless:
		for key: String in ["rootRenderCpuMilliseconds", "rootRenderGpuMilliseconds",
				"worldRenderCpuMilliseconds", "worldRenderGpuMilliseconds",
				"drawCalls", "primitives"]:
			(raw[key] as Array).append(null)
		return
	var root_cpu := RenderingServer.viewport_get_measured_render_time_cpu(
		root.get_viewport_rid())
	var root_gpu := RenderingServer.viewport_get_measured_render_time_gpu(
		root.get_viewport_rid())
	var viewport := _world_viewport()
	var world_cpu := 0.0 if viewport == null else \
		RenderingServer.viewport_get_measured_render_time_cpu(viewport.get_viewport_rid())
	var world_gpu := 0.0 if viewport == null else \
		RenderingServer.viewport_get_measured_render_time_gpu(viewport.get_viewport_rid())
	(raw["rootRenderCpuMilliseconds"] as Array).append(root_cpu if root_cpu > 0.0 else null)
	(raw["rootRenderGpuMilliseconds"] as Array).append(root_gpu if root_gpu > 0.0 else null)
	(raw["worldRenderCpuMilliseconds"] as Array).append(world_cpu if world_cpu > 0.0 else null)
	(raw["worldRenderGpuMilliseconds"] as Array).append(world_gpu if world_gpu > 0.0 else null)
	(raw["drawCalls"] as Array).append(RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME))
	(raw["primitives"] as Array).append(RenderingServer.get_rendering_info(
		RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME))


func _census(nodes: Dictionary) -> Dictionary:
	var camera := _main.get("gameplay_camera") as Camera3D
	var local := nodes.get(FIRST_ACTOR_ID) as Node3D
	var tiers := {"full": 0, "half": 0, "paused": 0}
	var drawn := 0
	var frustum := 0
	var visible := 0
	var near := 0
	var mid := 0
	var beyond := 0
	var height_synchronized := 0
	var nameplates_visible := 0
	var health_visible := 0
	var humanoids := 0
	var creatures := 0
	for value: Variant in nodes.values():
		if not is_instance_valid(value):
			continue
		var actor := value as ReplicatedActor3D
		drawn += int(actor.is_drawn())
		frustum += int(_frustum_intersects(camera, actor))
		visible += int(_camera_visible(camera, actor))
		var distance := 0.0 if local == null else \
			local.global_position.distance_to(actor.global_position)
		if distance <= 45.0:
			near += 1
		elif distance <= 80.0:
			mid += 1
		else:
			beyond += 1
		height_synchronized += int(is_finite(actor.global_position.y)
			and is_finite(actor.server_target.y)
			and absf(actor.global_position.y - actor.server_target.y) <= 0.05)
		var nameplate := actor.get("_nameplate") as Node3D
		var health := actor.get("_health_bar_background") as Node3D
		nameplates_visible += int(is_instance_valid(nameplate) and nameplate.visible)
		health_visible += int(is_instance_valid(health) and health.visible)
		var record := (_app_state.get("actors") as Dictionary).get(actor.actor_id, {}) as Dictionary
		if int(record.get("kind", 0)) == 1:
			humanoids += 1
		else:
			creatures += 1
		match actor.animation_tier():
			AnimationGate.Tier.HALF: tiers["half"] += 1
			AnimationGate.Tier.PAUSED: tiers["paused"] += 1
			_: tiers["full"] += 1
	return {"total": nodes.size(), "humanoids": humanoids, "creatures": creatures,
		"withinDrawDistance": drawn, "frustumIntersecting": frustum,
		"frustumAndDrawVisible": visible,
		"distanceBands": {"near0To45": near, "mid45To80": mid,
			"beyond80": beyond},
		"heightSynchronized": height_synchronized,
		"visibleNameplates": nameplates_visible, "visibleHealthBars": health_visible,
		"animationTiers": tiers}


func _activity_census(nodes: Dictionary) -> Dictionary:
	var physics := 0
	var active_animation_players := 0
	var actions: Dictionary = {}
	for value: Variant in nodes.values():
		if not is_instance_valid(value):
			continue
		var actor := value as ReplicatedActor3D
		physics += int(actor.is_physics_processing())
		active_animation_players += int(actor.animation_player != null
			and actor.animation_player.active)
		actions[str(actor.current_action)] = int(actions.get(str(actor.current_action), 0)) + 1
	return {"physicsProcessing": physics,
		"activeAnimationPlayers": active_animation_players, "actions": actions}


func _grounding_census(nodes: Dictionary) -> Dictionary:
	var world := _main.get("gameplay_world") as World3D
	if world == null:
		return {"surfaceHits": 0, "surfaceMatches": 0,
			"surfaceMisses": nodes.size(), "maximumHeightError": null}
	var hits := 0
	var matches := 0
	var misses := 0
	var maximum_error := 0.0
	var mask := WorldLoader.NAVIGATION_SURFACE_LAYER \
		| ExteriorRegionStream.PREVIEW_SURFACE_LAYER
	for value: Variant in nodes.values():
		if not is_instance_valid(value):
			continue
		var actor := value as ReplicatedActor3D
		var position := actor.server_target
		var query := PhysicsRayQueryParameters3D.create(
			Vector3(position.x, 400.0, position.z),
			Vector3(position.x, -100.0, position.z), mask)
		var hit := world.direct_space_state.intersect_ray(query)
		var point: Variant = hit.get("position")
		if point is not Vector3:
			misses += 1
			continue
		hits += 1
		var error := absf(actor.server_target.y - ((point as Vector3).y + 0.02))
		maximum_error = maxf(maximum_error, error)
		matches += int(error <= 0.05)
	return {"surfaceHits": hits, "surfaceMatches": matches,
		"surfaceMisses": misses, "maximumHeightError": _round(maximum_error)}


func _actor_diagnostics(nodes: Dictionary, spec: Dictionary) -> Dictionary:
	var native_equipment := 0
	var fallback_equipment := 0
	var skinned_equipment := 0
	var combat_presentations := 0
	var mesh_instances := 0
	var distinct_meshes: Dictionary = {}
	var animation_players := 0
	var equipped_humanoids := 0
	var fully_equipped_humanoids := 0
	var applied_equipment_visuals := 0
	for value: Variant in nodes.values():
		if not is_instance_valid(value):
			continue
		var actor := value as ReplicatedActor3D
		var diag := actor.equipment_diagnostics()
		var visuals := diag.get("visuals", {}) as Dictionary
		if not visuals.is_empty():
			equipped_humanoids += 1
			applied_equipment_visuals += visuals.size()
			fully_equipped_humanoids += int(visuals.size() == 7)
		native_equipment += int(diag.get("native", 0))
		fallback_equipment += int(diag.get("fallback", 0))
		skinned_equipment += int(diag.get("skinned", 0))
		combat_presentations += int(actor.combat_presentation != null)
		animation_players += int(actor.animation_player != null)
		for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
			var mesh_node := node as MeshInstance3D
			mesh_instances += 1
			if mesh_node.mesh != null:
				distinct_meshes[mesh_node.mesh.get_instance_id()] = true
	if str(spec["features"]) not in ["bare"] and str(spec["population"]) != "creature":
		_expect(native_equipment > 0 and fallback_equipment == 0,
			"%s uses native equipment without fallback substitutions" % spec["id"])
	return {
		"nativeEquipmentNodes": native_equipment,
		"fallbackEquipmentNodes": fallback_equipment,
		"skinnedEquipmentNodes": skinned_equipment,
		"combatPresentations": combat_presentations,
		"animationPlayers": animation_players,
		"equippedHumanoids": equipped_humanoids,
		"fullyEquippedHumanoids": fully_equipped_humanoids,
		"appliedEquipmentVisuals": applied_equipment_visuals,
		"meshInstances": mesh_instances,
		"distinctMeshes": distinct_meshes.size(),
		"cachedScenes": GlbSceneCache.cached_scene_count(),
		"cachedAnimationLibraries": NativeAnimationImporter.cached_library_count(),
	}


func _capture_cell(file_name: String) -> void:
	file_name = str(_report.get("runId", "manual")) + "-" + file_name
	await _settle_frames(3)
	await RenderingServer.frame_post_draw
	var image := root.get_texture().get_image()
	if not _expect(image != null and image.get_size() == root.size,
			file_name + " captures the full root viewport"):
		return
	_expect(image.save_png(_artifacts.path_join(file_name)) == OK,
		file_name + " is written")


func _measure_packet_bursts() -> Dictionary:
	var variants := {"movement": [22, 26], "turn_attack": [38, 46]}
	var out: Dictionary = {}
	var seeded: Dictionary = {}
	for index: int in range(24):
		var id := FIRST_ACTOR_ID + index
		seeded[id] = {"actor_id": id, "x": 180, "y": 180,
			"rotation": 0, "actor_type": 1, "kind": 1, "name": "Burst",
			"health": 80, "max_health": 100, "alive": true}
	for name: String in variants:
		var commands: Array = variants[name]
		var bytes := PackedByteArray()
		for packet: int in range(500):
			var payload := PackedByteArray()
			for slot: int in range(8):
				var id := FIRST_ACTOR_ID + ((packet + slot) % 24)
				payload.append(id & 0xff)
				payload.append((id >> 8) & 0xff)
				payload.append(int(commands[packet % commands.size()]))
			bytes.append_array(EloriaProtocol.encode(
				EloriaProtocol.ServerMessage.ADD_ACTOR_COMMAND, payload))
		var decode_samples: Array = []
		var full_samples: Array = []
		var decoded := 0
		for repeat: int in range(8):
			var offset := 0
			decoded = 0
			var started := Time.get_ticks_usec()
			while offset < bytes.size():
				var frame := EloriaProtocol.try_decode(bytes, offset)
				if str(frame.get("status", "")) != "ok":
					break
				offset += int(frame["consumed"])
				decoded += 1
			decode_samples.append(float(Time.get_ticks_usec() - started) / 1000.0)
		for repeat: int in range(8):
			_app_state.set("actors", seeded.duplicate(true))
			_app_state.call("take_changed_actors")
			var offset := 0
			var started := Time.get_ticks_usec()
			while offset < bytes.size():
				var frame := EloriaProtocol.try_decode(bytes, offset)
				if str(frame.get("status", "")) != "ok":
					break
				offset += int(frame["consumed"])
				_app_state.call("_on_packet", int(frame["command"]),
					frame["payload"] as PackedByteArray)
			full_samples.append(float(Time.get_ticks_usec() - started) / 1000.0)
		_expect(decoded == 500, "%s burst decodes all 500 frames" % name)
		out[name] = {
			"shape": "500 ADD_ACTOR_COMMAND packets, eight commands each",
			"packets": 500, "commandsPerPacket": 8, "actorCommands": 4000,
			"seededActors": 24, "bytes": bytes.size(),
			"decodeOnlyMilliseconds": _distribution(decode_samples),
			"decodeAndReduceMilliseconds": _distribution(full_samples),
			"raw": {"decodeOnlyMilliseconds": decode_samples,
				"decodeAndReduceMilliseconds": full_samples},
		}
	_app_state.set("actors", {})
	_app_state.call("take_changed_actors")
	return out


func _world_viewport() -> SubViewport:
	return _main.get_node_or_null("GameView/ViewportContainer/Viewport") as SubViewport


func _wait_for_world_readiness(label: String, minimum_elapsed_msec: int) -> Dictionary:
	if str(_report.get("map", "")) == "none":
		var synthetic := _resource_readiness_snapshot()
		synthetic.merge({"label": label, "waitMilliseconds": 0,
			"stableFrames": 0, "ready": true,
			"reason": "synthetic no-map diagnostic"}, true)
		return synthetic
	var started := Time.get_ticks_msec()
	var deadline := started + MAX_READINESS_MSEC
	var stable_frames := 0
	var previous_signature := ""
	var quiet_since := -1
	var snapshot: Dictionary = {}
	while Time.get_ticks_msec() < deadline:
		await physics_frame
		await process_frame
		snapshot = _resource_readiness_snapshot()
		var signature := JSON.stringify([
			snapshot["sceneNodes"], snapshot["resourceObjects"],
			snapshot["cachedScenes"], snapshot["cachedAnimationLibraries"],
			snapshot["worldNodes"], snapshot["streamingResidentCells"]])
		var streaming_idle := bool(snapshot["streamingIdle"])
		if signature == previous_signature and streaming_idle:
			stable_frames += 1
			if quiet_since < 0:
				quiet_since = Time.get_ticks_msec()
		else:
			stable_frames = 0
			quiet_since = -1
		previous_signature = signature
		var elapsed := Time.get_ticks_msec() - started
		var quiet_elapsed := 0 if quiet_since < 0 else Time.get_ticks_msec() - quiet_since
		if elapsed >= minimum_elapsed_msec and stable_frames >= 12 \
				and quiet_elapsed >= 500:
			break
	var quiet_elapsed := 0 if quiet_since < 0 else Time.get_ticks_msec() - quiet_since
	var ready := Time.get_ticks_msec() < deadline and stable_frames >= 12 \
		and quiet_elapsed >= 500 and bool(snapshot.get("streamingIdle", false))
	_expect(ready, "%s reaches stable resources with no map/chunk work pending" % label)
	snapshot["label"] = label
	snapshot["waitMilliseconds"] = Time.get_ticks_msec() - started
	snapshot["stableFrames"] = stable_frames
	snapshot["quietWindowMilliseconds"] = quiet_elapsed
	snapshot["ready"] = ready
	return snapshot


func _resource_readiness_snapshot() -> Dictionary:
	var loader := _main.get("world_loader") as WorldLoader
	var world: Node = loader.world_root if loader != null else null
	var chunk := world as ContinentChunkStream
	return {
		"sceneNodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"resourceObjects": int(Performance.get_monitor(
			Performance.OBJECT_RESOURCE_COUNT)),
		"cachedScenes": GlbSceneCache.cached_scene_count(),
		"cachedAnimationLibraries": NativeAnimationImporter.cached_library_count(),
		"worldNodes": _node_count(world),
		"streamingResidentCells": chunk.cells.size() if chunk != null else null,
		"streamingIdle": _streaming_idle(loader, chunk),
		"transientWorldEffects": _live_world_effect_count(),
	}


func _streaming_idle(loader: WorldLoader, chunk: ContinentChunkStream) -> bool:
	if loader == null or loader.world_root == null:
		return false
	if int(loader.get("_cache_write_countdown")) > 0:
		return false
	if chunk != null:
		if chunk.get("_thread") != null or not (chunk.get("_retiring") as Array).is_empty():
			return false
		if ContinentChunkStream.orphans_pending() > 0:
			return false
	var exterior := _main.get("exterior_stream") as ExteriorRegionStream
	return exterior == null or exterior.is_idle()


func _drain_streaming_before_teardown() -> void:
	var loader := _main.get("world_loader") as WorldLoader
	var chunk: ContinentChunkStream = null
	if loader != null:
		chunk = loader.world_root as ContinentChunkStream
	if chunk != null:
		chunk.pause_streaming()
	var exterior := _main.get("exterior_stream") as ExteriorRegionStream
	if exterior != null:
		exterior.clear()
	var deadline := Time.get_ticks_msec() + MAX_READINESS_MSEC
	while Time.get_ticks_msec() < deadline:
		var chunk_idle := chunk == null or (chunk.get("_thread") == null \
			and (chunk.get("_retiring") as Array).is_empty()
			and ContinentChunkStream.orphans_pending() == 0)
		var exterior_idle := exterior == null or exterior.is_idle()
		if chunk_idle and exterior_idle:
			break
		await process_frame
	_expect(Time.get_ticks_msec() < deadline,
		"map and chunk workers drain before benchmark shutdown")


func _node_count(node: Node) -> int:
	if node == null:
		return 0
	var count := 1
	for child: Node in node.get_children():
		count += _node_count(child)
	return count


func _live_world_effect_count() -> int:
	var count := 0
	for value: Variant in _main.get("world_effects") as Array:
		count += int(is_instance_valid(value) and not (value as Node).is_queued_for_deletion())
	return count


func _memory_sample() -> Dictionary:
	return {
		"staticBytes": OS.get_static_memory_usage(),
		"objects": int(Performance.get_monitor(Performance.OBJECT_COUNT)),
		"resources": int(Performance.get_monitor(Performance.OBJECT_RESOURCE_COUNT)),
		"nodes": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"textureBytes": null if _headless else int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_TEXTURE_MEM_USED)),
		"bufferBytes": null if _headless else int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_BUFFER_MEM_USED)),
		"videoBytes": null if _headless else int(RenderingServer.get_rendering_info(
			RenderingServer.RENDERING_INFO_VIDEO_MEM_USED)),
	}


func _memory_delta(before: Dictionary, after: Dictionary) -> Dictionary:
	var out: Dictionary = {}
	for key: Variant in after:
		out[key] = null if after[key] == null or before.get(key) == null \
			else int(after[key]) - int(before.get(key, 0))
	return out


func _distribution(values: Array) -> Variant:
	var usable: Array[float] = []
	for value: Variant in values:
		if value != null:
			usable.append(float(value))
	if usable.is_empty():
		return null
	usable.sort()
	var total := 0.0
	for value: float in usable:
		total += value
	return {
		"samples": usable.size(), "mean": _round(total / float(usable.size())),
		"p50": _percentile(usable, 0.50), "p95": _percentile(usable, 0.95),
		"p99": _percentile(usable, 0.99), "max": _round(usable.back()),
	}


func _sum_numeric(values: Array) -> float:
	var total := 0.0
	for value: Variant in values:
		if value != null:
			total += float(value)
	return total


func _percentile(values: Array[float], fraction: float) -> float:
	var index := clampi(ceili(fraction * float(values.size())) - 1, 0, values.size() - 1)
	return _round(values[index])


func _creature_actor_types() -> Array:
	var catalogue := _json(MODELS)
	var models: Dictionary = catalogue.get("models", {}) as Dictionary
	var actor_types: Dictionary = catalogue.get("actorTypes", {}) as Dictionary
	var candidates: Array = []
	for raw_type: Variant in actor_types:
		var actor_type := int(str(raw_type))
		if actor_type < 200:
			continue
		var model_id := str(actor_types[raw_type])
		var model := models.get(model_id, {}) as Dictionary
		var scene := str(model.get("scene", ""))
		if not scene.is_empty() and FileAccess.file_exists(scene):
			candidates.append({"actorType": actor_type, "model": model_id,
				"scale": float((model.get("import", {}) as Dictionary).get("scale", 1.0))})
	candidates.sort_custom(func(a: Variant, b: Variant) -> bool:
		return float((a as Dictionary)["scale"]) < float((b as Dictionary)["scale"]))
	var chosen: Array = []
	if candidates.is_empty():
		return []
	for step: int in range(10):
		var index := int(floor(float(step) * float(candidates.size() - 1) / 9.0))
		chosen.append((candidates[index] as Dictionary).duplicate())
	return chosen


func _json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}


func _settle_frames(frames: int) -> void:
	for unused: int in range(frames):
		await process_frame


func _settle_milliseconds(duration: int) -> void:
	var deadline := Time.get_ticks_msec() + duration
	while Time.get_ticks_msec() < deadline:
		await process_frame


func _environment_or(key: String, fallback: String) -> String:
	var value := OS.get_environment(key).strip_edges()
	return fallback if value.is_empty() else value


func _environment_int(key: String, fallback: int, minimum: int) -> int:
	var raw := OS.get_environment(key).strip_edges()
	return maxi(minimum, int(raw)) if not raw.is_empty() else fallback


func _csv(raw: String) -> Array:
	return _csv_static(raw, [])


func _csv_ints(raw: String) -> Array:
	return _csv_ints_static(raw, [])


static func _csv_static(raw: String, fallback: Array) -> Array:
	if raw.strip_edges().is_empty():
		return fallback.duplicate()
	var out: Array = []
	for part: String in raw.split(",", false):
		out.append(part.strip_edges())
	return out


static func _csv_ints_static(raw: String, fallback: Array) -> Array:
	var strings := _csv_static(raw, [])
	if strings.is_empty():
		return fallback.duplicate()
	var out: Array = []
	for value: String in strings:
		out.append(int(value))
	return out


func _round(value: float) -> float:
	return snappedf(value, 0.001)


func _expect(value: bool, label: String) -> bool:
	if value:
		return true
	_failures += 1
	(_report.get("failures", []) as Array).append(label)
	push_error("FAIL: " + label)
	return false


func _finish() -> void:
	var output := _environment_or("ELORIA_CROWD_OUTPUT",
		"crowd-headless.json" if _headless else "crowd-windowed.json")
	var output_path := _artifacts.path_join(output)
	var file := FileAccess.open(output_path, FileAccess.WRITE)
	if file == null:
		_failures += 1
		push_error("FAIL: benchmark artifact cannot be opened: " + output_path)
	else:
		_report["failureCount"] = _failures
		file.store_string(JSON.stringify(_report, "  "))
		file.close()
		print("wrote ", output_path)
	_report["failureCount"] = _failures
	print("native crowd benchmark: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)
