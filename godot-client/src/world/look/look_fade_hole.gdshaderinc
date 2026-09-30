// Look pass layer L3: the hole a faded occluder opens around the player.
//
// Included by every faded look material (painted_foliage_body's faded
// variants, look_faded_standard and the blended painted ground). Develop fades
// an occluder by blending all of it towards glass. The pass first dithered
// all of it instead, at 35 % coverage with one-pixel interleaved gradient
// noise, and at 1:1 that read as a diagonal crosshatch, a window screen laid
// over up to a fifth of the frame and locked to the screen while the world
// moved under it. So the occluder now stays solid and opens a round hole
// where it covers the player, as the reference frames' crown fade does:
//
// - the hole is centred on the player's chest (look_fade_focus, a world
//   position OccluderFade hands LookFade every frame) and measured across the
//   view at the player's own depth, so it is look_fade_hole_metres wide in the
//   world whatever the zoom;
// - it opens with the fade (look_fade_open, 0 closed to 1 open over
//   OccluderFade's FADE_SECONDS) rather than popping;
// - only what stands in front of the player is cut, so a wall or the far half
//   of a crown behind them stays whole;
// - its last look_fade_rim_metres are a dithered rim, not a hard circle: a
//   4 x 4 Bayer pattern on 2 x 2 pixel blocks, which makes no diagonal lines
//   and is coarse enough to read as a soft brush edge rather than a mesh.
//
// Nothing here reads the screen, so it runs in the compatibility renderer
// and in Forward+ alike. A faded copy never casts its own shadow (LookFade
// hands that to a solid twin, or turns it off for a crown), so the shadow pass
// never sees the hole.

// How far the hole is open, 0 (closed, the occluder whole) to 1.
uniform float look_fade_open = 0.0;
// The world position the hole is centred on (the player's chest).
uniform vec3 look_fade_focus = vec3(0.0);
// The hole's radius and its dithered rim, in metres across the view at the
// focus's depth, and how far behind the focus the cut still reaches.
uniform float look_fade_hole_metres = 2.4;
uniform float look_fade_rim_metres = 0.4;
uniform float look_fade_behind_metres = 0.4;

// The 4 x 4 Bayer threshold (0..1) of the 2 x 2 pixel block a fragment lies
// in: two interleaved 2 x 2 Bayer matrices, (0 2 / 3 1).
float look_fade_bayer(vec2 fragment) {
	ivec2 cell = ivec2(floor(fragment * 0.5));
	int x = cell.x & 3;
	int y = cell.y & 3;
	int fine = 2 * ((x & 1) ^ (y & 1)) + (y & 1);
	int coarse = 2 * (((x >> 1) & 1) ^ ((y >> 1) & 1)) + ((y >> 1) & 1);
	return (float(4 * fine + coarse) + 0.5) / 16.0;
}

// True where the faded occluder is cut away. `view_vertex` is the fragment's
// view-space position (VERTEX), the matrices are the fragment stage's own.
bool look_fade_cut(vec3 view_vertex, mat4 view_matrix, mat4 projection, vec2 fragment) {
	if (look_fade_open <= 0.001) {
		return false;
	}
	vec3 focus = (view_matrix * vec4(look_fade_focus, 1.0)).xyz;
	// View space looks down -z: a fragment further away than the focus (and
	// its body) is behind the player and stays.
	if (view_vertex.z < focus.z - look_fade_behind_metres) {
		return false;
	}
	// Where the fragment's line of sight crosses the focus's depth. An
	// orthographic camera (the map cameras) sees straight along -z.
	vec2 across = view_vertex.xy;
	if (projection[3][3] < 0.5) {
		across *= focus.z / min(view_vertex.z, -0.001);
	}
	float radius = look_fade_hole_metres * look_fade_open;
	float coverage = smoothstep(radius - look_fade_rim_metres, radius,
		length(across - focus.xy));
	return coverage < look_fade_bayer(fragment);
}
