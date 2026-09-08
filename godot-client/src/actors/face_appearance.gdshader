shader_type spatial;
render_mode cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D base_texture : source_color, filter_linear_mipmap, repeat_enable;
// Linear data: R protects the whole eye from skin dye, G selects the iris,
// B selects source brow pigment or authored fine hair strokes on bare brows.
// All use the original head UV atlas.
uniform sampler2D region_texture : filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap, repeat_enable;
uniform bool use_normal = false;
uniform float normal_scale = 1.0;
uniform vec4 base_color : source_color = vec4(1.0);
uniform vec4 skin_tint : source_color = vec4(1.0);
uniform vec4 eye_tint : source_color = vec4(1.0);
uniform vec4 hair_tint : source_color = vec4(1.0);
uniform float roughness = 0.85;

void fragment() {
	vec3 original = texture(base_texture, UV).rgb * base_color.rgb;
	vec3 mask = texture(region_texture, UV).rgb;
	vec3 skin = original * skin_tint.rgb;
	vec3 eye = original;
	float peak = max(original.r, max(original.g, original.b));
	// Neutralise the authored iris hue, retaining its pupil and highlights.
	vec3 iris = eye_tint.rgb * min(peak * 1.6, 1.0);
	float highlight = smoothstep(0.55, 0.9, min(original.r, min(original.g, original.b)));
	eye = mix(eye, mix(iris, original, highlight), mask.g);
	ALBEDO = mix(skin, eye, mask.r);
	ALBEDO = mix(ALBEDO, vec3(peak) * hair_tint.rgb, mask.b);
	ROUGHNESS = roughness;
	if (use_normal) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
}
