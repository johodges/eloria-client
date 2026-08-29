extends Control
## The tabbed settings window, and the key-rebinding UI.
##
## The client had one flat panel with four controls and 26 fixed input actions
## that could not be rebound at all. The legacy client had 296 options across
## eleven tabs and 102 bindings; most of those options are fixed-function
## OpenGL toggles that mean nothing to a Godot GL-Compatibility client, so this
## carries the ones that do and the traceability row records what was dropped.
##
## Every setting here is about this machine and this screen. None of it is sent
## to the server, and none of it changes what the server decides - the gameplay
## tab's entries are commands the server owns, sent as the player's own words
## rather than applied locally.
##
## The script declares no `class_name`: a global class is parsed before the
## autoload singletons are registered, and this reads `AppState` directly.

const PANEL_SIZE := Vector2(560.0, 430.0)
## Nothing may cover the fixed resource rail down the right-hand edge.
const RESERVED_RIGHT_RAIL := 96.0

## The actions a player may rebind, grouped the way they are used. Actions the
## client does not own - text editing inside a LineEdit, for instance - are not
## offered, because rebinding them would break the box they are typed in.
const BINDABLE := {
	"Movement": ["move_north", "move_south", "move_west", "move_east",
		"turn_left", "turn_right", "recenter_viewport"],
	"Windows": ["toggle_inventory", "toggle_map", "toggle_minimap",
		"toggle_console", "toggle_encyclopedia", "chat_focus"],
	"Actions": ["attack_selected", "toggle_sit", "cancel", "connect",
		"disconnect"],
	"Items": ["quick_item_1", "quick_item_2", "quick_item_3", "quick_item_4",
		"quick_item_5", "quick_item_6", "quick_item_7", "quick_item_8"],
	"Spells": ["quick_spell_1", "quick_spell_2", "quick_spell_3",
		"quick_spell_4", "quick_spell_5", "quick_spell_6", "quick_spell_7",
		"quick_spell_8", "quick_spell_9", "quick_spell_10", "quick_spell_11",
		"quick_spell_12"],
}

signal setting_changed(section: String, key: String, value: Variant)
signal binding_changed(action: String)

var panel: PanelContainer
var tabs: TabContainer
var binding_rows: Dictionary = {}
var capture_label: Label

## The action waiting for a key. While this is set the window swallows every
## key press, so a rebind cannot fire the action it is rebinding.
var capturing := ""

func _ready() -> void:
	name = "SettingsLayer"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()

func is_open() -> bool:
	return panel.visible

func toggle() -> void:
	panel.visible = not panel.visible
	if panel.visible:
		panel.move_to_front()
		_refresh_bindings()
	else:
		capturing = ""

func close() -> void:
	capturing = ""
	panel.hide()

## The tab titles, in order. Used by the tests and by nothing else.
func tab_titles() -> Array[String]:
	var titles: Array[String] = []
	for index: int in range(tabs.get_tab_count()):
		titles.append(tabs.get_tab_title(index))
	return titles

func begin_capture(action: String) -> void:
	capturing = action
	capture_label.text = tr("ELORIA_SETTINGS_CAPTURE").format({"action": action})
	capture_label.show()

## Applies a captured key to an action. Returns false when the event is not a
## key, or when the player pressed Escape to keep what they had.
func apply_capture(event: InputEvent) -> bool:
	if capturing.is_empty() or not event is InputEventKey:
		return false
	var key: InputEventKey = event as InputEventKey
	var action: String = capturing
	capturing = ""
	capture_label.hide()
	if key.physical_keycode == KEY_ESCAPE:
		return false
	var binding := InputEventKey.new()
	binding.physical_keycode = key.physical_keycode
	binding.shift_pressed = key.shift_pressed
	binding.ctrl_pressed = key.ctrl_pressed
	binding.alt_pressed = key.alt_pressed
	InputMap.action_erase_events(action)
	InputMap.action_add_event(action, binding)
	_refresh_bindings()
	binding_changed.emit(action)
	return true

## Every rebound action, as text this client can store and read back. An
## action whose binding cannot be written as text is left out rather than
## stored as an empty string, which would read back as "unbind this".
func stored_bindings() -> Dictionary:
	var stored: Dictionary = {}
	for group: Variant in BINDABLE:
		for action: Variant in BINDABLE[group]:
			var name: String = str(action)
			if not InputMap.has_action(name):
				continue
			var events: Array[InputEvent] = InputMap.action_get_events(name)
			if events.is_empty():
				continue
			var described: String = _describe(events[0])
			if not described.is_empty():
				stored[name] = described
	return stored

## Restores bindings saved by a previous session.
##
## A stored value that cannot be read back leaves the action exactly as it is.
## Erasing first and then failing to parse would silently unbind the action,
## which is how a settings file written by an older build could take the map
## key away and leave nothing to press.
func restore_bindings(stored: Dictionary) -> int:
	var restored := 0
	for action: Variant in stored:
		var name: String = str(action)
		if not InputMap.has_action(name):
			continue
		var event: InputEventKey = _parse(str(stored[action]))
		if event == null:
			continue
		InputMap.action_erase_events(name)
		InputMap.action_add_event(name, event)
		restored += 1
	_refresh_bindings()
	return restored

func _describe(event: InputEvent) -> String:
	if not event is InputEventKey:
		return ""
	var key: InputEventKey = event as InputEventKey
	var parts: Array[String] = []
	if key.ctrl_pressed:
		parts.append("Ctrl")
	if key.shift_pressed:
		parts.append("Shift")
	if key.alt_pressed:
		parts.append("Alt")
	parts.append(OS.get_keycode_string(key.physical_keycode))
	return "+".join(parts)

func _parse(described: String) -> InputEventKey:
	if described.is_empty():
		return null
	var parts: PackedStringArray = described.split("+", false)
	var event := InputEventKey.new()
	for part: String in parts:
		match part:
			"Ctrl":
				event.ctrl_pressed = true
			"Shift":
				event.shift_pressed = true
			"Alt":
				event.alt_pressed = true
			_:
				event.physical_keycode = OS.find_keycode_from_string(part)
	return event if event.physical_keycode != 0 else null

func _refresh_bindings() -> void:
	for action: Variant in binding_rows:
		var button: Button = binding_rows[action] as Button
		var events: Array[InputEvent] = (InputMap.action_get_events(str(action))
			if InputMap.has_action(str(action)) else [])
		button.text = (_describe(events[0]) if not events.is_empty()
			else tr("ELORIA_SETTINGS_UNBOUND"))

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "SettingsWindow"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.position = Vector2(
		(1280.0 - RESERVED_RIGHT_RAIL - PANEL_SIZE.x) * 0.5, 90.0)
	panel.custom_minimum_size = PANEL_SIZE
	panel.size = PANEL_SIZE
	panel.hide()
	add_child(panel)

	var column := VBoxContainer.new()
	column.name = "SettingsBody"
	panel.add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var title := Label.new()
	title.name = "SettingsTitle"
	title.text = tr("ELORIA_SETTINGS_TITLE")
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.name = "SettingsWindowClose"
	close_button.text = tr("ELORIA_SETTINGS_CLOSE")
	close_button.pressed.connect(close)
	header.add_child(close_button)

	tabs = TabContainer.new()
	tabs.name = "SettingsTabs"
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(tabs)
	_build_graphics()
	_build_camera()
	_build_gameplay()
	_build_controls()

	capture_label = Label.new()
	capture_label.name = "SettingsCapture"
	capture_label.hide()
	column.add_child(capture_label)

func _build_graphics() -> void:
	var page := VBoxContainer.new()
	page.name = tr("ELORIA_SETTINGS_GRAPHICS")
	tabs.add_child(page)
	_add_toggle(page, "shadows", tr("ELORIA_SETTINGS_SHADOWS"), true)
	_add_toggle(page, "particles", tr("ELORIA_SETTINGS_PARTICLES"), true)
	_add_toggle(page, "nameplates", tr("ELORIA_SETTINGS_NAMEPLATES"), true)
	# The combat box can also be dismissed from its own right-click menu, so
	# this is the way back once a player has done that.
	_add_toggle(page, "combat_hud", tr("ELORIA_SETTINGS_COMBAT_HUD"), true)

func _build_camera() -> void:
	var page := VBoxContainer.new()
	page.name = tr("ELORIA_SETTINGS_CAMERA")
	tabs.add_child(page)
	_add_slider(page, "rotation_sensitivity", tr("ELORIA_SETTINGS_ROTATION"), 0.05, 1.0, 0.25)
	_add_slider(page, "pan_sensitivity", tr("ELORIA_SETTINGS_PAN"), 0.004, 0.05, 0.012)
	_add_toggle(page, "follow_player", tr("ELORIA_SETTINGS_FOLLOW"), true)

func _build_gameplay() -> void:
	var page := VBoxContainer.new()
	page.name = tr("ELORIA_SETTINGS_GAMEPLAY")
	tabs.add_child(page)
	var hint := Label.new()
	hint.text = tr("ELORIA_SETTINGS_SERVER_HINT")
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	page.add_child(hint)
	_add_button(page, "target_mode_strong", tr("ELORIA_SETTINGS_TARGET_STRONG"))
	_add_button(page, "target_mode_weak", tr("ELORIA_SETTINGS_TARGET_WEAK"))
	_add_button(page, "autogather", tr("ELORIA_SETTINGS_AUTOGATHER"))

func _build_controls() -> void:
	var page := VBoxContainer.new()
	page.name = tr("ELORIA_SETTINGS_CONTROLS")
	tabs.add_child(page)
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	page.add_child(scroll)
	var list := VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	for group: Variant in BINDABLE:
		var heading := Label.new()
		heading.text = str(group)
		list.add_child(heading)
		for action: Variant in BINDABLE[group]:
			var name: String = str(action)
			var row := HBoxContainer.new()
			row.name = "Bind_" + name
			list.add_child(row)
			var label := Label.new()
			label.text = name.replace("_", " ")
			label.custom_minimum_size = Vector2(220.0, 0.0)
			row.add_child(label)
			var button := Button.new()
			button.name = "Binding"
			button.custom_minimum_size = Vector2(150.0, 0.0)
			button.pressed.connect(begin_capture.bind(name))
			row.add_child(button)
			binding_rows[name] = button

## Pushes a stored value back onto a toggle without re-emitting it, so the
## panel opens showing what the client actually has rather than the default it
## was built with.
func restore_toggle(key: String, value: bool) -> bool:
	var toggle: CheckButton = find_child(key, true, false) as CheckButton
	if toggle == null:
		return false
	toggle.set_pressed_no_signal(value)
	return true

func _add_toggle(page: VBoxContainer, key: String, label: String,
		value: bool) -> void:
	var row := HBoxContainer.new()
	page.add_child(row)
	var toggle := CheckButton.new()
	toggle.name = key
	toggle.text = label
	toggle.button_pressed = value
	toggle.toggled.connect(func(pressed: bool) -> void:
		setting_changed.emit(page.name, key, pressed))
	row.add_child(toggle)

func _add_slider(page: VBoxContainer, key: String, label: String,
		minimum: float, maximum: float, value: float) -> void:
	var row := HBoxContainer.new()
	page.add_child(row)
	var caption := Label.new()
	caption.text = label
	caption.custom_minimum_size = Vector2(200.0, 0.0)
	row.add_child(caption)
	var slider := HSlider.new()
	slider.name = key
	slider.min_value = minimum
	slider.max_value = maximum
	slider.step = (maximum - minimum) / 40.0
	slider.value = value
	slider.custom_minimum_size = Vector2(220.0, 0.0)
	slider.value_changed.connect(func(moved: float) -> void:
		setting_changed.emit(page.name, key, moved))
	row.add_child(slider)

func _add_button(page: VBoxContainer, key: String, label: String) -> void:
	var button := Button.new()
	button.name = key
	button.text = label
	button.pressed.connect(func() -> void:
		setting_changed.emit(page.name, key, true))
	page.add_child(button)
