extends SceneTree
## The map window's continent and its region previews are the client's own tab
## maps, and they work the way the legacy map window did: the small map in the
## sidebar swaps between the continent and the map you stand on, a click on a
## region of the continent opens that region's own top-down map, and the cursor
## names server tiles over a preview as it does over the live map.

var failures: int = 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene_resource: Resource = load("res://src/app/main.tscn")
	_expect(scene_resource is PackedScene, "main scene loads")
	if not scene_resource is PackedScene:
		quit(1)
		return
	var main: Control = (scene_resource as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	var app_state: Node = root.get_node("AppState")
	(main.get_node("GameView") as Control).show()
	var full_map: Control = main.get_node("GameView/FullMap") as Control
	var map_image: TextureRect = main.get_node(
		"GameView/FullMap/MapLayout/MapImage") as TextureRect
	var region_preview: TextureRect = main.get_node(
		"GameView/FullMap/MapLayout/RegionPreview") as TextureRect
	var continent_view: Control = main.get_node(
		"GameView/FullMap/MapLayout/ContinentView") as Control
	var continent_image: TextureRect = main.get_node(
		"GameView/FullMap/MapLayout/ContinentView/ContinentImage") as TextureRect
	var continent_button: TextureButton = main.get_node(
		"GameView/FullMap/MapLayout/Sidebar/SidebarContent/ContinentButton") as TextureButton
	var map_title: Label = main.get_node("GameView/FullMap/MapLayout/MapTitle") as Label
	var map_coordinates: Label = main.get_node(
		"GameView/FullMap/MapLayout/Sidebar/SidebarContent/MapCoordinates") as Label
	var full_map_viewport: SubViewport = main.get_node("GameView/FullMapViewport") as SubViewport

	# The cartography: every exterior region, each drawn from its own tab map.
	var cartography: Dictionary = main.get("cartography") as Dictionary
	var regions: Array = main.get("cartography_regions") as Array
	_expect(int(cartography.get("schemaVersion", 0)) == 2, "cartography is the tab-map schema")
	var continent: Dictionary = cartography.get("continent", {}) as Dictionary
	var image_size: Array = continent.get("imageSize", []) as Array
	_expect(image_size.size() == 2 and int(image_size[0]) > 0 and int(image_size[1]) > 0,
		"the continent picture states its size")
	var continent_path: String = str(continent.get("texture", ""))
	_expect(continent_path.ends_with("continent-map.webp") and not continent_path.contains("concept"),
		"the continent is the composed tab maps, not the concept painting")
	_expect(regions.size() == 12, "every exterior region is on the continent")
	_expect(not main.has_node("GameView/FullMap/MapLayout/ContinentView/RegionButtons"),
		"the region button list is gone; the continent itself is the index")
	var overlay: Control = main.get_node(
		"GameView/FullMap/MapLayout/ContinentView/ContinentMap") as Control
	_expect(overlay != null and int(overlay.call("region_count")) == regions.size(),
		"the continent overlay knows every region")
	var wrapped: PackedStringArray = overlay.call("_label_lines", overlay.get_theme_default_font(), "Amethyst Barrens", 90.0)
	_expect(wrapped.size() == 2 and wrapped[0] == "Amethyst" and wrapped[1] == "Barrens",
		"long adjacent-region labels wrap without truncation")
	_expect(region_preview.mouse_filter != Control.MOUSE_FILTER_IGNORE,
		"a preview takes the cursor, so it can name tiles")
	for region_value: Variant in regions:
		var region: Dictionary = region_value as Dictionary
		var name: String = str(region.get("name", ""))
		var tab_map: Dictionary = region.get("tabMap", {}) as Dictionary
		var texture_path: String = str(tab_map.get("texture", ""))
		_expect(not texture_path.contains("concept") and not region.has("preview"),
			name + " is drawn from its tab map, not concept art")
		_expect(FileAccess.file_exists(ProjectSettings.globalize_path(texture_path)),
			name + "'s tab map exists on disk")
		var rect: Array = region.get("continentRect", []) as Array
		_expect(rect.size() == 4 and int(rect[0]) >= 0 and int(rect[1]) >= 0
			and int(rect[0]) + int(rect[2]) <= int(image_size[0])
			and int(rect[1]) + int(rect[3]) <= int(image_size[1]),
			name + " has a rectangle on the continent picture")
	_expect(continent_image.texture == null and continent_button.texture_normal == null,
		"the continent picture is not decoded before the map window opens")

	app_state.set("current_map", "four_gates")
	main.call("_toggle_full_map")
	await process_frame
	_expect(full_map.visible and map_image.visible and not continent_view.visible,
		"the map window opens on the live map")
	var continent_texture: Texture2D = continent_button.texture_normal
	_expect(continent_texture != null and continent_texture.get_size()
		== Vector2(float(image_size[0]), float(image_size[1])),
		"the small map shows the composed continent at its stated size")
	_expect(continent_image.texture == continent_texture,
		"the big continent view holds the same picture")

	# The small map swaps the two views, as the legacy map window's did.
	main.call("_on_continent_button_pressed")
	_expect(continent_view.visible and not map_image.visible and not region_preview.visible,
		"the small map opens the continent")
	_expect(continent_button.texture_normal is ViewportTexture,
		"on the continent the small map shows the live current map")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"the continent view idles the world render")
	_expect(map_title.text == "NYMARA CONTINENT", "the title names the continent")
	main.call("_on_continent_button_pressed")
	_expect(map_image.visible and not continent_view.visible
		and continent_button.texture_normal == continent_texture,
		"pressing the small map again returns to the current map")

	# A click on a region of the continent opens that region's own tab map.
	main.call("_show_continent_view")
	await process_frame
	var mirrorhold_index: int = _index_of(regions, "mirrorhold")
	var display: Rect2 = overlay.call("region_rect", mirrorhold_index) as Rect2
	_expect(display.size.x > 0.0 and display.size.y > 0.0,
		"Mirrorhold has a rectangle on the drawn continent")
	var centre: Vector2 = display.get_center()
	_expect(int(overlay.call("region_at", centre)) == mirrorhold_index,
		"the middle of Mirrorhold's rectangle is Mirrorhold")
	_expect(int(overlay.call("region_at", Vector2(-50.0, -50.0))) == -1,
		"off the picture there is no region")
	var motion := InputEventMouseMotion.new()
	motion.position = centre
	overlay.call("_gui_input", motion)
	_expect(map_coordinates.text.contains("Mirrorhold"),
		"hovering a region names it in the sidebar")
	var click := InputEventMouseButton.new()
	click.button_index = MOUSE_BUTTON_LEFT
	click.pressed = true
	click.position = centre
	overlay.call("_gui_input", click)
	_expect(region_preview.visible and not continent_view.visible and not map_image.visible,
		"clicking a region shows its tab map")
	_expect(region_preview.texture != null
		and region_preview.texture.get_size() == Vector2(383.0, 383.0),
		"Mirrorhold's preview is its whole minimap, one pixel a metre")
	_expect(map_title.text == "MIRRORHOLD", "the title is the region's name")
	_expect(continent_button.texture_normal == continent_texture,
		"over a preview the small map shows the continent again")
	_expect(full_map_viewport.render_target_update_mode == SubViewport.UPDATE_DISABLED,
		"a preview idles the world render")

	# The cursor names server tiles over the preview, through the map's own
	# transform: the middle of Mirrorhold's compact 383 m framing is tile (191, 191).
	await process_frame
	var preview_centre: Vector2 = region_preview.size * 0.5
	var tile_value: Variant = main.call("_preview_tile_at", preview_centre)
	_expect(tile_value is Vector2i and (tile_value as Vector2i) == Vector2i(191, 191),
		"the middle of Mirrorhold's map is server tile (191, 191), got " + str(tile_value))
	var preview_motion := InputEventMouseMotion.new()
	preview_motion.position = preview_centre
	main.call("_on_region_preview_gui_input", preview_motion)
	_expect(map_coordinates.text == "Coordinates: 191, 191",
		"the sidebar reports the tile under the cursor")
	var off_picture := InputEventMouseMotion.new()
	off_picture.position = Vector2(-10.0, -10.0)
	main.call("_on_region_preview_gui_input", off_picture)
	_expect(map_coordinates.text == "Coordinates: outside map image",
		"off the picture there is no tile")
	main.call("_on_region_preview_mouse_exited")
	_expect(map_coordinates.text.begins_with("Coordinates:"),
		"leaving the preview clears the reading")

	# A preview is framed as the live Tab map frames the map: Sunmane to its
	# addressable tiles, Four Gates to its map bounds rather than its backdrop.
	main.call("_preview_region", _index_of(regions, "sunmane_steppe"))
	var sunmane_texture: Texture2D = region_preview.texture
	_expect(sunmane_texture is AtlasTexture
		and (sunmane_texture as AtlasTexture).region == Rect2(0.0, 1.0, 383.0, 383.0),
		"Sunmane's preview is the live map's framing, not the landform past its last tile")
	var four_gates_index: int = _index_of(regions, "four_gates")
	main.call("_preview_region", four_gates_index)
	_expect(map_image.visible and not region_preview.visible,
		"asking for the map you are standing on returns to the live map")
	app_state.set("current_map", "mirrorhold")
	main.call("_preview_region", four_gates_index)
	var four_gates_texture: Texture2D = region_preview.texture
	_expect(four_gates_texture != null and not four_gates_texture is AtlasTexture
		and four_gates_texture.get_size() == Vector2(396.0, 396.0),
		"Four Gates' preview frames the compact civic island")
	_expect(main.call("_tab_map_texture", regions[four_gates_index]) == four_gates_texture,
		"a tab map is decoded once and kept")
	_expect(map_title.text == "FOUR GATES", "the preview is titled with the map's name")

	# Mirrorhold is where the player stands now.
	main.call("_show_continent_view")
	_expect(int(overlay.get("_current_index")) == mirrorhold_index,
		"the continent marks the map the player stands on")
	overlay.call("_gui_input", motion)
	_expect(map_coordinates.text.contains("where you are"),
		"hovering your own map says so")
	overlay.call("_gui_input", click)
	_expect(map_image.visible and not region_preview.visible and not continent_view.visible,
		"clicking your own map on the continent returns to the live map")

	main.call("_show_continent_view")
	main.call("_preview_region", 99)
	_expect(continent_view.visible, "an unknown region index changes nothing")
	main.call("_toggle_full_map")
	_expect(not full_map.visible and full_map_viewport.render_target_update_mode
		== SubViewport.UPDATE_DISABLED, "closing the map window idles its viewport")
	main.call("_toggle_full_map")
	_expect(full_map.visible and map_image.visible and not continent_view.visible,
		"reopening the map window shows the current map")
	_finish()

func _index_of(regions: Array, server_map: String) -> int:
	for index: int in range(regions.size()):
		if str((regions[index] as Dictionary).get("serverMap", "")) == server_map:
			return index
	return -1

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)

func _finish() -> void:
	if failures == 0:
		print("continent map fixtures passed")
	else:
		print("continent map fixtures failed: ", failures)
	quit(failures)
