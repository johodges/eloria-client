@tool
extends RefCounted
## Undoable batch edits on the selected placed objects.
##
## Only authored placements are touched: assets, cosmetic scenery and gameplay
## markers. Terrain patches, paths, bridges, water and ground regions are
## excluded because moving those nodes reshapes terrain or routes.

const Probe := preload("res://addons/map_authoring_usability/terrain_probe.gd")
const Placement := preload("res://addons/map_asset_palette/placement.gd")
const EDITABLE_CONTAINERS := ["AuthoredAssets", "AuthoredScenery", "Gameplay"]
const PREFAB_CONTAINERS := ["AuthoredAssets", "AuthoredScenery"]


## Selected nodes below one of `containers`, never the root, a container itself,
## unowned/generated nodes, or a node whose selected ancestor already moves it.
static func placements(root: Node3D, nodes: Array,
		containers: Array = EDITABLE_CONTAINERS) -> Array[Node3D]:
	var candidates: Array[Node3D] = []
	if root == null:
		return candidates
	for value in nodes:
		if not value is Node3D:
			continue
		var node := value as Node3D
		if node == root or node.owner != root or not root.is_ancestor_of(node):
			continue
		var top := _top_container(root, node)
		if top == null or top == node or not String(top.name) in containers:
			continue
		candidates.append(node)
	var result: Array[Node3D] = []
	for node in candidates:
		var nested := false
		for other in candidates:
			if other != node and other.is_ancestor_of(node):
				nested = true
				break
		if not nested:
			result.append(node)
	return result


static func drop_to_ground(undo_redo: EditorUndoRedoManager, root: Node3D,
		nodes: Array[Node3D]) -> int:
	var changes: Array[Dictionary] = []
	for node in nodes:
		var ground := Probe.height_at(root, node.global_position)
		if is_nan(ground):
			continue
		var transform := node.global_transform
		var bounds := Placement.mesh_bounds(node)
		if bool(bounds.get("valid", false)):
			var oriented := Transform3D(transform.basis, Vector3.ZERO) * (bounds.bounds as AABB)
			transform.origin.y = ground - oriented.position.y
		else:
			transform.origin.y = ground
		if not transform.origin.is_equal_approx(node.global_position):
			changes.append({"node": node, "transform": transform})
	return _commit(undo_redo, root, changes, "Drop %d object%s to the ground")


static func rotate_each(undo_redo: EditorUndoRedoManager, root: Node3D,
		nodes: Array[Node3D], degrees: float) -> int:
	var changes: Array[Dictionary] = []
	for node in nodes:
		var transform := node.global_transform
		transform.basis = Basis(Vector3.UP, deg_to_rad(degrees)) * transform.basis
		changes.append({"node": node, "transform": transform})
	return _commit(undo_redo, root, changes,
		"Rotate each of %d object%s " + "%s°" % str(roundi(degrees)))


static func randomize_turn(undo_redo: EditorUndoRedoManager, root: Node3D,
		nodes: Array[Node3D], rng: RandomNumberGenerator) -> int:
	var changes: Array[Dictionary] = []
	for node in nodes:
		var transform := node.global_transform
		transform.basis = Basis(Vector3.UP, rng.randf_range(-PI, PI)) * transform.basis
		changes.append({"node": node, "transform": transform})
	return _commit(undo_redo, root, changes, "Randomly turn %d object%s")


## Rescales each asset about its own origin and keeps its visible base where it
## was, so objects neither float nor sink. Markers are skipped: they have no size.
static func randomize_size(undo_redo: EditorUndoRedoManager, root: Node3D,
		nodes: Array[Node3D], variation: float, rng: RandomNumberGenerator) -> int:
	var changes: Array[Dictionary] = []
	for node in nodes:
		var bounds := Placement.mesh_bounds(node)
		if not bool(bounds.get("valid", false)):
			continue
		var transform := node.global_transform
		var local_bounds := bounds.bounds as AABB
		var base := transform.origin.y + \
			(Transform3D(transform.basis, Vector3.ZERO) * local_bounds).position.y
		var factor := rng.randf_range(1.0 - variation, 1.0 + variation)
		transform.basis = transform.basis.scaled(Vector3.ONE * factor)
		transform.origin.y = base - (Transform3D(transform.basis, Vector3.ZERO) *
			local_bounds).position.y
		changes.append({"node": node, "transform": transform})
	return _commit(undo_redo, root, changes, "Randomly resize %d object%s")


static func _commit(undo_redo: EditorUndoRedoManager, root: Node3D,
		changes: Array[Dictionary], name_format: String) -> int:
	if changes.is_empty() or undo_redo == null:
		return 0
	undo_redo.create_action(name_format % [changes.size(), "" if changes.size() == 1 else "s"],
		UndoRedo.MERGE_DISABLE, root)
	for change: Dictionary in changes:
		var node := change.node as Node3D
		undo_redo.add_do_property(node, &"global_transform", change.transform)
		undo_redo.add_undo_property(node, &"global_transform", node.global_transform)
	undo_redo.commit_action()
	return changes.size()


static func _top_container(root: Node, node: Node) -> Node:
	var current := node
	while current != null and current.get_parent() != root:
		current = current.get_parent()
	return current
