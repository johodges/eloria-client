class_name LookGround
extends RefCounted
## Look pass layer L2: gives the ground a value hierarchy - pale roads over a
## deeper, richer verge - by swapping its materials for painted ones as each
## region, chunk and neighbour is finished. Does nothing unless
## LookProfile.enabled().
##
## The ground has no per-class materials to retune. Grass and road colour on
## the continent come from four sources, and each gets a painted stand-in that
## keeps its texture, UVs and colour and adds the paint (see
## painted_ground_paint.gdshaderinc):
##
## - Terrain_*: one texture tinted by vertex colour. The exporter paints its
##   worn roads into that vertex colour, so the shader finds them by colour.
## - AuthoredGround_<region>Base: the biome blend. Its shader is copied at run
##   time with the paint spliced onto its albedo, so it follows whatever
##   biome_blend.gdshader becomes; if the splice no longer fits, the blend is
##   left as it is and a warning says so.
## - AuthoredGround_<region>_<patch>: tinted overlays (yards, forecourts, leaf
##   litter), lifted a little, cut to the footprint the exporter wrote into
##   their vertex alpha (which the import never read) with a crisp, broken
##   edge. Pale paving keeps almost all of its geometry, as develop draws it.
## - Walk_*: the worn-road decks, painted as paths whatever their colour and
##   cut at their rim the same way, so a road no longer ends in a hard step
##   along the terrain cells, with a dark edging band beyond it. A road that
##   runs through pale paving is painted darker than the paving, not lighter.
##
## One painted material is made per source material and shared by every mesh
## that used it (the biome blend is already one material per node). A root is
## painted with its region's trims (LookProfile.GROUND_TRIMS), and its roads
## learn where its pale paving lies from the paving patches' bounds. They go in
## as surface overrides, never into the shared material or the mesh, and only
## after the loader has taken its cache snapshot, so a map cache written with
## the pass on holds the loader's own materials and a client started without
## it reads develop's ground. A batched mesh is skipped: its MultiMesh draws
## the mesh's own material and the ground carries collision, which the batcher
## refuses anyway.
##
## Continent maps are painted where the loader finishes them, which covers the
## active territory's chunks, every neighbour region and their chunks, on the
## worker or main thread alike. A map outside the continent is painted after
## main has bound it instead, because its scene script (Lantern Reach's among
## them) switches vertex colour on for every material only then.

const SHADER_OPAQUE := preload("res://src/world/look/painted_ground.gdshader")
const SHADER_TWO_SIDED := preload("res://src/world/look/painted_ground_two_sided.gdshader")
const SHADER_OVERLAY := preload("res://src/world/look/painted_ground_overlay.gdshader")
const SHADER_BLEND := preload("res://src/world/look/painted_ground_blend.gdshader")
const SHADER_DECK := preload("res://src/world/look/painted_ground_deck.gdshader")

const BIOME_SHADER_PATH := "res://src/world/biome_blend.gdshader"
const PAINT_INCLUDE := "res://src/world/look/painted_ground_paint.gdshaderinc"
## The line of the biome blend the paint is spliced onto.
const BIOME_ALBEDO_LINE := "ALBEDO = color / total;"
const BIOME_PAINTED_LINE := "if (look_debug > 0) { ALBEDO = vec3(0.0); " \
	+ "EMISSION = look_debug_colour(color / total, vec3(1.0)); } " \
	+ "else { ALBEDO = look_paint(color / total, color / total, vec3(1.0), " \
	+ "continent_xz, abs((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y)); }"

## Marks a material this layer made, so painting a root twice is harmless.
const PAINTED_META := &"look_painted_ground"
## WorldLoader.BATCH_META: the node is hidden and a MultiMesh draws it.
const BATCH_META := &"static_batch"

enum Kind { NONE = -1, TERRAIN = 0, BIOME = 1, PATCH = 2, DECK = 3 }

static var _biome_mutex := Mutex.new()
static var _biome_tried := false
static var _biome_shader: Shader
static var _biome_uniforms := PackedStringArray()

## Paints a continent map's root as the loader finishes it. Maps outside the
## continent wait for `paint_bound`. Returns the surfaces painted.
static func paint_loaded(root: Node, manifest: WorldManifest) -> int:
	if not LookProfile.enabled() or root == null or manifest == null:
		return 0
	if not manifest.data.has("continentGeography"):
		return 0
	return paint(root, region_of(manifest))

## Paints a map outside the continent once main has bound it and its scene
## script has set its materials up. Interiors are left alone, as the grade
## leaves them. Returns the surfaces painted.
static func paint_bound(root: Node, manifest: WorldManifest) -> int:
	if not LookProfile.enabled() or root == null or manifest == null:
		return 0
	if manifest.data.has("continentGeography") or not _outdoor(manifest):
		return 0
	return paint(root, region_of(manifest))

## The region a manifest paints as: a continent chunk's own region
## (`<region>__chunk_<x>_<z>`), or the map itself.
static func region_of(manifest: WorldManifest) -> String:
	return manifest.asset_id().get_slice("__chunk_", 0)

## Paints every ground surface under `root`, with `region`'s trims. Safe to
## call again on a root it has already painted.
static func paint(root: Node, region := "") -> int:
	if not LookProfile.enabled() or root == null:
		return 0
	var ground: Array[MeshInstance3D] = []
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh == null or mesh_instance.material_override != null \
				or mesh_instance.has_meta(BATCH_META):
			continue
		if kind_of(String(mesh_instance.name)) != Kind.NONE:
			ground.append(mesh_instance)
	var paving := paving_rects(ground)
	var made: Dictionary = {}
	var surfaces := 0
	for mesh_instance: MeshInstance3D in ground:
		var kind := kind_of(String(mesh_instance.name))
		for surface: int in mesh_instance.mesh.get_surface_count():
			var source: Material = mesh_instance.get_active_material(surface)
			if source == null or source.has_meta(PAINTED_META):
				continue
			var key := source.get_instance_id()
			if not made.has(key):
				made[key] = painted_for(source, kind, mesh_instance.mesh, surface,
					region, paving)
			var painted: Material = made[key]
			if painted == null:
				continue
			mesh_instance.set_surface_override_material(surface, painted)
			surfaces += 1
	var materials := 0
	for value: Variant in made.values():
		if value != null:
			materials += 1
	if surfaces > 0:
		print("look_ground stage=painted root=%s surfaces=%d materials=%d"
			% [root.name, surfaces, materials])
	return surfaces

## The ground class a mesh belongs to, from the names the continent exporter
## and the island scenes give it.
static func kind_of(node_name: String) -> Kind:
	if node_name.begins_with("Water_") or node_name.begins_with("Scenery_Water"):
		return Kind.NONE
	if node_name.begins_with("Terrain_") or node_name.begins_with("Walk_Terrain"):
		return Kind.TERRAIN
	if node_name.begins_with("AuthoredGround_"):
		return Kind.PATCH
	if node_name.begins_with("Walk_"):
		return Kind.DECK
	return Kind.NONE

## Pale stone paving: an authored patch whose tint is bright and nearly grey
## (LookProfile.PAVING_TINT_VALUE). Roads through it go darker than it.
static func is_paving(material: Material) -> bool:
	var standard := material as BaseMaterial3D
	if standard == null or standard.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
		return false
	return standard.albedo_color.v >= LookProfile.PAVING_TINT_VALUE \
		and standard.albedo_color.s <= LookProfile.PAVING_TINT_SATURATION

## The continent-space bounds (min x, min z, max x, max z) of the pale paving
## among `ground`, the largest first. Mesh space is the continent frame (see
## painted_ground_surface.gdshaderinc), so a mesh's own AABB is enough and no
## vertex has to be read back.
static func paving_rects(ground: Array[MeshInstance3D]) -> PackedVector4Array:
	var boxes: Array[AABB] = []
	for mesh_instance: MeshInstance3D in ground:
		if kind_of(String(mesh_instance.name)) != Kind.PATCH:
			continue
		var material := mesh_instance.get_active_material(0)
		if material != null and not material.has_meta(PAINTED_META) and is_paving(material):
			boxes.append(mesh_instance.get_aabb())
	boxes.sort_custom(func(a: AABB, b: AABB) -> bool:
		return a.size.x * a.size.z > b.size.x * b.size.z)
	var rects := PackedVector4Array()
	for box: AABB in boxes.slice(0, LookProfile.PAVING_RECTS_MAX):
		rects.append(Vector4(box.position.x, box.position.z, box.end.x, box.end.z))
	return rects

## The painted stand-in for `source`, or null when it is not ground this
## layer paints (water, bridge timber, an invisible threshold, a cut-out).
## `region` picks the ground trims; `paving` is where the root's pale paving
## lies, for its roads.
static func painted_for(source: Material, kind: Kind, mesh: Mesh, surface: int,
		region := "", paving := PackedVector4Array()) -> Material:
	if source is ShaderMaterial:
		var shader := (source as ShaderMaterial).shader
		if shader != null and shader.resource_path == BIOME_SHADER_PATH:
			return _painted_biome(source as ShaderMaterial, region)
		return null
	var standard := source as BaseMaterial3D
	if standard == null or standard.albedo_color.a <= 0.01:
		return null
	var shader: Shader
	var blended := false
	match standard.transparency:
		BaseMaterial3D.TRANSPARENCY_DISABLED:
			if standard.cull_mode == BaseMaterial3D.CULL_BACK:
				shader = SHADER_OPAQUE
			elif standard.cull_mode == BaseMaterial3D.CULL_DISABLED:
				shader = SHADER_TWO_SIDED
		BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS:
			shader = SHADER_DECK if kind == Kind.DECK else SHADER_OVERLAY
			blended = true
		BaseMaterial3D.TRANSPARENCY_ALPHA:
			shader = SHADER_BLEND
			blended = true
	if shader == null:
		return null
	# An opaque deck without vertex colour is a bridge's timber or cobble, not
	# a worn road: it stays a bridge.
	if kind == Kind.DECK and not blended and not standard.vertex_color_use_as_albedo:
		return null
	var has_colour: bool = (mesh.surface_get_format(surface) & Mesh.ARRAY_FORMAT_COLOR) != 0
	var painted := ShaderMaterial.new()
	painted.resource_name = standard.resource_name
	painted.shader = shader
	painted.render_priority = standard.render_priority
	painted.next_pass = standard.next_pass
	painted.set_shader_parameter(&"albedo_texture", standard.albedo_texture)
	painted.set_shader_parameter(&"albedo_color", standard.albedo_color)
	painted.set_shader_parameter(&"use_vertex_albedo",
		standard.vertex_color_use_as_albedo and has_colour)
	painted.set_shader_parameter(&"vertex_albedo_srgb", standard.vertex_color_is_srgb)
	painted.set_shader_parameter(&"use_vertex_alpha", blended and has_colour
		and kind != Kind.TERRAIN)
	var rim := LookProfile.DECK_RIM
	if kind == Kind.PATCH:
		rim = LookProfile.PAVING_RIM if is_paving(standard) else LookProfile.PATCH_RIM
	painted.set_shader_parameter(&"look_rim", rim)
	painted.set_shader_parameter(&"look_opacity",
		LookProfile.PATCH_OPACITY if kind == Kind.PATCH and not is_paving(standard) else 1.0)
	painted.set_shader_parameter(&"look_rim_noise_metres", LookProfile.RIM_NOISE_METRES)
	painted.set_shader_parameter(&"look_edge_band",
		LookProfile.EDGE_BAND if kind == Kind.DECK else 0.0)
	painted.set_shader_parameter(&"look_edge_band_from", LookProfile.EDGE_BAND_FROM)
	painted.set_shader_parameter(&"look_edge_band_push", LookProfile.EDGE_BAND_PUSH_METRES)
	painted.set_shader_parameter(&"has_normal_texture",
		standard.normal_enabled and standard.normal_texture != null)
	painted.set_shader_parameter(&"normal_texture", standard.normal_texture)
	painted.set_shader_parameter(&"normal_scale", standard.normal_scale)
	painted.set_shader_parameter(&"roughness_value", standard.roughness)
	painted.set_shader_parameter(&"metallic_value", standard.metallic)
	painted.set_shader_parameter(&"specular_value", standard.metallic_specular)
	painted.set_shader_parameter(&"uv1_scale", standard.uv1_scale)
	painted.set_shader_parameter(&"uv1_offset", standard.uv1_offset)
	# An opaque patch is a base surface the biome blend did not take over:
	# verge, not a yard.
	var class_kind := kind
	if kind == Kind.PATCH and not blended:
		class_kind = Kind.BIOME
	_set_paint(painted, class_kind,
		kind == Kind.TERRAIN and standard.vertex_color_use_as_albedo and has_colour,
		region, paving if kind == Kind.DECK or (kind == Kind.PATCH and blended
			and not is_paving(standard)) else PackedVector4Array())
	return painted

static func _painted_biome(source: ShaderMaterial, region: String) -> ShaderMaterial:
	var shader := _biome_painted_shader()
	if shader == null:
		return null
	var painted := ShaderMaterial.new()
	painted.resource_name = source.resource_name
	painted.shader = shader
	painted.render_priority = source.render_priority
	painted.next_pass = source.next_pass
	for uniform_name: String in _biome_uniforms:
		painted.set_shader_parameter(uniform_name, source.get_shader_parameter(uniform_name))
	_set_paint(painted, Kind.BIOME, false, region, PackedVector4Array())
	return painted

## The biome blend with the paint spliced onto its albedo, made once and
## shared. Chunks load on worker threads, so the first two can race here.
static func _biome_painted_shader() -> Shader:
	_biome_mutex.lock()
	if not _biome_tried:
		_biome_tried = true
		var source := load(BIOME_SHADER_PATH) as Shader
		var code := source.code if source != null else ""
		var header_end := code.find(";", code.find("render_mode"))
		if code.count(BIOME_ALBEDO_LINE) != 1 or code.find("render_mode") < 0 \
				or header_end < 0:
			push_warning("look_ground: biome_blend.gdshader no longer has the line "
				+ "the paint is spliced onto; the biome blend is left unpainted")
		else:
			code = code.replace(BIOME_ALBEDO_LINE, BIOME_PAINTED_LINE)
			code = code.insert(header_end + 1, "\n#include \"%s\"\n" % PAINT_INCLUDE)
			var shader := Shader.new()
			shader.code = code
			_biome_shader = shader
			var uniform_pattern := RegEx.create_from_string(
				"(?m)^\\s*uniform\\s+\\w+\\s+(\\w+)")
			for found: RegExMatch in uniform_pattern.search_all(source.code):
				_biome_uniforms.append(found.get_string(1))
	var result := _biome_shader
	_biome_mutex.unlock()
	return result

static func _set_paint(painted: ShaderMaterial, kind: Kind, road_detect: bool,
		region: String, paving: PackedVector4Array) -> void:
	painted.set_meta(PAINTED_META, true)
	painted.set_shader_parameter(&"look_class", int(kind))
	painted.set_shader_parameter(&"look_debug",
		clampi(OS.get_environment(LookProfile.GROUND_DEBUG_VARIABLE).to_int(), 0, 3))
	painted.set_shader_parameter(&"look_path_force", 1.0 if kind == Kind.DECK else 0.0)
	painted.set_shader_parameter(&"look_yard", 1.0 if kind == Kind.PATCH else 0.0)
	painted.set_shader_parameter(&"look_pale", 0.0 if kind == Kind.BIOME else 1.0)
	painted.set_shader_parameter(&"look_road_detect", 1.0 if road_detect else 0.0)
	var road := LookProfile.TERRAIN_ROAD_COLOUR
	painted.set_shader_parameter(&"look_road_colour", Vector3(road.r, road.g, road.b))
	painted.set_shader_parameter(&"look_road_tolerance", LookProfile.TERRAIN_ROAD_TOLERANCE)
	painted.set_shader_parameter(&"look_path_luma",
		_trim(region, "path_luma", LookProfile.PATH_LUMA))
	painted.set_shader_parameter(&"look_path_lift_max", LookProfile.PATH_LIFT_MAX)
	var tint: Color = _trim(region, "path_tint", LookProfile.PATH_TINT)
	painted.set_shader_parameter(&"look_path_tint", Vector3(tint.r, tint.g, tint.b))
	painted.set_shader_parameter(&"look_path_chroma",
		_trim(region, "path_chroma", LookProfile.PATH_CHROMA))
	painted.set_shader_parameter(&"look_path_detail", LookProfile.PATH_DETAIL)
	painted.set_shader_parameter(&"look_path_fine_metres", LookProfile.PATH_FINE_METRES)
	painted.set_shader_parameter(&"look_path_fine", LookProfile.PATH_FINE)
	var rects := paving.duplicate()
	rects.resize(LookProfile.PAVING_RECTS_MAX)
	painted.set_shader_parameter(&"look_paving_rects", rects)
	painted.set_shader_parameter(&"look_paving_count", mini(paving.size(),
		LookProfile.PAVING_RECTS_MAX))
	painted.set_shader_parameter(&"look_paving_inset", LookProfile.PAVING_INSET_METRES)
	painted.set_shader_parameter(&"look_paving_luma", LookProfile.ROAD_UNDER_PAVING_LUMA)
	painted.set_shader_parameter(&"look_paving_chroma", LookProfile.ROAD_UNDER_PAVING_CHROMA)
	painted.set_shader_parameter(&"look_compat_chroma", LookProfile.COMPAT_CHROMA)
	painted.set_shader_parameter(&"look_yard_luma", LookProfile.YARD_LUMA)
	painted.set_shader_parameter(&"look_yard_lift_max", LookProfile.YARD_LIFT_MAX)
	painted.set_shader_parameter(&"look_yard_saturation", LookProfile.YARD_SATURATION)
	painted.set_shader_parameter(&"look_pale_luma", LookProfile.PALE_LUMA)
	painted.set_shader_parameter(&"look_gold_hue", LookProfile.GOLD_HUE)
	painted.set_shader_parameter(&"look_gold_saturation", LookProfile.GOLD_SATURATION)
	painted.set_shader_parameter(&"look_gold_value", LookProfile.GOLD_VALUE)
	painted.set_shader_parameter(&"look_gold_chroma", LookProfile.GOLD_CHROMA)
	painted.set_shader_parameter(&"look_gold_chroma_compat", LookProfile.GOLD_CHROMA_COMPAT)
	painted.set_shader_parameter(&"look_verge_value_green",
		_trim(region, "verge_value_green", LookProfile.VERGE_VALUE_GREEN))
	painted.set_shader_parameter(&"look_verge_value_earth",
		_trim(region, "verge_value_earth", LookProfile.VERGE_VALUE_EARTH))
	painted.set_shader_parameter(&"look_verge_saturation",
		_trim(region, "verge_saturation", LookProfile.VERGE_SATURATION))
	painted.set_shader_parameter(&"look_verge_green_red", LookProfile.VERGE_GREEN_RED)
	painted.set_shader_parameter(&"look_verge_fine_metres", LookProfile.VERGE_FINE_METRES)
	painted.set_shader_parameter(&"look_verge_fine", LookProfile.VERGE_FINE)
	painted.set_shader_parameter(&"look_variation_metres", LookProfile.VARIATION_METRES)
	painted.set_shader_parameter(&"look_variation", LookProfile.VARIATION)
	painted.set_shader_parameter(&"look_variation_hue", LookProfile.VARIATION_HUE)
	painted.set_shader_parameter(&"look_path_variation_share",
		LookProfile.PATH_VARIATION_SHARE)
	painted.set_shader_parameter(&"look_slope_up", LookProfile.SLOPE_UP)
	painted.set_shader_parameter(&"look_slope_shade", LookProfile.SLOPE_SHADE)

static func _trim(region: String, key: String, fallback: Variant) -> Variant:
	return LookProfile.ground_value(region, key, fallback)

## An outdoor map declares a sun and does not disable it, as LookGrade reads it.
static func _outdoor(manifest: WorldManifest) -> bool:
	var environment: Variant = manifest.data.get("environment")
	if environment is not Dictionary:
		return false
	var sun: Variant = (environment as Dictionary).get("sun")
	return sun is Dictionary and bool((sun as Dictionary).get("enabled", true))
