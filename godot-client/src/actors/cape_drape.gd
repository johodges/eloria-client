class_name CapeDrape
extends RefCounted
## Holds a cape's rigid yoke outside the armour it is actually worn over.
##
## The cape's collar, and the sheet above the shoulder blades, are skinned to
## spine_03 and to nothing else - no cape bone touches them, so the cloth solver
## in `cape_cloth.gd` has no authority there whatever it does below. They were
## conformed once, offline, against the BARE back. Every torso in the ladder
## stands deeper than that: between 11 and 53 mm over the shoulder blades on the
## plainest shirt, and a gorget or a mantle reaches 100 mm further still. So the
## armour came through the cloth on every armoured wearer, in every pose.
##
## One authored cape cannot clear all sixty-four of them. Conformed to the
## deepest, its collar stands off the shoulders like a shelf on everything else
## - measured, and looked at. So the yoke is pushed out here instead, against
## the piece the actor is wearing, and the result is cached per cape and torso.

## The envelope is a radius per bearing around the trunk, per height band.
## A depth alone cannot describe a collar: it is a ring, and holding a ring back
## in z flattens it into a bar behind the shoulders. What a cape does over a
## gorget is take a wider radius at the same bearing, which is what this
## measures and what the push restores.
##
## The trunk line is taken as x = 0, z = 0 rather than the spine bone, which
## wanders 40 mm through the chest. Envelope and cloth are read against the same
## origin, so a shared one is all the clearance needs; over the back half of a
## torso every bearing still meets the surface once, which is the only property
## relied on.
const BEARING_STEP := 10.0
const BEARING_LIMIT := 90.0
const BAND_STEP := 0.05
const BAND_FLOOR := 0.90
const BAND_CEILING := 1.65
## Half the trunk the envelope is built from. Torso models are authored in an A
## pose, so a sleeve reaches 700 mm out; measured around the spine that reads as
## a bearing of 80 degrees at three times the radius of the back it belongs to,
## and it would inflate the cape into a barrel. A cape is worn over the trunk,
## and the arms hang outside it.
const TRUNK_HALF := 0.26
## How far outside the armour the cloth rides.
const CLEARANCE := 0.02
## The bare trunk's radius, and the floor under every measured reach: a bare
## back stands 0.18 behind the spine and the cloth rides clear of it. The
## solver holds this constant too, so it is stated once here.
const BARE_TRUNK_RADIUS := 0.205
## The cape is the outer layer across the back, and only there.
##
## A pauldron sitting over the end of the collar is how armour is worn, not a
## defect, and so is a gorget standing over the collar itself: the cloth tucks
## under both. Push those out and the collar stops being a ring around the
## shoulders and becomes a plank across them - which is what conforming the
## whole yoke looked like, rendered. So the push is full across the back and
## gone past the point of the shoulder, and full below the shoulder line and
## gone at the collar. What is left is the sheet over the shoulder blades,
## where the cape is unambiguously the outer layer and where the armour was in
## fact coming through.
const DRAPE_ARC := 50.0
const DRAPE_FADE := 65.0
const DRAPE_SHOULDER := 1.44
const DRAPE_COLLAR := 1.53
## Samples along a bone axis in the reach the cloth solver is given. Nine over
## the trunk is a sample every 55 mm, which follows a back plate without
## chasing the rivets on it.
const REACH_SAMPLES := 9
## A vertex with no weight on a cape bone is yoke, and takes the whole push;
## one the solver shares takes its share. Below that the solver owns the cloth
## and lifts it off the body every frame, and an offset baked in here would be
## added on top of whatever it does.
const CAPE_BONE_PREFIX := "cape_"


static func columns() -> int:
	return int(round(BEARING_LIMIT * 2.0 / BEARING_STEP)) + 1


static func rows() -> int:
	return int(round((BAND_CEILING - BAND_FLOOR) / BAND_STEP)) + 1


## How far the worn torso reaches from the trunk line, per bearing and band.
## Empty when the pieces carry no geometry in the band a cape covers.
static func envelope(pieces: Array) -> PackedFloat32Array:
	var wide: int = columns()
	var tall: int = rows()
	var grid := PackedFloat32Array()
	grid.resize(tall * wide)
	grid.fill(0.0)
	var seen := false
	for piece_value: Variant in pieces:
		var piece: Dictionary = piece_value as Dictionary
		var mesh: Mesh = piece.get("mesh") as Mesh
		if mesh == null:
			continue
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for point: Vector3 in vertices:
				if absf(point.x) > TRUNK_HALF:
					continue
				if point.y < BAND_FLOOR or point.y >= BAND_CEILING:
					continue
				var bearing: float = rad_to_deg(atan2(point.x, -point.z))
				if absf(bearing) > BEARING_LIMIT:
					continue
				var at: int = (int((point.y - BAND_FLOOR) / BAND_STEP) * wide
					+ int((bearing + BEARING_LIMIT) / BEARING_STEP))
				var radius: float = Vector2(point.x, point.z).length()
				if radius > grid[at]:
					grid[at] = radius
					seen = true
	if not seen:
		return PackedFloat32Array()
	return _dilate(grid, tall, wide)


## Deep cells spread into the bearings beside them before anything is read
## against them: a cell boundary is not a surface, and interpolating between a
## proud cell and the slack one beside it threads the cloth back through the
## plate that made the first one proud. Only sideways, though - a back that is
## deep at the shoulder blade and shallow at the collar is a slope, not a step,
## and smearing it up the spine lifted the collar off the shoulders.
static func _dilate(grid: PackedFloat32Array, tall: int,
		wide: int) -> PackedFloat32Array:
	var out := grid.duplicate()
	for row: int in range(tall):
		for column: int in range(wide):
			var best: float = grid[row * wide + column]
			for across: int in [-1, 0, 1]:
				var near_column: int = column + across
				if near_column < 0 or near_column >= wide:
					continue
				best = maxf(best, grid[row * wide + near_column])
			out[row * wide + column] = best
	return out


## The envelope at a bearing and height, bilinear between cell centres.
static func reach(grid: PackedFloat32Array, bearing: float, y: float) -> float:
	var wide: int = columns()
	var tall: int = rows()
	var across: float = clampf((bearing + BEARING_LIMIT) / BEARING_STEP - 0.5,
		0.0, float(wide) - 1.0001)
	var down: float = clampf((y - BAND_FLOOR) / BAND_STEP - 0.5,
		0.0, float(tall) - 1.0001)
	var column: int = int(across)
	var row: int = int(down)
	var fx: float = across - float(column)
	var fy: float = down - float(row)
	var top: float = lerpf(grid[row * wide + column],
		grid[row * wide + column + 1], fx)
	var bottom: float = lerpf(grid[(row + 1) * wide + column],
		grid[(row + 1) * wide + column + 1], fx)
	return lerpf(top, bottom, fy)


## A copy of a cape surface set with its yoke pushed clear of the envelope, or
## the mesh itself when nothing had to move.
static func drape(mesh: Mesh, bones: PackedStringArray,
		grid: PackedFloat32Array) -> Mesh:
	if mesh == null or grid.is_empty():
		return mesh
	var built := ArrayMesh.new()
	var moved := false
	for surface: int in range(mesh.get_surface_count()):
		var arrays: Array = mesh.surface_get_arrays(surface)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var bone_indices: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
		var per_vertex: int = 0
		if not vertices.is_empty() and not bone_indices.is_empty():
			per_vertex = bone_indices.size() / vertices.size()
		for index: int in range(vertices.size()):
			var rigid: float = _rigid_share(bones, bone_indices, weights,
				index, per_vertex)
			if rigid <= 0.0:
				continue
			var point: Vector3 = vertices[index]
			if point.y < BAND_FLOOR or point.y >= BAND_CEILING:
				continue
			var bearing: float = rad_to_deg(atan2(point.x, -point.z))
			var fade: float = (1.0 - smoothstep(DRAPE_ARC, DRAPE_FADE,
				absf(bearing))) * (1.0 - smoothstep(DRAPE_SHOULDER,
				DRAPE_COLLAR, point.y))
			if fade <= 0.0:
				continue
			var radius: float = Vector2(point.x, point.z).length()
			if radius < 0.001:
				continue
			var wanted: float = reach(grid, bearing, point.y) + CLEARANCE
			if wanted <= radius:
				continue
			# Straight out along its own bearing, so the ring stays a ring.
			var push: float = (wanted - radius) * rigid * fade / radius
			vertices[index] = Vector3(point.x + point.x * push, point.y,
				point.z + point.z * push)
			moved = true
		arrays[Mesh.ARRAY_VERTEX] = vertices
		built.add_surface_from_arrays(mesh.surface_get_primitive_type(surface),
			arrays, [], {},
			mesh.surface_get_format(surface) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		built.surface_set_material(surface, mesh.surface_get_material(surface))
	return built if moved else mesh


## How much of a vertex the spine holds rather than the cloth solver.
static func _rigid_share(bones: PackedStringArray,
		bone_indices: PackedInt32Array, weights: PackedFloat32Array,
		index: int, per_vertex: int) -> float:
	if per_vertex <= 0 or weights.size() < (index + 1) * per_vertex:
		return 0.0
	var rigid := 0.0
	for slot: int in range(per_vertex):
		var at: int = index * per_vertex + slot
		var bone: int = bone_indices[at]
		if bone < 0 or bone >= bones.size():
			continue
		if bones[bone].begins_with(CAPE_BONE_PREFIX):
			continue
		rigid += weights[at]
	return clampf(rigid, 0.0, 1.0)


## How far the worn torso reaches from one of the solver's bone axes, sampled
## along it. The drape measures about the trunk line because it is cutting a
## ring; the solver pushes radially out of a capsule, so what it needs is the
## reach about that capsule's own axis and nothing else would be exact.
##
## The chest is left out. A breastplate is as proud as a back plate and no cape
## ever touches it, and counting it would inflate the capsule the hem swings
## around into a barrel the cloth could not fall inside of.
static func axis_reach(pieces: Array, from: Vector3, to: Vector3,
		floor_radius: float) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(REACH_SAMPLES)
	out.fill(floor_radius)
	var axis: Vector3 = to - from
	var span: float = axis.length_squared()
	if span < 1e-9:
		return out
	for piece_value: Variant in pieces:
		var piece: Dictionary = piece_value as Dictionary
		var mesh: Mesh = piece.get("mesh") as Mesh
		if mesh == null:
			continue
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			for point: Vector3 in vertices:
				if absf(point.x) > TRUNK_HALF:
					continue
				# Only what stands beside the axis, not what stands past its
				# ends: a capsule's cap measures a shoulder from the waist
				# bone as if it were a metre of girth, which is how the first
				# cut of this pushed the cape 400 mm off the back.
				var travel: float = (point - from).dot(axis) / span
				if travel < 0.0 or travel > 1.0:
					continue
				var away: Vector3 = point - (from + axis * travel)
				if away.z > 0.0:
					continue
				var slot: int = int(round(travel * float(REACH_SAMPLES - 1)))
				var radius: float = away.length()
				if radius > out[slot]:
					out[slot] = radius
	# A sample boundary is not a surface either: each one carries its
	# neighbours so the interpolation between two never dips inside the plate
	# that made the deeper of them deep.
	var smeared := out.duplicate()
	for slot: int in range(REACH_SAMPLES):
		if slot > 0:
			smeared[slot] = maxf(smeared[slot], out[slot - 1])
		if slot + 1 < REACH_SAMPLES:
			smeared[slot] = maxf(smeared[slot], out[slot + 1])
	return smeared
