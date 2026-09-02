extends SceneTree
## Guards the nine Eloria extension windows.
##
## Each is driven by one server-push state packet and renders that snapshot and
## nothing else. Every payload below is the exact output of the server's own
## builder in eloria/protocol.py, so a window can only pass here if it is
## reading what the real server sends.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	var game_view: Control = main.get_node("GameView") as Control
	game_view.show()
	(main.get_node("LoginPanel") as Control).hide()
	var app_state: Node = root.get_node("/root/AppState")
	app_state.set("authenticated", true)
	var windows: Control = main.get("extension_windows") as Control
	var resource_rail: Control = main.get_node("GameView/ResourceHud") as Control
	if not _expect(windows != null, "the extension windows are built"):
		quit(failures)
		return
	await process_frame

	# Nothing is on screen until the server sends something.
	_expect(not windows.has_open_window(),
		"no extension window opens itself")
	_expect(not windows.navigation_label.visible
		and not windows.combat_panel.visible and not windows.events_panel.visible,
		"the always-on readouts stay hidden until the server reports state")

	# 230 navigation HUD.
	app_state.call("_on_packet", 230, _hex(
		"010203e1010c00666f75725f676174657300526565642062616e6b00"))
	await process_frame
	_expect(windows.navigation_label.visible
		and windows.navigation_label.text.contains("Reed bank")
		and windows.navigation_label.text.contains("770")
		and windows.navigation_label.text.contains("12"),
		"the navigation HUD names the waypoint, its tile and the distance: "
			+ windows.navigation_label.text)
	app_state.call("_on_packet", 230, _hex("000000000000000000"))
	await process_frame
	_expect(not windows.navigation_label.visible,
		"clearing the waypoint hides the navigation HUD rather than freezing it")

	# 227 combat HUD, including the defeat that ends the engagement.
	app_state.call("_on_packet", 227, _hex(
		"016600120014001e002c00050052656564686f726e205374616700"))
	await process_frame
	_expect(windows.combat_panel.visible
		and windows.combat_target.text == "Reedhorn Stag"
		and is_equal_approx(windows.combat_player_bar.value, 18.0)
		and is_equal_approx(windows.combat_player_bar.max_value, 20.0)
		and is_equal_approx(windows.combat_target_bar.value, 30.0)
		and is_equal_approx(windows.combat_target_bar.max_value, 44.0)
		and windows.combat_event.text.contains("5"),
		"the combat HUD shows both health bars and the outcome")
	app_state.call("_on_packet", 227, _hex(
		"046600120014000000 2c00000052656564686f726e205374616700".replace(" ", "")))
	await process_frame
	# The box reports a fight and then has nothing left to say, so a defeat
	# leaves it up for its hold and fades it rather than vanishing mid-blow.
	_expect(windows.combat_panel.visible,
		"a defeat leaves the last frame up for the box's hold")
	windows.set("_combat_expiry_msec",
		Time.get_ticks_msec() - windows.COMBAT_FADE_MSEC - 1)
	windows.call("_process", 0.0)
	_expect(not windows.combat_panel.visible
		and is_equal_approx(windows.combat_panel.modulate.a, 1.0),
		"the combat box fades out once its hold has run out")
	# Pinned, it stays regardless; dismissed, it does not come back until the
	# settings panel puts it back.
	windows.call("set_combat_hud_pinned", true)
	_expect(windows.combat_panel.visible,
		"pinning the combat box keeps it on screen")
	windows.call("set_combat_hud_enabled", false)
	_expect(not windows.combat_panel.visible,
		"dismissing the combat box from its own menu hides it")
	windows.call("set_combat_hud_enabled", true)
	windows.call("set_combat_hud_pinned", false)
	windows.combat_panel.hide()

	# 232 special events.
	app_state.call("_on_packet", 232, _hex(
		"4861727665737420666573746976616c0050686173652032206f66203300"))
	await process_frame
	_expect(windows.events_panel.visible
		and windows.events_text.text.contains("Harvest festival")
		and windows.events_text.text.contains("Phase 2 of 3"),
		"the special-event panel shows every line the server sent")
	app_state.call("_on_packet", 232, PackedByteArray([0]))
	await process_frame
	_expect(not windows.events_panel.visible,
		"an empty payload clears the panel rather than leaving stale text")

	# 224 quest journal.
	app_state.call("_on_packet", 224, _hex(
		"01000001000000030000004b696c6c205468656d20416c6c0044656665617420332"
		+ "07261747300466f757220476174657300"))
	await process_frame
	windows.toggle_quest_journal()
	await process_frame
	_expect(windows.quest_panel.visible and windows.quest_list.item_count == 1
		and windows.quest_list.get_item_text(0).contains("Kill Them All")
		and windows.quest_list.get_item_text(0).contains("1/3"),
		"the quest journal lists the entry with its progress")
	_expect(windows.quest_detail.text.contains("Defeat 3 rats")
		and windows.quest_detail.text.contains("Four Gates"),
		"selecting a quest shows its objective and location")

	# Tracking a quest. Which quest to watch is the player's own choice about
	# their screen; everything shown about it is the server's journal entry.
	_expect(not windows.tracked_quest.visible,
		"nothing is tracked until the player asks for it")
	windows._on_quest_track_pressed()
	await process_frame
	_expect(windows.tracked_quest.visible
		and windows.tracked_quest_text.text.contains("Kill Them All")
		and windows.tracked_quest_text.text.contains("Defeat 3 rats")
		and windows.tracked_quest_text.text.contains("1 of 3")
		and windows.tracked_quest_text.text.contains("Four Gates"),
		"the tracked readout states the quest, the objective and the progress")
	var tracked_rect: Rect2 = windows.tracked_quest.get_global_rect()
	_expect(tracked_rect.position.x >= 0.0 and tracked_rect.end.y <= 720.0
		and not tracked_rect.intersects(resource_rail.get_global_rect()),
		"the tracked readout fits 1280x720 clear of the resource rail")
	# The server restates the journal with the quest ready to turn in.
	app_state.call("_on_packet", 224, _hex(
		"01000103000000030000004b696c6c205468656d20416c6c00446566656174203"
		+ "3207261747300466f757220476174657300"))
	await process_frame
	_expect(windows.tracked_quest.visible
		and windows.tracked_quest_text.text.contains("Ready to turn in"),
		"the readout follows the server rather than the moment it was pinned")
	# A quest the server stops listing stops being tracked.
	app_state.call("_on_packet", 224, _hex("0000"))
	await process_frame
	_expect(not windows.tracked_quest.visible,
		"a quest the server no longer lists is no longer tracked")
	app_state.call("_on_packet", 224, _hex(
		"01000001000000030000004b696c6c205468656d20416c6c0044656665617420332"
		+ "07261747300466f757220476174657300"))
	await process_frame
	_expect(not windows.tracked_quest.visible,
		"the readout does not come back on its own when the quest returns")

	# 229 mail.
	app_state.call("_on_packet", 229, _hex(
		"01000300000000f1536500416c6963650048656c6c6f004d656574206d6520617420"
		+ "74686520676174652e00"))
	await process_frame
	windows.toggle_mail()
	await process_frame
	_expect(windows.mail_panel.visible and not windows.quest_panel.visible,
		"opening one window closes the other: they are mutually exclusive")
	_expect(windows.mail_list.item_count == 1
		and windows.mail_list.get_item_text(0).begins_with("*")
		and windows.mail_body.text.contains("Meet me at the gate."),
		"the inbox marks unread mail and shows the selected body")

	# 225 item detail, which the server opens rather than the player.
	app_state.call("_on_packet", 225, _hex(
		"a000020000000053756e6c656166005265736f75726365730000412070616c65206c"
		+ "6561662e00454d55203100477561726420436170650041726d6f757220322"
		+ "02d3e203000"))
	await process_frame
	_expect(windows.detail_panel.visible
		and windows.detail_text.text.contains("Sunleaf")
		and windows.detail_text.text.contains("A pale leaf.")
		and windows.detail_text.text.contains("Guard Cape")
		and windows.detail_text.text.contains("Armour 2 -> 0"),
		"item detail shows the description and the equipped-item comparison")

	# 223 merchant.
	app_state.call("_on_packet", 223, _hex(
		"5b00fa0000001400000050000000010053616c696e61000000280000000c00000005"
		+ "000000140053756e6c65616600"))
	await process_frame
	_expect(windows.merchant_panel.visible
		and windows.merchant_header.text.contains("Salina")
		and windows.merchant_header.text.contains("250")
		and windows.merchant_list.item_count == 1
		and windows.merchant_list.get_item_text(0).contains("40"),
		"the merchant window shows the NPC, the purse and the buy price")
	windows._on_merchant_mode("sell")
	await process_frame
	_expect(windows.merchant_list.get_item_text(0).contains("12"),
		"switching to sell shows the sell price instead")
	windows._on_merchant_mode("buy")

	# 222 marketplace.
	app_state.call("_on_packet", 222, _hex(
		"00fa000000030000000100070000000c0000002300000058020000140053756e6c65"
		+ "616600416c69636500"))
	await process_frame
	_expect(windows.market_panel.visible
		and windows.market_header.text.contains("250")
		and windows.market_header.text.contains("3")
		and windows.market_list.item_count == 1
		and windows.market_list.get_item_text(0).contains("Sunleaf")
		and windows.market_list.get_item_text(0).contains("Alice"),
		"the exchange shows gold, escrow and the listing")
	_expect(int(windows.market_list.get_item_metadata(0)) == 7,
		"a listing row carries the server's listing id, not its row index")

	# 241 the completed-quest archive: the half of the journal that answers
	# "what have I done", which no client-side log could survive a reinstall.
	windows.close_all()
	app_state.call("_on_packet", 241, _hex(
		"0200426567696e6e6572205475746f7269616c0049736c61205072696d6100596f75"
		+ "206c6561726e656420746f206d6f76652c2066696768742c2067617468657220616e"
		+ "64206d69782e00546865205765737465726e20526f6164004e796d6172610059"
		+ "6f752077616c6b65642074686520726f6164207765737420616e642063616d652062"
		+ "61636b2e00"))
	windows.toggle_quest_journal()
	await process_frame
	_expect(windows.quest_done_button.text.contains("2"),
		"the completed tab counts what the server says is finished")
	windows._on_quest_view(true)
	await process_frame
	_expect(windows.quest_list.item_count == 2
		and windows.quest_list.get_item_text(0).contains("Beginner Tutorial")
		and windows.quest_detail.text.contains("You learned to move")
		and windows.quest_track_button.disabled,
		"the completed view lists finished quests and cannot track them")
	windows._on_quest_view(false)
	await process_frame
	_expect(not windows.quest_done_button.button_pressed
		and windows.quest_active_button.button_pressed,
		"switching back to active leaves exactly one view selected")
	# Pressing the tab that is already down must not leave the window blank.
	windows._on_quest_view(false)
	await process_frame
	_expect(windows.quest_active_button.button_pressed,
		"pressing the selected tab keeps it selected")
	windows.close_all()

	# 240 party. The window's job is the member who is not on your screen, so
	# what matters is that an absent one is still drawn and still says so.
	app_state.call("_on_packet", 240, _hex(
		"0102037800b40028003c000003e0014b656c6c616e00666f75725f67617465730004"
		+ "5a0096000a0037009a00b6004d6172656e006d6972726f72686f6c6400000000"))
	await process_frame
	_expect(windows.party_panel.visible
		and windows.party_rows.get_child_count() == 2
		and windows.party_header.text.contains("1 of 2"),
		"the party window draws every member and counts who is online")
	var absent_row: Control = windows.party_rows.get_child(1) as Control
	_expect(_row_text(absent_row).contains("Maren")
		and _row_text(absent_row).contains("offline"),
		"an offline member keeps their row and is named as offline")
	var leader_row: Control = windows.party_rows.get_child(0) as Control
	_expect(_row_text(leader_row).contains("leader")
		and _row_text(leader_row).contains("four_gates"),
		"the leader is marked and their location is stated")
	var leader_health: ProgressBar = leader_row.get_node("Health") as ProgressBar
	_expect(is_equal_approx(leader_health.value, 120.0)
		and is_equal_approx(leader_health.max_value, 180.0),
		"a member's health bar reads the server's numbers")

	# An invitation with no party is a real state: the window has to appear to
	# carry the answer buttons, with nothing else in it.
	app_state.call("_on_packet", 240, _hex("00004b656c6c616e004b00"))
	await process_frame
	_expect(windows.party_panel.visible and windows.party_invite_row.visible
		and windows.party_invite_label.text.contains("Kellan")
		and windows.party_rows.get_child_count() == 0,
		"a pending invitation opens the window with no members in it")

	# And the party going away closes it rather than leaving a stale roster.
	app_state.call("_on_packet", 240, _hex("0000000000"))
	await process_frame
	_expect(not windows.party_panel.visible and not windows.party_invite_row.visible,
		"no party and no invitation hides the window")

	# Bounds and the fixed resource rail, for every window at once.
	for panel: PanelContainer in [windows.combat_panel, windows.events_panel,
			windows.quest_panel, windows.mail_panel, windows.detail_panel,
			windows.merchant_panel, windows.market_panel, windows.party_panel]:
		var was_visible: bool = panel.visible
		panel.show()
		await process_frame
		var rect: Rect2 = panel.get_global_rect()
		_expect(rect.position.x >= 0.0 and rect.position.y >= 0.0
			and rect.end.x <= 1280.0 and rect.end.y <= 720.0,
			"%s fits within 1280x720 (%s)" % [panel.name, rect])
		_expect(not rect.intersects(resource_rail.get_global_rect()),
			"%s does not cover the fixed resource rail" % panel.name)
		panel.visible = was_visible
	var navigation_rect: Rect2 = windows.navigation_label.get_global_rect()
	_expect(navigation_rect.end.x <= 1280.0
		and not navigation_rect.intersects(resource_rail.get_global_rect()),
		"the navigation readout stays clear of the resource rail")

	# The cancel cascade: server-opened windows first, then the player's own.
	windows.close_all()
	app_state.call("_on_packet", 224, _hex("0000"))
	windows.toggle_quest_journal()
	app_state.call("_on_packet", 225, _hex("00000000000000410042004300440045004600470"
		+ "0"))
	await process_frame
	_expect(windows.detail_panel.visible and windows.quest_panel.visible,
		"a server-opened window does not close one the player opened")
	var escape: InputEventKey = InputMap.action_get_events(
		"cancel")[0].duplicate() as InputEventKey
	escape.pressed = true
	main.call("_unhandled_input", escape)
	await process_frame
	_expect(not windows.detail_panel.visible and windows.quest_panel.visible,
		"cancel closes the server-opened window first")
	main.call("_unhandled_input", escape)
	await process_frame
	_expect(not windows.quest_panel.visible,
		"a second cancel closes the window the player opened")

	# Disconnecting clears every window rather than leaving another session's
	# state on screen.
	app_state.call("_on_packet", 223, _hex(
		"5b00fa0000001400000050000000010053616c696e61000000280000000c00000005"
		+ "000000140053756e6c65616600"))
	await process_frame
	_expect(windows.merchant_panel.visible, "the merchant window is open")
	app_state.call("_on_connection_state_changed", "disconnected")
	await process_frame
	_expect(not windows.has_open_window() and not windows.navigation_label.visible
		and not windows.combat_panel.visible and not windows.events_panel.visible,
		"a disconnect clears every extension window")

	print("extension window tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

## Every Label under one member row, joined. The row is built from several
## controls, so asserting against any single one of them would pin the layout
## rather than what the row says.
func _row_text(row: Control) -> String:
	var parts: PackedStringArray = PackedStringArray()
	for child: Node in row.get_children():
		if child is Label:
			parts.append((child as Label).text)
	return " ".join(parts)

func _hex(value: String) -> PackedByteArray:
	var bytes := PackedByteArray()
	for index: int in range(0, value.length(), 2):
		bytes.append(value.substr(index, 2).hex_to_int())
	return bytes

func _expect(value: bool, label: String) -> bool:
	if not value:
		failures += 1
		push_error("FAIL: " + label)
	return value
