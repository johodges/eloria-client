extends SkeletonModifier3D
## Verlet cloth for the cape chains on the player rig.
##
## A cape skinned to the spine cannot avoid a leg. Measured against the shared
## clips, the body passes 254 mm behind the cape in a walk and 858 mm in a run,
## and weighting the hem to the thighs does not help: one cape spanning both
## legs follows their average, which is exactly where neither leg is.
##
## So the rig carries three chains of four bones - cape_{l,c,r}_01..04 - that no
## clip in the shared library names, and this drives them. Three chains rather
## than one because a single column cannot twist, and the halves of a cape have
## to part around a leg independently.
##
## The simulation runs in world space, not skeleton space, so the cape trails
## when the actor runs rather than only reacting to the spine bobbing. It is a
## SkeletonModifier3D so the engine orders it after the animation has posed the
## skeleton; writing bone poses from _process would race the AnimationPlayer.

const CHAINS: Array[String] = ["l", "c", "r"]
const LINKS := 4
## Heavier than the real 9.8: a cape driven by a skeleton has no air to push
## against, so weighting it down is what keeps the hem from flying up behind a
## moving actor.
const GRAVITY := Vector3(0.0, -14.0, 0.0)
## Fraction of velocity carried between steps. Cloth that keeps everything
## oscillates forever. 0.84 carried enough momentum to lift the hem well past
## the waist in motion and hold it there; this settles in about a quarter of a
## second and trails lower while travelling.
const DAMPING := 0.72
## Two passes is enough for a four-link chain and is the whole reason this is
## affordable. More iterations buy stiffness nobody can see on a cape.
const RELAX_PASSES := 2
## The leg capsules the cape is pushed out of, as a fraction over the measured
## thigh radius, so cloth rides clear of the skin rather than exactly on it.
const LEG_RADIUS := 0.115
## A frame longer than this is a hitch, not motion: clamping stops a stall from
## flinging the chain and leaving it to swing back for a second afterwards.
const MAX_STEP := 1.0 / 30.0
## Move further than this in one step and the actor was teleported, not walked.
const TELEPORT := 1.5
## Once the anchor is slower than this the wearer has stopped, and the cape
## should come back down briskly instead of drifting: gravity multiplies and
## the damping drops so the swing dies in a fraction of the travelling time.
const SETTLE_SPEED := 0.15
const SETTLE_GRAVITY := 25.0
const SETTLE_DAMPING := 0.30

var _cached := false
var _anchor := -1
var _bones: Array[PackedInt32Array] = []
var _points: Array[PackedVector3Array] = []
var _previous: Array[PackedVector3Array] = []
var _lengths: Array[PackedFloat32Array] = []
var _legs: Array[PackedInt32Array] = []
var _settled := false
var _last_anchor := Vector3.ZERO
var _torso := PackedInt32Array()
## The trunk capsule is fatter than a leg.
const TORSO_RADIUS := 0.185
## The shoulder line and the neck give the torso a forward axis each frame,
## so the cape can be held behind the back however the torso twists or leans.
var _shoulder_l := -1
var _shoulder_r := -1
var _neck := -1
## Which way `side.cross(up)` points, locked at cache time against the rest
## hang: a cape hangs behind, so forward is whichever sign opposes it.
var _forward_sign := 1.0
## Cape points stay this far behind the spine plane. The bone runs down the
## middle of the torso, so a small negative keeps cloth off the chest and the
## sternum while never disturbing a cape already hanging down the back.
const BACK_OFFSET := -0.02


func _cache(skeleton: Skeleton3D) -> bool:
	_cached = true
	_anchor = skeleton.find_bone("spine_03")
	if _anchor < 0:
		return false
	for chain in CHAINS:
		var bones := PackedInt32Array()
		for link in range(LINKS):
			var bone := skeleton.find_bone("cape_%s_%02d" % [chain, link + 1])
			if bone < 0:
				return false
			bones.append(bone)
		var lengths := PackedFloat32Array()
		for link in range(1, LINKS):
			lengths.append(skeleton.get_bone_rest(bones[link]).origin.length())
		# The last bone has no child, so its tip repeats its own drop.
		lengths.append(lengths[lengths.size() - 1])
		_bones.append(bones)
		_lengths.append(lengths)
		_points.append(PackedVector3Array())
		_previous.append(PackedVector3Array())
	for side in ["l", "r"]:
		var pair := PackedInt32Array()
		pair.append(skeleton.find_bone("thigh_%s" % side))
		pair.append(skeleton.find_bone("calf_%s" % side))
		if pair[0] >= 0 and pair[1] >= 0:
			_legs.append(pair)
	# The trunk keeps the upper sheet off the back the same way the legs
	# keep the hem off the shins; without it the simulation relaxes the
	# top links straight into the shoulder blades.
	var trunk := PackedInt32Array()
	trunk.append(skeleton.find_bone("spine_01"))
	trunk.append(skeleton.find_bone("neck_01"))
	if trunk[0] >= 0 and trunk[1] >= 0:
		_torso = trunk
	# The torso's forward axis, for holding the cape behind the back. The
	# shoulder line and the spine-up cross to a forward that follows every
	# twist and lean; its sign is fixed once against the rest hang, since a
	# cape at rest drapes behind and forward must oppose it.
	_shoulder_l = skeleton.find_bone("upperarm_l")
	_shoulder_r = skeleton.find_bone("upperarm_r")
	_neck = skeleton.find_bone("neck_01")
	if _shoulder_l >= 0 and _shoulder_r >= 0 and _neck >= 0:
		var anchor_rest := skeleton.get_bone_global_rest(_anchor).origin
		var up := (skeleton.get_bone_global_rest(_neck).origin
			- anchor_rest).normalized()
		var side := (skeleton.get_bone_global_rest(_shoulder_l).origin
			- skeleton.get_bone_global_rest(_shoulder_r).origin).normalized()
		var forward := side.cross(up)
		var hang := skeleton.get_bone_global_rest(_bones[1][1]).origin - anchor_rest
		hang -= up * hang.dot(up)
		if forward.dot(hang) > 0.0:
			_forward_sign = -1.0
	return true


## The torso's forward direction in world space, or ZERO if the bones that
## define it are missing. Recomputed each frame so a leaning, twisting attack
## carries the "behind the back" plane with it.
func _torso_forward(skeleton: Skeleton3D, to_world: Transform3D) -> Vector3:
	if _shoulder_l < 0 or _shoulder_r < 0 or _neck < 0:
		return Vector3.ZERO
	var anchor_pos := to_world * skeleton.get_bone_global_pose(_anchor).origin
	var up := (to_world * skeleton.get_bone_global_pose(_neck).origin
		- anchor_pos)
	var side := (to_world * skeleton.get_bone_global_pose(_shoulder_l).origin
		- to_world * skeleton.get_bone_global_pose(_shoulder_r).origin)
	if up.length_squared() < 1e-9 or side.length_squared() < 1e-9:
		return Vector3.ZERO
	var forward := side.normalized().cross(up.normalized()) * _forward_sign
	if forward.length_squared() < 1e-9:
		return Vector3.ZERO
	return forward.normalized()


func _rest_joints(skeleton: Skeleton3D, to_world: Transform3D,
		chain: int) -> PackedVector3Array:
	"""Where this chain hangs with no simulation, in world space."""
	var joints := PackedVector3Array()
	var frame := skeleton.get_bone_global_pose(_anchor)
	for link in range(LINKS):
		var rest := skeleton.get_bone_rest(_bones[chain][link])
		frame = frame * rest
		joints.append(to_world * frame.origin)
	var last := skeleton.get_bone_rest(_bones[chain][LINKS - 1])
	joints.append(to_world * (frame * last.origin))
	return joints


func _push_out_of_legs(skeleton: Skeleton3D, to_world: Transform3D,
		point: Vector3) -> Vector3:
	if not _torso.is_empty():
		point = _push_out_of_capsule(skeleton, to_world, point, _torso,
			TORSO_RADIUS)
	for pair in _legs:
		point = _push_out_of_capsule(skeleton, to_world, point, pair,
			LEG_RADIUS)
	return point


func _push_out_of_capsule(skeleton: Skeleton3D, to_world: Transform3D,
		point: Vector3, pair: PackedInt32Array, radius: float) -> Vector3:
	var a := to_world * skeleton.get_bone_global_pose(pair[0]).origin
	var b := to_world * skeleton.get_bone_global_pose(pair[1]).origin
	var axis := b - a
	var span := axis.length_squared()
	var travel := 0.0 if span < 1e-9 else clampf((point - a).dot(axis) / span, 0.0, 1.0)
	var near := a + axis * travel
	var away := point - near
	var gap := away.length()
	if gap < radius:
		# Straight out from the bone, or straight back if the point landed
		# exactly on it, which happens the frame a leg swings through.
		var direction := (away / gap) if gap > 1e-5 else -to_world.basis.z.normalized()
		point = near + direction * radius
	return point


func _process_modification_with_delta(delta: float) -> void:
	var skeleton := get_skeleton()
	if skeleton == null:
		return
	if not _cached and not _cache(skeleton):
		return
	if _anchor < 0 or _bones.is_empty():
		return
	var to_world := skeleton.global_transform
	var to_local := to_world.affine_inverse()
	var step := minf(maxf(delta, 0.0), MAX_STEP)
	var anchor_world := to_world * skeleton.get_bone_global_pose(_anchor).origin
	var anchor_speed := 0.0 if step <= 0.0 else (
		anchor_world.distance_to(_last_anchor) / step)
	_last_anchor = anchor_world
	var still := anchor_speed < SETTLE_SPEED
	var fall := GRAVITY * (SETTLE_GRAVITY if still else 1.0) * step * step
	var damping := SETTLE_DAMPING if still else DAMPING
	# The back-of-the-torso plane, held for every chain this frame: a cape
	# swings and cannot pass to the chest, which is what an attack's lean and
	# twist made it do.
	var forward := _torso_forward(skeleton, to_world)
	var plane_at := (to_world * skeleton.get_bone_global_pose(_anchor).origin).dot(
		forward) + BACK_OFFSET if forward != Vector3.ZERO else 0.0

	for chain in range(_bones.size()):
		var rest := _rest_joints(skeleton, to_world, chain)
		var points := _points[chain]
		if points.size() != rest.size() or not _settled:
			points = rest.duplicate()
			_previous[chain] = rest.duplicate()
		# The root joint is carried by the spine and never simulated.
		points[0] = rest[0]
		var previous := _previous[chain]
		previous[0] = rest[0]
		if points[1].distance_to(rest[1]) > TELEPORT:
			points = rest.duplicate()
			previous = rest.duplicate()
		for index in range(1, points.size()):
			var current := points[index]
			points[index] = current + (current - previous[index]) * damping + fall
			previous[index] = current
		for _pass in range(RELAX_PASSES):
			for index in range(1, points.size()):
				var offset := points[index] - points[index - 1]
				var length := offset.length()
				if length > 1e-6:
					points[index] = points[index - 1] + offset * (
						_lengths[chain][index - 1] / length)
			for index in range(1, points.size()):
				points[index] = _push_out_of_legs(skeleton, to_world, points[index])
				if forward != Vector3.ZERO:
					var ahead := points[index].dot(forward) - plane_at
					if ahead > 0.0:
						points[index] -= forward * ahead
		_points[chain] = points
		_previous[chain] = previous

		# Aim each bone at the joint below it. The chain is walked from the
		# top so every bone sees the pose its parent has just been given.
		var parent := skeleton.get_bone_global_pose(_anchor)
		for link in range(LINKS):
			var bone := _bones[chain][link]
			var bone_rest := skeleton.get_bone_rest(bone)
			var head := parent * bone_rest.origin
			var basis := parent.basis * bone_rest.basis
			var child: Vector3 = (skeleton.get_bone_rest(_bones[chain][link + 1]).origin
				if link + 1 < LINKS else bone_rest.origin)
			var aimed := (basis * child).normalized()
			var wanted := (to_local * points[link + 1] - head).normalized()
			if aimed.length_squared() > 0.5 and wanted.length_squared() > 0.5:
				basis = Basis(Quaternion(aimed, wanted)) * basis
			skeleton.set_bone_pose_rotation(bone,
				(parent.basis.inverse() * basis).get_rotation_quaternion())
			parent = Transform3D(basis, head)
	_settled = true


func reset() -> void:
	"""Drop the chains back onto their rest hang, for a teleport or a respawn."""
	_settled = false
