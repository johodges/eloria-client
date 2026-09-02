class_name IsometricCameraController
extends Node3D

@export_range(-80.0, -15.0) var pitch_degrees := -60.0
@export var yaw_degrees := 0.0
@export_range(3.0, 100.0) var distance := 26.0
@export var zoom_step := 2.5
@export var rotation_sensitivity := 0.25
@export var pan_sensitivity := 0.012
# The rig never brings the camera nearer than this to its focus, which is what
# lets `main.tscn` carry a 1 m near plane. That matters: the client renders
# through GL Compatibility, whose depth buffer is fixed-point, so the resolvable
# depth step at distance z is about z^2 / (near * 2^24) metres. At the engine
# default near of 0.05 that is 12 mm at 100 m and 48 mm at 200 m, and every
# authored 5 mm clearance in the map kits shimmers; at 1 m it is 0.6 mm and
# 2.4 mm. Three metres is as near as that near plane allows without clipping
# into the focused actor; going below it means revisiting the near plane.
# Interiors keep their own tighter limits through their manifests' camera
# blocks, which override these.
@export var min_distance := 3.0
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
