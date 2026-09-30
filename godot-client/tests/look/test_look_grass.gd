extends SceneTree
## Guards the look pass's grass beds (layer L4).
##
## With ELORIA_LOOK unset nothing is grown and no node is added. With it on,
## tufts grow on the grass and densest along a road's verge, never on the
## road itself, under a wall, on a steep bank, under water, on pale paving or
## where a second road deck covers the rim of the first; placement is the
## same every time it is worked out, lives in the ground's frame (so moving
## the world moves the bed, not the tufts within it), stays inside its
## budget, draws in three MultiMeshes on the gameplay layer without shadows,
## and the tuft meshes are the tapered 5-9 blade tufts the shader expects.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var previous := OS.get_environment(LookProfile.ENABLE_VARIABLE)
	var manifest := WorldManifest.new()
	manifest.data = {"continentGeography": {"geometryMode": "continent-chunks-v1"},
		"environment": {"sun": {"enabled": true}}}
	var interior := WorldManifest.new()
	interior.data = {"environment": {"sun": {"enabled": false}}}
	var parent := Node3D.new()
	parent.name = "WorldRoot"
	root.add_child(parent)
	var world := _world()
	parent.add_child(world)
	for i in 3:
		await physics_frame

	# --- Tuft meshes -------------------------------------------------------
	for variant: int in LookProfile.GRASS_TUFTS.size():
		var mesh := LookGrassBeds.tuft_mesh(variant)
		var blades := int(LookProfile.GRASS_TUFTS[variant].blades)
		var arrays := mesh.surface_get_arrays(0)
		var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
		var colours: PackedColorArray = arrays[Mesh.ARRAY_COLOR]
		var uvs: PackedVector2Array = arrays[Mesh.ARRAY_TEX_UV]
		var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		_expect(blades >= 5 and blades <= 9 and vertices.size() == blades * 5
			and indices.size() == blades * 9,
			"tuft %d has %d tapered two-segment blades" % [variant, blades])
		var root_shade := 1.0
		var tip_shade := 0.0
		var tip_width_zero := true
		for blade: int in blades:
			root_shade = minf(root_shade, colours[blade * 5].r)
			tip_shade = maxf(tip_shade, colours[blade * 5 + 4].r)
			tip_width_zero = tip_width_zero and uvs[blade * 5 + 4].y == 1.0 \
				and uvs[blade * 5].y == 0.0
		_expect(root_shade < tip_shade and tip_width_zero,
			"tuft %d's vertex colour darkens towards the root, UV.y runs root to tip" % variant)
		_expect(LookGrassBeds.tuft_mesh(variant) == mesh, "tuft %d is built once" % variant)

	# --- Classification helpers ----------------------------------------------
	_expect(int(LookGrassBeds.vertex_ground(Color(0.22, 0.44, 0.28)).x) == LookGrassBeds.Ground.GRASS,
		"an island's green vertex colour is grass")
	_expect(int(LookGrassBeds.vertex_ground(Color(0.82, 0.76, 0.58)).x) == LookGrassBeds.Ground.PATH,
		"its sand-gold trail is path")
	_expect(int(LookGrassBeds.vertex_ground(Color(0.46, 0.57, 0.41)).x) == LookGrassBeds.Ground.VERGE,
		"the blend between them is verge")
	_expect(int(LookGrassBeds.vertex_ground(Color(0.45, 0.44, 0.42)).x) == LookGrassBeds.Ground.NONE,
		"grey rock is neither")
	var road := LookProfile.TERRAIN_ROAD_COLOUR
	_expect(LookGrassBeds.road_weight(Color(road.r / 0.92, road.g / 0.92, road.b / 0.92), false) > 0.99
		and LookGrassBeds.road_weight(Color(0.1, 0.3, 0.05), false) < 0.01,
		"the terrain's worn road colour is road, its grass colour is not")
	var grass_texture := ImageTexture.new()
	grass_texture.resource_path = "res://tmp/ground-basecolor.png"
	var scree_texture := ImageTexture.new()
	scree_texture.resource_path = "res://tmp/alpine-scree-lichen-v001.png"
	var heather_texture := ImageTexture.new()
	heather_texture.resource_path = "res://tmp/moor-peat-heather-v001.png"
	_expect(LookGrassBeds.grassiness(grass_texture) == 1.0
		and LookGrassBeds.grassiness(scree_texture) == 0.0
		and absf(LookGrassBeds.grassiness(heather_texture) - 0.6) < 0.001
		and LookGrassBeds.grassiness(null) == LookProfile.GRASS_LAYER_DEFAULT,
		"biome layers are as grassy as their textures say")
	var weights := LookGrassBeds.barycentric_xz(Vector3(0.25, 5.0, 0.25),
		Vector3.ZERO, Vector3(1, 0, 0), Vector3(0, 0, 1))
	_expect(weights.is_equal_approx(Vector3(0.5, 0.25, 0.25)), "barycentric weights across the ground")
	_expect(LookGrassBeds.value_noise(3.3, -7.1, 11) == LookGrassBeds.value_noise(3.3, -7.1, 11)
		and LookGrassBeds.value_noise(3.3, -7.1, 11) >= 0.0
		and LookGrassBeds.value_noise(3.3, -7.1, 11) <= 1.0, "the bed noise is deterministic")

	# --- Look off: nothing ---------------------------------------------------
	# The focus sits on the terrain frame's origin, (100, 0, -50) in the world.
	var focus := Vector3(100.0, 0.0, -50.0)
	OS.set_environment(LookProfile.ENABLE_VARIABLE, "0")
	LookGrassBeds.tend(parent, world, manifest, {}, focus)
	_expect(parent.get_node_or_null(LookGrassBeds.NODE_NAME) == null,
		"with the look off no grass node is added")

	# --- Look on ---------------------------------------------------------------
	OS.set_environment(LookProfile.ENABLE_VARIABLE, "1")
	LookGrassBeds.tend(parent, world, manifest, {}, focus)
	var beds := parent.get_node_or_null(LookGrassBeds.NODE_NAME) as LookGrassBeds
	_expect(beds != null, "with the look on the grass node is added")
	if beds == null:
		_finish(previous)
		return
	beds.settle()
	var positions := beds.tuft_positions()
	_expect(positions.size() > 500, "tufts grow on the grass (%d)" % positions.size())
	var counts := beds.tuft_counts()
	_expect(counts[0] + counts[1] + counts[2] == positions.size()
		and positions.size() <= LookProfile.GRASS_INSTANCE_BUDGET,
		"the MultiMeshes hold every placed tuft, within the budget")
	var on_road := 0
	var verge := 0
	var open := 0
	var in_house := 0
	var on_bank := 0
	var in_pond := 0
	var on_paving := 0
	var on_overlap := 0
	for position: Vector3 in positions:
		# The frame is the terrain's own space, offset from the world by
		# (100, 0, -50); the road runs along x = 0 there.
		var x := position.x
		var z := position.z
		if absf(x) < 1.2 and z < 18.5:
			on_road += 1
		elif absf(x) >= 1.9 and absf(x) < 2.7 and z < 19.0:
			verge += 1
		elif absf(x) > 6.0 and absf(x) < 12.0 and z > -12.0 and z < 12.0:
			open += 1
		if x > 14.0 and x < 18.0 and z > -2.0 and z < 2.0:
			in_house += 1
		if x > -21.5 and x < -16.5 and z > -23.0 and z < -15.0:
			on_bank += 1
		if x > 8.0 and x < 12.0 and z > -24.0 and z < -20.0:
			in_pond += 1
		if x > -13.15 and x < -6.85 and z > 14.85 and z < 21.15:
			on_paving += 1
		if absf(x) < 1.2 and z >= 18.5 and z < 24.0:
			on_overlap += 1
	_expect(on_road == 0, "no tuft on the road (%d)" % on_road)
	_expect(verge > 0 and float(verge) / (0.8 * 2.0 * 51.0) > float(open) / (6.0 * 2.0 * 24.0),
		"the verge is denser than open grass (%d on the verge, %d in the open)" % [verge, open])
	_expect(in_house == 0, "no tuft under a wall (%d)" % in_house)
	_expect(on_bank == 0, "no tuft on a steep bank (%d)" % on_bank)
	_expect(in_pond == 0, "no tuft under water (%d)" % in_pond)
	_expect(on_paving == 0, "no tuft on pale paving nor within its margin (%d)" % on_paving)
	_expect(on_overlap == 0, "no tuft on a deck's rim where another deck is road (%d)" % on_overlap)
	var census := beds.get("_census") as Dictionary
	_expect(census.get("face_mismatch", 0) == 0, "every face index found its triangle")

	# Deterministic: forgetting and placing again grows the same tufts.
	var first := _sorted(positions)
	beds.update(null, manifest, {}, focus)
	_expect(beds.tuft_positions().is_empty() and not beds.visible,
		"a map without ground forgets the bed")
	beds.update(world, manifest, {}, focus)
	beds.settle()
	_expect(_sorted(beds.tuft_positions()) == first, "the same ground grows the same tufts")

	# The bed rides the frame: moving the world moves the node, not the tufts.
	world.position += Vector3(30.0, 2.0, -12.0)
	await physics_frame
	await physics_frame
	beds.update(world, manifest, {}, focus + Vector3(30.0, 2.0, -12.0))
	_expect(beds.global_position.is_equal_approx(Vector3(130.0, 2.0, -62.0))
		and _sorted(beds.tuft_positions()) == first, "a rebase moves the bed with its ground")

	var drawn := beds.get_child(0) as MultiMeshInstance3D
	_expect(beds.get_child_count() == 3 and drawn != null
		and drawn.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		and drawn.layers == LookProfile.GRASS_RENDER_LAYER
		and drawn.multimesh.use_colors and drawn.multimesh.use_custom_data
		and (drawn.material_override as ShaderMaterial).shader
			== preload("res://src/world/look/grass_beds.gdshader"),
		"three MultiMeshes, shadowless, on the gameplay layer, with colours and custom data")

	beds.update(world, interior, {}, Vector3.ZERO)
	_expect(not beds.visible and beds.tuft_positions().is_empty(), "an interior grows no grass")
	_finish(previous)

func _sorted(positions: PackedVector3Array) -> PackedVector3Array:
	var copy := positions.duplicate()
	copy.sort()
	return copy

func _finish(previous: String) -> void:
	OS.set_environment(LookProfile.ENABLE_VARIABLE, previous)
	print("test_look_grass: %d failure(s)" % failures)
	quit(1 if failures > 0 else 0)

## A small continent map, 64 m square, in a terrain frame offset from its
## root: flat grass with a road deck down x = 0 (coverage 1 in the middle,
## 0 at 2.4 m out), a second deck overlapping its far end, a walled house, a
## steep bank, a pond, and a pale paving patch.
func _world() -> Node3D:
	var world := Node3D.new()
	world.name = "ImportedWorld_test"
	var frame := Vector3(100.0, 0.0, -50.0)
	var grass := StandardMaterial3D.new()
	grass.resource_name = "continental_ground"
	_walk(world, "Terrain_test_0_0", _plane(-32.0, -32.0, 32.0, 32.0, 0.0, Color(0.2, 0.5, 0.1), 16),
		grass, frame)
	var deck := StandardMaterial3D.new()
	deck.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	deck.cull_mode = BaseMaterial3D.CULL_DISABLED
	_walk(world, "Walk_test_road", _strip(-2.4, 2.4, -32.0, 24.0, 0.06), deck, frame)
	# A second deck crossing the first one's far end, a little above it so the
	# rays always find it first: its rim lies over the first one's road.
	_walk(world, "Walk_test_crossing", _strip_x(-6.0, 6.0, 19.0, 25.0, 0.09), deck, frame)
	var house := StaticBody3D.new()
	house.collision_layer = LookGrassBeds.WORLD_LAYER
	var box := CollisionShape3D.new()
	box.shape = BoxShape3D.new()
	(box.shape as BoxShape3D).size = Vector3(6.0, 5.0, 6.0)
	house.position = frame + Vector3(16.0, 2.5, 0.0)
	house.add_child(box)
	world.add_child(house)
	# A steep bank (50 degrees), wholly above the ground so the rays find it:
	# turned about its own middle, (-19, 5, -19) in the frame.
	var bank := _walk(world, "Terrain_test_bank", _plane(-24.0, -24.0, -14.0, -14.0, 0.0,
		Color(0.2, 0.5, 0.1), 2), grass, frame)
	bank.rotation = Vector3(0.0, 0.0, deg_to_rad(50.0))
	bank.position = frame + Vector3(-19.0, 5.0, 0.0) - (bank.basis * Vector3(-19.0, 0.0, 0.0))
	var pond := MeshInstance3D.new()
	pond.name = "Water_test_pond"
	pond.mesh = _plane(7.0, -25.0, 13.0, -19.0, 0.4, Color.WHITE, 1)
	pond.position = frame
	world.add_child(pond)
	var paving := StandardMaterial3D.new()
	paving.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	paving.albedo_color = Color("ccba9c")
	var plaza := MeshInstance3D.new()
	plaza.name = "AuthoredGround_test_plaza"
	plaza.mesh = _plane(-13.0, 15.0, -7.0, 21.0, 0.03, Color(1, 1, 1, 1), 2)
	plaza.material_override = null
	plaza.set_surface_override_material(0, paving)
	plaza.position = frame
	world.add_child(plaza)
	return world

func _walk(world: Node3D, node_name: String, mesh: ArrayMesh, material: Material,
		frame: Vector3) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	node.set_surface_override_material(0, material)
	node.position = frame
	world.add_child(node)
	var body := StaticBody3D.new()
	body.name = node_name + "_WalkSurfaceCollision"
	body.collision_layer = LookGrassBeds.WALK_LAYER
	var shape := CollisionShape3D.new()
	shape.shape = mesh.create_trimesh_shape()
	body.add_child(shape)
	node.add_child(body)
	return node

## A flat grid of `cells` x `cells` quads with one vertex colour. Every mesh
## here is wound to face up, as the exporters' walk surfaces are: the physics
## server's concave ray casts never report a back face.
func _plane(x0: float, z0: float, x1: float, z1: float, y: float, colour: Color,
		cells: int) -> ArrayMesh:
	var vertices := PackedVector3Array()
	var colours := PackedColorArray()
	var indices := PackedInt32Array()
	for i: int in cells + 1:
		for j: int in cells + 1:
			vertices.append(Vector3(lerpf(x0, x1, float(i) / cells), y, lerpf(z0, z1, float(j) / cells)))
			colours.append(colour)
	for i: int in cells:
		for j: int in cells:
			var a := i * (cells + 1) + j
			indices.append_array([a, a + cells + 1, a + 1, a + 1, a + cells + 1, a + cells + 2])
	return _mesh(vertices, colours, indices)

## A road deck across x (x0..x1) along z, with coverage 1 in its middle
## third and 0 at its edges, as the exporter writes it.
func _strip(x0: float, x1: float, z0: float, z1: float, y: float) -> ArrayMesh:
	var xs := [x0, lerpf(x0, x1, 0.25), lerpf(x0, x1, 0.75), x1]
	var alphas := [0.0, 1.0, 1.0, 0.0]
	var vertices := PackedVector3Array()
	var colours := PackedColorArray()
	var indices := PackedInt32Array()
	var rows := 14
	for r: int in rows + 1:
		for c: int in 4:
			vertices.append(Vector3(xs[c], y, lerpf(z0, z1, float(r) / rows)))
			colours.append(Color(1, 1, 1, alphas[c]))
	for r: int in rows:
		for c: int in 3:
			var a := r * 4 + c
			indices.append_array([a, a + 1, a + 4, a + 1, a + 5, a + 4])
	return _mesh(vertices, colours, indices)

## The same, running across x with its coverage across z.
func _strip_x(x0: float, x1: float, z0: float, z1: float, y: float) -> ArrayMesh:
	var zs := [z0, lerpf(z0, z1, 0.25), lerpf(z0, z1, 0.75), z1]
	var alphas := [0.0, 1.0, 1.0, 0.0]
	var vertices := PackedVector3Array()
	var colours := PackedColorArray()
	var indices := PackedInt32Array()
	var columns := 6
	for c: int in columns + 1:
		for r: int in 4:
			vertices.append(Vector3(lerpf(x0, x1, float(c) / columns), y, zs[r]))
			colours.append(Color(1, 1, 1, alphas[r]))
	for c: int in columns:
		for r: int in 3:
			var a := c * 4 + r
			indices.append_array([a, a + 4, a + 1, a + 1, a + 4, a + 5])
	return _mesh(vertices, colours, indices)

func _mesh(vertices: PackedVector3Array, colours: PackedColorArray,
		indices: PackedInt32Array) -> ArrayMesh:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_COLOR] = colours
	arrays[Mesh.ARRAY_INDEX] = indices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS " + message)
	else:
		failures += 1
		print("FAIL " + message)
