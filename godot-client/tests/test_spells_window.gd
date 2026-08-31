extends SceneTree
## Guards the Spells window.
##
## The window is a view of two honest sources: the client's own spell
## catalog, and the server's state in AppState - owned sigils, stats,
## inventory. It groups the catalogued spells the way Eternal Lands does,
## dims what the client can see no way to cast, writes the first blocking
## reason beside the name, and its Cast button only asks: the id goes to a
## Callable and the server decides. Everything below checks that the window
## says exactly what those sources say and nothing more.

var failures := 0
var cast_ids: Array[int] = []

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var app_state: Node = root.get_node("/root/AppState")
	var catalog := SpellCatalog.new()
	catalog.configure(_json("res://data/spells/catalog.json"))
	_expect(catalog.spell_ids().size() == 22,
		"the real catalog carries 22 spells: %d" % catalog.spell_ids().size())
	var window: Control = (load("res://src/ui/spells_window.gd")
		as GDScript).new() as Control
	root.add_child(window)
	await process_frame
	window.call("configure", catalog,
		func(spell_id: int) -> void: cast_ids.append(spell_id))
	var panel: PanelContainer = window.get_node("SpellsWindow") as PanelContainer

	_expect(not panel.visible, "the spells window starts closed")
	window.call("toggle")
	await process_frame
	_expect(panel.visible and bool(window.call("is_open")), "toggle opens it")
	var rect: Rect2 = panel.get_global_rect()
	_expect(rect.position.x >= 0.0 and rect.position.y >= 0.0
		and rect.end.x <= 1280.0 - float(window.get("RESERVED_RIGHT_RAIL"))
		and rect.end.y <= 720.0,
		"it fits 1280x720 clear of the resource rail: %s" % rect)

	# All 22 spells appear, each exactly once, across the four groups.
	var body := "SpellsWindow/SpellsBody/"
	var listed: Array[int] = []
	for group: String in ["Health", "General", "Attack", "Defense"]:
		var row: HFlowContainer = window.get_node(
			body + "%sSpellsRow" % group) as HFlowContainer
		for child: Node in row.get_children():
			listed.append(int(str(child.name).trim_prefix("SpellButton")))
	_expect(listed.size() == 22,
		"all 22 spells are on the window: %d" % listed.size())
	for spell_id: int in catalog.spell_ids():
		_expect(listed.has(spell_id), "spell %d is listed" % spell_id)

	# The documented grouping, spot-checked by effect.
	_expect(str(window.call("group_of", 0)) == "Health",
		"Heal is a health spell")
	_expect(str(window.call("group_of", 6)) == "Attack",
		"Harm is an attack spell")
	_expect(str(window.call("group_of", 3)) == "Defense",
		"Shield is a defense spell")
	_expect(str(window.call("group_of", 15)) == "General",
		"Invisibility, an effect no group names, is a general spell")
	var heal_button: Button = window.get_node(
		body + "HealthSpellsRow/SpellButton0") as Button
	_expect(heal_button != null, "Heal's button sits in the health row")
	_expect(heal_button.tooltip_text == "Heal",
		"a spell button says which spell it is: " + heal_button.tooltip_text)
	_expect(heal_button.icon is Texture2D,
		"and carries its sigil-atlas icon")
	# Within a group the spells stand in order of the level each asks for.
	var health_names: Array[String] = []
	for child: Node in window.get_node(body + "HealthSpellsRow").get_children():
		health_names.append(str(child.name))
	_expect(health_names == ["SpellButton0", "SpellButton1", "SpellButton7",
			"SpellButton12", "SpellButton21"],
		"health spells are ordered by required level: %s" % str(health_names))

	# With nothing owned, nothing is castable: dimmed, not hidden, and still
	# there to inspect.
	(app_state.get("owned_sigils") as Array).clear()
	(app_state.get("stats") as Dictionary).clear()
	(app_state.get("inventory") as Dictionary).clear()
	window.call("sync")
	var blocked_alpha: float = float(window.get("BLOCKED_ALPHA"))
	_expect(is_equal_approx(heal_button.modulate.a, blocked_alpha),
		"an uncastable spell is dimmed: %f" % heal_button.modulate.a)
	var cast: Button = window.get_node(body + "CastButton") as Button
	_expect(cast.disabled, "Cast is disabled while nothing is selected")
	_expect(int(window.get("selected_spell_id")) == -1,
		"and no spell starts selected")
	var invisibility: Button = window.get_node(
		body + "GeneralSpellsRow/SpellButton15") as Button
	invisibility.pressed.emit()
	await process_frame
	_expect(int(window.get("selected_spell_id")) == 15,
		"clicking a spell selects it")
	var name_label: Label = window.get_node(
		body + "SpellDetails/SpellName") as Label
	_expect(name_label.text == "Invisibility (Missing sigils: 22, 15, 20)",
		"the blocked name carries the first blocking reason: " + name_label.text)
	_expect(name_label.get_theme_color("font_color")
			== (window.get("BLOCKED_COLOR") as Color),
		"and is drawn red")
	var sigils_label: Label = window.get_node(
		body + "SpellDetails/SpellSigils") as Label
	_expect(sigils_label.text.begins_with("Sigils: !"),
		"missing sigils are marked with !: " + sigils_label.text)
	_expect(not cast.disabled, "selecting a spell enables Cast")
	cast.pressed.emit()
	_expect(cast_ids == [15],
		"Cast asks with the selected id: %s" % str(cast_ids))

	# The server grants what Heal needs; the window follows AppState.
	var owned: Array = app_state.get("owned_sigils") as Array
	owned.append(3)
	owned.append(23)
	var stats: Dictionary = app_state.get("stats") as Dictionary
	stats["magic"] = 5
	stats["ether"] = 50
	var inventory: Dictionary = app_state.get("inventory") as Dictionary
	inventory[0] = {"image_id": 59, "quantity": 10}
	app_state.emit_signal("state_changed", &"stats")
	await process_frame
	_expect(is_equal_approx(heal_button.modulate.a, 1.0),
		"a castable spell is drawn at full strength: %f" % heal_button.modulate.a)
	heal_button.pressed.emit()
	await process_frame
	_expect(name_label.text == "Heal",
		"a castable name carries no reason: " + name_label.text)
	_expect(name_label.get_theme_color("font_color")
			== (window.get("CASTABLE_COLOR") as Color),
		"and is drawn green-white")
	var description: Label = window.get_node(
		body + "SpellDetails/SpellDescription") as Label
	_expect(not description.text.strip_edges().is_empty(),
		"the description line is filled")
	var numbers: Label = window.get_node(
		body + "SpellDetails/SpellNumbers") as Label
	_expect(numbers.text == "Level 0   Mana 5",
		"the level and mana are stated: " + numbers.text)
	_expect(sigils_label.text.begins_with("Sigils: ")
			and not sigils_label.text.contains("!"),
		"owned sigils are named plainly: " + sigils_label.text)
	var reagents: Label = window.get_node(
		body + "SpellDetails/SpellReagents") as Label
	_expect(reagents.text == "Reagents: #59 x1",
		"reagents are listed by image and count: " + reagents.text)
	cast.pressed.emit()
	_expect(cast_ids == [15, 0],
		"Cast asks with the new selection: %s" % str(cast_ids))

	window.call("close")
	_expect(not panel.visible and not bool(window.call("is_open")),
		"close hides it")

	# Leave AppState as this suite found it.
	owned.clear()
	stats.clear()
	inventory.clear()

	print("spells window tests: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	window.queue_free()
	await process_frame
	quit(failures)

func _json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}

func _expect(value: bool, label: String) -> bool:
	if not value:
		failures += 1
		push_error("FAIL: " + label)
	return value
