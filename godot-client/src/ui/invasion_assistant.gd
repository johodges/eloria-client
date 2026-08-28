class_name InvasionAssistantWindow
extends Window

signal command_requested(command: String)

const MapCanvasScript := preload("res://src/ui/invasion_map_canvas.gd")

var map_registry: Dictionary = {}
var index_state: Dictionary = {}
var map_state: Dictionary = {}
var groups_state: Dictionary = {}
var monsters_state: Dictionary = {}
var selected_map_id := ""
var selected_group: Dictionary = {}
var selected_monster: Dictionary = {}

var tabs: TabContainer
var summary: Label
var map_filter: LineEdit
var map_list: ItemList
var map_canvas
var map_title: Label
var map_roster: RichTextLabel
var location_picker: OptionButton
var coordinate_x: SpinBox
var coordinate_y: SpinBox
var teleport_button: Button
var map_status: Label
var group_filter: LineEdit
var group_list: ItemList
var group_detail: RichTextLabel
var group_open_map: Button
var monster_filter: LineEdit
var monster_list: ItemList
var monster_detail: RichTextLabel
var status: Label


func _ready() -> void:
	title = "Invasion Assistant"
	size = Vector2i(1120, 720)
	min_size = Vector2i(900, 600)
	close_requested.connect(hide)
	_build_ui()
	hide()


func configure_registry(value: Dictionary) -> void:
	map_registry = value


func apply_update(update: Dictionary) -> void:
	var kind := str(update.get("kind", ""))
	match kind:
		"index":
			index_state = update.duplicate(true)
			selected_map_id = str(update.get("selected_map", selected_map_id))
			_rebuild_maps()
			_update_summary()
		"map":
			map_state = update.duplicate(true)
			var map: Dictionary = map_state.get("map", {}) as Dictionary
			selected_map_id = str(map.get("id", selected_map_id))
			_show_map_state()
		"groups":
			groups_state = update.duplicate(true)
			_rebuild_groups()
		"monsters":
			monsters_state = update.duplicate(true)
			_rebuild_monsters()
	if not visible:
		popup_centered(size)


func _build_ui() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 12)
	margin.add_theme_constant_override("margin_top", 10)
	margin.add_theme_constant_override("margin_right", 12)
	margin.add_theme_constant_override("margin_bottom", 10)
	add_child(margin)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 8)
	margin.add_child(root)

	var header := HBoxContainer.new()
	root.add_child(header)
	var heading := Label.new()
	heading.text = "INVASION ASSISTANT"
	heading.add_theme_font_size_override("font_size", 22)
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(heading)
	summary = Label.new()
	summary.text = "Waiting for server snapshot…"
	header.add_child(summary)
	var refresh_all := Button.new()
	refresh_all.text = "Refresh"
	refresh_all.tooltip_text = "Refresh map counts and the current tab from the server"
	refresh_all.pressed.connect(_refresh_current)
	header.add_child(refresh_all)

	tabs = TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.tab_changed.connect(_on_tab_changed)
	root.add_child(tabs)
	_build_maps_tab()
	_build_groups_tab()
	_build_monsters_tab()

	status = Label.new()
	status.text = "Server-authorized invasion masters only. Click the map to stage a teleport."
	status.add_theme_color_override("font_color", Color("9fc0d4"))
	root.add_child(status)


func _build_maps_tab() -> void:
	var page := HSplitContainer.new()
	page.name = "Maps"
	tabs.add_child(page)
	var sidebar := VBoxContainer.new()
	sidebar.custom_minimum_size.x = 250
	page.add_child(sidebar)
	map_filter = LineEdit.new()
	map_filter.placeholder_text = "Filter server maps…"
	map_filter.text_changed.connect(func(_value: String) -> void: _rebuild_maps())
	sidebar.add_child(map_filter)
	map_list = ItemList.new()
	map_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_list.item_selected.connect(_on_map_selected)
	map_list.item_activated.connect(_on_map_selected)
	sidebar.add_child(map_list)
	var legend := RichTextLabel.new()
	legend.bbcode_enabled = true
	legend.fit_content = true
	legend.custom_minimum_size.y = 92
	legend.text = ("[color=#68e7ff]●[/color] Player   "
		+ "[color=#ff6b63]◆[/color] Invader   "
		+ "[color=#ffc94f]◆[/color] Boss\n"
		+ "[color=#c8a8ff]■[/color] Spawn location   "
		+ "[color=#55cfee]■[/color] Portal\n"
		+ "Click anywhere to select exact coordinates.")
	sidebar.add_child(legend)

	var map_column := VBoxContainer.new()
	map_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_child(map_column)
	map_title = Label.new()
	map_title.text = "Select a map"
	map_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	map_title.add_theme_font_size_override("font_size", 18)
	map_column.add_child(map_title)
	var map_split := HSplitContainer.new()
	map_split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_column.add_child(map_split)
	map_canvas = MapCanvasScript.new()
	map_canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	map_canvas.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_canvas.coordinate_selected.connect(_on_coordinate_selected)
	map_split.add_child(map_canvas)
	map_roster = RichTextLabel.new()
	map_roster.bbcode_enabled = true
	map_roster.custom_minimum_size.x = 230
	map_roster.size_flags_vertical = Control.SIZE_EXPAND_FILL
	map_split.add_child(map_roster)

	var location_row := HBoxContainer.new()
	map_column.add_child(location_row)
	location_picker = OptionButton.new()
	location_picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	location_picker.item_selected.connect(_on_location_selected)
	location_row.add_child(location_picker)
	coordinate_x = SpinBox.new()
	coordinate_x.prefix = "X "
	coordinate_x.min_value = 0
	coordinate_x.max_value = 2047
	coordinate_x.custom_minimum_size.x = 115
	location_row.add_child(coordinate_x)
	coordinate_y = SpinBox.new()
	coordinate_y.prefix = "Y "
	coordinate_y.min_value = 0
	coordinate_y.max_value = 2047
	coordinate_y.custom_minimum_size.x = 115
	location_row.add_child(coordinate_y)
	teleport_button = Button.new()
	teleport_button.text = "Teleport"
	teleport_button.disabled = true
	teleport_button.tooltip_text = "Teleport your invasion-master character to the selected coordinates"
	teleport_button.pressed.connect(_teleport)
	location_row.add_child(teleport_button)
	map_status = Label.new()
	map_status.text = "Live markers are loaded on demand."
	map_status.add_theme_color_override("font_color", Color("a9bdc9"))
	map_column.add_child(map_status)


func _build_groups_tab() -> void:
	var page := HSplitContainer.new()
	page.name = "Spawn Groups"
	tabs.add_child(page)
	var list_column := VBoxContainer.new()
	list_column.custom_minimum_size.x = 430
	page.add_child(list_column)
	group_filter = LineEdit.new()
	group_filter.placeholder_text = "Filter by group, map, monster, or active…"
	group_filter.text_changed.connect(func(_value: String) -> void: _rebuild_groups())
	list_column.add_child(group_filter)
	group_list = ItemList.new()
	group_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	group_list.item_selected.connect(_on_group_selected)
	group_list.item_activated.connect(_on_group_selected)
	list_column.add_child(group_list)
	var detail_column := VBoxContainer.new()
	detail_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page.add_child(detail_column)
	group_detail = RichTextLabel.new()
	group_detail.bbcode_enabled = true
	group_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	group_detail.text = "Select a configured invasion spawn group."
	detail_column.add_child(group_detail)
	group_open_map = Button.new()
	group_open_map.text = "Open group map"
	group_open_map.disabled = true
	group_open_map.pressed.connect(_open_group_map)
	detail_column.add_child(group_open_map)


func _build_monsters_tab() -> void:
	var page := HSplitContainer.new()
	page.name = "Monsters"
	tabs.add_child(page)
	var list_column := VBoxContainer.new()
	list_column.custom_minimum_size.x = 470
	page.add_child(list_column)
	monster_filter = LineEdit.new()
	monster_filter.placeholder_text = "Filter type, name, tier, or configured…"
	monster_filter.text_changed.connect(func(_value: String) -> void: _rebuild_monsters())
	list_column.add_child(monster_filter)
	monster_list = ItemList.new()
	monster_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	monster_list.item_selected.connect(_on_monster_selected)
	list_column.add_child(monster_list)
	monster_detail = RichTextLabel.new()
	monster_detail.bbcode_enabled = true
	monster_detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	monster_detail.text = "Select an invadable monster to inspect its strength."
	page.add_child(monster_detail)


func _update_summary() -> void:
	var totals: Dictionary = index_state.get("totals", {}) as Dictionary
	summary.text = "%d players  •  %d invaders  •  %d active groups" % [
		int(totals.get("players", 0)), int(totals.get("invasions", 0)),
		int(totals.get("active_groups", 0))]


func _rebuild_maps() -> void:
	if map_list == null:
		return
	map_list.clear()
	var query := map_filter.text.strip_edges().to_lower()
	var selected_index := -1
	for raw_map: Variant in index_state.get("maps", []):
		var map := raw_map as Dictionary
		var searchable := "%s %s %s" % [map.get("id", ""), map.get("name", ""), map.get("file", "")]
		if not query.is_empty() and not query in searchable.to_lower():
			continue
		var label := "%s  ·  %dP / %dI" % [str(map.get("name", map.get("id", "Map"))),
			int(map.get("players", 0)), int(map.get("invasions", 0))]
		if int(map.get("active_groups", 0)) > 0:
			label += " / %dG" % int(map.get("active_groups", 0))
		var item := map_list.add_item(label)
		map_list.set_item_metadata(item, map)
		map_list.set_item_tooltip(item, "%s\n%s" % [map.get("id", ""), map.get("file", "")])
		if str(map.get("id", "")) == selected_map_id:
			selected_index = item
	if selected_index >= 0:
		map_list.select(selected_index)
		map_list.ensure_current_is_visible()


func _on_map_selected(index: int) -> void:
	var map: Dictionary = map_list.get_item_metadata(index) as Dictionary
	selected_map_id = str(map.get("id", ""))
	map_status.text = "Refreshing live markers for %s…" % map.get("name", selected_map_id)
	command_requested.emit("#invasion_assistant map " + selected_map_id)


func _show_map_state() -> void:
	var map: Dictionary = map_state.get("map", {}) as Dictionary
	var display_state: Dictionary = map_state.duplicate(true)
	var locations: Array = (display_state.get("locations", []) as Array).duplicate(true)
	locations.append_array(_local_landmarks(str(map.get("id", ""))))
	display_state["locations"] = locations
	map_title.text = "%s  —  %s" % [str(map.get("name", "Map")), str(map.get("id", ""))]
	coordinate_x.max_value = maxi(0, int(map.get("width", 2048)) - 1)
	coordinate_y.max_value = maxi(0, int(map.get("height", 2048)) - 1)
	teleport_button.disabled = false
	location_picker.clear()
	location_picker.add_item("Named locations…")
	location_picker.set_item_metadata(0, {})
	for raw_location: Variant in locations:
		var location := raw_location as Dictionary
		location_picker.add_item("%s  [%d, %d]" % [str(location.get("name", "Location")),
			int(location.get("x", 0)), int(location.get("y", 0))])
		location_picker.set_item_metadata(location_picker.item_count - 1, location)
	map_canvas.set_map_state(display_state, _map_texture(str(map.get("id", ""))))
	_rebuild_roster()
	map_status.text = "%d named locations, %d players, %d invasion creatures. Live markers are server-authoritative." % [
		locations.size(),
		(map_state.get("players", []) as Array).size(),
		(map_state.get("creatures", []) as Array).size()]
	_rebuild_maps()


func _rebuild_roster() -> void:
	var lines: Array[String] = ["[b]LIVE PLAYERS[/b]"]
	var players: Array = map_state.get("players", []) as Array
	if players.is_empty():
		lines.append("[color=#8296a3]None[/color]")
	for raw_player: Variant in players:
		var player := raw_player as Dictionary
		lines.append("[color=#68e7ff]●[/color] %s  CL %d  [%d,%d]" % [
			player.get("name", "Player"), player.get("combat_level", 0),
			player.get("x", 0), player.get("y", 0)])
	lines.append("\n[b]INVASION CREATURES[/b]")
	var creatures: Array = map_state.get("creatures", []) as Array
	if creatures.is_empty():
		lines.append("[color=#8296a3]None[/color]")
	for raw_creature: Variant in creatures:
		var creature := raw_creature as Dictionary
		var marker := "[color=#ffc94f]◆[/color]" if bool(creature.get("boss", false)) else "[color=#ff6b63]◆[/color]"
		lines.append("%s %s\n   %s · %d/%d HP · [%d,%d]" % [marker,
			creature.get("name", "Invader"), creature.get("tier", "Unknown"),
			creature.get("health", 0), creature.get("max_health", 0),
			creature.get("x", 0), creature.get("y", 0)])
	map_roster.text = "\n".join(lines)


func _on_coordinate_selected(tile: Vector2i) -> void:
	coordinate_x.value = tile.x
	coordinate_y.value = tile.y
	location_picker.select(0)
	map_status.text = "Selected %d, %d on %s." % [tile.x, tile.y, selected_map_id]


func _on_location_selected(index: int) -> void:
	var location: Dictionary = location_picker.get_item_metadata(index) as Dictionary
	if location.is_empty():
		return
	coordinate_x.value = int(location.get("x", 0))
	coordinate_y.value = int(location.get("y", 0))
	map_canvas.selected_tile = Vector2i(int(coordinate_x.value), int(coordinate_y.value))
	map_canvas.queue_redraw()


func _teleport() -> void:
	if selected_map_id.is_empty():
		return
	var x := int(coordinate_x.value)
	var y := int(coordinate_y.value)
	status.text = "Teleporting to %s [%d, %d]…" % [selected_map_id, x, y]
	command_requested.emit("#invasion_assistant teleport %s %d %d" % [selected_map_id, x, y])


func _rebuild_groups() -> void:
	if group_list == null:
		return
	group_list.clear()
	var query := group_filter.text.strip_edges().to_lower()
	for raw_group: Variant in groups_state.get("groups", []):
		var group := raw_group as Dictionary
		var searchable := "%s %s %s %s %s" % [group.get("name", ""),
			group.get("description", ""), group.get("map_name", ""),
			" ".join(group.get("creatures", []) as Array),
			"active" if bool(group.get("active", false)) else "inactive"]
		if not query.is_empty() and not query in searchable.to_lower():
			continue
		var activity := "ACTIVE %d" % int(group.get("alive", 0)) if bool(group.get("active", false)) else "ready"
		var item := group_list.add_item("%s  ·  %s  ·  %s" % [
			group.get("name", "Group"), group.get("map_name", "Map"), activity])
		group_list.set_item_metadata(item, group)


func _on_group_selected(index: int) -> void:
	selected_group = (group_list.get_item_metadata(index) as Dictionary).duplicate(true)
	group_open_map.disabled = str(selected_group.get("map_id", "")).is_empty()
	var creatures: Array = selected_group.get("creatures", []) as Array
	group_detail.text = ("[font_size=22][b]%s[/b][/font_size]\n%s\n\n"
		+ "[b]Map[/b]  %s (%s)\n"
		+ "[b]Population[/b]  %d–%d across %d authored points\n"
		+ "[b]Current state[/b]  %s\n"
		+ "[b]Creature types[/b]  %s\n"
		+ "[b]Peak strength rating[/b]  %d\n"
		+ "[b]Spawn health multiplier[/b]  ×%.2f\n"
		+ "[b]Boss[/b]  %s") % [
		selected_group.get("name", "Group"), selected_group.get("description", ""),
		selected_group.get("map_name", ""), selected_group.get("map_id", ""),
		selected_group.get("minimum", 0), selected_group.get("maximum", 0),
		selected_group.get("points", 0),
		("ACTIVE — %d alive" % int(selected_group.get("alive", 0))) if bool(selected_group.get("active", false)) else "Ready",
		", ".join(creatures), selected_group.get("strength", 0),
		float(selected_group.get("health_multiplier", 1.0)),
		selected_group.get("boss", "None") if not str(selected_group.get("boss", "")).is_empty() else "None"]


func _open_group_map() -> void:
	selected_map_id = str(selected_group.get("map_id", ""))
	tabs.current_tab = 0
	command_requested.emit("#invasion_assistant map " + selected_map_id)


func _rebuild_monsters() -> void:
	if monster_list == null:
		return
	monster_list.clear()
	var query := monster_filter.text.strip_edges().to_lower()
	for raw_monster: Variant in monsters_state.get("monsters", []):
		var monster := raw_monster as Dictionary
		var searchable := "%s %s %s %s" % [monster.get("type", ""),
			monster.get("name", ""), monster.get("tier", ""),
			"configured" if bool(monster.get("configured", false)) else "available"]
		if not query.is_empty() and not query in searchable.to_lower():
			continue
		var configured := "★ " if bool(monster.get("configured", false)) else ""
		var item := monster_list.add_item("%s%s  ·  %-10s  ·  rating %d" % [
			configured, monster.get("name", "Monster"), monster.get("tier", "Unknown"),
			monster.get("rating", 0)])
		monster_list.set_item_metadata(item, monster)


func _on_monster_selected(index: int) -> void:
	selected_monster = (monster_list.get_item_metadata(index) as Dictionary).duplicate(true)
	monster_detail.text = ("[font_size=22][b]%s[/b][/font_size]\n[color=#9fc0d4]%s[/color]\n\n"
		+ "[b]General strength[/b]  %s (rating %d)\n"
		+ "[b]Combat level[/b]  %d\n[b]Native level[/b]  %d\n"
		+ "[b]Health / Ether[/b]  %d / %d\n"
		+ "[b]Attack / Defense[/b]  %d / %d\n"
		+ "[b]Damage[/b]  %d–%d\n[b]Armor[/b]  %d–%d\n\n"
		+ "%s") % [selected_monster.get("name", "Monster"),
		selected_monster.get("type", ""), selected_monster.get("tier", "Unknown"),
		selected_monster.get("rating", 0), selected_monster.get("combat_level", 0),
		selected_monster.get("level", 0), selected_monster.get("health", 0),
		selected_monster.get("ether", 0), selected_monster.get("attack", 0),
		selected_monster.get("defense", 0), selected_monster.get("damage_min", 0),
		selected_monster.get("damage_max", 0), selected_monster.get("armor_min", 0),
		selected_monster.get("armor_max", 0),
		("[color=#ffd36a]★ Used by a configured invasion spawn group[/color]"
		if bool(selected_monster.get("configured", false)) else
		"Available for ad-hoc invasion spawning")]


func _on_tab_changed(tab: int) -> void:
	if tab == 1 and groups_state.is_empty():
		status.text = "Loading invasion spawn groups…"
		command_requested.emit("#invasion_assistant groups")
	elif tab == 2 and monsters_state.is_empty():
		status.text = "Loading invadable monsters…"
		command_requested.emit("#invasion_assistant monsters")


func _refresh_current() -> void:
	command_requested.emit("#invasion_assistant refresh")
	match tabs.current_tab:
		0:
			if not selected_map_id.is_empty():
				command_requested.emit("#invasion_assistant map " + selected_map_id)
		1:
			command_requested.emit("#invasion_assistant groups")
		2:
			command_requested.emit("#invasion_assistant monsters")
	status.text = "Refreshing server-authoritative data…"


func _map_texture(map_id: String) -> Texture2D:
	if map_registry.is_empty():
		return null
	var entry: Dictionary = MapRegistry.resolve(map_registry, map_id)
	var manifest_path := str(entry.get("manifest", ""))
	if manifest_path.is_empty():
		return null
	var minimap_path := manifest_path.get_base_dir().path_join("minimap.webp")
	if not ResourceLoader.exists(minimap_path):
		return null
	return load(minimap_path) as Texture2D


func _local_landmarks(map_id: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	if map_registry.is_empty():
		return result
	var entry: Dictionary = MapRegistry.resolve(map_registry, map_id)
	var manifest_path := str(entry.get("manifest", ""))
	if manifest_path.is_empty() or not FileAccess.file_exists(manifest_path):
		return result
	var file := FileAccess.open(manifest_path, FileAccess.READ)
	if file == null:
		return result
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		return result
	var manifest := parsed as Dictionary
	var transform: Dictionary = entry.get("coordinateTransform",
		manifest.get("coordinateTransform", {})) as Dictionary
	var adapter := CoordinateAdapter.new(transform)
	var seen: Dictionary = {}
	for section: String in ["landmarks", "pointsOfInterest", "spawnPoints"]:
		var raw_entries: Variant = manifest.get(section, [])
		if not raw_entries is Array:
			continue
		for raw_landmark: Variant in raw_entries as Array:
			if not raw_landmark is Dictionary:
				continue
			var landmark := raw_landmark as Dictionary
			var tile := Vector2i(-1, -1)
			var server_tile: Variant = landmark.get("serverTile", [])
			if server_tile is Array and (server_tile as Array).size() >= 2:
				tile = Vector2i(int(server_tile[0]), int(server_tile[1]))
			else:
				var raw_position: Variant = landmark.get("position", [])
				if raw_position is Array and (raw_position as Array).size() >= 3:
					tile = adapter.godot_to_server(Vector3(
						float(raw_position[0]), float(raw_position[1]), float(raw_position[2])))
			if tile.x < 0 or tile.y < 0:
				continue
			var name := str(landmark.get("name", landmark.get("id",
				landmark.get("kind", "Landmark")))).replace("_", " ").capitalize()
			var key := "%s:%d:%d" % [name, tile.x, tile.y]
			if seen.has(key):
				continue
			seen[key] = true
			result.append({"name": name, "kind": "landmark", "x": tile.x,
				"y": tile.y, "source": "client_map"})
	return result
