class_name WorldEffect3D
extends Node3D
## One short-lived effect the server said happened in the world.
##
## `SEND_SPECIAL_EFFECT(79)` names an effect id and the actor it happened to,
## plus a second actor when the effect travels between two. The client had no
## decoder for it at all, so a swarm of bees interrupting a harvest, a lucky
## find, or a spell landing on someone all happened with nothing on screen.
##
## The visual is generated here rather than drawn from artwork: an expanding
## unshaded ring, and a beam when the server named a second actor. It is
## deliberately abstract - it says something happened here, and where it went -
## because the effect ids are a legacy namespace and inventing a distinct piece
## of art per id would be inventing meaning the server never sent.

const LIFETIME_SECONDS := 0.9
const RING_RADIUS := 1.4

## The effect classes the server actually uses, by the palette they draw in.
## Everything else is neutral rather than guessed at.
const HARM_EFFECTS: Array[int] = [0, 2, 5, 17]
const BLESSING_EFFECTS: Array[int] = [1, 4, 9, 12, 14]

var effect_id: int = -1
var elapsed: float = 0.0

var _ring: MeshInstance3D
var _beam: MeshInstance3D
var _material: StandardMaterial3D

func configure(effect: int, origin: Vector3, target: Variant = null) -> void:
	effect_id = effect
	global_position = origin
	_material = StandardMaterial3D.new()
	_material.albedo_color = _palette()
	_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	var ring_mesh := TorusMesh.new()
	ring_mesh.inner_radius = RING_RADIUS * 0.82
	ring_mesh.outer_radius = RING_RADIUS
	ring_mesh.material = _material
	_ring = MeshInstance3D.new()
	_ring.name = "EffectRing"
	_ring.mesh = ring_mesh
	_ring.position.y = 0.2
	add_child(_ring)
	if target is Vector3:
		_add_beam(target as Vector3)

## A beam only exists when the server named a second actor: the effect went
## from one to the other, and that is the server's statement, not a guess.
func _add_beam(target: Vector3) -> void:
	var to_target: Vector3 = target - global_position
	var length: float = to_target.length()
	if length < 0.05:
		return
	var beam_mesh := CylinderMesh.new()
	beam_mesh.top_radius = 0.06
	beam_mesh.bottom_radius = 0.06
	beam_mesh.height = length
	beam_mesh.material = _material
	_beam = MeshInstance3D.new()
	_beam.name = "EffectBeam"
	_beam.mesh = beam_mesh
	_beam.position = to_target * 0.5 + Vector3(0.0, 1.0, 0.0)
	_beam.look_at_from_position(_beam.position,
		_beam.position + to_target.normalized(), Vector3.UP)
	_beam.rotate_object_local(Vector3.RIGHT, PI * 0.5)
	add_child(_beam)

func _palette() -> Color:
	if effect_id in HARM_EFFECTS:
		return Color(0.92, 0.34, 0.28)
	if effect_id in BLESSING_EFFECTS:
		return Color(0.46, 0.86, 0.52)
	return Color(0.62, 0.74, 0.98)

func _process(delta: float) -> void:
	elapsed += delta
	var progress: float = clampf(elapsed / LIFETIME_SECONDS, 0.0, 1.0)
	if is_instance_valid(_ring):
		var scale_factor: float = 0.4 + progress * 1.6
		_ring.scale = Vector3(scale_factor, 1.0, scale_factor)
	if _material != null:
		_material.albedo_color.a = 1.0 - progress
	if progress >= 1.0:
		queue_free()
