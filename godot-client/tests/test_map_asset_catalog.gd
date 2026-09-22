extends SceneTree

const Catalog := preload("res://addons/map_asset_palette/asset_catalog.gd")
const OBJECTS_PATH := "res://data/world/objects.json"
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
	_expect(entries.size() == harvestable_count + interactive_count +
		STARTER_NODES.size(),
		"catalog contains every JSON model plus seven starter subtrees")
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
	_expect(Catalog.categories(entries) == PackedStringArray([
		"Harvestables", "Interactives", "Starter scenery"]),
		"categories preserve stable catalog order")


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
