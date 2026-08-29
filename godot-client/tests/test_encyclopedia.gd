extends SceneTree
## Guards the encyclopedia and the move icon's attack preview.
##
## The encyclopedia is half written and half built. The written half is checked
## for being reachable; the built half is checked against the catalogue it was
## built from, so a page can never quietly claim a level, a cost or a material
## the recipe table does not state.
##
## The move icon is checked for the one rule that is easy to get wrong: Alt is
## a preview and not a mode, so it must never disturb an attack mode the player
## chose from the HUD.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("GameView") as Control).show()
	(main.get_node("LoginPanel") as Control).hide()
	await process_frame
	var window: Control = main.get("reference_window") as Control
	var panel: PanelContainer = window.get_node("ReferenceWindow") as PanelContainer
	var view: EncyclopediaView = window.get("encyclopedia") as EncyclopediaView
	var body: RichTextLabel = view.get_node("EntryBody") as RichTextLabel
	var buttons: String = "GameView/Quickbar/QuickRows/Buttons/"
	var icon: Button = main.get_node(buttons + "EncyclopediaButton") as Button
	var walk: Button = main.get_node(buttons + "WalkButton") as Button
	var attack: Button = main.get_node(buttons + "AttackButton") as Button

	# The icon on the lower HUD, and Ctrl+E, both open it on its own page.
	_expect(not panel.visible, "the window starts closed")
	icon.pressed.emit()
	await process_frame
	_expect(panel.visible, "the HUD icon opens the window")
	_expect(bool(window.call("is_encyclopedia_open")),
		"and opens it on the encyclopedia rather than whichever tab was last used")
	_expect(icon.button_pressed, "so the icon is lit while it is showing")
	icon.pressed.emit()
	await process_frame
	_expect(not panel.visible, "and the icon closes it again")
	main.call("_input", _key(KEY_E, true))
	await process_frame
	_expect(bool(window.call("is_encyclopedia_open")), "Ctrl+E opens it")
	# Turning right is a bare E. It must not open the encyclopedia as well.
	main.call("_input", _key(KEY_E, true))
	await process_frame
	_expect(not panel.visible, "and Ctrl+E closes it")
	main.call("_input", _key(KEY_E, false))
	await process_frame
	_expect(not panel.visible,
		"a bare E turns the player and leaves the encyclopedia alone")
	main.call("_input", _key(KEY_E, true))
	await process_frame

	# The index: every category, each one a link.
	_expect(view.category_count() >= 12,
		"the index carries its categories: %d" % view.category_count())
	_expect(body.text.contains("[url=cat:alchemy:0]")
		and body.text.contains("[url=cat:books:0]"),
		"and every one of them is a link off the index page")
	_expect(body.get_parsed_text().contains("The Eloria Encyclopedia"),
		"the index is titled")

	# The built half says what the recipe table says, and nothing else.
	var catalogue: ManufacturingCatalog = main.get(
		"manufacturing_catalog") as ManufacturingCatalog
	_expect(catalogue.count() > 0, "the client has a recipe table to build from")
	var checked := 0
	for index: int in range(catalogue.count()):
		var recipe: Dictionary = catalogue.recipe(index)
		if str(recipe.get("skill", "")) != "alchemy":
			continue
		view.open_entry("alchemy", _slug(str(recipe.get("output", ""))))
		var page: String = body.get_parsed_text()
		var stated: bool = page.contains("Recommended Alchemy level: %d"
				% int(recipe.get("level", 0))) \
			and page.contains("Alchemy experience given: %d"
				% int(recipe.get("experience", 0))) \
			and page.contains("Food subtracted: %d" % int(recipe.get("food", 0)))
		if not _expect(stated, "%s states the recipe's own numbers"
				% str(recipe.get("output", ""))):
			break
		var ingredients: Variant = recipe.get("ingredients", [])
		if ingredients is Array:
			for raw: Variant in ingredients as Array:
				stated = stated and page.contains(str((raw as Dictionary).get("name", "")))
			_expect(stated, "%s names every material the recipe lists"
				% str(recipe.get("output", "")))
		_expect(page.contains("Back To Alchemy Index"),
			"and offers the way back to its own index")
		checked += 1
	_expect(checked > 10, "every alchemy recipe has a page: %d" % checked)

	# A recipe that needs a book links to the book, and the book links back.
	var with_book := -1
	for index: int in range(catalogue.count()):
		if not str(catalogue.recipe(index).get("knowledge", "")).is_empty():
			with_book = index
			break
	if _expect(with_book >= 0, "the recipe table has a recipe that needs a book"):
		var recipe: Dictionary = catalogue.recipe(with_book)
		var book: String = str(recipe.get("knowledge", ""))
		var made: String = str(recipe.get("output", ""))
		view.open_page_key("entry:%s:%s" % [_category_for(
			str(recipe.get("skill", ""))), _slug(made)])
		_expect(body.text.contains("entry:books:%s" % _slug(book)),
			"%s links to the book it needs" % made)
		view.open_entry("books", _slug(book))
		_expect(body.get_parsed_text().contains(made),
			"and %s lists %s among what it opens" % [book, made])

	# Long categories are paged rather than run off the bottom of the window.
	view.open_page_key("cat:tailoring:0")
	var pages: int = ceili(float(view.entry_count_in("tailoring"))
		/ float(EncyclopediaView.ENTRIES_PER_PAGE))
	_expect(pages > 1, "tailoring is long enough to need paging: %d pages" % pages)
	_expect(view.page_label.visible and view.page_label.text == "Page 1/%d" % pages,
		"the page count is stated: %s" % view.page_label.text)
	_expect(view.previous_button.disabled and not view.next_button.disabled,
		"there is nothing before the first page and something after it")
	var first_page: String = body.get_parsed_text()
	view.next_button.pressed.emit()
	_expect(view.page_label.text == "Page 2/%d" % pages
		and body.get_parsed_text() != first_page,
		"and the forward control turns the page")
	view.previous_button.pressed.emit()
	_expect(body.get_parsed_text() == first_page, "the back control turns it back")

	# Back walks the trail, whatever the trail was made of.
	view.reset_to_index()
	_expect(view.back_button.disabled, "there is nothing behind the front page")
	view.open_category("world", 0)
	view.open_entry("world", "time")
	_expect(view.page_key() == "entry:world:time", "an entry page is where it says")
	view.go_back()
	_expect(view.page_key() == "cat:world:0", "Back returns to the category")
	view.go_back()
	_expect(view.page_key() == "index", "and again to the index")

	# Search reads the written half as well as the built half.
	view.search("harvesting")
	_expect(view.matches("harvesting").size() >= 2,
		"search finds the pages that say it: %d" % view.matches("harvesting").size())
	_expect(body.get_parsed_text().contains("Harvesting"),
		"and the results name them")
	_expect(view.matches("a phrase no page contains").is_empty(),
		"and finds nothing when there is nothing")

	# The right-click menu, which is what the status line points at.
	_expect(view.status_line.text.contains("Right-click"),
		"the window says where the search and the bookmarks are")
	_expect(not view.search_row.visible,
		"and the search field stays out of the way until it is asked for")
	view.call("_on_menu_id_pressed", 0)
	_expect(view.search_row.visible, "the menu's search entry brings it up")
	view.call("_on_search_submitted", "sigils")
	_expect(view.page_key() == "search:sigils", "and submitting it searches")

	# A bookmark is the player's own, and is kept in the client's own file.
	view.open_category("alchemy", 0)
	view.call("_on_menu_id_pressed", 1)
	await process_frame
	_expect(view.bookmarks().size() == 1
		and str((view.bookmarks()[0] as Dictionary).get("key", "")) == "cat:alchemy:0",
		"the page is bookmarked: %s" % str(view.bookmarks()))
	var config := ConfigFile.new()
	_expect(config.load(str(main.get("SETTINGS_PATH"))) == OK
		and (config.get_value("encyclopedia", "bookmarks", []) as Array).size() == 1,
		"and written to the client's settings file, not sent anywhere")
	view.call("_on_menu_id_pressed", 2)
	await process_frame
	_expect(view.bookmarks().is_empty(),
		"and removing it leaves the settings file as this suite found it")
	window.call("close")
	await process_frame

	# The move icon while Alt is held.
	main.call("_on_walk_button_pressed")
	main.call("_sync_hud_button_states", true)
	var walk_icon: Rect2 = _region(walk)
	var attack_icon: Rect2 = _region(attack)
	_expect(walk_icon != attack_icon and walk_icon != Rect2(),
		"the move and attack icons are different pictures")
	main.call("_input", _modifier(true))
	_expect(_region(walk) == attack_icon,
		"holding Alt turns the move icon into the attack icon")
	main.call("_input", _modifier(false))
	_expect(_region(walk) == walk_icon, "letting Alt go turns it back")

	# An attack mode chosen from the HUD is the player's decision, and Alt is
	# not allowed to look like what put it there or what took it away.
	main.call("_on_attack_button_pressed")
	main.call("_sync_hud_button_states", true)
	_expect(attack.button_pressed and str(main.get("_interaction_mode")) == "attack",
		"clicking the attack icon latches attack mode")
	main.call("_input", _modifier(true))
	_expect(attack.button_pressed and _region(walk) == walk_icon,
		"pressing Alt leaves it alone and leaves the move icon alone")
	main.call("_input", _modifier(false))
	_expect(attack.button_pressed and str(main.get("_interaction_mode")) == "attack",
		"and letting Alt go does not drop the player back into walk mode")
	main.call("_on_walk_button_pressed")
	main.call("_sync_hud_button_states", true)
	_expect(str(main.get("_interaction_mode")) == "walk",
		"the move icon is still how attack mode is left")

	# The move icon does what it is showing: while Alt is held it is the
	# attack icon, so pressing it is pressing the attack icon.
	main.call("_input", _modifier(true))
	main.call("_on_walk_button_pressed")
	_expect(str(main.get("_interaction_mode")) == "attack",
		"pressing the move icon while it shows attack chooses attack")
	main.call("_input", _modifier(false))
	main.call("_on_walk_button_pressed")
	main.call("_sync_hud_button_states", true)

	print("encyclopedia tests: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _category_for(skill: String) -> String:
	return "potions" if skill == "potion" else skill

static func _slug(text: String) -> String:
	var slug := ""
	for unit: int in text.to_lower().to_utf8_buffer():
		if (unit >= 97 and unit <= 122) or (unit >= 48 and unit <= 57):
			slug += char(unit)
		elif not slug.ends_with("-"):
			slug += "-"
	return slug.trim_suffix("-")

static func _region(button: Button) -> Rect2:
	var texture: AtlasTexture = button.icon as AtlasTexture
	return texture.region if texture != null else Rect2()

static func _key(keycode: Key, with_control: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.pressed = true
	event.physical_keycode = keycode
	event.keycode = keycode
	event.ctrl_pressed = with_control
	return event

static func _modifier(held: bool) -> InputEventKey:
	var event := InputEventKey.new()
	event.pressed = held
	event.physical_keycode = KEY_ALT
	event.keycode = KEY_ALT
	event.alt_pressed = held
	return event

func _expect(value: bool, label: String) -> bool:
	if not value:
		failures += 1
		push_error("FAIL: " + label)
	return value
