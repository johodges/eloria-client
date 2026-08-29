extends Control
## The reference windows: help, notes, links and the encyclopedia.
##
## The legacy client had ten of these, all XML- or file-driven, and this client
## had none. The four here are the ones that can be built honestly:
##
## * **Help** is generated from the client's own input map and console table,
##   so it can never drift from what the keys and commands actually are. A
##   help page maintained by hand goes stale the first time a key moves.
## * **Notes** is the player's own notepad, kept in the client's settings file.
## * **Links** collects the addresses the server has said in chat, so a URL
##   scrolling past is not lost. It reads what arrived; it invents nothing.
## * **Encyclopedia** is original Eloria reference text describing this
##   server's own rules.
##
## The rest are recorded in the traceability matrix rather than faked: skills
## already have a window, and rules and astrology are server policy this
## server states only as chat text, which this client must not parse.
##
## The script declares no `class_name`: a global class is parsed before the
## autoload singletons are registered, and this reads `AppState` directly.

const ENCYCLOPEDIA := "res://data/reference/encyclopedia.json"
const PANEL_SIZE := Vector2(600.0, 420.0)
## Nothing may cover the fixed resource rail down the right-hand edge.
const RESERVED_RIGHT_RAIL := 96.0

signal notes_changed(text: String)

var panel: PanelContainer
var tabs: TabContainer
var help_text: RichTextLabel
var notes_edit: TextEdit
var links_list: ItemList
var entry_list: ItemList
var entry_body: RichTextLabel

var console_commands: ConsoleCommands
var bindable: Dictionary = {}
var _entries: Array[Dictionary] = []

func _ready() -> void:
	name = "ReferenceLayer"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_load_entries()
	_build()
	AppState.state_changed.connect(_on_state_changed)

func configure(commands: ConsoleCommands, bindable_actions: Dictionary,
		notes: String) -> void:
	console_commands = commands
	bindable = bindable_actions
	notes_edit.text = notes
	_refresh_help()

func is_open() -> bool:
	return panel.visible

func toggle() -> void:
	panel.visible = not panel.visible
	if panel.visible:
		panel.move_to_front()
		_refresh_help()
		_refresh_links()

func close() -> void:
	panel.hide()

func tab_titles() -> Array[String]:
	var titles: Array[String] = []
	for index: int in range(tabs.get_tab_count()):
		titles.append(tabs.get_tab_title(index))
	return titles

func entry_count() -> int:
	return _entries.size()

## Every address the server has said, oldest first and each one only once.
func known_links() -> Array[String]:
	var found: Array[String] = []
	for line_value: Variant in AppState.chat_lines:
		for url: String in ConsoleCommands.urls_in(
				str((line_value as Dictionary).get("text", ""))):
			if not found.has(url):
				found.append(url)
	return found

func _on_state_changed(path: StringName) -> void:
	if path == &"chat" and panel.visible:
		_refresh_links()

## Built from the input map and the console table rather than written out, so
## a rebound key or a new command is in the help the moment it exists.
func _refresh_help() -> void:
	var lines: Array[String] = ["[b]Keys[/b]"]
	for group: Variant in bindable:
		lines.append("[i]%s[/i]" % str(group))
		for action: Variant in bindable[group]:
			var name: String = str(action)
			if not InputMap.has_action(name):
				continue
			var events: Array[InputEvent] = InputMap.action_get_events(name)
			var described: String = "unbound"
			if not events.is_empty() and events[0] is InputEventKey:
				var key: InputEventKey = events[0] as InputEventKey
				var parts: Array[String] = []
				if key.ctrl_pressed:
					parts.append("Ctrl")
				if key.shift_pressed:
					parts.append("Shift")
				if key.alt_pressed:
					parts.append("Alt")
				parts.append(OS.get_keycode_string(key.physical_keycode))
				described = "+".join(parts)
			lines.append("  %s  -  %s" % [described, name.replace("_", " ")])
	lines.append("")
	lines.append("[b]Commands this client answers itself[/b]")
	if console_commands != null:
		for command: Variant in ConsoleCommands.COMMANDS:
			lines.append("  %s  -  %s" % [str(command),
				str(ConsoleCommands.COMMANDS[command])])
	lines.append("")
	lines.append("Anything else you type beginning with # is sent to the"
		+ " server exactly as written.")
	help_text.text = "\n".join(lines)

func _refresh_links() -> void:
	var links: Array[String] = known_links()
	if links.size() == links_list.item_count:
		return
	links_list.clear()
	for url: String in links:
		links_list.add_item(url)
	if links.is_empty():
		links_list.add_item("Nothing has been linked yet.")
		links_list.set_item_disabled(0, true)

func _load_entries() -> void:
	var file := FileAccess.open(ENCYCLOPEDIA, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		return
	for raw_entry: Variant in (parsed as Dictionary).get("entries", []):
		if raw_entry is Dictionary:
			_entries.append(raw_entry as Dictionary)

func _show_entry(index: int) -> void:
	if index < 0 or index >= _entries.size():
		return
	var entry: Dictionary = _entries[index]
	entry_body.text = "[b]%s[/b]\n\n%s" % [str(entry.get("title", "")),
		str(entry.get("body", ""))]

func _on_notes_changed() -> void:
	notes_changed.emit(notes_edit.text)

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "ReferenceWindow"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.position = Vector2(
		(1280.0 - RESERVED_RIGHT_RAIL - PANEL_SIZE.x) * 0.5, 80.0)
	panel.custom_minimum_size = PANEL_SIZE
	panel.size = PANEL_SIZE
	panel.hide()
	add_child(panel)

	var column := VBoxContainer.new()
	column.name = "ReferenceBody"
	panel.add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var title := Label.new()
	title.name = "ReferenceTitle"
	title.text = "Reference"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.name = "ReferenceClose"
	close_button.text = tr("ELORIA_SETTINGS_CLOSE")
	close_button.pressed.connect(close)
	header.add_child(close_button)

	tabs = TabContainer.new()
	tabs.name = "ReferenceTabs"
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(tabs)

	var help_page := VBoxContainer.new()
	help_page.name = "Help"
	tabs.add_child(help_page)
	var help_scroll := ScrollContainer.new()
	help_scroll.name = "HelpScroll"
	help_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	help_page.add_child(help_scroll)
	help_text = RichTextLabel.new()
	help_text.name = "HelpText"
	help_text.bbcode_enabled = true
	help_text.fit_content = true
	help_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	help_scroll.add_child(help_text)

	var notes_page := VBoxContainer.new()
	notes_page.name = "Notes"
	tabs.add_child(notes_page)
	notes_edit = TextEdit.new()
	notes_edit.name = "NotesEdit"
	notes_edit.size_flags_vertical = Control.SIZE_EXPAND_FILL
	notes_edit.placeholder_text = "Your own notes. Kept on this machine."
	notes_edit.text_changed.connect(_on_notes_changed)
	notes_page.add_child(notes_edit)

	var links_page := VBoxContainer.new()
	links_page.name = "Links"
	tabs.add_child(links_page)
	links_list = ItemList.new()
	links_list.name = "LinksList"
	links_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	links_page.add_child(links_list)

	var entries_page := HSplitContainer.new()
	entries_page.name = "Encyclopedia"
	tabs.add_child(entries_page)
	entry_list = ItemList.new()
	entry_list.name = "EntryList"
	entry_list.custom_minimum_size = Vector2(180.0, 0.0)
	entry_list.item_selected.connect(_show_entry)
	entries_page.add_child(entry_list)
	entry_body = RichTextLabel.new()
	entry_body.name = "EntryBody"
	entry_body.bbcode_enabled = true
	entries_page.add_child(entry_body)
	for entry: Dictionary in _entries:
		entry_list.add_item(str(entry.get("title", "")))
	if not _entries.is_empty():
		entry_list.select(0)
		_show_entry(0)
