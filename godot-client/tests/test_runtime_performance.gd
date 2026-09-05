extends SceneTree
## Guards the runtime-cost work: the map SubViewports must stay idle while their
## UI is hidden, the surface sampler must not re-query physics for an actor that
## has not moved, the animation importer must rebuild only the clips an actor
## can play, and the glTF cache must parse a file once. Then the per-packet
## work: item icons are shared, only the actors that changed are re-presented,
## a hidden statistics window is not rebuilt, a chat line is appended rather
## than the logs rebuilt, the animation library is parsed ahead of the first
## actor, and a pack of actors is built over several frames.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var scene: Node = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(scene)
	await process_frame

	var map_viewport: SubViewport = scene.get_node("%MapViewport")
	var full_map_viewport: SubViewport = scene.get_node("%FullMapViewport")
	var preview_viewport: SubViewport = scene.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport")
	var minimap_frame: Control = scene.get_node("%MinimapFrame")
	var full_map: Control = scene.get_node("%FullMap")
	var map_image: Control = scene.get_node("%MapImage")

	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"minimap viewport ships idle instead of redrawing the world every frame")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"full-map viewport ships idle")
	_expect(preview_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"character preview viewport ships idle")

	minimap_frame.hide()
	full_map.hide()
	scene.call("_request_map_redraw")
	scene.call("_update_map_viewports")
	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"a hidden minimap requests no redraw")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"a hidden full map requests no redraw")

	minimap_frame.show()
	full_map.show()
	map_image.show()
	scene.call("_request_map_redraw")
	scene.call("_update_map_viewports")
	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"a visible minimap requests a single redraw")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"a visible full map requests a single redraw")

	map_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	scene.call("_update_map_viewports")
	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"minimap redraws are throttled rather than requested every frame")
	minimap_frame.hide()
	full_map.hide()

	# The map-load and toggle path runs on every map load and every full-map
	# toggle. It used to set UPDATE_ALWAYS for a visible panel, which put the
	# world back on full-rate rendering for up to one throttle interval and
	# undid the throttle it shares the file with. It may only ever idle a
	# viewport or request its single first frame.
	minimap_frame.show()
	full_map.show()
	map_image.show()
	scene.call("_sync_map_viewport_activity")
	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE
		and full_map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"a map load with both panels visible requests one frame, not continuous redraw")
	minimap_frame.hide()
	full_map.hide()
	scene.call("_sync_map_viewport_activity")
	_expect(map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED
		and full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"a map load with both panels hidden idles both viewports")

	# The toggle paths themselves: opening the tab map or the minimap must not
	# reach UPDATE_ALWAYS either, and closing them must idle immediately.
	scene.call("_toggle_full_map")
	_expect(full_map.visible
		and full_map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"opening the tab map requests one redraw")
	scene.call("_show_continent_view")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"switching the tab map to the continent view idles the world render")
	scene.call("_show_current_map_view")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"switching back to the live map requests one redraw")
	scene.call("_toggle_full_map")
	_expect(not full_map.visible
		and full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"closing the tab map idles its viewport")
	scene.call("_toggle_minimap")
	_expect(minimap_frame.visible
		and map_viewport.render_target_update_mode == SubViewport.UPDATE_ONCE,
		"showing the minimap requests one redraw")
	scene.call("_toggle_minimap")
	_expect(not minimap_frame.visible
		and map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"hiding the minimap idles its viewport")

	# The surface sampler is the per-actor physics query; it must be skipped for
	# an actor that has not moved since the last sample.
	var actor := ReplicatedActor3D.new()
	actor.actor_id = 4242
	actor.server_target = Vector3(3.0, 0.0, 7.0)
	scene.get_node("%WorldRoot").add_child(actor)
	var samples: Dictionary = scene.get("_actor_surface_samples")
	samples.clear()
	scene.call("_place_actor_on_surface", actor)
	_expect(samples.has(4242), "the first placement samples the rendered surface")
	var recorded: Variant = samples[4242]
	scene.call("_place_actor_on_surface", actor)
	_expect(samples[4242] == recorded, "an unmoved actor is not re-sampled")
	actor.server_target = Vector3(9.0, 0.0, 7.0)
	scene.call("_place_actor_on_surface", actor)
	_expect(samples[4242] != recorded, "a moved actor is re-sampled")
	actor.queue_free()

	# Only the clips the action map can request are worth rebuilding.
	var resolver := AnimationResolver.new({
		"actions": {"idle": "Idle_A", "walk": "Walk", "run": "Walk"}})
	var required: PackedStringArray = resolver.required_clips()
	_expect(required.size() == 2 and required.has("Idle_A") and required.has("Walk"),
		"the resolver reports each distinct clip once")

	# Packet decoding in place, so draining a burst does not re-copy the buffer.
	var burst := EloriaProtocol.encode(1, PackedByteArray([7, 8]))
	burst.append_array(EloriaProtocol.encode(2, PackedByteArray([9])))
	var first: Dictionary = EloriaProtocol.try_decode(burst)
	var second: Dictionary = EloriaProtocol.try_decode(burst, int(first.consumed))
	_expect(first.status == "ok" and int(first.command) == 1,
		"the first packet of a burst decodes at offset zero")
	_expect(second.status == "ok" and int(second.command) == 2,
		"the second packet decodes in place at an offset")

	# Item icons are built once per picture and shared, not rebuilt per slot
	# per refresh.
	var atlas: RefCounted = scene.get("item_atlas")
	_expect(is_same(atlas.icon_for(3), atlas.icon_for(3)),
		"an item icon is built once and shared")
	_expect(not is_same(atlas.icon_for(3), atlas.icon_for(4)),
		"different pictures get different icons")

	# AppState names the actors it wrote, so a flush visits only those.
	var app_state: Node = root.get_node("AppState")
	app_state.set("authenticated", false)
	app_state.set("actors", {
		7: {"actor_id": 7, "x": 1, "y": 1, "rotation": 0, "actor_type": 1,
			"kind": 1, "name": "Seven", "health": 5, "max_health": 9},
		8: {"actor_id": 8, "x": 2, "y": 1, "rotation": 0, "actor_type": 1,
			"kind": 1, "name": "Eight", "health": 5, "max_health": 9}})
	app_state.call("take_changed_actors")
	app_state.call("_on_packet", EloriaProtocol.ServerMessage.ADD_ACTOR_COMMAND,
		PackedByteArray([7, 0, 20]))
	var changed: Dictionary = app_state.call("take_changed_actors")
	_expect(changed.has(7) and not changed.has(8),
		"an actor that moved is in the change set and one that stood still is not")
	_expect((app_state.call("take_changed_actors") as Dictionary).is_empty(),
		"taking the change set empties it")
	app_state.call("mark_all_actors_changed")
	_expect((app_state.call("take_changed_actors") as Dictionary).size() == 2,
		"the footprint table marks every actor")

	# The statistics window is not rebuilt while it is hidden.
	var stats_panel: Control = scene.get_node("%StatsPanel")
	var perk_line: Label = scene.get("stats_perk_line")
	stats_panel.hide()
	perk_line.text = "untouched"
	app_state.set("stats", {"health": 3, "max_health": 9})
	scene.call("_sync_stats")
	_expect(perk_line.text == "untouched",
		"a stats packet leaves a hidden statistics window alone")
	stats_panel.show()
	_expect(perk_line.text.begins_with("Perks:"),
		"showing the statistics window rebuilds it")
	stats_panel.hide()

	# A chat line is appended to the logs rather than rebuilding them, and the
	# panel keeps to its cap.
	var chat_output: RichTextLabel = scene.get_node("%ChatOutput")
	var lines: Array = app_state.get("chat_lines")
	lines.clear()
	for index: int in range(3):
		lines.append({"channel": 0, "text": "line %d" % index})
	scene.call("_sync_chat")
	var paragraphs: int = chat_output.get_paragraph_count()
	app_state.set("authenticated", true)
	app_state.call("append_local_message", "one more line", 0)
	_expect(chat_output.get_paragraph_count() == paragraphs + 1
		and chat_output.get_parsed_text().contains("one more line"),
		"a new chat line is appended to the panel")
	for index: int in range(120):
		app_state.call("append_local_message", "filler %d" % index, 0)
	_expect(chat_output.get_paragraph_count() == 101,
		"the chat panel keeps its hundred newest lines")
	_expect(chat_output.get_parsed_text().contains("filler 119")
		and not chat_output.get_parsed_text().contains("one more line"),
		"the oldest lines are the ones dropped")
	app_state.set("authenticated", false)

	# The shared animation library is parsed ahead of the first actor, and a
	# pack of actors is built over several frames rather than in one.
	var library: String = ProjectSettings.globalize_path(
		"res://assets/actors/native/shared/Universal_Animation_Library.glb")
	NativeAnimationImporter.prewarm(library)
	_expect(NativeAnimationImporter.is_prewarming(library)
		or NativeAnimationImporter.has_source(library),
		"prewarming starts the library parse")
	var pack: Dictionary = {}
	for index: int in range(7):
		pack[300 + index] = {"actor_id": 300 + index, "x": 3 + index, "y": 4,
			"rotation": 0, "actor_type": 1, "kind": 1, "name": "Pack %d" % index,
			"health": 5, "max_health": 9}
	app_state.set("actors", pack)
	scene.call("_sync_world")
	var nodes: Dictionary = scene.get("actor_nodes")
	_expect(nodes.size() == 4, "one pass builds at most the spawn budget of actors")
	for unused: int in range(4):
		await process_frame
	_expect(nodes.size() == 7, "the rest of the pack follows on the next frames")
	_expect(NativeAnimationImporter.has_source(library),
		"the first actor used the prewarmed library")
	app_state.set("actors", {})
	scene.call("_sync_world")
	NativeAnimationImporter.clear()

	print("runtime performance tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	scene.queue_free()
	await process_frame
	quit(failures)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
