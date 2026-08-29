extends Control
## The sigils the player owns, and what each one unlocks.
##
## The server sends the whole 64-bit ownership set at login and again whenever
## it changes, and the client reduced it into `AppState.owned_sigils` and
## rendered none of it - so a player could see "you do not have these sigils"
## on a failed cast with no way to find out which ones they were missing.
##
## Ownership is entirely the server's. The names are the client's spell
## catalog, the same place the spell names and buff labels live, and the
## per-spell readout is computed from the catalog's own sigil lists.
##
## The script declares no `class_name`: a global class is parsed before the
## autoload singletons are registered, and this reads `AppState` directly.

const PANEL_SIZE := Vector2(420.0, 360.0)
## Nothing may cover the fixed resource rail down the right-hand edge.
const RESERVED_RIGHT_RAIL := 96.0

var catalog: SpellCatalog
var panel: PanelContainer
var owned_list: ItemList
var summary: RichTextLabel

func _ready() -> void:
	name = "SigilLayer"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()
	AppState.state_changed.connect(_on_state_changed)
	sync()

func configure(spell_catalog: SpellCatalog) -> void:
	catalog = spell_catalog
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

func _on_state_changed(path: StringName) -> void:
	if path == &"spells" or path == &"connection":
		sync()

func sync() -> void:
	if not panel.visible:
		return
	owned_list.clear()
	var owned: Array = AppState.owned_sigils
	var total: int = catalog.sigil_count() if catalog != null else 0
	for sigil_id: int in range(total):
		var name_text: String = (catalog.sigil_name(sigil_id)
			if catalog != null else "")
		if name_text.is_empty():
			continue
		var carried: bool = owned.has(sigil_id)
		var index: int = owned_list.item_count
		owned_list.add_item("%s  %s" % ["*" if carried else "-", name_text])
		owned_list.set_item_metadata(index, sigil_id)
		owned_list.set_item_disabled(index, not carried)
	summary.text = _summary_text(owned, total)

## Which catalogued spells the owned set can and cannot reach. Every number
## here comes from the server's own ownership set and the catalog's sigil
## lists; nothing decides whether a cast will succeed, which is the server's.
func _summary_text(owned: Array, total: int) -> String:
	if catalog == null:
		return ""
	var castable: Array[String] = []
	var blocked: Array[String] = []
	for spell_id: int in catalog.spell_ids():
		var definition: Dictionary = catalog.spell(spell_id)
		var required: Variant = definition.get("sigils", [])
		if required is not Array:
			continue
		var missing: Array[String] = []
		for raw_sigil: Variant in required as Array:
			if not owned.has(int(raw_sigil)):
				var missing_name: String = catalog.sigil_name(int(raw_sigil))
				missing.append(missing_name if not missing_name.is_empty()
					else "sigil %d" % int(raw_sigil))
		var title: String = str(definition.get("name", "Spell %d" % spell_id))
		if missing.is_empty():
			castable.append(title)
		else:
			blocked.append("%s (needs %s)" % [title, ", ".join(missing)])
	var lines: Array[String] = ["[b]%d of %d sigils[/b]" % [owned.size(), total]]
	lines.append("[color=#8fdc8f]Sigils for: %s[/color]"
		% (", ".join(castable) if not castable.is_empty() else "nothing yet"))
	if not blocked.is_empty():
		lines.append("Still needed:")
		for entry: String in blocked:
			lines.append("  " + entry)
	return "\n".join(lines)

func _build() -> void:
	panel = PanelContainer.new()
	panel.name = "SigilWindow"
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.position = Vector2(
		(1280.0 - RESERVED_RIGHT_RAIL - PANEL_SIZE.x) * 0.5, 120.0)
	panel.custom_minimum_size = PANEL_SIZE
	panel.size = PANEL_SIZE
	panel.hide()
	add_child(panel)

	var column := VBoxContainer.new()
	column.name = "SigilBody"
	panel.add_child(column)
	var header := HBoxContainer.new()
	column.add_child(header)
	var title := Label.new()
	title.name = "SigilTitle"
	title.text = "Sigils"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title)
	var close_button := Button.new()
	close_button.name = "SigilClose"
	close_button.text = "Close"
	close_button.pressed.connect(close)
	header.add_child(close_button)

	var columns := HSplitContainer.new()
	columns.name = "SigilColumns"
	columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(columns)
	owned_list = ItemList.new()
	owned_list.name = "SigilList"
	owned_list.custom_minimum_size = Vector2(170.0, 0.0)
	columns.add_child(owned_list)
	summary = RichTextLabel.new()
	summary.name = "SigilSummary"
	summary.bbcode_enabled = true
	columns.add_child(summary)
