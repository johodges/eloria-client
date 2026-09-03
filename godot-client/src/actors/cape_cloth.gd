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
## The most a single cape point may travel in one step. A trail moves a hem a
## few centimetres a frame; a spike is a point flung far past that, so capping
## the step kills the spike and leaves the trail alone.
const MAX_MOVE := 0.09
## How far above its own animated rest a cape point may rise. A trailing cape
## lags below its rest; a spike flings a corner well above it, so a small cap
## cuts the spike without touching the trail or the high-sitting collar.
const CAPE_RISE := 0.05
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
var _lumbar := PackedInt32Array()
## The trunk capsule is fatter than a leg, and fat enough to clear a worn
## cuirass: measured, the armour's back plate stands about 0.196 behind the
## spine where the bare back reaches 0.18, so the cape rides at 0.205 to stay
## outside the plate rather than letting it poke through the cloth.
const TORSO_RADIUS := 0.205
## The spine bone's own local axis that points at the chest, found once at
## cache time against the rest hang. Multiplied by the bone's live basis each
## frame it gives a forward that follows the torso's lean and twist without
## being thrown off by an arm swinging across the body during an attack.
var _forward_local := Vector3.ZERO
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
	# The lumbar capsule covers the waist, between the trunk and the thighs.
	# Without it the lower back and the fauld of a cuirass sat in a gap that
	# no capsule guarded, and the cape crept through them during a lean.
	var lumbar := PackedInt32Array()
	lumbar.append(skeleton.find_bone("pelvis"))
	lumbar.append(skeleton.find_bone("spine_01"))
	if lumbar[0] >= 0 and lumbar[1] >= 0:
		_lumbar = lumbar
	# The torso's forward axis, for holding the cape behind the back, taken
	# from the SPINE bone's own orientation rather than the shoulder line: an
	# attack swings one arm across the body, and a forward derived from the
	# arms swung with it, so the "behind the back" plane stopped being behind
	# the torso exactly when the swing threw the cape forward. The spine bone
	# turns with the torso and not the arms. Which of its local axes points at
	# the chest is found once, against the rest hang the cape drapes opposite.
	var anchor_rest := skeleton.get_bone_global_rest(_anchor)
	var up_rest := Vector3.UP
	var neck := skeleton.find_bone("neck_01")
	if neck >= 0:
		up_rest = (skeleton.get_bone_global_rest(neck).origin
			- anchor_rest.origin).normalized()
	var hang := skeleton.get_bone_global_rest(_bones[1][1]).origin - anchor_rest.origin
	hang -= up_rest * hang.dot(up_rest)
	if hang.length_squared() > 1e-9:
		hang = hang.normalized()
		var best := -2.0
		for local in [Vector3.RIGHT, Vector3.LEFT, Vector3.UP, Vector3.DOWN,
				Vector3.FORWARD, Vector3.BACK]:
			var world: Vector3 = (anchor_rest.basis * local).normalized()
			var flat := world - up_rest * world.dot(up_rest)
			if flat.length_squared() < 1e-4:
				continue
			# Forward opposes the hang, which points behind.
			var score: float = flat.normalized().dot(-hang)
			if score > best:
				best = score
				_forward_local = local
	return true


## The torso's forward direction in world space, or ZERO if it is undefined.
## Recomputed each frame from the spine bone's live basis so a leaning,
## twisting attack carries the "behind the back" plane with the torso -- and
## only the torso, not the arms.
func _torso_forward(skeleton: Skeleton3D, to_world: Transform3D) -> Vector3:
	if _forward_local == Vector3.ZERO:
		return Vector3.ZERO
	var basis: Basis = to_world.basis * skeleton.get_bone_global_pose(_anchor).basis
	var forward := (basis * _forward_local)
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
	if not _lumbar.is_empty():
		point = _push_out_of_capsule(skeleton, to_world, point, _lumbar,
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
			var candidate := current + (current - previous[index]) * damping + fall
			# Cap how far a point may travel in one step. An attack lunges the
			# anchor half a metre in a few frames, and the carried velocity flung
			# a hem corner into a sharp spike above the shoulder; a per-step cap
			# bleeds that off without stiffening the ordinary trail.
			var move := candidate - current
			var far := move.length()
			if far > MAX_MOVE:
				candidate = current + move * (MAX_MOVE / far)
			points[index] = candidate
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
				# No point may rise far above where the animation alone would
				# place it. A trailing cape lags below its rest; a spike is the
				# simulation flinging a hem corner well above it, over the
				# shoulder. Capping the rise against each point's own rest keeps
				# the collar high where it belongs and only cuts the spike.
				var ceiling := rest[index].y + CAPE_RISE
				if points[index].y > ceiling:
					points[index].y = ceiling
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
