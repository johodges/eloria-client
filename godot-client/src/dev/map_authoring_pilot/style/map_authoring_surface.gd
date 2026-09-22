@tool
class_name MapAuthoringSurface
extends Resource

## One object's saved surface choice. The source material is the authored data;
## rotated derivatives live only in the private runtime backend.

enum MaterialMode {
	SURFACE,
	ROAD_SHADER,
}

var _material_choices := {}
var _backend := MapAuthoringVisualStyle.new()

# Keep this order: loading must establish the factory mode and preset before it
# restores a hand-edited source material from the resource file.
@export_storage var material_mode := MaterialMode.SURFACE:
	set(value):
		var bounded := clampi(value, MaterialMode.SURFACE, MaterialMode.ROAD_SHADER)
		if material_mode == bounded:
			return
		_remember_current_choice()
		material_mode = bounded
		source_material = _material_for_choice(texture_preset, source_material)
		_sync_backend()
		_finish_editor_change()

@export_enum("Custom", "Grass", "Worn earth", "Soil", "Sand", "Timber",
	"Stone", "Thatch", "Textile", "Canvas", "Metal", "Leather", "Hide",
	"Bone", "Crystal", "Cavern", "Slate") var texture_preset := \
	MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if texture_preset == value:
			return
		_remember_current_choice()
		texture_preset = value
		source_material = _material_for_choice(value, source_material)
		_finish_editor_change()

@export_range(-180.0, 180.0, 1.0, "degrees") var rotation_degrees := 0.0:
	set(value):
		var bounded := clampf(value, -180.0, 180.0)
		if is_equal_approx(rotation_degrees, bounded):
			return
		rotation_degrees = bounded
		_sync_backend_rotation()
		emit_changed()

@export var show_advanced_materials := false:
	set(value):
		if show_advanced_materials == value:
			return
		show_advanced_materials = value
		notify_property_list_changed()
		emit_changed()

@export var source_material: Material:
	set(value):
		if source_material == value:
			return
		source_material = value
		_sync_backend_source()
		emit_changed()


func _init() -> void:
	resource_local_to_scene = true
	_sync_backend()


static func from_preset(preset: String,
		road_shader: bool = false) -> MapAuthoringSurface:
	var surface := MapAuthoringSurface.new()
	surface.material_mode = (MaterialMode.ROAD_SHADER
		if road_shader else MaterialMode.SURFACE)
	surface.texture_preset = preset
	return surface


static func from_material(source: Material,
		preset: String = MapAuthoringTexturePresets.CUSTOM,
		road_shader: bool = false) -> MapAuthoringSurface:
	var surface := MapAuthoringSurface.new()
	surface.material_mode = (MaterialMode.ROAD_SHADER
		if road_shader else MaterialMode.SURFACE)
	surface.texture_preset = preset
	surface.source_material = source.duplicate(true) as Material if source != null else null
	return surface


func get_material(extra_rotation_degrees: float = 0.0) -> Material:
	return _backend.get_material(_backend_slot(), extra_rotation_degrees)


func signature() -> Array:
	return [get_instance_id(), material_mode, texture_preset, rotation_degrees] + \
		_backend.rotation_signature()


func _validate_property(property: Dictionary) -> void:
	if StringName(property.name) != &"source_material":
		return
	if not show_advanced_materials and \
			texture_preset != MapAuthoringTexturePresets.CUSTOM:
		property.usage = int(property.usage) & ~PROPERTY_USAGE_EDITOR


func _backend_slot() -> String:
	return "road" if material_mode == MaterialMode.ROAD_SHADER else "terrain"


func _sync_backend() -> void:
	_backend.terrain_material = (source_material
		if material_mode == MaterialMode.SURFACE else null)
	_backend.worn_path_material = (source_material
		if material_mode == MaterialMode.ROAD_SHADER else null)
	_sync_backend_rotation()


func _sync_backend_source() -> void:
	if material_mode == MaterialMode.ROAD_SHADER:
		_backend.worn_path_material = source_material
	else:
		_backend.terrain_material = source_material


func _sync_backend_rotation() -> void:
	if material_mode == MaterialMode.ROAD_SHADER:
		_backend.road_texture_rotation_degrees = rotation_degrees
	else:
		_backend.terrain_texture_rotation_degrees = rotation_degrees


func _choice_key(preset: String = texture_preset) -> String:
	return "%d:%s" % [material_mode, preset]


func _remember_current_choice() -> void:
	if source_material != null:
		_material_choices[_choice_key()] = source_material


func _material_for_choice(preset: String, current: Material) -> Material:
	var key := _choice_key(preset)
	if _material_choices.has(key):
		return _material_choices[key]
	if preset == MapAuthoringTexturePresets.CUSTOM:
		return current
	if material_mode == MaterialMode.ROAD_SHADER:
		return MapAuthoringTexturePresets.create_road_material(preset)
	return MapAuthoringTexturePresets.create_material(preset)


func _finish_editor_change() -> void:
	notify_property_list_changed()
	emit_changed()
