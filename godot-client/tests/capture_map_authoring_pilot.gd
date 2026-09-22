extends SceneTree

const PILOT := preload("res://src/dev/map_authoring_pilot/map_authoring_pilot.tscn")


func _init() -> void:
	call_deferred("_capture")


func _capture() -> void:
	var pilot: Node = PILOT.instantiate()
	root.add_child(pilot)
	for unused in 12:
		await process_frame
	var destination := "res://docs/images/map-authoring-pilot.png"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://docs/images"))
	var image := root.get_texture().get_image()
	var error := image.save_png(ProjectSettings.globalize_path(destination))
	if error != OK:
		push_error("map authoring pilot capture failed: %s" % error_string(error))
		quit(1)
		return
	print("map authoring pilot capture: ", ProjectSettings.globalize_path(destination))
	quit(0)
