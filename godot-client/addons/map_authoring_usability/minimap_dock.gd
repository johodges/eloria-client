@tool
extends EditorDock
## A live minimap of the open territory: a top-down render (north up) with the
## editor camera, the selection, gameplay markers and the play-test walker
## drawn over it. Click or drag on it to move the 3D view there.
##
## The picture is rendered in memory from the scene itself (the same capture as
## Map tools > Capture top-down image, at a low resolution) when a territory
## opens and on Refresh; the overlays follow the scene continuously.

signal jump_requested(local: Vector3)
signal refresh_requested

var _view: MinimapView
var _status: Label
var _refresh: Button


func _init() -> void:
	title = "Minimap"
	layout_key = "MapAuthoringMinimap"
	default_slot = EditorDock.DOCK_SLOT_LEFT_BR
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(column)
	var row := HBoxContainer.new()
	_refresh = Button.new()
	_refresh.text = "Refresh"
	_refresh.tooltip_text = "Render the minimap again from the scene (after large edits)."
	_refresh.pressed.connect(func() -> void: refresh_requested.emit())
	row.add_child(_refresh)
	_status = Label.new()
	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.clip_text = true
	_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	row.add_child(_status)
	column.add_child(row)
	_view = MinimapView.new()
	_view.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_view.custom_minimum_size = Vector2(160, 160)
	_view.jump_requested.connect(func(local: Vector3) -> void: jump_requested.emit(local))
	column.add_child(_view)


## A new picture: `framing` from top_down_capture.plan (territory-local rect).
func set_image(image: Image, framing: Dictionary) -> void:
	_view.texture = ImageTexture.create_from_image(image) if image != null else null
	_view.framing = framing
	_view.queue_redraw()


func clear(message: String = "") -> void:
	_view.texture = null
	_view.framing = {}
	_view.state = {}
	_view.queue_redraw()
	set_status(message)


func set_status(message: String) -> void:
	_status.text = message
	_status.tooltip_text = message


## Overlay state: camera (local position and forward), selected local points,
## markers [[local, colour]], walker local position and route.
func set_state(state: Dictionary) -> void:
	_view.state = state
	_view.queue_redraw()


func view() -> Control:
	return _view


func framing() -> Dictionary:
	return _view.framing


class MinimapView extends Control:
	signal jump_requested(local: Vector3)

	var texture: Texture2D
	var framing: Dictionary = {}
	var state: Dictionary = {}
	var _dragging := false

	func _init() -> void:
		mouse_default_cursor_shape = Control.CURSOR_CROSS
		clip_contents = true

	## Where the picture sits inside the control (aspect kept, centred).
	func image_rect() -> Rect2:
		if framing.is_empty():
			return Rect2()
		var rect: Rect2 = framing.rect
		var aspect := rect.size.x / maxf(rect.size.y, 0.001)
		var fit := size
		if fit.x / maxf(fit.y, 0.001) > aspect:
			fit.x = fit.y * aspect
		else:
			fit.y = fit.x / aspect
		return Rect2((size - fit) * 0.5, fit)

	func to_view(local: Vector3) -> Vector2:
		var shown := image_rect()
		var rect: Rect2 = framing.rect
		return shown.position + Vector2((local.x - rect.position.x) / rect.size.x * shown.size.x,
			(local.z - rect.position.y) / rect.size.y * shown.size.y)

	func to_territory(point: Vector2) -> Vector3:
		var shown := image_rect()
		var rect: Rect2 = framing.rect
		var u := (point.x - shown.position.x) / maxf(shown.size.x, 0.001)
		var v := (point.y - shown.position.y) / maxf(shown.size.y, 0.001)
		return Vector3(rect.position.x + u * rect.size.x, 0.0, rect.position.y + v * rect.size.y)

	func _gui_input(event: InputEvent) -> void:
		if framing.is_empty():
			return
		if event is InputEventMouseButton and (event as InputEventMouseButton).button_index == \
				MOUSE_BUTTON_LEFT:
			_dragging = event.pressed
			if event.pressed and image_rect().has_point(event.position):
				jump_requested.emit(to_territory(event.position))
			accept_event()
		elif event is InputEventMouseMotion and _dragging and \
				image_rect().has_point(event.position):
			jump_requested.emit(to_territory(event.position))
			accept_event()

	func _draw() -> void:
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.08, 0.09, 0.1))
		if framing.is_empty():
			return
		var shown := image_rect()
		if texture != null:
			draw_texture_rect(texture, shown, false)
		else:
			draw_rect(shown, Color(0.18, 0.2, 0.2))
		for marker: Array in state.get("markers", []):
			draw_circle(to_view(marker[0] as Vector3), 2.0, marker[1] as Color)
		var route: PackedVector3Array = state.get("route", PackedVector3Array())
		if route.size() >= 2:
			var points := PackedVector2Array()
			for point in route:
				points.append(to_view(point))
			draw_polyline(points, Color(1.0, 0.9, 0.35), 1.5)
		for point: Vector3 in state.get("selection", []):
			var at := to_view(point)
			draw_rect(Rect2(at - Vector2(3, 3), Vector2(6, 6)), Color(1.0, 0.55, 0.15), false, 1.5)
		var walker: Variant = state.get("walker")
		if walker is Vector3 and (walker as Vector3).is_finite():
			draw_circle(to_view(walker as Vector3), 4.0, Color(1.0, 0.78, 0.18))
		var camera: Variant = state.get("camera")
		if camera is Vector3:
			var at := to_view(camera as Vector3)
			var forward: Vector3 = state.get("camera_forward", Vector3.FORWARD)
			var heading := Vector2(forward.x, forward.z)
			if heading.length_squared() > 0.0001:
				heading = heading.normalized()
				var side := Vector2(-heading.y, heading.x)
				draw_colored_polygon(PackedVector2Array([at, at + heading * 22.0 + side * 12.0,
					at + heading * 22.0 - side * 12.0]), Color(0.45, 0.8, 1.0, 0.35))
			draw_circle(at, 4.5, Color(0.1, 0.1, 0.1))
			draw_circle(at, 3.0, Color(0.45, 0.8, 1.0))
