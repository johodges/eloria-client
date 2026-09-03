class_name InvasionMapCanvas
extends Control

signal coordinate_selected(tile: Vector2i)

const PAD := 16.0
const GRID_COLOR := Color("324454")
const LOCATION_COLOR := Color("c8a8ff")
const PORTAL_COLOR := Color("55cfee")
const PLAYER_COLOR := Color("68e7ff")
const INVASION_COLOR := Color("ff6b63")
const BOSS_COLOR := Color("ffc94f")
const MARKER_FONT_SIZE := 10

var state: Dictionary = {}
var selected_tile := Vector2i(-1, -1)
var background: Texture2D
var _hover_text := ""


func _ready() -> void:
	custom_minimum_size = Vector2(238, 188)
	mouse_default_cursor_shape = Control.CURSOR_CROSS
	# A marker near the right edge draws its name past the canvas, where the
	# roster is; unclipped, the two read as one smeared column.
	clip_contents = true
	mouse_filter = Control.MOUSE_FILTER_STOP
	set_process(false)


func set_map_state(value: Dictionary, texture: Texture2D = null) -> void:
	var previous_map := str((state.get("map", {}) as Dictionary).get("id", ""))
	var next_map := str((value.get("map", {}) as Dictionary).get("id", ""))
	state = value.duplicate(true)
	background = texture
	if previous_map != next_map:
		selected_tile = Vector2i(-1, -1)
	_hover_text = ""
	tooltip_text = "Click the tactical map to select teleport coordinates."
	queue_redraw()


func _map_rect() -> Rect2:
	return Rect2(Vector2(PAD, PAD), Vector2(
		maxf(1.0, size.x - PAD * 2.0), maxf(1.0, size.y - PAD * 2.0)))


func _bounds() -> Vector2:
	var map: Dictionary = state.get("map", {}) as Dictionary
	return Vector2(maxf(1.0, float(map.get("width", 2048))),
		maxf(1.0, float(map.get("height", 2048))))


func _point(tile: Vector2) -> Vector2:
	var rect := _map_rect()
	var bounds := _bounds()
	return rect.position + Vector2(
		clampf(tile.x / bounds.x, 0.0, 1.0) * rect.size.x,
		clampf(tile.y / bounds.y, 0.0, 1.0) * rect.size.y)


func _tile(point: Vector2) -> Vector2i:
	var rect := _map_rect()
	var bounds := _bounds()
	var relative := (point - rect.position) / rect.size
	return Vector2i(clampi(roundi(relative.x * bounds.x), 0, int(bounds.x) - 1),
		clampi(roundi(relative.y * bounds.y), 0, int(bounds.y) - 1))


func _draw() -> void:
	var rect := _map_rect()
	draw_rect(Rect2(Vector2.ZERO, size), Color("101820"), true)
	if background != null:
		draw_texture_rect(background, rect, false, Color(1, 1, 1, 0.68))
	else:
		draw_rect(rect, Color("182734"), true)
	for step: int in range(1, 8):
		var fraction := float(step) / 8.0
		draw_line(Vector2(rect.position.x + rect.size.x * fraction, rect.position.y),
			Vector2(rect.position.x + rect.size.x * fraction, rect.end.y), GRID_COLOR, 1.0)
		draw_line(Vector2(rect.position.x, rect.position.y + rect.size.y * fraction),
			Vector2(rect.end.x, rect.position.y + rect.size.y * fraction), GRID_COLOR, 1.0)
	draw_rect(rect, Color("7392a6"), false, 2.0)

	var font: Font = ThemeDB.fallback_font
	for raw_location: Variant in state.get("locations", []):
		var location := raw_location as Dictionary
		var point := _point(Vector2(float(location.get("x", 0)), float(location.get("y", 0))))
		var color := PORTAL_COLOR if str(location.get("kind", "")) == "portal" else LOCATION_COLOR
		draw_rect(Rect2(point - Vector2(3, 3), Vector2(6, 6)), color, true)
		draw_string(font, point + Vector2(6, -4), str(location.get("name", "Location")),
			HORIZONTAL_ALIGNMENT_LEFT, -1.0, MARKER_FONT_SIZE, Color.WHITE)
	for raw_player: Variant in state.get("players", []):
		var player := raw_player as Dictionary
		var point := _point(Vector2(float(player.get("x", 0)), float(player.get("y", 0))))
		draw_circle(point, 4.5, PLAYER_COLOR)
		draw_circle(point, 1.5, Color.WHITE)
		draw_string(font, point + Vector2(6, 3), str(player.get("name", "Player")),
			HORIZONTAL_ALIGNMENT_LEFT, -1.0, MARKER_FONT_SIZE, PLAYER_COLOR)
	for raw_creature: Variant in state.get("creatures", []):
		var creature := raw_creature as Dictionary
		var point := _point(Vector2(float(creature.get("x", 0)), float(creature.get("y", 0))))
		var color := BOSS_COLOR if bool(creature.get("boss", false)) else INVASION_COLOR
		var diamond := PackedVector2Array([
			point + Vector2(0, -5), point + Vector2(5, 0),
			point + Vector2(0, 5), point + Vector2(-5, 0)])
		draw_colored_polygon(diamond, color)
	if selected_tile.x >= 0:
		var selected_point := _point(Vector2(selected_tile))
		draw_circle(selected_point, 7.0, Color("f4ef7a"), false, 2.0)
		draw_line(selected_point - Vector2(10, 0), selected_point + Vector2(10, 0),
			Color("f4ef7a"), 1.0)
		draw_line(selected_point - Vector2(0, 10), selected_point + Vector2(0, 10),
			Color("f4ef7a"), 1.0)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button := event as InputEventMouseButton
		if button.button_index == MOUSE_BUTTON_LEFT and button.pressed \
				and _map_rect().has_point(button.position):
			selected_tile = _tile(button.position)
			coordinate_selected.emit(selected_tile)
			queue_redraw()
			accept_event()
	elif event is InputEventMouseMotion:
		_update_hover((event as InputEventMouseMotion).position)


func _update_hover(position: Vector2) -> void:
	if not _map_rect().has_point(position):
		tooltip_text = "Click the tactical map to select teleport coordinates."
		return
	var nearest_text := ""
	var nearest_distance := 10.0
	for key: String in ["locations", "players", "creatures"]:
		for raw_marker: Variant in state.get(key, []):
			var marker := raw_marker as Dictionary
			var marker_point := _point(Vector2(float(marker.get("x", 0)),
				float(marker.get("y", 0))))
			var distance := marker_point.distance_to(position)
			if distance < nearest_distance:
				nearest_distance = distance
				nearest_text = "%s — %d, %d" % [str(marker.get("name", key)),
					int(marker.get("x", 0)), int(marker.get("y", 0))]
	var tile := _tile(position)
	tooltip_text = nearest_text if not nearest_text.is_empty() else "%d, %d" % [tile.x, tile.y]
