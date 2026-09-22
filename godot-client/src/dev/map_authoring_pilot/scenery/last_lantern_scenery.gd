@tool
class_name LastLanternScenery
extends Node3D

## Saved, hand-placed cosmetic dressing for the map-authoring pilot. These nodes
## stay outside GeneratedPreview so transforms and lighting remain scene data.

var _visual_style: MapAuthoringVisualStyle


func _ready() -> void:
	if get_parent() != null and "visual_style" in get_parent():
		apply_visual_style(get_parent().visual_style)


func apply_visual_style(style: MapAuthoringVisualStyle) -> void:
	_visual_style = style
	_apply_style(self)


func _apply_style(node: Node) -> void:
	if node is MeshInstance3D and node.has_meta("style_slot"):
		var mesh_instance := node as MeshInstance3D
		if _visual_style == null:
			mesh_instance.material_override = null
		else:
			match String(node.get_meta("style_slot")):
				"timber":
					mesh_instance.material_override = _visual_style.timber_material
				"stone":
					mesh_instance.material_override = _visual_style.stone_material
				"slate":
					mesh_instance.material_override = _visual_style.slate_material
	for child in node.get_children():
		_apply_style(child)
