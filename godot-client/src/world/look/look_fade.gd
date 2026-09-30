class_name LookFade
extends RefCounted
## Look pass layer L3: occluders open a hole round the player instead of
## blending. Used by OccluderFade only when LookProfile.enabled(); with the
## pass off OccluderFade blends exactly as it does on develop.
##
## OccluderFade fades an obstacle by swapping in a copy of its material that
## alpha-blends towards FADED_ALPHA. A blended surface stops writing depth, so
## a faded crown's hundreds of overlapping leaf cards sort against each other
## and against the ground and read as a brown smear, and a roof loses its own
## shading under the blend. The pass first dithered the whole occluder
## instead, a one-pixel screen-door at 35 % coverage, which read as a
## crosshatched window screen over up to a fifth of the frame. Now the
## occluder stays solid, lit and depth-tested as always, and a round hole
## with a dithered rim opens where it covers the player
## (look_fade_hole.gdshaderinc), as the reference frames' crown fade cuts one.
## The fade's timing is OccluderFade's, unchanged: it opens the hole.
##
## - A painted look material (LookFoliage's crowns, LookGround's blended
##   ground) names its dithered variant in FADED_SHADER_META; the copy
##   switches to that shader and OccluderFade opens its hole.
## - A StandardMaterial3D is copied into look_faded_standard.gdshader, which
##   draws what the engine would draw for it and cuts the hole. The
##   engine's own dither for it, hashed alpha, is ignored by the compatibility
##   renderer (its copies drew fully opaque there). A material using a feature
##   that shader does not reproduce keeps develop's blended copy.
## - Any other ShaderMaterial is left solid, as on develop.
##
## Every one of them cuts the same hole, and only the faded copies carry its
## discard, so a resting surface keeps the engine's early depth test.
##
## A faded copy would cast its hole into its shadow too, so while a mesh fades
## it stops casting. A wall or a roof hands its shadow to a shadow-only twin
## with its resting materials, because a room lighting up as the player walks
## in reads as a bug. A crown casts none, as develop's blended copies cast
## none: the twin held a giant canopy's whole shadow over the player and took
## the deep grove from luminance 80 to 64 (53 in Forward+), the darkest frame
## of the pass, where walking under a tree on develop lights the ground.
##
## The ground never fades. Develop has no walk collision on the continent's
## authored ground patches, so the patch a player stands on was indexed as an
## occluder and faded to glass under their feet; with the pass on, anything
## LookGround paints as ground is kept out of the index, as walk surfaces are.

const SHADER_STANDARD := preload("res://src/world/look/look_faded_standard.gdshader")
const SHADER_STANDARD_TWO_SIDED := preload("res://src/world/look/look_faded_standard_two_sided.gdshader")

## On a painted material: the Shader its faded copy switches to.
const FADED_SHADER_META := &"look_faded_shader"
## On a fading mesh: the cast_shadow setting to give back to it.
const SHADOW_META := &"look_fade_shadow"
const SHADOW_TWIN_NAME := &"LookFadeShadow"
## The uniform a dithered material records its opacity in.
const FADE_PARAMETER := &"look_fade"
## The uniforms that open its hole, and centre it.
const OPEN_PARAMETER := &"look_fade_open"
const FOCUS_PARAMETER := &"look_fade_focus"

## Where the holes are centred this frame: the local player's chest, handed
## over by OccluderFade.update before it animates its fades.
static var focus := Vector3.ZERO

## BaseMaterial3D.TextureChannel as the vector look_faded_standard dots a
## texel with.
const CHANNELS := [Vector4(1, 0, 0, 0), Vector4(0, 1, 0, 0), Vector4(0, 0, 1, 0),
	Vector4(0, 0, 0, 1), Vector4(0.333333, 0.333333, 0.333333, 0)]

## True when a mesh stays solid whatever covers the player: ground.
static func keeps_solid(node_name: String) -> bool:
	return LookGround.kind_of(node_name) != LookGround.Kind.NONE

## A dithered copy of `source` for OccluderFade to fade by, or null when it
## has none (OccluderFade then does what develop does). Its hole is sized for
## `node`, the mesh it fades (see hole_metres).
static func dither_copy(source: Material, node: MeshInstance3D = null) -> ShaderMaterial:
	if source is BaseMaterial3D:
		var standard := _dithered_standard(source as BaseMaterial3D)
		if standard != null:
			_size_hole(standard, node)
		return standard
	var painted := source as ShaderMaterial
	if painted == null or not painted.has_meta(FADED_SHADER_META):
		return null
	var faded_shader := painted.get_meta(FADED_SHADER_META) as Shader
	if faded_shader == null:
		return null
	var copy := painted.duplicate() as ShaderMaterial
	copy.shader = faded_shader
	_set_hole(copy)
	_size_hole(copy, node)
	return copy

## The hole's radius for an occluder: FADE_HOLE_METRES, or a share of a
## larger occluder's width. A giant canopy the camera looks down through
## covered most of the frame round a hole sized for a player, as a ceiling of
## flat leaf cards; opened by a fifth of its width it reads as a gap in the
## crown, with the canopy round the frame's edges.
static func hole_metres(node: MeshInstance3D) -> float:
	if node == null or node.mesh == null:
		return LookProfile.FADE_HOLE_METRES
	var size := node.mesh.get_aabb().size
	var scale := node.transform.basis.get_scale()
	if node.is_inside_tree():
		scale = node.global_transform.basis.get_scale()
	var width := maxf(size.x * absf(scale.x), size.z * absf(scale.z))
	return clampf(width * LookProfile.FADE_HOLE_SHARE, LookProfile.FADE_HOLE_METRES,
		LookProfile.FADE_HOLE_MAX_METRES)

## Sets a dithered copy's opacity (1 solid, 0 gone), how far its hole is open
## (the fade's progress, 0..1) and where it is centred.
static func write(copy: ShaderMaterial, opacity: float, open := 1.0) -> void:
	copy.set_shader_parameter(FADE_PARAMETER, clampf(opacity, 0.0, 1.0))
	copy.set_shader_parameter(OPEN_PARAMETER, clampf(open, 0.0, 1.0))
	copy.set_shader_parameter(FOCUS_PARAMETER, focus)

## True when `node` draws a painted crown (LookFoliage): a crown fades without
## a shadow, as develop's blended copies do.
static func is_crown(node: MeshInstance3D) -> bool:
	if node.material_override != null:
		return node.material_override.has_meta(LookFoliage.PAINTED_META)
	var surfaces := 0 if node.mesh == null else node.mesh.get_surface_count()
	for surface: int in surfaces:
		var material := node.get_active_material(surface)
		if material != null and material.has_meta(LookFoliage.PAINTED_META):
			return true
	return false

## True when look_faded_standard draws `material` as the engine does.
static func reproduces(material: BaseMaterial3D) -> bool:
	if material is ORMMaterial3D:
		return false
	if material.shading_mode != BaseMaterial3D.SHADING_MODE_PER_PIXEL \
			or material.blend_mode != BaseMaterial3D.BLEND_MODE_MIX \
			or material.cull_mode == BaseMaterial3D.CULL_FRONT \
			or material.diffuse_mode != BaseMaterial3D.DIFFUSE_BURLEY \
			or material.specular_mode != BaseMaterial3D.SPECULAR_SCHLICK_GGX \
			or material.billboard_mode != BaseMaterial3D.BILLBOARD_DISABLED \
			or material.distance_fade_mode != BaseMaterial3D.DISTANCE_FADE_DISABLED \
			or material.depth_draw_mode != BaseMaterial3D.DEPTH_DRAW_OPAQUE_ONLY:
		return false
	if material.uv1_triplanar or material.uv2_triplanar or material.grow \
			or material.detail_enabled or material.rim_enabled \
			or material.clearcoat_enabled or material.anisotropy_enabled \
			or material.heightmap_enabled or material.subsurf_scatter_enabled \
			or material.backlight_enabled or material.refraction_enabled \
			or material.proximity_fade_enabled or material.emission_on_uv2 \
			or material.ao_on_uv2:
		return false
	for flag: int in [BaseMaterial3D.FLAG_DISABLE_DEPTH_TEST, BaseMaterial3D.FLAG_USE_POINT_SIZE,
			BaseMaterial3D.FLAG_FIXED_SIZE, BaseMaterial3D.FLAG_USE_SHADOW_TO_OPACITY,
			BaseMaterial3D.FLAG_UV1_USE_WORLD_TRIPLANAR, BaseMaterial3D.FLAG_PARTICLE_TRAILS_MODE]:
		if material.get_flag(flag):
			return false
	return material.texture_filter in [BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS,
		BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC]

## The dithered stand-in for a StandardMaterial3D, or null when
## look_faded_standard cannot reproduce it.
static func _dithered_standard(source: BaseMaterial3D) -> ShaderMaterial:
	if not reproduces(source):
		return null
	var copy := ShaderMaterial.new()
	copy.resource_name = source.resource_name
	copy.shader = SHADER_STANDARD_TWO_SIDED \
		if source.cull_mode == BaseMaterial3D.CULL_DISABLED else SHADER_STANDARD
	copy.render_priority = source.render_priority
	copy.next_pass = source.next_pass
	var alpha_mode := 0
	match source.transparency:
		BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
			alpha_mode = 1
		BaseMaterial3D.TRANSPARENCY_ALPHA, BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS, \
				BaseMaterial3D.TRANSPARENCY_ALPHA_HASH:
			alpha_mode = 2
	copy_standard_surface(source, copy)
	copy.set_shader_parameter(&"use_vertex_albedo", source.vertex_color_use_as_albedo)
	copy.set_shader_parameter(&"vertex_albedo_srgb", source.vertex_color_is_srgb)
	copy.set_shader_parameter(&"alpha_mode", alpha_mode)
	copy.set_shader_parameter(&"alpha_scissor_threshold", source.alpha_scissor_threshold)
	_set_hole(copy)
	return copy

## A fresh faded copy: whole, its hole's size from LookProfile.
static func _set_hole(copy: ShaderMaterial) -> void:
	copy.set_shader_parameter(FADE_PARAMETER, 1.0)
	copy.set_shader_parameter(OPEN_PARAMETER, 0.0)
	copy.set_shader_parameter(FOCUS_PARAMETER, focus)
	copy.set_shader_parameter(&"look_fade_hole_metres", LookProfile.FADE_HOLE_METRES)
	copy.set_shader_parameter(&"look_fade_rim_metres", LookProfile.FADE_RIM_METRES)
	copy.set_shader_parameter(&"look_fade_behind_metres", LookProfile.FADE_BEHIND_METRES)

## Sizes a faded copy's hole, and its rim with it, for the mesh it fades.
static func _size_hole(copy: ShaderMaterial, node: MeshInstance3D) -> void:
	var radius := hole_metres(node)
	copy.set_shader_parameter(&"look_fade_hole_metres", radius)
	copy.set_shader_parameter(&"look_fade_rim_metres",
		maxf(LookProfile.FADE_RIM_METRES, radius * LookProfile.FADE_RIM_SHARE))

## Fills the uniforms of look_standard_surface.gdshaderinc (albedo, normal,
## roughness, metallic, occlusion, emission, UV scale) on `target` from
## `source`, so a look shader lights as the material it stands in for.
static func copy_standard_surface(source: BaseMaterial3D, target: ShaderMaterial) -> void:
	target.set_shader_parameter(&"albedo_color", source.albedo_color)
	target.set_shader_parameter(&"albedo_texture", source.albedo_texture)
	target.set_shader_parameter(&"has_normal_texture",
		source.normal_enabled and source.normal_texture != null)
	target.set_shader_parameter(&"normal_texture", source.normal_texture)
	target.set_shader_parameter(&"normal_scale", source.normal_scale)
	target.set_shader_parameter(&"roughness_value", source.roughness)
	target.set_shader_parameter(&"roughness_texture", source.roughness_texture)
	target.set_shader_parameter(&"roughness_channel", CHANNELS[source.roughness_texture_channel])
	target.set_shader_parameter(&"metallic_value", source.metallic)
	target.set_shader_parameter(&"metallic_texture", source.metallic_texture)
	target.set_shader_parameter(&"metallic_channel", CHANNELS[source.metallic_texture_channel])
	target.set_shader_parameter(&"specular_value", source.metallic_specular)
	target.set_shader_parameter(&"has_ao", source.ao_enabled and source.ao_texture != null)
	target.set_shader_parameter(&"ao_texture", source.ao_texture)
	target.set_shader_parameter(&"ao_channel", CHANNELS[source.ao_texture_channel])
	target.set_shader_parameter(&"ao_light_affect", source.ao_light_affect)
	target.set_shader_parameter(&"has_emission", source.emission_enabled)
	target.set_shader_parameter(&"emission_color", source.emission)
	target.set_shader_parameter(&"emission_texture", source.emission_texture)
	target.set_shader_parameter(&"emission_energy", source.emission_energy_multiplier)
	target.set_shader_parameter(&"emission_operator", int(source.emission_operator))
	target.set_shader_parameter(&"uv1_scale", source.uv1_scale)
	target.set_shader_parameter(&"uv1_offset", source.uv1_offset)

## Stops `node` casting while it fades, and hands a wall's or roof's shadow
## to a shadow-only twin drawing its current (resting) materials; a crown gets
## no twin (see the header). Call before the faded copies go in. Returns the
## twin, or null when there is none.
static func hold_shadow(node: MeshInstance3D) -> MeshInstance3D:
	if not is_instance_valid(node) or node.mesh == null:
		return null
	if node.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF \
			or node.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
		return null
	node.set_meta(SHADOW_META, node.cast_shadow)
	var crown := is_crown(node)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	if crown:
		return null
	var twin := MeshInstance3D.new()
	twin.name = SHADOW_TWIN_NAME
	twin.mesh = node.mesh
	twin.material_override = node.material_override
	for surface: int in node.get_surface_override_material_count():
		twin.set_surface_override_material(surface, node.get_surface_override_material(surface))
	twin.layers = node.layers
	twin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	node.add_child(twin)
	return twin

## Gives `node` its shadow back and takes any twin out of the tree at once (a
## twin left for the frame a queue_free takes would double the shadow). Either
## may be null: a node freed with its map, a crown that has no twin.
static func release_shadow(node: MeshInstance3D, twin: MeshInstance3D) -> void:
	if node != null and node.has_meta(SHADOW_META):
		node.cast_shadow = int(node.get_meta(SHADOW_META)) \
			as GeometryInstance3D.ShadowCastingSetting
		node.remove_meta(SHADOW_META)
	if twin == null:
		return
	var parent := twin.get_parent()
	if parent != null:
		parent.remove_child(twin)
	twin.queue_free()
