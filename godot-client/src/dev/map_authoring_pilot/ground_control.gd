@tool
class_name MapAuthoringGroundControl
extends Node3D

@export var base_surface: MapAuthoringSurface

var _bound_surface: MapAuthoringSurface


func _ready() -> void:
	set_process(true)
	sync_surface_binding()


func _process(_delta: float) -> void:
	if base_surface != _bound_surface:
		sync_surface_binding()


func sync_surface_binding() -> void:
	if base_surface == _bound_surface:
		return
	if base_surface != null:
		base_surface = base_surface.duplicate(true) as MapAuthoringSurface
		base_surface.resource_local_to_scene = true
	_bound_surface = base_surface


func surface_signature() -> Array:
	sync_surface_binding()
	return base_surface.signature() if base_surface != null else []
