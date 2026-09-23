@tool
extends EditorDock

signal open_requested(scene_path: String)
signal references_changed(ids: PackedStringArray)
signal refresh_requested

var _entries: Array[Dictionary] = []
var _active_id := ""
var _selected_ids := PackedStringArray()
var _active: Label
var _territory: OptionButton
var _open: Button
var _references: ItemList
var _hide: Button
var _refresh: Button
var _status: Label


func configure(entries: Array[Dictionary], active_id: String,
		selected_ids := PackedStringArray()) -> void:
	if _active == null:
		_build_ui()
	_entries = entries.duplicate(true)
	_active_id = active_id
	_selected_ids = selected_ids.duplicate()
	_rebuild()


func show_status(message: String) -> void:
	if _status != null:
		_status.text = message


func selected_reference_ids() -> PackedStringArray:
	return _selected_ids.duplicate()


func _build_ui() -> void:
	title = "Territories"
	layout_key = "MapAuthoringWorkspace"
	default_slot = EditorDock.DOCK_SLOT_RIGHT_BL
	icon_name = &"WorldEnvironment"
	name = "MapAuthoringWorkspace"
	var margin := MarginContainer.new()
	for side in ["margin_left", "margin_top", "margin_right", "margin_bottom"]:
		margin.add_theme_constant_override(side, 8)
	add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 6)
	margin.add_child(column)
	var heading := Label.new()
	heading.text = "Territory workspace"
	heading.add_theme_font_size_override("font_size", 16)
	column.add_child(heading)
	_active = Label.new()
	_active.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_active)
	var row := HBoxContainer.new()
	_territory = OptionButton.new()
	_territory.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_territory.item_selected.connect(func(_index: int) -> void: _update_open())
	row.add_child(_territory)
	_open = Button.new()
	_open.text = "Open"
	_open.pressed.connect(_open_selected)
	row.add_child(_open)
	column.add_child(row)
	var reference_label := Label.new()
	reference_label.text = "Read-only references"
	column.add_child(reference_label)
	_references = ItemList.new()
	_references.select_mode = ItemList.SELECT_MULTI
	_references.custom_minimum_size = Vector2(270, 180)
	_references.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_references.multi_selected.connect(func(_index: int, _selected: bool) -> void:
		_collect_reference_selection())
	column.add_child(_references)
	var actions := HBoxContainer.new()
	_hide = Button.new()
	_hide.text = "Hide all"
	_hide.pressed.connect(_hide_all)
	actions.add_child(_hide)
	_refresh = Button.new()
	_refresh.text = "Refresh sources"
	_refresh.tooltip_text = "Reload the territory catalog and selected saved/published references."
	_refresh.pressed.connect(func() -> void: refresh_requested.emit())
	actions.add_child(_refresh)
	column.add_child(actions)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_status)


func _rebuild() -> void:
	_active.text = "Active: %s" % (_label(_active_id) if not _active_id.is_empty() \
		else "Open an authored territory scene")
	_territory.clear()
	for entry in _entries:
		_territory.add_item("%s — %s" % [String(entry.label),
			"editable" if bool(entry.editable) else "published reference only"])
		_territory.set_item_metadata(_territory.item_count - 1, String(entry.id))
		_territory.set_item_tooltip(_territory.item_count - 1, _tooltip(entry))
		if String(entry.id) == _active_id:
			_territory.select(_territory.item_count - 1)
	_references.clear()
	for entry in _entries:
		if String(entry.id) == _active_id:
			continue
		_references.add_item("%s — %s" % [String(entry.label), String(entry.source_label)])
		var index := _references.item_count - 1
		_references.set_item_metadata(index, String(entry.id))
		_references.set_item_tooltip(index, _tooltip(entry))
		if String(entry.id) in _selected_ids:
			_references.select(index, false)
	_update_open()
	_hide.disabled = _selected_ids.is_empty()
	_status.text = "Choose neighbours to compare in the active territory's local frame." \
		if not _active_id.is_empty() else "Open an authored territory scene first."


func _update_open() -> void:
	var entry := _selected_entry()
	_open.disabled = entry.is_empty() or not bool(entry.editable) or \
		String(entry.id) == _active_id
	_open.tooltip_text = "Open this saved authored scene in its native editor tab." \
		if not _open.disabled else "This territory has no complete authored source yet."


func _open_selected() -> void:
	var entry := _selected_entry()
	if not entry.is_empty() and bool(entry.editable):
		open_requested.emit(String(entry.scene_path))


func _selected_entry() -> Dictionary:
	if _territory.selected < 0:
		return {}
	var id := String(_territory.get_item_metadata(_territory.selected))
	for entry in _entries:
		if String(entry.id) == id:
			return entry
	return {}


func _collect_reference_selection() -> void:
	_selected_ids.clear()
	for index in _references.get_selected_items():
		_selected_ids.append(String(_references.get_item_metadata(index)))
	_hide.disabled = _selected_ids.is_empty()
	references_changed.emit(_selected_ids.duplicate())


func _hide_all() -> void:
	_references.deselect_all()
	_selected_ids.clear()
	_hide.disabled = true
	references_changed.emit(PackedStringArray())


func _label(id: String) -> String:
	for entry in _entries:
		if String(entry.id) == id:
			return String(entry.label)
	return id


func _tooltip(entry: Dictionary) -> String:
	return "%s\n%s\nrevision %s\n%s" % [String(entry.source_label),
		String(entry.source_path), String(entry.revision), String(entry.source_sha256)]
