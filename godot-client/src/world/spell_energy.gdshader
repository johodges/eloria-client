shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never;

uniform bool radial = false;
uniform float intensity = 1.0;

void fragment() {
	float distance_to_edge = radial ? length(UV * 2.0 - 1.0) : abs(UV.y * 2.0 - 1.0);
	float softness = pow(max(0.0, 1.0 - distance_to_edge), radial ? 2.6 : 1.8);
	ALBEDO = COLOR.rgb;
	ALPHA = min(1.0, COLOR.a * softness * intensity);
}
