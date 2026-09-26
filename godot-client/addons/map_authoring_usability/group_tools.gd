@tool
extends RefCounted
## Groups and copy-drag for placed assets, scenery and gameplay markers.
##
## A group is a shared tag in each member's node metadata (saved in the scene).
## Members stay direct children of their containers, because the bake requires
## every AuthoredAssets child to be an asset wrapper and ignores node metadata,
## so grouping never changes what is exported. Selecting one member selects
## its whole group; double-click opens the group so a single member can be
## picked.
##
## Copy-drag (Alt+drag on a selected object) duplicates the selection and
## drops the copies where the drag ends. Each copy gets a fresh asset id or
## record id, its own local resources and new group ids, and keeps its height
## above the ground. It is one undo step.

const Tools := preload("res://addons/map_authoring_usability/selection_tools.gd")
const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")
const Prefabs := preload("res://addons/map_asset_palette/prefab_library.gd")
const Markers := preload("res://addons/map_asset_palette/marker_library.gd")
const ASSET_SCRIPT := preload("res://src/dev/map_authoring_region/asset_control.gd")
const MARKER_SCRIPT := preload("res://src/dev/map_authoring_region/gameplay_marker.gd")
const GROUP_META := &"map_authoring_group"
const GHOST_NAME := "__MapAuthoringCopyDrag"

var _drag_nodes: Array[Node3D] = []
var _drag_start := Vector3.INF
var _drag_offset := Vector3.ZERO
var _ghost: Node3D
var _root: Node3D


static func group_of(node: Node) -> String:
	return String(node.get_meta(GROUP_META, "")) if node != null else ""


## Every placement in the territory carrying `group_id`.
static func members(root: Node3D, group_id: String) -> Array[Node3D]:
	var result: Array[Node3D] = []
	if group_id.is_empty() or root == null:
		return result
	for container in Tools.EDITABLE_CONTAINERS:
		var node := root.get_node_or_null(NodePath(container))
		if node == null:
			continue
		for child in node.find_children("*", "Node3D", true, true):
			if group_of(child) == group_id:
				result.append(child as Node3D)
	return result


## The selection with every touched group completed, unless `open_group` is
## the group being edited member by member.
static func expand(root: Node3D, nodes: Array, open_group: String = "") -> Array[Node3D]:
	var result: Array[Node3D] = []
	var seen := {}
	for value in nodes:
		if not value is Node3D:
			continue
		var node := value as Node3D
		var group := group_of(node)
		var batch: Array[Node3D] = [node]
		if not group.is_empty() and group != open_group:
			batch = members(root, group)
		for member in batch:
			if not seen.has(member.get_instance_id()):
				seen[member.get_instance_id()] = true
				result.append(member)
	return result


static func fresh_group_id(root: Node3D, reserved: Dictionary = {}) -> String:
	var used := reserved.duplicate()
	for container in Tools.EDITABLE_CONTAINERS:
		var node := root.get_node_or_null(NodePath(container))
		if node == null:
			continue
		for child in node.find_children("*", "Node3D", true, true):
			var group := group_of(child)
			if not group.is_empty():
				used[group] = true
	var index := 1
	while used.has("group-%02d" % index):
		index += 1
	return "group-%02d" % index


## Tags the placements as one new group (one undo step). Returns its id.
static func group(undo_redo: EditorUndoRedoManager, root: Node3D, nodes: Array) -> String:
	var targets := Tools.placements(root, nodes)
	if targets.size() < 2:
		return ""
	var identity := fresh_group_id(root)
	undo_redo.create_action("Group %d objects as %s" % [targets.size(), identity],
		UndoRedo.MERGE_DISABLE, root)
	for node in targets:
		undo_redo.add_do_method(node, &"set_meta", GROUP_META, identity)
		_add_restore(undo_redo, node)
	undo_redo.commit_action()
	return identity


## Removes the group tags of every group the placements belong to.
static func ungroup(undo_redo: EditorUndoRedoManager, root: Node3D, nodes: Array) -> int:
	var groups := {}
	for node in Tools.placements(root, nodes):
		var group := group_of(node)
		if not group.is_empty():
			groups[group] = true
	var targets: Array[Node3D] = []
	for group: String in groups:
		targets.append_array(members(root, group))
	if targets.is_empty():
		return 0
	undo_redo.create_action("Ungroup %d objects" % targets.size(), UndoRedo.MERGE_DISABLE, root)
	for node in targets:
		undo_redo.add_do_method(node, &"remove_meta", GROUP_META)
		_add_restore(undo_redo, node)
	undo_redo.commit_action()
	return targets.size()


static func _add_restore(undo_redo: EditorUndoRedoManager, node: Node) -> void:
	if node.has_meta(GROUP_META):
		undo_redo.add_undo_method(node, &"set_meta", GROUP_META, node.get_meta(GROUP_META))
	else:
		undo_redo.add_undo_method(node, &"remove_meta", GROUP_META)


# Copy-drag -----------------------------------------------------------------

func is_dragging() -> bool:
	return not _drag_nodes.is_empty()


## True when `ground` (a terrain point) lies on one of the selected placements,
## so an Alt+press there starts a copy-drag rather than an orbit.
static func hits_selection(nodes: Array[Node3D], ground: Vector3) -> bool:
	for node in nodes:
		var bounds := Placement.mesh_bounds(node)
		if not bool(bounds.get("valid", false)):
			if Vector2(node.global_position.x - ground.x,
					node.global_position.z - ground.z).length() < 1.5:
				return true
			continue
		var box: AABB = node.global_transform * (bounds.bounds as AABB)
		if ground.x >= box.position.x - 0.5 and ground.x <= box.end.x + 0.5 and \
				ground.z >= box.position.z - 0.5 and ground.z <= box.end.z + 0.5:
			return true
	return false


func begin_drag(root: Node3D, nodes: Array[Node3D], ground: Vector3) -> void:
	cancel_drag()
	_root = root
	_drag_nodes = nodes.duplicate()
	_drag_start = ground
	_drag_offset = Vector3.ZERO
	_ghost = Node3D.new()
	_ghost.name = GHOST_NAME
	for node in _drag_nodes:
		var copy: Node3D
		if node.get_script() == MARKER_SCRIPT:
			copy = Markers.pin_node(String(node.get("kind")))
		else:
			copy = node.duplicate() as Node3D
			if copy.get_script() != null:
				copy.set_script(null)
		_ghost.add_child(copy)
	Placement.make_ghost(_ghost, 0.5)
	root.add_child(_ghost, false, Node.INTERNAL_MODE_BACK)
	_ghost.global_transform = Transform3D.IDENTITY
	update_drag(ground)


func update_drag(ground: Vector3) -> void:
	if not is_dragging() or _ghost == null:
		return
	_drag_offset = Vector3(ground.x - _drag_start.x, 0.0, ground.z - _drag_start.z)
	for index in _drag_nodes.size():
		var copy := _ghost.get_child(index) as Node3D
		copy.global_transform = moved_transform(_root, _drag_nodes[index], _drag_offset)


## The copies (one undo step); returns them. Cancels when the drag did not move.
func finish_drag(undo_redo: EditorUndoRedoManager) -> Array[Node3D]:
	var nodes := _drag_nodes.duplicate()
	var offset := _drag_offset
	var root := _root
	cancel_drag()
	if nodes.is_empty() or Vector2(offset.x, offset.z).length() < 0.05:
		return []
	return commit_copies(undo_redo, root, nodes, offset)


func cancel_drag() -> void:
	if _ghost != null and is_instance_valid(_ghost):
		if _ghost.get_parent() != null:
			_ghost.get_parent().remove_child(_ghost)
		_ghost.queue_free()
	_ghost = null
	_drag_nodes.clear()
	_drag_start = Vector3.INF
	_drag_offset = Vector3.ZERO


func ghost() -> Node3D:
	return _ghost if _ghost != null and is_instance_valid(_ghost) else null


## `node` moved by `offset` in X/Z, keeping its height above the ground.
static func moved_transform(root: Node3D, node: Node3D, offset: Vector3) -> Transform3D:
	var transform := node.global_transform
	var before := Probe.height_at(root, transform.origin)
	transform.origin += Vector3(offset.x, 0.0, offset.z)
	var after := Probe.height_at(root, transform.origin)
	if not is_nan(before) and not is_nan(after):
		transform.origin.y += after - before
	return transform


## Duplicates `nodes` next to their originals, moved by `offset`, as one undo
## step with fresh identities and group ids.
static func commit_copies(undo_redo: EditorUndoRedoManager, root: Node3D, nodes: Array,
		offset: Vector3) -> Array[Node3D]:
	var sources := Tools.placements(root, nodes)
	var copies: Array[Node3D] = []
	var owned: Array[Array] = []
	var reserved_assets := {}
	var reserved_records := {}
	var reserved_groups := {}
	var group_map := {}
	var asset_map := {}
	var followers: Array[Node3D] = []
	for source in sources:
		var copy := source.duplicate() as Node3D
		var owned_here: Array[Node] = []
		for descendant in _descendants(source):
			if descendant.owner == root:
				var twin := copy.get_node_or_null(source.get_path_to(descendant))
				if twin != null:
					owned_here.append(twin)
		if copy.get_script() == ASSET_SCRIPT:
			var identity := Prefabs._fresh_asset_id(source.get_parent(),
				String(copy.get("catalog_asset_id")), String(copy.get("asset_id")), reserved_assets)
			reserved_assets[identity] = true
			copy.set("asset_id", identity)
			copy.set("node_name", "Authored_%s" % identity.replace(":", "_").replace("-", "_"))
			asset_map[String(source.get("asset_id"))] = identity
		elif copy.get_script() == MARKER_SCRIPT:
			var record := Markers.fresh_record_id(root, String(copy.get("label")),
				String(copy.get("kind")), reserved_records)
			reserved_records[record] = true
			copy.set("record_id", record)
			copy.name = record
			# Runtime bindings name certified server records of the original.
			var unbound: Array[Dictionary] = []
			copy.set("runtime_bindings", unbound)
			followers.append(copy)
		var old_group := group_of(copy)
		if not old_group.is_empty():
			if not group_map.has(old_group):
				group_map[old_group] = fresh_group_id(root, reserved_groups)
				reserved_groups[group_map[old_group]] = true
			copy.set_meta(GROUP_META, group_map[old_group])
		Prefabs._localize_resources(copy)
		for twin in owned_here:
			Prefabs._localize_resources(twin)
		copies.append(copy)
		owned.append(owned_here)
	# A marker riding on a copied asset follows the copy; one copied without its
	# asset would jump back onto the original, so it stops following.
	for marker in followers:
		var followed := String(marker.get("follow_asset_id"))
		if not followed.is_empty():
			marker.set("follow_asset_id", String(asset_map.get(followed, "")))
	if copies.is_empty():
		return copies
	undo_redo.create_action("Copy %d object%s" % [copies.size(), "" if copies.size() == 1 else "s"],
		UndoRedo.MERGE_DISABLE, root)
	for index in copies.size():
		var copy := copies[index]
		var parent := sources[index].get_parent()
		undo_redo.add_do_method(parent, &"add_child", copy, true)
		undo_redo.add_do_method(copy, &"set_owner", root)
		for twin: Node in owned[index]:
			undo_redo.add_do_method(twin, &"set_owner", root)
		undo_redo.add_do_property(copy, &"global_transform",
			moved_transform(root, sources[index], offset))
		undo_redo.add_do_reference(copy)
		undo_redo.add_undo_method(parent, &"remove_child", copy)
	undo_redo.commit_action()
	return copies


static func _descendants(node: Node) -> Array[Node]:
	var result: Array[Node] = []
	for child in node.get_children():
		result.append(child)
		result.append_array(_descendants(child))
	return result
