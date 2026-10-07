class_name TorsoBodyCover
extends RefCounted
## Generated clothing supplies its own fitted backing. Remove the default
## split wardrobe surfaces and covered body faces beneath it.
## Work on a copy of the index buffers: UVs, skinning, materials and the original
## mesh remain intact, and unequipping restores the exact original resource.

const BACKING_NAME := "GeneratedArmorBacking"
const LOW := 0.95
const HIGH := 1.535
const WRIST := 0.665
const NECK_ENVELOPE_MIN_Y := 1.40
const NECK_ENVELOPE_HALF_WIDTH := .18
const NECK_RIM_MIN_Y := 1.35
const NECK_RIM_MAX_Y := 1.55
const NECK_RIM_HALF_WIDTH := .10
const NECK_RIM_MIN_Z := -.11
const NECK_RIM_MAX_Z := .11
const NECK_RIM_INSET := .65
const FRONT_APRON_MIN_Y := 1.403
const FRONT_APRON_MAX_Y := 1.470
const FRONT_APRON_HALF_WIDTH := .032
const FRONT_APRON_MIN_Z := .005
## Race heads reach the body through a "Shared neck bridge" whose lowest rear
## rows flare out to the old wardrobe collar. Every generated torso shares one
## backing band and its collar rises to at least 1.555 at the back (all 64
## measured), so those rows hang outside it as a ragged skirt and prongs. Rows
## behind the canonical neck_01->Head axis and below this height are trimmed.
const REAR_BRIDGE_MAX_Y := 1.53
const NECK_AXIS_BASE := Vector3(0., 1.452, -.051)
const NECK_AXIS_TOP := Vector3(0., 1.568, .011)
## Beside the neck the trim ramps down from REAR_BRIDGE_MAX_Y at the side to
## SIDE_TRIM_MIN_Y at SIDE_TRIM_START_DEGREES from straight ahead. Without
## it the full-weight side rows end in a step below the rear trim, which
## swings out through 5:184/5:225 as hanging slivers. The lowest collar top
## of all 64 generated torsos is 1.500 at 60 degrees, 1.512 at 70, 1.522 at
## 80 and 1.532 at 90 (measured 2026-10-06), so the ramp stays under it.
const SIDE_TRIM_START_DEGREES := 60.0
const SIDE_TRIM_MIN_Y := 1.49
## In front of the neck axis the bridge is the throat, framed by the open front
## of coats such as 5:189, 5:184 and 5:222. Its long faces blend from the jaw
## down to the chest, so the whole-face 0.5 test cut them into a saw-tooth of
## spikes. They stay while every corner keeps at least this Head/neck_01
## weight; the unweighted chest rows below still go.
const FRONT_BRIDGE_MIN_WEIGHT := .25
## Any cut through the irregular bridge leaves spikes hanging off it by one
## edge and small fans joined only to each other (1 to 27 faces measured),
## which draw as loose skin shards beside the neck. See _clean_bridge_cut.
const BRIDGE_SPIKE_PASSES := 2
const BRIDGE_ISLAND_MAX_FACES := 64
## Both cuts follow the bridge triangles, so each open edge is a saw-tooth
## hem. Its points are levelled: onto the trim line behind and beside the
## neck, and onto the front edge's median height within FRONT_HEM_HALF_ANGLE
## degrees of straight ahead. See _hem_bridge_cut.
const REAR_HEM_BAND := .03
const FRONT_HEM_HALF_ANGLE := 50.0
const FRONT_HEM_BAND := .02
const HEM_MAX_TURN_COS := .7
## A wardrobe-only neckline tucks its open rim behind the fitted shirt. On a
## bridged race the bridge above this height is the visible neck, so it stays
## put; only a reviewed profile's own hole is tucked like the Human's rim.
const WARDROBE_BRIDGE_RIM_MAX_Y := 1.50

## Immutable masks live once here rather than in every actor's deep-copied
## model config. The model selects one profile by compact id/version; strict
## surface fingerprints below prevent face ordinals from drifting silently.
##
## A mask names two fingerprints because the same GLB reaches the game by two
## routes. An editor checkout loads the imported scene; an exported client has
## no resource path, so GlbSceneCache parses the loose GLB with GLTFDocument
## (`_build_raw`). The two meshes list the same faces in the same order (all
## 567 of Orun's bridge faces were matched by corner position and UV), but
## the importer re-lays each face's corners, so the bytes - and the
## fingerprint - differ. `rawSurfaceFingerprintSHA256` pins the parsed mesh,
## so the reviewed ordinals apply on either route and on nothing else.
const PROFILE_REGISTRY := {
	"orun-male-rear-neck-v1": {
		"id": "orun-male-rear-neck-v1",
		"version": 1,
		"targetNodes": ["body", "char1", "mesh_node"],
		"rearFaceMasks": [{
			"surface": 3,
			"sourceRole": "shared_neck",
			"indexAccessor": 72,
			"baseFaceCount": 567,
			"expectedVertexCount": 1701,
			"expectedIndexCount": 1701,
			"surfaceFingerprintSHA256": "580ab6ee1d57c3cc98369636e872556bbe2a6e1d290c86270c31fcf985dd5446",
			"rawSurfaceFingerprintSHA256": "adadf7459870edb2824a2010e68656f7272c382d76621c216594cba95dedf07b",
			"faces": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15,
				16, 17, 18, 20, 21, 27, 28, 36, 37, 50, 51, 57, 63, 64, 67,
				68, 69, 71, 86, 88, 89, 95, 101, 109, 112, 125, 128, 129,
				151, 152, 160, 192, 213, 219, 220, 249, 251, 278, 342, 343,
				344, 346, 387, 409, 414, 415, 432, 433, 443, 453, 461, 462,
				467, 468, 470, 490, 491, 492, 504, 508, 509, 510, 512, 517,
				523, 524, 525, 526, 531, 537, 538, 545, 546],
		}],
	},
}

static var _cache: Dictionary = {}
static var _profile_warnings: Dictionary = {}

## Covered meshes are shared across equivalent actors for the duration of one
## session. Release those derived resources alongside the imported scene cache
## when leaving a world, so later sessions cannot accumulate stale mesh ids.
static func clear() -> void:
	_cache.clear()
	_profile_warnings.clear()

static func covers(point: Vector3, regions: Array = [], preserve_tail: bool = false) -> bool:
	if preserve_tail and is_tail(point):
		return false
	if regions.is_empty():
		return point.y > LOW and point.y < HIGH and absf(point.x) < WRIST
	for region: Vector3 in regions:
		if point.y > region.x and point.y < region.y and absf(point.x) < region.z:
			return true
	return false

static func apply(instance: MeshInstance3D, enabled: bool,
		to_rig: Transform3D, fit: float, regions: Array = [],
		preserve_tail: bool = false, profile: Dictionary = {},
		mask_to_wardrobe_neckline: bool = false) -> void:
	if not instance.has_meta("uncovered_body_mesh"):
		if not enabled or instance.mesh == null:
			return
		instance.set_meta("uncovered_body_mesh", instance.mesh)
	var original: Mesh = instance.get_meta("uncovered_body_mesh") as Mesh
	if not enabled:
		instance.mesh = original
		return
	var active_profile := _resolve_profile(profile)
	var target_nodes: Array = profile.get("targetNodes", []) as Array
	if not active_profile.is_empty():
		target_nodes = active_profile.get("targetNodes", []) as Array
	if not target_nodes.is_empty() and not target_nodes.has(instance.name.to_lower()):
		active_profile = {}
	# The original shirt collar can extend above the trunk coverage band.
	# Its replacement is the equipped collar; leave neck skin on the body.
	if instance.name.to_lower() == "wardrobe_shirt" and covers(Vector3(0., 1.30, 0.), regions):
		regions = regions.duplicate()
		if regions.is_empty():
			regions.append(Vector3(LOW, HIGH, WRIST))
		regions.append(Vector3(1.40, 1.65, .20))
	var protected_binds := PackedInt32Array()
	if instance.skin != null and instance.name.to_lower() in ["body", "char1", "mesh_node"]:
		var skeleton := instance.get_node_or_null(instance.skeleton) as Skeleton3D
		for bind: int in range(instance.skin.get_bind_count()):
			var bone_name := instance.skin.get_bind_name(bind)
			var bone_index := instance.skin.get_bind_bone(bind)
			# Imported body skins may use numeric binds; rebound equipment uses
			# named binds. Both forms identify the same canonical joints.
			if bone_name.is_empty() and skeleton != null and bone_index >= 0:
				bone_name = skeleton.get_bone_name(bone_index)
			if bone_name in [&"Head", &"neck_01"]:
				protected_binds.append(bind)
	var profile_key := ("%s@%s" % [str(profile.get("id", "")),
		str(profile.get("version", 0))]) if not active_profile.is_empty() else ""
	var key := "%s|%s|%s|%s|%s|%s|%s|%s" % [original.get_instance_id(), to_rig,
		fit, regions, preserve_tail, protected_binds, profile_key,
		mask_to_wardrobe_neckline]
	if not _cache.has(key):
		_cache[key] = cut(original, to_rig, fit, regions, preserve_tail,
			protected_binds, active_profile, mask_to_wardrobe_neckline)
	instance.mesh = _cache[key] as Mesh

static func cut(original: Mesh, to_rig: Transform3D, fit: float,
		regions: Array = [], preserve_tail: bool = false,
		protected_binds: PackedInt32Array = PackedInt32Array(),
		profile: Dictionary = {},
		mask_to_wardrobe_neckline: bool = false) -> ArrayMesh:
	var result := ArrayMesh.new()
	# Pants and boots also request body coverage, but must never activate the
	# shaped collar mask.  Only a region that reaches the lower neck opts into
	# the geometry-first whole-face neckline below.
	var shaped_neck_active := (mask_to_wardrobe_neckline
		or (not protected_binds.is_empty()
			and covers(Vector3(0., NECK_ENVELOPE_MIN_Y, 0.), regions, preserve_tail)))
	for blend: int in range(original.get_blend_shape_count()):
		result.add_blend_shape(original.get_blend_shape_name(blend))
	if original is ArrayMesh:
		result.blend_shape_mode = (original as ArrayMesh).blend_shape_mode
	# Classify every surface before touching any of them. The neck bridge, the
	# race head and the shared body are separate surfaces welded along seams,
	# so loose bridge shards and the true open rim are only known across all.
	var passes: Array[Dictionary] = []
	var bridged := false
	var profiled := false
	for surface: int in range(original.get_surface_count()):
		var arrays: Array = original.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var source: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if source.is_empty():
			for index: int in range(vertices.size()):
				source.append(index)
		var bones := PackedInt32Array()
		if arrays[Mesh.ARRAY_BONES] is PackedInt32Array:
			bones = arrays[Mesh.ARRAY_BONES] as PackedInt32Array
		var weights := PackedFloat32Array()
		if arrays[Mesh.ARRAY_WEIGHTS] is PackedFloat32Array:
			weights = arrays[Mesh.ARRAY_WEIGHTS] as PackedFloat32Array
		var stride: int = bones.size() / maxi(vertices.size(), 1)
		var material := original.surface_get_material(surface)
		var bridge_surface := (material != null
			and material.resource_name == "Shared neck bridge")
		var profile_mask := _profile_mask(profile, surface, arrays, source,
			bridge_surface)
		# A hash-pinned profile owns its reviewed bridge faces completely. The
		# topology detector is for unprofiled wardrobe necks such as Luminous;
		# applying it on top of Orun's ordinal mask would remove extra rows.
		var detached_neck_vertices := (_detached_neck_vertices(
			source, vertices, to_rig, fit) if mask_to_wardrobe_neckline
			and profile_mask.is_empty() else {})
		bridged = bridged or bridge_surface
		profiled = profiled or not profile_mask.is_empty()
		passes.append({"arrays": arrays, "vertices": vertices, "bones": bones,
			"weights": weights, "stride": stride, "source": source,
			"bridge": bridge_surface, "profile_mask": profile_mask,
			"detached": detached_neck_vertices, "dropped": {}})
	# A reviewed, fingerprint-pinned profile owns its whole bridge cut: its
	# rig keeps the reviewed rear trim and nothing below is added to it.
	var generic_cut := bridged and not profiled
	# Classify faces before moving the derived rim. The tuck must not cause
	# coverage to walk down successive torso rows.
	for entry: Dictionary in passes:
		entry["kept"] = _filtered_indices(entry["source"], entry["vertices"],
			entry["bones"], entry["weights"], entry["stride"], to_rig, fit,
			regions, preserve_tail, protected_binds, shaped_neck_active,
			entry["bridge"], entry["profile_mask"], mask_to_wardrobe_neckline,
			entry["detached"], generic_cut)
	var welded: Array[PackedInt32Array] = []
	if shaped_neck_active and generic_cut:
		welded = _welded_points(passes, to_rig, fit)
		_clean_bridge_cut(passes, welded)
		if not mask_to_wardrobe_neckline:
			_hem_bridge_cut(passes, welded, to_rig, fit)
	if mask_to_wardrobe_neckline:
		if welded.is_empty():
			welded = _welded_points(passes, to_rig, fit)
		_inset_wardrobe_neckline_rim(passes, welded, to_rig, fit, profiled)
	for surface: int in range(original.get_surface_count()):
		var entry := passes[surface]
		var arrays: Array = entry["arrays"]
		var kept: PackedInt32Array = entry["kept"]
		var dropped: Dictionary = entry["dropped"]
		var lod_candidates: Dictionary = {}
		var source_lods := _surface_lods(original, surface)
		for distance: Variant in source_lods:
			var lod_source := source_lods[distance] as PackedInt32Array
			var lod_kept := _filtered_indices(lod_source, entry["vertices"],
				entry["bones"], entry["weights"], entry["stride"], to_rig, fit,
				regions, preserve_tail, protected_binds, shaped_neck_active,
				entry["bridge"], entry["profile_mask"], mask_to_wardrobe_neckline,
				entry["detached"], generic_cut)
			lod_candidates[distance] = (lod_kept if dropped.is_empty()
				else _without_vertices(lod_kept, dropped))
		var blend_arrays: Array = original.surface_get_blend_shape_arrays(surface)
		# Preserve surface numbering and its material overrides even when a
		# whole wardrobe surface is covered. A zero-area triangle draws nothing.
		if kept.is_empty():
			kept = PackedInt32Array([0, 0, 0])
		var lods: Dictionary = {}
		for distance: Variant in lod_candidates:
			var lod_kept := lod_candidates[distance] as PackedInt32Array
			# Godot rejects empty LODs and levels which do not reduce the base
			# index count. Omitting one keeps the last valid level visible instead
			# of replacing it with a disappearing, degenerate surface.
			if not lod_kept.is_empty() and lod_kept.size() < kept.size():
				lods[distance] = lod_kept
		arrays[Mesh.ARRAY_INDEX] = kept
		result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays,
			blend_arrays, lods,
			original.surface_get_format(surface) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		result.surface_set_material(surface, original.surface_get_material(surface))
	return result

static func _filtered_indices(source: PackedInt32Array,
		vertices: PackedVector3Array, bones: PackedInt32Array,
		weights: PackedFloat32Array, stride: int, to_rig: Transform3D,
		fit: float, regions: Array, preserve_tail: bool,
		protected_binds: PackedInt32Array, shaped_neck_active: bool,
		bridge_surface: bool, profile_mask: Dictionary = {},
		mask_to_wardrobe_neckline: bool = false,
		detached_neck_vertices: Dictionary = {},
		generic_cut: bool = false) -> PackedInt32Array:
	var kept := PackedInt32Array()
	var base_face_count := int(profile_mask.get("baseFaceCount", -1))
	var exact_base_order := base_face_count >= 0 and source.size() == base_face_count * 3
	var masked_faces: Dictionary = profile_mask.get("faces", {}) as Dictionary
	var masked_vertices: Dictionary = profile_mask.get("vertices", {}) as Dictionary
	var profile_driven_bridge := bridge_surface and not profile_mask.is_empty()
	for index: int in range(0, source.size(), 3):
		if (mask_to_wardrobe_neckline
				and (detached_neck_vertices.has(source[index])
					or detached_neck_vertices.has(source[index + 1])
					or detached_neck_vertices.has(source[index + 2]))):
			continue
		if shaped_neck_active and _profile_masks_face(source, index,
				exact_base_order, masked_faces, masked_vertices):
			continue
		if _keeps_face(source, index, vertices, bones, weights, stride, to_rig,
				fit, regions, preserve_tail, protected_binds,
				shaped_neck_active, bridge_surface, profile_driven_bridge,
				mask_to_wardrobe_neckline, generic_cut):
			kept.append_array(source.slice(index, index + 3))
	return kept

static func _resolve_profile(selection: Dictionary) -> Dictionary:
	if selection.is_empty():
		return {}
	var id := str(selection.get("id", ""))
	var entry: Dictionary = PROFILE_REGISTRY.get(id, {}) as Dictionary
	if entry.is_empty() or int(entry.get("version", -1)) != int(selection.get("version", -2)):
		_warn_profile_once(id, "unknown id/version")
		return {}
	return entry

static func _warn_profile_once(id: String, reason: String) -> void:
	var key := "%s:%s" % [id, reason]
	if _profile_warnings.has(key):
		return
	_profile_warnings[key] = true
	push_warning("Ignoring torso cover profile %s: %s" % [id, reason])

static func _profile_mask(profile: Dictionary, surface: int, arrays: Array,
		source: PackedInt32Array, bridge_surface: bool) -> Dictionary:
	for value: Variant in profile.get("rearFaceMasks", []) as Array:
		if value is not Dictionary:
			continue
		var entry := value as Dictionary
		if int(entry.get("surface", -1)) != surface:
			continue
		var profile_id := str(profile.get("id", "unnamed"))
		if str(entry.get("sourceRole", "")) == "shared_neck" and not bridge_surface:
			_warn_profile_once(profile_id, "surface role/material drifted")
			return {}
		var vertices := arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array
		if vertices.size() != int(entry.get("expectedVertexCount", -1)):
			_warn_profile_once(profile_id, "surface vertex count drifted")
			return {}
		if source.size() != int(entry.get("expectedIndexCount", -1)):
			_warn_profile_once(profile_id, "surface index count drifted")
			return {}
		var expected_fingerprint := str(entry.get("surfaceFingerprintSHA256", ""))
		var raw_fingerprint := str(entry.get("rawSurfaceFingerprintSHA256", ""))
		var actual_fingerprint := _surface_fingerprint(arrays, source)
		if expected_fingerprint.is_empty() or (actual_fingerprint != expected_fingerprint
				and (raw_fingerprint.is_empty() or actual_fingerprint != raw_fingerprint)):
			_warn_profile_once(profile_id, "surface fingerprint drifted (%s)" % actual_fingerprint)
			return {}
		var faces := {}
		var masked_vertices := {}
		var previous := -1
		var base_face_count := int(entry.get("baseFaceCount", -1))
		for face_value: Variant in entry.get("faces", []) as Array:
			var face := int(face_value)
			if face <= previous or face < 0 or face >= base_face_count:
				_warn_profile_once(profile_id, "face manifest is unsorted, duplicated, or out of range")
				return {}
			previous = face
			faces[face] = true
			masked_vertices[source[face * 3]] = true
			masked_vertices[source[face * 3 + 1]] = true
			masked_vertices[source[face * 3 + 2]] = true
		var masks_faces := bool(entry.get("maskFaces", true))
		return {
			"baseFaceCount": base_face_count,
			"faces": faces if masks_faces else {},
			"vertices": masked_vertices if masks_faces else {},
		}
	return {}

static func _surface_fingerprint(arrays: Array,
		source: PackedInt32Array) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update((arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).to_byte_array())
	context.update((arrays[Mesh.ARRAY_TEX_UV] as PackedVector2Array).to_byte_array())
	context.update((arrays[Mesh.ARRAY_BONES] as PackedInt32Array).to_byte_array())
	context.update((arrays[Mesh.ARRAY_WEIGHTS] as PackedFloat32Array).to_byte_array())
	context.update(source.to_byte_array())
	return context.finish().hex_encode()

static func _profile_masks_face(source: PackedInt32Array, index: int,
		exact_base_order: bool, masked_faces: Dictionary,
		masked_vertices: Dictionary) -> bool:
	if masked_faces.is_empty():
		return false
	if exact_base_order:
		return masked_faces.has(index / 3)
	# Imported LOD triangles may connect a reduced subset of the base vertices.
	# Remove a LOD triangle touching the reviewed rear-only patch so cheaper
	# levels cannot reintroduce the apron behind the fitted collar.
	return (masked_vertices.has(source[index])
		or masked_vertices.has(source[index + 1])
		or masked_vertices.has(source[index + 2]))

static func _keeps_face(source: PackedInt32Array, index: int,
		vertices: PackedVector3Array, bones: PackedInt32Array,
		weights: PackedFloat32Array, stride: int, to_rig: Transform3D,
		fit: float, regions: Array, preserve_tail: bool,
		protected_binds: PackedInt32Array, shaped_neck_active: bool,
		bridge_surface: bool, profile_driven_bridge: bool,
		mask_to_wardrobe_neckline: bool, generic_cut: bool = false) -> bool:
	var center := (vertices[source[index]] + vertices[source[index + 1]]
		+ vertices[source[index + 2]]) / 3.0
	var head_weight := 0.0
	var lowest_corner_weight := 1.0
	var all_corners_protected := not protected_binds.is_empty()
	if not protected_binds.is_empty():
		for corner: int in range(3):
			var corner_head_weight := 0.0
			for slot: int in range(stride):
				var offset: int = source[index+corner]*stride+slot
				if bones[offset] in protected_binds:
					corner_head_weight += weights[offset]
			head_weight += corner_head_weight / 3.0
			lowest_corner_weight = minf(lowest_corner_weight, corner_head_weight)
			all_corners_protected = (all_corners_protected
				and corner_head_weight > .5)
	var rest_center: Vector3 = (to_rig * center) / fit
	# Empty regions traditionally mean the whole default torso band. A
	# wardrobe-only collar must not opt into that broad deletion: it owns only
	# the narrow neck envelope, while any explicit trouser/boot regions remain
	# additive.
	var covered := (false if mask_to_wardrobe_neckline and regions.is_empty()
		else covers(rest_center, regions, preserve_tail))
	if (mask_to_wardrobe_neckline
			and rest_center.y > NECK_ENVELOPE_MIN_Y and rest_center.y < HIGH
			and absf(rest_center.x) < NECK_ENVELOPE_HALF_WIDTH):
		covered = true
	# The laced shirt has a small intentional front opening. Preserve only the
	# short central apron behind it so cape colour cannot show through; the low,
	# wide connected apron remains covered and cannot recreate the skin bib.
	if (mask_to_wardrobe_neckline
			and rest_center.y > FRONT_APRON_MIN_Y
			and rest_center.y < FRONT_APRON_MAX_Y
			and absf(rest_center.x) < FRONT_APRON_HALF_WIDTH
			and rest_center.z > FRONT_APRON_MIN_Z):
		covered = false
	# Require the whole low-poly face to be part of the visible neck. A single
	# protected corner otherwise leaves a long skin triangle crossing the collar.
	var neck_envelope := (shaped_neck_active
		and covered
		and rest_center.y > NECK_ENVELOPE_MIN_Y
		and absf(rest_center.x) < NECK_ENVELOPE_HALF_WIDTH)
	var outer_head := head_weight > .5 and not neck_envelope
	# Generic fitted collars retain only faces whose complete triangle belongs
	# predominantly to Head/neck_01. Averaging the three corners let a strongly
	# weighted neck vertex keep two torso vertices, producing a long skin wedge
	# through the collar. The reviewed Orun profile deliberately retains its
	# unmasked bridge rows and therefore keeps the legacy mean-weight predicate.
	var protected_face := (bridge_surface or head_weight > .5
		if profile_driven_bridge else all_corners_protected)
	# The generic shared-neck bridge is the visible neck from the jaw down:
	# dropping the surface outright left every bridged race's head floating
	# above a high collar. Under real armour its flared rows behind and beside
	# the neck are trimmed (_bridge_trim_y), the generic analogue of Orun's
	# reviewed rear-row mask; the fitted native shirt follows the body's own
	# collar, so a wardrobe-only neckline keeps them. Behind the neck axis the
	# rest takes the whole-face test. In front of the axis it is the throat
	# inside the collar's opening and keeps its blended faces down to
	# FRONT_BRIDGE_MIN_WEIGHT.
	if neck_envelope and bridge_surface and not profile_driven_bridge:
		if (not mask_to_wardrobe_neckline
				and rest_center.y < _bridge_trim_y(rest_center, generic_cut)):
			return false
		if rest_center.z >= _neck_axis_z(rest_center.y):
			return lowest_corner_weight > FRONT_BRIDGE_MIN_WEIGHT
	return ((protected_face if neck_envelope else
		(protected_face if shaped_neck_active else outer_head)) or (not neck_envelope
		and not covered))

## Height below which the generic bridge is trimmed under real armour:
## REAR_BRIDGE_MAX_Y behind the neck axis, ramping down beside the neck to
## SIDE_TRIM_MIN_Y at SIDE_TRIM_START_DEGREES from straight ahead, and no
## trim further forward, where the collar opens. A profiled rig (`side` off)
## keeps only the reviewed rear trim.
static func _bridge_trim_y(point: Vector3, side: bool = true) -> float:
	var ahead := point.z - _neck_axis_z(point.y)
	if ahead < 0.0:
		return REAR_BRIDGE_MAX_Y
	if not side:
		return -INF
	var angle := rad_to_deg(atan2(absf(point.x), ahead))
	if angle < SIDE_TRIM_START_DEGREES:
		return -INF
	return lerpf(SIDE_TRIM_MIN_Y, REAR_BRIDGE_MAX_Y,
		(angle - SIDE_TRIM_START_DEGREES) / (90.0 - SIDE_TRIM_START_DEGREES))

## Depth of the canonical neck axis at a rest-space height.
static func _neck_axis_z(y: float) -> float:
	var along := (y - NECK_AXIS_BASE.y) / (NECK_AXIS_TOP.y - NECK_AXIS_BASE.y)
	return lerpf(NECK_AXIS_BASE.z, NECK_AXIS_TOP.z, along)

## Wardrobe-only class torsos expose a shaped opening rather than a horizontal
## band. Keep the neck high at the rear and sides, then dip smoothly only at
## the front centre where the fitted native shirt owns the visible collar.
static func _wardrobe_neckline_y(point: Vector3) -> float:
	var front := smoothstep(-0.040, 0.010, point.z)
	var centre := 1.0 - smoothstep(0.015, 0.100, absf(point.x))
	return lerpf(1.462, 1.450, front * centre)

## The narrow apron mask creates an open edge in coarse source topology. Weld
## UV-split duplicates in rest space, project only that retained edge to one
## smooth curve, and inset it behind the shirt. This keeps the coarse boundary
## behind the collar without deleting another body row. The source mesh
## remains immutable; the moved positions belong to the derived ArrayMesh.
## The rim is found across all surfaces at once: a race's neck bridge meets
## its head and the shared body along welded seams, and finding the rim one
## surface at a time took those seams for open edges, dragged them down to
## the neckline and folded the bridge over the collar. The bridge above
## WARDROBE_BRIDGE_RIM_MAX_Y is the visible neck and stays in place, except
## around a reviewed profile's own hole (`profiled`).
static func _inset_wardrobe_neckline_rim(passes: Array[Dictionary],
		welded: Array[PackedInt32Array], to_rig: Transform3D, fit: float,
		profiled: bool) -> void:
	var edge_counts := {}
	var bridge_points := {}
	for surface: int in range(passes.size()):
		var kept: PackedInt32Array = passes[surface]["kept"]
		var ids: PackedInt32Array = welded[surface]
		var bridge := bool(passes[surface]["bridge"])
		for index: int in range(0, kept.size(), 3):
			for corner: int in range(3):
				var edge := _welded_edge(ids[kept[index + corner]],
					ids[kept[index + (corner + 1) % 3]])
				edge_counts[edge] = int(edge_counts.get(edge, 0)) + 1
				if bridge:
					bridge_points[ids[kept[index + corner]]] = true
	var boundary_points := {}
	for edge_value: Variant in edge_counts:
		if int(edge_counts[edge_value]) != 1:
			continue
		var edge := edge_value as Vector2i
		boundary_points[edge.x] = true
		boundary_points[edge.y] = true
	var from_rig := to_rig.affine_inverse()
	for surface: int in range(passes.size()):
		if (passes[surface]["kept"] as PackedInt32Array).is_empty():
			continue
		var arrays: Array = passes[surface]["arrays"]
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var ids: PackedInt32Array = welded[surface]
		var result := vertices.duplicate()
		for vertex: int in range(vertices.size()):
			if not boundary_points.has(ids[vertex]):
				continue
			var rest_point := (to_rig * vertices[vertex]) / fit
			if (rest_point.y <= NECK_RIM_MIN_Y or rest_point.y >= NECK_RIM_MAX_Y
					or absf(rest_point.x) >= NECK_RIM_HALF_WIDTH
					or rest_point.z <= NECK_RIM_MIN_Z
					or rest_point.z >= NECK_RIM_MAX_Z):
				continue
			if (bridge_points.has(ids[vertex]) and not profiled
					and rest_point.y > WARDROBE_BRIDGE_RIM_MAX_Y):
				continue
			rest_point.y = _wardrobe_neckline_y(rest_point)
			rest_point.x *= NECK_RIM_INSET
			rest_point.z *= NECK_RIM_INSET
			result[vertex] = from_rig * (rest_point * fit)
		arrays[Mesh.ARRAY_VERTEX] = result

## Rest-space point ids shared by every surface of one mesh. UV and normal
## splits, and the seams where the neck bridge meets the race head and the
## shared body, all collapse onto one id per position.
static func _welded_points(passes: Array[Dictionary], to_rig: Transform3D,
		fit: float) -> Array[PackedInt32Array]:
	var point_ids := {}
	var result: Array[PackedInt32Array] = []
	for entry: Dictionary in passes:
		var vertices: PackedVector3Array = entry["vertices"]
		var welded := PackedInt32Array()
		welded.resize(vertices.size())
		for vertex: int in range(vertices.size()):
			var point := (to_rig * vertices[vertex]) / fit
			var key := Vector3i(roundi(point.x * 100000.0), roundi(point.y * 100000.0),
				roundi(point.z * 100000.0))
			if not point_ids.has(key):
				point_ids[key] = point_ids.size()
			welded[vertex] = int(point_ids[key])
		result.append(welded)
	return result

static func _welded_edge(first: int, second: int) -> Vector2i:
	return Vector2i(mini(first, second), maxi(first, second))

## Tidy the cut through the generic bridge, across all surfaces. First peel
## spikes, bridge faces left hanging by one edge (two open edges), for
## BRIDGE_SPIKE_PASSES rounds; then drop components made only of bridge faces
## and no larger than BRIDGE_ISLAND_MAX_FACES. Every component that reaches
## the head or the body stays, so the neck itself cannot come away.
static func _clean_bridge_cut(passes: Array[Dictionary],
		welded: Array[PackedInt32Array]) -> void:
	var faces: Array[Vector2i] = []
	var edges: Array[Vector2i] = []
	var bridge_faces := PackedByteArray()
	var alive := PackedByteArray()
	for surface: int in range(passes.size()):
		var kept: PackedInt32Array = passes[surface]["kept"]
		var ids: PackedInt32Array = welded[surface]
		var bridge := bool(passes[surface]["bridge"])
		for index: int in range(0, kept.size(), 3):
			faces.append(Vector2i(surface, index))
			for corner: int in range(3):
				edges.append(_welded_edge(ids[kept[index + corner]],
					ids[kept[index + (corner + 1) % 3]]))
			bridge_faces.append(1 if bridge else 0)
			alive.append(1)
	for spike_pass: int in range(BRIDGE_SPIKE_PASSES):
		var edge_counts := {}
		for face: int in range(faces.size()):
			if alive[face] == 1:
				for corner: int in range(3):
					var edge := edges[face * 3 + corner]
					edge_counts[edge] = int(edge_counts.get(edge, 0)) + 1
		var spikes: Array[int] = []
		for face: int in range(faces.size()):
			if alive[face] == 0 or bridge_faces[face] == 0:
				continue
			var open_edges := 0
			for corner: int in range(3):
				if int(edge_counts[edges[face * 3 + corner]]) == 1:
					open_edges += 1
			if open_edges >= 2:
				spikes.append(face)
		if spikes.is_empty():
			break
		for face: int in spikes:
			alive[face] = 0
	var parents := PackedInt32Array()
	parents.resize(faces.size())
	var ranks := PackedInt32Array()
	ranks.resize(faces.size())
	var owners := {}
	for face: int in range(faces.size()):
		parents[face] = face
		if alive[face] == 0:
			continue
		for corner: int in range(3):
			var edge := edges[face * 3 + corner]
			if not owners.has(edge):
				owners[edge] = face
				continue
			var first_root := _component_root(parents, face)
			var other_root := _component_root(parents, int(owners[edge]))
			if first_root != other_root:
				if ranks[first_root] < ranks[other_root]:
					var swap := first_root
					first_root = other_root
					other_root = swap
				parents[other_root] = first_root
				if ranks[first_root] == ranks[other_root]:
					ranks[first_root] += 1
	var sizes := {}
	var anchored := {}
	for face: int in range(faces.size()):
		if alive[face] == 0:
			continue
		var root := _component_root(parents, face)
		sizes[root] = int(sizes.get(root, 0)) + 1
		if bridge_faces[face] == 0:
			anchored[root] = true
	for face: int in range(faces.size()):
		if alive[face] == 0:
			continue
		var root := _component_root(parents, face)
		if not anchored.has(root) and int(sizes[root]) <= BRIDGE_ISLAND_MAX_FACES:
			alive[face] = 0
	var face := 0
	for surface: int in range(passes.size()):
		var kept: PackedInt32Array = passes[surface]["kept"]
		var retained := PackedInt32Array()
		var dropped := {}
		for index: int in range(0, kept.size(), 3):
			if alive[face] == 1:
				retained.append_array(kept.slice(index, index + 3))
			else:
				for corner: int in range(3):
					dropped[kept[index + corner]] = true
			face += 1
		if dropped.is_empty():
			continue
		for vertex: int in retained:
			dropped.erase(vertex)
		passes[surface]["kept"] = retained
		passes[surface]["dropped"] = dropped

## Any cut along the irregular bridge triangles leaves a saw-tooth hem: over
## the back of the collar at the rear and side trim, and inside the open front
## where the weights fade out. Level both. Open-edge points within
## REAR_HEM_BAND of the trim line (_bridge_trim_y) go onto it; open-edge
## points within FRONT_HEM_HALF_ANGLE of the front go onto the median height
## of that front edge, when within FRONT_HEM_BAND of it. Only bridge points
## that no kept head or body face uses may move, in every surface sharing the
## welded point, and never one that would flip a face or open a T-junction,
## so the closing caps and every seam stay shut. Weights, UVs and the source
## mesh are untouched.
static func _hem_bridge_cut(passes: Array[Dictionary],
		welded: Array[PackedInt32Array], to_rig: Transform3D, fit: float) -> void:
	var edge_counts := {}
	var anchored_points := {}
	var rest_points := {}
	var bridge_faces: Array[PackedInt32Array] = []
	for surface: int in range(passes.size()):
		var kept: PackedInt32Array = passes[surface]["kept"]
		var ids: PackedInt32Array = welded[surface]
		var vertices: PackedVector3Array = passes[surface]["vertices"]
		var bridge := bool(passes[surface]["bridge"])
		for index: int in range(0, kept.size(), 3):
			var corners := PackedInt32Array([ids[kept[index]], ids[kept[index + 1]],
				ids[kept[index + 2]]])
			for corner: int in range(3):
				var edge := _welded_edge(corners[corner], corners[(corner + 1) % 3])
				edge_counts[edge] = int(edge_counts.get(edge, 0)) + 1
				if not bridge:
					anchored_points[corners[corner]] = true
				elif not rest_points.has(corners[corner]):
					rest_points[corners[corner]] = (to_rig * vertices[kept[index + corner]]) / fit
			if bridge:
				bridge_faces.append(corners)
	var open_points := {}
	for edge_value: Variant in edge_counts:
		if int(edge_counts[edge_value]) != 1:
			continue
		var edge := edge_value as Vector2i
		for point: int in [edge.x, edge.y]:
			if rest_points.has(point) and not anchored_points.has(point):
				open_points[point] = rest_points[point]
	var front_heights: Array[float] = []
	for point_value: Variant in open_points:
		var rest_point := open_points[point_value] as Vector3
		if _front_hem_point(rest_point):
			front_heights.append(rest_point.y)
	var front_y := INF
	if not front_heights.is_empty():
		front_heights.sort()
		front_y = front_heights[front_heights.size() / 2]
	var targets := {}
	for point_value: Variant in open_points:
		var rest_point := open_points[point_value] as Vector3
		if absf(rest_point.x) >= NECK_ENVELOPE_HALF_WIDTH:
			continue
		var trim_y := _bridge_trim_y(rest_point)
		if trim_y > -INF and absf(rest_point.y - trim_y) < REAR_HEM_BAND:
			targets[point_value] = trim_y
		elif _front_hem_point(rest_point) and absf(rest_point.y - front_y) < FRONT_HEM_BAND:
			targets[point_value] = front_y
	_keep_hem_closed(targets, rest_points, bridge_faces)
	if targets.is_empty():
		return
	var from_rig := to_rig.affine_inverse()
	for surface: int in range(passes.size()):
		var arrays: Array = passes[surface]["arrays"]
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var ids: PackedInt32Array = welded[surface]
		var result := PackedVector3Array()
		for vertex: int in range(vertices.size()):
			if not targets.has(ids[vertex]):
				continue
			if result.is_empty():
				result = vertices.duplicate()
			var rest_point := (to_rig * vertices[vertex]) / fit
			rest_point.y = float(targets[ids[vertex]])
			result[vertex] = from_rig * (rest_point * fit)
		if not result.is_empty():
			arrays[Mesh.ARRAY_VERTEX] = result

## In front of the neck axis and within FRONT_HEM_HALF_ANGLE of straight ahead.
static func _front_hem_point(point: Vector3) -> bool:
	var ahead := point.z - _neck_axis_z(point.y)
	return ahead > 0.0 and absf(point.x) < ahead * tan(deg_to_rad(FRONT_HEM_HALF_ANGLE))

## Drop hem targets that would open the mesh. The decimated bridge has a few
## T-junctions, a point resting on another face's edge; moving the point or
## either end of that edge opens a pixel crack along it. A target that tilts
## a face by more than HEM_MAX_TURN_COS turns it edge-on or over, and once
## skinned its back is culled to a dark line. Rest positions; targets set y.
static func _keep_hem_closed(targets: Dictionary, rest_points: Dictionary,
		bridge_faces: Array[PackedInt32Array]) -> void:
	if targets.is_empty():
		return
	var cell := .01
	var grid := {}
	for point_value: Variant in rest_points:
		var key := Vector3i(((rest_points[point_value] as Vector3) / cell).floor())
		if not grid.has(key):
			grid[key] = PackedInt32Array()
		(grid[key] as PackedInt32Array).append(int(point_value))
	var edges := {}
	for corners: PackedInt32Array in bridge_faces:
		for corner: int in range(3):
			edges[_welded_edge(corners[corner], corners[(corner + 1) % 3])] = true
	for edge_value: Variant in edges:
		var edge := edge_value as Vector2i
		var start := rest_points[edge.x] as Vector3
		var end := rest_points[edge.y] as Vector3
		var low := Vector3i((start.min(end) / cell).floor())
		var high := Vector3i((start.max(end) / cell).floor())
		var span := high - low
		if span.x * span.y * span.z > 64:
			continue
		var length_squared := start.distance_squared_to(end)
		if length_squared < 1e-12:
			continue
		for x: int in range(low.x, high.x + 1):
			for y: int in range(low.y, high.y + 1):
				for z: int in range(low.z, high.z + 1):
					for point: int in grid.get(Vector3i(x, y, z), PackedInt32Array()):
						if point == edge.x or point == edge.y:
							continue
						if not (targets.has(point) or targets.has(edge.x)
								or targets.has(edge.y)):
							continue
						var position := rest_points[point] as Vector3
						var along := (position - start).dot(end - start) / length_squared
						if (along > .001 and along < .999
								and position.distance_to(start.lerp(end, along)) < .00005):
							targets.erase(point)
							targets.erase(edge.x)
							targets.erase(edge.y)
	for attempt: int in range(4):
		var turned := false
		for corners: PackedInt32Array in bridge_faces:
			if not (targets.has(corners[0]) or targets.has(corners[1])
					or targets.has(corners[2])):
				continue
			var before: Array[Vector3] = []
			var after: Array[Vector3] = []
			for corner: int in range(3):
				var position := rest_points[corners[corner]] as Vector3
				before.append(position)
				if targets.has(corners[corner]):
					position.y = float(targets[corners[corner]])
				after.append(position)
			var normal_before := (before[1] - before[0]).cross(before[2] - before[0])
			var normal_after := (after[1] - after[0]).cross(after[2] - after[0])
			if (normal_before.dot(normal_after) <= HEM_MAX_TURN_COS
					* normal_before.length() * normal_after.length()):
				for corner: int in range(3):
					targets.erase(corners[corner])
				turned = true
		if not turned:
			break

## Generated LOD triangles connect a reduced subset of the base vertices.
## Drop the ones touching a removed bridge shard so cheaper levels cannot
## draw it again.
static func _without_vertices(indices: PackedInt32Array,
		vertices: Dictionary) -> PackedInt32Array:
	var kept := PackedInt32Array()
	for index: int in range(0, indices.size(), 3):
		if (vertices.has(indices[index]) or vertices.has(indices[index + 1])
				or vertices.has(indices[index + 2])):
			continue
		kept.append_array(indices.slice(index, index + 3))
	return kept

## Some canonical heads carry a second, disconnected lower-neck shell. It is
## fully Head-weighted, so skinning weights cannot distinguish it from the
## anatomical neck. Find only small welded components wholly inside the collar
## band; their vertex ids also mask generated LOD triangles which touch them.
static func _detached_neck_vertices(source: PackedInt32Array,
		vertices: PackedVector3Array, to_rig: Transform3D, fit: float) -> Dictionary:
	var point_ids := {}
	var welded := PackedInt32Array()
	welded.resize(vertices.size())
	var rest_points := PackedVector3Array()
	for vertex: int in range(vertices.size()):
		var point := (to_rig * vertices[vertex]) / fit
		var key := Vector3i(roundi(point.x * 100000.0), roundi(point.y * 100000.0),
			roundi(point.z * 100000.0))
		if not point_ids.has(key):
			point_ids[key] = rest_points.size()
			rest_points.append(point)
		welded[vertex] = int(point_ids[key])
	var parents := PackedInt32Array()
	parents.resize(rest_points.size())
	for point_id: int in range(parents.size()):
		parents[point_id] = point_id
	for index: int in range(0, source.size(), 3):
		var first_root := _component_root(parents, welded[source[index]])
		for corner: int in range(1, 3):
			var other_root := _component_root(parents, welded[source[index + corner]])
			if first_root != other_root:
				parents[other_root] = first_root
	var face_counts := {}
	for index: int in range(0, source.size(), 3):
		var root := _component_root(parents, welded[source[index]])
		face_counts[root] = int(face_counts.get(root, 0)) + 1
	var minima := {}
	var maxima := {}
	for point_id: int in range(rest_points.size()):
		var root := _component_root(parents, point_id)
		var point := rest_points[point_id]
		minima[root] = point if not minima.has(root) else (minima[root] as Vector3).min(point)
		maxima[root] = point if not maxima.has(root) else (maxima[root] as Vector3).max(point)
	var detached_roots := {}
	for root_value: Variant in face_counts:
		var root := int(root_value)
		var minimum := minima[root] as Vector3
		var maximum := maxima[root] as Vector3
		if (int(face_counts[root]) <= 128
				and minimum.y >= 1.460 and maximum.y <= 1.520
				and maxf(absf(minimum.x), absf(maximum.x)) <= 0.100
				and minimum.z >= -0.110 and maximum.z <= 0.040):
			detached_roots[root] = true
	var result := {}
	for vertex: int in range(vertices.size()):
		if detached_roots.has(_component_root(parents, welded[vertex])):
			result[vertex] = true
	return result

static func _component_root(parents: PackedInt32Array, point_id: int) -> int:
	var root := point_id
	while parents[root] != root:
		root = parents[root]
	return root

## Godot 4.7 exposes generated LODs through RenderingServer as packed index
## buffers. Convert them back to the dictionary accepted by ArrayMesh.
static func _surface_lods(original: Mesh, surface: int) -> Dictionary:
	if original is not ArrayMesh:
		return {}
	var raw: Dictionary = RenderingServer.mesh_get_surface(
		original.get_rid(), surface)
	var raw_lods: Variant = raw.get("lods", [])
	if raw_lods is not Array:
		return {}
	var index_width := 2 if int(raw.get("vertex_count", 0)) <= 65536 else 4
	var result: Dictionary = {}
	for lod_value: Variant in raw_lods as Array:
		if lod_value is not Dictionary:
			continue
		var lod := lod_value as Dictionary
		var distance := float(lod.get("edge_length", 0.0))
		var bytes_value: Variant = lod.get("index_data", PackedByteArray())
		if distance <= 0.0 or bytes_value is not PackedByteArray:
			continue
		var bytes := bytes_value as PackedByteArray
		if bytes.is_empty() or bytes.size() % index_width != 0:
			continue
		var indices := PackedInt32Array()
		indices.resize(bytes.size() / index_width)
		for index: int in range(indices.size()):
			var offset := index * index_width
			indices[index] = (bytes.decode_u16(offset) if index_width == 2
				else bytes.decode_u32(offset))
		result[distance] = indices
	return result

## Canonical Rest_Pose geometry. Matches equipment_authoring.tail_region;
## source stripes never split the tail mask. No body vertices or weights move.
static func is_tail(point: Vector3) -> bool:
	if point.y >= .9367 or (point.x <= .13 and point.z >= -.11):
		return false
	var distance := INF
	for side: float in [-1.0, 1.0]:
		var chain := [Vector3(.089 * side, .9321, .0014),
			Vector3(.09109 * side, .52587, .01922),
			Vector3(.089 * side, .09796, -.04823),
			Vector3(.089 * side, .0152, .1132), Vector3(.089 * side, .0152, .2632)]
		for index: int in range(chain.size()-1):
			var a: Vector3 = chain[index]
			var axis: Vector3 = chain[index+1]-a
			var t := clampf((point-a).dot(axis)/axis.length_squared(),0.,1.)
			distance = minf(distance,point.distance_to(a+axis*t))
	return distance > .115
