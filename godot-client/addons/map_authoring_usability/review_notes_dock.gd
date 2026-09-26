@tool
extends EditorDock
## The review notes of the open territory (see review_notes.gd): a list, the
## text of the chosen note, and buttons to add one by clicking in the 3D view,
## save its text, resolve or reopen it, delete it and move the view to it.

signal add_requested(text: String)
signal text_saved(identity: String, text: String)
signal status_toggled(identity: String)
signal delete_requested(identity: String)
signal focus_requested(identity: String)

var _list: ItemList
var _text: LineEdit
var _status: Label
var _buttons: Dictionary = {}
var _confirm: ConfirmationDialog
var _ids := PackedStringArray()


func _init() -> void:
	title = "Review notes"
	layout_key = "MapAuthoringReviewNotes"
	default_slot = EditorDock.DOCK_SLOT_LEFT_BR
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(column)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(_status)
	_list = ItemList.new()
	_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_list.custom_minimum_size = Vector2(160, 120)
	_list.item_selected.connect(func(_index: int) -> void: _sync_selection())
	_list.item_activated.connect(func(index: int) -> void: focus_requested.emit(_ids[index]))
	column.add_child(_list)
	_text = LineEdit.new()
	_text.placeholder_text = "Note text"
	column.add_child(_text)
	var row := HFlowContainer.new()
	column.add_child(row)
	for pair: Array in [["add", "Add at click", "Click a spot in the 3D view to pin a new note with this text."],
			["save", "Save text", "Replace the chosen note's text."],
			["resolve", "Resolve", "Mark the chosen note resolved (or open again)."],
			["focus", "Go to", "Move the 3D view to the chosen note."],
			["delete", "Delete…", "Remove the chosen note from the notes file."]]:
		var button := Button.new()
		button.text = pair[1]
		button.tooltip_text = pair[2]
		row.add_child(button)
		_buttons[pair[0]] = button
	(_buttons.add as Button).pressed.connect(func() -> void: add_requested.emit(_text.text))
	(_buttons.save as Button).pressed.connect(func() -> void:
		if not selected_id().is_empty():
			text_saved.emit(selected_id(), _text.text))
	(_buttons.resolve as Button).pressed.connect(func() -> void:
		if not selected_id().is_empty():
			status_toggled.emit(selected_id()))
	(_buttons.focus as Button).pressed.connect(func() -> void:
		if not selected_id().is_empty():
			focus_requested.emit(selected_id()))
	_confirm = ConfirmationDialog.new()
	_confirm.title = "Delete review note"
	_confirm.confirmed.connect(func() -> void:
		if not selected_id().is_empty():
			delete_requested.emit(selected_id()))
	add_child(_confirm)
	(_buttons.delete as Button).pressed.connect(func() -> void:
		if selected_id().is_empty():
			return
		_confirm.dialog_text = "Delete %s from the notes file? This cannot be undone." % selected_id()
		if is_inside_tree():
			_confirm.popup_centered())
	show_notes([], "Open a territory to see its review notes.", false)


## Lists `notes` (review_notes.gd records); `writable` enables editing.
func show_notes(notes: Array, message: String, writable: bool) -> void:
	var previous := selected_id()
	_list.clear()
	_ids = PackedStringArray()
	for note: Dictionary in notes:
		var resolved := String(note.status) == "resolved"
		var index := _list.add_item("%s %s: %s" % ["✓" if resolved else "●", String(note.id),
			String(note.text)])
		_list.set_item_custom_fg_color(index, Color(0.62, 0.66, 0.7) if resolved else Color(1.0, 0.72, 0.4))
		_list.set_item_tooltip(index, String(note.text))
		_ids.append(String(note.id))
		if String(note.id) == previous:
			_list.select(index)
	_status.text = message
	_status.tooltip_text = message
	(_buttons.add as Button).disabled = not writable
	for key in ["save", "resolve", "delete"]:
		(_buttons[key] as Button).disabled = not writable
	_sync_selection()


func set_message(message: String) -> void:
	_status.text = message
	_status.tooltip_text = message


func selected_id() -> String:
	var chosen := _list.get_selected_items()
	return _ids[chosen[0]] if not chosen.is_empty() and chosen[0] < _ids.size() else ""


func select_id(identity: String) -> bool:
	var index := _ids.find(identity)
	if index < 0:
		return false
	_list.select(index)
	_sync_selection()
	return true


func text_field() -> LineEdit:
	return _text


func _sync_selection() -> void:
	var chosen := selected_id()
	(_buttons.focus as Button).disabled = chosen.is_empty()
	if not chosen.is_empty():
		var item := _list.get_item_text(_ids.find(chosen))
		_text.text = item.substr(item.find(": ") + 2)
		(_buttons.resolve as Button).text = "Reopen" if item.begins_with("✓") else "Resolve"
