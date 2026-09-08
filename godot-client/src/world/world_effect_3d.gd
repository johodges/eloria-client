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
## Palettes and motion follow the server's effect_by_spell mapping: healing
## rises, wards orbit, harmful impacts scatter. Thin runes and soft particles
## read at gameplay distance without covering the actor in an opaque ring.

## The visual layer the gameplay camera renders. Effects are not navigation
## aids, so unlike map markers they belong in the world view.
const GAMEPLAY_LAYER := 1
const LIFETIME_SECONDS := 1.1
const RING_RADIUS := 0.72
const PARTICLE_COUNT := 32
const SpellFlight = preload("res://src/world/spell_flight_3d.gd")

## The effect classes the server actually uses, by the palette they draw in.
## Everything else is neutral rather than guessed at.
const HARM_EFFECTS: Array[int] = [0, 2, 5, 10, 17, 73]
const BLESSING_EFFECTS: Array[int] = [1, 4, 9, 12, 14]
const WARD_EFFECTS: Array[int] = [3, 6, 72, 74]

var effect_id: int = -1
var power_level := 1
var elapsed: float = 0.0

var _ring: MeshInstance3D
var flight: Node3D
var release_delay := 0.0
var impact_started := false
var _source_actor: WeakRef
var _target_actor: WeakRef
var _launched := false
var _burst: GPUParticles3D
var _material: StandardMaterial3D
var _details := ImmediateMesh.new()
var _detail_material := CombatEffectMesh.material()
var _impact := Vector3.ZERO

func configure(effect: int, origin: Vector3, target: Variant = null, power := 1) -> void:
	effect_id = effect
	power_level = clampi(power, 1, 10)
	var brightness := SpellPresentation.power_intensity(power_level)
	_detail_material.albedo_color = Color(1.0, 1.0, 1.0, brightness)
	global_position = origin
	_impact = Vector3.ZERO
	if target is Vector3:
		_impact = target as Vector3 - origin
	var palette: Color = _palette()
	_material = StandardMaterial3D.new()
	_material.albedo_color = palette
	_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_material.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	var ring_mesh := TorusMesh.new()
	ring_mesh.inner_radius = (RING_RADIUS - 0.014) * SpellPresentation.power_radius(power_level)
	ring_mesh.outer_radius = RING_RADIUS * SpellPresentation.power_radius(power_level)
	ring_mesh.rings = 48
	ring_mesh.ring_segments = 6
	ring_mesh.material = _material
	_ring = MeshInstance3D.new()
	_ring.name = "EffectRing"
	_ring.mesh = ring_mesh
	_ring.position = _impact + Vector3.UP * 0.055
	_ring.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_ring)
	var details_node := MeshInstance3D.new()
	details_node.name = "EffectRunes"
	details_node.mesh = _details
	details_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(details_node)
	_add_burst(palette)
	if target is Vector3 and _impact.length_squared() > 0.0025:
		flight = SpellFlight.new()
		flight.name = "SpellFlight"
		add_child(flight)
		var from := Vector3.UP
		var to := _impact + Vector3.UP
		# Effect 10 is mana stolen from the target, returning to the caster.
		flight.configure(effect_id, palette, to if effect_id == 10 else from,
			from if effect_id == 10 else to, power_level)
		if effect_id == 10:
			_impact = Vector3.ZERO
		_ring.hide()
		_burst.emitting = false
	else:
		_start_impact()

## Weak references keep removal/teleport packets safe during a visual flight.
## Bind before its first frame; geometry stays in this effect's local space.
func bind_actors(source: Node3D, target_actor: Node3D) -> void:
	if is_instance_valid(source) and source is ReplicatedActor3D and source.combat_presentation != null:
		if SpellPresentation.action_for_effect(effect_id) == source.current_action:
			source.combat_presentation.set_spell_palette(_palette(), power_level)
	if flight == null:
		return
	if is_instance_valid(source):
		_source_actor = weakref(source)
		if source is ReplicatedActor3D:
			var release_time := 0.48 if source.current_action == &"heal" else 0.45
			release_delay = clampf(release_time - source.animation_player.current_animation_position, 0.0, release_time)
	if is_instance_valid(target_actor):
		_target_actor = weakref(target_actor)
	_update_anchors()

func _update_anchors() -> void:
	var from: Vector3 = flight.destination if effect_id == 10 else flight.start
	var to: Vector3 = flight.start if effect_id == 10 else flight.destination
	var source: Node3D = _source_actor.get_ref() as Node3D if _source_actor != null else null
	var receiver: Node3D = _target_actor.get_ref() as Node3D if _target_actor != null else null
	if is_instance_valid(source) and (not _launched or effect_id == 10):
		from = to_local(source.spell_release_origin() if source is ReplicatedActor3D
			else source.global_position + Vector3.UP)
	if is_instance_valid(receiver) and (not _launched or effect_id != 10):
		to = to_local(receiver.spell_target_position() if receiver is ReplicatedActor3D
			else receiver.global_position + Vector3.UP)
	flight.set_endpoints(to if effect_id == 10 else from, from if effect_id == 10 else to)
	var impact_actor := source if effect_id == 10 else receiver
	if is_instance_valid(impact_actor):
		_impact = to_local(impact_actor.global_position)
	_ring.position = _impact + Vector3.UP * 0.055
	_burst.position = flight.destination

func _start_impact() -> void:
	impact_started = true
	_ring.show()
	_burst.restart()
	_burst.emitting = true

## The particles themselves. A harmful effect falls inwards and a beneficial
## one rises, which is the one piece of meaning the server's own grouping
## supports; everything else drifts.
func _add_burst(palette: Color) -> void:
	var brightness := SpellPresentation.power_intensity(power_level)
	var size := SpellPresentation.power_scale(power_level)
	var process := ParticleProcessMaterial.new()
	process.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_SPHERE
	process.emission_sphere_radius = 0.38 * SpellPresentation.power_radius(power_level)
	process.direction = Vector3(0.0, 1.0, 0.0)
	process.spread = 110.0 if effect_id in HARM_EFFECTS else 24.0
	process.initial_velocity_min = 0.5
	process.initial_velocity_max = 2.0 if effect_id in HARM_EFFECTS else 1.3
	process.gravity = Vector3(0.0, -3.0 if effect_id in HARM_EFFECTS else 0.25, 0.0)
	process.scale_min = 0.22 * size
	process.scale_max = 0.60 * size
	process.color = Color.WHITE
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
	dot.albedo_color = Color(1.0, 1.0, 1.0, brightness)
	dot.albedo_texture = dot_texture
	dot.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dot.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dot.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	dot.vertex_color_use_as_albedo = true
	dot.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	var quad := QuadMesh.new()
	quad.size = Vector2(0.20, 0.20)
	quad.material = dot

	_burst = GPUParticles3D.new()
	_burst.name = "EffectBurst"
	_burst.amount = SpellPresentation.power_count(PARTICLE_COUNT, power_level)
	_burst.lifetime = LIFETIME_SECONDS * 0.8
	_burst.one_shot = true
	_burst.explosiveness = 0.96 if effect_id in HARM_EFFECTS else 0.48
	_burst.process_material = process
	_burst.draw_pass_1 = quad
	_burst.layers = GAMEPLAY_LAYER
	_burst.position = _impact + Vector3.UP * 0.9
	_burst.visibility_aabb = AABB(Vector3(-4, -2, -4), Vector3(8, 8, 8))
	_burst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_burst)
	_burst.emitting = false

func _palette() -> Color:
	if effect_id in [0, 73]:
		return Color(0.64, 0.88, 0.20)
	if effect_id == 10:
		return Color(0.70, 0.42, 1.0)
	if effect_id in HARM_EFFECTS:
		return Color(1.0, 0.42, 0.18)
	if effect_id in BLESSING_EFFECTS:
		return Color(0.46, 0.86, 0.52)
	return Color(0.62, 0.74, 0.98)

func _process(delta: float) -> void:
	elapsed += delta
	var impact_time := elapsed
	if flight != null:
		if not impact_started:
			_update_anchors()
		if elapsed >= release_delay:
			_launched = true
		flight.draw_at(elapsed - release_delay)
		impact_time -= release_delay + float(flight.duration)
		if impact_time < 0.0:
			return
		if not impact_started:
			_start_impact()
	var progress: float = clampf(impact_time / LIFETIME_SECONDS, 0.0, 1.0)
	if is_instance_valid(_ring):
		var scale_factor: float = 0.55 + (1.0-pow(1.0-progress, 3.0)) * 0.6
		_ring.scale = Vector3(scale_factor, 1.0, scale_factor)
	if _material != null:
		_material.albedo_color.a = (1.0 - progress) * 0.65 * SpellPresentation.power_intensity(power_level)
	_draw_details(progress)
	if progress >= 1.0:
		queue_free()

func _draw_details(progress: float) -> void:
	_details.clear_surfaces()
	_details.surface_begin(Mesh.PRIMITIVE_TRIANGLES, _detail_material)
	var color := _palette()
	var size := SpellPresentation.power_scale(power_level)
	var radius := SpellPresentation.power_radius(power_level)
	color.a = sin(progress * PI) * 0.7
	var centre := _impact + Vector3.UP * 0.065
	for i: int in 8:
		var angle := i*TAU/8.0 + elapsed*0.3
		var direction := Vector3(cos(angle), 0, sin(angle))
		CombatEffectMesh.line(_details, centre+direction*0.56*radius, centre+direction*0.66*radius,
			0.022*size, color)
	if effect_id in BLESSING_EFFECTS:
		var count := SpellPresentation.power_count(20, power_level)
		for i: int in count:
			var height := fposmod(float(i)/count + elapsed*0.6, 1.0)
			var angle := i*2.4 + elapsed*2.0
			var tint := color.lerp(Color(1.0, 0.84, 0.40, color.a), float(i%3)/3.0)
			tint.a *= sin(height*PI)
			CombatEffectMesh.spark(_details, _impact+Vector3(cos(angle)*0.45*radius,
				height*1.9, sin(angle)*0.45*radius), 0.047*size, tint)
	elif effect_id in WARD_EFFECTS:
		for i: int in 3:
			CombatEffectMesh.arc(_details, _impact+Vector3.UP*(0.6+i*0.35),
				0.56*radius, 0.018*size, color, elapsed*(1.0 if i%2 == 0 else -1.0)+i, TAU*0.75)
	else:
		for i: int in SpellPresentation.power_count(14, power_level):
			var angle := float(i)*2.399
			var direction := Vector3(cos(angle), sin(i*1.7)*0.6, sin(angle))
			var point := _impact+Vector3.UP*0.95+direction*(0.12+progress*0.7)*radius
			CombatEffectMesh.line(_details, point, point+direction*0.10*(1.0-progress)*size,
				0.014*size, color)
	if flight != null:
		# A brief contact star and expanding fragments punctuate the arrival.
		var contact: Vector3 = flight.destination
		var flash := 1.0 - smoothstep(0.0, 0.22, progress)
		CombatEffectMesh.spark(_details, contact, 0.22 * flash * size,
			Color(1.0, 0.91, 0.70, flash * 0.85))
	_details.surface_end()
