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
## would make it unreadable. The layout is deliberately plain: these are data
## windows, and the artwork budget belongs to the world.

const RESERVED_RIGHT_RAIL := 96.0
const PANEL_SIZE := Vector2(560.0, 380.0)
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
var merchant_quantity: OptionButton
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

# The quantity ladder the server offers for a shop trade, and the response ids
# that drive one. These are the legacy dialogue response ids; a client with
# merchant_window_v1 sends them without the dialogue ever being drawn.
const SHOP_QUANTITIES: Array[int] = [1, 5, 10, 20, 50, 100, 200, 500, 1000]
const SHOP_BUY_ITEM := 3100
const SHOP_SELL_ITEM := 3200
const SHOP_QUANTITY := 3300
const SHOP_MAX := SHOP_QUANTITY + 9

var _merchant_mode := "buy"
## The quest the player asked to keep on screen, by its title. Which quest to
## watch is the player's choice about their own screen, so it is kept here;
## everything shown about it is the server's own journal entry, restated on
## every 224, and a tracked quest the server stops sending simply stops being
## tracked.
var _tracked_quest_title := ""

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

## Cancel order: the windows the server opened come first, because they are the
## ones the player did not choose to have on screen.
func _cascade() -> Array[PanelContainer]:
	# The tracked-quest readout is deliberately absent: it is a HUD element the
	# player pinned, not a window covering the screen, so cancel leaves it be.
	return [merchant_panel, market_panel, detail_panel, mail_panel,
		quest_panel, party_panel]

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
		quest_list.add_item("%s  [%s]" % [str(entry.get("title", "")), status])
	if AppState.quest_journal.is_empty():
		quest_detail.text = "[center]%s[/center]" % tr("ELORIA_QUEST_NONE")
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
		quest_list.add_item("%s  [%s]" % [str(entry.get("title", "")),
			str(entry.get("location", ""))])
	quest_track_button.disabled = true
	if AppState.quest_archive.is_empty():
		quest_detail.text = "[center]You have not finished any quests yet.[/center]"
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
		tracked_quest.hide()
		quest_track_button.text = "Track"
		return
	var target: int = int(tracked.get("target", 0))
	var lines: Array[String] = ["[b]%s[/b]" % str(tracked.get("title", ""))]
	lines.append(str(tracked.get("objective", "")))
	if bool(tracked.get("ready", false)):
		lines.append("[color=#8fdc8f]Ready to turn in at %s[/color]"
			% str(tracked.get("location", "unknown")))
	elif target > 0:
		lines.append("%d of %d  -  %s" % [int(tracked.get("current", 0)),
			target, str(tracked.get("location", "unknown"))])
	else:
		lines.append(str(tracked.get("location", "unknown")))
	tracked_quest_text.text = "\n".join(lines)
	tracked_quest.show()

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
	quest_detail.text = "[b]%s[/b]\n[i]%s[/i]\n\n%s" % [
		str(entry.get("title", "")), str(entry.get("location", "")),
		str(entry.get("detail", ""))]

func _show_quest(index: int) -> void:
	if index < 0 or index >= AppState.quest_journal.size():
		return
	var entry: Dictionary = AppState.quest_journal[index]
	var target: int = int(entry.get("target", 0))
	var lines: Array[String] = ["[b]%s[/b]" % str(entry.get("title", ""))]
	lines.append(str(entry.get("objective", "")))
	lines.append("Location: %s" % str(entry.get("location", "unknown")))
	if bool(entry.get("ready", false)):
		lines.append("[color=#8fdc8f]%s[/color]" % tr("ELORIA_QUEST_READY"))
	elif target > 0:
		lines.append("Progress: %d of %d" % [int(entry.get("current", 0)), target])
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
		return
	merchant_header.text = "%s  -  %d gold  -  load %d/%d" % [
		str(AppState.merchant.get("npc_name", "Merchant")),
		int(AppState.merchant.get("gold", 0)),
		int(AppState.merchant.get("carried", 0)),
		int(AppState.merchant.get("capacity", 0))]
	var selected: int = _selected_index(merchant_list)
	merchant_list.clear()
	for entry: Dictionary in AppState.merchant.get("items", []) as Array:
		var price: int = int(entry.get("buy_price" if _merchant_mode == "buy"
			else "sell_price", 0))
		var index: int = merchant_list.item_count
		merchant_list.add_item("%s  -  %d gc  (you have %d)" % [
			str(entry.get("name", "")), price, int(entry.get("owned", 0))])
		merchant_list.set_item_metadata(index, int(entry.get("index", index)))
		if item_atlas != null:
			var icon: Texture2D = item_atlas.icon_for(int(entry.get("image_id", 0)))
			if icon != null:
				merchant_list.set_item_icon(index, icon)
	if merchant_list.item_count > 0:
		merchant_list.select(clampi(selected, 0, merchant_list.item_count - 1))
	merchant_panel.show()
	merchant_panel.move_to_front()

func _on_merchant_mode(mode: String) -> void:
	_merchant_mode = mode
	_sync_merchant()

## A shop trade is two authoritative steps: choose the item, then the quantity.
## The dialogue response ids are the same ones the legacy menu used; with
## merchant_window_v1 the server answers with an updated window instead of a
## dialogue, so the menu is never drawn.
func _on_merchant_trade() -> void:
	var actor_id: int = int(AppState.merchant.get("actor_id", -1))
	var selected: PackedInt32Array = merchant_list.get_selected_items()
	if actor_id < 0 or selected.is_empty():
		merchant_status.text = "Select an item first."
		return
	var item_index: int = int(merchant_list.get_item_metadata(int(selected[0])))
	var base: int = SHOP_BUY_ITEM if _merchant_mode == "buy" else SHOP_SELL_ITEM
	var select_error: Error = Network.respond_to_npc(actor_id, base + item_index)
	if select_error != OK:
		merchant_status.text = "Merchant request failed: " + error_string(select_error)
		return
	var quantity_index: int = merchant_quantity.get_selected_id()
	var response: int = (SHOP_MAX if quantity_index < 0
		else SHOP_QUANTITY + quantity_index)
	var trade_error: Error = Network.respond_to_npc(actor_id, response)
	if trade_error != OK:
		merchant_status.text = "Merchant request failed: " + error_string(trade_error)
		return
	merchant_status.text = "Sent to the server; the window updates when it answers."

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
			var icon: Texture2D = item_atlas.icon_for(int(listing.get("image_id", 0)))
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

	quest_panel = _window("QuestJournal", "Quest journal")
	var quest_views := HBoxContainer.new()
	quest_views.name = "QuestViews"
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
	var quest_columns := HSplitContainer.new()
	quest_columns.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_window_body(quest_panel).add_child(quest_columns)
	quest_list = ItemList.new()
	quest_list.name = "QuestList"
	quest_list.custom_minimum_size = Vector2(240.0, 0.0)
	quest_list.item_selected.connect(_on_quest_selected)
	quest_columns.add_child(quest_list)
	var quest_side := VBoxContainer.new()
	quest_columns.add_child(quest_side)
	quest_detail = RichTextLabel.new()
	quest_detail.name = "QuestDetail"
	quest_detail.bbcode_enabled = true
	quest_detail.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_side.add_child(quest_detail)
	quest_track_button = Button.new()
	quest_track_button.name = "QuestTrack"
	quest_track_button.text = "Track"
	quest_track_button.pressed.connect(_on_quest_track_pressed)
	quest_side.add_child(quest_track_button)

	tracked_quest = _panel("TrackedQuest", Vector2(12.0, 250.0),
		Vector2(300.0, 96.0), Control.PRESET_TOP_LEFT)
	tracked_quest_text = RichTextLabel.new()
	tracked_quest_text.name = "TrackedQuestText"
	tracked_quest_text.bbcode_enabled = true
	tracked_quest_text.fit_content = true
	tracked_quest.add_child(tracked_quest_text)

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

	merchant_panel = _window("MerchantWindow", "Merchant")
	var merchant_body: VBoxContainer = _window_body(merchant_panel)
	merchant_header = Label.new()
	merchant_header.name = "MerchantHeader"
	merchant_body.add_child(merchant_header)
	merchant_list = ItemList.new()
	merchant_list.name = "MerchantList"
	merchant_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	merchant_body.add_child(merchant_list)
	var merchant_actions := HBoxContainer.new()
	merchant_body.add_child(merchant_actions)
	var buy_mode := Button.new()
	buy_mode.name = "MerchantBuyMode"
	buy_mode.text = "Buy"
	buy_mode.pressed.connect(_on_merchant_mode.bind("buy"))
	merchant_actions.add_child(buy_mode)
	var sell_mode := Button.new()
	sell_mode.name = "MerchantSellMode"
	sell_mode.text = "Sell"
	sell_mode.pressed.connect(_on_merchant_mode.bind("sell"))
	merchant_actions.add_child(sell_mode)
	merchant_quantity = OptionButton.new()
	merchant_quantity.name = "MerchantQuantity"
	for index: int in range(SHOP_QUANTITIES.size()):
		merchant_quantity.add_item(str(SHOP_QUANTITIES[index]), index)
	merchant_quantity.select(0)
	merchant_actions.add_child(merchant_quantity)
	var trade := Button.new()
	trade.name = "MerchantTrade"
	trade.text = "Trade"
	trade.pressed.connect(_on_merchant_trade)
	merchant_actions.add_child(trade)
	merchant_status = Label.new()
	merchant_status.name = "MerchantStatus"
	merchant_body.add_child(merchant_status)

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
