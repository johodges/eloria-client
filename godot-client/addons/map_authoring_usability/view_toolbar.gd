@tool
extends HBoxContainer
## One-click toggles in the 3D editor's toolbar for the map editor's view
## options, so the common ones need no trip into the Map tools menu:
## Grid (cursor grid always on), Snap (placement grid snap), Pins (gameplay
## markers), Walk (walkability overlay mode), Play (play-test walker) and
## Low spec (half resolution and far-asset culling).

signal option_toggled(option: String, on: bool)
signal walk_mode_selected(mode: int)

const WALK_MODES := ["Off", "Published grid (exact)", "Live suggestion", "Changes since publish"]
const TOGGLES := [
	["grid", "Grid", "Show the terrain grid under the cursor all the time (off: only while placing)."],
	["snap", "Snap", "Snap placements and drawn points to the grid (G)."],
	["pins", "Pins", "Show gameplay markers as coloured pins with labels."],
	["play", "Play", "Play test: click to walk the territory like a player (Esc stops)."],
	["low_spec", "Low spec", "Half-resolution 3D view, far assets hidden, frame time shown."],
]

var _buttons := {}
var _walk: MenuButton


func _init() -> void:
	name = "MapAuthoringViewToolbar"
	add_theme_constant_override("separation", 2)
	add_child(VSeparator.new())
	for spec: Array in TOGGLES:
		var button := Button.new()
		button.text = String(spec[1])
		button.tooltip_text = String(spec[2])
		button.toggle_mode = true
		button.flat = true
		button.focus_mode = Control.FOCUS_NONE
		button.toggled.connect(func(on: bool) -> void: option_toggled.emit(String(spec[0]), on))
		add_child(button)
		_buttons[spec[0]] = button
		if spec[0] == "pins":
			_walk = MenuButton.new()
			_walk.text = "Walk"
			_walk.flat = true
			_walk.tooltip_text = "Walkability overlay: where players can walk."
			for index in WALK_MODES.size():
				_walk.get_popup().add_radio_check_item(String(WALK_MODES[index]), index)
			_walk.get_popup().id_pressed.connect(func(id: int) -> void: walk_mode_selected.emit(id))
			add_child(_walk)


## Mirrors the current state without emitting signals:
## {grid, snap, pins, play, low_spec: bool, walk_mode: int}.
func sync(state: Dictionary) -> void:
	for key: String in _buttons:
		(_buttons[key] as Button).set_pressed_no_signal(bool(state.get(key, false)))
	var mode := int(state.get("walk_mode", 0))
	var popup := _walk.get_popup()
	for index in popup.item_count:
		popup.set_item_checked(index, popup.get_item_id(index) == mode)
	_walk.text = "Walk" if mode == 0 else "Walk: %s" % ["", "published", "live", "changes"][mode]


func button(option: String) -> Button:
	return _buttons.get(option) as Button


func walk_menu() -> MenuButton:
	return _walk
