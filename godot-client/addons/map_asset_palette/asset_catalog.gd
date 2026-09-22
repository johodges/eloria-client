extends RefCounted

const OBJECTS_PATH := "res://data/world/objects.json"
const STARTER_SCENE_PATH := \
	"res://src/dev/map_authoring_pilot/scenery/last_lantern_scenery.tscn"
const STARTER_ENTRIES := [
	["starter:cabin_lantern", "Cabin Lantern", "CabinLantern", "lantern light cabin"],
	["starter:shore_rock_west", "Shore Rock West", "ShoreRockWest", "rock stone shore"],
	["starter:shore_rock_east", "Shore Rock East", "ShoreRockEast", "rock stone shore"],
	["starter:wind_pine", "Wind Pine", "WindPine", "tree pine foliage"],
	["starter:grass_clump_north", "Grass Clump North", "GrassClumpNorth", "grass foliage"],
	["starter:grass_clump_south", "Grass Clump South", "GrassClumpSouth", "grass foliage"],
	["starter:weathered_sign", "Weathered Sign", "WeatheredSign", "sign timber"],
]

static var _cache: Array[Dictionary] = []
static var _cache_ready := false


static func entries(refresh_cache: bool = false) -> Array[Dictionary]:
	if refresh_cache or not _cache_ready:
		_cache = _build_entries()
		_cache_ready = true
	var result: Array[Dictionary] = []
	for entry: Dictionary in _cache:
		result.append(entry.duplicate(true))
	return result


static func filter_entries(source_entries: Array[Dictionary], query: String,
		category: String = "") -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var wanted_query := query.strip_edges().to_lower()
	var wanted_category := category.strip_edges().to_lower()
	if wanted_category == "all":
		wanted_category = ""
	for entry: Dictionary in source_entries:
		if not wanted_category.is_empty() and \
				String(entry.get("category", "")).to_lower() != wanted_category:
			continue
		var searchable := String(entry.get("search_text", "")).to_lower()
		if not wanted_query.is_empty() and searchable.find(wanted_query) < 0:
			continue
		result.append(entry)
	return result


static func categories(source_entries: Array[Dictionary]) -> PackedStringArray:
	var result := PackedStringArray()
	var seen := {}
	for entry: Dictionary in source_entries:
		var category := String(entry.get("category", "")).strip_edges()
		if category.is_empty() or seen.has(category):
			continue
		seen[category] = true
		result.append(category)
	return result


static func _build_entries() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var catalog := _read_dictionary(OBJECTS_PATH)
	if catalog.is_empty():
		return result
	_append_native_group(result, catalog, "harvestables", "Harvestables")
	_append_native_group(result, catalog, "interactives", "Interactives")
	if _valid_resource_path(STARTER_SCENE_PATH):
		for spec: Array in STARTER_ENTRIES:
			result.append(_entry(String(spec[0]), String(spec[1]),
				"Starter scenery", STARTER_SCENE_PATH, String(spec[2]), 0.0,
				String(spec[3])))
	else:
		push_warning("Map asset catalog skipped missing starter scene: %s" %
			STARTER_SCENE_PATH)
	return result


static func _append_native_group(result: Array[Dictionary], catalog: Dictionary,
		group_name: String, category: String) -> void:
	var group := catalog.get(group_name, {}) as Dictionary
	var models := group.get("models", {}) as Dictionary
	var roles := group.get("roles", {}) as Dictionary
	var role_names := {}
	for role_label: String in roles:
		role_names[String(roles[role_label])] = role_label
	var sorted_models: Array[Dictionary] = []
	for model_id: String in models:
		var model := models[model_id] as Dictionary
		sorted_models.append({"id": model_id, "model": model})
	sorted_models.sort_custom(func(left: Dictionary, right: Dictionary) -> bool:
		var left_label := String((left.model as Dictionary).get("label", left.id))
		var right_label := String((right.model as Dictionary).get("label", right.id))
		if left_label.naturalnocasecmp_to(right_label) == 0:
			return String(left.id) < String(right.id)
		return left_label.naturalnocasecmp_to(right_label) < 0)
	for item: Dictionary in sorted_models:
		var model_id := String(item.id)
		var model := item.model as Dictionary
		var scene_path := String(model.get("scene", ""))
		if not _valid_resource_path(scene_path):
			push_warning("Map asset catalog skipped invalid path for '%s': %s" % [
				model_id, scene_path])
			continue
		var label := String(model.get("label", model_id))
		var search_fields := [String(model.get("kind", "")),
			String(role_names.get(model_id, "")), group_name]
		result.append(_entry(model_id, label, category, scene_path, "",
			float(model.get("height", 0.0)), " ".join(search_fields)))


static func _entry(id: String, label: String, category: String,
		scene_path: String, source_node: String, height: float,
		extra_search: String) -> Dictionary:
	return {
		"id": id,
		"label": label,
		"category": category,
		"scene_path": scene_path,
		"source_node": source_node,
		"height": height,
		"search_text": "%s %s %s %s %s" % [
			id, label, category, source_node, extra_search],
	}


static func _read_dictionary(path: String) -> Dictionary:
	if not _valid_resource_path(path):
		push_warning("Map asset catalog source is missing: %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		push_warning("Map asset catalog source is not a JSON object: %s" % path)
		return {}
	return parsed as Dictionary


static func _valid_resource_path(path: String) -> bool:
	return path.begins_with("res://") and FileAccess.file_exists(path)
