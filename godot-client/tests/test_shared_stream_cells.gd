extends SceneTree

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _expect(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)

func _surface(parent: Node3D, title: String, z: float, depth: float, y := 0.0) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = title
	var box := BoxMesh.new()
	box.size = Vector3(20, .02, depth)
	mesh.mesh = box
	mesh.position = Vector3(0, y, z)
	parent.add_child(mesh)
	var body := StaticBody3D.new()
	body.collision_layer = WorldLoader.NAVIGATION_SURFACE_LAYER
	mesh.add_child(body)
	var shape := CollisionShape3D.new()
	var bounds := BoxShape3D.new()
	bounds.size = box.size
	shape.shape = bounds
	body.add_child(shape)
	return mesh

func _manifest(identity: String, outward: Array) -> WorldManifest:
	var result := WorldManifest.new()
	result.data = {"asset": {"id": identity, "serverCells": 64},
		"coordinateTransform": {"serverOrigin": [10,10], "serverCells": [64,64]},
		"streamingBorders": [{"id": "test-road", "anchor": [0,0,0], "outward": outward,
			"geometryMode": "shared-cells-v2", "sceneNodes": ["Terrain_Approach"]}]}
	return result

func _run() -> void:
	var stage := Node3D.new()
	root.add_child(stage)
	var loader := WorldLoader.new()
	stage.add_child(loader)
	var near_manifest := _manifest("amberwood", [0,-1])
	var far_manifest := _manifest("whitehorn_range", [0,1])
	var near := Node3D.new()
	stage.add_child(near)
	_surface(near,"Terrain_Approach",10,20)
	_surface(near,"Terrain_Core",30,20)
	var threshold := _surface(near,"Walk_StreamThreshold_test-road",-1,2,.5)
	loader.world_root = near
	loader.manifest = near_manifest
	loader._group_streaming_views()
	_expect(not threshold.visible, "source threshold supports the trigger without drawing duplicate scenery")
	var far := Node3D.new()
	stage.add_child(far)
	var actual := _surface(far,"Terrain_Approach",-10,20)
	var far_core := _surface(far,"Terrain_Core",-30,20)
	var original_id := actual.get_instance_id()
	loader.world_root = far
	loader.manifest = far_manifest
	loader._group_streaming_views()
	var stream := ExteriorRegionStream.new()
	stage.add_child(stream)
	stream.links = [{"seamless": true, "ends": [
		{"map":"amberwood", "position":[0,0,-1], "frame":near_manifest.data.streamingBorders[0]},
		{"map":"whitehorn_range", "position":[0,0,1], "frame":far_manifest.data.streamingBorders[0]}]}]
	stream.residents["whitehorn_range"] = {"root":far,"manifest":far_manifest}
	stream.activate("amberwood",near,near_manifest)
	await physics_frame
	await physics_frame
	_expect(actual.is_visible_in_tree() and not far_core.is_visible_in_tree(), "resident exposes its actual shared approach")
	_expect(far.find_children("Terrain_Approach", "MeshInstance3D", true, false).size() == 1, "approach has one node, not a preview copy")
	var space := stage.get_world_3d().direct_space_state
	for depth: float in [1.1,12.1]:
		var target: Variant = stream.pick_neighbor(space,Vector3(0,20,-depth),Vector3.DOWN,true)
		_expect(target is Vector3, "visible neighbor target accepts a click at depth %s" % depth)
		_expect(stream.pending_walk.get("map") == "whitehorn_range", "click keeps the destination map")
		_expect(stream.pending_walk.get("tile") == Vector2i(10,floori(10+depth)), "click keeps the destination's tile frame")
		_expect(stream.pending_walk.get("run") == true, "shift-click preserves run intent")
	far_manifest.data.coordinateTransform.serverCells = [1,1]
	_expect(stream.pick_neighbor(space,Vector3(0,20,-10),Vector3.DOWN,false) == null, "rendered margins outside served bounds are rejected")
	_expect(stream.pending_walk.is_empty(), "rejected click cannot leave a stale continuation")
	far_manifest.data.coordinateTransform.serverCells = [64,64]
	stream.pick_neighbor(space,Vector3(0,20,-12.1),Vector3.DOWN,false)
	var continuation := stream.take_continuation("whitehorn_range")
	_expect(continuation.tile == Vector2i(10,22) and stream.pending_walk.is_empty(), "crossing consumes the exact target once")
	ExteriorRegionStream._set_view(far)
	ExteriorRegionStream._set_collision(far,true)
	_expect(actual.get_instance_id() == original_id and actual.is_visible_in_tree(), "adoption keeps the same visible authored node")
	_expect((actual.get_child(0) as StaticBody3D).collision_layer == WorldLoader.NAVIGATION_SURFACE_LAYER, "adoption changes physics ownership")
	stream.residents.clear()
	loader.world_root = null
	stage.queue_free()
	await process_frame
	print("shared stream cells: ", "PASS" if failures == 0 else "FAIL")
	quit(failures)
