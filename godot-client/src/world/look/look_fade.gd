class_name LookFade
extends RefCounted
## Look pass layer L3: occluders dither out instead of blending. Used by
## OccluderFade only when LookProfile.enabled(); with the pass off OccluderFade
## blends exactly as it does on develop.
##
## OccluderFade fades an obstacle by swapping in a copy of its material that
## alpha-blends towards FADED_ALPHA. A blended surface stops writing depth, so
## a faded crown's hundreds of overlapping leaf cards sort against each other
## and against the ground and read as a brown smear, and a roof loses its own
## shading under the blend. A screen-door keeps both: each pixel is the
## occluder, lit and depth-tested as always, or a hole onto what lies behind.
## The fade's timing and opacity are OccluderFade's, unchanged; only the
## material it swaps in differs.
##
## - A painted look material (LookFoliage's crowns, LookGround's blended
##   ground) names its dithered variant in FADED_SHADER_META; the copy
##   switches to that shader and OccluderFade drives its `look_fade`.
## - A StandardMaterial3D is copied into look_faded_standard.gdshader, which
##   draws what the engine would draw for it and dithers by `look_fade`. The
##   engine's own dither for it, hashed alpha, is ignored by the compatibility
##   renderer (its copies drew fully opaque there). A material using a feature
##   that shader does not reproduce keeps develop's blended copy.
## - Any other ShaderMaterial is left solid, as on develop.
##
## Every one of them cuts the same screen-door (interleaved gradient noise on
## FRAGCOORD), and only the faded copies carry its discard, so a resting
## surface keeps the engine's early depth test.
##
## A dithered surface would also cast a dithered shadow - a crown overhead
## would let a third of the sun through for as long as it is faded - so while
## a mesh fades it stops casting and a shadow-only twin with its resting
## materials casts in its place.
##
## The ground never fades. Develop has no walk collision on the continent's
## authored ground patches, so the patch a player stands on was indexed as an
## occluder and faded to glass under their feet; with the pass on, anything
## LookGround paints as ground is kept out of the index, as walk surfaces are.

const SHADER_STANDARD := preload("res://src/world/look/look_faded_standard.gdshader")
const SHADER_STANDARD_TWO_SIDED := preload("res://src/world/look/look_faded_standard_two_sided.gdshader")

## On a painted material: the Shader its faded copy switches to.
const FADED_SHADER_META := &"look_faded_shader"
## On a shadow twin: the cast_shadow setting to give back to its mesh.
const SHADOW_META := &"look_fade_shadow"
const SHADOW_TWIN_NAME := &"LookFadeShadow"
## The uniform a dithered material reads its opacity from.
const FADE_PARAMETER := &"look_fade"

## BaseMaterial3D.TextureChannel as the vector look_faded_standard dots a
## texel with.
const CHANNELS := [Vector4(1, 0, 0, 0), Vector4(0, 1, 0, 0), Vector4(0, 0, 1, 0),
	Vector4(0, 0, 0, 1), Vector4(0.333333, 0.333333, 0.333333, 0)]

## True when a mesh stays solid whatever covers the player: ground.
static func keeps_solid(node_name: String) -> bool:
	return LookGround.kind_of(node_name) != LookGround.Kind.NONE

## A dithered copy of `source` for OccluderFade to fade by, or null when it
## has none (OccluderFade then does what develop does).
static func dither_copy(source: Material) -> ShaderMaterial:
	if source is BaseMaterial3D:
		return _dithered_standard(source as BaseMaterial3D)
	var painted := source as ShaderMaterial
	if painted == null or not painted.has_meta(FADED_SHADER_META):
		return null
	var faded_shader := painted.get_meta(FADED_SHADER_META) as Shader
	if faded_shader == null:
		return null
	var copy := painted.duplicate() as ShaderMaterial
	copy.shader = faded_shader
	copy.set_shader_parameter(FADE_PARAMETER, 1.0)
	return copy

## Sets a dithered copy's opacity (1 solid, 0 gone).
static func write(copy: ShaderMaterial, opacity: float) -> void:
	copy.set_shader_parameter(FADE_PARAMETER, clampf(opacity, 0.0, 1.0))

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
	copy.set_shader_parameter(FADE_PARAMETER, 1.0)
	return copy

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

## Hands `node`'s shadow to a shadow-only twin drawing its current (resting)
## materials, and stops `node` casting. Call before the faded copies go in.
## Returns the twin, or null when the node casts no shadow.
static func hold_shadow(node: MeshInstance3D) -> MeshInstance3D:
	if not is_instance_valid(node) or node.mesh == null:
		return null
	if node.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF \
			or node.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY:
		return null
	var twin := MeshInstance3D.new()
	twin.name = SHADOW_TWIN_NAME
	twin.mesh = node.mesh
	twin.material_override = node.material_override
	for surface: int in node.get_surface_override_material_count():
		twin.set_surface_override_material(surface, node.get_surface_override_material(surface))
	twin.layers = node.layers
	twin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	twin.set_meta(SHADOW_META, node.cast_shadow)
	node.add_child(twin)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return twin

## Gives `node` its shadow back and takes the twin out of the tree at once (a
## twin left for the frame a queue_free takes would double the shadow).
static func release_shadow(node: MeshInstance3D, twin: MeshInstance3D) -> void:
	if twin == null or not is_instance_valid(twin):
		return
	if is_instance_valid(node):
		node.cast_shadow = int(twin.get_meta(SHADOW_META,
			GeometryInstance3D.SHADOW_CASTING_SETTING_ON)) as GeometryInstance3D.ShadowCastingSetting
	var parent := twin.get_parent()
	if parent != null:
		parent.remove_child(twin)
	twin.queue_free()
