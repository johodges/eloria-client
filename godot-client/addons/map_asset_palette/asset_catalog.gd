extends RefCounted

const OBJECTS_PATH := "res://data/world/objects.json"
const EXTRAS_PATH := "res://data/world/map_asset_extras.json"
const EXTRA_CATEGORIES := {
	"Continent props": true,
	"Continent structures": true,
	"Continent landmarks": true,
}
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

## Drop-in library: every model or scene under this folder becomes a palette
## entry with no JSON to edit. A first-level subfolder names its category
## ("Library: Rocks"); files directly inside are listed under "Library".
const LIBRARY_DIRECTORY := "res://assets/world/library"
const LIBRARY_EXTENSIONS := ["glb", "gltf", "tscn", "scn"]
const IMPORT_EXTENSIONS := ["glb", "gltf"]
const LIBRARY_CATEGORY := "Library"
const LIBRARY_PREFIX := "library:"

static var library_directory := LIBRARY_DIRECTORY
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
	_append_extras(result)
	_append_library(result)
	return result


## Library entries, found by walking library_directory (see LIBRARY_DIRECTORY).
static func library_entries() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	_append_library(result)
	return result


static func _append_library(result: Array[Dictionary]) -> void:
	var root := library_directory.trim_suffix("/")
	if not DirAccess.dir_exists_absolute(root):
		return
	var known_ids := {}
	for existing: Dictionary in result:
		known_ids[String(existing.id)] = true
	_scan_library(result, known_ids, root, root, "")


static func _scan_library(result: Array[Dictionary], known_ids: Dictionary, root: String,
		directory: String, category: String) -> void:
	var files := DirAccess.get_files_at(directory)
	var sorted_files := Array(files)
	sorted_files.sort_custom(func(a: String, b: String) -> bool:
		return a.naturalnocasecmp_to(b) < 0)
	for file_name: String in sorted_files:
		if file_name.begins_with(".") or not file_name.get_extension().to_lower() in \
				LIBRARY_EXTENSIONS:
			continue
		var path := directory.path_join(file_name)
		var relative := path.trim_prefix(root + "/").get_basename()
		var id := LIBRARY_PREFIX + relative
		if known_ids.has(id):
			id = LIBRARY_PREFIX + path.trim_prefix(root + "/")
		if known_ids.has(id):
			continue
		known_ids[id] = true
		var label := file_name.get_basename().replace("_", " ").replace("-", " ").capitalize()
		var category_name := LIBRARY_CATEGORY if category.is_empty() else \
			"%s: %s" % [LIBRARY_CATEGORY, category]
		result.append(_entry(id, label, category_name, path, "", 0.0,
			"library imported %s %s" % [category, relative.replace("/", " ")]))
	var folders := Array(DirAccess.get_directories_at(directory))
	folders.sort_custom(func(a: String, b: String) -> bool:
		return a.naturalnocasecmp_to(b) < 0)
	for folder: String in folders:
		if folder.begins_with("."):
			continue
		_scan_library(result, known_ids, root, directory.path_join(folder),
			folder if category.is_empty() else category)


## Copies model files from anywhere on disk into library_directory/<category>
## (glTF keeps its buffers and images beside it). Existing names get a numeric
## suffix; nothing is overwritten. Returns {"copied": [res paths],
## "skipped": [reasons]}. The editor still has to scan and import the copies.
static func import_models(sources: PackedStringArray, category: String) -> Dictionary:
	var copied: Array[String] = []
	var skipped: Array[String] = []
	var folder := library_directory.trim_suffix("/")
	var cleaned := _clean_name(category)
	if not cleaned.is_empty():
		folder = folder.path_join(cleaned)
	var absolute_folder := ProjectSettings.globalize_path(folder)
	DirAccess.make_dir_recursive_absolute(absolute_folder)
	for source in sources:
		var extension := source.get_extension().to_lower()
		if not extension in IMPORT_EXTENSIONS:
			skipped.append("%s: only .glb and .gltf models can be imported" % source.get_file())
			continue
		if not FileAccess.file_exists(source):
			skipped.append("%s: file not found" % source)
			continue
		var stem := _clean_name(source.get_file().get_basename())
		if stem.is_empty():
			stem = "model"
		var target_name := "%s.%s" % [stem, extension]
		var suffix := 2
		while FileAccess.file_exists(absolute_folder.path_join(target_name)):
			target_name = "%s_%d.%s" % [stem, suffix, extension]
			suffix += 1
		var error := DirAccess.copy_absolute(source, absolute_folder.path_join(target_name))
		if error != OK:
			skipped.append("%s: copy failed (%s)" % [source.get_file(), error_string(error)])
			continue
		if extension == "gltf":
			for companion in _gltf_companions(source):
				var from := source.get_base_dir().path_join(companion)
				var to := absolute_folder.path_join(companion)
				DirAccess.make_dir_recursive_absolute(to.get_base_dir())
				if FileAccess.file_exists(from) and not FileAccess.file_exists(to):
					DirAccess.copy_absolute(from, to)
		copied.append(folder.path_join(target_name))
	return {"copied": copied, "skipped": skipped}


## Relative buffer and image files a .gltf refers to.
static func _gltf_companions(path: String) -> PackedStringArray:
	var result := PackedStringArray()
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return result
	for key in ["buffers", "images"]:
		var items: Variant = (parsed as Dictionary).get(key, [])
		if not items is Array:
			continue
		for item: Variant in items:
			if item is Dictionary and (item as Dictionary).has("uri"):
				var uri := String(item.uri).uri_decode()
				if not uri.begins_with("data:") and not uri.contains("..") and \
						not uri.is_absolute_path():
					result.append(uri)
	return result


static func _clean_name(text: String) -> String:
	var cleaned := ""
	for character in text.strip_edges():
		if character.is_valid_identifier() or character.is_valid_int() or character == "-":
			cleaned += character
		elif not cleaned.ends_with("_"):
			cleaned += "_"
	return cleaned.trim_prefix("_").trim_suffix("_")


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


static func _append_extras(result: Array[Dictionary]) -> void:
	if not FileAccess.file_exists(EXTRAS_PATH):
		return
	var manifest := _read_dictionary(EXTRAS_PATH)
	var declared: Variant = manifest.get("entries", null)
	if int(manifest.get("version", 0)) != 1 or not declared is Array:
		push_warning("Map asset extras must use version 1 with an entries array: %s" %
			EXTRAS_PATH)
		return
	var known_ids := {}
	for existing: Dictionary in result:
		known_ids[String(existing.id)] = true
	for value: Variant in declared as Array:
		if not value is Dictionary:
			push_warning("Map asset extras skipped a non-object entry")
			continue
		var extra := value as Dictionary
		var id := String(extra.get("id", "")).strip_edges()
		var label := String(extra.get("label", "")).strip_edges()
		var category := String(extra.get("category", "")).strip_edges()
		var scene_path := String(extra.get("scene_path", "")).strip_edges()
		var height := float(extra.get("height", 0.0))
		var tags_value: Variant = extra.get("tags", [])
		if not id.begins_with("continent:") or label.is_empty() or \
				not EXTRA_CATEGORIES.has(category) or known_ids.has(id) or \
				not scene_path.begins_with("res://assets/world/continent/") or \
				not _valid_resource_path(scene_path) or not is_finite(height) or \
				height < 0.0 or not tags_value is Array:
			push_warning("Map asset extras skipped invalid or duplicate entry '%s'" % id)
			continue
		var tags: Array[String] = []
		var tags_valid := true
		for tag_value: Variant in tags_value as Array:
			if not tag_value is String:
				tags_valid = false
				break
			var tag := String(tag_value).strip_edges()
			if not tag.is_empty():
				tags.append(tag)
		if not tags_valid:
			push_warning("Map asset extras skipped invalid tags for '%s'" % id)
			continue
		known_ids[id] = true
		result.append(_entry(id, label, category, scene_path, "", height,
			" ".join(tags)))


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
