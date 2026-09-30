// Look pass layer L3: a StandardMaterial3D's stand-in while OccluderFade
// fades it, dithered out by look_fade.
//
// Develop fades an occluder by blending a copy of its material. The look
// pass dithers it instead (see LookFade), and the engine's own dither for a
// StandardMaterial3D, hashed alpha, is ignored by the compatibility renderer:
// its copies drew fully opaque there. So the copy is this shader, set up by
// LookFade from the source material's own properties. It covers what the
// continent's occluders use (a census of two chunks: albedo, normal,
// roughness, metallic and ambient occlusion textures, emission, vertex colour,
// alpha scissor, one- and two-sided) with the engine's own formulas for them
// (look_standard_surface.gdshaderinc), so a mesh does not change its look as
// it starts to fade; LookFade leaves a material that uses anything else to
// develop's blend.
//
// The painted_ground and painted_foliage shaders cut the same screen-door
// pattern (interleaved gradient noise on FRAGCOORD), so everything that fades
// fades alike. Only these faded copies carry the discard.

#include "res://src/world/look/look_standard_surface.gdshaderinc"

uniform bool use_vertex_albedo = false;
uniform bool vertex_albedo_srgb = false;
// 0 opaque, 1 alpha-cut at alpha_scissor_threshold, 2 blended (its alpha
// becomes coverage).
uniform int alpha_mode = 0;
uniform float alpha_scissor_threshold = 0.5;
uniform float look_fade = 1.0;

void vertex() {
	UV = UV * uv1_scale.xy + uv1_offset.xy;
	if (vertex_albedo_srgb) {
		COLOR.rgb = mix(pow((COLOR.rgb + vec3(0.055)) * (1.0 / 1.055), vec3(2.4)),
			COLOR.rgb * (1.0 / 12.92), lessThan(COLOR.rgb, vec3(0.04045)));
	}
}

void fragment() {
	vec4 albedo = texture(albedo_texture, UV) * albedo_color;
	if (use_vertex_albedo) {
		albedo *= COLOR;
	}
	float coverage = look_fade;
	if (alpha_mode == 1 && albedo.a < alpha_scissor_threshold) {
		discard;
	}
	if (alpha_mode == 2) {
		coverage *= albedo.a;
	}
	if (fract(52.9829189 * fract(dot(FRAGCOORD.xy, vec2(0.06711056, 0.00583715))))
			>= coverage) {
		discard;
	}
	ALBEDO = albedo.rgb;
	vec4 surface = look_standard_surface(UV);
	ROUGHNESS = surface.x;
	METALLIC = surface.y;
	SPECULAR = surface.z;
	if (has_ao) {
		AO = surface.w;
		AO_LIGHT_AFFECT = ao_light_affect;
	}
	if (has_normal_texture) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
	if (has_emission) {
		EMISSION = look_standard_emission(UV);
	}
}
