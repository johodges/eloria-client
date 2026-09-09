extends Control
signal cast_slot(index: int)
signal edit_slot(index: int)
signal open_book
const SpellButton := preload("res://src/ui/prepared_spell_button.gd")
const SCOPE_BADGES := {"self": "Self", "target": "Target", "allies": "Allies", "burst": "Burst", "location": "Ground", "inventory": "Item", "destination": "Recall"}
var loadout
var panel: PanelContainer
var mode_picker: OptionButton
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
	mode_picker.item_selected.connect(func(index: int): loadout.set_mode("aimed" if index == 1 else "prepared"))
	header.add_child(mode_picker)
	var book := Button.new()
	book.text = "Spellbook"
	book.pressed.connect(func(): open_book.emit())
	header.add_child(book)
	WindowDrag.attach(panel, header)
	var row := GridContainer.new()
	row.columns = 6
	body.add_child(row)
	for index in range(12):
		var cell := VBoxContainer.new()
		cell.custom_minimum_size.x = 52
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(cell)
		var button := SpellButton.new()
		button.name = "PreparedSpell%d" % index
		button.accepts_spells = true
		button.expand_icon = true
		button.custom_minimum_size = Vector2(44, 36)
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(func(): cast_slot.emit(index))
		button.spell_dropped.connect(func(id: int, power: int): loadout.assign_slot(index, id, power))
		button.gui_input.connect(_slot_input.bind(index))
		cell.add_child(button)
		var key := Label.new()
		key.name = "Key"
		key.text = str(index + 1) if index < 9 else ["0", "-", "="][index - 9]
		key.position = Vector2(2, 0)
		key.mouse_filter = Control.MOUSE_FILTER_IGNORE
		key.add_theme_font_size_override("font_size", 10)
		key.add_theme_constant_override("outline_size", 3)
		button.add_child(key)
		var badge := Label.new()
		badge.name = "Badge"
		badge.add_theme_font_size_override("font_size", 11)
		badge.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cell.add_child(badge)
		buttons.append(button)
	menu = PopupMenu.new()
	menu.add_item("Edit spell / power", 0)
	menu.add_item("Clear slot", 1)
	menu.id_pressed.connect(func(id: int):
		if id == 0: edit_slot.emit(_menu_slot)
		else: loadout.assign_slot(_menu_slot, -1, 1))
	add_child(menu)
	loadout.changed.connect(refresh)
	refresh()

func refresh() -> void:
	if mode_picker == null: return
	mode_picker.select(1 if loadout.mode == "aimed" else 0)
	for index in range(buttons.size()):
		var slot: Dictionary = loadout.slots[index]
		var button = buttons[index]
		button.spell_id = int(slot.id)
		button.power = int(slot.power)
		var definition: Dictionary = loadout.catalog.spell(int(slot.id))
		button.icon = loadout.catalog.icon_for(int(slot.id)) if int(slot.id) >= 0 else null
		button.text = "+" if int(slot.id) < 0 else ""
		var badge := button.get_parent().get_node("Badge") as Label
		var scope := str(SCOPE_BADGES.get(definition.get("scope", ""), ""))
		var limit: Dictionary = AppState.spell_power.get(loadout.catalog.effect_for(int(slot.id)), {})
		var effective_power := mini(int(slot.power), maxi(1, int(limit.get("limit", 1))))
		badge.text = "%s P%d" % [scope, effective_power] if int(slot.id) >= 0 else "Empty"
		var keys: Array[InputEvent] = InputMap.action_get_events("quick_spell_%d" % (index + 1))
		var shortcut := keys[0].as_text() if not keys.is_empty() else "Unbound"
		button.tooltip_text = "%s · P%d\n%s\nRight click to edit; drag a spell here." % [definition.get("name", "Empty slot"), int(slot.power), shortcut]
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
