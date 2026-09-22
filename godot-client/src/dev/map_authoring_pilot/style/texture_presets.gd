@tool
class_name MapAuthoringTexturePresets
extends RefCounted

## Small, named material library for the map-authoring preview. Every call
## returns a new material so changing one style cannot edit another style.

const CUSTOM := "Custom"
const GRASS := "Grass"
const WORN_EARTH := "Worn earth"
const TIMBER := "Timber"
const STONE := "Stone"
const THATCH := "Thatch"
const TEXTILE := "Textile"
const CANVAS := "Canvas"
const METAL := "Metal"
const LEATHER := "Leather"
const HIDE := "Hide"
const BONE := "Bone"
const CRYSTAL := "Crystal"
const CAVERN := "Cavern"
const SLATE := "Slate"

const PRESET_NAMES := [
	CUSTOM, GRASS, WORN_EARTH, TIMBER, STONE, THATCH, TEXTILE, CANVAS,
	METAL, LEATHER, HIDE, BONE, CRYSTAL, CAVERN, SLATE,
]

const ROAD_MESH_UV_DENSITY := 0.24
const _TEXTURE_ROOT := "res://src/dev/map_authoring_pilot/style/textures/"
const _WORN_PATH_SHADER := preload("res://src/dev/map_authoring_pilot/style/worn_path.gdshader")

# Values with a direct Last Lantern or Sunmane authoring equivalent keep its
# tint and scale. The other families use restrained neutral tints and scales
# based on their authored real-world repeat size.
const _PRESETS := {
	GRASS: {
		"family": "ground", "tint": Color(0.78, 0.86, 0.72, 1.0),
		"roughness": 1.0, "normal_strength": 0.75, "density": 0.24,
	},
	WORN_EARTH: {
		"family": "ground", "tint": Color(0.60, 0.48, 0.31, 1.0),
		"roughness": 1.0, "normal_strength": 0.72, "density": 0.24,
	},
	TIMBER: {
		"family": "timber", "tint": Color(0.65, 0.64, 0.59, 1.0),
		"roughness": 0.86, "normal_strength": 0.8, "density": 0.5,
	},
	STONE: {
		"family": "stone", "tint": Color(0.48, 0.56, 0.56, 1.0),
		"roughness": 1.0, "normal_strength": 0.72, "density": 0.8,
	},
	THATCH: {
		"family": "thatch", "tint": Color(1.0, 0.94, 0.76, 1.0),
		"roughness": 0.92, "normal_strength": 0.7, "density": 0.56,
	},
	TEXTILE: {
		"family": "textile", "tint": Color(0.58, 0.45, 0.25, 1.0),
		"roughness": 0.86, "normal_strength": 0.65, "density": 2.0,
	},
	CANVAS: {
		"family": "canvas", "tint": Color(0.78, 0.77, 0.65, 1.0),
		"roughness": 0.88, "normal_strength": 0.65, "density": 1.2,
	},
	METAL: {
		"family": "metal", "tint": Color.WHITE,
		"roughness": 0.44, "normal_strength": 0.75, "density": 2.0,
		"metallic": 1.0,
	},
	LEATHER: {
		"family": "leather", "tint": Color(0.28, 0.25, 0.19, 1.0),
		"roughness": 0.70, "normal_strength": 0.7, "density": 1.0,
	},
	HIDE: {
		"family": "hide", "tint": Color(0.92, 0.88, 0.78, 1.0),
		"roughness": 0.86, "normal_strength": 0.6, "density": 1.1,
	},
	BONE: {
		"family": "bone", "tint": Color(0.90, 0.86, 0.72, 1.0),
		"roughness": 0.52, "normal_strength": 0.65, "density": 1.67,
	},
	CRYSTAL: {
		"family": "crystal", "tint": Color(0.72, 0.56, 0.86, 1.0),
		"roughness": 0.18, "normal_strength": 0.8, "density": 0.9,
	},
	CAVERN: {
		"family": "cavern", "tint": Color(0.66, 0.62, 0.56, 1.0),
		"roughness": 0.93, "normal_strength": 0.72, "density": 0.23,
	},
}


static func create_material(preset: String) -> Material:
	if preset == SLATE:
		var slate := StandardMaterial3D.new()
		slate.albedo_color = Color(0.095, 0.17, 0.20, 1.0)
		slate.roughness = 0.55
		slate.uv1_scale = Vector3(0.8, 0.8, 0.8)
		slate.uv1_triplanar = true
		slate.uv1_world_triplanar = true
		slate.cull_mode = BaseMaterial3D.CULL_DISABLED
		return slate
	if not _PRESETS.has(preset):
		return null
	var spec: Dictionary = _PRESETS[preset]
	var family: String = spec["family"]
	var material := ORMMaterial3D.new()
	material.albedo_color = spec["tint"]
	material.albedo_texture = _texture(family, "basecolor")
	material.roughness = spec["roughness"]
	material.metallic = spec.get("metallic", 0.0)
	material.normal_enabled = true
	material.normal_scale = spec["normal_strength"]
	material.normal_texture = _texture(family, "normal")
	material.orm_texture = _texture(family, "orm")
	material.uv1_scale = Vector3.ONE * float(spec["density"])
	material.uv1_triplanar = true
	material.uv1_world_triplanar = true
	material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return material


static func create_road_material(preset: String) -> ShaderMaterial:
	if preset == CUSTOM or not _PRESETS.has(preset) and preset != SLATE:
		return null
	var material := ShaderMaterial.new()
	material.render_priority = 1
	material.shader = _WORN_PATH_SHADER
	if preset == SLATE:
		# The road shader always needs a complete texture triplet. Slate keeps its
		# established colour while borrowing unobtrusive stone surface detail.
		material.set_shader_parameter("ground_albedo", _texture("stone", "basecolor"))
		material.set_shader_parameter("ground_normal", _texture("stone", "normal"))
		material.set_shader_parameter("ground_orm", _texture("stone", "orm"))
		material.set_shader_parameter("worn_tint", Color(0.095, 0.17, 0.20, 1.0))
		material.set_shader_parameter("texture_scale", 0.8 / ROAD_MESH_UV_DENSITY)
		material.set_shader_parameter("roughness_multiplier", 0.55)
		material.set_shader_parameter("normal_strength", 0.72)
	else:
		var spec: Dictionary = _PRESETS[preset]
		var family: String = spec["family"]
		material.set_shader_parameter("ground_albedo", _texture(family, "basecolor"))
		material.set_shader_parameter("ground_normal", _texture(family, "normal"))
		material.set_shader_parameter("ground_orm", _texture(family, "orm"))
		material.set_shader_parameter("worn_tint", spec["tint"])
		material.set_shader_parameter(
			"texture_scale", float(spec["density"]) / ROAD_MESH_UV_DENSITY)
		material.set_shader_parameter("roughness_multiplier", 1.0)
		material.set_shader_parameter("normal_strength", spec["normal_strength"])
	material.set_shader_parameter("edge_feather", 0.16)
	return material


static func _texture(family: String, map_name: String) -> Texture2D:
	return load(_TEXTURE_ROOT + family + "-" + map_name + ".png") as Texture2D
