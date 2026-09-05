extends Control
## Draws the server's map markers over the full map.
##
## The full map frames a whole map at once - 1600 metres across - so a marker
## modelled in the world is roughly one pixel there. The legacy client drew its
## markers on the map window rather than in the world for the same reason, and
## this does the same: the 3D pin is what the minimap shows, and this overlay is
## what the full map shows.
##
## It holds no marker state. `main.gd` hands it the markers the server placed on
## the map the player is standing on, and it projects them through the same
## camera the map image is rendered with, so a marker cannot drift away from the
## map underneath it.

const MARKER_COLOUR := Color(0.98, 0.78, 0.22)
const MARKER_RADIUS := 10.0

## How large a portal's P or an exit's X is drawn, in pixels: a glyph is read
## rather than found, so it is bigger than a pin and its outline is heavy.
const GLYPH_SIZE := 18
const GLYPH_OUTLINE := 4

var _camera: Camera3D
var _adapter: CoordinateAdapter
var _viewport_size := Vector2i.ZERO
var _markers: Array[Dictionary] = []
## The waygates and the ways off the map, each a world `position`, a `glyph`,
## a `colour` and a `label` naming where it leads. `main.gd` hands them over
## whenever the map's objects change.
var _waypoints: Array[Dictionary] = []
## The player's own marks. Drawn in a different colour from the server's, so
## nobody mistakes their own annotation for something the world told them.
var _player_marks: Array[Dictionary] = []

func configure(camera: Camera3D, adapter: CoordinateAdapter,
		viewport_size: Vector2i) -> void:
	_camera = camera
	_adapter = adapter
	_viewport_size = viewport_size
	queue_redraw()

## The markers on the current map, already filtered by `main.gd`.
func set_markers(markers: Array[Dictionary]) -> void:
	_markers = markers
	queue_redraw()

func set_player_marks(marks: Array[Dictionary]) -> void:
	_player_marks = marks
	queue_redraw()

func set_waypoints(waypoints: Array[Dictionary]) -> void:
	_waypoints = waypoints
	queue_redraw()

func waypoint_count() -> int:
	return _waypoints.size()

const PLAYER_MARK_COLOUR := Color(0.50, 0.83, 1.0)

func _draw() -> void:
	if not is_instance_valid(_camera) or _adapter == null:
		return
	if _markers.is_empty() and _player_marks.is_empty() and _waypoints.is_empty():
		return
	var font: Font = get_theme_default_font()
	var font_size: int = get_theme_default_font_size()
	_draw_waypoints(font, font_size)
	_draw_set(_markers, MARKER_COLOUR, font, font_size)
	_draw_set(_player_marks, PLAYER_MARK_COLOUR, font, font_size)

## The P of a waygate and the X of a way off the map, each with the name of
## where it leads beside it. Drawn under the server's own markers, so a pin
## placed on a doorway is still the pin.
func _draw_waypoints(font: Font, font_size: int) -> void:
	if font == null:
		return
	for waypoint: Dictionary in _waypoints:
		var world: Vector3 = waypoint.get("position", Vector3.ZERO) as Vector3
		if _camera.is_position_behind(world):
			continue
		var point_value: Variant = _texture_position(_camera.unproject_position(world))
		if not point_value is Vector2:
			continue
		var point: Vector2 = point_value as Vector2
		var glyph: String = str(waypoint.get("glyph", "X"))
		var colour: Color = waypoint.get("colour", Color.WHITE) as Color
		var extent: Vector2 = font.get_string_size(glyph, HORIZONTAL_ALIGNMENT_LEFT, -1,
			GLYPH_SIZE)
		var baseline := Vector2(point.x - extent.x * 0.5,
			point.y + (font.get_ascent(GLYPH_SIZE) - font.get_descent(GLYPH_SIZE)) * 0.5)
		draw_string_outline(font, baseline, glyph, HORIZONTAL_ALIGNMENT_LEFT, -1,
			GLYPH_SIZE, GLYPH_OUTLINE, Color(0.04, 0.04, 0.05, 0.95))
		draw_string(font, baseline, glyph, HORIZONTAL_ALIGNMENT_LEFT, -1, GLYPH_SIZE, colour)
		var label: String = str(waypoint.get("label", ""))
		if not label.is_empty():
			var at := Vector2(point.x + extent.x * 0.5 + 4.0, point.y + 5.0)
			draw_string_outline(font, at, label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size,
				3, Color(0.04, 0.04, 0.05, 0.9))
			draw_string(font, at, label, HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, colour)

func _draw_set(marks: Array[Dictionary], colour: Color, font: Font,
		font_size: int) -> void:
	for marker: Dictionary in marks:
		var world: Vector3 = _adapter.tile_center(
			int(marker.get("x", 0)), int(marker.get("y", 0)))
		if _camera.is_position_behind(world):
			continue
		var point_value: Variant = _texture_position(
			_camera.unproject_position(world))
		if not point_value is Vector2:
			continue
		var point: Vector2 = point_value as Vector2
		draw_colored_polygon(PackedVector2Array([
			point + Vector2(0.0, -MARKER_RADIUS),
			point + Vector2(MARKER_RADIUS, 0.0),
			point + Vector2(0.0, MARKER_RADIUS),
			point + Vector2(-MARKER_RADIUS, 0.0)]), colour)
		var label: String = str(marker.get("label", ""))
		if not label.is_empty() and font != null:
			draw_string(font, point + Vector2(MARKER_RADIUS + 4.0, 5.0), label,
				HORIZONTAL_ALIGNMENT_LEFT, -1, font_size, colour)

## Viewport pixels to a position on this control, matching the map image's
## keep-aspect-centred stretch. Returns null for a point off the drawn image.
func _texture_position(viewport_position: Vector2) -> Variant:
	var target := Vector2(_viewport_size)
	if size.x <= 0.0 or size.y <= 0.0 or target.x <= 0.0 or target.y <= 0.0:
		return null
	var scale: float = minf(size.x / target.x, size.y / target.y)
	var displayed_size: Vector2 = target * scale
	var displayed_origin: Vector2 = (size - displayed_size) * 0.5
	var point: Vector2 = displayed_origin + viewport_position * scale
	if not Rect2(displayed_origin, displayed_size).has_point(point):
		return null
	return point
