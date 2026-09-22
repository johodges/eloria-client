extends SceneTree

const Catalog := preload("res://addons/map_asset_palette/asset_catalog.gd")
const OBJECTS_PATH := "res://data/world/objects.json"
const EXTRAS_PATH := "res://data/world/map_asset_extras.json"
const STARTER_PATH := \
	"res://src/dev/map_authoring_pilot/scenery/last_lantern_scenery.tscn"
const STARTER_NODES := [
	"CabinLantern", "ShoreRockWest", "ShoreRockEast", "WindPine",
	"GrassClumpNorth", "GrassClumpSouth", "WeatheredSign",
]

var _failures := 0


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var entries := Catalog.entries()
	_test_real_counts(entries)
	_test_valid_unique_entries(entries)
	_test_source_nodes(entries)
	_test_extra_manifest(entries)
	_test_metadata_and_stability(entries)
	_test_filtering(entries)
	print("map asset catalog: ",
		"PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	quit(_failures)


func _test_real_counts(entries: Array[Dictionary]) -> void:
	var source: Dictionary = JSON.parse_string(
		FileAccess.get_file_as_string(OBJECTS_PATH)) as Dictionary
	var harvestable_count := ((source.harvestables as Dictionary).models as Dictionary).size()
	var interactive_count := ((source.interactives as Dictionary).models as Dictionary).size()
	var extra_count := (_extras_manifest().get("entries", []) as Array).size()
	_expect(entries.size() == harvestable_count + interactive_count +
		STARTER_NODES.size() + extra_count,
		"catalog contains every native model, starter subtree, and declared extra")
	_expect(Catalog.filter_entries(entries, "", "Harvestables").size() ==
		harvestable_count and Catalog.filter_entries(entries, "", "Interactives").size() ==
		interactive_count and Catalog.filter_entries(entries, "", "Starter scenery").size() == 7,
		"category totals match their real sources")


func _test_valid_unique_entries(entries: Array[Dictionary]) -> void:
	var ids := {}
	var valid := true
	for entry: Dictionary in entries:
		var id := String(entry.get("id", ""))
		var label := String(entry.get("label", ""))
		var path := String(entry.get("scene_path", ""))
		valid = valid and not id.is_empty() and not label.is_empty() and \
			not ids.has(id) and \
			path.begins_with("res://") and FileAccess.file_exists(path)
		ids[id] = true
	_expect(valid, "every entry has a unique ID, nonempty label, and existing res path")
	_expect(not ids.has("quartz"),
		"the uncataloged legacy quartz duplicate is not invented as an entry")


func _test_source_nodes(entries: Array[Dictionary]) -> void:
	var scene_text := FileAccess.get_file_as_string(STARTER_PATH)
	var found := {}
	var valid := true
	for entry: Dictionary in entries:
		var source_node := String(entry.get("source_node", ""))
		if entry.category == "Starter scenery":
			valid = valid and entry.scene_path == STARTER_PATH and \
				source_node in STARTER_NODES and \
				scene_text.find('[node name="%s"' % source_node) >= 0
			found[source_node] = true
		else:
			valid = valid and source_node.is_empty()
	_expect(valid and found.size() == STARTER_NODES.size(),
		"starter entries name real top-level subtrees and full scenes leave source_node empty")


func _test_extra_manifest(entries: Array[Dictionary]) -> void:
	var manifest := _extras_manifest()
	var declared := manifest.get("entries", []) as Array
	var valid := true
	var declared_ids := PackedStringArray()
	for value: Variant in declared:
		if not value is Dictionary:
			valid = false
			continue
		var extra := value as Dictionary
		var extra_id := String(extra.get("id", ""))
		declared_ids.append(extra_id)
		var found := _by_id(entries, extra_id)
		valid = valid and not found.is_empty() and \
			found.label == extra.get("label") and \
			found.category == extra.get("category") and \
			found.scene_path == extra.get("scene_path") and \
			is_equal_approx(float(found.height), float(extra.get("height", 0.0)))
		for tag: Variant in extra.get("tags", []) as Array:
			var tag_text := String(tag).strip_edges()
			var matches := Catalog.filter_entries(entries, tag_text,
				String(extra.get("category", "")))
			valid = valid and not tag_text.is_empty() and \
				matches.any(func(entry: Dictionary) -> bool:
				return entry.id == extra.get("id"))
	var catalog_ids := PackedStringArray()
	for entry: Dictionary in entries:
		if String(entry.id).begins_with("continent:"):
			catalog_ids.append(String(entry.id))
	_expect(valid,
		"every declared continent extra preserves identity and searchable manifest tags")
	_expect(catalog_ids == declared_ids,
		"continent extras preserve manifest order")


func _test_metadata_and_stability(entries: Array[Dictionary]) -> void:
	var reed := _by_id(entries, "mirror_reed")
	var gate := _by_id(entries, "gate")
	_expect(reed.label == "Reed" and reed.scene_path.ends_with("mirror_reed.glb") and
		is_equal_approx(float(reed.height), 1.606) and gate.label == "Gate" and
		is_equal_approx(float(gate.height), 2.62),
		"catalog preserves native labels, source paths, and desired heights")
	var second := Catalog.entries(true)
	var original_label := String(second[0].label)
	entries[0]["label"] = "mutated"
	_expect(second.size() == entries.size() and second[0].label == original_label and
		Catalog.entries()[0].label == original_label,
		"refresh keeps stable order and returned dictionaries cannot mutate the cache")
	entries[0]["label"] = original_label


func _test_filtering(entries: Array[Dictionary]) -> void:
	var fibre := Catalog.filter_entries(entries, "FIBRE", "hArVeStAbLeS")
	var station := Catalog.filter_entries(entries, "crafting STATION", "INTERACTIVES")
	var shore := Catalog.filter_entries(entries, "shore ROCK west", "starter SCENERY")
	var geode := Catalog.filter_entries(entries, "VOLTAIC_GEODE", "")
	_expect(fibre.any(func(entry: Dictionary) -> bool: return entry.id == "mirror_reed") and
		station.size() == 1 and station[0].id == "crafting_station" and
		shore.size() == 1 and shore[0].source_node == "ShoreRockWest" and
		geode.size() == 1 and geode[0].id == "voltaic_geode",
		"query and category matching are case-insensitive across kind, label, node, and ID")
	var expected_categories := PackedStringArray([
		"Harvestables", "Interactives", "Starter scenery"])
	for value: Variant in _extras_manifest().get("entries", []) as Array:
		if not value is Dictionary:
			continue
		var category := String((value as Dictionary).get("category", ""))
		if not category.is_empty() and category not in expected_categories:
			expected_categories.append(category)
	_expect(Catalog.categories(entries) == expected_categories,
		"categories preserve stable catalog order")


func _extras_manifest() -> Dictionary:
	if not FileAccess.file_exists(EXTRAS_PATH):
		return {"version": 1, "entries": []}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(EXTRAS_PATH))
	return parsed as Dictionary if parsed is Dictionary else {}


func _by_id(entries: Array[Dictionary], id: String) -> Dictionary:
	for entry: Dictionary in entries:
		if entry.id == id:
			return entry
	return {}


func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	_failures += 1
	push_error("FAIL: " + message)
	return false
