shader_type spatial;
render_mode cull_disabled;

// This transform is authored map space -> continent space. It does not change
// when the client rebases a resident region at a crossing.
uniform mat4 water_to_continent;
uniform sampler2D wave_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_wave_texture = false;
varying vec2 continent_position;

void vertex() {
	continent_position = (water_to_continent * vec4(VERTEX, 1.0)).xz;
}

void fragment() {
	vec2 p = continent_position;
	float broad = sin(dot(p, vec2(.019, -.013))) * .5 + .5;
	float ripple = sin(dot(p, vec2(.43, .19)) + TIME * .45);
	float crossing = sin(dot(p, vec2(-.16, .37)) - TIME * .31);
	// Broad, low-contrast variation belongs to the water body, not a map tile.
	float curl = sin(dot(p, vec2(.13, -.29))) * 3.0 + sin(dot(p, vec2(.15, .37))) * 2.0;
	float crest = sin(dot(p, vec2(1.8, .92)) + curl + TIME * .3);
	float broken = smoothstep(.05, .75, sin(dot(p, vec2(-.6, .44)) + crossing));
	ALBEDO = mix(vec3(.045, .14, .17), vec3(.058, .18, .19), broad);
	ALBEDO += vec3(.006, .014, .016) * (ripple * crossing);
	if (has_wave_texture) {
		vec3 first = texture(wave_texture, p * .075 + vec2(TIME * .002, 0.0)).rgb;
		vec3 second = texture(wave_texture, p.yx * .043 + vec2(0.0, TIME * .0015)).rgb;
		float detail = dot(mix(first, second, .35), vec3(.2126, .7152, .0722));
		ALBEDO *= .7 + detail * 1.6;
	} else {
		ALBEDO += vec3(.012, .022, .025) * smoothstep(.82, .98, crest) * broken;
	}
	// All exterior frames are translation-only, so these continent-space
	// ripple normals also agree across differently authored water primitives.
	vec3 ripple_normal = normalize(vec3(-.055 * ripple, 1.0, -.045 * crossing));
	NORMAL = normalize((VIEW_MATRIX * vec4(ripple_normal, 0.0)).xyz);
	ROUGHNESS = .64;
	METALLIC = .0;
	SPECULAR = .16;
}
