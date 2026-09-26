@tool
extends PopupPanel
## Options for the ground-region and plateau tools (see area_tool.gd), opened
## from Map tools or the toolbar. Start closes it and arms the tool.

signal start_requested(kind: String, options: Dictionary)

const GROUND_SCRIPT := preload("res://src/dev/map_authoring_region/ground_region_control.gd")

var kind := "ground"
var _title: Label
var _ground: GridContainer
var _plateau: GridContainer
var _surface: OptionButton
var _surface_choices: Array[Dictionary] = []
var _ground_shape: OptionButton
var _blend: SpinBox
var _opacity: SpinBox
var _priority: SpinBox
var _operation: OptionButton
var _plateau_shape: OptionButton
var _height: SpinBox
var _feather: SpinBox
var _height_label: Label


func _init() -> void:
	var column := VBoxContainer.new()
	column.custom_minimum_size = Vector2(340, 0)
	column.add_theme_constant_override("separation", 6)
	add_child(column)
	_title = Label.new()
	_title.add_theme_font_size_override("font_size", 15)
	column.add_child(_title)
	_ground = GridContainer.new()
	_ground.columns = 2
	column.add_child(_ground)
	_surface = OptionButton.new()
	_surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_field(_ground, "Surface", _surface)
	_ground_shape = _shape_picker()
	_field(_ground, "Shape", _ground_shape)
	_blend = _spin(0.0, 16.0, 0.25, 3.0, " m")
	_field(_ground, "Feather", _blend)
	_opacity = _spin(0.05, 1.0, 0.01, 0.9, "")
	_field(_ground, "Opacity", _opacity)
	_priority = _spin(-1000.0, 1000.0, 1.0, 10.0, "")
	_field(_ground, "Priority", _priority)
	_plateau = GridContainer.new()
	_plateau.columns = 2
	column.add_child(_plateau)
	_operation = OptionButton.new()
	_operation.add_item("Level at a height (Set)")
	_operation.add_item("Raise or lower (Add)")
	_operation.item_selected.connect(func(_index: int) -> void: _sync_height_label())
	_field(_plateau, "Operation", _operation)
	_plateau_shape = _shape_picker()
	_field(_plateau, "Shape", _plateau_shape)
	_height = _spin(-200.0, 400.0, 0.1, 3.0, " m")
	_height_label = _field(_plateau, "Above ground", _height)
	_feather = _spin(0.0, 64.0, 0.5, 6.0, " m")
	_field(_plateau, "Feather", _feather)
	var note := Label.new()
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.text = "Press where the centre goes in the 3D view and drag out the size. Esc discards a draft; right-click stops."
	column.add_child(note)
	var start := Button.new()
	start.text = "Start drawing"
	start.pressed.connect(func() -> void:
		hide()
		start_requested.emit(kind, current_options()))
	column.add_child(start)


## Opens for "ground" or "plateau"; `root` supplies the territory's own surfaces.
func open_for(tool_kind: String, root: Node, anchor: Rect2i) -> void:
	kind = tool_kind
	_title.text = "Paint ground regions" if kind == "ground" else "Stamp plateaus"
	_ground.visible = kind == "ground"
	_plateau.visible = kind == "plateau"
	fill_surfaces(root)
	_sync_height_label()
	if is_inside_tree():
		popup(anchor)


## Surfaces this territory's ground regions already use (a shared surface file
## is reused; an embedded one is copied), then the texture presets.
func fill_surfaces(root: Node) -> void:
	var previous := _surface.get_item_text(_surface.selected) if _surface.item_count > 0 else ""
	_surface.clear()
	_surface_choices.clear()
	var seen := {}
	var regions := root.get_node_or_null("Ground/Regions") if root != null else null
	if regions != null:
		for child in regions.get_children():
			if child.get_script() != GROUND_SCRIPT or child.get("surface") == null:
				continue
			var surface: Resource = child.get("surface")
			var shared := not surface.resource_path.is_empty() and not "::" in surface.resource_path
			var key := surface.resource_path if shared else str(surface.get_instance_id())
			if seen.has(key):
				continue
			seen[key] = true
			_surface_choices.append({"label": surface.resource_path.get_file() if shared else
				"As %s (copy)" % String(child.get("region_id")), "surface": surface,
				"copy": not shared})
	for preset: String in MapAuthoringTexturePresets.PRESET_NAMES:
		if preset != MapAuthoringTexturePresets.CUSTOM:
			_surface_choices.append({"label": "Preset: %s" % preset, "preset": preset})
	for choice in _surface_choices:
		_surface.add_item(String(choice.label))
		if String(choice.label) == previous:
			_surface.select(_surface.item_count - 1)


## The options area_tool.gd expects.
func current_options() -> Dictionary:
	if kind == "ground":
		var choice: Dictionary = _surface_choices[_surface.selected] \
			if _surface.selected >= 0 and _surface.selected < _surface_choices.size() else {}
		var options := {"shape": _ground_shape.selected, "blend_width": _blend.value,
			"opacity": _opacity.value, "priority": int(_priority.value),
			"surface_label": String(choice.get("label", ""))}
		if choice.has("surface"):
			options["surface"] = (choice.surface as Resource).duplicate(true) \
				if bool(choice.get("copy", false)) else choice.surface
		elif choice.has("preset"):
			options["preset"] = choice.preset
		return options
	return {"operation": "set" if _operation.selected == 0 else "add",
		"shape": _plateau_shape.selected, "height": _height.value, "feather": _feather.value}


func select_surface(label: String) -> bool:
	for index in _surface.item_count:
		if _surface.get_item_text(index) == label:
			_surface.select(index)
			return true
	return false


func _sync_height_label() -> void:
	_height_label.text = "Above ground" if _operation.selected == 0 else "Raise by"


func _shape_picker() -> OptionButton:
	var picker := OptionButton.new()
	picker.add_item("Ellipse")
	picker.add_item("Rectangle")
	return picker


func _field(grid: GridContainer, text: String, control: Control) -> Label:
	var label := Label.new()
	label.text = text
	grid.add_child(label)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_child(control)
	return label


func _spin(minimum: float, maximum: float, step: float, value: float, suffix: String) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.step = step
	spin.value = value
	spin.suffix = suffix
	return spin
