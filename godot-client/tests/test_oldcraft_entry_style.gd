extends SceneTree

const EntryStyle := preload("res://src/ui/oldcraft_entry_style.gd")

var failures := 0
var checks := 0


func _init() -> void:
	call_deferred("_run")


func _expect(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _run() -> void:
	root.size = Vector2i(1280, 720)
	var main := (load("res://src/app/main.tscn") as PackedScene).instantiate() as Control
	root.add_child(main)
	await process_frame
	EntryStyle.apply(main)
	var login := main.get_node("%LoginPanel") as PanelContainer
	var creation := main.get_node("%CreationPanel") as PanelContainer
	var login_frame := login.get_theme_stylebox("panel") as StyleBoxFlat
	var creation_frame := creation.get_theme_stylebox("panel") as StyleBoxFlat
	_expect(login_frame != null and login_frame.border_width_left >= 5,
		"login uses a heavy stone frame")
	_expect(creation_frame != null and creation_frame.border_color.is_equal_approx(
		EntryStyle.GOLD_DARK), "creation uses the same forged frame")
	var rail_frame := (main.get_node("%ClassRail") as PanelContainer).get_theme_stylebox(
		"panel") as StyleBoxFlat
	_expect(rail_frame != null and rail_frame.border_width_left == 3,
		"creation class icons sit in a compact stone rail")
	var selected_class_frame := (main.get_node("%ClassChoice0") as Button).get_theme_stylebox(
		"pressed") as StyleBoxFlat
	_expect(selected_class_frame != null and selected_class_frame.border_width_left == 4 and
		selected_class_frame.border_color.is_equal_approx(EntryStyle.GOLD_BRIGHT),
		"selected class gets an unmistakable bright brass frame")
	var form_frame := (main.get_node("%FormPanel") as PanelContainer).get_theme_stylebox(
		"panel") as StyleBoxFlat
	_expect(form_frame != null and form_frame.bg_color.is_equal_approx(
		Color(EntryStyle.PARCHMENT, 0.965)), "creation form uses parchment chrome")
	var login_button := main.get_node("%Login") as Button
	var normal := login_button.get_theme_stylebox("normal") as StyleBoxFlat
	_expect(normal != null and normal.bg_color.r > normal.bg_color.g * 4.0,
		"primary actions use Oldcraft burgundy")
	_expect(login_button.get_theme_color("font_color").r > 0.85,
		"action text stays warm and readable")
	var username := main.get_node("%Username") as LineEdit
	_expect((username.get_theme_stylebox("normal") as StyleBoxFlat).border_width_left == 2,
		"entry fields are inset and bordered")
	_expect((main.get_node("LoginPanel/Content/Subtitle") as Label).text ==
		"ENTER THE WORLD OF ELORIA", "Eloria identity is retained")
	var environment := (main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport/PreviewRoot/PreviewEnvironment") \
		as WorldEnvironment).environment
	_expect(environment.background_color.is_equal_approx(EntryStyle.PREVIEW_SKY),
		"creation preview keeps transparent moonlit ambient lighting")
	_expect((main.get_node(
		"CreationPanel/Columns/CharacterPreview/Viewport") as SubViewport).transparent_bg,
		"live character is composited over the painted stage")
	_expect(main.get_node_or_null("%CreationBackdrop") is TextureRect and
		main.get_node_or_null("%ClassChoice3") is Button,
		"creation exposes a scenic backdrop and four-class icon rail")
	var stage := main.get_node_or_null("%PreviewRoot/OldcraftStage")
	_expect(stage != null and stage.get_child_count() == 2,
		"creation preview has a lightweight two-piece plinth")
	EntryStyle.apply(main)
	_expect((main.get_node("%PreviewRoot/OldcraftStage") as Node).get_child_count() == 2,
		"re-applying entry style does not duplicate stage geometry")
	main.queue_free()
	await process_frame
	NativeAnimationImporter.clear()
	print("oldcraft entry style: %s (%d checks)" % [
		"PASS" if failures == 0 else "FAIL", checks])
	quit(1 if failures else 0)
