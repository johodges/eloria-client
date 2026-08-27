class_name ItemAtlas
extends RefCounted

var _atlas_paths: Array[String] = []
var _textures: Dictionary = {}
var _aliases: Dictionary = {}
var _cell_size := Vector2(50.0, 50.0)
var _columns := 5
var _images_per_atlas := 25
var _fallback_image_id := -1

func configure(config: Dictionary) -> void:
	_atlas_paths.clear()
	_textures.clear()
	_aliases.clear()
	var cell_value: Variant = config.get("cellSize", [50, 50])
	if cell_value is Array:
		var values: Array = cell_value as Array
		if values.size() >= 2:
			_cell_size = Vector2(float(values[0]), float(values[1]))
	_columns = maxi(1, int(config.get("columns", 5)))
	_images_per_atlas = maxi(1, int(config.get("imagesPerAtlas", 25)))
	_fallback_image_id = int(config.get("fallbackImageId", -1))
	var aliases_value: Variant = config.get("aliases", {})
	if aliases_value is Dictionary:
		var aliases: Dictionary = aliases_value as Dictionary
		for source_value: Variant in aliases:
			_aliases[int(str(source_value))] = int(aliases.get(source_value, -1))
	var paths_value: Variant = config.get("atlases", [])
	if paths_value is Array:
		for raw_path: Variant in paths_value:
			_atlas_paths.append(str(raw_path))

func icon_for(image_id: int) -> Texture2D:
	if image_id < 0:
		return null
	var resolved_image_id: int = _resolved_image_id(image_id)
	if resolved_image_id < 0:
		return null
	var atlas_index: int = floori(float(resolved_image_id) / float(_images_per_atlas))
	if atlas_index < 0 or atlas_index >= _atlas_paths.size():
		return null
	var texture: Texture2D = _texture_for(atlas_index)
	if texture == null:
		return null
	var local_id: int = resolved_image_id % _images_per_atlas
	var atlas_texture: AtlasTexture = AtlasTexture.new()
	atlas_texture.atlas = texture
	atlas_texture.region = Rect2(
		float(local_id % _columns) * _cell_size.x,
		float(floori(float(local_id) / float(_columns))) * _cell_size.y,
		_cell_size.x, _cell_size.y)
	return atlas_texture

func supports(image_id: int) -> bool:
	return image_id >= 0 and image_id < _atlas_paths.size() * _images_per_atlas

func uses_substitute(image_id: int) -> bool:
	return image_id >= 0 and (_aliases.has(image_id) or not supports(image_id))

func _resolved_image_id(image_id: int) -> int:
	if _aliases.has(image_id):
		return int(_aliases.get(image_id, -1))
	if supports(image_id):
		return image_id
	return _fallback_image_id

func _texture_for(atlas_index: int) -> Texture2D:
	if _textures.has(atlas_index):
		return _textures[atlas_index] as Texture2D
	var resource: Resource = load(_atlas_paths[atlas_index])
	if not resource is Texture2D:
		return null
	var texture: Texture2D = resource as Texture2D
	_textures[atlas_index] = texture
	return texture
