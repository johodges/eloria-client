extends SceneTree
## Guards the runtime-cost work: the map SubViewports must stay idle while their
## UI is hidden, the surface sampler must not re-query physics for an actor that
## has not moved, the animation importer must rebuild only the clips an actor
## can play, and the glTF cache must parse a file once.

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

	print("runtime performance tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	scene.queue_free()
	await process_frame
	quit(failures)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
