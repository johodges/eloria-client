class_name RangerBow3D
extends Node3D
## Shared native prop meshes; string and nocked arrow follow both posed hands.
const ARROW_PATH := "res://assets/actors/native/equipment/ranger_arrow.glb"
const DEFAULT_BOW := "res://assets/actors/native/equipment/amberwood_ranger_bow.glb"
var bow: Node3D
var arrow: Node3D
var _string: ImmediateMesh
var _string_material: StandardMaterial3D
var _tip_y := 0.68
var _tip_z := 0.18
var _path := ""
var _aim_back := Vector3.ZERO

func _init() -> void:
	name = "RangerBow"
	_string = ImmediateMesh.new()
	_string_material = CombatEffectMesh.material()
	_string_material.blend_mode = BaseMaterial3D.BLEND_MODE_MIX
	var string_node := MeshInstance3D.new()
	string_node.name = "LiveBowstring"
	string_node.mesh = _string
	string_node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(string_node)
	arrow = GlbSceneCache.instantiate(ARROW_PATH)
	if arrow != null:
		arrow.name = "NockedArrow"
		add_child(arrow)
	set_asset(DEFAULT_BOW)

func set_asset(path: String) -> void:
	if path == _path:
		return
	var instance := GlbSceneCache.instantiate(path)
	if instance == null:
		return
	if is_instance_valid(bow):
		remove_child(bow)
		bow.queue_free()
	bow = instance
	_path = path
	_tip_y = 0.64 if path.contains("sunmane") else 0.68
	_tip_z = 0.16 if path.contains("sunmane") else 0.18
	add_child(bow)
	var rest_string := bow.find_child("RestString", true, false) as Node3D
	if rest_string != null:
		rest_string.hide()

func pose(grip: Vector3, draw_hand: Vector3, up: Vector3, forward: Vector3,
		is_drawing: bool, release_time: float, size: float, arrow_size := 1.0) -> void:
	global_position = grip
	var back := (draw_hand - grip).normalized() if is_drawing else -forward.normalized()
	if is_drawing:
		_aim_back = back
	elif release_time >= 0.0 and _aim_back.length_squared() > 0.01:
		back = _aim_back
	if absf(back.dot(up)) > 0.95:
		back = -forward.normalized()
	var right := up.cross(back).normalized()
	var pose_basis := Basis(right, back.cross(right).normalized(), back)
	if not is_drawing and release_time < 0.0 and is_inside_tree():
		pose_basis = global_basis.orthonormalized().slerp(pose_basis, 0.2)
	global_basis = pose_basis.scaled(Vector3.ONE * size)
	var draw_point := to_local(draw_hand) if is_drawing else Vector3(0, 0, _tip_z)
	draw_point.x = 0.0
	# Damped string recoil immediately after release, then a quiet braced string.
	if release_time >= 0.0:
		draw_point.z += sin(release_time * 95.0) * exp(-release_time * 24.0) * 0.055
	var flex := clampf((draw_point.z-_tip_z)*0.18, -0.025, 0.11)
	for limb: Node3D in bow.get_children():
		if String(limb.name).begins_with("Upper"):
			limb.rotation.x = flex
		elif String(limb.name).begins_with("Lower"):
			limb.rotation.x = -flex
	var upper_tip := Basis(Vector3.RIGHT, flex) * Vector3(0, _tip_y, _tip_z)
	var lower_tip := Basis(Vector3.RIGHT, -flex) * Vector3(0, -_tip_y, _tip_z)
	_string.clear_surfaces()
	_string.surface_begin(Mesh.PRIMITIVE_TRIANGLES, _string_material)
	CombatEffectMesh.line(_string, upper_tip, draw_point,
		0.0035, Color(0.82, 0.77, 0.58), Vector3.RIGHT)
	CombatEffectMesh.line(_string, draw_point, lower_tip,
		0.0035, Color(0.82, 0.77, 0.58), Vector3.RIGHT)
	_string.surface_end()
	if arrow != null:
		# Shared animation positions preserve draw length across race proportions.
		# Fit the bow to stature, and the arrow to the animated skeleton's units.
		arrow.scale = Vector3.ONE * arrow_size / maxf(size, 0.01)
		arrow.visible = is_drawing
		arrow.position = draw_point
		# Nock stays at the fingers; the broadhead extends beyond the arrow rest.
		arrow.rotation = Vector3.ZERO

func nock_position() -> Vector3:
	return arrow.global_position if arrow != null else global_position
