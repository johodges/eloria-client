extends SceneTree
var failures := 0
var observed: Array[int] = []
var casts: Array[Dictionary] = []
var render := false
var main: Control
func _init() -> void: call_deferred("run")
func check(value: bool, message: String) -> void:
	if not value:
		failures += 1
		push_error("FAIL: " + message)
func key(code: Key, pressed := true) -> InputEventKey:
	var event := InputEventKey.new()
	event.physical_keycode = code
	event.keycode = code
	event.location = KEY_LOCATION_LEFT if code == KEY_SHIFT else KEY_LOCATION_UNSPECIFIED
	event.pressed = pressed
	event.shift_pressed = true
	return event
func run() -> void:
	render = "--render" in OS.get_cmdline_user_args()
	root.size = Vector2i(1280,720)
	main = (load("res://src/app/main.tscn") as PackedScene).instantiate()
	root.add_child(main)
	await process_frame
	var state := root.get_node("AppState")
	state.authenticated = true
	state.select_actor(-1)
	state.spell_power["heal"] = {"limit":10}
	main.game_view.show()
	main.login_panel.hide()
	main.spell_loadout.profile = ""
	main.spell_wheel.anchor_provider = func(): return Vector2(root.size) / 2
	main.spell_wheel.opened.connect(func(): observed.append(20))
	main.spell_wheel.tutorial_action.connect(func(action: int): observed.append(action))
	main.magic_selection.request_sender = func(data: Dictionary) -> Error:
		casts.append(data.duplicate(true))
		return OK
	show_lesson("spell_ring", "Your spell ring", "Hold Left Shift to open your spell ring, or click Ring on the quickbar. Alt remains available for quickbar shortcuts.")
	check(main.lantern_guide.control_for_step() == main.casting_bar.wheel_button, "closed-ring lesson highlights the Ring button")
	root.push_input(key(KEY_SHIFT), true)
	await process_frame
	check(observed == [20] and main.spell_wheel.visible, "Left Shift opens the live ring and records one tutorial observation")
	await capture("intro-open")
	root.push_input(key(KEY_1), true)
	await process_frame
	check(observed == [20,21] and main.spell_wheel.category == "Healing", "the displayed class shortcut records browsing")
	root.push_input(key(KEY_SHIFT,false), true)
	check(observed == [20,21,22] and casts.is_empty(), "release records dismissal without a spell request")
	main.casting_bar.open_wheel.emit()
	main.spell_wheel.enter_class("Healing")
	root.push_input(key(KEY_ESCAPE), true)
	check(observed.slice(-3) == [20,21,22], "mouse-only ring can browse and dismiss with Escape")
	main.spell_wheel.open_wheel(true)
	main.spell_wheel.enter_class("Healing")
	main.spell_wheel.select_scope("self")
	var before := observed.size()
	root.push_input(key(KEY_1), true)
	root.push_input(key(KEY_SHIFT,false), true)
	check(observed.size() == before and casts.back().get("op") == "cast", "casting and its Shift release cannot report tutorial cancellation")
	main.spell_wheel.open_wheel()
	main.spell_wheel.enter_class("Healing")
	for control in ["ring_target","ring_power"]:
		show_lesson(control, "Choose your cast", "Hold Left Shift, open Healing and hover Heal. Right click cycles Self, Target, Allies and Burst. Scroll to Power 2, then choose Heal. The quickbar saves the last cast target type and power in the icon corners.")
		await capture(control)
		check(main.lantern_guide.control_for_step() == (main.spell_wheel._scope_bar if control == "ring_target" else main.spell_wheel._power_label), "lesson highlights " + control + " visible=" + str(main.spell_wheel.visible) + " actual=" + str(main.lantern_guide.control_for_step()))
	for percent in [75,125]:
		main.spell_loadout.set_ring_size(percent)
		await capture("size-%d" % percent)
	main.spell_wheel.reset()
	show_lesson("quickbar", "A spell within reach", "Find Heal on the quickbar (default Alt+1). Its top-left badge is the saved target type; top-right is power. Click it or use its shortcut to heal this second wound.")
	await capture("quickbar")
	check(main.lantern_guide.control_for_step() == main.casting_bar.panel, "quickbar teaching highlights the panel rather than the whole viewport")
	main.free()
	await process_frame
	NativeAnimationImporter.clear()
	GlbSceneCache.clear()
	print("magic ring tutorial: ", "PASS" if failures == 0 else "FAIL")
	quit(failures)
func show_lesson(control: String, title: String, hint: String) -> void:
	main.lantern_guide.apply_state({"active":true,"tutorial":"borrowed_sky","stage":1,"total":39,"control":control,"title":title,"hint":hint})
func capture(name: String) -> void:
	for frame in range(6): await process_frame
	var card: Rect2 = main.lantern_guide.card.get_global_rect()
	check(main.casting_bar.panel.get_global_rect().end.x <= root.size.x-96, "ring size control leaves the live resource rail clear")
	check(Rect2(Vector2.ZERO,Vector2(root.size)).encloses(card), "tutorial card stays in the viewport")
	if main.spell_wheel.visible:
		var bounds: Rect2 = main.spell_wheel.get_ring_bounds()
		check(not card.intersects(bounds), "tutorial card leaves ring sectors unobstructed")
	if render:
		await RenderingServer.frame_post_draw
		DirAccess.make_dir_recursive_absolute("res://test-artifacts/magic-casting")
		root.get_texture().get_image().save_png("res://test-artifacts/magic-casting/tutorial-"+name+".png")
