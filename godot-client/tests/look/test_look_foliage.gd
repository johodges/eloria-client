extends SceneTree
## Guards the look pass's painted crowns and dithered occluder fade (layer L3).
##
## With ELORIA_LOOK=0 the crowns keep the loader's materials and
## OccluderFade blends exactly as on develop. With it on, only crowns are
## painted (never trunks, ground or a merged scatter mesh), the source
## materials and meshes are never edited, painting twice is harmless, a
## crown's jitter seed does not move when the world is rebased, a batch and
## its hidden members draw the same crown, and OccluderFade opens a hole round
## the player in painted and standard materials, lets a faded crown's shadow go
## (as develop's blended copies do) but keeps a wall's on a twin, and puts
## everything back after.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var previous := OS.get_environment(LookProfile.ENABLE_VARIABLE)
	var continent := WorldManifest.new()
	continent.data = {"continentGeography": {"geometryMode": "continent-chunks-v1"},
		"environment": {"sun": {"enabled": true}}}
	var island := WorldManifest.new()
	island.data = {"environment": {"sun": {"enabled": true}}}

	var leaves := StandardMaterial3D.new()
	leaves.resource_name = "foliage_amber"
	leaves.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	leaves.alpha_scissor_threshold = 0.4
	leaves.cull_mode = BaseMaterial3D.CULL_DISABLED
	var bark := StandardMaterial3D.new()
	bark.resource_name = "bark_oak"
	var atlas := StandardMaterial3D.new()
	atlas.resource_name = "Material_0"
	atlas.cull_mode = BaseMaterial3D.CULL_DISABLED
	atlas.roughness = 0.8
	var shrub_atlas := atlas.duplicate() as StandardMaterial3D
	var flower_atlas := atlas.duplicate() as StandardMaterial3D
	var litter_atlas := atlas.duplicate() as StandardMaterial3D
	var pine_colour := StandardMaterial3D.new()
	pine_colour.resource_name = "wind_pine"
	pine_colour.cull_mode = BaseMaterial3D.CULL_DISABLED
	pine_colour.vertex_color_use_as_albedo = true
	var ground := StandardMaterial3D.new()
	ground.resource_name = "foliage_amber"
	ground.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	ground.cull_mode = BaseMaterial3D.CULL_DISABLED
	var leaves_before := _properties(leaves)
	var atlas_before := _properties(atlas)

	var world := Node3D.new()
	world.name = "ImportedWorld_test__chunk_4_5"
	root.add_child(world)
	var canopy := _mesh(world, "Tree_0361_pale_birch_Canopy", leaves, Vector3(8, 6, 8), Vector3(-10, 30, 5))
	var wood := _mesh(world, "Tree_0361_pale_birch_Wood", bark, Vector3(1, 8, 1), Vector3(-10, 30, 5))
	var maple := _mesh(world, "kit-crimson-maple-3", atlas, Vector3(9, 9, 9), Vector3(20, 18, 40))
	var maple_twin := MeshInstance3D.new()
	maple_twin.name = "kit-crimson-maple-4"
	maple_twin.mesh = maple.mesh
	maple_twin.position = Vector3(-35, 17, 90)
	world.add_child(maple_twin)
	var shrub := _mesh(world, "kit-autumn-shrub-2", shrub_atlas, Vector3(2, 2, 2), Vector3(3, 18, 3))
	var flower := _mesh(world, "kit-flower-shrub-1", flower_atlas, Vector3(1, 1, 1), Vector3(4, 18, 4))
	var litter := _mesh(world, "kit-fallen-leaves-1", litter_atlas, Vector3(4, 0.1, 4), Vector3(5, 18, 5))
	var pines := _mesh(world, "Scenery_WindPines_12", pine_colour, Vector3(74, 4, 65), Vector3.ZERO)
	var merged := _mesh(world, "Grove_Merged_1", leaves, Vector3(60, 4, 50), Vector3.ZERO)
	var patch := _mesh(world, "AuthoredGround_test_ground-31_test_4_5", ground, Vector3(4, 0.2, 4), Vector3.ZERO)
	# A static batch of two firs: the members are hidden and the MultiMesh
	# draws them.
	var fir_atlas := atlas.duplicate() as StandardMaterial3D
	var fir_a := _mesh(world, "kit-dark-fir-1", fir_atlas, Vector3(5, 12, 5), Vector3(50, 20, 50))
	var fir_b := MeshInstance3D.new()
	fir_b.name = "kit-dark-fir-2"
	fir_b.mesh = fir_a.mesh
	world.add_child(fir_b)
	var batch := MultiMeshInstance3D.new()
	batch.name = "StaticBatch_0_kit-dark-fir-1"
	batch.multimesh = MultiMesh.new()
	batch.multimesh.transform_format = MultiMesh.TRANSFORM_3D
	batch.multimesh.mesh = fir_a.mesh
	batch.multimesh.instance_count = 2
	world.add_child(batch)
	for index: int in 2:
		var member: MeshInstance3D = [fir_a, fir_b][index]
		member.visible = false
		member.set_meta(LookFoliage.BATCH_META, batch)
		member.set_meta(LookFoliage.BATCH_INDEX_META, index)

	# Off: nothing changes, and OccluderFade blends as on develop.
	OS.set_environment(LookProfile.ENABLE_VARIABLE, "0")
	_expect(LookFoliage.paint_loaded(world, continent) == 0 and LookFoliage.paint(world) == 0,
		"with ELORIA_LOOK=0 nothing is painted")
	_expect(canopy.get_surface_override_material(0) == null
		and maple.get_surface_override_material(0) == null and batch.material_override == null,
		"with ELORIA_LOOK=0 the crowns keep the loader's materials")
	var off_fade := _fade_of(world, wood)
	off_fade.apply()
	var off_copy := wood.get_surface_override_material(0) as BaseMaterial3D
	_expect(off_copy != null and off_copy.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA
		and wood.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		and wood.get_child_count() == 0,
		"with ELORIA_LOOK=0 an occluder blends and keeps its own shadow, as on develop")
	off_fade.restore()
	_expect(wood.get_surface_override_material(0) == null, "and is put back after")
	_expect(_indexed(world) == _mesh_count(world),
		"with ELORIA_LOOK=0 every mesh is indexed as on develop, ground patches included")

	# On.
	OS.unset_environment(LookProfile.ENABLE_VARIABLE)
	_expect(LookFoliage.paint_loaded(world, island) == 0,
		"a map outside the continent is not painted")
	var painted_count := LookFoliage.paint_loaded(world, continent)
	var canopy_paint := canopy.get_surface_override_material(0) as ShaderMaterial
	var maple_paint := maple.get_surface_override_material(0) as ShaderMaterial
	_expect(canopy_paint != null and canopy_paint.shader == LookFoliage.SHADER_CUTOUT,
		"an authored canopy is painted with the alpha-cut shader")
	_expect(canopy_paint != null
		and is_equal_approx(float(canopy_paint.get_shader_parameter(&"alpha_scissor_threshold")), 0.4),
		"and keeps its cutout threshold")
	_expect(maple_paint != null and maple_paint.shader == LookFoliage.SHADER_OPAQUE,
		"a kit tree is painted with the opaque shader")
	_expect(wood.get_surface_override_material(0) == null,
		"a trunk is not painted")
	_expect(litter.get_surface_override_material(0) == null,
		"fallen leaves on the ground are not a crown")
	_expect(pines.get_surface_override_material(0) == null
		and merged.get_surface_override_material(0) == null,
		"a merged scatter mesh and a vertex-coloured one are left alone")
	_expect(patch.get_surface_override_material(0) == null,
		"ground is never painted as a crown, whatever its material")
	var maple_min: Vector3 = maple_paint.get_shader_parameter(&"look_crown_min")
	var canopy_min: Vector3 = canopy_paint.get_shader_parameter(&"look_crown_min")
	_expect(is_equal_approx(maple_min.y, 9.0 * LookProfile.CROWN_FLOOR)
		and is_equal_approx(canopy_min.y, 0.0),
		"a kit tree's crown starts at CROWN_FLOOR of its height, a canopy's at its foot")
	var shrub_paint := shrub.get_surface_override_material(0) as ShaderMaterial
	var flower_paint := flower.get_surface_override_material(0) as ShaderMaterial
	_expect(shrub_paint != null and is_equal_approx(
			(shrub_paint.get_shader_parameter(&"look_crown_min") as Vector3).y, 0.0)
		and float(shrub_paint.get_shader_parameter(&"look_tame")) == 1.0,
		"a shrub is crown from the ground up, and tamed")
	_expect(flower_paint != null and float(flower_paint.get_shader_parameter(&"look_tame")) == 0.0,
		"blossom keeps its hue")
	_expect(_properties(leaves) == leaves_before and _properties(atlas) == atlas_before
		and maple.mesh.surface_get_material(0) == atlas,
		"the source materials and meshes are never edited")
	_expect(canopy_paint.get_meta(LookFade.FADED_SHADER_META) == LookFoliage.SHADER_CUTOUT_FADED
		and maple_paint.get_meta(LookFade.FADED_SHADER_META) == LookFoliage.SHADER_OPAQUE_FADED,
		"every painted crown names its dithered variant")
	_expect(LookFoliage.paint(world) == 0 and canopy.get_surface_override_material(0) == canopy_paint,
		"painting a root twice changes nothing")
	_expect(painted_count == 7, "seven crown surfaces are painted (got %d)" % painted_count)

	# Seeds: from the position in the region, not the world, and in variants.
	var seed_a := LookFoliage.seed_of(maple, world)
	world.position = Vector3(1200, -40, -800)
	world.rotation = Vector3(0, 0.7, 0)
	_expect(is_equal_approx(LookFoliage.seed_of(maple, world), seed_a),
		"a crown's seed does not move when the world is rebased")
	world.transform = Transform3D.IDENTITY
	var maple_seed := float(maple_paint.get_shader_parameter(&"look_seed"))
	_expect(is_equal_approx(maple_seed * LookProfile.CROWN_JITTER_VARIANTS,
			roundf(maple_seed * LookProfile.CROWN_JITTER_VARIANTS)),
		"a crown's seed is one of CROWN_JITTER_VARIANTS")
	var twin_paint := maple_twin.get_surface_override_material(0) as ShaderMaterial
	_expect(twin_paint != null and (twin_paint == maple_paint) == is_equal_approx(
			float(twin_paint.get_shader_parameter(&"look_seed")), maple_seed),
		"copies of a kit tree share a material exactly when they share a seed")

	# Batches: the MultiMesh and its hidden members draw the same crown.
	var batch_paint := batch.material_override as ShaderMaterial
	var member_paint := fir_b.get_surface_override_material(0) as ShaderMaterial
	_expect(batch_paint != null and member_paint != null
		and batch_paint.shader == LookFoliage.SHADER_OPAQUE,
		"a batch of crowns and its members are painted")
	var batch_seed := float(batch_paint.get_shader_parameter(&"look_seed"))
	_expect(is_equal_approx(float(member_paint.get_shader_parameter(&"look_seed")),
			fposmod(batch_seed + LookFoliage.INSTANCE_SEED_STEP, 1.0)),
		"a member's seed is the one the batch's shader gives its instance")

	# The dithered fade.
	var fade := _fade_of(world, canopy)
	fade.apply()
	var faded := canopy.get_surface_override_material(0) as ShaderMaterial
	_expect(faded != null and faded != canopy_paint
		and faded.shader == LookFoliage.SHADER_CUTOUT_FADED,
		"a faded painted crown swaps to a copy with the dithered shader")
	_expect(faded != null and faded.get_shader_parameter(&"look_crown_max")
			== canopy_paint.get_shader_parameter(&"look_crown_max"),
		"and the copy keeps the crown's paint")
	_expect(canopy.get_node_or_null(NodePath(String(LookFade.SHADOW_TWIN_NAME))) == null
		and canopy.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF,
		"while a crown fades it casts no shadow and has no twin, as on develop")
	_expect(faded != null and is_zero_approx(float(faded.get_shader_parameter(&"look_fade_open")))
		and is_equal_approx(float(faded.get_shader_parameter(&"look_fade_hole_metres")),
			LookProfile.FADE_HOLE_METRES),
		"a fresh faded copy starts whole, with the profile's hole")
	LookFade.focus = Vector3(1.0, 2.0, 3.0)
	fade.fade = 1.0
	fade.write_alpha()
	_expect(is_equal_approx(float(faded.get_shader_parameter(&"look_fade")),
			OccluderFade.FADED_ALPHA)
		and is_equal_approx(float(faded.get_shader_parameter(&"look_fade_open")), 1.0)
		and faded.get_shader_parameter(&"look_fade_focus") == Vector3(1.0, 2.0, 3.0),
		"the fade opens the hole at the focus")
	_expect(is_equal_approx(float(canopy_paint.get_shader_parameter(&"look_fade")), 1.0)
		and canopy_paint.get_shader_parameter(&"look_fade_open") == null,
		"the shared painted material is never faded")
	fade.restore()
	_expect(canopy.get_surface_override_material(0) == canopy_paint
		and canopy.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		and canopy.get_node_or_null(NodePath(String(LookFade.SHADOW_TWIN_NAME))) == null,
		"restoring puts the painted crown and its own shadow back and drops the twin")

	# A StandardMaterial3D dithers through look_faded_standard.
	bark.normal_enabled = true
	bark.normal_scale = 0.7
	bark.roughness = 0.6
	bark.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_GREEN
	var wood_fade := _fade_of(world, wood)
	wood_fade.apply()
	var standard := wood.get_surface_override_material(0) as ShaderMaterial
	_expect(standard != null and standard.shader == LookFade.SHADER_STANDARD,
		"a faded one-sided StandardMaterial3D dithers through look_faded_standard")
	var wood_shadow := wood.get_node_or_null(NodePath(String(LookFade.SHADOW_TWIN_NAME))) as MeshInstance3D
	_expect(wood_shadow != null
		and wood_shadow.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
		and wood_shadow.get_surface_override_material(0) == null
		and wood.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_OFF,
		"while a wall or trunk fades a twin casts its resting shadow and it casts none")
	_expect(standard != null
		and is_equal_approx(float(standard.get_shader_parameter(&"normal_scale")), 0.7)
		and is_equal_approx(float(standard.get_shader_parameter(&"roughness_value")), 0.6)
		and standard.get_shader_parameter(&"roughness_channel") == Vector4(0, 1, 0, 0),
		"and carries the source's own properties")
	wood_fade.restore()
	_expect(wood.cast_shadow == GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		and wood.get_node_or_null(NodePath(String(LookFade.SHADOW_TWIN_NAME))) == null
		and not wood.has_meta(LookFade.SHADOW_META),
		"restoring gives the wall its own shadow back and drops the twin")
	var triplanar := StandardMaterial3D.new()
	triplanar.uv1_triplanar = true
	_expect(LookFade.dither_copy(triplanar) == null,
		"a material the stand-in cannot reproduce keeps develop's blend")
	var two_sided := StandardMaterial3D.new()
	two_sided.cull_mode = BaseMaterial3D.CULL_DISABLED
	two_sided.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
	var two_sided_copy := LookFade.dither_copy(two_sided)
	_expect(two_sided_copy != null and two_sided_copy.shader == LookFade.SHADER_STANDARD_TWO_SIDED
		and int(two_sided_copy.get_shader_parameter(&"alpha_mode")) == 1,
		"a two-sided alpha-cut one keeps both")
	var foreign := ShaderMaterial.new()
	foreign.shader = Shader.new()
	_expect(LookFade.dither_copy(foreign) == null,
		"any other ShaderMaterial stays solid, as on develop")

	# The ground is never an occluder with the pass on.
	_expect(_indexed(world) == _mesh_count(world) - 1,
		"with the look on (the default) a ground patch is kept out of the fade index")

	# A kit prop named for a plant is not a crown; a single-sided crown keeps
	# its culling.
	_expect(LookFoliage.kind_of("kit-reed-raft-3", atlas) == LookFoliage.Kind.NONE
		and LookFoliage.kind_of("kit-reed-bed-3", atlas) == LookFoliage.Kind.KIT_SHRUB,
		"a reed raft is a boat, not a shrub")
	var one_sided := atlas.duplicate() as StandardMaterial3D
	one_sided.cull_mode = BaseMaterial3D.CULL_BACK
	var one_sided_paint := LookFoliage.painted_for(one_sided, LookFoliage.Kind.KIT_TREE,
		_mesh(world, "kit-steppe-tree-1", one_sided, Vector3(3, 5, 3), Vector3.ZERO).mesh)
	_expect(one_sided_paint != null and one_sided_paint.shader == LookFoliage.SHADER_OPAQUE_BACK
		and one_sided_paint.get_meta(LookFade.FADED_SHADER_META) == LookFoliage.SHADER_OPAQUE_BACK_FADED,
		"a single-sided crown is painted back-face culled, and fades so")

	# Occluders blend as on develop on an interior, and when a hole could not
	# open most of them; a crown and a cottage keep the hole.
	var roof := _mesh(world, "Roof_giant_dome", bark, Vector3(40, 8, 40), Vector3(0, 20, 0))
	var cottage := _mesh(world, "Roof_cottage", bark, Vector3(10, 4, 8), Vector3(0, 10, 0))
	LookFade.bind(island)
	_expect(not LookFade.keeps_hole(roof) and LookFade.keeps_hole(cottage)
		and LookFade.keeps_hole(canopy) and LookFade.dither_copy(bark, roof) == null,
		"outdoors a giant dome blends; a cottage's roof and a crown keep the hole")
	var interior := WorldManifest.new()
	interior.data = {"environment": {"sun": {"enabled": false}}}
	LookFade.bind(interior)
	_expect(not LookFade.keeps_hole(cottage) and not LookFade.keeps_hole(canopy),
		"on an interior everything blends")
	var sunlit_inside := WorldManifest.new()
	sunlit_inside.data = {"asset": {"interiorClass": "gauntlet"},
		"environment": {"sun": {"enabled": true}}}
	LookFade.bind(sunlit_inside)
	_expect(LookFade.blend_only, "a sunlit interior (an interiorClass) blends too")
	LookFade.bind(island)

	world.queue_free()
	if previous.is_empty():
		OS.unset_environment(LookProfile.ENABLE_VARIABLE)
	else:
		OS.set_environment(LookProfile.ENABLE_VARIABLE, previous)
	print("test_look_foliage: %s (%d failures)" % ["PASS" if failures == 0 else "FAIL", failures])
	quit(1 if failures > 0 else 0)

## A box-shaped mesh of `size`, foot at its origin, placed at `at`.
func _mesh(parent: Node, node_name: String, material: Material, size: Vector3,
		at: Vector3) -> MeshInstance3D:
	var box := BoxMesh.new()
	box.size = size
	var tool := SurfaceTool.new()
	tool.create_from(box, 0)
	var arrays := tool.commit_to_arrays()
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	for index: int in vertices.size():
		vertices[index].y += size.y * 0.5
	arrays[Mesh.ARRAY_VERTEX] = vertices
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	mesh.surface_set_material(0, material)
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	node.position = at
	parent.add_child(node)
	return node

## The OccluderFade record for one node, as its index builds it.
func _fade_of(world: Node3D, node: MeshInstance3D) -> OccluderFade.Occluder:
	var fade := OccluderFade.new()
	fade.configure(null, world)
	for occluder: OccluderFade.Occluder in fade._occluders:
		if occluder.node == node:
			return occluder
	var record := OccluderFade.Occluder.new()
	record.node = node
	return record

func _indexed(world: Node3D) -> int:
	var fade := OccluderFade.new()
	return fade.configure(null, world)

## Meshes OccluderFade would weigh at all: visible and narrower than its cap.
func _mesh_count(world: Node3D) -> int:
	var count := 0
	for node: Node in world.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := node as MeshInstance3D
		if String(mesh_instance.name) == String(LookFade.SHADOW_TWIN_NAME):
			continue
		var box := mesh_instance.get_aabb()
		if maxf(box.size.x, box.size.z) <= OccluderFade.MAX_EXTENT_METRES:
			count += 1
	return count

func _properties(material: StandardMaterial3D) -> Array:
	return [material.albedo_color, material.transparency, material.cull_mode,
		material.roughness, material.alpha_scissor_threshold, material.get_meta_list()]

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS " + message)
	else:
		failures += 1
		print("FAIL " + message)
