class_name WorldEffect3D
extends Node3D
## One short-lived effect the server said happened in the world.
##
## `SEND_SPECIAL_EFFECT(79)` names an effect id and the actor it happened to,
## plus a second actor when the effect travels between two. The client had no
## decoder for it and no particle system of any kind, so a swarm of bees
## interrupting a harvest, a lucky find, or a spell landing on someone all
## happened with nothing on screen.
##
## The effect ids are a legacy namespace with no names on the wire, so this
## does not invent a distinct piece of art per id. It sorts them into the three
## classes the server actually uses - something harmful, something beneficial,
## anything else - and gives each a generated burst: particles rising from the
## actor, a ground ring, and a beam when the server named a second actor.
## Everything is built from primitives and shaded colour; nothing is imported.

## The visual layer the gameplay camera renders. Effects are not navigation
## aids, so unlike map markers they belong in the world view.
const GAMEPLAY_LAYER := 1
const LIFETIME_SECONDS := 1.1
const RING_RADIUS := 1.4
const PARTICLE_COUNT := 48

## The effect classes the server actually uses, by the palette they draw in.
## Everything else is neutral rather than guessed at.
const HARM_EFFECTS: Array[int] = [0, 2, 5, 17]
const BLESSING_EFFECTS: Array[int] = [1, 4, 9, 12, 14]

var effect_id: int = -1
var elapsed: float = 0.0

var _ring: MeshInstance3D
var _beam: MeshInstance3D
var _burst: GPUParticles3D
var _material: StandardMaterial3D

func configure(effect: int, origin: Vector3, target: Variant = null) -> void:
	effect_id = effect
	global_position = origin
	var palette: Color = _palette()
	_material = StandardMaterial3D.new()
	_material.albedo_color = palette
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
	_add_burst(palette)
	if target is Vector3:
		_add_beam(target as Vector3)

## The particles themselves. A harmful effect falls inwards and a beneficial
## one rises, which is the one piece of meaning the server's own grouping
## supports; everything else drifts.
func _add_burst(palette: Color) -> void:
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	process.emission_sphere_radius = 0.55
	process.direction = Vector3(0.0, 1.0, 0.0)
	process.spread = 32.0
	process.initial_velocity_min = 1.4
	process.initial_velocity_max = 3.1
	process.gravity = Vector3(0.0, 3.6 if effect_id in HARM_EFFECTS else -1.1, 0.0)
	process.scale_min = 0.35
	process.scale_max = 0.85
	process.color = palette
	var fade := Gradient.new()
	fade.set_color(0, Color(palette.r, palette.g, palette.b, 1.0))
	fade.set_color(1, Color(palette.r, palette.g, palette.b, 0.0))
	var ramp := GradientTexture1D.new()
	ramp.gradient = fade
	process.color_ramp = ramp

	# A soft radial dot, generated rather than imported: a bare quad reads as a
	# hard square at any camera distance.
	var glow := Gradient.new()
	glow.set_color(0, Color(1.0, 1.0, 1.0, 1.0))
	glow.set_color(1, Color(1.0, 1.0, 1.0, 0.0))
	var dot_texture := GradientTexture2D.new()
	dot_texture.gradient = glow
	dot_texture.fill = GradientTexture2D.FILL_RADIAL
	dot_texture.fill_from = Vector2(0.5, 0.5)
	dot_texture.fill_to = Vector2(1.0, 0.5)
	dot_texture.width = 32
	dot_texture.height = 32

	var dot := StandardMaterial3D.new()
	dot.albedo_color = palette
	dot.albedo_texture = dot_texture
	dot.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dot.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dot.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	dot.vertex_color_use_as_albedo = true
	dot.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	var quad := QuadMesh.new()
	quad.size = Vector2(0.42, 0.42)
	quad.material = dot

	_burst = GPUParticles3D.new()
	_burst.name = "EffectBurst"
	_burst.amount = PARTICLE_COUNT
	_burst.lifetime = LIFETIME_SECONDS * 0.8
	_burst.one_shot = true
	_burst.explosiveness = 0.85
	_burst.process_material = process
	_burst.draw_pass_1 = quad
	_burst.layers = GAMEPLAY_LAYER
	_burst.position.y = 0.9
	add_child(_burst)
	_burst.emitting = true

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
