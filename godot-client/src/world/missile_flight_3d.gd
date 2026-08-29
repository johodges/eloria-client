class_name MissileFlight3D
extends Node3D
## One arrow, in flight between the two actors the server named.
##
## `MISSILE_AIM_A_AT_B(84)` and `MISSILE_FIRE_A_TO_B(86)` were undecoded, so a
## ranged fight was two actors standing still while damage numbers appeared:
## nothing was ever drawn between them.
##
## The flight is presentation over an event that has already happened - the
## server resolves the shot on its own and sends the damage separately - so
## this decides nothing. It travels from where the shooter stood to where the
## target stood, in the time the shot is given, and frees itself.

const FLIGHT_SECONDS := 0.25
## An arrow at true scale is two pixels at gameplay camera distance, which is
## no better than drawing nothing. The shaft is drawn thicker than life and
## given a bright trail so the shot reads as a shot.
const SHAFT_LENGTH := 1.3
const SHAFT_RADIUS := 0.07
const TRAIL_LENGTH := 2.6
const ARROW_COLOUR := Color(0.98, 0.92, 0.66)
const TRAIL_COLOUR := Color(1.0, 0.86, 0.45, 0.55)

var origin := Vector3.ZERO
var destination := Vector3.ZERO
var elapsed := 0.0

var _shaft: MeshInstance3D
var _trail: MeshInstance3D

func configure(from_position: Vector3, to_position: Vector3) -> void:
	origin = from_position + Vector3(0.0, 1.1, 0.0)
	destination = to_position + Vector3(0.0, 1.0, 0.0)
	global_position = origin
	var material := StandardMaterial3D.new()
	material.albedo_color = ARROW_COLOUR
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	var shaft_mesh := CylinderMesh.new()
	shaft_mesh.top_radius = SHAFT_RADIUS
	shaft_mesh.bottom_radius = SHAFT_RADIUS
	shaft_mesh.height = SHAFT_LENGTH
	shaft_mesh.material = material
	_shaft = MeshInstance3D.new()
	_shaft.name = "Shaft"
	_shaft.mesh = shaft_mesh
	add_child(_shaft)

	var trail_material := StandardMaterial3D.new()
	trail_material.albedo_color = TRAIL_COLOUR
	trail_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	trail_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	trail_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	var trail_mesh := CylinderMesh.new()
	trail_mesh.top_radius = SHAFT_RADIUS * 0.35
	trail_mesh.bottom_radius = SHAFT_RADIUS * 0.9
	trail_mesh.height = TRAIL_LENGTH
	trail_mesh.material = trail_material
	_trail = MeshInstance3D.new()
	_trail.name = "Trail"
	_trail.mesh = trail_mesh
	add_child(_trail)
	_point_along(destination - origin)

func _point_along(direction: Vector3) -> void:
	if direction.length_squared() < 0.0001:
		return
	var up: Vector3 = (Vector3.UP if absf(direction.normalized().dot(Vector3.UP))
		< 0.999 else Vector3.FORWARD)
	for part: MeshInstance3D in [_shaft, _trail]:
		part.look_at_from_position(Vector3.ZERO, direction.normalized(), up)
		part.rotate_object_local(Vector3.RIGHT, PI * 0.5)
	# The trail sits behind the head, along the path already flown.
	_trail.position = -direction.normalized() * (TRAIL_LENGTH * 0.5)

func _process(delta: float) -> void:
	elapsed += delta
	var progress: float = clampf(elapsed / FLIGHT_SECONDS, 0.0, 1.0)
	global_position = origin.lerp(destination, progress)
	if progress >= 1.0:
		queue_free()
