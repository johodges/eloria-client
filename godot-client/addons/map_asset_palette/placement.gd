@tool
extends RefCounted

const CONTAINER_NAME := "AuthoredAssets"
const MIN_AUTO_SCALE := 0.05
const MAX_AUTO_SCALE := 20.0


static func instantiate_entry(entry: Dictionary) -> Dictionary:
	var scene_path := String(entry.get("scene_path", ""))
	var source_node := String(entry.get("source_node", ""))
	var packed := load(scene_path) as PackedScene
	if packed == null:
		return {"error": "Could not load %s." % scene_path}
	var result: Node3D
	var is_starter := not source_node.is_empty()
	if is_starter:
		var template := packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE)
		if template == null:
			return {"error": "Could not open starter scene %s." % scene_path}
		var source := template.get_node_or_null(NodePath(source_node))
		if source is Node3D:
			result = source.duplicate() as Node3D
		template.free()
		if result == null:
			return {"error": "Starter node %s is missing." % source_node}
	else:
		result = packed.instantiate(PackedScene.GEN_EDIT_STATE_INSTANCE) as Node3D
		if result == null:
			return {"error": "%s does not have a Node3D root." % scene_path}
	result.name = _safe_node_name(String(entry.get("label", result.name)))
	result.set_meta(&"map_asset_id", String(entry.get("id", "")))
	result.set_meta(&"map_asset_scene", scene_path)
	if is_starter:
		result.set_meta(&"map_asset_source_node", source_node)
	return {"node": result, "starter": is_starter}


static func ground_transform(node: Node3D, entry: Dictionary,
		ground_position: Vector3) -> Transform3D:
	var transform := Transform3D(node.transform.basis, ground_position)
	var bounds_result := mesh_bounds(node)
	if not bool(bounds_result.get("valid", false)):
		return transform
	var local_bounds: AABB = bounds_result.bounds
	var oriented := Transform3D(transform.basis, Vector3.ZERO) * local_bounds
	var desired_height := float(entry.get("height", 0.0))
	if String(entry.get("source_node", "")).is_empty() and desired_height > 0.0 and \
			oriented.size.y > 0.0001:
		var factor := desired_height / oriented.size.y
		if is_finite(factor) and factor >= MIN_AUTO_SCALE and factor <= MAX_AUTO_SCALE:
			transform.basis = transform.basis.scaled(Vector3.ONE * factor)
		else:
			push_warning(("Map asset '%s' kept its authored scale because the catalog height " +
				"would require an unsafe scale factor.") % String(entry.get("label", node.name)))
		oriented = Transform3D(transform.basis, Vector3.ZERO) * local_bounds
	transform.origin.y = ground_position.y - oriented.position.y
	return transform


static func mesh_bounds(root: Node3D) -> Dictionary:
	var state := {"valid": false, "bounds": AABB()}
	_collect_mesh_bounds(root, Transform3D.IDENTITY, true, state)
	return state


static func commit_with_undo(undo_redo: EditorUndoRedoManager, scene_root: Node,
		entry: Dictionary, node: Node3D, starter: bool,
		world_transform: Transform3D) -> Node3D:
	if undo_redo == null or scene_root == null or node == null:
		return null
	var container := scene_root.get_node_or_null(NodePath(CONTAINER_NAME)) as Node3D
	var new_container := false
	if container == null:
		if scene_root.has_node(NodePath(CONTAINER_NAME)):
			push_warning("Map Assets needs '%s' to be a Node3D." % CONTAINER_NAME)
			return null
		container = Node3D.new()
		container.name = CONTAINER_NAME
		new_container = true
	var label := String(entry.get("label", node.name))
	undo_redo.create_action("Place %s" % label, UndoRedo.MERGE_DISABLE, scene_root)
	if new_container:
		undo_redo.add_do_method(scene_root, &"add_child", container, true)
		undo_redo.add_do_method(container, &"set_owner", scene_root)
		undo_redo.add_do_reference(container)
	undo_redo.add_do_method(container, &"add_child", node, true)
	undo_redo.add_do_method(node, &"set_owner", scene_root)
	if starter:
		for descendant in _descendants(node):
			undo_redo.add_do_method(descendant, &"set_owner", scene_root)
	undo_redo.add_do_property(node, &"global_transform", world_transform)
	undo_redo.add_do_reference(node)
	undo_redo.add_undo_method(container, &"remove_child", node)
	if new_container:
		undo_redo.add_undo_method(scene_root, &"remove_child", container)
	undo_redo.commit_action()
	return node


static func preview_scene(entry: Dictionary) -> PackedScene:
	var created := instantiate_entry(entry)
	var node := created.get("node") as Node3D
	if node == null:
		return null
	for descendant in _descendants(node):
		descendant.owner = node
	var packed := PackedScene.new()
	var error := packed.pack(node)
	node.free()
	return packed if error == OK else null


static func _collect_mesh_bounds(node: Node, relative: Transform3D,
		ancestors_visible: bool, state: Dictionary) -> void:
	var here := relative
	var visible := ancestors_visible
	if node is Node3D:
		visible = visible and (node as Node3D).visible
	if node is MeshInstance3D and visible:
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh != null:
			var current := here * mesh_node.get_aabb()
			if bool(state.valid):
				state.bounds = (state.bounds as AABB).merge(current)
			else:
				state.bounds = current
				state.valid = true
	for child in node.get_children():
		var child_relative := here
		if child is Node3D:
			child_relative = here * (child as Node3D).transform
		_collect_mesh_bounds(child, child_relative, visible, state)


static func _descendants(root: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child in root.get_children():
		result.append(child)
		result.append_array(_descendants(child))
	return result


static func _safe_node_name(label: String) -> String:
	var result := label.strip_edges()
	for invalid in [".", ":", "@", "/", "\"", "%"]:
		result = result.replace(invalid, "")
	return result if not result.is_empty() else "MapAsset"
