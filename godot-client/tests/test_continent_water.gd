extends SceneTree

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _expect(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _water(parent: Node3D, name_value: String, at: Vector3) -> MeshInstance3D:
	var node := MeshInstance3D.new()
	node.name = name_value
	var plane := PlaneMesh.new()
	plane.material = StandardMaterial3D.new()
	node.mesh = plane
	node.position = at
	parent.add_child(node)
	return node

func _loader(origin: Vector3) -> WorldLoader:
	var loader := WorldLoader.new()
	root.add_child(loader)
	loader.world_root = Node3D.new()
	loader.add_child(loader.world_root)
	loader.manifest = WorldManifest.new()
	loader.manifest.data = {"continentGeography": {}, "streamingBorders": [
		{"globalTranslation": [origin.x, origin.y, origin.z]}]}
	return loader

func _run() -> void:
	var west := _loader(Vector3(618, 0, 1490))
	var group := Node3D.new()
	group.position = Vector3(12, 0, -4)
	west.world_root.add_child(group)
	var water := _water(group, "Water_Delta", Vector3(30, 0, 20))
	var pond := _water(group, "Water_RaisedPond", Vector3(0, 5, 0))
	var floor := _water(group, "Terrain_Floor", Vector3.ZERO)
	_expect(west._apply_continent_water([water, pond, floor]) == 1,
		"Only sea-level water changes; raised ponds and ground retain their authored materials")
	var material := water.get_surface_override_material(0) as ShaderMaterial
	_expect(bool(material.get_shader_parameter("has_wave_texture"))
		and material.get_shader_parameter("wave_texture") is Texture2D,
		"A region without a packaged water_lake material still loads the shared texture")
	var transform: Transform3D = material.get_shader_parameter("water_to_continent")
	_expect((transform * Vector3.ZERO).is_equal_approx(Vector3(660, 0, 1506)),
		"Nested local placement contributes to the continent water coordinates")
	var east := _loader(Vector3(1144, 0, 1500))
	var peer := _water(east.world_root, "Water_Basin", Vector3(-484, 0, 6))
	east._apply_continent_water([peer])
	var peer_transform: Transform3D = (peer.get_surface_override_material(0) as ShaderMaterial).get_shader_parameter("water_to_continent")
	_expect(transform.is_equal_approx(peer_transform), "Both map frames sample the same water at a shared physical point")
	west.world_root.position = Vector3(-526, 0, -10)
	_expect(transform == material.get_shader_parameter("water_to_continent"),
		"A seamless scene rebase does not move the ripple phase")
	var packed := PackedScene.new()
	group.owner = west.world_root
	water.owner = west.world_root
	pond.owner = west.world_root
	floor.owner = west.world_root
	_expect(packed.pack(west.world_root) == OK, "Water overrides can be cached")
	var restored := packed.instantiate() as Node3D
	var restored_material := (restored.get_node(NodePath(str(group.name) + "/Water_Delta")) as MeshInstance3D).get_surface_override_material(0) as ShaderMaterial
	_expect(restored_material != null and restored_material.get_shader_parameter("water_to_continent") == transform,
		"Cached water retains the same continent transform")
	restored.free()
	west.free()
	east.free()
	print("continent water: ", "PASS" if failures == 0 else "FAIL")
	quit(0 if failures == 0 else 1)
