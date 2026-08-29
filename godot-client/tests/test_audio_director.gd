extends SceneTree
## Guards the audio layer.
##
## Every sound is answered to an authoritative event: a harvest the server
## started, an item it put in the backpack, a combat outcome it reported, an
## effect it announced. Nothing plays on a guess, and a snapshot that restates
## what was already true is not a new event.

var failures := 0
var played: Array[String] = []

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main: Control = (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	(main.get_node("GameView") as Control).show()
	(main.get_node("LoginPanel") as Control).hide()
	var app_state: Node = root.get_node("/root/AppState")
	app_state.set("authenticated", true)
	var director: Node = main.get("audio_director") as Node
	if not _expect(director != null, "the audio director is built"):
		quit(failures)
		return
	await process_frame

	var names: Array = director.call("sound_names") as Array
	_expect(names.size() == 10 and names.has("harvest_start")
		and names.has("combat_hit") and names.has("world_effect"),
		"the whole generated sound set loaded: %s" % str(names))

	# Harvesting. The server states it started; a restatement is not a new one.
	director.set("enabled", true)
	_expect(bool(director.call("play", "ui_click")),
		"a sound the catalog has can be played")
	director.call("stop_all")
	var harvest_started := PackedByteArray([1, 0xf0, 0x01])
	harvest_started.append_array(_nul("Sunleaf"))
	app_state.call("_on_packet", 237, harvest_started)
	await process_frame
	_expect(bool(director.call("is_playing")),
		"the server starting a harvest is heard")
	director.call("stop_all")
	app_state.call("_on_packet", 237, harvest_started)
	await process_frame
	_expect(not bool(director.call("is_playing")),
		"restating the same harvest is not a second start")
	app_state.call("_on_packet", 237, PackedByteArray([0, 0, 0, 0]))
	await process_frame

	# Combat outcomes.
	director.call("stop_all")
	app_state.call("_on_packet", 227, _hex(
		"016600120014001e002c00050052656564686f726e205374616700"))
	await process_frame
	_expect(bool(director.call("is_playing")),
		"a hit the server reported is heard")
	director.call("stop_all")
	app_state.call("_on_packet", 227, _hex(
		"016600120014001e002c00050052656564686f726e205374616700"))
	await process_frame
	_expect(not bool(director.call("is_playing")),
		"the same outcome restated is not a second hit")

	# An effect the server announced.
	director.call("stop_all")
	app_state.call("_on_packet", 79, PackedByteArray([17, 0x5b, 0]))
	await process_frame
	_expect(bool(director.call("is_playing")),
		"an effect the server announced is heard")

	# Off means off, and stays off across events.
	director.call("stop_all")
	director.set("enabled", false)
	_expect(not bool(director.call("play", "ui_click")),
		"nothing plays while sound is off")
	app_state.call("_on_packet", 79, PackedByteArray([17, 0x5b, 0]))
	await process_frame
	_expect(not bool(director.call("is_playing")),
		"an announced effect stays silent while sound is off")
	director.set("enabled", true)

	# The setting is the player's own, and it is kept.
	var toggle: CheckButton = main.get_node(
		"GameView/SettingsPanel/Content/SoundRow/SoundEnabled") as CheckButton
	var slider: HSlider = main.get_node(
		"GameView/SettingsPanel/Content/SoundRow/SoundVolume") as HSlider
	var readout: Label = main.get_node(
		"GameView/SettingsPanel/Content/SoundRow/SoundVolumeValue") as Label
	main.call("_on_sound_volume_changed", 0.35)
	await process_frame
	_expect(is_equal_approx(float(director.get("volume_linear")), 0.35)
		and readout.text == "35%",
		"the volume the player chose is applied and shown: " + readout.text)
	main.call("_on_sound_enabled_toggled", false)
	await process_frame
	_expect(not bool(director.get("enabled")),
		"the toggle turns sound off")
	var config := ConfigFile.new()
	_expect(config.load(str(main.get("SETTINGS_PATH"))) == OK
		and not bool(config.get_value("audio", "enabled", true))
		and is_equal_approx(float(config.get_value("audio", "volume", 1.0)), 0.35),
		"both settings are written to the settings file")
	main.call("_on_sound_enabled_toggled", true)
	main.call("_on_sound_volume_changed", 0.7)
	_expect(toggle != null and slider != null,
		"the settings panel exposes both controls")

	print("audio director tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	main.queue_free()
	await process_frame
	quit(failures)

func _nul(value: String) -> PackedByteArray:
	var bytes: PackedByteArray = value.to_utf8_buffer()
	bytes.append(0)
	return bytes

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
