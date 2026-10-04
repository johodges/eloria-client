class_name OldcraftActorStyle
extends RefCounted
## A zero-topology-cost heroic silhouette and painted-surface finish for actors.
##
## The shared animation library has rotation and translation tracks, but no
## scale tracks.  Pose scales therefore remain stable across clips without a
## per-frame SkeletonModifier3D.  They deliberately do not alter the canonical
## 77-joint rest pose, inverse binds, names or ordering: bodies, rebound
## garments, skinned hair and BoneAttachment3D equipment all keep using the
## same rig contract and inherit the same silhouette.

const STYLE_VERSION := 1
const SKELETON_STYLE_META := &"eloria_oldcraft_skeleton_style"
const AUTHORED_SCALES_META := &"eloria_oldcraft_authored_pose_scales"
const MATERIAL_FINISH_META := &"eloria_oldcraft_painted_finish"
const AUTHORED_FINISH_META := &"eloria_oldcraft_authored_finish"

## Bone-local Y is the long axis on the canonical limbs.  X/Z growth thickens
## arms and legs without lengthening them.  Spine X/Z growth widens the chest;
## hand, foot and head growth is uniform enough to keep their equipment seated.
const BULK_TARGETS := {
	"spine_02": Vector3(1.07, 0.985, 1.05),
	"spine_03": Vector3(1.13, 0.985, 1.09),
	"neck_01": Vector3(1.05, 1.0, 1.05),
	"upperarm_l": Vector3(1.13, 1.0, 1.13),
	"upperarm_r": Vector3(1.13, 1.0, 1.13),
	"lowerarm_l": Vector3(1.16, 1.0, 1.16),
	"lowerarm_r": Vector3(1.16, 1.0, 1.16),
	"thigh_l": Vector3(1.09, 1.0, 1.09),
	"thigh_r": Vector3(1.09, 1.0, 1.09),
	"calf_l": Vector3(1.11, 1.0, 1.11),
	"calf_r": Vector3(1.11, 1.0, 1.11),
}
const EXTREMITY_TARGETS := {
	"hand_l": Vector3(1.24, 1.24, 1.24),
	"hand_r": Vector3(1.24, 1.24, 1.24),
	"foot_l": Vector3(1.18, 1.20, 1.18),
	"foot_r": Vector3(1.18, 1.20, 1.18),
}
const HEAD_TARGET := Vector3(1.12, 1.09, 1.11)

## Each Eloria culture keeps its identity while sharing Oldcraft's readable
## silhouette language.  Heavy cultures push the heroic masses farther;
## long-limbed and spectral cultures keep a lighter trunk but retain readable
## hands, feet and head at gameplay distance.
const CULTURE_STRENGTHS := {
	"luminous": {"bulk": 1.00, "extremity": 1.00, "head": 1.00},
	"orun": {"bulk": 1.22, "extremity": 1.18, "head": 0.78},
	"stoneborn": {"bulk": 1.28, "extremity": 1.22, "head": 1.00},
	"votary": {"bulk": 1.15, "extremity": 1.15, "head": 0.92},
	"ssarathi": {"bulk": 1.04, "extremity": 1.08, "head": 0.90},
	"glasswarden": {"bulk": 0.72, "extremity": 0.92, "head": 0.96},
	"greyhaven": {"bulk": 0.78, "extremity": 1.02, "head": 0.92},
	"mycelari": {"bulk": 0.82, "extremity": 1.04, "head": 1.08},
}
const DEFAULT_STRENGTH := {"bulk": 1.00, "extremity": 1.00, "head": 1.00}

## Oldcraft's materials read as painted color blocks rather than polished
## plastic.  These bounds retain authored textures, tint, transparency,
## emission and metallic masks; only the broad highlight response is softened.
const ROUGHNESS_FLOOR := 0.68
const DIELECTRIC_SPECULAR_CEILING := 0.35
## Preserve the authored normal map, but keep its fine relief subordinate to
## the large painted value shapes. The reference shader uses 0.55; 0.65 keeps
## a little more of Eloria's existing equipment detail.
const NORMAL_SCALE_CEILING := 0.65


static func _strengths(culture: String) -> Dictionary:
	return CULTURE_STRENGTHS.get(culture.strip_edges().to_lower(),
		DEFAULT_STRENGTH) as Dictionary


## Creature rigs often reuse humanoid-looking bone names without sharing the
## player rig or equipment contract. Styling is therefore an explicit model
## profile, never something inferred from whichever bone names happen to fit.
static func has_profile(model_config: Dictionary) -> bool:
	if not model_config.has("culture"):
		return false
	return CULTURE_STRENGTHS.has(
		str(model_config.get("culture", "")).strip_edges().to_lower())


static func _towards(target: Vector3, strength: float) -> Vector3:
	return Vector3.ONE.lerp(target, strength)


static func pose_scales(culture: String) -> Dictionary:
	var strengths := _strengths(culture)
	var result: Dictionary = {}
	for bone: String in BULK_TARGETS:
		result[bone] = _towards(BULK_TARGETS[bone] as Vector3,
			float(strengths.bulk))
	for bone: String in EXTREMITY_TARGETS:
		result[bone] = _towards(EXTREMITY_TARGETS[bone] as Vector3,
			float(strengths.extremity))
	result["Head"] = _towards(HEAD_TARGET, float(strengths.head))
	return result


## Applies the culture's silhouette once. Re-applying, including after a live
## settings refresh, is absolute from the authored scales rather than
## multiplicative, so it cannot progressively inflate a character.
static func apply_skeleton(skeleton: Skeleton3D, culture: String) -> int:
	if skeleton == null:
		return 0
	var targets := pose_scales(culture)
	var authored: Dictionary = skeleton.get_meta(AUTHORED_SCALES_META, {}) as Dictionary
	if authored.is_empty():
		for bone: String in targets:
			var bone_index := skeleton.find_bone(bone)
			if bone_index >= 0:
				authored[bone] = skeleton.get_bone_pose_scale(bone_index)
		skeleton.set_meta(AUTHORED_SCALES_META, authored.duplicate(true))
	var changed := 0
	for bone: String in targets:
		var index := skeleton.find_bone(bone)
		if index < 0:
			continue
		var base: Vector3 = authored.get(bone,
			skeleton.get_bone_pose_scale(index)) as Vector3
		skeleton.set_bone_pose_scale(index, base * (targets[bone] as Vector3))
		changed += 1
	skeleton.set_meta(SKELETON_STYLE_META, {
		"version": STYLE_VERSION, "culture": culture.strip_edges().to_lower()})
	return changed


static func restore_skeleton(skeleton: Skeleton3D) -> int:
	if skeleton == null:
		return 0
	var authored: Dictionary = skeleton.get_meta(AUTHORED_SCALES_META, {}) as Dictionary
	var restored := 0
	for bone: String in authored:
		var index := skeleton.find_bone(bone)
		if index >= 0:
			skeleton.set_bone_pose_scale(index, authored[bone] as Vector3)
			restored += 1
	skeleton.remove_meta(SKELETON_STYLE_META)
	return restored


## Applies the finish to one mesh without cloning its mesh, skin, materials or
## textures.  Shared imported materials are marked and touched only once.
static func apply_mesh_finish(mesh_instance: MeshInstance3D) -> int:
	if mesh_instance == null or mesh_instance.mesh == null:
		return 0
	var changed := 0
	var seen: Dictionary = {}
	for surface in mesh_instance.mesh.get_surface_count():
		var material := mesh_instance.get_active_material(surface) as BaseMaterial3D
		if material == null:
			continue
		var identity := material.get_instance_id()
		if seen.has(identity):
			continue
		seen[identity] = true
		if not material.has_meta(AUTHORED_FINISH_META):
			material.set_meta(AUTHORED_FINISH_META, {
				"roughness": material.roughness,
				"metallic_specular": material.metallic_specular,
				"normal_scale": material.normal_scale,
			})
		material.roughness = maxf(material.roughness, ROUGHNESS_FLOOR)
		material.metallic_specular = minf(material.metallic_specular,
			DIELECTRIC_SPECULAR_CEILING)
		if material.normal_enabled and material.normal_texture != null:
			material.normal_scale = minf(material.normal_scale,
				NORMAL_SCALE_CEILING)
		material.set_meta(MATERIAL_FINISH_META, STYLE_VERSION)
		changed += 1
	return changed


static func apply_surface_finish(root: Node) -> int:
	if root == null:
		return 0
	var changed := 0
	if root is MeshInstance3D:
		changed += apply_mesh_finish(root as MeshInstance3D)
	for value: Node in root.find_children("*", "MeshInstance3D", true, false):
		changed += apply_mesh_finish(value as MeshInstance3D)
	return changed
