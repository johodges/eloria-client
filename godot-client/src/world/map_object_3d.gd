class_name MapObject3D
extends StaticBody3D
## A clickable world object: a harvest node or an interactive.
##
## The world package renders the surrounding scenery as ordinary map geometry,
## and the client has no way to tell which mesh is a resource - the legacy
## client tried to match object basenames against a lowercase harvestable list
## and matched nothing, because the packs wrote relative paths. So the server
## states which object ids exist and where they are, and this places the object
## at each one rather than guessing from the scene.
##
## What stands on the tile is the thing itself: the reed bed, the ore seam, the
## notice board, the well. Both were a plain unshaded ring before, green for a
## harvest node and blue for an interactive, which said "this is clickable" and
## nothing else - a plaza of service points and a hillside of ore read as the
## same row of circles. The models are authored per resource and per role in
## `data/world/objects.json`; the ring survives only as the fallback for an
## object the registry does not describe, and as the mark on a node the player
## is currently harvesting.
##
## The map cameras keep their coloured discs. A whole map at once is too small a
## scale for a prop to read at, and the legend names the colours.

const PICK_LAYER := 32
## The disc's radius in metres. The full map frames 1600 metres at once, so
## a disc sized for the world is a pixel there; this is sized for the map.
const MAP_MARKER_RADIUS := 7.0
## Harvest nodes and interactives are told apart on the map by colour rather
## than by a label the player has to read before every click. The legend in the
## full map's sidebar names both.
const HARVEST_COLOUR := Color(0.42, 0.86, 0.44)
const INTERACTIVE_COLOUR := Color(0.95, 0.62, 0.24)
const ACTIVE_COLOUR := Color(1.0, 0.86, 0.36)
## The ring drawn under a node while the player is harvesting it, and under any
## object the registry could not place a model for.
const RING_INNER_RADIUS := 0.62
const RING_OUTER_RADIUS := 0.78

var object_id: int = -1
var kind: int = 0
var server_tile: Vector2i = Vector2i.ZERO
var label: String = ""
var detail: String = ""
var model_id: String = ""
## The ring as built, before any ground was laid under it. Kept so an object
## re-draped after a map's walk surface arrives is shaped by the ground it
## stands on rather than by whatever it was draped over before.
var _ring_flat: Mesh = null

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		catalog: Dictionary = {}) -> void:
	object_id = int(dto.get("object_id", -1))
	kind = int(dto.get("kind", 0))
	server_tile = Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	label = str(dto.get("label", ""))
	detail = str(dto.get("detail", ""))
	name = "MapObject_%d" % object_id
	collision_layer = PICK_LAYER
	collision_mask = 0
	position = adapter.tile_center(server_tile.x, server_tile.y)
	_build_visual(catalog)

func is_harvestable() -> bool:
	return kind == EloriaProtocol.MAP_OBJECT_HARVEST

func set_surface_height(height: float) -> void:
	global_position.y = height + 0.05
	_drape_ring()

## Marks the node the player is currently harvesting. The ring is hidden while
## an object is merely standing there, so this is the only thing that draws it
## on an object whose model loaded.
func set_active(active: bool) -> void:
	var ring: MeshInstance3D = get_node_or_null("Ring") as MeshInstance3D
	if not is_instance_valid(ring):
		return
	ring.visible = active or model_id.is_empty()
	var material: StandardMaterial3D = ring.material_override as StandardMaterial3D
	if material == null:
		return
	material.albedo_color = ACTIVE_COLOUR if active else _marker_colour()
	material.albedo_color.a = 0.75
	_drape_ring()

## Lay the ring over the ground it is drawn on.
##
## The ring is a flat circle a metre and a half across, and the ground under it
## is not flat: on a region such as Whitehorn Range most of it disappeared into
## the slope, leaving a crescent that grew and shrank as the camera moved past.
## Draping it holds the whole circle the same height over the ground all the
## way round, so what is drawn stays the ring the node is marked with.
func _drape_ring() -> void:
	var ring: MeshInstance3D = get_node_or_null("Ring") as MeshInstance3D
	if not is_instance_valid(ring) or not ring.visible:
		return
	if _ring_flat == null:
		_ring_flat = ring.mesh
	var draped: ArrayMesh = GroundDrape.drape(ring, _ring_flat)
	ring.mesh = _ring_flat if draped == null else draped

func _marker_colour() -> Color:
	return HARVEST_COLOUR if is_harvestable() else INTERACTIVE_COLOUR

## The colour this object is marked in on either map. The full map draws the
## modelled disc below; the minimap draws its own mark and asks for the colour
## here, so both maps mark an ore seam in one green rather than two.
func map_dot_colour() -> Color:
	return _marker_colour()

## The registry entry for this object, or an empty dictionary.
##
## A harvest node is named by its resource label and an interactive by the label
## the server derives from its role, because that is all either of them carries
## on the wire. The registry holds both maps, written by the same generator that
## writes the models, so a resource whose id is not its slugified name - Slate
## and Deep Coal both keep their bootstrap model names - resolves without the
## client guessing at a filename.
func _catalog_entry(catalog: Dictionary) -> Dictionary:
	var section: Dictionary = catalog.get(
		"harvestables" if is_harvestable() else "interactives", {}) as Dictionary
	var keys: Dictionary = section.get(
		"resources" if is_harvestable() else "roles", {}) as Dictionary
	var id: String = str(keys.get(label, ""))
	if id.is_empty():
		return {}
	var models: Dictionary = section.get("models", {}) as Dictionary
	var entry: Dictionary = models.get(id, {}) as Dictionary
	if entry.is_empty():
		return {}
	var described: Dictionary = entry.duplicate(true)
	described["id"] = id
	return described

func _build_visual(catalog: Dictionary) -> void:
	if get_child_count() > 0:
		return
	var entry: Dictionary = _catalog_entry(catalog)
	var height: float = _add_model(entry)
	_add_ring()
	_add_map_marker()
	_add_pick_shape(height)

## Returns the height of the model that was placed, or 0.0 for none.
func _add_model(entry: Dictionary) -> float:
	if entry.is_empty():
		return 0.0
	var model: Node3D = GlbSceneCache.instantiate(
		_external_path(str(entry.get("scene", ""))))
	if model == null:
		push_warning("map object %d: model %s failed to load" % [
			object_id, entry.get("scene", "")])
		return 0.0
	model.name = "Model"
	add_child(model)
	model_id = str(entry.get("id", ""))
	# The same node id stands on every map that declares it, so an unvaried
	# model reads as a stamped copy wherever two are in view of each other.
	# The object id is the server's own stable name for this one, which is what
	# makes the variation the same on every client without being sent.
	var rng := RandomNumberGenerator.new()
	rng.seed = object_id
	model.rotation.y = rng.randf() * TAU
	model.scale = Vector3.ONE * rng.randf_range(0.92, 1.08)
	return float(entry.get("height", 1.0)) * model.scale.y

func _add_ring() -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = _marker_colour()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color.a = 0.75
	var ring_mesh := TorusMesh.new()
	ring_mesh.inner_radius = RING_INNER_RADIUS
	ring_mesh.outer_radius = RING_OUTER_RADIUS
	ring_mesh.rings = 24
	ring_mesh.ring_segments = 8
	var ring := MeshInstance3D.new()
	ring.name = "Ring"
	ring.mesh = ring_mesh
	ring.material_override = material
	ring.visible = model_id.is_empty()
	add_child(ring)

func _add_map_marker() -> void:
	# A secret's entrance is found by looking, not by reading the map: it gets
	# its pick ring and nothing on either map.
	if label == "Secret":
		return
	# Sized for the map cameras, not the world: 0.6 metres was a third of a
	# pixel on the full map.
	var map_marker: MeshInstance3D = MapMarkerDisc.build(
		"MapMarker", MAP_MARKER_RADIUS, _marker_colour())
	map_marker.position.y = 4.0
	add_child(map_marker)

## The click target. A pick shape cut to the ring rather than to the object was
## fine while every object was a ring; a notice board is two metres of board a
## player aims at, and an ore seam is knee high, so the shape follows the model
## the registry measured.
func _add_pick_shape(height: float) -> void:
	var standing: float = maxf(height, 1.2)
	var shape := CylinderShape3D.new()
	shape.radius = 0.9
	shape.height = standing
	var collision := CollisionShape3D.new()
	collision.name = "PickShape"
	collision.shape = shape
	collision.position.y = standing * 0.5
	add_child(collision)

static func _external_path(path: String) -> String:
	return ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
