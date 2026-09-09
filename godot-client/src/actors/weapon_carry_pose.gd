extends SkeletonModifier3D
## Pose the arms after locomotion, keeping each weapon in its actual grip.
## The skeleton restores the animation pose after modifiers, so this never
## changes shared clips or leaves a wrist correction behind in another action.

var actor: ReplicatedActor3D
var _hands: Array[Dictionary] = []
var _weight := 0.0

func refresh_equipment() -> void:
	_hands.clear()
	var skeleton := get_skeleton()
	for part: int in [0, 1]:
		var visual: int = int(actor._equipment_visuals.get(part, 0))
		# The off-hand weapon bank starts at 160; shields keep their own pose.
		if visual == 0 or (part == 1 and visual < 160):
			continue
		var model := actor._equipment_model_config(part, visual)
		if model.get("attach", "socket") != "socket" or model.has("rangedAnimationScene"):
			continue
		var side := "r" if part == 0 else "l"
		var upper := skeleton.find_bone("upperarm_" + side)
		var lower := skeleton.find_bone("lowerarm_" + side)
		var hand := skeleton.find_bone("hand_" + side)
		if mini(upper, mini(lower, hand)) < 0:
			continue
		for attachment: Node in actor._equipment_nodes.get(part, []):
			if attachment is BoneAttachment3D and attachment.get_child_count() > 0:
				var prop := attachment.get_child(0) as Node3D
				if prop != null:
					_hands.append({"upper": upper, "lower": lower, "hand": hand,
						"side": 1.0 if part == 0 else -1.0,
						"grip": prop.basis.orthonormalized()})
	update_activity()
	if _hands.is_empty():
		_weight = 0.0

func update_activity() -> void:
	active = not _hands.is_empty() and actor.animation_tier() != AnimationGate.Tier.PAUSED

func _process_modification_with_delta(delta: float) -> void:
	var moving := actor.current_action in [&"walk", &"run"]
	_weight = move_toward(_weight, 1.0 if moving else 0.0,
		maxf(delta, 0.0) / maxf(actor.action_blend_seconds, 0.01))
	if _weight <= 0.0:
		return
	var skeleton := get_skeleton()
	var to_skeleton := skeleton.global_basis.orthonormalized().inverse() * actor.global_basis.orthonormalized()
	# A slight lift keeps the point clear of the ground while aiming ahead.
	var point := Vector3(0.0, 0.10, -1.0).normalized()
	var weapon_basis := to_skeleton * Basis(Vector3.RIGHT, point, Vector3.RIGHT.cross(point))
	for carry: Dictionary in _hands:
		# Keep the elbow near the body and bend the forearm forward. Shoulder
		# translation still follows the stride's natural rise and fall.
		_aim_bone(skeleton, carry.upper, carry.lower,
			to_skeleton * Vector3(0.18 * carry.side, -1.0, -0.08).normalized())
		_aim_bone(skeleton, carry.lower, carry.hand,
			to_skeleton * Vector3(0.05 * carry.side, -0.15, -1.0).normalized())
		_set_basis(skeleton, carry.hand, weapon_basis * (carry.grip as Basis).inverse())

func _aim_bone(skeleton: Skeleton3D, bone: int, child: int, direction: Vector3) -> void:
	var pose := skeleton.get_bone_global_pose(bone)
	var along := (skeleton.get_bone_global_pose(child).origin - pose.origin).normalized()
	_set_basis(skeleton, bone, Basis(Quaternion(along, direction)) * pose.basis.orthonormalized())

func _set_basis(skeleton: Skeleton3D, bone: int, basis: Basis) -> void:
	var parent := skeleton.get_bone_global_pose(skeleton.get_bone_parent(bone)).basis.orthonormalized()
	var target := (parent.inverse() * basis).get_rotation_quaternion()
	skeleton.set_bone_pose_rotation(bone,
		skeleton.get_bone_pose_rotation(bone).slerp(target, _weight))
