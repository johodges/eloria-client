extends Control
## The spell book: effect rows and target columns, within the health,
## general, attack and defense groups, with reasons a cast would fail.
##
## Everything on it is a rendering of what the client honestly knows. The
## definitions are the client's own spell catalog; the sigils the player
## owns, their magic level, their mana and their reagents are the server's
## state as it last arrived in `AppState`. A spell the client can see no way
## to cast is dimmed and its first blocking reason is written beside its
## name, the way the legacy client dimmed and annotated its own - but the
## window never decides whether a cast succeeds. Pressing Cast only asks;
## the server answers, because the sigils, the mana and the inventory are
## all its to spend.
##
## The script declares no `class_name`: a global class is parsed before the
## autoload singletons are registered, and this reads `AppState` directly.

const PANEL_SIZE := Vector2(560.0, 600.0)
## Nothing may cover the fixed resource rail down the right-hand edge.
const RESERVED_RIGHT_RAIL := 96.0

## The four Eternal Lands groups, in the order the legacy window draws them.
const GROUP_ORDER: Array[String] = ["Health", "General", "Attack", "Defense"]
## Which group each catalogued effect belongs to. Anything the table does not
## name - Blinkstep and any other spell with no effect at all - is a General
## spell.
const EFFECT_GROUPS := {
	"heal": "Health", "regeneration": "Health", "dispel": "Health",
	"heat_bolt": "Attack", "cold_bolt": "Attack", "radiation_bolt": "Attack",
	"disrupt": "Attack", "cripple": "Attack", "expose_magic": "Attack",
	"expose_heat": "Attack", "expose_cold": "Attack", "expose_radiation": "Attack",
	"poison": "Attack",
	"harm": "Attack",
	"life_drain": "Attack",
	"mana_drain": "Attack",
	"shield": "Defense",
	"magic_protection": "Defense",
	"magic_immunity": "Defense",
	"heat_protection": "Defense",
	"cold_protection": "Defense",
	"radiation_protection": "Defense",
	"element_ward": "Defense",
}

## EL dims what you cannot cast rather than hiding it, so it can still be
## clicked and read.
const BLOCKED_ALPHA := 0.45
const BLOCKED_COLOR := Color(1.0, 0.36, 0.36)
const CASTABLE_COLOR := Color(0.85, 1.0, 0.85)
const ICON_SIZE := Vector2(28.0, 28.0)
const TARGET_COLUMNS: Array[String] = ["self", "target", "allies", "burst", "utility"]
const EFFECT_COLUMN_WIDTH := 164.0
const TARGET_COLUMN_WIDTH := 56.0
const EFFECT_LABELS := {
	"harm": "Magic Damage", "heat_bolt": "Fire Damage", "cold_bolt": "Frost Damage",
	"radiation_bolt": "Radiation Damage", "mana_drain": "Ether Drain",
	"invisibility": "Conceal", "magic_protection": "Magic Ward",
	"heat_protection": "Heat Ward", "cold_protection": "Cold Ward",
	"radiation_protection": "Radiation Ward", "element_ward": "Elemental Ward",
	"expose_magic": "Weaken Magic", "expose_heat": "Weaken Heat",
	"expose_cold": "Weaken Cold", "expose_radiation": "Weaken Radiation",
}

var catalog: SpellCatalog
var selected_spell_id: int = -1

var panel: PanelContainer
var name_label: Label
var description_label: Label
var numbers_label: Label
var sigils_label: Label
var reagents_label: Label
var cast_button: Button

var _cast: Callable = Callable()
## Effect key to its row, and group name to its section.
var _rows: Dictionary = {}
var _groups: Dictionary = {}
var _empty_label: Label
## Spell id to its Button, for re-dimming without a rebuild.
var _buttons: Dictionary = {}
## Spell id to the Array[String] of everything blocking a cast, as the
## catalog last computed it from the server's state. Empty means castable
## as far as the client can see.
var _reasons: Dictionary = {}
var search: LineEdit
var scope_filter: OptionButton
var requested_power := 1
var _quote_request := ""
var _last_quote: Dictionary = {}

func _quote_state(data: Dictionary) -> void:
	if data.get("kind") != "preview" or int(data.get("id", -1)) != selected_spell_id or int(data.get("requested", 0)) != requested_power:
		return
	_last_quote=data.duplicate(true)
	name_label.text = str(catalog.spell(selected_spell_id).get("name", "Spell"))
	name_label.add_theme_color_override("font_color",CASTABLE_COLOR if data.get("ready",false) else BLOCKED_COLOR)
	numbers_label.text = "Power %d / %d allowed · Ether %d" % [int(data.power), int(data.limit), int(data.mana)]
	var parts: Array[String] = []
	for reagent: Dictionary in data.get("reagents", []):
		parts.append("%s %d (have %d)" % [str(reagent.name), int(reagent.quantity), int(reagent.have)])
	reagents_label.text = ", ".join(parts)
	if not str(data.get("focus", "")).is_empty():
		reagents_label.text += "\n%s replaces the anchor with one charge." % str(data.focus)
	if not bool(data.get("ready", false)):
		name_label.text += " — " + str(data.get("reason", "Unavailable"))
	cast_button.disabled = not bool(data.get("ready", false))

func _ready() -> void:
	AppState.magic_state_received.connect(_quote_state)
	name = "SpellsLayer"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()
	AppState.state_changed.connect(_on_state_changed)
	sync()

func configure(spell_catalog: SpellCatalog, cast: Callable) -> void:
	catalog = spell_catalog
	_cast = cast
	_populate()
	sync()

func is_open() -> bool:
	return panel.visible

func toggle() -> void:
	panel.visible = not panel.visible
	if panel.visible:
		panel.move_to_front()
		sync()

func close() -> void:
	panel.hide()

## Which of the four groups a spell is drawn under, from its catalogued
## effect alone.
func group_of(spell_id: int) -> String:
	if catalog == null:
		return "General"
	var effect_value: Variant = catalog.spell(spell_id).get("effect", "")
	var effect: String = effect_value if effect_value is String else ""
	return str(EFFECT_GROUPS.get(effect, "General"))

func _on_state_changed(path: StringName) -> void:
	if path == &"spells" or path == &"stats" or path == &"inventory":
		sync()

## Re-asks the catalog what blocks every spell, dims accordingly and redraws
## the selected details. Everything it reads is the server's last word held
## in AppState; nothing here predicts what the server will actually allow.
func sync() -> void:
	_quote_request = ""
	if not panel.visible or catalog == null:
		return
	_reasons.clear()
	for spell_id: int in catalog.spell_ids():
		var reasons: Array[String] = catalog.unavailable_reasons(
			spell_id, AppState.owned_sigils, AppState.stats, AppState.inventory)
		_reasons[spell_id] = reasons
		var button: Button = _buttons.get(spell_id) as Button
		if button != null:
			button.modulate = Color(1.0, 1.0, 1.0,
				1.0 if reasons.is_empty() else BLOCKED_ALPHA)
	_refresh_details()

func _on_spell_pressed(spell_id: int) -> void:
	selected_spell_id = spell_id
	_refresh_details()

## Only asks. The server owns the sigils, the mana and the reagents, so it
## alone decides whether the cast happens.
func _on_cast_pressed() -> void:
	if selected_spell_id >= 0 and _cast.is_valid():
		_cast.call(selected_spell_id)

func _refresh_details() -> void:
	cast_button.disabled = selected_spell_id < 0
	if selected_spell_id < 0 or catalog == null:
		name_label.text = ""
		description_label.text = ""
		numbers_label.text = ""
		sigils_label.text = ""
		reagents_label.text = ""
		return
	var definition: Dictionary = catalog.spell(selected_spell_id)
	var title: String = str(definition.get("name", "Spell %d" % selected_spell_id))
	var reasons: Array = _reasons.get(selected_spell_id, []) as Array
	if reasons.is_empty():
		name_label.text = title
		name_label.add_theme_color_override("font_color", CASTABLE_COLOR)
	else:
		name_label.text = "%s (%s)" % [title, str(reasons[0])]
		name_label.add_theme_color_override("font_color", BLOCKED_COLOR)
	description_label.text = str(definition.get("description", ""))
	numbers_label.text = "Magic %d   Base ether %d" % [
		int(definition.get("level", 0)), int(definition.get("mana", 0))]
	sigils_label.text = _sigils_line(definition)
	reagents_label.text = _reagents_line(definition)
	if AppState.authenticated:
		var token := "%d:%d" % [selected_spell_id, requested_power]
		if token != _quote_request:
			_quote_request = token
			cast_button.disabled = true
			Network.magic_request({"op":"preview", "id":selected_spell_id, "power":requested_power})
		elif not _last_quote.is_empty():
			_quote_state(_last_quote)

## The required sigils by name, owned ones plain and missing ones marked
## with a leading "!". Ownership is the server's set in AppState.
func _sigils_line(definition: Dictionary) -> String:
	var parts: Array[String] = []
	var sigils_value: Variant = definition.get("sigils", [])
	if sigils_value is Array:
		for raw_sigil: Variant in sigils_value as Array:
			var sigil_id: int = int(raw_sigil)
			var sigil_label: String = catalog.sigil_name(sigil_id)
			if sigil_label.is_empty():
				sigil_label = "sigil %d" % sigil_id
			if not AppState.owned_sigils.has(sigil_id):
				sigil_label = "!" + sigil_label
			parts.append(sigil_label)
	return "Sigils: " + (", ".join(parts) if not parts.is_empty() else "none")

## The required reagents by the name the server gives the item, with a
## leading "!" on any the backpack is short of - the same mark the sigils
## line uses, so both lines answer "what am I missing" the same way. What is
## carried is the server's inventory in AppState.
func _reagents_line(definition: Dictionary) -> String:
	var parts: Array[String] = []
	var reagents_value: Variant = definition.get("reagents", [])
	if reagents_value is Array:
		for raw_reagent: Variant in reagents_value as Array:
			if raw_reagent is Dictionary:
				var reagent: Dictionary = raw_reagent as Dictionary
				var required: int = int(reagent.get("quantity", 0))
				var label: String = "%s x%d" % [
					SpellCatalog.reagent_name(reagent), required]
				if catalog.reagent_quantity(reagent, AppState.inventory) < required:
					label = "!" + label
				parts.append(label)
	return "Reagents: " + (", ".join(parts) if not parts.is_empty() else "none")

## Each effect owns a row. Target cells stay in place even when empty or
## filtered, so comparing variants never changes the meaning of a column.
func _populate() -> void:
	for group: String in GROUP_ORDER:
		var section: VBoxContainer = _groups[group] as VBoxContainer
		for child: Node in section.get_children():
			if child is Label:
				continue
			section.remove_child(child)
			child.free()
	_rows.clear()
	_buttons.clear()
	if catalog == null:
		return
	var grouped: Dictionary = {}
	for group: String in GROUP_ORDER:
		grouped[group] = []
	for spell_id: int in catalog.spell_ids():
		(grouped[group_of(spell_id)] as Array).append(spell_id)
	for group: String in GROUP_ORDER:
		var ids: Array = grouped[group] as Array
		ids.sort_custom(func(a: Variant, b: Variant) -> bool:
			var level_a: int = int(catalog.spell(int(a)).get("level", 0))
			var level_b: int = int(catalog.spell(int(b)).get("level", 0))
			return level_a < level_b if level_a != level_b else int(a) < int(b))
		for raw_id: Variant in ids:
			var spell_id: int = int(raw_id)
			var definition := catalog.spell(spell_id)
			var effect := str(definition.get("effect", ""))
			if effect.is_empty():
				effect = str(definition.get("name", "Spell %d" % spell_id))
			if not _rows.has(effect):
				var row := _make_effect_row(effect)
				(_groups[group] as VBoxContainer).add_child(row)
				_rows[effect] = row
			var scope := str(definition.get("scope", "self"))
			var target := scope if scope in TARGET_COLUMNS else "utility"
			var cell := (_rows[effect] as HBoxContainer).get_node(
				"%sCell" % target.capitalize()) as VBoxContainer
			(cell.get_node("Empty") as Label).hide()
			var button := Button.new()
			button.name = "SpellButton%d" % spell_id
			button.tooltip_text = str(definition.get("name", ""))
			if target == "utility":
				button.tooltip_text += "\nTarget: " + scope.capitalize()
			button.icon = catalog.icon_for(spell_id)
			button.expand_icon = true
			button.custom_minimum_size = ICON_SIZE
			button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
			button.pressed.connect(_on_spell_pressed.bind(spell_id))
			cell.add_child(button)
			_buttons[spell_id] = button
	_filter_spells()

func _make_effect_row(effect: String, heading := false) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.name = "TargetHeadings" if heading else "%sEffectRow" % effect.to_pascal_case()
	var label := Label.new()
	label.name = "EffectLabel"
	label.text = "Effect" if heading else str(EFFECT_LABELS.get(effect, effect.capitalize()))
	label.tooltip_text = label.text
	label.custom_minimum_size.x = EFFECT_COLUMN_WIDTH
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(label)
	for target: String in TARGET_COLUMNS:
		var cell := VBoxContainer.new()
		cell.name = "%sCell" % target.capitalize()
		cell.custom_minimum_size.x = TARGET_COLUMN_WIDTH
		cell.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		cell.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_child(cell)
		var placeholder := Label.new()
		placeholder.name = "Empty"
		placeholder.text = target.capitalize() if heading else "—"
		placeholder.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		if not heading:
			placeholder.modulate.a = BLOCKED_ALPHA
		cell.add_child(placeholder)
	return row

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "SpellsWindow"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	# Left of centre, where the legacy client keeps its own spell window.
	panel.position = Vector2(
		(1280.0 - RESERVED_RIGHT_RAIL - PANEL_SIZE.x) * 0.5 - 110.0, 120.0)
	panel.custom_minimum_size = PANEL_SIZE
	panel.size = PANEL_SIZE
	panel.hide()
	add_child(panel)

	var column := VBoxContainer.new()
	column.name = "SpellsBody"
	panel.add_child(column)
	var header := HBoxContainer.new()
	header.name = "SpellsHeader"
	column.add_child(header)
	WindowDrag.attach(panel, header)
	var title := Label.new()
	title.name = "SpellsTitle"
	title.text = "Spells"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	header.add_child(title)
	var close_button := Button.new()
	close_button.name = "SpellsClose"
	close_button.text = "X"
	close_button.pressed.connect(close)
	header.add_child(close_button)

	search = LineEdit.new()
	search.name = "SpellSearch"
	search.placeholder_text = "Search spells, effects or damage types"
	column.add_child(search)
	scope_filter = OptionButton.new()
	for option: String in ["All targets", "Self", "Target", "Allies", "Burst", "Utility"]:
		scope_filter.add_item(option)
	column.add_child(scope_filter)
	search.text_changed.connect(func(_text: String) -> void: _filter_spells())
	scope_filter.item_selected.connect(func(_index: int) -> void: _filter_spells())
	var headings := MarginContainer.new()
	headings.name = "SpellTargetHeadings"
	column.add_child(headings)
	headings.add_child(_make_effect_row("", true))
	var scroll := ScrollContainer.new()
	scroll.name = "SpellScroll"
	scroll.custom_minimum_size.y = 230
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_ALWAYS
	column.add_child(scroll)
	# Reserve the same scrollbar gutter in the fixed headings as in the rows.
	headings.add_theme_constant_override("margin_right",
		int(scroll.get_v_scroll_bar().get_combined_minimum_size().x))
	var groups := VBoxContainer.new()
	groups.name = "SpellGroups"
	groups.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(groups)
	for group: String in GROUP_ORDER:
		var section := VBoxContainer.new()
		section.name = "%sSpells" % group
		groups.add_child(section)
		var label := Label.new()
		label.name = "%sSpellsLabel" % group
		label.text = "%s Spells" % group
		section.add_child(label)
		_groups[group] = section
	_empty_label = Label.new()
	_empty_label.name = "NoMatchingSpells"
	_empty_label.text = "No spells match your search."
	_empty_label.hide()
	groups.add_child(_empty_label)

	var details := VBoxContainer.new()
	details.name = "SpellDetails"
	column.add_child(details)
	name_label = Label.new()
	name_label.name = "SpellName"
	name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.add_child(name_label)
	description_label = Label.new()
	description_label.name = "SpellDescription"
	description_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.add_child(description_label)
	numbers_label = Label.new()
	numbers_label.name = "SpellNumbers"
	details.add_child(numbers_label)
	sigils_label = Label.new()
	sigils_label.name = "SpellSigils"
	sigils_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.add_child(sigils_label)
	reagents_label = Label.new()
	reagents_label.name = "SpellReagents"
	reagents_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	details.add_child(reagents_label)

	cast_button = Button.new()
	cast_button.name = "CastButton"
	cast_button.text = "Cast"
	cast_button.disabled = true
	cast_button.size_flags_horizontal = Control.SIZE_SHRINK_END
	cast_button.pressed.connect(_on_cast_pressed)
	column.add_child(cast_button)

func _filter_spells() -> void:
	if catalog == null: return
	var selected := "" if scope_filter.selected <= 0 else TARGET_COLUMNS[scope_filter.selected - 1]
	var query := search.text.strip_edges().to_lower()
	for spell_id: int in catalog.spell_ids():
		var spell := catalog.spell(spell_id)
		var scope := str(spell.get("scope", "self"))
		var target := scope if scope in TARGET_COLUMNS else "utility"
		var effect := str(spell.get("effect", ""))
		var scope_matches := selected.is_empty() or target == selected
		var haystack := "%s %s %s %s" % [spell.name, effect, spell.get("damage_type", ""), EFFECT_LABELS.get(effect, effect.capitalize())]
		(_buttons[spell_id] as Button).visible = scope_matches and (query.is_empty() or haystack.to_lower().contains(query))

	var any_matches := false
	for row: HBoxContainer in _rows.values():
		var any_visible := false
		for target: String in TARGET_COLUMNS:
			var cell := row.get_node("%sCell" % target.capitalize()) as VBoxContainer
			var cell_visible := false
			for child: Node in cell.get_children():
				if child is Button:
					cell_visible = cell_visible or (child as Button).visible
			(cell.get_node("Empty") as Label).visible = not cell_visible
			any_visible = any_visible or cell_visible
		row.visible = any_visible
		any_matches = any_matches or any_visible
	for group: String in GROUP_ORDER:
		var section: VBoxContainer = _groups[group]
		var any_visible := false
		for child: Node in section.get_children():
			if child is HBoxContainer:
				any_visible = any_visible or (child as Control).visible
		section.visible = any_visible
	_empty_label.visible = not any_matches
