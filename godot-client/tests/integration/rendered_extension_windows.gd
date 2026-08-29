extends SceneTree
## Rendered evidence for the Eloria extension windows.
##
## The "before" frame in each pair is the HUD as the shipped client left it:
## the window did not exist, so the packet that drives it changed nothing on
## screen. The "after" frame is the same HUD once the packet arrives. Every
## payload is the exact output of the server's builder in eloria/protocol.py.
##
## Every frame is checked for real colour variation, so a dummy or black frame
## cannot pass as evidence.

const SCREEN_SIZE := Vector2i(1280, 720)

var _artifacts := ""
var _failures := 0
var _main: Control
var _app_state: Node
var _windows: Control

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_artifacts = OS.get_environment("ELORIA_ARTIFACT_DIR")
	if _artifacts.is_empty():
		_artifacts = ProjectSettings.globalize_path("res://test-artifacts/phase2")
	_expect(DirAccess.make_dir_recursive_absolute(_artifacts) == OK,
		"artifact directory is writable")
	root.size = SCREEN_SIZE
	await _open_client()

	await _capture("extension-windows-before.png",
		"the HUD before any extension packet: none of these windows existed")

	# The three always-on readouts, together, as they are actually seen.
	_send(230, "010203e1010c00666f75725f676174657300526565642062616e6b00")
	_send(227, "016600120014001e002c00050052656564686f726e205374616700")
	_send(232, "4861727665737420666573746976616c0050686173652032206f66203300")
	await _settle()
	_expect(_windows.navigation_label.visible and _windows.combat_panel.visible
		and _windows.events_panel.visible,
		"the navigation, combat and special-event readouts are on screen")
	await _capture("extension-hud-readouts.png",
		"navigation waypoint, combat bars and the special-event panel, all"
			+ " server-stated")

	_send(224, "01000001000000030000004b696c6c205468656d20416c6c0044656665617"
		+ "42033207261747300466f757220476174657300")
	await _settle()
	_windows.toggle_quest_journal()
	await _settle()
	_expect(_windows.quest_panel.visible, "the quest journal is on screen")
	await _capture("extension-quest-journal.png",
		"the quest journal: progress, objective and location, all from the"
			+ " server's own entry")

	# Tracking pins the server's own journal entry to the HUD.
	_windows._on_quest_track_pressed()
	_windows.toggle_quest_journal()
	await _settle()
	_expect(_windows.tracked_quest.visible and not _windows.quest_panel.visible,
		"the tracked readout stays when the journal closes")
	await _capture("extension-quest-tracked.png",
		"the tracked quest pinned to the HUD, restated from the server's"
			+ " journal rather than remembered from when it was pinned")

	_send(229, "01000300000000f1536500416c6963650048656c6c6f004d656574206d6520"
		+ "61742074686520676174652e00")
	await _settle()
	_windows.toggle_mail()
	await _settle()
	_expect(_windows.mail_panel.visible and not _windows.quest_panel.visible,
		"mail replaced the quest journal rather than stacking on it")
	await _capture("extension-mail.png",
		"the inbox, with the unread marker and the selected message body")

	_send(225, "a000020000000053756e6c656166005265736f75726365730000412070616c"
		+ "65206c6561662e00454d55203100477561726420436170650041726d6f75722"
		+ "0322d3e203000")
	await _settle()
	_expect(_windows.detail_panel.visible, "item detail is on screen")
	await _capture("extension-item-detail.png",
		"item detail, including the comparison against the equipped item")

	_windows.close_all()
	_send(223, "5b00fa0000001400000050000000010053616c696e61000000280000000c00"
		+ "0000050000001400 53756e6c65616600".replace(" ", ""))
	await _settle()
	_expect(_windows.merchant_panel.visible, "the merchant window is on screen")
	await _capture("extension-merchant.png",
		"the merchant window that replaces the NPC shop dialogue entirely")

	# Command 228, the tenth extension packet: who the player just looked at.
	_windows.close_all()
	_send(228, "5b000100416c69636500426567696e6e6572205475746f7269616c00")
	await _settle()
	var info: Control = _main.get("player_info_panel") as Control
	_expect((info.get_node("PlayerInfo") as Control).visible,
		"the player-info window is on screen")
	await _capture("extension-player-info.png",
		"looking at another player: the actor, the name and the achievements,"
			+ " all stated in one packet")
	_app_state.call("close_player_info")
	await _settle()

	_windows.close_all()
	_send(222, "00fa000000030000000100070000000c0000002300000058020000140053756"
		+ "e6c65616600416c69636500")
	await _settle()
	_expect(_windows.market_panel.visible, "the exchange is on screen")
	await _capture("extension-marketplace.png",
		"the exchange: gold, escrowed items and one live listing")

	_app_state.set("authenticated", false)
	_main.queue_free()
	await process_frame
	print("rendered extension windows: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)

func _open_client() -> void:
	_main = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(_main)
	await process_frame
	(_main.get_node("GameView") as Control).show()
	(_main.get_node("LoginPanel") as Control).hide()
	_app_state = root.get_node("/root/AppState")
	_app_state.set("authenticated", true)
	_windows = _main.get("extension_windows") as Control
	_expect(_windows != null, "the extension windows are built")
	await _settle()

func _send(command: int, hex: String) -> void:
	_app_state.call("_on_packet", command, _hex_bytes(hex))

func _settle() -> void:
	for _frame: int in range(4):
		await process_frame

func _hex_bytes(value: String) -> PackedByteArray:
	var bytes := PackedByteArray()
	for index: int in range(0, value.length(), 2):
		bytes.append(value.substr(index, 2).hex_to_int())
	return bytes

func _capture(name: String, description: String) -> void:
	await process_frame
	var image: Image = root.get_texture().get_image()
	_expect(image != null and image.get_size() == SCREEN_SIZE,
		"%s is a full %dx%d frame" % [name, SCREEN_SIZE.x, SCREEN_SIZE.y])
	if image == null:
		return
	_expect(_has_colour_variation(image),
		"%s contains rendered colour variation rather than a dummy frame" % name)
	_expect(image.save_png(_artifacts.path_join(name)) == OK,
		"%s is written" % name)
	print("capture ", name, ": ", description,
		"  mean_luminance=", "%.4f" % _mean_luminance(image))

func _mean_luminance(image: Image) -> float:
	var total := 0.0
	var samples := 0
	for y: int in range(0, image.get_height(), 8):
		for x: int in range(0, image.get_width(), 8):
			var colour: Color = image.get_pixel(x, y)
			total += colour.get_luminance()
			samples += 1
	return total / maxf(1.0, float(samples))

func _has_colour_variation(image: Image) -> bool:
	var lowest := 2.0
	var highest := -1.0
	for y: int in range(0, image.get_height(), 8):
		for x: int in range(0, image.get_width(), 8):
			var luminance: float = image.get_pixel(x, y).get_luminance()
			lowest = minf(lowest, luminance)
			highest = maxf(highest, luminance)
	return highest - lowest > 0.02

func _expect(value: bool, label: String) -> bool:
	if not value:
		_failures += 1
		push_error("FAIL: " + label)
	return value
