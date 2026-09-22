@tool
class_name MapAuthoringVisualStyle
extends Resource

## Compact texture choices for the disposable preview builders. Selectors are
## declared before their saved materials so Resource loading applies the saved,
## possibly hand-adjusted material after a selector has initialized its preset.

var _terrain_choices := {}
var _road_choices := {}
var _woodwork_choices := {}
var _stonework_choices := {}
var _roof_choices := {}

@export_enum("Custom", "Grass", "Worn earth", "Timber", "Stone", "Thatch",
	"Textile", "Canvas", "Metal", "Leather", "Hide", "Bone", "Crystal",
	"Cavern", "Slate") var terrain_texture := MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if terrain_texture == value:
			return
		_remember_choice(_terrain_choices, terrain_texture, terrain_material)
		terrain_texture = value
		terrain_material = _standard_choice(
			_terrain_choices, value, terrain_material)
		_finish_choice_change()

@export_enum("Custom", "Grass", "Worn earth", "Timber", "Stone", "Thatch",
	"Textile", "Canvas", "Metal", "Leather", "Hide", "Bone", "Crystal",
	"Cavern", "Slate") var road_texture := MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if road_texture == value:
			return
		_remember_choice(_road_choices, road_texture, worn_path_material)
		road_texture = value
		worn_path_material = _road_choice(_road_choices, value, worn_path_material)
		_finish_choice_change()

@export_enum("Custom", "Grass", "Worn earth", "Timber", "Stone", "Thatch",
	"Textile", "Canvas", "Metal", "Leather", "Hide", "Bone", "Crystal",
	"Cavern", "Slate") var woodwork_texture := MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if woodwork_texture == value:
			return
		_remember_choice(_woodwork_choices, woodwork_texture, timber_material)
		woodwork_texture = value
		timber_material = _standard_choice(
			_woodwork_choices, value, timber_material)
		_finish_choice_change()

@export_enum("Custom", "Grass", "Worn earth", "Timber", "Stone", "Thatch",
	"Textile", "Canvas", "Metal", "Leather", "Hide", "Bone", "Crystal",
	"Cavern", "Slate") var stonework_texture := MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if stonework_texture == value:
			return
		_remember_choice(_stonework_choices, stonework_texture, stone_material)
		stonework_texture = value
		stone_material = _standard_choice(
			_stonework_choices, value, stone_material)
		_finish_choice_change()

@export_enum("Custom", "Grass", "Worn earth", "Timber", "Stone", "Thatch",
	"Textile", "Canvas", "Metal", "Leather", "Hide", "Bone", "Crystal",
	"Cavern", "Slate") var roof_texture := MapAuthoringTexturePresets.CUSTOM:
	set(value):
		if roof_texture == value:
			return
		_remember_choice(_roof_choices, roof_texture, slate_material)
		roof_texture = value
		slate_material = _standard_choice(_roof_choices, value, slate_material)
		_finish_choice_change()

@export var show_advanced_materials := false:
	set(value):
		if show_advanced_materials == value:
			return
		show_advanced_materials = value
		notify_property_list_changed()
		emit_changed()

## Saved material references remain the builder API and serialization format.
## They are hidden from the Inspector unless Custom or Advanced is selected.
@export var terrain_material: Material
@export var worn_path_material: Material
@export var timber_material: Material
@export var stone_material: Material
@export var slate_material: Material
@export var water_material: Material


func _validate_property(property: Dictionary) -> void:
	var property_name := StringName(property.name)
	var visible := show_advanced_materials
	match property_name:
		&"terrain_material":
			visible = visible or terrain_texture == MapAuthoringTexturePresets.CUSTOM
		&"worn_path_material":
			visible = visible or road_texture == MapAuthoringTexturePresets.CUSTOM
		&"timber_material":
			visible = visible or woodwork_texture == MapAuthoringTexturePresets.CUSTOM
		&"stone_material":
			visible = visible or stonework_texture == MapAuthoringTexturePresets.CUSTOM
		&"slate_material":
			visible = visible or roof_texture == MapAuthoringTexturePresets.CUSTOM
		&"water_material":
			pass
		_:
			return
	if not visible:
		property.usage = int(property.usage) & ~PROPERTY_USAGE_EDITOR


func _finish_choice_change() -> void:
	notify_property_list_changed()
	emit_changed()


func _remember_choice(choices: Dictionary, preset: String, material: Material) -> void:
	if material != null:
		choices[preset] = material


func _standard_choice(choices: Dictionary, preset: String,
		current: Material) -> Material:
	if choices.has(preset):
		return choices[preset]
	if preset == MapAuthoringTexturePresets.CUSTOM:
		return current
	return MapAuthoringTexturePresets.create_material(preset)


func _road_choice(choices: Dictionary, preset: String,
		current: Material) -> Material:
	if choices.has(preset):
		return choices[preset]
	if preset == MapAuthoringTexturePresets.CUSTOM:
		return current
	return MapAuthoringTexturePresets.create_road_material(preset)
