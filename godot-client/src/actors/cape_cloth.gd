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

var _cached := false
var _anchor := -1
var _bones: Array[PackedInt32Array] = []
var _points: Array[PackedVector3Array] = []
var _previous: Array[PackedVector3Array] = []
var _lengths: Array[PackedFloat32Array] = []
var _legs: Array[PackedInt32Array] = []
var _settled := false


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
	return true


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
	for pair in _legs:
		var a := to_world * skeleton.get_bone_global_pose(pair[0]).origin
		var b := to_world * skeleton.get_bone_global_pose(pair[1]).origin
		var axis := b - a
		var span := axis.length_squared()
		var travel := 0.0 if span < 1e-9 else clampf((point - a).dot(axis) / span, 0.0, 1.0)
		var near := a + axis * travel
		var away := point - near
		var gap := away.length()
		if gap < LEG_RADIUS:
			# Straight out from the bone, or straight back if the point landed
			# exactly on it, which happens the frame a leg swings through.
			var direction := (away / gap) if gap > 1e-5 else -to_world.basis.z.normalized()
			point = near + direction * LEG_RADIUS
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
	var fall := GRAVITY * step * step

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
			points[index] = current + (current - previous[index]) * DAMPING + fall
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
