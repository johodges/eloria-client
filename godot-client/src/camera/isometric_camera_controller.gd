class_name IsometricCameraController
extends Node3D

@export_range(-80.0, -15.0) var pitch_degrees := -52.0
@export var yaw_degrees := 0.0
@export_range(3.0, 100.0) var distance := 34.0
@export var zoom_step := 2.5
@export var rotation_sensitivity := 0.25
@export var pan_sensitivity := 0.012
@export var min_distance := 8.0
@export var max_distance := 90.0

@onready var camera: Camera3D = %Camera

var focus := Vector3.ZERO
var pan_offset := Vector3.ZERO
var _rotating := false
var _panning := false

func _ready() -> void:
	_update_camera()

func set_focus(value: Vector3) -> void:
	focus = value
	_update_camera()

func handle_mouse_button(event: InputEventMouseButton) -> bool:
	if event.button_index == MOUSE_BUTTON_RIGHT:
		_rotating = event.pressed
		return true
	if event.button_index == MOUSE_BUTTON_MIDDLE:
		_panning = event.pressed
		return true
	if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
		distance = clampf(distance - zoom_step, min_distance, max_distance)
		_update_camera()
		return true
	if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
		distance = clampf(distance + zoom_step, min_distance, max_distance)
		_update_camera()
		return true
	return false

func handle_mouse_motion(event: InputEventMouseMotion) -> bool:
	if _rotating:
		yaw_degrees -= event.relative.x * rotation_sensitivity
		pitch_degrees = clampf(pitch_degrees - event.relative.y * rotation_sensitivity, -80.0, -15.0)
		_update_camera()
		return true
	if _panning:
		var right := camera.global_basis.x
		var forward := -camera.global_basis.z
		right.y = 0.0
		forward.y = 0.0
		pan_offset += (-right.normalized() * event.relative.x
			+ forward.normalized() * event.relative.y) * distance * pan_sensitivity
		_update_camera()
		return true
	return false

func screen_to_ground(screen_position: Vector2, ground_height: float) -> Variant:
	var origin := camera.project_ray_origin(screen_position)
	var direction := camera.project_ray_normal(screen_position)
	if absf(direction.y) < 0.0001:
		return null
	var distance_to_plane := (ground_height - origin.y) / direction.y
	if distance_to_plane < 0.0:
		return null
	return origin + direction * distance_to_plane

func ray_origin(screen_position: Vector2) -> Vector3:
	return camera.project_ray_origin(screen_position)

func ray_direction(screen_position: Vector2) -> Vector3:
	return camera.project_ray_normal(screen_position)

func camera_diagnostics() -> Dictionary:
	return {
		"focus": focus,
		"pan_offset": pan_offset,
		"rig_transform": global_transform,
		"camera_transform": camera.global_transform if is_instance_valid(camera) else Transform3D.IDENTITY,
		"yaw_degrees": yaw_degrees,
		"pitch_degrees": pitch_degrees,
		"distance": distance,
	}

func reset_pan() -> void:
	pan_offset = Vector3.ZERO
	_update_camera()

func _update_camera() -> void:
	if not is_instance_valid(camera):
		return
	var yaw := deg_to_rad(yaw_degrees)
	var pitch := deg_to_rad(pitch_degrees)
	var offset := Vector3(
		sin(yaw) * cos(pitch),
		-sin(pitch),
		cos(yaw) * cos(pitch)) * distance
	global_position = focus + pan_offset
	camera.position = offset
	camera.look_at(global_position + Vector3.UP * 1.2, Vector3.UP)
