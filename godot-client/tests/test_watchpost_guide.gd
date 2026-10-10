extends SceneTree

class GuideHost extends Control:
	var inventory_slot_buttons: Array = []
	var manufacturing_mix_one: Button
	var manufacturing_detail: Control

var failures := 0

func expect(ok: bool, label: String) -> void:
	if not ok:
		failures += 1
		push_error(label)

func _init() -> void:
	call_deferred("run")

func run() -> void:
	var host := GuideHost.new()
	root.add_child(host)
	var panel := PanelContainer.new()
	panel.name = "ManufacturingPanel"
	host.add_child(panel)
	panel.owner = host
	panel.unique_name_in_owner = true
	var list := ItemList.new()
	list.name = "ManufacturingList"
	host.add_child(list)
	list.owner = host
	list.unique_name_in_owner = true
	list.add_item("Bandage")
	list.add_item("Torch")
	host.manufacturing_mix_one = Button.new()
	host.add_child(host.manufacturing_mix_one)
	var guide: Control = load("res://src/ui/lantern_guide.gd").new()
	host.add_child(guide)
	guide.configure(host)
	guide.set_process(false)
	var app_state := root.get_node("AppState")
	var authenticated: bool = app_state.authenticated
	app_state.authenticated = true
	var state := {"active":true, "tutorial":"watchpost", "stage":4, "total":6,
		"title":"Gather the ingredients", "hint":"Gather 2 Sage.",
		"key":"sage", "count":1, "required":2, "control":"world", "item":"Sage"}
	guide.apply_state(state)
	expect(guide.chapter.text == "HELP FOR THE WATCHPOST  ·  4 / 6", "quest uses its own chapter label")
	expect(guide.instruction.text.contains("Progress: 1 / 2"), "gathering progress is visible")
	expect(guide.help.visible and guide.help.text == "Quest help", "quest help is available")
	state.stage = 5
	state.key = "watchpost"
	state.required = 1
	state.control = "manufacture"
	state.item = "Bandage"
	guide.apply_state(state)
	list.select(0)
	expect(guide.control_for_step() == host.manufacturing_mix_one, "selected Bandage highlights Mix One")
	list.select(1)
	expect(guide.control_for_step() == list, "another recipe points back to the recipe list")
	guide.apply_state({"active":false})
	expect(not guide.visible, "completion hides the guide")
	app_state.authenticated = authenticated
	host.queue_free()
	print("Watchpost guide: %d failures" % failures)
	quit(failures)
