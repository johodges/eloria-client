extends Control
## The nine Eloria extension windows, built here rather than in main.gd.
##
## Each is driven by one server-push state packet and renders that snapshot and
## nothing else: the server states the whole window, the client draws it. None
## of these windows holds state of its own, so none of them can disagree with
## the server about what it is showing.
##
## The script deliberately declares no `class_name`: a global class is parsed
## before the autoload singletons are registered, and this window reads
## `AppState` directly, so naming it globally makes it fail to compile.
##
## They live in one script because they share one seam - the fork's extension
## protocol - and because main.gd is already long enough that nine more windows
## would make it unreadable. The quest surfaces use retained shared textures
## and style resources: their fantasy chrome is built once and has no
## actor-count cost.

const RESERVED_RIGHT_RAIL := 96.0
const PANEL_SIZE := Vector2(560.0, 380.0)
const QUEST_JOURNAL_SIZE := Vector2(540.0, 650.0)
const QUEST_TRACKER_SIZE := Vector2(292.0, 124.0)
const QUEST_TRACKER_MAX_HEIGHT := 320.0
const QUEST_STONE := Color(0.135, 0.125, 0.12, 0.98)
const QUEST_STONE_RAISED := Color(0.205, 0.18, 0.145, 1.0)
const QUEST_BRASS := Color(0.72, 0.54, 0.23, 1.0)
const QUEST_BRASS_BRIGHT := Color(0.96, 0.77, 0.26, 1.0)
const QUEST_PARCHMENT_DARK := Color(0.34, 0.20, 0.08, 1.0)
const QUEST_INK := Color(0.17, 0.105, 0.055, 1.0)
const QUEST_WARM_TEXT := Color(0.96, 0.93, 0.84, 1.0)
const QUEST_MUTED_TEXT := Color(0.68, 0.62, 0.52, 1.0)
const QUEST_BURGUNDY := Color(0.45, 0.075, 0.045, 1.0)
const QUEST_BURGUNDY_HOVER := Color(0.62, 0.12, 0.065, 1.0)
const QUEST_PARCHMENT_TEXTURE: Texture2D = preload(
	"res://assets/ui/oldcraft_inspired/eloria_parchment.png")
const QUEST_CARVED_FRAME_TEXTURE: Texture2D = preload(
	"res://assets/ui/oldcraft_inspired/eloria_carved_frame.png")
## The combat box. It reports one fight and then has nothing to say, so it
## holds for this long after the last thing that happened and fades out - it
## used to sit there after the target was already dead.
const COMBAT_HOLD_MSEC := 5000
const COMBAT_FADE_MSEC := 700
const COMBAT_PANEL_SIZE := Vector2(208.0, 64.0)
const COMBAT_FONT_SIZE := 11

signal combat_hud_preference_changed()

var item_atlas: ItemAtlas

# Always-on HUD readouts.
var navigation_label: Label
var combat_panel: PanelContainer
var combat_target: Label
var combat_player_bar: ProgressBar
var combat_target_bar: ProgressBar
var combat_event: Label
var combat_menu: PopupMenu
## Off entirely: the player dismissed it from its own menu and gets it back
## from the settings panel.
var combat_hud_enabled := true
## Pinned boxes never fade; they stay put until combat says otherwise.
var combat_hud_pinned := false
var _combat_expiry_msec := 0
var _combat_dragging := false
var _combat_drag_offset := Vector2.ZERO
var events_panel: PanelContainer
var events_text: RichTextLabel

# Toggled or server-opened windows, in cancel-cascade order.
var quest_panel: PanelContainer
var quest_list: ItemList
var quest_detail: RichTextLabel
var quest_track_button: Button
var quest_active_button: Button
var quest_done_button: Button
var quest_count: Label
## Which half of the journal is showing. The player's choice about their own
## window, so it is kept here; both lists are the server's own state.
var _quest_showing_archive := false
var tracked_quest: PanelContainer
var tracked_quest_text: RichTextLabel
var mail_panel: PanelContainer
var mail_list: ItemList
var mail_body: RichTextLabel
var detail_panel: PanelContainer
var detail_text: RichTextLabel
var merchant_panel: PanelContainer
var merchant_header: Label
var merchant_list: ItemList
## merchant_list remains the active list for tutorial and integration callers.
var merchant_buy_list: ItemList
var merchant_sell_list: ItemList
var merchant_buy_mode: Button
var merchant_sell_mode: Button
var merchant_selection: Label
var merchant_totals: Label
var merchant_trade: Button
var merchant_selected_icon: TextureRect
var merchant_empty_pack: Label
var _merchant_actor := -1
var merchant_quantity: LineEdit
var merchant_status: Label
var market_panel: PanelContainer
var market_header: Label
var market_list: ItemList
var market_status: Label
var party_panel: PanelContainer
var party_header: Label
var party_rows: VBoxContainer
var party_invite_row: HBoxContainer
var party_invite_label: Label
var party_status: Label
var party_leave_button: Button
var achievements_panel: PanelContainer
var achievements_header: Label
var achievements_tabs: HBoxContainer
var achievements_rows: VBoxContainer
var achievements_title_picker: OptionButton
var achievements_status: Label
## Which category is showing. The player's choice about their own window; the
## pages themselves are the server's, one per category in the catalogue.
var _achievements_page := ""

var _merchant_mode := "buy"
## The quest the player asked to keep on screen, by its title. Which quest to
## watch is the player's choice about their own screen, so it is kept here;
## everything shown about it is the server's own journal entry, restated on
## every 224, and a tracked quest the server stops sending simply stops being
## tracked.
var _tracked_quest_title := ""
var _tracked_quest_layout_revision := 0

func _ready() -> void:
	name = "ExtensionWindows"
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	# Anchors alone keep the current (zero) rect; the offsets have to be reset
	# too, or every centre-anchored readout lands 640 pixels off screen.
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_build()
	AppState.state_changed.connect(_on_state_changed)
	sync_all()

func configure(atlas: ItemAtlas) -> void:
	item_atlas = atlas

## True when a window that owns the pointer or the keyboard is open, so the
## rest of the HUD can treat the screen as busy.
func has_open_window() -> bool:
	for panel: PanelContainer in _cascade():
		if panel.visible:
			return true
	return false

## Closes the topmost open window. Returns true when something closed, so the
## cancel cascade in main.gd can stop there.
func close_top() -> bool:
	for panel: PanelContainer in _cascade():
		if not panel.visible:
			continue
		if panel == merchant_panel:
			AppState.close_merchant()
		elif panel == market_panel:
			AppState.close_marketplace()
		elif panel == detail_panel:
			AppState.close_item_detail()
		else:
			panel.hide()
		return true
	return false

func close_all() -> void:
	while close_top():
		pass

func toggle_quest_journal() -> void:
	_toggle(quest_panel)

func toggle_mail() -> void:
	_toggle(mail_panel)

func toggle_achievements() -> void:
	_sync_achievements()
	_toggle(achievements_panel)

## Cancel order: the windows the server opened come first, because they are the
## ones the player did not choose to have on screen.
func _cascade() -> Array[PanelContainer]:
	# The tracked-quest readout is deliberately absent: it is a HUD element the
	# player pinned, not a window covering the screen, so cancel leaves it be.
	return [merchant_panel, market_panel, detail_panel, mail_panel,
		quest_panel, party_panel, achievements_panel]

func _toggle(panel: PanelContainer) -> void:
	if panel.visible:
		panel.hide()
		return
	for other: PanelContainer in _cascade():
		if other != panel:
			other.hide()
	panel.show()
	panel.move_to_front()

func _on_state_changed(path: StringName) -> void:
	match path:
		&"navigation":
			_sync_navigation()
		&"combat_state":
			_sync_combat()
		&"special_events":
			_sync_events()
		&"quest_journal", &"quest_archive":
			_sync_quests()
		&"mail":
			_sync_mail()
		&"item_detail":
			_sync_detail()
		&"merchant":
			_sync_merchant()
		&"marketplace":
			_sync_marketplace()
		&"party":
			_sync_party()
		&"achievements_catalog":
			_sync_achievements()
		&"connection":
			if AppState.connection_state == "disconnected":
				# A dropped session is not a fight that just ended: nothing
				# from it should linger, pinned or not.
				combat_panel.hide()
				combat_panel.modulate.a = 1.0
				sync_all()

func sync_all() -> void:
	_sync_navigation()
	_sync_combat()
	_sync_events()
	_sync_quests()
	_sync_mail()
	_sync_detail()
	_sync_merchant()
	_sync_marketplace()
	_sync_party()
	_sync_achievements()

# --- navigation --------------------------------------------------------------

func _sync_navigation() -> void:
	if not bool(AppState.navigation.get("active", false)):
		navigation_label.hide()
		return
	navigation_label.text = "%s  %d, %d  (%d tiles)" % [
		str(AppState.navigation.get("label", "Waypoint")),
		int(AppState.navigation.get("x", 0)), int(AppState.navigation.get("y", 0)),
		int(AppState.navigation.get("distance", 0))]
	navigation_label.show()

# --- combat ------------------------------------------------------------------

func _sync_combat() -> void:
	if not combat_hud_enabled:
		combat_panel.hide()
		return
	if not bool(AppState.combat_state.get("active", false)):
		return
	var target_name: String = str(AppState.combat_state.get("target_name", ""))
	combat_target.text = target_name if not target_name.is_empty() else "Target"
	combat_player_bar.max_value = maxi(1, int(
		AppState.combat_state.get("player_max_health", 1)))
	combat_player_bar.value = int(AppState.combat_state.get("player_health", 0))
	combat_target_bar.max_value = maxi(1, int(
		AppState.combat_state.get("target_max_health", 1)))
	combat_target_bar.value = int(AppState.combat_state.get("target_health", 0))
	combat_event.text = _combat_event_text()
	combat_panel.modulate.a = 1.0
	combat_panel.show()
	_combat_expiry_msec = Time.get_ticks_msec() + COMBAT_HOLD_MSEC

## The box holds for five seconds after the last thing combat said and then
## fades. A pinned one is left alone, and a dismissed one is already hidden.
func _process(_delta: float) -> void:
	if not combat_panel.visible or combat_hud_pinned or _combat_dragging:
		return
	var past: int = Time.get_ticks_msec() - _combat_expiry_msec
	if past < 0:
		return
	if past >= COMBAT_FADE_MSEC:
		combat_panel.hide()
		combat_panel.modulate.a = 1.0
		return
	combat_panel.modulate.a = 1.0 - float(past) / float(COMBAT_FADE_MSEC)

## Left drag moves the box; right click offers to pin or dismiss it.
func _on_combat_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_RIGHT and button.pressed:
			combat_menu.set_item_checked(0, combat_hud_pinned)
			combat_menu.position = Vector2i(get_viewport().get_mouse_position())
			combat_menu.popup()
			combat_panel.accept_event()
			return
		if button.button_index != MOUSE_BUTTON_LEFT:
			return
		_combat_dragging = button.pressed
		if button.pressed:
			_combat_drag_offset = (get_viewport().get_mouse_position()
				- combat_panel.position)
			combat_panel.modulate.a = 1.0
		else:
			_combat_expiry_msec = Time.get_ticks_msec() + COMBAT_HOLD_MSEC
			combat_hud_preference_changed.emit()
		combat_panel.accept_event()
	elif event is InputEventMouseMotion and _combat_dragging:
		var wanted: Vector2 = get_viewport().get_mouse_position() - _combat_drag_offset
		# The panel is anchored to the top centre, so its position is an offset
		# from there rather than a screen coordinate; keeping it on screen is a
		# clamp against half the width either side.
		var half: float = size.x * 0.5
		combat_panel.position = Vector2(
			clampf(wanted.x, -half, maxf(-half, half - combat_panel.size.x)),
			clampf(wanted.y, 0.0, maxf(0.0, size.y - combat_panel.size.y)))
		combat_panel.accept_event()

func _on_combat_menu_pressed(id: int) -> void:
	if id == 0:
		set_combat_hud_pinned(not combat_hud_pinned)
	else:
		set_combat_hud_enabled(false)
	combat_hud_preference_changed.emit()

func set_combat_hud_enabled(enabled: bool) -> void:
	combat_hud_enabled = enabled
	if not enabled:
		combat_panel.hide()
		return
	combat_panel.modulate.a = 1.0
	_sync_combat()

func set_combat_hud_pinned(pinned: bool) -> void:
	combat_hud_pinned = pinned
	if pinned and combat_hud_enabled:
		combat_panel.modulate.a = 1.0
		combat_panel.show()

func combat_hud_position() -> Vector2:
	return combat_panel.position

func set_combat_hud_position(where: Vector2) -> void:
	combat_panel.position = where

func _combat_event_text() -> String:
	var damage: int = int(AppState.combat_state.get("recent_damage", 0))
	match int(AppState.combat_state.get("event", 0)):
		EloriaProtocol.COMBAT_EVENT_HIT:
			return "Hit for %d" % damage
		EloriaProtocol.COMBAT_EVENT_MISS:
			return "Missed"
		EloriaProtocol.COMBAT_EVENT_DODGE:
			return "Dodged"
		EloriaProtocol.COMBAT_EVENT_DEFEAT:
			return "Defeated"
		_:
			return "In combat"

# --- special events ----------------------------------------------------------

func _sync_events() -> void:
	if AppState.special_events.is_empty():
		events_panel.hide()
		return
	events_text.text = "\n".join(AppState.special_events)
	events_panel.show()

# --- quest journal -----------------------------------------------------------

func _sync_quests() -> void:
	quest_active_button.button_pressed = not _quest_showing_archive
	quest_done_button.button_pressed = _quest_showing_archive
	quest_done_button.text = "Completed (%d)" % AppState.quest_archive.size()
	quest_count.text = ("%d COMPLETE" % AppState.quest_archive.size()
		if _quest_showing_archive else "%d ACTIVE" % AppState.quest_journal.size())
	if _quest_showing_archive:
		_sync_quest_archive()
		return
	var selected: int = _selected_index(quest_list)
	quest_list.clear()
	for entry: Dictionary in AppState.quest_journal:
		var target: int = int(entry.get("target", 0))
		var current: int = int(entry.get("current", 0))
		var status: String = ("ready" if bool(entry.get("ready", false))
			else ("%d/%d" % [current, target] if target > 0 else "in progress"))
		quest_list.add_item("◆  %s  [%s]" % [str(entry.get("title", "")), status])
		var row: int = quest_list.item_count - 1
		quest_list.set_item_custom_fg_color(row, QUEST_BRASS_BRIGHT
			if bool(entry.get("ready", false)) else QUEST_WARM_TEXT)
	if AppState.quest_journal.is_empty():
		quest_detail.text = ("[center][color=#7c5a34][font_size=16]"
			+ "%s[/font_size][/color][/center]" % tr("ELORIA_QUEST_NONE"))
		quest_track_button.disabled = true
		_sync_tracked_quest()
		return
	quest_track_button.disabled = false
	var index: int = clampi(selected, 0, AppState.quest_journal.size() - 1)
	quest_list.select(index)
	_show_quest(index)
	_sync_tracked_quest()
	quest_track_button.text = ("Untrack"
		if str((AppState.quest_journal[index] as Dictionary).get("title", ""))
			== _tracked_quest_title else "Track")

## The finished half of the same window. Tracking is meaningless here - there
## is nothing left to do - so the button is disabled rather than removed, which
## would move everything else when the view changes.
func _sync_quest_archive() -> void:
	var selected: int = _selected_index(quest_list)
	quest_list.clear()
	for entry: Dictionary in AppState.quest_archive:
		quest_list.add_item("✓  %s  [%s]" % [str(entry.get("title", "")),
			str(entry.get("location", ""))])
		quest_list.set_item_custom_fg_color(quest_list.item_count - 1,
			QUEST_MUTED_TEXT)
	quest_track_button.disabled = true
	if AppState.quest_archive.is_empty():
		quest_detail.text = ("[center][color=#7c5a34][font_size=16]"
			+ "You have not finished any quests yet.[/font_size][/color][/center]")
		return
	var index: int = clampi(selected, 0, AppState.quest_archive.size() - 1)
	quest_list.select(index)
	_show_archived_quest(index)

func _on_quest_view(archive: bool) -> void:
	if _quest_showing_archive == archive:
		# Both are toggle buttons, so pressing the one already down would
		# otherwise un-press it and leave the window showing neither view.
		quest_active_button.button_pressed = not archive
		quest_done_button.button_pressed = archive
		return
	_quest_showing_archive = archive
	quest_list.deselect_all()
	_sync_quests()

## Pins the selected quest to the screen, or unpins it when it is already the
## tracked one.
func _on_quest_track_pressed() -> void:
	var index: int = _selected_index(quest_list)
	if index < 0 or index >= AppState.quest_journal.size():
		return
	var title: String = str(
		(AppState.quest_journal[index] as Dictionary).get("title", ""))
	_tracked_quest_title = "" if title == _tracked_quest_title else title
	_sync_quests()

## The tracked quest as the server last stated it. Nothing is remembered from
## an earlier journal: if the server stops listing the quest, the readout goes.
func _sync_tracked_quest() -> void:
	var tracked: Dictionary = {}
	for entry: Dictionary in AppState.quest_journal:
		if str(entry.get("title", "")) == _tracked_quest_title:
			tracked = entry
			break
	if tracked.is_empty():
		_tracked_quest_title = ""
		_tracked_quest_layout_revision += 1
		tracked_quest.hide()
		quest_track_button.text = "Track"
		return
	var target: int = int(tracked.get("target", 0))
	var lines: Array[String] = [
		"[center][font_size=20][color=#8f6425][b]QUEST TRACKER[/b][/color][/font_size][/center]",
		"[font_size=17][color=#592b18]◆  [b]%s[/b][/color][/font_size]"
			% str(tracked.get("title", "")),
		"[indent][font_size=15][color=#2b1a0e]%s[/color][/font_size][/indent]"
			% str(tracked.get("objective", ""))]
	if bool(tracked.get("ready", false)):
		lines.append("[indent][font_size=15][color=#946c1d][b]Ready to turn in[/b][/color]"
			+ "[color=#5e4b35] at %s[/color][/font_size][/indent]"
			% str(tracked.get("location", "unknown")))
	elif target > 0:
		lines.append(("[indent][font_size=15][color=#70491d]%d of %d[/color]"
			+ "[color=#5e4b35]  ·  %s[/color][/font_size][/indent]") % [
				int(tracked.get("current", 0)), target,
				str(tracked.get("location", "unknown"))])
	else:
		lines.append("[indent][font_size=15][color=#5e4b35]%s[/color][/font_size][/indent]"
			% str(tracked.get("location", "unknown")))
	# Let the label report its natural wrapped height for this one update. The
	# event-driven fitter turns this back off after applying the bounded size.
	tracked_quest.custom_minimum_size.y = QUEST_TRACKER_SIZE.y
	tracked_quest.size.y = QUEST_TRACKER_SIZE.y
	tracked_quest_text.fit_content = true
	tracked_quest_text.text = "\n".join(lines)
	tracked_quest.show()
	# RichTextLabel resolves wrapped line height after its container settles.
	# Fit only when the server changes the quest, never from `_process()`.
	_tracked_quest_layout_revision += 1
	_fit_tracked_quest_to_content(_tracked_quest_layout_revision)

func _fit_tracked_quest_to_content(revision: int) -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	if revision != _tracked_quest_layout_revision or not tracked_quest.visible:
		return
	var content_height := tracked_quest_text.get_content_height()
	tracked_quest_text.fit_content = false
	var desired_height := clampf(content_height + 32.0,
		QUEST_TRACKER_SIZE.y, QUEST_TRACKER_MAX_HEIGHT)
	tracked_quest.custom_minimum_size.y = desired_height
	tracked_quest.size.y = desired_height
	tracked_quest_text.scroll_active = content_height + 32.0 > QUEST_TRACKER_MAX_HEIGHT

## One list serves both halves of the window, so a selection has to be read
## against whichever half is showing - against the other one it would either
## describe the wrong quest or silently describe nothing.
func _on_quest_selected(index: int) -> void:
	if _quest_showing_archive:
		_show_archived_quest(index)
	else:
		_show_quest(index)

func _show_archived_quest(index: int) -> void:
	if index < 0 or index >= AppState.quest_archive.size():
		return
	var entry: Dictionary = AppState.quest_archive[index]
	quest_detail.text = ("[font_size=22][color=#592b18][b]%s[/b][/color][/font_size]"
		+ "\n[color=#9b682d][font_size=11][b]COMPLETED IN[/b][/font_size][/color]"
		+ "\n[color=#2b1a0e]%s[/color]\n\n"
		+ "[color=#9b682d][font_size=11][b]CHRONICLE[/b][/font_size][/color]"
		+ "\n[color=#2b1a0e]%s[/color]") % [str(entry.get("title", "")),
			str(entry.get("location", "")), str(entry.get("detail", ""))]

func _show_quest(index: int) -> void:
	if index < 0 or index >= AppState.quest_journal.size():
		return
	var entry: Dictionary = AppState.quest_journal[index]
	var target: int = int(entry.get("target", 0))
	var lines: Array[String] = [
		"[font_size=22][color=#592b18][b]%s[/b][/color][/font_size]"
			% str(entry.get("title", "")),
		"[color=#9b682d][font_size=11][b]QUEST OBJECTIVES[/b][/font_size][/color]",
		"[color=#2b1a0e]◆  %s[/color]" % str(entry.get("objective", "")),
		"",
		"[color=#9b682d][font_size=11][b]LOCATION[/b][/font_size][/color]",
		"[color=#2b1a0e]%s[/color]" % str(entry.get("location", "unknown"))]
	if bool(entry.get("ready", false)):
		lines.append("\n[color=#946c1d][b]%s[/b][/color]"
			% tr("ELORIA_QUEST_READY"))
	elif target > 0:
		lines.append("\n[color=#9b682d][font_size=11][b]PROGRESS[/b][/font_size][/color]")
		lines.append("[color=#2b1a0e]%d of %d complete[/color]"
			% [int(entry.get("current", 0)), target])
	quest_detail.text = "\n".join(lines)

# --- mail --------------------------------------------------------------------

func _sync_mail() -> void:
	var selected: int = _selected_index(mail_list)
	mail_list.clear()
	for message: Dictionary in AppState.mail:
		mail_list.add_item("%s%s  -  %s" % [
			"" if bool(message.get("read", false)) else "* ",
			str(message.get("sender", "")), str(message.get("subject", ""))])
	if AppState.mail.is_empty():
		mail_body.text = "[center]No mail.[/center]"
		return
	var index: int = clampi(selected, 0, AppState.mail.size() - 1)
	mail_list.select(index)
	_show_mail(index)

func _show_mail(index: int) -> void:
	if index < 0 or index >= AppState.mail.size():
		return
	var message: Dictionary = AppState.mail[index]
	mail_body.text = "[b]%s[/b]\nfrom %s\n\n%s" % [
		str(message.get("subject", "")), str(message.get("sender", "")),
		str(message.get("body", ""))]

func _on_mail_selected(index: int) -> void:
	_show_mail(index)
	if index < 0 or index >= AppState.mail.size():
		return
	var message: Dictionary = AppState.mail[index]
	if bool(message.get("read", false)):
		return
	# The read flag is the server's. Asking it to mark the message read is the
	# only way to change it; the list redraws when the new inbox arrives.
	Network.send_chat("#mail read %d" % int(message.get("mail_id", 0)))

# --- item detail -------------------------------------------------------------

## Whether an item description may open this window. The inventory sets it
## before each request: a plain click wants only the line along the bottom of
## the inventory, and Inspect wants the whole card. The state that arrives is
## the same either way - what changes is whether it is shown here.
var detail_popup_allowed := true

func _sync_detail() -> void:
	if not bool(AppState.item_detail.get("open", false)) or not detail_popup_allowed:
		detail_panel.hide()
		return
	var lines: Array[String] = ["[b]%s[/b]" % str(AppState.item_detail.get("name", ""))]
	var category: String = str(AppState.item_detail.get("category", ""))
	if not category.is_empty():
		lines.append(category)
	if bool(AppState.item_detail.get("equipped", false)):
		lines.append("[color=#8fdc8f]Equipped.[/color]")
	var quantity: int = int(AppState.item_detail.get("quantity", 0))
	if quantity > 1:
		lines.append("Quantity: %d" % quantity)
	for field: String in ["description", "stats"]:
		var value: String = str(AppState.item_detail.get(field, ""))
		if not value.is_empty():
			lines.append("")
			lines.append(value)
	var comparison_name: String = str(AppState.item_detail.get("comparison_name", ""))
	if not comparison_name.is_empty():
		lines.append("")
		lines.append("[b]Compared with %s[/b]" % comparison_name)
		lines.append(str(AppState.item_detail.get("comparison", "")))
	detail_text.text = "\n".join(lines)
	detail_panel.show()
	detail_panel.move_to_front()

# --- merchant ----------------------------------------------------------------

func _sync_merchant() -> void:
	if not bool(AppState.merchant.get("open", false)):
		merchant_panel.hide()
		_merchant_actor = -1
		return
	var actor_id := int(AppState.merchant.get("actor_id", -1))
	var selected_id := -1
	if _merchant_actor == actor_id and merchant_list != null and not merchant_list.get_selected_items().is_empty():
		selected_id = int(merchant_list.get_item_metadata(merchant_list.get_selected_items()[0]))
	else:
		_merchant_mode = "buy"
		merchant_quantity.text = "1"
	_merchant_actor = actor_id
	merchant_header.text = "%s    ·    Gold: %d gc    ·    Carry: %d/%d" % [
		str(AppState.merchant.get("npc_name", "Merchant")),
		int(AppState.merchant.get("gold", 0)), int(AppState.merchant.get("carried", 0)),
		int(AppState.merchant.get("capacity", 0))]
	merchant_buy_list.clear()
	merchant_sell_list.clear()
	for entry: Dictionary in AppState.merchant.get("items", []) as Array:
		_add_merchant_row(merchant_buy_list, entry, false)
		if int(entry.get("owned", 0)) > 0 and int(entry.get("sell_price", 0)) > 0:
			_add_merchant_row(merchant_sell_list, entry, true)
	merchant_empty_pack.visible = merchant_sell_list.item_count == 0
	merchant_list = merchant_buy_list if _merchant_mode == "buy" else merchant_sell_list
	for index: int in range(merchant_list.item_count):
		if int(merchant_list.get_item_metadata(index)) == selected_id:
			merchant_list.select(index)
			break
	if merchant_list.get_selected_items().is_empty() and merchant_list.item_count > 0:
		merchant_list.select(0)
	merchant_list.ensure_current_is_visible()
	merchant_status.text = ""
	_sync_merchant_summary()
	merchant_panel.show()
	merchant_panel.move_to_front()

func _add_merchant_row(list: ItemList, entry: Dictionary, selling: bool) -> void:
	var name := str(entry.get("name", ""))
	var price := int(entry.get("sell_price" if selling else "buy_price", 0))
	var label := "%s  ×%d     ·     %d gc each" % [name, int(entry.get("owned", 0)), price] if selling else "%s     ·     %d gc each" % [name, price]
	var row := list.item_count
	list.add_item(label, _named_icon(int(entry.get("image_id", 0)), name))
	list.set_item_metadata(row, int(entry.get("index", row)))
	list.set_item_tooltip(row, "%s\n%s: %d gc each\nIn your pack: %d" % [name, "Sell price" if selling else "Buy price", price, int(entry.get("owned", 0))])

func _on_merchant_selected(_index: int, mode: String) -> void:
	_merchant_mode = mode
	merchant_list = merchant_buy_list if mode == "buy" else merchant_sell_list
	(merchant_sell_list if mode == "buy" else merchant_buy_list).deselect_all()
	merchant_list.ensure_current_is_visible()
	_sync_merchant_summary()

func _on_merchant_mode(mode: String) -> void:
	_merchant_mode = mode
	merchant_list = merchant_buy_list if mode == "buy" else merchant_sell_list
	(merchant_sell_list if mode == "buy" else merchant_buy_list).deselect_all()
	if merchant_list.get_selected_items().is_empty() and merchant_list.item_count > 0:
		merchant_list.select(0)
	merchant_list.ensure_current_is_visible()
	_sync_merchant_summary()

func _merchant_entry() -> Dictionary:
	var selected := merchant_list.get_selected_items()
	if selected.is_empty():
		return {}
	var item_index := int(merchant_list.get_item_metadata(selected[0]))
	for entry: Dictionary in AppState.merchant.get("items", []) as Array:
		if int(entry.get("index", -1)) == item_index:
			return entry
	return {}

func _merchant_maximum(entry: Dictionary) -> int:
	if entry.is_empty():
		return 0
	if _merchant_mode == "sell":
		return mini(1000000, int(entry.get("owned", 0)))
	var price := int(entry.get("buy_price", 0))
	var maximum := mini(1000000, int(AppState.merchant.get("gold", 0)) / price) if price > 0 else 1000000
	var weight := int(entry.get("emu", 0))
	if weight > 0:
		var free := maxi(0, int(AppState.merchant.get("capacity", 0)) - int(AppState.merchant.get("carried", 0)))
		maximum = mini(maximum, free / weight)
	return maximum

func _merchant_change_quantity(delta: int) -> void:
	merchant_quantity.text = str(clampi(int(merchant_quantity.text) + delta, 1, 1000000))
	_sync_merchant_summary()

func _merchant_set_maximum() -> void:
	merchant_quantity.text = str(maxi(1, _merchant_maximum(_merchant_entry())))
	_sync_merchant_summary()

func _sync_merchant_summary(_text: String = "") -> void:
	merchant_buy_mode.set_pressed_no_signal(_merchant_mode == "buy")
	merchant_sell_mode.set_pressed_no_signal(_merchant_mode == "sell")
	var entry := _merchant_entry()
	merchant_trade.disabled = true
	if entry.is_empty():
		merchant_selection.text = "Select an item to buy or sell."
		merchant_totals.text = ""
		merchant_selected_icon.texture = null
		merchant_trade.text = "Buy" if _merchant_mode == "buy" else "Sell"
		return
	var buying := _merchant_mode == "buy"
	var price := int(entry.get("buy_price" if buying else "sell_price", 0))
	merchant_selection.text = "%s\n%s · %d gc each" % ["BUYING" if buying else "SELLING", str(entry.get("name", "")), price]
	merchant_selected_icon.texture = _named_icon(int(entry.get("image_id", 0)), str(entry.get("name", "")))
	var quantity_text := merchant_quantity.text.strip_edges()
	var valid := quantity_text.is_valid_int() and int(quantity_text) >= 1 and int(quantity_text) <= 1000000
	if not valid:
		merchant_totals.text = "Enter a whole quantity\nbetween 1 and 1,000,000."
		return
	var quantity := int(quantity_text)
	var total := quantity * price
	var gold_after := int(AppState.merchant.get("gold", 0)) + (-total if buying else total)
	merchant_totals.text = "%s: %d gc\nGold after: %d gc" % ["Cost" if buying else "Receive", total, gold_after]
	if entry.has("emu"):
		var carry_after := int(AppState.merchant.get("carried", 0)) + int(entry.emu) * quantity * (1 if buying else -1)
		merchant_totals.text += "\nCarry after: %d/%d" % [maxi(0, carry_after), int(AppState.merchant.get("capacity", 0))]
	merchant_trade.text = "%s %d" % ["Buy" if buying else "Sell", quantity]
	merchant_trade.disabled = quantity > _merchant_maximum(entry)
	merchant_trade.tooltip_text = "Not enough gold or free carry space." if buying and merchant_trade.disabled else "You do not own that many." if merchant_trade.disabled else ""

## The dedicated shop command accepts an exact quantity in one request. The
## server validates stock, gold, carrying capacity and ownership as before.
func _merchant_trade_command() -> String:
	var quantity_text := merchant_quantity.text.strip_edges()
	if not quantity_text.is_valid_int() or int(quantity_text) < 1 or int(quantity_text) > 1000000:
		merchant_status.text = "Enter a whole quantity between 1 and 1,000,000."
		return ""
	var actor_id: int = int(AppState.merchant.get("actor_id", -1))
	var selected: PackedInt32Array = merchant_list.get_selected_items()
	if actor_id < 0 or selected.is_empty():
		merchant_status.text = "Select an item first."
		return ""
	var item_index: int = int(merchant_list.get_item_metadata(int(selected[0])))
	return "#shop %s %d %d %d" % [_merchant_mode, actor_id, item_index, int(quantity_text)]


func _on_merchant_trade() -> void:
	_sync_merchant_summary()
	if merchant_trade.disabled:
		return
	var command := _merchant_trade_command()
	if command.is_empty():
		return
	var trade_error: Error = Network.send_chat(command)
	if trade_error != OK:
		merchant_status.text = "Merchant request failed: " + error_string(trade_error)
		return
	merchant_status.text = "Buying…" if _merchant_mode == "buy" else "Selling…"

# --- marketplace -------------------------------------------------------------

func _sync_marketplace() -> void:
	if not bool(AppState.marketplace.get("open", false)):
		market_panel.hide()
		return
	market_header.text = "Nymara Exchange  -  %d gold  -  %d item(s) in escrow" % [
		int(AppState.marketplace.get("gold", 0)),
		int(AppState.marketplace.get("returned_items", 0))]
	var selected: int = _selected_index(market_list)
	market_list.clear()
	for listing: Dictionary in AppState.marketplace.get("listings", []) as Array:
		var index: int = market_list.item_count
		market_list.add_item("%s x%d  -  %d gc each  -  %s  -  %s left" % [
			str(listing.get("item_name", "")), int(listing.get("quantity", 0)),
			int(listing.get("unit_price", 0)), str(listing.get("seller", "")),
			_duration_text(int(listing.get("seconds_left", 0)))])
		market_list.set_item_metadata(index, int(listing.get("listing_id", -1)))
		if item_atlas != null:
			var icon: Texture2D = _named_icon(int(listing.get("image_id", 0)),
				str(listing.get("item_name", "")))
			if icon != null:
				market_list.set_item_icon(index, icon)
	if market_list.item_count > 0:
		market_list.select(clampi(selected, 0, market_list.item_count - 1))
	market_panel.show()
	market_panel.move_to_front()

func _on_market_buy() -> void:
	var selected: PackedInt32Array = market_list.get_selected_items()
	if selected.is_empty():
		market_status.text = "Select a listing first."
		return
	var listing_id: int = int(market_list.get_item_metadata(int(selected[0])))
	# "all" is the server's own word for the whole listing.
	var error: Error = Network.send_chat("#auction buy %d all" % listing_id)
	market_status.text = ("Sent to the server; the window updates when it answers."
		if error == OK else "Purchase request failed: " + error_string(error))

func _on_market_collect() -> void:
	var error: Error = Network.send_chat("#auction collect")
	market_status.text = ("Collecting escrow." if error == OK
		else "Collect request failed: " + error_string(error))

func _on_market_view(view: String) -> void:
	var error: Error = Network.send_chat("#auction ui %s" % view)
	if error != OK:
		market_status.text = "View request failed: " + error_string(error)

func _duration_text(seconds: int) -> String:
	if seconds >= 86400:
		return "%dd" % (seconds / 86400)
	if seconds >= 3600:
		return "%dh" % (seconds / 3600)
	return "%dm" % maxi(1, seconds / 60)

# --- party -------------------------------------------------------------------

## The window exists to answer one question the world view cannot: how is
## somebody doing who is not on your screen. So every row carries health and
## ether as bars and states where that person is standing, and a member the
## server reports offline keeps their row and says so.
func _sync_party() -> void:
	var state: Dictionary = AppState.party
	var members: Array = state.get("members", []) as Array
	var invited_by: String = str(state.get("invited_by", ""))

	party_invite_label.text = "%s invited you. Accept?" % invited_by
	party_invite_row.visible = not invited_by.is_empty()

	if not bool(state.get("in_party", false)) and invited_by.is_empty():
		party_panel.hide()
		return

	for child: Node in party_rows.get_children():
		child.queue_free()
	var online_count := 0
	for raw: Variant in members:
		var member: Dictionary = raw as Dictionary
		if bool(member.get("online", false)):
			online_count += 1
		party_rows.add_child(_party_row(member))
	party_header.text = ("Party - %d of %d online" % [online_count, members.size()]
		if not members.is_empty() else "No party")
	party_leave_button.disabled = members.is_empty()
	party_panel.show()
	party_panel.move_to_front()

func _party_row(member: Dictionary) -> Control:
	var row := VBoxContainer.new()
	row.name = "Member" + str(member.get("name", ""))
	var online: bool = bool(member.get("online", false))
	# A row that has stopped updating should look like it has stopped, rather
	# than showing the last health the player had before they vanished.
	var tint: Color = Color(1, 1, 1, 1) if online else Color(1, 1, 1, 0.45)

	# Name and standing share a line so a full party of eight fits without
	# the window becoming a scroll of near-identical blocks.
	var header := HBoxContainer.new()
	header.name = "Header"
	row.add_child(header)
	var title := Label.new()
	title.name = "Name"
	var marks := ""
	if bool(member.get("leader", false)):
		marks += "  (leader)"
	if bool(member.get("is_self", false)):
		marks += "  (you)"
	title.text = "%s%s" % [str(member.get("name", "")), marks]
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title.modulate = tint
	header.add_child(title)
	var where := Label.new()
	where.name = "Standing"
	if online:
		where.text = "%d/%d · %d/%d · %s (%d, %d)" % [
			int(member.get("health", 0)), int(member.get("max_health", 0)),
			int(member.get("ether", 0)), int(member.get("max_ether", 0)),
			str(member.get("map_id", "")), int(member.get("x", 0)),
			int(member.get("y", 0))]
	else:
		where.text = "offline"
	where.modulate = tint
	header.add_child(where)

	var health := _bar("Health", Color(0.78, 0.24, 0.22))
	health.custom_minimum_size = Vector2(0.0, 9.0)
	health.max_value = maxf(1.0, float(member.get("max_health", 1)))
	health.value = float(member.get("health", 0))
	health.modulate = tint
	row.add_child(health)

	var ether := _bar("Ether", Color(0.27, 0.45, 0.78))
	ether.custom_minimum_size = Vector2(0.0, 9.0)
	ether.max_value = maxf(1.0, float(member.get("max_ether", 1)))
	ether.value = float(member.get("ether", 0))
	ether.modulate = tint
	row.add_child(ether)
	return row

## The catalogue, one category at a time, with a bar on every line.
##
## Everything drawn came off the wire, including which pages exist: a category
## the server's catalogue gains appears here without this file changing.
func _sync_achievements() -> void:
	var entries: Array = AppState.achievements_catalog.get("entries", []) as Array
	var done := 0
	var pages: Array[String] = []
	for raw: Variant in entries:
		var entry: Dictionary = raw as Dictionary
		if bool(entry.get("done", false)):
			done += 1
		var page: String = str(entry.get("category", ""))
		if not pages.has(page):
			pages.append(page)
	achievements_header.text = ("%d of %d earned" % [done, entries.size()]
		if not entries.is_empty() else "No achievements yet")
	if not pages.has(_achievements_page):
		_achievements_page = pages[0] if not pages.is_empty() else ""
	_sync_achievement_tabs(pages)
	_sync_achievement_titles(entries)
	for child: Node in achievements_rows.get_children():
		achievements_rows.remove_child(child)
		child.queue_free()
	for raw: Variant in entries:
		var entry: Dictionary = raw as Dictionary
		if str(entry.get("category", "")) == _achievements_page:
			achievements_rows.add_child(_achievement_row(entry))

func _sync_achievement_tabs(pages: Array[String]) -> void:
	for child: Node in achievements_tabs.get_children():
		achievements_tabs.remove_child(child)
		child.queue_free()
	for page: String in pages:
		var button := Button.new()
		button.name = "Page" + page
		button.text = page
		button.toggle_mode = true
		button.button_pressed = page == _achievements_page
		button.pressed.connect(_on_achievements_page_chosen.bind(page))
		achievements_tabs.add_child(button)

func _on_achievements_page_chosen(page: String) -> void:
	_achievements_page = page
	_sync_achievements()

## The picker offers exactly the titles this character has earned, because the
## server refuses any other and a menu of things it would refuse is worse than
## a short menu.
func _sync_achievement_titles(entries: Array) -> void:
	var worn: String = str(AppState.achievements_catalog.get("worn_title", ""))
	achievements_title_picker.clear()
	achievements_title_picker.add_item("(none)")
	achievements_title_picker.set_item_metadata(0, "none")
	var chosen := 0
	for raw: Variant in entries:
		var entry: Dictionary = raw as Dictionary
		var title: String = str(entry.get("title", ""))
		if title.is_empty() or not bool(entry.get("done", false)):
			continue
		achievements_title_picker.add_item(title)
		var index: int = achievements_title_picker.item_count - 1
		achievements_title_picker.set_item_metadata(index, title)
		if title == worn:
			chosen = index
	achievements_title_picker.select(chosen)
	achievements_title_picker.disabled = achievements_title_picker.item_count <= 1

func _on_achievement_title_chosen(index: int) -> void:
	var wanted: String = str(achievements_title_picker.get_item_metadata(index))
	var error: Error = Network.send_chat("#title " + wanted)
	achievements_status.text = ("Sent to the server; the window updates when it answers."
		if error == OK else "Title request failed: " + error_string(error))

func _achievement_row(entry: Dictionary) -> Control:
	var row := VBoxContainer.new()
	row.name = "Achievement" + str(entry.get("key", ""))
	var header := HBoxContainer.new()
	header.name = "Header"
	row.add_child(header)
	var name_label := Label.new()
	name_label.name = "Name"
	name_label.text = str(entry.get("name", ""))
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(name_label)
	var progress: int = int(entry.get("progress", 0))
	var target: int = maxi(1, int(entry.get("target", 1)))
	var count := Label.new()
	count.name = "Count"
	count.text = "%d / %d" % [progress, target]
	header.add_child(count)
	var tick := Label.new()
	tick.name = "Done"
	tick.custom_minimum_size = Vector2(24, 0)
	tick.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tick.text = "*" if bool(entry.get("done", false)) else ""
	header.add_child(tick)
	var bar := _bar("Progress", Color(0.42, 0.62, 0.35))
	bar.custom_minimum_size = Vector2(0.0, 9.0)
	bar.max_value = float(target)
	bar.value = float(mini(progress, target))
	row.add_child(bar)
	var blurb := Label.new()
	blurb.name = "Description"
	blurb.text = str(entry.get("description", ""))
	blurb.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	# An unearned row is the catalogue a player browses rather than a failure,
	# so it stays legible; the tick and the full bar mark the earned ones.
	blurb.modulate = Color(1.0, 1.0, 1.0, 0.7)
	row.add_child(blurb)
	var granted: String = str(entry.get("title", ""))
	if not granted.is_empty():
		var reward := Label.new()
		reward.name = "Grants"
		reward.text = "   grants the title \"%s\"" % granted
		reward.modulate = Color(0.85, 0.78, 0.45, 1.0)
		row.add_child(reward)
	return row

func _on_party_accept() -> void:
	_send_party_command("#party accept")

func _on_party_decline() -> void:
	_send_party_command("#party decline")

func _on_party_leave() -> void:
	_send_party_command("#party leave")

func _send_party_command(command: String) -> void:
	var error: Error = Network.send_chat(command)
	party_status.text = ("Sent to the server; the window updates when it answers."
		if error == OK else "Party request failed: " + error_string(error))

func toggle_party() -> void:
	if party_panel.visible:
		party_panel.hide()
		return
	_sync_party()
	# Nothing to show is worth saying, rather than a button that does nothing.
	if not party_panel.visible:
		party_status.text = ""
		party_header.text = "No party"
		for child: Node in party_rows.get_children():
			child.queue_free()
		party_panel.show()
		party_panel.move_to_front()

# --- construction ------------------------------------------------------------

## Worn goods look worn here too: a merchant's stock and the exchange both name
## what they are selling, so the name is enough to decide without the server
## restating it per row.
func _named_icon(image_id: int, name: String) -> Texture2D:
	if item_atlas == null:
		return null
	if AppState.is_degraded_item(name):
		var worn: Texture2D = item_atlas.worn_icon_for(image_id)
		if worn != null:
			return worn
	return item_atlas.icon_for(image_id)

func _selected_index(list: ItemList) -> int:
	var selected: PackedInt32Array = list.get_selected_items()
	return int(selected[0]) if not selected.is_empty() else 0

func _build() -> void:
	navigation_label = Label.new()
	navigation_label.name = "NavigationHud"
	navigation_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	navigation_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	navigation_label.position = Vector2(-180.0, 34.0)
	navigation_label.custom_minimum_size = Vector2(360.0, 24.0)
	navigation_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	navigation_label.hide()
	add_child(navigation_label)

	combat_panel = _panel("CombatHud",
		Vector2(-COMBAT_PANEL_SIZE.x * 0.5, 64.0), COMBAT_PANEL_SIZE,
		Control.PRESET_CENTER_TOP)
	combat_panel.gui_input.connect(_on_combat_gui_input)
	var combat_box := VBoxContainer.new()
	combat_box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	combat_box.add_theme_constant_override("separation", 1)
	combat_panel.add_child(combat_box)
	combat_target = Label.new()
	combat_target.name = "CombatTarget"
	combat_target.mouse_filter = Control.MOUSE_FILTER_IGNORE
	combat_target.add_theme_font_size_override("font_size", COMBAT_FONT_SIZE)
	combat_target.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	combat_box.add_child(combat_target)
	combat_target_bar = _bar("CombatTargetBar", Color(0.82, 0.32, 0.28))
	combat_target_bar.custom_minimum_size = Vector2(0.0, 9.0)
	combat_target_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	combat_box.add_child(combat_target_bar)
	combat_player_bar = _bar("CombatPlayerBar", Color(0.36, 0.72, 0.42))
	combat_player_bar.custom_minimum_size = Vector2(0.0, 9.0)
	combat_player_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	combat_box.add_child(combat_player_bar)
	combat_event = Label.new()
	combat_event.name = "CombatEvent"
	combat_event.mouse_filter = Control.MOUSE_FILTER_IGNORE
	combat_event.add_theme_font_size_override("font_size", COMBAT_FONT_SIZE)
	combat_event.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	combat_box.add_child(combat_event)
	combat_menu = PopupMenu.new()
	combat_menu.name = "CombatHudMenu"
	combat_menu.add_check_item(tr("ELORIA_COMBAT_HUD_PIN"), 0)
	combat_menu.add_item(tr("ELORIA_COMBAT_HUD_HIDE"), 1)
	combat_menu.id_pressed.connect(_on_combat_menu_pressed)
	combat_panel.add_child(combat_menu)

	events_panel = _panel("SpecialEvents", Vector2(12.0, 120.0),
		Vector2(300.0, 120.0), Control.PRESET_TOP_LEFT)
	events_text = RichTextLabel.new()
	events_text.name = "SpecialEventsText"
	events_text.fit_content = true
	events_panel.add_child(events_text)

	quest_panel = _window("QuestJournal", "QUEST JOURNAL")
	quest_panel.custom_minimum_size = QUEST_JOURNAL_SIZE
	quest_panel.size = QUEST_JOURNAL_SIZE
	quest_panel.position = Vector2(24.0,
		(720.0 - QUEST_JOURNAL_SIZE.y) * 0.5)
	quest_panel.set_meta(&"visual_style", "eloria_field_journal")
	var quest_backdrop := ColorRect.new()
	quest_backdrop.name = "JournalBackdrop"
	quest_backdrop.color = Color(0.035, 0.03, 0.027, 0.985)
	quest_backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	quest_panel.add_child(quest_backdrop)
	quest_panel.move_child(quest_backdrop, 0)
	var quest_header := _window_body(quest_panel).get_node("Header") as HBoxContainer
	var quest_close := quest_header.get_node("Close") as Button
	quest_count = Label.new()
	quest_count.name = "QuestCount"
	quest_count.text = "0 ACTIVE"
	quest_count.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	quest_count.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	quest_header.add_child(quest_count)
	quest_header.move_child(quest_count, quest_close.get_index())
	var quest_views := HBoxContainer.new()
	quest_views.name = "QuestViews"
	quest_views.alignment = BoxContainer.ALIGNMENT_CENTER
	quest_views.add_theme_constant_override("separation", 8)
	_window_body(quest_panel).add_child(quest_views)
	quest_active_button = Button.new()
	quest_active_button.name = "QuestActive"
	quest_active_button.text = "Active"
	quest_active_button.toggle_mode = true
	quest_active_button.button_pressed = true
	quest_active_button.pressed.connect(_on_quest_view.bind(false))
	quest_views.add_child(quest_active_button)
	quest_done_button = Button.new()
	quest_done_button.name = "QuestDone"
	quest_done_button.text = "Completed (0)"
	quest_done_button.toggle_mode = true
	quest_done_button.pressed.connect(_on_quest_view.bind(true))
	quest_views.add_child(quest_done_button)
	var quest_columns := VBoxContainer.new()
	quest_columns.name = "QuestColumns"
	quest_columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_columns.add_theme_constant_override("separation", 10)
	_window_body(quest_panel).add_child(quest_columns)
	quest_list = ItemList.new()
	quest_list.name = "QuestList"
	quest_list.custom_minimum_size = Vector2(0.0, 170.0)
	quest_list.item_selected.connect(_on_quest_selected)
	quest_columns.add_child(quest_list)
	var quest_side := VBoxContainer.new()
	quest_side.name = "QuestDetailSide"
	quest_side.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_side.add_theme_constant_override("separation", 8)
	quest_columns.add_child(quest_side)
	var quest_record_heading := Label.new()
	quest_record_heading.name = "QuestRecordHeading"
	quest_record_heading.text = "ADVENTURER'S RECORD"
	quest_side.add_child(quest_record_heading)
	var quest_parchment := PanelContainer.new()
	quest_parchment.name = "QuestParchment"
	quest_parchment.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	quest_parchment.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_side.add_child(quest_parchment)
	var quest_parchment_surface := PanelContainer.new()
	quest_parchment_surface.name = "ParchmentTexture"
	quest_parchment_surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	quest_parchment_surface.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_parchment.add_child(quest_parchment_surface)
	quest_detail = RichTextLabel.new()
	quest_detail.name = "QuestDetail"
	quest_detail.bbcode_enabled = true
	quest_detail.scroll_active = true
	quest_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	quest_detail.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	quest_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_parchment_surface.add_child(quest_detail)
	quest_track_button = Button.new()
	quest_track_button.name = "QuestTrack"
	quest_track_button.text = "Track"
	quest_track_button.pressed.connect(_on_quest_track_pressed)
	quest_side.add_child(quest_track_button)
	_style_quest_journal(quest_views, quest_parchment,
		quest_parchment_surface, quest_record_heading)

	# This is a pinned HUD note, not another modal window. It sits immediately
	# left of the fixed 96-pixel resource rail and leaves the centre view clear.
	tracked_quest = _panel("TrackedQuest",
		Vector2(-RESERVED_RIGHT_RAIL - QUEST_TRACKER_SIZE.x - 12.0, 18.0),
		QUEST_TRACKER_SIZE, Control.PRESET_TOP_RIGHT)
	tracked_quest.z_index = 20
	tracked_quest.clip_contents = true
	tracked_quest.set_meta(&"visual_style", "eloria_quest_tracker")
	var tracker_parchment := PanelContainer.new()
	tracker_parchment.name = "TrackerParchment"
	tracker_parchment.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tracker_parchment.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tracked_quest.add_child(tracker_parchment)
	var tracker_parchment_surface := PanelContainer.new()
	tracker_parchment_surface.name = "ParchmentTexture"
	tracker_parchment_surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tracker_parchment_surface.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tracker_parchment.add_child(tracker_parchment_surface)
	tracked_quest_text = RichTextLabel.new()
	tracked_quest_text.name = "TrackedQuestText"
	tracked_quest_text.bbcode_enabled = true
	tracked_quest_text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tracked_quest_text.scroll_active = false
	tracked_quest_text.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tracked_quest_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tracker_parchment_surface.add_child(tracked_quest_text)
	_style_quest_tracker(tracker_parchment, tracker_parchment_surface)

	mail_panel = _window("MailWindow", "Mail")
	var mail_columns := HSplitContainer.new()
	mail_columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_window_body(mail_panel).add_child(mail_columns)
	mail_list = ItemList.new()
	mail_list.name = "MailList"
	mail_list.custom_minimum_size = Vector2(240.0, 0.0)
	mail_list.item_selected.connect(_on_mail_selected)
	mail_columns.add_child(mail_list)
	mail_body = RichTextLabel.new()
	mail_body.name = "MailBody"
	mail_body.bbcode_enabled = true
	mail_columns.add_child(mail_body)

	detail_panel = _window("ItemDetail", "Item")
	detail_text = RichTextLabel.new()
	detail_text.name = "ItemDetailText"
	detail_text.bbcode_enabled = true
	detail_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_window_body(detail_panel).add_child(detail_text)

	_build_merchant_window()

	market_panel = _window("MarketplaceWindow", "Nymara Exchange")
	var market_body: VBoxContainer = _window_body(market_panel)
	market_header = Label.new()
	market_header.name = "MarketplaceHeader"
	market_body.add_child(market_header)
	market_list = ItemList.new()
	market_list.name = "MarketplaceList"
	market_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	market_body.add_child(market_list)
	var market_actions := HBoxContainer.new()
	market_body.add_child(market_actions)
	for view: String in ["browse", "mine"]:
		var view_button := Button.new()
		view_button.name = "Marketplace" + view.capitalize()
		view_button.text = view.capitalize()
		view_button.pressed.connect(_on_market_view.bind(view))
		market_actions.add_child(view_button)
	var buy := Button.new()
	buy.name = "MarketplaceBuy"
	buy.text = "Buy listing"
	buy.pressed.connect(_on_market_buy)
	market_actions.add_child(buy)
	var collect := Button.new()
	collect.name = "MarketplaceCollect"
	collect.text = "Collect escrow"
	collect.pressed.connect(_on_market_collect)
	market_actions.add_child(collect)
	market_status = Label.new()
	market_status.name = "MarketplaceStatus"
	market_body.add_child(market_status)

	party_panel = _window("PartyWindow", "Party")
	var party_body: VBoxContainer = _window_body(party_panel)
	party_header = Label.new()
	party_header.name = "PartyHeader"
	party_body.add_child(party_header)
	party_invite_row = HBoxContainer.new()
	party_invite_row.name = "PartyInvite"
	party_invite_row.hide()
	party_body.add_child(party_invite_row)
	party_invite_label = Label.new()
	party_invite_label.name = "PartyInviteLabel"
	party_invite_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	party_invite_row.add_child(party_invite_label)
	var accept := Button.new()
	accept.name = "PartyAccept"
	accept.text = "Accept"
	accept.pressed.connect(_on_party_accept)
	party_invite_row.add_child(accept)
	var decline := Button.new()
	decline.name = "PartyDecline"
	decline.text = "Decline"
	decline.pressed.connect(_on_party_decline)
	party_invite_row.add_child(decline)
	var party_scroll := ScrollContainer.new()
	party_scroll.name = "PartyScroll"
	party_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	party_body.add_child(party_scroll)
	party_rows = VBoxContainer.new()
	party_rows.name = "PartyMembers"
	party_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	party_scroll.add_child(party_rows)
	var party_actions := HBoxContainer.new()
	party_body.add_child(party_actions)
	party_leave_button = Button.new()
	party_leave_button.name = "PartyLeave"
	party_leave_button.text = "Leave party"
	party_leave_button.pressed.connect(_on_party_leave)
	party_actions.add_child(party_leave_button)
	# Inviting needs a name, and a name needs typing; the chat command already
	# reads well, so the window points at it rather than growing a text field
	# that would duplicate it.
	var party_hint := Label.new()
	party_hint.name = "PartyHint"
	party_hint.text = "  #party invite <name>   ·   #p <message>"
	party_actions.add_child(party_hint)
	party_status = Label.new()
	party_status.name = "PartyStatus"
	party_body.add_child(party_status)
	party_panel.hide()

	# The achievement catalogue. Server-stated end to end: the pages are
	# whatever categories the catalogue file has in it, and so are the names,
	# the descriptions, the thresholds and the titles. Nothing here is a table
	# of this client's own, so nothing here can go stale when one moves.
	achievements_panel = _window("Achievements", "Achievements")
	var achievements_body: VBoxContainer = _window_body(achievements_panel)
	achievements_header = Label.new()
	achievements_header.name = "AchievementsHeader"
	achievements_body.add_child(achievements_header)
	var achievements_title_row := HBoxContainer.new()
	achievements_title_row.name = "TitleRow"
	achievements_body.add_child(achievements_title_row)
	var achievements_title_label := Label.new()
	achievements_title_label.name = "TitleLabel"
	achievements_title_label.text = "Title:"
	achievements_title_row.add_child(achievements_title_label)
	achievements_title_picker = OptionButton.new()
	achievements_title_picker.name = "TitlePicker"
	achievements_title_picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	achievements_title_picker.item_selected.connect(_on_achievement_title_chosen)
	achievements_title_row.add_child(achievements_title_picker)
	achievements_tabs = HBoxContainer.new()
	achievements_tabs.name = "AchievementsTabs"
	achievements_tabs.alignment = BoxContainer.ALIGNMENT_CENTER
	achievements_body.add_child(achievements_tabs)
	var achievements_scroll := ScrollContainer.new()
	achievements_scroll.name = "AchievementsScroll"
	achievements_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	achievements_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	achievements_body.add_child(achievements_scroll)
	achievements_rows = VBoxContainer.new()
	achievements_rows.name = "AchievementsBody"
	achievements_rows.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	achievements_scroll.add_child(achievements_rows)
	achievements_status = Label.new()
	achievements_status.name = "AchievementsStatus"
	achievements_body.add_child(achievements_status)
	achievements_panel.hide()

## Low-cost, retained quest chrome. The two source textures are preloaded once,
## and these StyleBoxes are built once with the windows; tracking a quest only
## changes label text and visibility, so a busy scene pays no repeating
## decoration cost.
func _quest_box(background: Color, border: Color, width: int,
		corner: int, margin: float) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = background
	box.border_color = border
	box.set_border_width_all(width)
	box.set_corner_radius_all(corner)
	box.set_content_margin_all(margin)
	return box

func _quest_texture_box(texture: Texture2D, margin: float,
		modulation := Color.WHITE) -> StyleBoxTexture:
	var box := StyleBoxTexture.new()
	box.texture = texture
	box.modulate_color = modulation
	box.set_content_margin_all(margin)
	return box

func _style_quest_button(button: Button, primary: bool) -> void:
	var normal_background := QUEST_BURGUNDY if primary else QUEST_STONE
	var hover_background := QUEST_BURGUNDY_HOVER if primary else QUEST_STONE_RAISED
	var normal := _quest_box(normal_background, QUEST_BRASS, 2, 9, 7.0)
	var hover := _quest_box(hover_background, QUEST_BRASS_BRIGHT, 3, 10, 7.0)
	var pressed := _quest_box(QUEST_BURGUNDY, QUEST_BRASS_BRIGHT, 3, 8, 7.0)
	var disabled := _quest_box(Color(0.09, 0.08, 0.07, 0.92),
		Color(0.3, 0.27, 0.22, 0.9), 1, 9, 7.0)
	for raised: StyleBoxFlat in [normal, hover, disabled]:
		raised.border_blend = true
		raised.shadow_color = Color(0.015, 0.01, 0.008, 0.88)
		raised.shadow_size = 3
		raised.shadow_offset = Vector2(0.0, 2.0)
	pressed.border_blend = true
	pressed.shadow_color = Color(0.015, 0.01, 0.008, 0.82)
	pressed.shadow_size = 1
	pressed.shadow_offset = Vector2(0.0, 1.0)
	button.add_theme_stylebox_override("normal", normal)
	button.add_theme_stylebox_override("hover", hover)
	button.add_theme_stylebox_override("pressed", pressed)
	button.add_theme_stylebox_override("hover_pressed", pressed)
	button.add_theme_stylebox_override("focus", hover)
	button.add_theme_stylebox_override("disabled", disabled)
	button.add_theme_color_override("font_color", QUEST_WARM_TEXT)
	button.add_theme_color_override("font_hover_color", QUEST_BRASS_BRIGHT)
	button.add_theme_color_override("font_pressed_color", QUEST_BRASS_BRIGHT)
	button.add_theme_color_override("font_disabled_color", QUEST_MUTED_TEXT)
	button.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
	button.add_theme_constant_override("outline_size", 2)
	button.custom_minimum_size.y = maxf(button.custom_minimum_size.y, 38.0)

func _style_quest_journal(quest_views: HBoxContainer,
		parchment: PanelContainer, parchment_surface: PanelContainer,
		record_heading: Label) -> void:
	# The transparent centre of the carved frame reveals JournalBackdrop while
	# its opaque perimeter supplies all of the tactile stone and aged brass.
	var frame := _quest_texture_box(QUEST_CARVED_FRAME_TEXTURE, 56.0)
	quest_panel.add_theme_stylebox_override("panel", frame)
	var body := _window_body(quest_panel)
	body.add_theme_constant_override("separation", 10)
	var header := body.get_node("Header") as HBoxContainer
	header.add_theme_constant_override("separation", 10)
	var title := header.get_node("Title") as Label
	title.add_theme_color_override("font_color", QUEST_BRASS_BRIGHT)
	title.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.95))
	title.add_theme_constant_override("outline_size", 3)
	title.add_theme_font_size_override("font_size", 22)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	quest_count.add_theme_color_override("font_color", QUEST_BRASS_BRIGHT)
	quest_count.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.95))
	quest_count.add_theme_constant_override("outline_size", 2)
	quest_count.add_theme_font_size_override("font_size", 12)
	quest_count.custom_minimum_size.x = 92.0
	_style_quest_button(header.get_node("Close") as Button, true)
	for child: Node in quest_views.get_children():
		if child is Button:
			var tab := child as Button
			tab.custom_minimum_size.x = 142.0
			tab.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			_style_quest_button(tab, false)
	var list_panel := _quest_box(Color(0.055, 0.05, 0.048, 0.98),
		QUEST_BRASS, 2, 3, 8.0)
	quest_list.add_theme_stylebox_override("panel", list_panel)
	var selected := _quest_box(QUEST_BURGUNDY, QUEST_BRASS_BRIGHT, 2, 2, 4.0)
	for state: String in ["cursor", "cursor_unfocused", "selected",
			"selected_focus", "hovered_selected"]:
		quest_list.add_theme_stylebox_override(state, selected)
	quest_list.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	quest_list.add_theme_color_override("font_color", QUEST_WARM_TEXT)
	quest_list.add_theme_color_override("font_selected_color", QUEST_BRASS_BRIGHT)
	quest_list.add_theme_color_override("font_hovered_selected_color",
		QUEST_BRASS_BRIGHT)
	quest_list.add_theme_color_override("guide_color", Color(QUEST_BRASS, 0.22))
	quest_list.add_theme_font_size_override("font_size", 14)
	quest_list.add_theme_constant_override("line_separation", 8)
	record_heading.add_theme_color_override("font_color", QUEST_BRASS_BRIGHT)
	record_heading.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
	record_heading.add_theme_constant_override("outline_size", 2)
	record_heading.add_theme_font_size_override("font_size", 12)
	var page := _quest_box(Color(0.14, 0.075, 0.025, 1.0),
		QUEST_PARCHMENT_DARK, 2, 5, 4.0)
	page.shadow_color = Color(0.0, 0.0, 0.0, 0.38)
	page.shadow_size = 5
	page.shadow_offset = Vector2(0.0, 3.0)
	parchment.add_theme_stylebox_override("panel", page)
	parchment_surface.add_theme_stylebox_override("panel",
		_quest_texture_box(QUEST_PARCHMENT_TEXTURE, 14.0,
			Color(0.94, 0.88, 0.76, 1.0)))
	quest_detail.add_theme_color_override("default_color", QUEST_INK)
	quest_detail.add_theme_color_override("font_selected_color", QUEST_INK)
	quest_detail.add_theme_color_override("selection_color", Color(0.55, 0.35, 0.12, 0.28))
	quest_detail.add_theme_font_size_override("normal_font_size", 15)
	_style_quest_button(quest_track_button, true)
	quest_track_button.custom_minimum_size.x = 154.0
	quest_track_button.size_flags_horizontal = Control.SIZE_SHRINK_END

func _style_quest_tracker(parchment: PanelContainer,
		parchment_surface: PanelContainer) -> void:
	# The pinned tracker is the torn page from the larger journal, not another
	# heavy window. The parchment itself supplies the edge and small shadow.
	tracked_quest.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	var page := _quest_box(Color(0.14, 0.075, 0.025, 0.98),
		QUEST_PARCHMENT_DARK, 2, 5, 3.0)
	page.shadow_color = Color(0.0, 0.0, 0.0, 0.62)
	page.shadow_size = 6
	page.shadow_offset = Vector2(0.0, 3.0)
	parchment.add_theme_stylebox_override("panel", page)
	parchment_surface.add_theme_stylebox_override("panel",
		_quest_texture_box(QUEST_PARCHMENT_TEXTURE, 9.0,
			Color(0.96, 0.90, 0.78, 0.985)))
	tracked_quest_text.add_theme_color_override("default_color", QUEST_INK)
	tracked_quest_text.add_theme_font_size_override("normal_font_size", 13)

## Two inventories share one explicit transaction, matching the selected concept.
func _build_merchant_window() -> void:
	merchant_panel = _window("MerchantWindow", "Merchant")
	merchant_panel.custom_minimum_size = Vector2(1040.0, 550.0)
	merchant_panel.size = merchant_panel.custom_minimum_size
	merchant_panel.position = Vector2(72.0, 65.0)
	merchant_panel.add_theme_stylebox_override("panel", _quest_box(Color("15120f"), Color("9a7843"), 1, 3, 12.0))
	var body := _window_body(merchant_panel)
	body.add_theme_constant_override("separation", 10)
	var header := body.get_node("Header") as HBoxContainer
	(header.get_node("Title") as Label).hide()
	merchant_header = Label.new()
	merchant_header.name = "MerchantHeader"
	merchant_header.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	merchant_header.add_theme_font_size_override("font_size", 18)
	header.add_child(merchant_header)
	header.move_child(merchant_header, 0)
	var columns := HBoxContainer.new()
	columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	columns.add_theme_constant_override("separation", 12)
	body.add_child(columns)
	for selling: bool in [false, true]:
		var panel := PanelContainer.new()
		panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		panel.size_flags_stretch_ratio = 1.0
		panel.add_theme_stylebox_override("panel", _quest_box(Color("1c1813"), Color("76603b"), 1, 2, 10.0))
		columns.add_child(panel)
		var column := VBoxContainer.new()
		panel.add_child(column)
		var mode := Button.new()
		mode.name = "MerchantSellMode" if selling else "MerchantBuyMode"
		mode.text = "Your backpack" if selling else "Shop goods"
		mode.toggle_mode = true
		mode.alignment = HORIZONTAL_ALIGNMENT_LEFT
		mode.add_theme_font_size_override("font_size", 19)
		mode.pressed.connect(_on_merchant_mode.bind("sell" if selling else "buy"))
		column.add_child(mode)
		var hint := Label.new()
		hint.text = "Select an item to sell · sell price" if selling else "Select an item to buy · buy price"
		hint.add_theme_font_size_override("font_size", 13)
		column.add_child(hint)
		var list := ItemList.new()
		list.name = "MerchantBackpack" if selling else "MerchantList"
		list.size_flags_vertical = Control.SIZE_EXPAND_FILL
		list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		list.fixed_icon_size = Vector2i(40, 40)
		list.icon_scale = 1.0
		list.add_theme_constant_override("icon_margin", 12)
		list.add_theme_font_size_override("font_size", 15)
		list.add_theme_color_override("font_color", QUEST_WARM_TEXT)
		list.add_theme_color_override("font_selected_color", QUEST_WARM_TEXT)
		list.add_theme_constant_override("v_separation", 7)
		list.add_theme_stylebox_override("panel", _quest_box(Color("151310"), Color("76603b"), 0, 0, 4.0))
		list.add_theme_stylebox_override("selected", _quest_box(Color("40331e"), Color("c59a53"), 1, 2, 3.0))
		list.add_theme_stylebox_override("selected_focus", _quest_box(Color("40331e"), Color("c59a53"), 1, 2, 3.0))
		list.item_selected.connect(_on_merchant_selected.bind("sell" if selling else "buy"))
		column.add_child(list)
		if selling:
			merchant_sell_mode = mode
			merchant_sell_list = list
			merchant_empty_pack = Label.new()
			merchant_empty_pack.text = "No items this merchant buys in your backpack."
			merchant_empty_pack.add_theme_font_size_override("font_size", 13)
			column.add_child(merchant_empty_pack)
		else:
			merchant_buy_mode = mode
			merchant_buy_list = list
	merchant_list = merchant_buy_list
	var footer := HBoxContainer.new()
	footer.add_theme_constant_override("separation", 14)
	body.add_child(footer)
	merchant_selected_icon = TextureRect.new()
	merchant_selected_icon.custom_minimum_size = Vector2(48, 48)
	merchant_selected_icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	merchant_selected_icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	footer.add_child(merchant_selected_icon)
	merchant_selection = Label.new()
	merchant_selection.name = "MerchantSelection"
	merchant_selection.custom_minimum_size.x = 250
	merchant_selection.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	merchant_selection.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	footer.add_child(merchant_selection)
	var quantities := VBoxContainer.new()
	footer.add_child(quantities)
	var quantity_label := Label.new()
	quantity_label.text = "Quantity"
	quantities.add_child(quantity_label)
	var stepper := HBoxContainer.new()
	quantities.add_child(stepper)
	var minus := Button.new()
	minus.text = "−"
	minus.pressed.connect(_merchant_change_quantity.bind(-1))
	stepper.add_child(minus)
	merchant_quantity = LineEdit.new()
	merchant_quantity.name = "MerchantQuantity"
	merchant_quantity.text = "1"
	merchant_quantity.custom_minimum_size.x = 80
	merchant_quantity.alignment = HORIZONTAL_ALIGNMENT_CENTER
	merchant_quantity.text_changed.connect(_sync_merchant_summary)
	stepper.add_child(merchant_quantity)
	var plus := Button.new()
	plus.text = "+"
	plus.pressed.connect(_merchant_change_quantity.bind(1))
	stepper.add_child(plus)
	var maximum := Button.new()
	maximum.name = "MerchantMaximum"
	maximum.text = "Max"
	maximum.pressed.connect(_merchant_set_maximum)
	stepper.add_child(maximum)
	merchant_totals = Label.new()
	merchant_totals.name = "MerchantTotals"
	merchant_totals.custom_minimum_size.x = 170
	footer.add_child(merchant_totals)
	merchant_trade = Button.new()
	merchant_trade.name = "MerchantTrade"
	merchant_trade.text = "Buy"
	merchant_trade.custom_minimum_size = Vector2(112, 44)
	merchant_trade.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	merchant_trade.add_theme_stylebox_override("normal", _quest_box(Color("5d4320"), Color("d5aa60"), 1, 3, 9.0))
	merchant_trade.add_theme_stylebox_override("hover", _quest_box(Color("77552a"), Color("ebc982"), 1, 3, 9.0))
	merchant_trade.pressed.connect(_on_merchant_trade)
	footer.add_child(merchant_trade)
	merchant_status = Label.new()
	merchant_status.name = "MerchantStatus"
	merchant_status.add_theme_font_size_override("font_size", 13)
	body.add_child(merchant_status)

func _bar(bar_name: String, colour: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.name = bar_name
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(0.0, 14.0)
	var fill := StyleBoxFlat.new()
	fill.bg_color = colour
	bar.add_theme_stylebox_override("fill", fill)
	return bar

func _panel(panel_name: String, offset: Vector2, size: Vector2,
		preset: int) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.name = panel_name
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.set_anchors_preset(preset)
	panel.position = offset
	panel.custom_minimum_size = size
	panel.size = size
	panel.hide()
	add_child(panel)
	return panel

## A centred window with a title row and a close button. Kept clear of the
## fixed right-hand resource rail, which nothing may cover.
func _window(window_name: String, title: String) -> PanelContainer:
	var available: float = 1280.0 - RESERVED_RIGHT_RAIL
	var panel := _panel(window_name,
		Vector2((available - PANEL_SIZE.x) * 0.5, (720.0 - PANEL_SIZE.y) * 0.5),
		PANEL_SIZE, Control.PRESET_TOP_LEFT)
	panel.z_index = 26
	var body := VBoxContainer.new()
	body.name = "Body"
	panel.add_child(body)
	var header := HBoxContainer.new()
	header.name = "Header"
	body.add_child(header)
	WindowDrag.attach(panel, header)
	var title_label := Label.new()
	title_label.name = "Title"
	title_label.text = title
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(title_label)
	var close := Button.new()
	close.name = "Close"
	close.text = "Close"
	close.pressed.connect(func() -> void:
		if panel == merchant_panel:
			AppState.close_merchant()
		elif panel == market_panel:
			AppState.close_marketplace()
		elif panel == detail_panel:
			AppState.close_item_detail()
		else:
			panel.hide())
	header.add_child(close)
	return panel

func _window_body(panel: PanelContainer) -> VBoxContainer:
	return panel.get_node("Body") as VBoxContainer
