extends SceneTree

const OldcraftActorStyleScript := preload("res://src/actors/oldcraft_actor_style.gd")

var failures := 0
var assertions := 0


func _init() -> void:
	_test_profiles()
	_test_skeleton_application()
	_test_painted_finish()
	if failures == 0:
		print("oldcraft actor style: PASS (%d assertions)" % assertions)
		quit(0)
	else:
		push_error("oldcraft actor style: FAIL (%d failures, %d assertions)"
			% [failures, assertions])
		quit(1)


func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if not condition:
		failures += 1
		push_error(message)


func _test_profiles() -> void:
	_expect(OldcraftActorStyleScript.has_profile({"culture": "luminous"})
		and not OldcraftActorStyleScript.has_profile({})
		and not OldcraftActorStyleScript.has_profile({"culture": "unprofiled"}),
		"only explicitly profiled player cultures receive humanoid deformation")
	var human: Dictionary = OldcraftActorStyleScript.pose_scales("luminous")
	var orc: Dictionary = OldcraftActorStyleScript.pose_scales("orun")
	var elf: Dictionary = OldcraftActorStyleScript.pose_scales("glasswarden")
	_expect(human.has("Head") and human.has("hand_l") and human.has("foot_r"),
		"profile covers the readable head, hand and foot landmarks")
	_expect((orc.spine_03 as Vector3).x > (human.spine_03 as Vector3).x,
		"Orun keeps the heavier Oldcraft orc trunk")
	_expect((elf.spine_03 as Vector3).x < (human.spine_03 as Vector3).x,
		"Glasswarden keeps the long-limbed Oldcraft elf read")
	_expect((orc.hand_l as Vector3).x > 1.2,
		"heavy profiles keep oversized readable hands")


func _test_skeleton_application() -> void:
	var skeleton := Skeleton3D.new()
	var bones := ["spine_02", "spine_03", "neck_01", "upperarm_l",
		"upperarm_r", "lowerarm_l", "lowerarm_r", "hand_l", "hand_r",
		"thigh_l", "thigh_r", "calf_l", "calf_r", "foot_l", "foot_r", "Head"]
	for bone: String in bones:
		skeleton.add_bone(bone)
	var count := OldcraftActorStyleScript.apply_skeleton(skeleton, "luminous")
	_expect(count == bones.size(), "every available style bone is applied")
	var head := skeleton.find_bone("Head")
	var hand := skeleton.find_bone("hand_l")
	var spine := skeleton.find_bone("spine_03")
	_expect(skeleton.get_bone_pose_scale(head).x > 1.0, "head is enlarged")
	_expect(skeleton.get_bone_pose_scale(hand).x >
		skeleton.get_bone_pose_scale(head).x, "hands are the stronger landmark")
	_expect(is_equal_approx(skeleton.get_bone_pose_scale(spine).y, 0.985),
		"chest is slightly compressed without shortening limbs")
	var first_hand := skeleton.get_bone_pose_scale(hand)
	OldcraftActorStyleScript.apply_skeleton(skeleton, "luminous")
	_expect(skeleton.get_bone_pose_scale(hand).is_equal_approx(first_hand),
		"re-applying style does not compound pose scale")
	OldcraftActorStyleScript.restore_skeleton(skeleton)
	_expect(skeleton.get_bone_pose_scale(hand).is_equal_approx(Vector3.ONE),
		"authored pose scale can be restored")
	skeleton.free()


func _test_painted_finish() -> void:
	var instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	var material := StandardMaterial3D.new()
	material.roughness = 0.2
	material.metallic = 0.8
	material.metallic_specular = 0.9
	material.normal_enabled = true
	material.normal_texture = GradientTexture2D.new()
	material.normal_scale = 1.0
	mesh.material = material
	instance.mesh = mesh
	var mesh_identity := instance.mesh
	var material_identity := instance.get_active_material(0)
	_expect(OldcraftActorStyleScript.apply_mesh_finish(instance) == 1,
		"painted finish finds the active material")
	_expect(instance.mesh == mesh_identity and instance.get_active_material(0) == material_identity,
		"painted finish preserves mesh and material identity")
	_expect(material.roughness >= OldcraftActorStyleScript.ROUGHNESS_FLOOR,
		"painted finish removes the plastic-sharp highlight")
	_expect(material.metallic_specular <=
		OldcraftActorStyleScript.DIELECTRIC_SPECULAR_CEILING,
		"dielectric specular is restrained")
	_expect(material.normal_scale <= OldcraftActorStyleScript.NORMAL_SCALE_CEILING,
		"fine normal relief stays subordinate to the painted value blocks")
	_expect(is_equal_approx(material.metallic, 0.8),
		"authored metallic response is retained")
	instance.free()
