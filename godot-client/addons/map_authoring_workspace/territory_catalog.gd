@tool
extends RefCounted

const SCHEMA := "eloria-map-authoring-territories-v1"
const CATALOG_PATH := "res://world_authoring/territories.json"

var errors: PackedStringArray = []


func entries() -> Array[Dictionary]:
	errors.clear()
	var source := _json(CATALOG_PATH)
	if source.is_empty() or String(source.get("schema", "")) != SCHEMA:
		errors.append("Territory catalog is missing or has an unsupported schema.")
		return []
	var result: Array[Dictionary] = []
	var seen := {}
	for raw: Variant in source.get("entries", []):
		if raw is not Dictionary:
			errors.append("Territory catalog entries must be objects.")
			continue
		var declared: Dictionary = raw
		var id := String(declared.get("id", "")).strip_edges()
		var label := String(declared.get("label", "")).strip_edges()
		var manifest_path := String(declared.get("manifestPath", ""))
		if id.is_empty() or label.is_empty() or seen.has(id):
			errors.append("Territory entries need unique IDs and labels: %s" % id)
			continue
		seen[id] = true
		var manifest := _json(manifest_path)
		var geography: Dictionary = manifest.get("continentGeography", {})
		var asset: Dictionary = manifest.get("asset", {})
		var translation := _vec3(geography.get("translation"))
		var polygon := _polygon(geography.get("ownershipPolygon"))
		if translation == null or polygon.size() < 3:
			errors.append("%s has no valid continent translation/ownership polygon." % id)
			continue
		var scene_path := _optional_path(declared.get("scenePath"))
		var spec_path := _optional_path(declared.get("authoringSpecPath"))
		if scene_path.is_empty() != spec_path.is_empty():
			errors.append("%s must declare both scenePath and authoringSpecPath, or neither." % id)
			continue
		var authored_error := ""
		if not scene_path.is_empty():
			authored_error = _authored_error(scene_path, spec_path, manifest_path, id, label)
			if not authored_error.is_empty():
				errors.append(authored_error)
		var scene_exists := not scene_path.is_empty() and authored_error.is_empty()
		var glb_name := String(asset.get("glb", "world.glb"))
		var published_path := manifest_path.get_base_dir().path_join(glb_name)
		result.append({
			"id": id,
			"label": label,
			"manifest_path": manifest_path,
			"manifest_sha256": _sha(manifest_path),
			"scene_path": scene_path,
			"authoring_spec_path": spec_path,
			"editable": scene_exists,
			"source_kind": "saved_authored" if scene_exists else "published",
			"source_label": "Saved authored source" if scene_exists else "Published reference only",
			"source_path": scene_path if scene_exists else published_path,
			"source_sha256": _sha(scene_path if scene_exists else published_path),
			"source_error": authored_error,
			"translation": translation,
			"ownership_polygon": polygon,
			"ownership_sha256": JSON.stringify(_polygon_array(polygon)).sha256_text(),
			"revision": String(geography.get("revision", "unversioned")),
		})
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return String(a.label).naturalnocasecmp_to(String(b.label)) < 0)
	for entry in result:
		entry["cache_key"] = _cache_key(entry)
	return result


func find(entries_value: Array[Dictionary], id: String) -> Dictionary:
	for entry in entries_value:
		if String(entry.id) == id:
			return entry
	return {}


func active_scene_error(root: Node, entry: Dictionary) -> String:
	if root == null or not root.has_method("export_snapshot") or \
			String(root.get("region_id")) != String(entry.get("id", "")):
		return "The active scene root does not match the catalogued territory ID."
	if String(root.scene_file_path) != String(entry.get("scene_path", "")):
		return "The active scene path is not the territory's registered authored scene."
	return ""


func _json(path: String) -> Dictionary:
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	var value: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return value if value is Dictionary else {}


func _vec3(value: Variant) -> Variant:
	if value is not Array or value.size() != 3:
		return null
	var result := Vector3(float(value[0]), float(value[1]), float(value[2]))
	return result if result.is_finite() else null


func _polygon(value: Variant) -> PackedVector2Array:
	var result := PackedVector2Array()
	if value is not Array:
		return result
	for point: Variant in value:
		if point is not Array or point.size() != 2:
			return PackedVector2Array()
		var parsed := Vector2(float(point[0]), float(point[1]))
		if not parsed.is_finite():
			return PackedVector2Array()
		result.append(parsed)
	return result


func _polygon_array(polygon: PackedVector2Array) -> Array:
	var result: Array = []
	for point in polygon:
		result.append([point.x, point.y])
	return result


func _sha(path: String) -> String:
	return FileAccess.get_sha256(ProjectSettings.globalize_path(path)) \
		if not path.is_empty() and FileAccess.file_exists(path) else ""


func _optional_path(value: Variant) -> String:
	return String(value) if value is String else ""


func _cache_key(entry: Dictionary) -> String:
	var dependencies := {}
	_collect_dependencies(String(entry.source_path), dependencies)
	_collect_dependencies(String(entry.manifest_path), dependencies)
	_collect_dependencies(String(entry.authoring_spec_path), dependencies)
	var paths := dependencies.keys()
	paths.sort()
	var records := PackedStringArray()
	for path: String in paths:
		records.append("%s:%s" % [path, _sha(path)])
	return "\n".join(records).sha256_text()


func _scene_matches(path: String, expected_id: String) -> bool:
	var packed := ResourceLoader.load(path, "PackedScene",
		ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
	if packed == null:
		return false
	var instance := packed.instantiate(PackedScene.GEN_EDIT_STATE_DISABLED)
	var matches := instance is Node3D and instance.has_method("export_snapshot") and \
		String(instance.get("region_id")) == expected_id
	instance.free()
	return matches


func _authored_error(scene_path: String, spec_path: String, manifest_path: String,
		expected_id: String, expected_label: String) -> String:
	if not ResourceLoader.exists(scene_path):
		return "%s authored scene is unavailable: %s" % [expected_label, scene_path]
	if not FileAccess.file_exists(spec_path):
		return "%s authoring spec is unavailable: %s" % [expected_label, spec_path]
	if not _scene_matches(scene_path, expected_id):
		return "%s authored scene root does not declare region_id %s." % [
			expected_label, expected_id]
	var spec := _json(spec_path)
	if String(spec.get("schema", "")) != "eloria-region-authoring-spec-v1" or \
			String(spec.get("regionId", "")) != expected_id or \
			String(spec.get("label", "")) != expected_label:
		return "%s authoring spec identity does not match the territory catalog." % expected_label
	var paths: Dictionary = spec.get("paths", {})
	if _repository_path(String(paths.get("scene", ""))) != \
			_repository_path(scene_path) or \
			_repository_path(String(paths.get("manifest", ""))) != \
			_repository_path(manifest_path):
		return "%s authoring spec paths do not match its registered scene and manifest." % \
			expected_label
	return ""


func _repository_path(path: String) -> String:
	if path.is_empty():
		return ""
	var resource_path := path if path.begins_with("res://") else "res://../" + path
	return ProjectSettings.globalize_path(resource_path).simplify_path()


func _collect_dependencies(path: String, found: Dictionary) -> void:
	if path.is_empty() or found.has(path) or not FileAccess.file_exists(path):
		return
	found[path] = true
	if not ResourceLoader.exists(path):
		return
	for encoded: String in ResourceLoader.get_dependencies(path):
		for part: String in encoded.split("::"):
			if part.begins_with("res://"):
				_collect_dependencies(part, found)
				break
