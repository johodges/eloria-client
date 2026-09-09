extends Control
signal cast_slot(index: int)
signal edit_slot(index: int)
signal open_book
signal open_wheel
const SpellButton := preload("res://src/ui/prepared_spell_button.gd")
const SCOPE_BADGES := {"self": "Self", "target": "Target", "allies": "Allies", "burst": "Burst", "location": "Ground", "inventory": "Item", "destination": "Recall"}
const CORNER_BADGES := {"self": "Self", "target": "Tgt", "allies": "All", "burst": "Burst", "location": "Gnd", "inventory": "Item", "destination": "Recall"}
var loadout
var panel: PanelContainer
var mode_picker: OptionButton
var wheel_button: Button
var ring_size_picker: OptionButton
var start_expanded := true
var launcher_bottom_margin := 8.0
var launcher: Button
var close_button: Button
var reserved_right_width := 8.0
var buttons: Array[Button] = []
var menu: PopupMenu
var _menu_slot := -1

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel = PanelContainer.new()
	panel.name = "PreparedCastingBar"
	panel.position = Vector2(680, 470)
	add_child(panel)
	launcher = Button.new()
	launcher.name = "QuickbarLauncher"
	launcher.text = "Quickbar"
	launcher.focus_mode = Control.FOCUS_NONE
	launcher.tooltip_text = "Show spell shortcuts and ring settings. Alt + number works while this panel is closed."
	launcher.pressed.connect(func(): set_expanded(true))
	add_child(launcher)
	var body := VBoxContainer.new()
	panel.add_child(body)
	var header := HBoxContainer.new()
	body.add_child(header)
	var label := Label.new()
	label.text = "Spells"
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(label)
	mode_picker = OptionButton.new()
	mode_picker.add_item("Prepared · selected target")
	mode_picker.add_item("Aimed · click target")
	mode_picker.add_item("Ring · Left Shift")
	mode_picker.item_selected.connect(func(index: int): loadout.set_mode(["prepared", "aimed", "wheel"][index]))
	header.add_child(mode_picker)
	wheel_button = Button.new()
	wheel_button.text = "Ring"
	wheel_button.tooltip_text = "Hold Left Shift to browse spells. Right click changes target; scroll changes power. Alt + number uses the quickbar."
	wheel_button.pressed.connect(func(): open_wheel.emit())
	header.add_child(wheel_button)
	ring_size_picker = OptionButton.new()
	ring_size_picker.name = "RingSize"
	ring_size_picker.focus_mode = Control.FOCUS_NONE
	ring_size_picker.tooltip_text = "Magic ring size, saved per character. Large rings automatically fit the window."
	for percent in [75, 90, 100, 110, 125]:
		ring_size_picker.add_item("Size %d%%" % percent, percent)
	ring_size_picker.item_selected.connect(func(index: int): loadout.set_ring_size(ring_size_picker.get_item_id(index)))
	header.add_child(ring_size_picker)
	var book := Button.new()
	book.text = "Spellbook"
	book.pressed.connect(func(): open_book.emit())
	header.add_child(book)
	close_button = Button.new()
	close_button.text = "X"
	close_button.focus_mode = Control.FOCUS_NONE
	close_button.tooltip_text = "Close the quickbar. Left Shift and Alt shortcuts stay available."
	close_button.pressed.connect(func(): set_expanded(false))
	header.add_child(close_button)
	WindowDrag.attach(panel, header)
	var row := GridContainer.new()
	row.columns = 6
	body.add_child(row)
	for index in range(12):
		var cell := VBoxContainer.new()
		cell.custom_minimum_size.x = 64
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(cell)
		var button := SpellButton.new()
		button.name = "PreparedSpell%d" % index
		button.accepts_spells = true
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.custom_minimum_size = Vector2(64, 48)
		button.add_theme_constant_override("icon_max_width", 26)
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(func(): cast_slot.emit(index))
		button.spell_dropped.connect(func(id: int, power: int): loadout.assign_slot(index, id, power))
		button.gui_input.connect(_slot_input.bind(index))
		cell.add_child(button)
		var key := Label.new()
		key.name = "Key"
		key.text = str(index + 1) if index < 9 else ["0", "-", "="][index - 9]
		key.mouse_filter = Control.MOUSE_FILTER_IGNORE
		key.add_theme_font_size_override("font_size", 10)
		key.add_theme_constant_override("outline_size", 3)
		key.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(key)
		for corner in ["Target", "Power"]:
			var badge := Label.new()
			badge.name = corner
			badge.add_theme_font_size_override("font_size", 11)
			badge.add_theme_constant_override("outline_size", 4)
			badge.add_theme_color_override("font_outline_color", Color(0.035, 0.03, 0.02))
			badge.mouse_filter = Control.MOUSE_FILTER_IGNORE
			button.add_child(badge)
			badge.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
			badge.offset_left = 3
			badge.offset_right = -3
			badge.offset_top = 1
			badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT if corner == "Power" else HORIZONTAL_ALIGNMENT_LEFT
		buttons.append(button)
	menu = PopupMenu.new()
	menu.add_item("Edit spell / power", 0)
	menu.add_item("Clear slot", 1)
	menu.id_pressed.connect(func(id: int):
		if id == 0: edit_slot.emit(_menu_slot)
		else: loadout.assign_slot(_menu_slot, -1, 1))
	add_child(menu)
	loadout.changed.connect(refresh)
	AppState.magic_state_received.connect(func(_data: Dictionary): refresh())
	refresh()
	set_expanded(start_expanded)

func set_expanded(expanded: bool) -> void:
	panel.visible = expanded
	launcher.visible = not expanded
	_place_launcher()
	if not expanded:
		menu.hide()
		mode_picker.get_popup().hide()
		ring_size_picker.get_popup().hide()

func _place_launcher() -> void:
	launcher.position = Vector2(8, maxf(8, size.y - launcher.size.y - launcher_bottom_margin))

func refresh() -> void:
	if mode_picker == null: return
	mode_picker.select(["prepared", "aimed", "wheel"].find(loadout.mode))
	wheel_button.visible = loadout.mode == "wheel"
	ring_size_picker.visible = loadout.mode == "wheel"
	ring_size_picker.select(ring_size_picker.get_item_index(loadout.ring_size))
	ring_size_picker.text = "Size %d%%" % loadout.ring_size
	for index in range(buttons.size()):
		var slot: Dictionary = loadout.slots[index]
		var button = buttons[index]
		button.spell_id = int(slot.id)
		button.power = int(slot.power)
		var definition: Dictionary = loadout.catalog.spell(int(slot.id))
		button.icon = loadout.catalog.icon_for(int(slot.id)) if int(slot.id) >= 0 else null
		button.text = "+" if int(slot.id) < 0 else ""
		var scope := str(definition.get("scope", ""))
		var limit: Dictionary = AppState.spell_power.get(loadout.catalog.effect_for(int(slot.id)), {})
		var effective_power := mini(int(slot.power), maxi(1, int(limit.get("limit", 1))))
		button.get_node("Target").text = str(CORNER_BADGES.get(scope, ""))
		button.get_node("Power").text = "P%d" % int(slot.power) if int(slot.id) >= 0 else ""
		var keys: Array[InputEvent] = InputMap.action_get_events("quick_spell_%d" % (index + 1))
		var shortcut := keys[0].as_text() if not keys.is_empty() else "Unbound"
		button.tooltip_text = "%s · %s · P%d\n%s\nUses the last cast target type and power for this family.\nRight click to edit; drag a spell here." % [definition.get("name", "Empty slot"), SCOPE_BADGES.get(scope, ""), int(slot.power), shortcut]
		if effective_power != int(slot.power): button.tooltip_text += "\nSaved P%d; currently limited to P%d." % [int(slot.power), effective_power]
		var reasons: Array[String] = loadout.catalog.unavailable_reasons(int(slot.id), AppState.owned_sigils, AppState.stats, AppState.inventory) if int(slot.id) >= 0 else []
		button.modulate.a = 1.0 if reasons.is_empty() else 0.55
		if not reasons.is_empty(): button.tooltip_text += "\n" + reasons[0]

func _slot_input(event: InputEvent, index: int) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_RIGHT:
		_menu_slot = index
		menu.position = Vector2i(get_global_mouse_position())
		menu.popup()
		buttons[index].accept_event()

func _process(_delta: float) -> void:
	# Keep the extra ring setting and the draggable bar reachable after a resize.
	panel.position = panel.position.clamp(Vector2(8,8), (size-panel.size-Vector2(reserved_right_width,8)).max(Vector2(8,8)))
	_place_launcher()
