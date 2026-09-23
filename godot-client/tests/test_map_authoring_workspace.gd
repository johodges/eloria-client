extends SceneTree

const Catalog := preload("res://addons/map_authoring_workspace/territory_catalog.gd")
const Preview := preload("res://addons/map_authoring_workspace/reference_preview.gd")
const Region := preload("res://src/dev/map_authoring_region/region_control.gd")

var failures := 0
var assertions := 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_catalog()
	_test_shared_anchor_frames()
	_test_relative_clipping()
	_test_preview_visibility_restore()
	_test_ownerless_host_is_not_serialized()
	_test_fail_closed_ownership()
	await _test_snapshot_and_palette_isolation()
	print("map authoring workspace: %d assertions, %d failures" % [assertions, failures])
	quit(1 if failures else 0)


func _test_catalog() -> void:
	var catalog := Catalog.new()
	var entries := catalog.entries()
	_expect(catalog.errors.is_empty(), "shared territory catalog validates")
	_expect(entries.size() == 12, "catalog covers all twelve exterior territories")
	var ids := PackedStringArray()
	var labels := PackedStringArray()
	var unique_ids := {}
	for entry in entries:
		ids.append(String(entry.id))
		unique_ids[String(entry.id)] = true
		labels.append(String(entry.label))
		var translation: Vector3 = entry.translation
		var ownership: PackedVector2Array = entry.ownership_polygon
		_expect(translation.is_finite(), "%s has a finite translation" % entry.id)
		_expect(ownership.size() >= 3,
			"%s has an ownership polygon" % entry.id)
		_expect(not String(entry.cache_key).is_empty(), "%s has a dependency cache key" % entry.id)
	_expect(ids.size() == unique_ids.size(), "territory IDs are unique")
	var sorted: Array[String] = []
	for label in labels:
		sorted.append(label)
	sorted.sort_custom(func(a: String, b: String) -> bool:
		return a.naturalnocasecmp_to(b) < 0)
	var original_labels: Array[String] = []
	for label in labels:
		original_labels.append(label)
	_expect(original_labels == sorted, "territories are sorted by label")
	var sunmane := catalog.find(entries, "sunmane_steppe")
	var amethyst := catalog.find(entries, "amethyst_barrens")
	_expect(not sunmane.is_empty() and String(sunmane.source_label) == "Saved authored source",
		"Sunmane is labeled as saved authored source")
	_expect(String(sunmane.source_error).is_empty(),
		"Sunmane scene root and authoring spec match their catalog registration")
	_expect("spec identity" in catalog._authored_error(String(sunmane.scene_path),
		String(sunmane.authoring_spec_path), String(sunmane.manifest_path),
		String(sunmane.id), "Wrong label"),
		"a mismatched authoring spec identity fails closed")
	_expect("spec paths" in catalog._authored_error(String(sunmane.scene_path),
		String(sunmane.authoring_spec_path),
		"res://../eloria-assets/maps/nymara-regions/amethyst_barrens/world.json",
		String(sunmane.id), String(sunmane.label)),
		"a spec registered to another manifest fails closed")
	var saved_scene := load(String(sunmane.scene_path)) as PackedScene
	var saved_root := saved_scene.instantiate(PackedScene.GEN_EDIT_STATE_DISABLED)
	_expect(catalog.active_scene_error(saved_root, sunmane).is_empty(),
		"the registered saved scene root is accepted as the active territory")
	var copied_root := Node3D.new()
	copied_root.set_script(saved_root.get_script())
	copied_root.set("region_id", String(sunmane.id))
	_expect("active scene path" in catalog.active_scene_error(copied_root, sunmane),
		"an unregistered scene copy with the same region ID fails closed")
	saved_root.free()
	copied_root.free()
	_expect(not amethyst.is_empty(), "Amethyst Barrens is catalogued")
	for entry in entries:
		if String(entry.id) not in ["sunmane_steppe", "amethyst_barrens"]:
			_expect(not bool(entry.editable) and String(entry.source_label) == \
				"Published reference only", "%s is reference-only" % entry.id)


func _test_shared_anchor_frames() -> void:
	var catalog := Catalog.new()
	var entries := catalog.entries()
	var sunmane := catalog.find(entries, "sunmane_steppe")
	var amethyst := catalog.find(entries, "amethyst_barrens")
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(
		String(amethyst.manifest_path)))
	var shared := {}
	for border: Dictionary in manifest.streamingBorders:
		if String(border.destination) == "sunmane_steppe":
			shared = border
			break
	_expect(not shared.is_empty(), "Amethyst manifest declares the Sunmane seam")
	var anchor := Vector3(float(shared.anchor[0]), float(shared.anchor[1]),
		float(shared.anchor[2]))
	var global_anchor := Vector3(float(shared.globalAnchor[0]),
		float(shared.globalAnchor[1]), float(shared.globalAnchor[2]))
	var amethyst_translation: Vector3 = amethyst.translation
	var sunmane_translation: Vector3 = sunmane.translation
	var in_sunmane := anchor + Preview.relative_translation(amethyst_translation,
		sunmane_translation)
	_expect(in_sunmane.is_equal_approx(global_anchor - sunmane_translation),
		"Amethyst seam anchor displays in the exact Sunmane-local frame")
	var back_in_amethyst := in_sunmane + Preview.relative_translation(
		sunmane_translation, amethyst_translation)
	_expect(back_in_amethyst.is_equal_approx(anchor),
		"switching active territory preserves the seam anchor and source height")


func _test_relative_clipping() -> void:
	var active := Node3D.new()
	root.add_child(active)
	var source := MeshInstance3D.new()
	active.add_child(source)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([
		Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(0, 0, 1),
		Vector3(10, 0, 10), Vector3(11, 0, 10), Vector3(10, 0, 11)])
	arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2, 3, 4, 5])
	var original := ArrayMesh.new()
	original.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	source.mesh = original
	var polygon := PackedVector2Array([
		Vector2(-1, -1), Vector2(2, -1), Vector2(2, 2), Vector2(-1, 2)])
	var clipped := Preview.clipped_mesh(source, active, polygon, Vector3.ZERO)
	_expect(clipped != null and clipped.get_surface_count() == 1,
		"ownership clipping emits the inside surface")
	var clipped_indices: PackedInt32Array = clipped.surface_get_arrays(0)[Mesh.ARRAY_INDEX]
	_expect(clipped_indices.size() == 3, "ownership clipping removes the outside triangle")
	var crossing_arrays := []
	crossing_arrays.resize(Mesh.ARRAY_MAX)
	crossing_arrays[Mesh.ARRAY_VERTEX] = PackedVector3Array([
		Vector3(-2, 0, 0), Vector3(1, 0, 0), Vector3(-2, 0, 1)])
	crossing_arrays[Mesh.ARRAY_NORMAL] = PackedVector3Array([Vector3.UP, Vector3.UP,
		Vector3.UP])
	crossing_arrays[Mesh.ARRAY_TANGENT] = PackedFloat32Array([
		1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1])
	crossing_arrays[Mesh.ARRAY_TEX_UV] = PackedVector2Array([
		Vector2(0, 0), Vector2(1, 0), Vector2(0, 1)])
	crossing_arrays[Mesh.ARRAY_COLOR] = PackedColorArray([Color.RED, Color.GREEN,
		Color.BLUE])
	crossing_arrays[Mesh.ARRAY_INDEX] = PackedInt32Array([0, 1, 2])
	var crossing_source := ArrayMesh.new()
	crossing_source.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, crossing_arrays)
	source.mesh = crossing_source
	var crossing := Preview.clipped_mesh(source, active, polygon, Vector3.ZERO)
	var result_arrays := crossing.surface_get_arrays(0)
	var result_vertices: PackedVector3Array = result_arrays[Mesh.ARRAY_VERTEX]
	var result_indices: PackedInt32Array = result_arrays[Mesh.ARRAY_INDEX]
	var result_tangents: PackedFloat32Array = result_arrays[Mesh.ARRAY_TANGENT]
	for index in result_indices:
		_expect(result_vertices[index].x >= -1.00001,
			"crossing triangles are cut at the ownership edge")
	_expect(result_tangents.size() == result_vertices.size() * 4,
		"clipped terrain preserves interpolated tangents")
	_expect((result_arrays[Mesh.ARRAY_NORMAL] as PackedVector3Array).size() == \
		result_vertices.size(), "clipped terrain preserves interpolated normals")
	_expect((result_arrays[Mesh.ARRAY_TEX_UV] as PackedVector2Array).size() == \
		result_vertices.size(), "clipped terrain preserves interpolated UVs")
	_expect((result_arrays[Mesh.ARRAY_COLOR] as PackedColorArray).size() == \
		result_vertices.size(), "clipped terrain preserves interpolated colors")
	var preview := Preview.new()
	active.add_child(preview)
	preview.active_root = active
	preview.active_entry = {"translation": Vector3.ZERO}
	var published := Node3D.new()
	preview.add_child(published)
	var published_terrain := MeshInstance3D.new()
	published_terrain.name = "Terrain_Test_00_00"
	published_terrain.mesh = crossing_source
	published_terrain.position.y = 7.0
	published.add_child(published_terrain)
	var published_water := MeshInstance3D.new()
	published_water.name = "Water_Test_00_00"
	published_water.mesh = crossing_source
	published_water.position.y = 8.0
	published.add_child(published_water)
	_expect(preview._add_published_owned_surfaces(published, {
		"ownership_polygon": polygon}),
		"published fallback terrain is clipped against ownership")
	_expect(not published_terrain.visible and \
			preview.get_node_or_null("Owned_Terrain_Test_00_00") != null,
		"published rectangular terrain is replaced by an ownerless clipped display")
	var published_heights := preview._published_height_map(published)
	_expect(is_equal_approx(float(published_heights.get(
		Preview._height_key(Vector2(-2, 0)), NAN)), 8.0),
		"published boundary sampling uses transformed terrain mesh height")
	var published_sampler := preview._published_height_sampler(published)
	_expect(is_equal_approx(Preview._sample_published_height(
		Vector2(-0.5, 0), published_sampler), 8.0),
		"published boundary interpolates water height inside a triangle without an exact vertex")
	_expect(is_nan(Preview._sample_published_height(Vector2(2, 2), published_sampler)),
		"published boundary reports a point outside every rendered triangle as uncovered")
	var boundary_coverage := preview._add_boundary(published, {"id": "published_test",
		"label": "Published test",
		"translation": Vector3.ZERO,
		"ownership_polygon": PackedVector2Array([
			Vector2(-2, 0), Vector2(1, 0), Vector2(-2, 1), Vector2(2, 2)])})
	var published_boundary := preview.get_node("OwnershipBoundary_published_test") \
		as MeshInstance3D
	var boundary_vertices: PackedVector3Array = \
		published_boundary.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]
	_expect(is_equal_approx(boundary_vertices[0].y, 8.15),
		"published ownership boundary is draped just above its rendered terrain edge")
	_expect(int(boundary_coverage.matched) >= 3 and int(boundary_coverage.missing) > 0,
		"published boundary reports real mesh samples and unavailable contour points")
	for vertex in boundary_vertices:
		_expect(is_equal_approx(vertex.y, 8.15),
			"unavailable boundary spans are omitted instead of falling back to flat Y")
	preview.clear()
	_expect(published_terrain.visible,
		"hiding published references restores their source terrain visibility")
	active.queue_free()


func _test_preview_visibility_restore() -> void:
	var preview := Preview.new()
	var visible_source := MeshInstance3D.new()
	visible_source.visible = true
	preview._hide_source(visible_source)
	preview.clear()
	_expect(visible_source.visible, "hide restores an originally visible active preview")
	var hidden_source := MeshInstance3D.new()
	hidden_source.visible = false
	preview._hide_source(hidden_source)
	preview.clear()
	_expect(not hidden_source.visible, "hide preserves an originally hidden active preview")
	visible_source.free()
	hidden_source.free()
	preview.free()


func _test_ownerless_host_is_not_serialized() -> void:
	var authored := Node3D.new()
	authored.name = "Authored"
	var saved := Node3D.new()
	saved.name = "SavedControl"
	authored.add_child(saved)
	saved.owner = authored
	var host := Preview.new()
	authored.add_child(host, false, Node.INTERNAL_MODE_FRONT)
	host.name = Preview.HOST_NAME
	_expect(host.owner == null, "reference host is ownerless")
	var packed := PackedScene.new()
	_expect(packed.pack(authored) == OK, "authored scene packs with an editor reference host")
	var restored := packed.instantiate()
	_expect(restored.get_node_or_null("SavedControl") != null, "saved controls remain packed")
	_expect(restored.get_node_or_null(Preview.HOST_NAME) == null,
		"reference host is absent from packed scene bytes")
	restored.free()
	authored.free()


func _test_fail_closed_ownership() -> void:
	var region := Region.new()
	region.region_id = "sunmane_steppe"
	region.ownership_polygon_sha256 = "a".repeat(64)
	var preview := Preview.new()
	var error := preview._validate_authored(region, {
		"id": "sunmane_steppe", "label": "Sunmane Steppe",
		"ownership_sha256": "b".repeat(64)})
	_expect("ownership polygon" in error, "mismatched ownership hides authored references")
	region.free()
	preview.free()


func _test_snapshot_and_palette_isolation() -> void:
	var packed := load("res://world_authoring/regions/sunmane_steppe/sunmane_steppe.tscn") \
		as PackedScene
	var region := packed.instantiate(PackedScene.GEN_EDIT_STATE_DISABLED) as Node3D
	root.add_child(region)
	await process_frame
	var output_root := "res://test-artifacts/map-authoring-workspace"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output_root))
	var before: Dictionary = region.call("export_snapshot",
		output_root.path_join("before/continent-authoring.json"))
	var before_hit: Variant = region.call("authoring_ground_intersection",
		Vector3(0, 500, 0), Vector3.DOWN, 1000.0)
	var host := Preview.new()
	region.add_child(host, false, Node.INTERNAL_MODE_FRONT)
	var reference := Node3D.new()
	reference.name = "ReadOnlyReference"
	host.add_child(reference, false, Node.INTERNAL_MODE_FRONT)
	var fake_ground := MeshInstance3D.new()
	fake_ground.position = Vector3(0, 400, 0)
	reference.add_child(fake_ground, false, Node.INTERNAL_MODE_FRONT)
	var after_hit: Variant = region.call("authoring_ground_intersection",
		Vector3(0, 500, 0), Vector3.DOWN, 1000.0)
	var after: Dictionary = region.call("export_snapshot",
		output_root.path_join("after/continent-authoring.json"))
	_expect(not before.is_empty() and before == after,
		"ownerless references cannot change active bake records or dependency hashes")
	_expect(before_hit is Vector3 and after_hit is Vector3 and \
		(before_hit as Vector3).is_equal_approx(after_hit as Vector3),
		"active ground intersection ignores reference geometry used by palette placement")
	_expect(not region.is_editable_instance(host),
		"reference host is not an editable scene instance")
	host.clear()
	region.remove_child(host)
	host.free()
	region.queue_free()
	await process_frame


func _expect(condition: bool, message: String) -> void:
	assertions += 1
	if condition:
		return
	failures += 1
	push_error("FAIL: " + message)
