@tool
extends EditorDock

signal place_requested(entry: Dictionary)
signal add_at_center_requested(entry: Dictionary)
signal placement_cancel_requested

const Catalog := preload("res://addons/map_asset_palette/asset_catalog.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")

var _editor_interface: EditorInterface
var _entries: Array[Dictionary] = []
var _visible_entries: Array[Dictionary] = []
var _selected_entry: Dictionary = {}
var _preview_resources: Dictionary = {}
var _search: LineEdit
var _category: OptionButton
var _items: ItemList
var _preview: TextureRect
var _details: Label
var _place: Button
var _center: Button
var _cancel: Button
var _refresh: Button
var _status: Label
var _scene_available := false


func configure(editor_interface: EditorInterface) -> void:
	_editor_interface = editor_interface
	if _search == null:
		_build_ui()
	_reload_entries(false)


func set_scene_available(available: bool) -> void:
	_scene_available = available
	_update_buttons()
	if not available:
		set_placement_armed(false)
		_status.text = "Open the map authoring pilot to place assets."
	elif _selected_entry.is_empty():
		_status.text = "Choose an asset from the library."


func set_placement_armed(armed: bool, label: String = "") -> void:
	_cancel.visible = armed
	_place.disabled = armed or not _can_place()
	_center.disabled = armed or not _can_place()
	if armed:
		_status.text = "Click the terrain to place %s. Escape or right-click cancels." % label
	elif _scene_available and not _selected_entry.is_empty():
		_status.text = "Ready to place %s." % String(_selected_entry.label)


func show_message(message: String) -> void:
	_status.text = message


func status_text() -> String:
	return _status.text


func selected_entry() -> Dictionary:
	return _selected_entry.duplicate(true)


func visible_entry_ids() -> PackedStringArray:
	var result := PackedStringArray()
	for entry in _visible_entries:
		result.append(String(entry.id))
	return result


func has_usable_layout() -> bool:
	if _search == null or size.x <= 0.0 or size.y <= 0.0:
		return false
	var dock_rect := get_global_rect()
	for control: Control in [_search, _category, _refresh, _items, _preview,
			_place, _center, _cancel]:
		if not control.visible:
			continue
		var rect := control.get_global_rect()
		if rect.size.x <= 0.0 or rect.size.y <= 0.0 or \
				rect.position.x < dock_rect.position.x - 0.01 or \
				rect.position.y < dock_rect.position.y - 0.01 or \
				rect.end.x > dock_rect.end.x + 0.01 or \
				rect.end.y > dock_rect.end.y + 0.01:
			return false
	return true


func set_search_query(query: String) -> void:
	_search.text = query
	_apply_filter()


func select_category(category: String) -> void:
	for index in _category.item_count:
		if _category.get_item_text(index) == category:
			_category.select(index)
			_apply_filter()
			return


func select_entry_by_id(entry_id: String) -> bool:
	for index in _visible_entries.size():
		if String(_visible_entries[index].id) == entry_id:
			_items.select(index)
			_select_index(index)
			return true
	return false


func cancel_placement() -> void:
	placement_cancel_requested.emit()
	set_placement_armed(false)


func _build_ui() -> void:
	title = "Map Assets"
	layout_key = "MapAssetPalette"
	default_slot = EditorDock.DOCK_SLOT_RIGHT_BL
	icon_name = &"MeshInstance3D"
	name = "MapAssets"
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 8)
	margin.add_theme_constant_override("margin_top", 8)
	margin.add_theme_constant_override("margin_right", 8)
	margin.add_theme_constant_override("margin_bottom", 8)
	add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	margin.add_child(column)
	var heading := Label.new()
	heading.text = "Place library assets"
	heading.add_theme_font_size_override("font_size", 16)
	column.add_child(heading)
	_search = LineEdit.new()
	_search.placeholder_text = "Search assets…"
	_search.clear_button_enabled = true
	_search.text_changed.connect(func(_text: String) -> void: _apply_filter())
	column.add_child(_search)
	var filters := HBoxContainer.new()
	_category = OptionButton.new()
	_category.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_category.item_selected.connect(func(_index: int) -> void: _apply_filter())
	filters.add_child(_category)
	_refresh = Button.new()
	_refresh.text = "Refresh Library"
	_refresh.tooltip_text = "Reload objects.json and starter-scene entries."
	_refresh.pressed.connect(func() -> void: _reload_entries(true))
	filters.add_child(_refresh)
	column.add_child(filters)
	_items = ItemList.new()
	_items.custom_minimum_size = Vector2(260, 190)
	_items.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_items.item_selected.connect(_select_index)
	_items.item_activated.connect(func(index: int) -> void:
		_select_index(index)
		_request_place())
	column.add_child(_items)
	_preview = TextureRect.new()
	_preview.custom_minimum_size = Vector2(260, 150)
	_preview.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
	_preview.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	column.add_child(_preview)
	_details = Label.new()
	_details.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_details)
	var actions := HBoxContainer.new()
	_place = Button.new()
	_place.text = "Place on terrain"
	_place.tooltip_text = "Arm placement, then click the terrain in the 3D view."
	_place.pressed.connect(_request_place)
	actions.add_child(_place)
	_center = Button.new()
	_center.text = "Add at view center"
	_center.tooltip_text = "Place where the center of the 3D view meets the terrain."
	_center.pressed.connect(func() -> void:
		if _can_place(): add_at_center_requested.emit(selected_entry()))
	actions.add_child(_center)
	_cancel = Button.new()
	_cancel.text = "Cancel"
	_cancel.visible = false
	_cancel.pressed.connect(cancel_placement)
	column.add_child(actions)
	column.add_child(_cancel)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_status)


func _reload_entries(refresh_cache: bool) -> void:
	_cancel_if_armed()
	_entries = Catalog.entries(refresh_cache)
	var previous_category := _category.get_item_text(_category.selected) \
		if _category.item_count > 0 else "All"
	_category.clear()
	_category.add_item("All")
	for category in Catalog.categories(_entries):
		_category.add_item(category)
	select_category(previous_category)
	if _category.selected < 0:
		_category.select(0)
	_apply_filter()
	_status.text = "Library refreshed: %d assets." % _entries.size()


func _apply_filter() -> void:
	if _items == null:
		return
	_cancel_if_armed()
	var category := _category.get_item_text(_category.selected) \
		if _category.selected >= 0 else "All"
	_visible_entries = Catalog.filter_entries(_entries, _search.text, category)
	_items.clear()
	for entry in _visible_entries:
		_items.add_item(String(entry.label))
		_items.set_item_tooltip(_items.item_count - 1, "%s\n%s" % [
			String(entry.category), String(entry.scene_path)])
	_selected_entry = {}
	_preview.texture = null
	_details.text = "%d assets" % _visible_entries.size()
	_update_buttons()


func _select_index(index: int) -> void:
	if index < 0 or index >= _visible_entries.size():
		return
	_cancel_if_armed()
	_selected_entry = _visible_entries[index].duplicate(true)
	_details.text = "%s\n%s%s" % [String(_selected_entry.label),
		String(_selected_entry.category),
		" · %.2f m tall" % float(_selected_entry.height) \
			if float(_selected_entry.height) > 0.0 else ""]
	_preview.texture = null
	_queue_selected_preview()
	_update_buttons()
	if _scene_available:
		_status.text = "Ready to place %s." % String(_selected_entry.label)


func _queue_selected_preview() -> void:
	if _editor_interface == null or _selected_entry.is_empty():
		return
	var previewer := _editor_interface.get_resource_previewer()
	var entry_id := String(_selected_entry.id)
	if String(_selected_entry.source_node).is_empty():
		previewer.queue_resource_preview(String(_selected_entry.scene_path), self,
			&"_on_preview_ready", entry_id)
		return
	var packed := Placement.preview_scene(_selected_entry)
	if packed != null:
		_preview_resources[entry_id] = packed
		previewer.queue_edited_resource_preview(packed, self, &"_on_preview_ready", entry_id)


func _on_preview_ready(_path: String, preview: Texture2D, thumbnail: Texture2D,
		entry_id: Variant) -> void:
	var id := String(entry_id)
	_preview_resources.erase(id)
	if _selected_entry.is_empty() or String(_selected_entry.id) != id:
		return
	_preview.texture = preview if preview != null else thumbnail


func _request_place() -> void:
	if _can_place():
		place_requested.emit(selected_entry())


func _can_place() -> bool:
	return _scene_available and not _selected_entry.is_empty()


func _update_buttons() -> void:
	var armed := _cancel != null and _cancel.visible
	_place.disabled = armed or not _can_place()
	_center.disabled = armed or not _can_place()


func _cancel_if_armed() -> void:
	if _cancel != null and _cancel.visible:
		cancel_placement()
