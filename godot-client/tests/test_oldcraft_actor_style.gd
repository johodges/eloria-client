extends SceneTree

const OldcraftActorStyleScript := preload("res://src/actors/oldcraft_actor_style.gd")

var failures := 0
var assertions := 0


func _init() -> void:
	_test_no_skeleton_styling()
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


func _test_no_skeleton_styling() -> void:
	# Owner call 2026-10-05: no runtime bone growth on player bodies.
	for name: String in ["pose_scales", "apply_skeleton", "restore_skeleton", "has_profile"]:
		_expect(not (OldcraftActorStyleScript as Script).get_script_method_list().any(
			func(m: Dictionary) -> bool: return m.name == name),
			"the style no longer offers %s" % name)
	var source := FileAccess.get_file_as_string("res://src/actors/replicated_actor_3d.gd")
	_expect(not source.contains("apply_skeleton") and not source.contains("set_bone_pose_scale"),
		"actors never scale their skeleton's bones")


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
