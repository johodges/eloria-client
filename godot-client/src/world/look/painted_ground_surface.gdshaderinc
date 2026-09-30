// Look pass layer L2: the body of a painted ground material.
//
// Stands in for the StandardMaterial3D a ground mesh imported with, keeping
// what those materials use - the albedo texture and tint, UV scale and
// offset, the vertex colour where the source took its albedo from it, the
// normal map, roughness and specular - and passing the result through
// look_paint. The painted_ground*.gdshader files include this after choosing
// the render mode the source material had (culling, and whether it blends).
//
// A shader that defines LOOK_GROUND_ALPHA writes alpha as the source did, and
// multiplies in the vertex alpha when use_vertex_alpha is set. The continent
// exporter feathers every authored ground patch and walk deck through vertex
// alpha (the patch's blend width, the road's edge feather), but the imported
// StandardMaterial3D never reads vertex colour on a blended surface, so on
// develop those edges are hard steps along the terrain cells.

#include "res://src/world/look/painted_ground_paint.gdshaderinc"

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform bool use_vertex_albedo = false;
uniform bool vertex_albedo_srgb = false;
uniform bool use_vertex_alpha = false;
// The vertex alpha from which the surface is solid (1 takes it as it is).
uniform float vertex_alpha_full = 1.0;
uniform sampler2D normal_texture : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform bool has_normal_texture = false;
uniform float normal_scale = 1.0;
uniform float roughness_value : hint_range(0.0, 1.0) = 1.0;
uniform float metallic_value : hint_range(0.0, 1.0) = 0.0;
uniform float specular_value : hint_range(0.0, 1.0) = 0.5;
uniform vec3 uv1_scale = vec3(1.0);
uniform vec3 uv1_offset = vec3(0.0);

// The continent's exports store continent positions in the mesh and place
// them with translation-only wrappers, so object space is the continent frame
// the biome blend paints in: the variation runs on unbroken across chunk
// seams and from terrain onto patches, and a crossing that rebases the world
// does not slide it under the player.
varying vec2 look_ground_xz;

void vertex() {
	UV = UV * uv1_scale.xy + uv1_offset.xy;
	look_ground_xz = VERTEX.xz;
}

void fragment() {
	vec4 texel = texture(albedo_texture, UV);
	vec3 albedo = texel.rgb * albedo_color.rgb;
	vec3 vertex_colour = COLOR.rgb;
	if (vertex_albedo_srgb) {
		vertex_colour = mix(pow((vertex_colour + vec3(0.055)) * (1.0 / 1.055), vec3(2.4)),
			vertex_colour * (1.0 / 12.92), lessThan(vertex_colour, vec3(0.04045)));
	}
	// The smallest mip is the texture's mean colour: the reference the paint
	// classes and lifts by, so a lifted path keeps its texture's grain.
	vec3 reference = textureLod(albedo_texture, UV, 16.0).rgb * albedo_color.rgb;
	if (use_vertex_albedo) {
		albedo *= vertex_colour;
		reference *= vertex_colour;
	}
	float up = abs((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y);
	if (look_debug > 0) {
		ALBEDO = vec3(0.0);
		EMISSION = look_debug_colour(reference, vertex_colour);
	} else {
		ALBEDO = look_paint(albedo, reference, vertex_colour, look_ground_xz, up);
	}
	ROUGHNESS = roughness_value;
	METALLIC = metallic_value;
	SPECULAR = specular_value;
	if (has_normal_texture) {
		NORMAL_MAP = texture(normal_texture, UV).rgb;
		NORMAL_MAP_DEPTH = normal_scale;
	}
#ifdef LOOK_GROUND_ALPHA
	ALPHA = texel.a * albedo_color.a
		* (use_vertex_alpha ? clamp(COLOR.a / vertex_alpha_full, 0.0, 1.0) : 1.0);
#endif
}
