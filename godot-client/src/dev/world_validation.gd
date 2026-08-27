extends Node3D

@onready var loader: WorldLoader = %WorldLoader
@onready var status: Label = %Status

func _ready() -> void:
	loader.load_started.connect(func(path: String): status.text = "Loading " + path)
	loader.load_failed.connect(func(errors: Array[String]): status.text = "FAILED\n" + "\n".join(errors))
	loader.load_completed.connect(_on_loaded)
	var path := ProjectSettings.globalize_path(
		"res://../eloria-assets/maps/four-gates-city/four-gates-city.json")
	loader.load_world(path)

func _on_loaded(manifest: WorldManifest) -> void:
	status.text = "LOADED: " + manifest.asset_id()
	if not manifest.warnings.is_empty():
		status.text += "\nWARNINGS:\n" + "\n".join(manifest.warnings)
	var collision: Node = loader.world_root.find_child(
		"NavigationSurfaceCollision", false, false)
	if not collision is StaticBody3D or collision.get_child_count() == 0:
		push_error("world validation: Navigation surface collision missing")
		return
	print("world validation: navigation surface collision PASS")
