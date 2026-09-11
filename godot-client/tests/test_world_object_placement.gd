extends SceneTree
## A world object stands its own model on its tile, and falls back to a ring.
##
## The models were authored, the registry described all fifty-two of them and
## every GLB was on disk - and every harvest node in the world drew a bare green
## ring anyway, because the one place that builds these objects called
## `configure` without the registry and an empty one is a legal one. This walks
## the same path with the real `data/world/objects.json`: a resource the
## registry names gets its model and no ring, one it does not gets the ring.

const REGISTRY := "res://data/world/objects.json"

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var catalog: Dictionary = _json(REGISTRY)
	_expect(not catalog.is_empty(), "the registry loads from the path main.gd reads")
	var resources: Dictionary = (catalog.get("harvestables", {}) as Dictionary).get(
		"resources", {}) as Dictionary
	var roles: Dictionary = (catalog.get("interactives", {}) as Dictionary).get(
		"roles", {}) as Dictionary
	_expect(resources.size() >= 40, "and names a model for each of the resources in play")
	_expect(roles.size() >= 5, "and one for each interactive role")

	var adapter := CoordinateAdapter.new({"metresPerTile": 1.0, "serverOrigin": [0.0, 0.0]})
	var known: String = resources.keys()[0]
	var node := _object(adapter, catalog, EloriaProtocol.MAP_OBJECT_HARVEST, known, 1)
	_expect(node.get_node_or_null("Model") != null,
		"a node whose resource the registry names stands its model: " + known)
	var ring: MeshInstance3D = node.get_node_or_null("Ring") as MeshInstance3D
	_expect(ring != null and not ring.visible,
		"and does not draw the ring that stands in for a missing model")
	_expect(not node.model_id.is_empty(), "and remembers which model it placed")

	var role: String = roles.keys()[0]
	var built := _object(adapter, catalog, EloriaProtocol.MAP_OBJECT_INTERACTIVE, role, 2)
	_expect(built.get_node_or_null("Model") != null,
		"an interactive stands its model too: " + role)

	var stranger := _object(adapter, catalog, EloriaProtocol.MAP_OBJECT_HARVEST,
		"Nothing The Registry Knows", 3)
	_expect(stranger.get_node_or_null("Model") == null,
		"a resource the registry does not name places nothing")
	var fallback: MeshInstance3D = stranger.get_node_or_null("Ring") as MeshInstance3D
	_expect(fallback != null and fallback.visible,
		"and falls back to the ring, which is what the ring is for")

	# Two of the same node are varied, so a hillside of ore is not one model
	# stamped in a row; the object id is what makes it the same on every client.
	var first := _object(adapter, catalog, EloriaProtocol.MAP_OBJECT_HARVEST, known, 11)
	var second := _object(adapter, catalog, EloriaProtocol.MAP_OBJECT_HARVEST, known, 12)
	var one: Node3D = first.get_node_or_null("Model") as Node3D
	var two: Node3D = second.get_node_or_null("Model") as Node3D
	_expect(one != null and two != null and not is_equal_approx(one.rotation.y, two.rotation.y),
		"two of the same node do not stand identically")
	var crossing := MapObject3D.new()
	root.add_child(crossing)
	crossing.configure({"object_id": 23, "kind": EloriaProtocol.MAP_OBJECT_INTERACTIVE,
		"x": 10, "y": 10, "label": "Portal", "detail": "Beyond it lies Whitehorn Range."},
		adapter, catalog, true)
	_expect(crossing.get_node_or_null("Model") == null and crossing.get_node_or_null("Ring") == null,
		"an authored landscape crossing adds no second monument or ring")
	_expect(crossing.is_portal() and crossing.map_glyph() == "P" and crossing.destination() == "Whitehorn Range",
		"the crossing retains its interaction identity and map destination")

	print("world object placement tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _object(adapter: CoordinateAdapter, catalog: Dictionary, kind: int,
		label: String, object_id: int) -> MapObject3D:
	var node := MapObject3D.new()
	root.add_child(node)
	node.configure({"object_id": object_id, "kind": kind, "x": 10, "y": 10,
		"label": label, "detail": ""}, adapter, catalog)
	return node

static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}

func _expect(value: bool, label: String) -> void:
	if value:
		return
	failures += 1
	push_error("FAIL: " + label)
