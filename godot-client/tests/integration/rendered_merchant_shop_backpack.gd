extends SceneTree
## Production merchant interaction checks; set ELORIA_ARTIFACT_DIR for screenshots.

const SHOP := "5b00fa00000014000000500000000a0042657474616e79204f726c000000050000000200000003000000010042726561640001000a00000006000000020000000900436f6f6b6564204d65617400020005000000030000000c00000065005361676500030005000000010000000000000055005265656400040004000000010000000000000052024f6c6976650005000a000000040000000000000053024c656d6f6e000600050000000100000004000000f901456d707479205669616c0007001e0000000a000000000000000a00526177204d6561740008000a0000000300000002000000da01506f74696f6e206f66204d696e6f72204865616c696e6700090032000000140000000000000008004d6f7274617220616e6420506573746c65000a0001000000010000000100000001000000010000000100000001000000010000000100000001000000"

var failures := 0
var windows: Control

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main := (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await _settle()
	for name: String in ["LoginPanel", "LoginBackground", "CreationPanel", "ConnectionBanner"]:
		var panel := main.get_node_or_null("%" + name) as Control
		if panel != null:
			panel.hide()
	(main.get_node("GameView") as Control).show()
	var state := root.get_node("/root/AppState")
	state.set("authenticated", true)
	windows = main.get("extension_windows") as Control
	# Exact output of the server merchant_state builder using Bettany's stock.
	state.call("_on_packet", 223, SHOP.hex_decode())
	await _settle()
	_expect(windows.merchant_buy_list.item_count == 10, "all shop goods are visible")
	_expect(windows.merchant_sell_list.item_count == 5, "only owned goods the merchant buys appear in the backpack")
	windows.merchant_buy_list.select(8)
	windows._on_merchant_selected(8, "buy")
	windows.merchant_quantity.text = "3"
	windows._sync_merchant_summary()
	_expect(windows._merchant_trade_command() == "#shop buy 91 8 3", "buy retains the server item id")
	_expect(windows.merchant_totals.text.contains("Cost: 30 gc")
		and windows.merchant_totals.text.contains("Gold after: 220 gc")
		and windows.merchant_totals.text.contains("Carry after: 23/80"), "purchase previews cost, gold and load")
	_expect(not windows.merchant_trade.disabled, "an affordable purchase is enabled")
	await _capture("merchant-buy.png")
	windows._merchant_set_maximum()
	_expect(windows.merchant_quantity.text == "25", "buy Max is limited by gold")
	state.get("merchant")["capacity"] = 22
	windows._merchant_set_maximum()
	_expect(windows.merchant_quantity.text == "2", "buy Max also respects carrying space")
	windows.merchant_quantity.text = "3"
	windows._sync_merchant_summary()
	_expect(windows.merchant_trade.disabled, "an overweight purchase is disabled")
	state.get("merchant")["capacity"] = 80
	windows.merchant_sell_list.select(2)
	windows._on_merchant_selected(2, "sell")
	windows.merchant_quantity.text = "4"
	windows._sync_merchant_summary()
	_expect(windows._merchant_trade_command() == "#shop sell 91 2 4", "filtered backpack rows retain their server ids")
	_expect(windows.merchant_buy_list.get_selected_items().is_empty(), "the active sale clears the buy selection")
	_expect(windows.merchant_totals.text.contains("Receive: 12 gc")
		and windows.merchant_totals.text.contains("Gold after: 262 gc")
		and windows.merchant_totals.text.contains("Carry after: 16/80"), "sale previews proceeds, gold and load")
	await _capture("merchant-sell.png")
	windows._merchant_set_maximum()
	_expect(windows.merchant_quantity.text == "12", "sell Max uses the owned quantity")
	windows.merchant_quantity.text = "13"
	windows._sync_merchant_summary()
	_expect(windows.merchant_trade.disabled, "overselling is disabled")
	# Reordering a refreshed packet must keep the same server item selected.
	(state.get("merchant")["items"] as Array).reverse()
	windows._sync_merchant()
	_expect(windows._merchant_entry().name == "Sage", "refresh preserves selection by server id")
	for entry: Dictionary in state.get("merchant")["items"]:
		entry["owned"] = 0
	windows._sync_merchant()
	_expect(windows.merchant_empty_pack.visible and windows.merchant_trade.disabled,
		"an empty sellable backpack explains why trading is unavailable")
	state.set("authenticated", false)
	main.queue_free()
	await process_frame
	print("merchant shop/backpack checks: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _settle() -> void:
	for unused: int in range(5):
		await process_frame

func _capture(filename: String) -> void:
	await _settle()
	var bounds: Rect2 = windows.merchant_panel.get_global_rect()
	_expect(bounds.end.x <= 1184 and bounds.end.y <= 680, "the merchant panel clears the HUD rail and toolbar")
	var action: Rect2 = windows.merchant_trade.get_global_rect()
	_expect(bounds.encloses(action), "the transaction button stays inside the panel")
	var output := OS.get_environment("ELORIA_ARTIFACT_DIR")
	if output.is_empty():
		return
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(output)
	var image := root.get_texture().get_image()
	_expect(image != null and image.get_size() == Vector2i(1280, 720), "a full rendered frame is captured")
	if image != null:
		_expect(image.save_png(output.path_join(filename)) == OK, "the screenshot is saved")

func _expect(value: bool, description: String) -> void:
	if not value:
		failures += 1
		push_error("FAIL: " + description)
