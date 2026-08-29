extends SceneTree

## Known-answer checks for OccluderFade against a hand-built world.
##
## The camera sits above and behind the player, so the segment between them runs
## through a fixed point. A box parked on that point must fade, a box beside it
## must not, ground must never fade at all, and everything must come back
## exactly as it was found - including a prop the loader had collapsed into a
## MultiMesh, which has to be lifted out for the fade and handed back after.
##
## Run: Godot_v4.7.2-stable_win64.exe --headless --path . \
##         --script tests/test_occluder_fade.gd

# Preloaded rather than reached by class name: the global class cache is a
# build artifact, and a working copy that has not been opened in the editor
# since this file was added does not carry OccluderFade in it yet.
const OccluderFadeScript := preload("res://src/world/occluder_fade.gd")

const PLAYER_POSITION := Vector3.ZERO
const CAMERA_POSITION := Vector3(0.0, 10.0, 10.0)
## On the segment from the camera to the player's chest, roughly half way.
const ON_THE_LINE := Vector3(0.0, 5.5, 5.0)
const OFF_TO_THE_SIDE := Vector3(20.0, 5.5, 5.0)
## Long enough that a fade of FADE_SECONDS finishes inside one step.
const SETTLE := 0.5

var failures: int = 0

var world: Node3D
var camera: Camera3D
var player: Node3D
var blocker: MeshInstance3D
var aside: MeshInstance3D
var ground: MeshInstance3D
var batched: MeshInstance3D
var batch: MultiMeshInstance3D

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	_build_world()
	await process_frame

	var fade: RefCounted = OccluderFadeScript.new()
	var indexed: int = fade.configure(null, world)
	_expect(indexed == 3,
		"blocker, aside and the batched prop index; the walk surface does not")

	# Disabled: the probe runs but marks nothing.
	fade.update(SETTLE, camera, player)
	_expect(blocker.get_surface_override_material(0) == null,
		"nothing fades while the setting is off")

	fade.set_enabled(true)
	fade.update(SETTLE, camera, player)

	var faded: Material = blocker.get_surface_override_material(0)
	_expect(faded is BaseMaterial3D,
		"an obstacle on the sight line takes a faded material of its own")
	if faded is BaseMaterial3D:
		var material: BaseMaterial3D = faded as BaseMaterial3D
		_expect(material.transparency == BaseMaterial3D.TRANSPARENCY_ALPHA,
			"the faded material blends instead of writing depth")
		_expect(is_equal_approx(material.albedo_color.a, OccluderFadeScript.FADED_ALPHA),
			"the fade settles at FADED_ALPHA")
		_expect(material != blocker.mesh.surface_get_material(0),
			"the shared imported material is duplicated, not edited")
	_expect(is_equal_approx(blocker.mesh.surface_get_material(0).albedo_color.a, 1.0),
		"the material the mesh still shares with every other copy stays opaque")

	_expect(aside.get_surface_override_material(0) == null,
		"an obstacle beside the sight line is left alone")
	_expect(ground.get_surface_override_material(0) == null,
		"the walk surface under the player never fades")

	_expect(batched.visible and batched.get_surface_override_material(0) != null,
		"a batched prop on the sight line is lifted out of the batch to fade")
	if _multimesh_stores_transforms():
		_expect(batch.multimesh.get_instance_transform(0).basis.determinant() == 0.0,
			"the batch stops drawing the instance that was lifted out")

	# Walking clear of the obstacles: everything blends back and is handed back.
	player.global_position = Vector3(0.0, 0.0, 60.0)
	camera.global_position = Vector3(0.0, 10.0, 70.0)
	await process_frame
	fade.update(SETTLE, camera, player)
	_expect(blocker.get_surface_override_material(0) == null,
		"an obstacle that clears the sight line gets its own material back")
	_expect(not batched.visible
			and batched.get_surface_override_material(0) == null,
		"the lifted prop is handed back to the batch")
	if _multimesh_stores_transforms():
		_expect(batch.multimesh.get_instance_transform(0).origin.is_equal_approx(
				ON_THE_LINE),
			"the batch draws the returned instance where it always stood")

	# A map change frees the world while obstacles are still faded.
	player.global_position = PLAYER_POSITION
	camera.global_position = CAMERA_POSITION
	await process_frame
	fade.update(SETTLE, camera, player)
	_expect(blocker.get_surface_override_material(0) != null, "faded again")
	fade.reset()
	_expect(blocker.get_surface_override_material(0) == null,
		"reset restores every obstacle it was holding")
	_expect(fade.configure(null, null) == 0, "a world that failed to load indexes nothing")

	print("occluder fade tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	world.queue_free()
	await process_frame
	quit(failures)

## A miniature of what the world loader leaves behind: loose meshes, a walk
## surface carrying navigation collision, and one prop collapsed into a batch
## with its source node hidden and stamped.
func _build_world() -> void:
	world = Node3D.new()
	world.name = "ImportedWorld_test"
	root.add_child(world)

	camera = Camera3D.new()
	camera.position = CAMERA_POSITION
	world.add_child(camera)

	player = Node3D.new()
	player.position = PLAYER_POSITION
	world.add_child(player)

	blocker = _box("Blocker", ON_THE_LINE)
	aside = _box("Aside", OFF_TO_THE_SIDE)

	ground = _box("Terrain_Ground", ON_THE_LINE)
	var body := StaticBody3D.new()
	body.collision_layer = WorldLoader.NAVIGATION_SURFACE_LAYER
	ground.add_child(body)

	batched = _box("BatchedProp", ON_THE_LINE)
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.mesh = batched.mesh
	multimesh.instance_count = 1
	multimesh.set_instance_transform(0, batched.transform)
	batch = MultiMeshInstance3D.new()
	batch.name = "StaticBatch_0_BatchedProp"
	batch.multimesh = multimesh
	world.add_child(batch)
	batched.visible = false
	batched.set_meta(WorldLoader.BATCH_META, batch)
	batched.set_meta(WorldLoader.BATCH_INDEX_META, 0)

func _box(node_name: String, position: Vector3) -> MeshInstance3D:
	var mesh := BoxMesh.new()
	mesh.size = Vector3(2.0, 2.0, 2.0)
	mesh.material = StandardMaterial3D.new()
	var node := MeshInstance3D.new()
	node.name = node_name
	node.mesh = mesh
	node.position = position
	world.add_child(node)
	return node

## Whether the running rendering server keeps MultiMesh instance transforms at
## all. Godot's headless server is a stub that accepts every write and reports
## identity back, so under --headless the two assertions about what the batch
## draws would be testing the stub rather than this client. The node-side half
## of the same behaviour - hidden, lifted, hidden again - is observable either
## way, and is asserted unconditionally.
func _multimesh_stores_transforms() -> bool:
	var probe := MultiMesh.new()
	probe.transform_format = MultiMesh.TRANSFORM_3D
	probe.mesh = BoxMesh.new()
	probe.instance_count = 1
	var written := Transform3D(Basis(), Vector3(1.0, 2.0, 3.0))
	probe.set_instance_transform(0, written)
	return probe.get_instance_transform(0).origin.is_equal_approx(written.origin)

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
