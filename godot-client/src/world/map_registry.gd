class_name MapRegistry
extends RefCounted

## The registry is keyed by Eloria map id. The server still names a map by the
## path of an Eternal Lands map file - "./maps/nymara/westhaven.elm" - so what
## arrives on the wire is reduced to that id here rather than stored anywhere:
## the directory and the .elm extension are dropped, and what is left is the id.
## Once the server names its maps directly this only has to stop lowercasing.
static func normalize_server_map_id(value: String) -> String:
	var normalized: String = value.strip_edges().replace("\\", "/")
	while normalized.begins_with("/"):
		normalized = normalized.substr(1)
	while normalized.contains("//"):
		normalized = normalized.replace("//", "/")
	normalized = normalized.get_file()
	if normalized.get_extension().to_lower() == "elm":
		normalized = normalized.get_basename()
	return normalized.to_lower()

static func resolve(maps: Dictionary, server_map_id: String) -> Dictionary:
	var wanted: String = normalize_server_map_id(server_map_id)
	var canonical_key: String = ""
	for raw_key: Variant in maps.keys():
		var key: String = str(raw_key)
		if normalize_server_map_id(key) == wanted:
			canonical_key = key
			break
	if canonical_key.is_empty():
		return {}
	var raw_entry: Variant = maps.get(canonical_key, {})
	if not raw_entry is Dictionary:
		return {}
	var entry: Dictionary = raw_entry as Dictionary
	var visited: Dictionary = {}
	while entry.has("alias"):
		if visited.has(canonical_key):
			return {}
		visited[canonical_key] = true
		var alias: String = normalize_server_map_id(str(entry.get("alias", "")))
		canonical_key = ""
		for raw_key: Variant in maps.keys():
			var key: String = str(raw_key)
			if normalize_server_map_id(key) == alias:
				canonical_key = key
				break
		if canonical_key.is_empty():
			return {}
		raw_entry = maps.get(canonical_key, {})
		if not raw_entry is Dictionary:
			return {}
		entry = raw_entry as Dictionary
	var result: Dictionary = entry.duplicate(true)
	result["registryKey"] = canonical_key
	return result
