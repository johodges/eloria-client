class_name OldcraftEntryStyle
extends RefCounted
## Low-cost entry-screen styling inspired by Oldcraft's heavy fantasy frames.
##
## The screens keep Eloria's logo, world painting, controls and navigation.
## This helper supplies the visual language: dark carved-stone panels, warm
## brass edges, burgundy action buttons, inset fields and a moonlit preview
## stage.  Everything is generated from built-in UI/mesh resources, so the
## login path adds no downloaded art, texture memory or gameplay cost.

## Sampled from the shipped reference UI rather than eyeballed from a concept:
## brass #F4C542/#B88A3B, carved stone #1E1E22/#333338, parchment
## #E9D5A8, oxblood #8E1B12 and warm type #F5F0E0.
const GOLD := Color(0.957, 0.773, 0.259, 1.0)
const GOLD_DARK := Color(0.722, 0.541, 0.231, 1.0)
const GOLD_BRIGHT := Color(1.0, 0.86, 0.48, 1.0)
const PARCHMENT := Color(0.914, 0.835, 0.659, 1.0)
const WARM_TEXT := Color(0.961, 0.941, 0.878, 1.0)
const MUTED := Color(0.69, 0.65, 0.58, 1.0)
const STONE := Color(0.118, 0.118, 0.133, 0.94)
const STONE_RAISED := Color(0.20, 0.20, 0.22, 0.96)
const FIELD := Color(0.025, 0.026, 0.032, 0.96)
const BURGUNDY := Color(0.557, 0.106, 0.071, 0.98)
const BURGUNDY_HOVER := Color(0.722, 0.169, 0.102, 1.0)
const BURGUNDY_PRESSED := Color(0.31, 0.045, 0.028, 1.0)
const PREVIEW_SKY := Color(0.018, 0.035, 0.075, 1.0)
const STYLE_META := &"eloria_oldcraft_entry_style"


static func _flat_box(background: Color, border: Color, width: int,
		corner: int, margin: float) -> StyleBoxFlat:
	var box := StyleBoxFlat.new()
	box.bg_color = background
	box.border_color = border
	box.set_border_width_all(width)
	box.set_corner_radius_all(corner)
	box.set_content_margin_all(margin)
	return box


static func apply(main: Control) -> void:
	if main == null:
		return
	_style_panel(main.get_node_or_null("%LoginPanel") as PanelContainer, false)
	_style_panel(main.get_node_or_null("%CreationPanel") as PanelContainer, true)
	_style_controls(main.get_node_or_null("%LoginPanel") as Control)
	_style_controls(main.get_node_or_null("%CreationPanel") as Control)
	_style_titles(main)
	_style_preview(main)
	main.set_meta(STYLE_META, true)


static func _style_panel(panel: PanelContainer, wide: bool) -> void:
	if panel == null:
		return
	var frame := _flat_box(STONE, GOLD_DARK, 5, 4,
		18.0 if wide else 22.0)
	frame.shadow_color = Color(0.0, 0.0, 0.0, 0.78)
	frame.shadow_size = 12
	frame.shadow_offset = Vector2(0.0, 5.0)
	panel.add_theme_stylebox_override("panel", frame)
	# A thin brass inner edge catches the same warm light as the title and
	# buttons without needing a nine-patch texture.
	panel.add_theme_constant_override("outline_size", 1)


static func _style_controls(root: Control) -> void:
	if root == null:
		return
	var button_normal := _flat_box(BURGUNDY, GOLD_DARK,
		2, 4, 7.0)
	var button_hover := _flat_box(BURGUNDY_HOVER, GOLD_BRIGHT, 2, 4, 7.0)
	var button_pressed := _flat_box(BURGUNDY_PRESSED,
		Color(0.72, 0.48, 0.16, 1.0), 2, 4, 7.0)
	var button_disabled := _flat_box(Color(0.08, 0.065, 0.06, 0.86),
		Color(0.25, 0.22, 0.18, 0.8), 1, 4, 7.0)
	for value: Node in root.find_children("*", "Button", true, false):
		var button := value as Button
		button.add_theme_stylebox_override("normal", button_normal)
		button.add_theme_stylebox_override("hover", button_hover)
		button.add_theme_stylebox_override("pressed", button_pressed)
		button.add_theme_stylebox_override("hover_pressed", button_pressed)
		button.add_theme_stylebox_override("focus", button_hover)
		button.add_theme_stylebox_override("disabled", button_disabled)
		button.add_theme_color_override("font_color", WARM_TEXT)
		button.add_theme_color_override("font_hover_color", GOLD_BRIGHT)
		button.add_theme_color_override("font_pressed_color", GOLD)
		button.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
		button.add_theme_constant_override("outline_size", 2)
		button.custom_minimum_size.y = maxf(button.custom_minimum_size.y, 36.0)
	var field_normal := _flat_box(FIELD, GOLD_DARK,
		2, 3, 8.0)
	var field_focus := _flat_box(Color(0.018, 0.019, 0.026, 1.0), GOLD,
		2, 3, 8.0)
	for value: Node in root.find_children("*", "LineEdit", true, false):
		var field := value as LineEdit
		field.add_theme_stylebox_override("normal", field_normal)
		field.add_theme_stylebox_override("focus", field_focus)
		field.add_theme_color_override("font_color", WARM_TEXT)
		field.add_theme_color_override("font_placeholder_color", MUTED)
		field.add_theme_color_override("caret_color", GOLD_BRIGHT)
		field.custom_minimum_size.y = maxf(field.custom_minimum_size.y, 36.0)
	for value: Node in root.find_children("*", "CheckBox", true, false):
		var check := value as CheckBox
		check.add_theme_color_override("font_color", WARM_TEXT)
		check.add_theme_color_override("font_hover_color", GOLD_BRIGHT)
	for value: Node in root.find_children("*", "Label", true, false):
		var label := value as Label
		label.add_theme_color_override("font_color", WARM_TEXT)
		label.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.95))
		label.add_theme_constant_override("outline_size", 2)


static func _style_titles(main: Control) -> void:
	var login_title := main.get_node_or_null("LoginPanel/Content/Subtitle") as Label
	if login_title != null:
		login_title.text = "ENTER THE WORLD OF ELORIA"
		login_title.add_theme_color_override("font_color", GOLD_BRIGHT)
		login_title.add_theme_font_size_override("font_size", 21)
		login_title.add_theme_constant_override("outline_size", 4)
	var creation_title := main.get_node_or_null(
		"CreationPanel/Columns/Form/Title") as Label
	if creation_title != null:
		creation_title.text = "FORGE YOUR HERO"
		creation_title.add_theme_color_override("font_color", GOLD_BRIGHT)
		creation_title.add_theme_font_size_override("font_size", 27)
		creation_title.add_theme_constant_override("outline_size", 4)
	var status := main.get_node_or_null("%Status") as Label
	if status != null:
		status.add_theme_color_override("font_color", MUTED)
	var create_status := main.get_node_or_null("%CreateStatus") as Label
	if create_status != null:
		create_status.add_theme_color_override("font_color", MUTED)


static func _style_preview(main: Control) -> void:
	var preview_root := main.get_node_or_null("%PreviewRoot") as Node3D
	var world_environment := main.get_node_or_null(
		"CreationPanel/Columns/CharacterPreview/Viewport/PreviewRoot/PreviewEnvironment") \
		as WorldEnvironment
	if world_environment != null and world_environment.environment != null:
		world_environment.environment.background_mode = Environment.BG_COLOR
		world_environment.environment.background_color = PREVIEW_SKY
		world_environment.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		world_environment.environment.ambient_light_color = Color(0.34, 0.42, 0.56, 1.0)
		world_environment.environment.ambient_light_energy = 0.95
	var key := main.get_node_or_null("%KeyLight") as DirectionalLight3D
	if key != null:
		key.light_color = Color(1.0, 0.78, 0.48, 1.0)
		key.light_energy = 1.42
	var fill := main.get_node_or_null("%FillLight") as DirectionalLight3D
	if fill != null:
		fill.light_color = Color(0.22, 0.48, 0.78, 1.0)
		fill.light_energy = 0.52
	var rim := main.get_node_or_null("%RimLight") as DirectionalLight3D
	if rim != null:
		rim.light_color = Color(0.18, 0.72, 0.68, 1.0)
		rim.light_energy = 0.5
	var ground := main.get_node_or_null(
		"CreationPanel/Columns/CharacterPreview/Viewport/PreviewRoot/PreviewGround") \
		as MeshInstance3D
	if ground != null and ground.mesh != null:
		var ground_material := ground.get_active_material(0) as BaseMaterial3D
		if ground_material != null:
			ground_material.albedo_color = Color(0.13, 0.18, 0.19, 1.0)
			ground_material.roughness = 0.92
			ground_material.metallic_specular = 0.18
	if preview_root == null or preview_root.get_node_or_null("OldcraftStage") != null:
		return
	var stage := Node3D.new()
	stage.name = "OldcraftStage"
	preview_root.add_child(stage)
	_add_cylinder(stage, "StonePlinth", 0.95, 0.86, 0.14, -0.12,
		Color(0.075, 0.085, 0.09, 1.0), 24)
	_add_cylinder(stage, "BrassPlinthRing", 0.84, 0.84, 0.025, -0.035,
		Color(0.42, 0.29, 0.105, 1.0), 48, 0.58)


static func _material(color: Color, metallic := 0.0) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.86
	material.metallic = metallic
	material.metallic_specular = 0.24
	return material


static func _add_cylinder(parent: Node3D, node_name: String, top: float,
		bottom: float, height: float, y: float, color: Color, segments: int,
		metallic := 0.0) -> void:
	var mesh := CylinderMesh.new()
	mesh.top_radius = top
	mesh.bottom_radius = bottom
	mesh.height = height
	mesh.radial_segments = segments
	mesh.material = _material(color, metallic)
	var instance := MeshInstance3D.new()
	instance.name = node_name
	instance.position.y = y
	instance.mesh = mesh
	parent.add_child(instance)
