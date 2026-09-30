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
## painted with its region's trims (the `ground` section of its region file,
## LookProfile.ground_value), and its roads
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
const CONTINENT_WATER_PATH := "res://src/world/continent_water.gdshader"
const PAINT_INCLUDE := "res://src/world/look/painted_ground_paint.gdshaderinc"
## The line of the biome blend the paint is spliced onto.
const BIOME_ALBEDO_LINE := "ALBEDO = color / total;"
const BIOME_PAINTED_LINE := "if (look_debug > 0) { ALBEDO = vec3(0.0); " \
	+ "EMISSION = look_debug_colour(%s, vec3(1.0), continent_xz); } " \
	+ "else { ALBEDO = look_paint(color / total, %s, vec3(1.0), " \
	+ "continent_xz, abs((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).y)); }"
## The paint weighs the biome by its mean colour at a spot, its layers' mean
## texels (their smallest mips) mixed by the masks, as the other ground
## classes are weighed by their texture's mean. Weighed by each texel instead,
## the verge's depth (chosen by how green the colour is, over a narrow range)
## followed the grain, darkening the greener texels and sparing the browner
## ones, and drew the south gate's field as a camouflage mottle. Spliced in
## before fragment() because it reads the blend's own samplers and tint
## functions; a blend that no longer has them keeps the per-texel reference.
const BIOME_REFERENCE_NAMES := ["region_weights", "secondary_weights", "base_tint_at(",
	"secondary_tint_at(", "base_albedo_3", "secondary_albedo_3", "void fragment()"]
const BIOME_REFERENCE_CALL := "look_biome_reference(region_weights, secondary_weights)"
const BIOME_REFERENCE_FUNCTION := """
// Look pass (layer L2): the blend's mean colour here, for weighing the paint.
vec3 look_biome_mean(int index, bool secondary) {
	if (secondary) {
		if (index == 0) return textureLod(secondary_albedo_0, vec2(0.5), 16.0).rgb;
		if (index == 1) return textureLod(secondary_albedo_1, vec2(0.5), 16.0).rgb;
		if (index == 2) return textureLod(secondary_albedo_2, vec2(0.5), 16.0).rgb;
		return textureLod(secondary_albedo_3, vec2(0.5), 16.0).rgb;
	}
	if (index == 0) return textureLod(base_albedo_0, vec2(0.5), 16.0).rgb;
	if (index == 1) return textureLod(base_albedo_1, vec2(0.5), 16.0).rgb;
	if (index == 2) return textureLod(base_albedo_2, vec2(0.5), 16.0).rgb;
	return textureLod(base_albedo_3, vec2(0.5), 16.0).rgb;
}

vec3 look_biome_reference(vec4 weights, vec4 secondary) {
	vec3 mean = vec3(0.0);
	float total = 0.0;
	for (int index = 0; index < 4; index++) {
		float weight = max(weights[index], 0.0);
		if (weight <= (1.0 / 255.0)) {
			continue;
		}
		vec3 base = look_biome_mean(index, false) * base_tint_at(index);
		vec3 other = look_biome_mean(index, true) * secondary_tint_at(index);
		mean += mix(base, other, clamp(secondary[index], 0.0, 1.0)) * weight;
		total += weight;
	}
	return mean / max(total, 0.00001);
}

"""

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
	decode_continent_sea(root)
	return paint(root, region_of(manifest))

## Forward+ only: the continent's sea (continent_water.gdshader, which the
## loader puts on every sea cell) is decoded to linear albedo at
## LookProfile.CONTINENT_SEA_VALUE, as a copy put in as the surface's
## override, so the loader's cache keeps the loader's own material. One value
## for the whole continent: the sea runs on across every region's border.
## Returns the surfaces changed.
static func decode_continent_sea(root: Node) -> int:
	if not LookProfile.enabled() or root == null or not LookProfile.forward_plus():
		return 0
	var changed := 0
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh == null:
			continue
		for surface: int in mesh_instance.get_surface_override_material_count():
			var sea := mesh_instance.get_surface_override_material(surface) as ShaderMaterial
			if sea == null or sea.shader == null or sea.has_meta(PAINTED_META) \
					or sea.shader.resource_path != CONTINENT_WATER_PATH:
				continue
			var decoded := sea.duplicate() as ShaderMaterial
			decoded.set_meta(PAINTED_META, true)
			decoded.set_shader_parameter(&"look_decode_albedo", true)
			decoded.set_shader_parameter(&"look_sea_value", LookProfile.CONTINENT_SEA_VALUE)
			mesh_instance.set_surface_override_material(surface, decoded)
			changed += 1
	return changed

## Paints a map outside the continent once main has bound it and its scene
## script has set its materials up. Interiors are left alone, as the grade
## leaves them. Returns the surfaces painted.
static func paint_bound(root: Node, manifest: WorldManifest) -> int:
	if not LookProfile.enabled() or root == null or manifest == null:
		return 0
	if manifest.data.has("continentGeography") or not outdoor(manifest):
		return 0
	decode_water(root, region_of(manifest))
	return paint(root, region_of(manifest))

## Forward+ only: a sea whose shader's colours were picked in the
## compatibility renderer (named in `region`'s file, `water.decode_albedo`,
## LookProfile.water_decode_value) is told to decode them to linear albedo,
## at that entry's value. Its scene script puts the shader on as a material
## override, which `paint` leaves alone. Returns the meshes changed.
static func decode_water(root: Node, region := "") -> int:
	if not LookProfile.enabled() or root == null or not LookProfile.forward_plus():
		return 0
	var changed := 0
	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		var water := (node as MeshInstance3D).material_override as ShaderMaterial
		if water == null or water.shader == null:
			continue
		var sea_value := LookProfile.water_decode_value(region, water.shader.resource_path)
		if sea_value <= 0.0:
			continue
		water.set_shader_parameter(&"look_decode_albedo", true)
		water.set_shader_parameter(&"look_sea_value", sea_value)
		changed += 1
	return changed

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
	var areas := material_areas(ground)
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
					region, paving, areas.get(key, Rect2()))
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
## (LookProfile.PAVING_TINT_VALUE), warm or neutral stone rather than grass,
## snow or granite, and not beach sand (`stone_tint`, `sand_tint`). Roads
## through it go darker than it.
static func is_paving(material: Material) -> bool:
	var standard := material as BaseMaterial3D
	if standard == null or standard.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
		return false
	var tint := standard.albedo_color
	return tint.v >= LookProfile.PAVING_TINT_VALUE \
		and tint.s <= LookProfile.PAVING_TINT_SATURATION \
		and stone_tint(tint) and not sand_tint(tint)

## Worn cobble or stone: a patch nearly as grey as paving if not as pale (the
## east gate's forecourt), drawn solid rather than as a glaze
## (LookProfile.COBBLE_TINT); stone by its hue, not grass or snow, and not sand.
static func is_cobble(material: Material) -> bool:
	var standard := material as BaseMaterial3D
	if standard == null or standard.transparency == BaseMaterial3D.TRANSPARENCY_DISABLED:
		return false
	var tint := standard.albedo_color
	return tint.v >= LookProfile.COBBLE_TINT.x and tint.s <= LookProfile.COBBLE_TINT.y \
		and stone_tint(tint) and not sand_tint(tint)

## True when a patch's tint is warm or neutral stone: its green does not lead
## both its red and blue (a pale grass meadow, #b8eba8, is not paving) and its
## blue does not lead its red (granite, #b3b5bf, a cave's snow or scree, a
## lilac scree scatter are not). LookProfile.STONE_TINT_LEAD.
static func stone_tint(tint: Color) -> bool:
	return tint.g - maxf(tint.r, tint.b) <= LookProfile.STONE_TINT_LEAD.x \
		and tint.b - tint.r <= LookProfile.STONE_TINT_LEAD.y

## True when a patch's tint is pale beach sand (LookProfile.SAND_TINT): the
## life passes' sand banks and beaches, #fff5d1. A glaze over the ground
## rather than paving, and no grass grows on it.
static func sand_tint(tint: Color) -> bool:
	return tint.v >= LookProfile.SAND_TINT.x and tint.s >= LookProfile.SAND_TINT.y

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

## Where each source material among `ground` lies: the continent-space
## rectangle (x, z) its meshes cover, by the material's instance id. Mesh
## space is the continent frame, so the meshes' own AABBs are enough. A
## painted material is handed the region borders near this area (LookBorders).
static func material_areas(ground: Array[MeshInstance3D]) -> Dictionary:
	var areas := {}
	for mesh_instance: MeshInstance3D in ground:
		var box := mesh_instance.get_aabb()
		var area := Rect2(box.position.x, box.position.z, box.size.x, box.size.z)
		for surface: int in mesh_instance.mesh.get_surface_count():
			var source: Material = mesh_instance.get_active_material(surface)
			if source == null:
				continue
			var key := source.get_instance_id()
			areas[key] = (areas[key] as Rect2).merge(area) if areas.has(key) else area
	return areas

## The painted stand-in for `source`, or null when it is not ground this
## layer paints (water, bridge timber, an invisible threshold, a cut-out).
## `region` picks the ground trims; `paving` is where the root's pale paving
## lies, for its roads; `area` is where its meshes lie, for the borders its
## trims fade across (none when empty).
static func painted_for(source: Material, kind: Kind, mesh: Mesh, surface: int,
		region := "", paving := PackedVector4Array(), area := Rect2()) -> Material:
	if source is ShaderMaterial:
		var shader := (source as ShaderMaterial).shader
		if shader != null and shader.resource_path == BIOME_SHADER_PATH:
			return _painted_biome(source as ShaderMaterial, region, area)
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
	# A blended painted surface dithers itself out if OccluderFade fades it
	# (layer L3, LookFade); it already carries the dither.
	if blended:
		painted.set_meta(LookFade.FADED_SHADER_META, shader)
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
		LookProfile.PATCH_OPACITY if kind == Kind.PATCH and not is_cobble(standard) else 1.0)
	var surface_tint := LookProfile.PAVING_SURFACE_TINT \
		if kind == Kind.PATCH and is_paving(standard) else Color.WHITE
	painted.set_shader_parameter(&"look_surface_tint",
		Vector3(surface_tint.r, surface_tint.g, surface_tint.b))
	painted.set_shader_parameter(&"look_rim_noise_metres", LookProfile.RIM_NOISE_METRES)
	painted.set_shader_parameter(&"look_edge_band",
		LookProfile.EDGE_BAND if kind == Kind.DECK else 0.0)
	painted.set_shader_parameter(&"look_edge_band_paving",
		LookProfile.EDGE_BAND_PAVING if kind == Kind.DECK else 0.0)
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
			and not is_paving(standard)) else PackedVector4Array(), area)
	return painted

static func _painted_biome(source: ShaderMaterial, region: String,
		area := Rect2()) -> ShaderMaterial:
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
	_set_paint(painted, Kind.BIOME, false, region, PackedVector4Array(), area)
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
			var reference := "color / total"
			var fragment := code.find("void fragment()")
			var spliceable := true
			for needle: String in BIOME_REFERENCE_NAMES:
				spliceable = spliceable and code.contains(needle)
			if spliceable and code.count("void fragment()") == 1:
				code = code.insert(fragment, BIOME_REFERENCE_FUNCTION)
				reference = BIOME_REFERENCE_CALL
			else:
				push_warning("look_ground: biome_blend.gdshader's layers are not where the "
					+ "paint expects them; the biome is weighed texel by texel")
			code = code.replace(BIOME_ALBEDO_LINE, BIOME_PAINTED_LINE % [reference, reference])
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
		region: String, paving: PackedVector4Array, area := Rect2()) -> void:
	painted.set_meta(PAINTED_META, true)
	painted.set_shader_parameter(&"look_class", int(kind))
	painted.set_shader_parameter(&"look_debug",
		clampi(OS.get_environment(LookProfile.GROUND_DEBUG_VARIABLE).to_int(), 0, 4))
	_set_border(painted, LookBorders.near(region, area, LookProfile.BORDER_FEATHER_METRES)
		if area.has_area() else {})
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
	var paving_tint := LookProfile.ROAD_UNDER_PAVING_TINT
	painted.set_shader_parameter(&"look_paving_tint",
		Vector3(paving_tint.r, paving_tint.g, paving_tint.b))
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
	painted.set_shader_parameter(&"look_gold_value_compat", LookProfile.GOLD_VALUE_COMPAT)
	painted.set_shader_parameter(&"look_verge_value_green",
		_trim(region, "verge_value_green", LookProfile.VERGE_VALUE_GREEN))
	painted.set_shader_parameter(&"look_verge_value_earth",
		_trim(region, "verge_value_earth", LookProfile.VERGE_VALUE_EARTH))
	painted.set_shader_parameter(&"look_verge_saturation",
		_trim(region, "verge_saturation", LookProfile.VERGE_SATURATION))
	painted.set_shader_parameter(&"look_verge_green_red",
		_trim(region, "verge_green_red", LookProfile.VERGE_GREEN_RED))
	painted.set_shader_parameter(&"look_verge_fine_metres", LookProfile.VERGE_FINE_METRES)
	painted.set_shader_parameter(&"look_verge_fine", LookProfile.VERGE_FINE)
	painted.set_shader_parameter(&"look_verge_grain", LookProfile.VERGE_GRAIN)
	painted.set_shader_parameter(&"look_variation_metres", LookProfile.VARIATION_METRES)
	painted.set_shader_parameter(&"look_variation", LookProfile.VARIATION)
	painted.set_shader_parameter(&"look_variation_hue", LookProfile.VARIATION_HUE)
	painted.set_shader_parameter(&"look_path_variation_share",
		LookProfile.PATH_VARIATION_SHARE)
	painted.set_shader_parameter(&"look_slope_up", LookProfile.SLOPE_UP)
	painted.set_shader_parameter(&"look_slope_shade", LookProfile.SLOPE_SHADE)

## Hands a painted material the region borders near it and each neighbour's
## trims, for the paint to fade its own into (LookBorders; `border` is
## LookBorders.near's answer, empty away from every border).
static func _set_border(painted: ShaderMaterial, border: Dictionary) -> void:
	var segments: PackedVector4Array = border.get("segments", PackedVector4Array())
	var slots: PackedFloat32Array = border.get("slots", PackedFloat32Array())
	var neighbours: PackedStringArray = border.get("neighbours", PackedStringArray())
	var count := segments.size()
	segments = segments.duplicate()
	slots = slots.duplicate()
	segments.resize(LookProfile.BORDER_SEGMENTS_MAX)
	slots.resize(LookProfile.BORDER_SEGMENTS_MAX)
	painted.set_shader_parameter(&"look_border_segments", segments)
	painted.set_shader_parameter(&"look_border_neighbour", slots)
	painted.set_shader_parameter(&"look_border_count", count)
	painted.set_shader_parameter(&"look_border_feather", LookProfile.BORDER_FEATHER_METRES)
	var lumas := PackedFloat32Array()
	var tints := PackedVector3Array()
	var chromas := PackedFloat32Array()
	var verges := PackedVector4Array()
	for slot: int in LookProfile.BORDER_NEIGHBOURS_MAX:
		var neighbour := neighbours[slot] if slot < neighbours.size() else ""
		lumas.append(float(_trim(neighbour, "path_luma", LookProfile.PATH_LUMA)))
		var tint: Color = _trim(neighbour, "path_tint", LookProfile.PATH_TINT)
		tints.append(Vector3(tint.r, tint.g, tint.b))
		chromas.append(float(_trim(neighbour, "path_chroma", LookProfile.PATH_CHROMA)))
		verges.append(Vector4(
			float(_trim(neighbour, "verge_value_green", LookProfile.VERGE_VALUE_GREEN)),
			float(_trim(neighbour, "verge_value_earth", LookProfile.VERGE_VALUE_EARTH)),
			float(_trim(neighbour, "verge_saturation", LookProfile.VERGE_SATURATION)),
			float(_trim(neighbour, "verge_green_red", LookProfile.VERGE_GREEN_RED))))
	painted.set_shader_parameter(&"look_border_path_luma", lumas)
	painted.set_shader_parameter(&"look_border_path_tint", tints)
	painted.set_shader_parameter(&"look_border_path_chroma", chromas)
	painted.set_shader_parameter(&"look_border_verge", verges)

static func _trim(region: String, key: String, fallback: Variant) -> Variant:
	return LookProfile.ground_value(region, key, fallback)

## An outdoor map declares a sun and does not disable it, as LookGrade reads it.
static func outdoor(manifest: WorldManifest) -> bool:
	var environment: Variant = manifest.data.get("environment")
	if environment is not Dictionary:
		return false
	var sun: Variant = (environment as Dictionary).get("sun")
	return sun is Dictionary and bool((sun as Dictionary).get("enabled", true))
