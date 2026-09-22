extends SceneTree

const PILOT := preload("res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	if not Engine.is_editor_hint():
		push_error("map authoring pilot editor preview: Engine.is_editor_hint() is false")
		quit(1)
		return
	var pilot: Node = PILOT.instantiate()
	root.add_child(pilot)
	await process_frame
	await process_frame
	var preview := pilot.get_node_or_null("GeneratedPreview")
	var terrain := pilot.get_node_or_null("GeneratedPreview/Terrain")
	var bridge := pilot.get_node_or_null("GeneratedPreview/Bridge")
	var building := pilot.get_node_or_null("GeneratedPreview/Building")
	var overlay := pilot.get_node_or_null("GeneratedPreview/Walkability")
	if preview == null or terrain == null or bridge == null or building == null or overlay == null:
		push_error("map authoring pilot editor preview: generated subtree is incomplete")
		quit(1)
		return
	if overlay.visible:
		push_error("map authoring pilot editor preview: overlay should start hidden")
		quit(1)
		return
	var scenery := pilot.get_node_or_null("AuthoredScenery")
	var warm_light := pilot.get_node_or_null("AuthoredScenery/CabinLantern/WarmLight")
	var styled_rock := pilot.get_node_or_null("AuthoredScenery/ShoreRockWest") as MeshInstance3D
	if scenery == null or preview.is_ancestor_of(scenery) or warm_light == null:
		push_error("map authoring pilot editor preview: saved scenery/light separation is invalid")
		quit(1)
		return
	if styled_rock == null or styled_rock.material_override != pilot.visual_style.stone_material:
		push_error("map authoring pilot editor preview: authored scenery did not receive the saved style")
		quit(1)
		return
	print("map authoring pilot editor preview: PASS")
	quit(0)
