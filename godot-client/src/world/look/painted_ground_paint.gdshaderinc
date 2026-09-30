// Look pass layer L2: the painted ground's value hierarchy.
//
// Included by the painted ground shaders (painted_ground*.gdshader), which
// stand in for the ground's StandardMaterial3Ds, and by the painted copy of
// the biome blend that LookGround derives from biome_blend.gdshader at run
// time. Every value arrives as a uniform that LookGround sets from
// LookProfile, so the whole look is tuned in one place.
//
// It works on linear albedo, before light and tone curve, in three steps:
// a pixel is weighed as path (a walk deck, the exporter's worn-road colour in
// the terrain's vertex colour), yard (an authored ground patch) or pale ground
// (paving, sand, a gold trail); whatever is none of those is verge. Paths lift
// towards a pale warm value, the verge deepens and enriches, and everything
// carries a low-frequency variation in continent space and darkens with slope.
// Nothing reads the screen, so it runs in the compatibility renderer and in
// Forward+ alike.
//
// The compatibility renderer shades in sRGB: its albedo arrives gamma-encoded
// (measured: a walk deck whose linear luminance is 0.056 read above 0.2 there).
// Every threshold and target here is linear, so on that renderer the albedo
// is decoded on the way in and encoded again on the way out, and the two
// renderers paint the same colours.

// What the surface is. A walk deck is a path whatever its colour.
uniform float look_path_force = 0.0;
// Terrain only: read the exporter's worn-road colour out of the vertex colour.
uniform float look_road_detect = 0.0;
uniform vec3 look_road_colour = vec3(0.2265, 0.1746, 0.0855);
// Relative distance from the road colour that is still fully road, and where
// it stops being road at all.
uniform vec2 look_road_tolerance = vec2(0.12, 0.34);
// Authored ground patches: how much of the yard lift they take.
uniform float look_yard = 0.0;
// How much pale ground is spared the verge treatment (0 for the biome blend).
uniform float look_pale = 1.0;

uniform float look_path_luma = 0.24;
uniform float look_path_lift_max = 6.0;
uniform vec3 look_path_warmth = vec3(1.06, 1.0, 0.86);
uniform float look_path_saturation = 0.65;
uniform float look_yard_luma = 0.15;
uniform float look_yard_lift_max = 3.0;
uniform float look_yard_saturation = 0.85;
uniform vec2 look_pale_luma = vec2(0.16, 0.3);
uniform float look_verge_value_green = 0.66;
uniform float look_verge_value_earth = 0.8;
uniform float look_verge_saturation = 1.08;
uniform float look_variation_metres = 16.0;
uniform float look_variation = 0.2;
uniform float look_variation_hue = 0.06;
uniform float look_path_variation_share = 0.35;
uniform vec2 look_slope_up = vec2(0.94, 0.62);
uniform float look_slope_shade = 0.72;

// 0 paints; 1-3 are the debug views (see look_debug_colour).
uniform int look_debug = 0;
// 0 terrain, 1 biome blend, 2 authored patch, 3 walk deck. Only for debug.
uniform int look_class = 0;

float look_luma(vec3 colour) {
	return dot(colour, vec3(0.2126, 0.7152, 0.0722));
}

// Dave Hoskins' sine-free hash: stable at continent coordinates in the
// thousands of metres, where fract(sin()) bands.
float look_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float look_value_noise(vec2 p) {
	vec2 cell = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = look_hash(cell);
	float b = look_hash(cell + vec2(1.0, 0.0));
	float c = look_hash(cell + vec2(0.0, 1.0));
	float d = look_hash(cell + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Two octaves centred on zero, roughly -0.5..0.5.
float look_variation_at(vec2 xz) {
	vec2 p = xz / look_variation_metres;
	return 0.65 * look_value_noise(p)
		+ 0.35 * look_value_noise(p * 2.7 + vec2(13.1, 7.7)) - 0.5;
}

// How much of a terrain pixel is the exporter's worn road. The terrain mixes
// its biome colour towards the road colour and divides by 0.92, so a road
// vertex is the road colour over 0.92 and its verge fades into the biome.
float look_road_weight(vec3 vertex_colour) {
	vec3 road = look_road_colour / 0.92;
	float distance_from_road = length(vertex_colour - road) / length(road);
	return 1.0 - smoothstep(look_road_tolerance.x, look_road_tolerance.y,
		distance_from_road);
}

vec3 look_saturate(vec3 colour, float amount) {
	return max(mix(vec3(look_luma(colour)), colour, amount), vec3(0.0));
}

// The renderer's albedo encoding to linear, and back.
vec3 look_to_linear(vec3 colour) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	colour = max(colour, vec3(0.0));
	return mix(pow((colour + vec3(0.055)) * (1.0 / 1.055), vec3(2.4)),
		colour * (1.0 / 12.92), lessThan(colour, vec3(0.04045)));
#else
	return colour;
#endif
}

vec3 look_from_linear(vec3 colour) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	colour = clamp(colour, vec3(0.0), vec3(1.0));
	return mix(vec3(1.055) * pow(colour, vec3(1.0 / 2.4)) - vec3(0.055),
		colour * 12.92, lessThan(colour, vec3(0.0031308)));
#else
	return clamp(colour, vec3(0.0), vec3(1.0));
#endif
}

// How green-dominant a colour is: grass however pale, not olive or earth.
float look_green(vec3 colour) {
	return smoothstep(0.02, 0.12, (colour.g - colour.r) / max(colour.g, 0.0001));
}

// The weights look_paint uses (path, yard, pale), for the debug views too.
// `reference` is the surface's mean albedo, linear: classing and lifting by
// the mean rather than by each texel keeps the texture's own grain.
vec3 look_weights(vec3 reference, vec3 vertex_colour) {
	float luma = look_luma(reference);
	float road = look_road_detect > 0.0 ? look_road_weight(vertex_colour) : 0.0;
	float path = max(look_path_force, road);
	float green = look_green(reference);
	float pale = smoothstep(look_pale_luma.x, look_pale_luma.y, luma) * (1.0 - green)
		* look_pale;
	float yard = look_yard * (1.0 - green);
	return vec3(path, yard, pale);
}

// albedo: the renderer's albedo after texture, tint and vertex colour.
// reference: the same from the texture's smallest mip (its mean colour), or
// the albedo itself where there is no single texture to average.
// vertex_colour: the raw vertex colour (only the terrain reads it).
// xz: continent-space position in metres. up: |world normal . up|.
vec3 look_paint(vec3 albedo, vec3 reference, vec3 vertex_colour, vec2 xz, float up) {
	albedo = look_to_linear(albedo);
	reference = look_to_linear(reference);
	vec3 weights = look_weights(reference, vertex_colour);
	float path = weights.x;
	float yard = weights.y;
	float pale = weights.z;
	float luma = max(look_luma(reference), 0.0001);

	float verge_scale = mix(look_verge_value_earth, look_verge_value_green,
		look_green(reference));
	vec3 verge = look_saturate(albedo * verge_scale, look_verge_saturation);
	vec3 colour = mix(verge, albedo, pale);
	float yard_lift = clamp(look_yard_luma / luma, 1.0, look_yard_lift_max);
	vec3 yard_colour = look_saturate(albedo * yard_lift, look_yard_saturation)
		* look_path_warmth;
	colour = mix(colour, yard_colour, yard);
	float path_lift = clamp(look_path_luma / luma, 1.0, look_path_lift_max);
	vec3 path_colour = look_saturate(albedo * path_lift, look_path_saturation)
		* look_path_warmth;
	colour = mix(colour, path_colour, path);

	float variation = look_variation_at(xz)
		* mix(1.0, look_path_variation_share, max(path, max(yard, pale) * 0.5));
	colour *= 1.0 + variation * 2.0 * look_variation;
	colour *= vec3(1.0) + vec3(variation, 0.0, -variation) * 2.0 * look_variation_hue;
	colour *= mix(look_slope_shade, 1.0,
		smoothstep(look_slope_up.y, look_slope_up.x, up));
	return look_from_linear(colour);
}

// What the debug views draw as emission (ALBEDO is black): 1, the class as
// a flat colour (terrain red, biome blend green, patch blue, walk deck
// magenta); 2, the weights, path in red, yard in green and pale in blue;
// 3, the reference luminance in steps (red above 0.08, green above 0.12,
// blue above 0.2).
vec3 look_debug_colour(vec3 reference, vec3 vertex_colour) {
	reference = look_to_linear(reference);
	if (look_debug == 2) {
		return look_weights(reference, vertex_colour) * 0.5;
	}
	if (look_debug == 3) {
		float luma = look_luma(reference);
		return vec3(luma > 0.08 ? 0.5 : 0.0, luma > 0.12 ? 0.5 : 0.0,
			luma > 0.2 ? 0.5 : 0.0);
	}
	return look_class == 0 ? vec3(0.5, 0.0, 0.0)
		: look_class == 1 ? vec3(0.0, 0.5, 0.0)
		: look_class == 2 ? vec3(0.0, 0.0, 0.5)
		: vec3(0.5, 0.0, 0.5);
}
