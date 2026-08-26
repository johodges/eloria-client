class_name WorldManifest
extends RefCounted

const SUPPORTED_SCHEMA_MAJOR := 1

var source_path := ""
var data: Dictionary = {}
var errors: Array[String] = []
var warnings: Array[String] = []

static func load_file(path: String) -> WorldManifest:
	var result := WorldManifest.new()
	result.source_path = path
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		result.errors.append("manifest_open_failed: " + path)
		return result
	var parsed = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		result.errors.append("manifest_json_invalid")
		return result
	result.data = parsed
	result._validate()
	return result

func is_valid() -> bool:
	return errors.is_empty()

func asset_id() -> String:
	return str(data.get("asset", {}).get("id", ""))

func glb_path() -> String:
	var relative := str(data.get("asset", {}).get("glb", ""))
	return source_path.get_base_dir().path_join(relative)

func coordinate_adapter() -> CoordinateAdapter:
	var asset: Dictionary = data.get("asset", {})
	var coordinate: Dictionary = data.get("coordinateTransform", {})
	if coordinate.is_empty():
		coordinate = {
			"metresPerTile": 1.0,
			"origin": asset.get("origin", [0.0, 0.0, 0.0]),
			"walkingHeight": asset.get("origin", [0.0, 0.0, 0.0])[1],
			"invertServerY": true}
		warnings.append("coordinateTransform missing; using explicit documented defaults")
	return CoordinateAdapter.new(coordinate)

func _validate() -> void:
	var version := str(data.get("schemaVersion", ""))
	if version.is_empty():
		errors.append("schemaVersion missing")
	elif int(version.get_slice(".", 0)) != SUPPORTED_SCHEMA_MAJOR:
		errors.append("unsupported schemaVersion: " + version)
	var asset = data.get("asset")
	if not asset is Dictionary:
		errors.append("asset object missing")
		return
	for key in ["id", "glb", "units", "coordinateSystem", "bounds"]:
		if not asset.has(key):
			errors.append("asset." + key + " missing")
	if str(asset.get("units", "")) != "meters":
		errors.append("only metre GLB assets are currently supported")
	var axes: Dictionary = asset.get("coordinateSystem", {})
	if axes.get("upAxis") != "Y":
		errors.append("only Y-up GLB assets are currently supported")
	if not data.has("spawnPoints"):
		warnings.append("spawnPoints missing")
	if not data.has("collision"):
		warnings.append("collision declarations missing")
	if not data.has("navigation"):
		warnings.append("navigation declarations missing")
