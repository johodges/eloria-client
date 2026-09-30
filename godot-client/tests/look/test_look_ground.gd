extends SceneTree
## Guards the look pass's painted ground (layer L2).
##
## With ELORIA_LOOK unset the ground must be exactly what the loader built.
## With it on, only ground is painted, one painted material is shared by every
## mesh that used a source material, the source materials and meshes are never
## edited (a map cache is packed from them), and painting twice is harmless:
## a chunk can be finished by the loader and then seen again.

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
	var interior := WorldManifest.new()
	interior.data = {"environment": {"sun": {"enabled": false}}}

	var terrain_material := StandardMaterial3D.new()
	terrain_material.vertex_color_use_as_albedo = true
	var patch_material := StandardMaterial3D.new()
	patch_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	patch_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	patch_material.albedo_color = Color("ffa85c")
	var deck_material := StandardMaterial3D.new()
	deck_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	deck_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	deck_material.albedo_color = Color("997a4f")
	var threshold_material := deck_material.duplicate() as StandardMaterial3D
	threshold_material.albedo_color = Color(0, 0, 0, 0)
	var bridge_material := StandardMaterial3D.new()
	var water_material := StandardMaterial3D.new()
	var tree_material := StandardMaterial3D.new()
	var biome_material := ShaderMaterial.new()
	biome_material.shader = load(LookGround.BIOME_SHADER_PATH) as Shader
	biome_material.set_shader_parameter(&"mask_size", 66.0)
	biome_material.set_shader_parameter(&"base_tint_0", Color("b3eb80"))
	biome_material.set_shader_parameter(&"mask_metres_per_pixel", 1.5)

	var world := Node3D.new()
	world.name = "ImportedWorld_test"
	root.add_child(world)
	var terrain_a := _mesh(world, "Terrain_test_4_5", terrain_material)
	var terrain_b := _mesh(world, "Terrain_test_4_6", terrain_material)
	var biome := _mesh(world, "AuthoredGround_testBase_4_5", null)
	biome.set_surface_override_material(0, biome_material)
	var patch := _mesh(world, "AuthoredGround_test_ground-03_test_4_5", patch_material)
	var deck := _mesh(world, "Walk_test_highway-test-south_test_4_5", deck_material)
	var threshold := _mesh(world, "Walk__StreamThreshold_test--other", threshold_material)
	var bridge := _mesh(world, "Walk_ContinentalBridgeUnion_002_test", bridge_material, false)
	var water := _mesh(world, "Water_test_4_5", water_material)
	var tree := _mesh(world, "Tree_0361_pale_birch_Canopy", tree_material)
	var batched := _mesh(world, "Terrain_test_batched", terrain_material)
	batched.set_meta(LookGround.BATCH_META, NodePath("StaticBatch_0_Terrain"))
	var sources := {}
	for node: MeshInstance3D in [terrain_a, terrain_b, biome, patch, deck, threshold,
			bridge, water, tree, batched]:
		sources[node] = node.mesh.surface_get_material(0)
	var terrain_before := _properties(terrain_material)

	# Off: nothing changes.
	OS.set_environment(LookProfile.ENABLE_VARIABLE, "0")
	_expect(LookGround.paint_loaded(world, continent) == 0
		and LookGround.paint_bound(world, island) == 0 and LookGround.paint(world) == 0,
		"with ELORIA_LOOK=0 every entry point paints nothing")
	_expect(terrain_a.get_surface_override_material(0) == null
		and biome.get_surface_override_material(0) == biome_material,
		"with ELORIA_LOOK=0 the ground keeps the loader's materials")

	# On: the entry points keep to their own maps.
	OS.set_environment(LookProfile.ENABLE_VARIABLE, "1")
	_expect(LookGround.paint_loaded(world, island) == 0,
		"the loader leaves a map outside the continent to the bind")
	_expect(LookGround.paint_bound(world, continent) == 0,
		"the bind leaves continent maps to the loader")
	_expect(LookGround.paint_bound(world, interior) == 0,
		"an interior is never painted")
	var painted := LookGround.paint_loaded(world, continent)
	_expect(painted == 5, "five ground surfaces are painted (got %d)" % painted)

	var terrain_paint := terrain_a.get_surface_override_material(0) as ShaderMaterial
	_expect(terrain_paint != null and terrain_paint.shader == LookGround.SHADER_OPAQUE,
		"the terrain is painted with the opaque culled shader")
	_expect(terrain_b.get_surface_override_material(0) == terrain_paint,
		"meshes that shared a source material share one painted material")
	_expect(terrain_paint != null
		and bool(terrain_paint.get_shader_parameter(&"use_vertex_albedo"))
		and float(terrain_paint.get_shader_parameter(&"look_road_detect")) == 1.0,
		"the terrain keeps its vertex colour and looks in it for worn roads")
	var patch_paint := patch.get_surface_override_material(0) as ShaderMaterial
	_expect(patch_paint != null and patch_paint.shader == LookGround.SHADER_OVERLAY
		and bool(patch_paint.get_shader_parameter(&"use_vertex_alpha"))
		and float(patch_paint.get_shader_parameter(&"look_yard")) == 1.0
		and patch_paint.get_shader_parameter(&"albedo_color") == Color("ffa85c"),
		"a patch keeps its tint, is feathered by vertex alpha and lifted as a yard")
	var deck_paint := deck.get_surface_override_material(0) as ShaderMaterial
	_expect(deck_paint != null
		and float(deck_paint.get_shader_parameter(&"look_path_force")) == 1.0,
		"a walk deck is painted as a path")
	var biome_paint := biome.get_surface_override_material(0) as ShaderMaterial
	_expect(biome_paint != null and biome_paint != biome_material
		and biome_paint.shader != biome_material.shader
		and biome_paint.shader.code.contains("look_paint(")
		and is_equal_approx(float(biome_paint.get_shader_parameter(&"mask_size")), 66.0)
		and biome_paint.get_shader_parameter(&"base_tint_0") == Color("b3eb80"),
		"the biome blend is painted through its own spliced copy, parameters intact")
	_expect(threshold.get_surface_override_material(0) == null
		and bridge.get_surface_override_material(0) == null
		and water.get_surface_override_material(0) == null
		and tree.get_surface_override_material(0) == null
		and batched.get_surface_override_material(0) == null,
		"thresholds, bridge timber, water, trees and batched meshes are left alone")
	var untouched := true
	for node: MeshInstance3D in sources:
		untouched = untouched and node.mesh.surface_get_material(0) == sources[node]
	_expect(untouched and _properties(terrain_material) == terrain_before,
		"source materials and meshes are never edited, only overridden")

	var overrides: Array = []
	for node: MeshInstance3D in [terrain_a, terrain_b, biome, patch, deck]:
		overrides.append(node.get_surface_override_material(0))
	_expect(LookGround.paint(world) == 0, "painting a painted root again paints nothing")
	var same := true
	for index: int in overrides.size():
		var node: MeshInstance3D = [terrain_a, terrain_b, biome, patch, deck][index]
		same = same and node.get_surface_override_material(0) == overrides[index]
	_expect(same, "and leaves the painted materials in place")

	# An island map is painted at bind, with its scene's vertex colour.
	var island_root := Node3D.new()
	root.add_child(island_root)
	var island_material := StandardMaterial3D.new()
	island_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	island_material.vertex_color_use_as_albedo = true
	var island_ground := _mesh(island_root, "Walk_Terrain_0", island_material)
	_expect(LookGround.paint_bound(island_root, island) == 1
		and (island_ground.get_surface_override_material(0) as ShaderMaterial).shader
			== LookGround.SHADER_TWO_SIDED,
		"an island's two-sided ground is painted at bind with the two-sided shader")

	OS.set_environment(LookProfile.ENABLE_VARIABLE, previous)
	print("test_look_ground: %s (%d failures)" % [
		"PASS" if failures == 0 else "FAIL", failures])
	quit(1 if failures > 0 else 0)

func _mesh(parent: Node, node_name: String, material: Material,
		coloured := true) -> MeshInstance3D:
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	for corner: Vector3 in [Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1)]:
		if coloured:
			tool.set_color(Color(1, 1, 1, 0.5))
		tool.set_normal(Vector3.UP)
		tool.set_uv(Vector2(corner.x, corner.z))
		tool.add_vertex(corner)
	var mesh := tool.commit()
	if material != null:
		mesh.surface_set_material(0, material)
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	parent.add_child(node)
	return node

func _properties(material: StandardMaterial3D) -> Array:
	return [material.albedo_color, material.vertex_color_use_as_albedo,
		material.transparency, material.cull_mode, material.roughness,
		material.get_meta_list()]

func _expect(condition: bool, message: String) -> void:
	if condition:
		print("PASS " + message)
	else:
		failures += 1
		print("FAIL " + message)
