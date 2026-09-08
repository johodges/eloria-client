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

static var _cache: Dictionary = {}

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
		to_rig: Transform3D, fit: float, regions: Array = [], preserve_tail: bool = false) -> void:
	if not instance.has_meta("uncovered_body_mesh"):
		if not enabled or instance.mesh == null:
			return
		instance.set_meta("uncovered_body_mesh", instance.mesh)
	var original: Mesh = instance.get_meta("uncovered_body_mesh") as Mesh
	if not enabled:
		instance.mesh = original
		return
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
	var key := "%s|%s|%s|%s|%s|%s" % [original.get_instance_id(), to_rig, fit, regions, preserve_tail, protected_binds]
	if not _cache.has(key):
		_cache[key] = cut(original, to_rig, fit, regions, preserve_tail, protected_binds)
	instance.mesh = _cache[key] as Mesh

static func cut(original: Mesh, to_rig: Transform3D, fit: float, regions: Array = [], preserve_tail: bool = false, protected_binds: PackedInt32Array = PackedInt32Array()) -> ArrayMesh:
	var result := ArrayMesh.new()
	for blend: int in range(original.get_blend_shape_count()):
		result.add_blend_shape(original.get_blend_shape_name(blend))
	if original is ArrayMesh:
		result.blend_shape_mode = (original as ArrayMesh).blend_shape_mode
	for surface: int in range(original.get_surface_count()):
		var arrays: Array = original.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var source: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		if source.is_empty():
			for index: int in range(vertices.size()):
				source.append(index)
		var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
		var stride := bones.size() / maxi(vertices.size(), 1)
		var kept := PackedInt32Array()
		for index: int in range(0, source.size(), 3):
			var center := (vertices[source[index]] + vertices[source[index + 1]]
				+ vertices[source[index + 2]]) / 3.0
			var head_weight := 0.0
			if not protected_binds.is_empty():
				for corner: int in range(3):
					for slot: int in range(stride):
						var offset: int = source[index+corner]*stride+slot
						if bones[offset] in protected_binds:
							head_weight += weights[offset]/3.0
			var rest_center: Vector3 = (to_rig * center) / fit
			# Some chin triangles inherit clavicle weights. Protect the visible
			# canonical neck geometrically too; a bone-weight threshold alone
			# cuts holes in the face and exposes a collar/back wall through it.
			var neck: bool = not protected_binds.is_empty() and is_neck(to_rig * center)
			if head_weight > .5 or neck or not covers(rest_center, regions, preserve_tail):
				kept.append_array(source.slice(index, index + 3))
		# Preserve surface numbering and its material overrides even when a
		# whole wardrobe surface is covered. A zero-area triangle draws nothing.
		if kept.is_empty():
			kept = PackedInt32Array([0, 0, 0])
		arrays[Mesh.ARRAY_INDEX] = kept
		result.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays,
			original.surface_get_blend_shape_arrays(surface), {},
			original.surface_get_format(surface) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		result.surface_set_material(surface, original.surface_get_material(surface))
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


static func is_neck(point: Vector3) -> bool:
	# The visible throat extends below neck_01's joint origin. End the mask
	# behind the upper breastplate, not across the opening of a raised collar.
	return point.y > 1.40 and absf(point.x) < .11
