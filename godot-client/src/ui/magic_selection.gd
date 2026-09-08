extends Control
## Server-authored inventory quotes and portal entrances for utility spells.
signal status_changed(message: String)
var catalog: SpellCatalog
var pending: Dictionary = {}
var popup: AcceptDialog
var choices: OptionButton
var quantity: SpinBox
var description: Label
var entries: Array = []
var kind := ""

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	popup = AcceptDialog.new()
	popup.title = "Spell selection"
	popup.min_size = Vector2i(520, 220)
	popup.get_ok_button().text = "Cast"
	popup.add_cancel_button("Cancel")
	add_child(popup)
	var body := VBoxContainer.new()
	popup.add_child(body)
	choices = OptionButton.new()
	choices.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(choices)
	quantity = SpinBox.new()
	quantity.min_value = 1
	quantity.max_value = 1
	quantity.step = 1
	quantity.prefix = "Quantity: "
	body.add_child(quantity)
	description = Label.new()
	description.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	description.custom_minimum_size = Vector2(480, 100)
	body.add_child(description)
	choices.item_selected.connect(func(_index: int) -> void: _update_quote())
	quantity.value_changed.connect(func(_value: float) -> void: _update_quote())
	popup.confirmed.connect(_confirm)
	popup.canceled.connect(cancel)
	AppState.magic_state_received.connect(_receive)
	AppState.state_changed.connect(func(path: StringName) -> void:
		if path == &"map": cancel())
	Network.magic_selection_completed.connect(func() -> void: AppState.pending_spell_target = "")
	Network.connection_state_changed.connect(func(state: String) -> void:
		if state == "disconnected": cancel())

func begin(spell_id: int, power: int) -> void:
	cancel()
	var spell: Dictionary = catalog.spell(spell_id)
	pending = {"op": "cast", "id": spell_id, "power": maxi(1, power)}
	var scope := str(spell.get("scope", "self"))
	if scope == "inventory" or (spell.get("effect") == "recall" and power >= 5):
		Network.magic_request({"op": "options", "id": spell_id})
	elif scope in ["target", "burst", "location"]:
		Network.magic_pending = pending.duplicate()
		Network.magic_scope = scope
		AppState.pending_spell_target = "actor" if scope == "target" else "location"
		status_changed.emit("Select %s for %s. Escape cancels." % [
			"an actor" if scope == "target" else "a location", spell.name])
		AppState.actor_animation_requested.emit({"actor_id": AppState.local_actor_id,
			"action": &"cast_channel_enter", "power": power})
	else:
		Network.magic_request(pending)
		pending.clear()

func cancel() -> void:
	pending.clear()
	Network.magic_pending.clear()
	AppState.pending_spell_target = ""
	if popup != null: popup.hide()

func _unhandled_key_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and (not pending.is_empty() or not Network.magic_pending.is_empty()):
		cancel()
		AppState.actor_animation_requested.emit({"actor_id": AppState.local_actor_id, "action": &"cast_exit"})
		get_viewport().set_input_as_handled()

func _receive(data: Dictionary) -> void:
	if data.get("kind") == "error":
		status_changed.emit(str(data.get("message", "Spell rejected")))
		return
	if pending.is_empty() or int(data.get("id", -1)) != int(pending.id): return
	kind = str(data.get("kind", ""))
	if kind not in ["transmute", "recall"]: return
	entries = data.get("entries", [])
	choices.clear()
	for entry: Dictionary in entries:
		choices.add_item("%s — %s" % [entry.name, entry.rarity] if kind == "transmute"
			else "%s — entrance (%d, %d)" % [entry.name, entry.x, entry.y])
	quantity.visible = kind == "transmute"
	popup.title = "Transmute items to gold" if kind == "transmute" else "Recall destination"
	_update_quote()
	popup.popup_centered()

func _update_quote() -> void:
	popup.get_ok_button().disabled = entries.is_empty()
	if entries.is_empty():
		description.text = "No eligible items or portal entrances available."
		return
	var entry: Dictionary = entries[maxi(0, choices.selected)]
	if kind == "transmute":
		quantity.max_value = int(entry.available)
		var required := int(entry.required_power)
		popup.get_ok_button().disabled = int(pending.get("power", 1)) < required
		description.text = "%s requires Power %d. Selected power: %d.\nConsume %d %s → %d Gold Coins." % [
			entry.rarity, required, int(pending.get("power", 1)), int(quantity.value),
			entry.name, int(quantity.value) * int(entry.unit_gold)]
	else:
		description.text = "Recall to the portal entrance of %s at (%d, %d).\nPower %d; your items travel with you." % [
			entry.name, entry.x, entry.y, int(pending.get("power", 1))]

func _confirm() -> void:
	if entries.is_empty() or pending.is_empty(): return
	var entry: Dictionary = entries[maxi(0, choices.selected)]
	if kind == "transmute":
		pending.merge({"slot": int(entry.slot), "item_id": int(entry.item_id), "instance_id": int(entry.get("instance_id", 0)), "quantity": int(quantity.value)}, true)
	else:
		pending["entry"] = str(entry.key)
	Network.magic_request(pending)
	pending.clear()
