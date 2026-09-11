extends Control
## The continent, as the map window shows it: every region's own tab map laid
## out to scale on one picture, and each of them a rectangle a click opens.
##
## The picture itself is the TextureRect under this control, drawn keep-aspect
## and centred. This control projects each region's rectangle through the same
## fit, names the regions, marks the one under the cursor and the one the
## player is standing on, and reports a click by region index. It holds no map
## state beyond the rectangles it was handed.

signal region_selected(region_index: int)
## -1 when the cursor is over none of them, or has left the map.
signal region_hovered(region_index: int)

const LABEL_SIZE := 15
const LABEL_OUTLINE := 4
const LABEL_COLOUR := Color(0.96, 0.96, 0.98)
const CURRENT_COLOUR := Color(0.98, 0.78, 0.22)
const HOVER_COLOUR := Color(1.0, 0.92, 0.55)
const OUTLINE_COLOUR := Color(1.0, 1.0, 1.0, 0.28)
const OUTLINE_WIDTH := 1.0
const CURRENT_WIDTH := 2.0
const HOVER_WIDTH := 3.0
## The smallest region is 191 m across, which at the window's scale is a
## square a few dozen pixels wide. Its click target grows to this so a mouse
## can still find it; the drawn rectangle stays the region's true size.
const MIN_HIT_SIZE := 44.0

var _image_size := Vector2.ZERO
var _regions: Array[Dictionary] = []
var _current_index := -1
var _hovered_index := -1

## `regions` carries a `name` and a `rect` in the picture's own pixels.
func configure(image_size: Vector2, regions: Array[Dictionary]) -> void:
	_image_size = image_size
	_regions = regions
	_hovered_index = -1
	queue_redraw()

func region_count() -> int:
	return _regions.size()

func set_current_region(index: int) -> void:
	_current_index = index
	queue_redraw()

func hovered_region() -> int:
	return _hovered_index

## Where the picture lands within this control: the keep-aspect, centred fit
## the TextureRect underneath uses.
func display_rect() -> Rect2:
	if _image_size.x <= 0.0 or _image_size.y <= 0.0 or size.x <= 0.0 or size.y <= 0.0:
		return Rect2()
	var scale_factor: float = minf(size.x / _image_size.x, size.y / _image_size.y)
	var displayed: Vector2 = _image_size * scale_factor
	return Rect2((size - displayed) * 0.5, displayed)

## A region's rectangle in this control's pixels.
func region_rect(index: int) -> Rect2:
	var display: Rect2 = display_rect()
	if index < 0 or index >= _regions.size() or display.size.x <= 0.0:
		return Rect2()
	var rect: Rect2 = _regions[index].get("rect", Rect2()) as Rect2
	var scale_factor: float = display.size.x / _image_size.x
	return Rect2(display.position + rect.position * scale_factor, rect.size * scale_factor)

## The rectangle a click has to land in, never smaller than a mouse can aim at.
func hit_rect(index: int) -> Rect2:
	var rect: Rect2 = region_rect(index)
	if rect.size.x <= 0.0:
		return rect
	var grown := Vector2(maxf(rect.size.x, MIN_HIT_SIZE), maxf(rect.size.y, MIN_HIT_SIZE))
	return Rect2(rect.get_center() - grown * 0.5, grown)

## The region under a point, or -1. A small region's grown target can sit
## inside a large neighbour's rectangle; the smaller one wins, being the one
## that would otherwise be unreachable.
func region_at(local_position: Vector2) -> int:
	var best := -1
	var best_area := INF
	for index: int in range(_regions.size()):
		var rect: Rect2 = hit_rect(index)
		if rect.size.x > 0.0 and rect.has_point(local_position) and rect.get_area() < best_area:
			best = index
			best_area = rect.get_area()
	return best

func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		_set_hovered(region_at((event as InputEventMouseMotion).position))
		return
	if not event is InputEventMouseButton:
		return
	var button: InputEventMouseButton = event as InputEventMouseButton
	if not button.pressed or button.button_index != MOUSE_BUTTON_LEFT:
		return
	var index: int = region_at(button.position)
	if index < 0:
		return
	accept_event()
	region_selected.emit(index)

func _notification(what: int) -> void:
	if what == NOTIFICATION_MOUSE_EXIT or what == NOTIFICATION_VISIBILITY_CHANGED:
		_set_hovered(-1)

func _set_hovered(index: int) -> void:
	if index == _hovered_index:
		return
	_hovered_index = index
	queue_redraw()
	region_hovered.emit(index)

func _draw() -> void:
	if display_rect().size.x <= 0.0:
		return
	for index: int in range(_regions.size()):
		var rect: Rect2 = region_rect(index)
		if rect.size.x <= 0.0:
			continue
		if index == _hovered_index:
			draw_rect(rect, Color(HOVER_COLOUR, 0.12), true)
			draw_rect(rect, HOVER_COLOUR, false, HOVER_WIDTH)
		elif index == _current_index:
			draw_rect(rect, CURRENT_COLOUR, false, CURRENT_WIDTH)
		else:
			draw_rect(rect, OUTLINE_COLOUR, false, OUTLINE_WIDTH)
	var font: Font = get_theme_default_font()
	if font == null:
		return
	for index: int in range(_regions.size()):
		var rect: Rect2 = region_rect(index)
		if rect.size.x <= 0.0:
			continue
		_draw_label(font, rect, str(_regions[index].get("name", "")),
			CURRENT_COLOUR if index == _current_index else LABEL_COLOUR)

## The name sits along the bottom edge of a region big enough to leave its
## map readable above it, and across the middle of one that is not. It is
## centred on the region by measuring it rather than by fitting it to the
## rectangle: a name wider than a small region runs past its edges, which
## reads, where a name cut to "Whitehorn R" does not.
func _draw_label(font: Font, rect: Rect2, text: String, colour: Color) -> void:
	if text.is_empty():
		return
	var ascent: float = font.get_ascent(LABEL_SIZE)
	var descent: float = font.get_descent(LABEL_SIZE)
	var baseline_y: float
	if rect.size.y > (ascent + descent) * 3.0:
		baseline_y = rect.end.y - descent - 4.0
	else:
		baseline_y = rect.get_center().y + (ascent - descent) * 0.5
	var extent: Vector2 = font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE)
	var baseline := Vector2(rect.get_center().x - extent.x * 0.5, baseline_y)
	draw_string_outline(font, baseline, text, HORIZONTAL_ALIGNMENT_LEFT, -1,
		LABEL_SIZE, LABEL_OUTLINE, Color(0.04, 0.04, 0.05, 0.95))
	draw_string(font, baseline, text, HORIZONTAL_ALIGNMENT_LEFT, -1, LABEL_SIZE, colour)
