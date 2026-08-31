extends Control
## The spell book: every catalogued spell, grouped the way Eternal Lands
## groups its own - health, general, attack, defense - with the reasons a
## cast would fail written where the player can read them.
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

const PANEL_SIZE := Vector2(470.0, 460.0)
## Nothing may cover the fixed resource rail down the right-hand edge.
const RESERVED_RIGHT_RAIL := 96.0

## The four Eternal Lands groups, in the order the legacy window draws them.
const GROUP_ORDER: Array[String] = ["Health", "General", "Attack", "Defense"]
## Which group each catalogued effect belongs to. Anything the table does not
## name - the teleports, Bones to Gold, True Sight, Invisibility, spells with
## no effect at all - is a General spell.
const EFFECT_GROUPS := {
	"heal": "Health",
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
}

## EL dims what you cannot cast rather than hiding it, so it can still be
## clicked and read.
const BLOCKED_ALPHA := 0.45
const BLOCKED_COLOR := Color(1.0, 0.36, 0.36)
const CASTABLE_COLOR := Color(0.85, 1.0, 0.85)
const ICON_SIZE := Vector2(28.0, 28.0)

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
## Group name to its HFlowContainer of spell buttons.
var _rows: Dictionary = {}
## Spell id to its Button, for re-dimming without a rebuild.
var _buttons: Dictionary = {}
## Spell id to the Array[String] of everything blocking a cast, as the
## catalog last computed it from the server's state. Empty means castable
## as far as the client can see.
var _reasons: Dictionary = {}

func _ready() -> void:
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
	numbers_label.text = "Level %d   Mana %d" % [
		int(definition.get("level", 0)), int(definition.get("mana", 0))]
	sigils_label.text = _sigils_line(definition)
	reagents_label.text = _reagents_line(definition)

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

func _reagents_line(definition: Dictionary) -> String:
	var parts: Array[String] = []
	var reagents_value: Variant = definition.get("reagents", [])
	if reagents_value is Array:
		for raw_reagent: Variant in reagents_value as Array:
			if raw_reagent is Dictionary:
				var reagent: Dictionary = raw_reagent as Dictionary
				parts.append("#%d x%d" % [
					int(reagent.get("image_id", -1)), int(reagent.get("quantity", 0))])
	return "Reagents: " + (", ".join(parts) if not parts.is_empty() else "none")

## Fills the four group rows from the catalog: one icon button per spell,
## grouped by effect and ordered by the level the spell asks for.
func _populate() -> void:
	for group: String in GROUP_ORDER:
		var row: HFlowContainer = _rows[group] as HFlowContainer
		for child: Node in row.get_children():
			row.remove_child(child)
			child.free()
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
			var button := Button.new()
			button.name = "SpellButton%d" % spell_id
			button.tooltip_text = str(catalog.spell(spell_id).get("name", ""))
			button.icon = catalog.icon_for(spell_id)
			button.expand_icon = true
			button.custom_minimum_size = ICON_SIZE
			button.pressed.connect(_on_spell_pressed.bind(spell_id))
			(_rows[group] as HFlowContainer).add_child(button)
			_buttons[spell_id] = button

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

	for group: String in GROUP_ORDER:
		var label := Label.new()
		label.name = "%sSpellsLabel" % group
		label.text = "%s Spells" % group
		column.add_child(label)
		var row := HFlowContainer.new()
		row.name = "%sSpellsRow" % group
		column.add_child(row)
		_rows[group] = row

	var details := VBoxContainer.new()
	details.name = "SpellDetails"
	details.size_flags_vertical = Control.SIZE_EXPAND_FILL
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
