@tool
extends EditorPlugin

const Catalog := preload("res://addons/map_authoring_workspace/territory_catalog.gd")
const Dock := preload("res://addons/map_authoring_workspace/territory_dock.gd")
const Preview := preload("res://addons/map_authoring_workspace/reference_preview.gd")

var _catalog := Catalog.new()
var _entries: Array[Dictionary] = []
var _dock: EditorDock
var _host: MapAuthoringReferencePreview
var _active_root: Node3D
var _elapsed := 0.0


func _enter_tree() -> void:
	_dock = Dock.new()
	_dock.open_requested.connect(_open_scene)
	_dock.references_changed.connect(_show_references)
	_dock.refresh_requested.connect(_reload_sources)
	add_dock(_dock)
	scene_changed.connect(_on_scene_changed)
	set_process(true)
	_reload_sources()
	_on_scene_changed(get_editor_interface().get_edited_scene_root())


func _exit_tree() -> void:
	_remove_host()
	if _dock != null:
		remove_dock(_dock)
		_dock.queue_free()
		_dock = null


func _process(delta: float) -> void:
	_elapsed += delta
	if _elapsed < 0.75:
		return
	_elapsed = 0.0
	if _host != null:
		_host.refresh_if_changed()


func _reload_sources() -> void:
	var selected: PackedStringArray = _dock.selected_reference_ids() \
		if _dock != null else PackedStringArray()
	_entries = _catalog.entries()
	var active_id := String(_active_root.get("region_id")) if _active_root != null else ""
	_dock.configure(_entries, active_id, selected)
	if not _catalog.errors.is_empty():
		_dock.show_status("Catalog error: " + " ".join(_catalog.errors))
		return
	if _host != null:
		_host.clear_source_cache()
		_show_references(selected)


func _on_scene_changed(scene_root: Node) -> void:
	_remove_host()
	_active_root = scene_root as Node3D if scene_root is Node3D and \
		scene_root.has_method("export_snapshot") else null
	var active_id := String(_active_root.get("region_id")) if _active_root != null else ""
	_dock.configure(_entries, active_id)
	if _active_root == null:
		return
	var entry := _catalog.find(_entries, active_id)
	if entry.is_empty() or not bool(entry.editable):
		_dock.show_status("This scene is not a complete catalogued authored territory.")
		return
	var active_error := _catalog.active_scene_error(_active_root, entry)
	if not active_error.is_empty():
		_dock.show_status(active_error + " Expected: %s" % String(entry.scene_path))
		return
	_host = Preview.new()
	_active_root.add_child(_host, false, Node.INTERNAL_MODE_FRONT)
	_host.configure(_active_root, entry)
	_host.status_changed.connect(_dock.show_status)


func _remove_host() -> void:
	if _host == null:
		return
	_host.clear()
	if is_instance_valid(_host.get_parent()):
		_host.get_parent().remove_child(_host)
	_host.queue_free()
	_host = null


func _open_scene(path: String) -> void:
	if path.is_empty() or not ResourceLoader.exists(path):
		_dock.show_status("Authored scene is unavailable: %s" % path)
		return
	get_editor_interface().open_scene_from_path(path)
	_dock.show_status("Opening saved authored scene: %s" % path)


func _show_references(ids: PackedStringArray) -> void:
	if _host == null:
		_dock.show_status("Open an authored territory before showing references.")
		return
	var references: Array[Dictionary] = []
	for id in ids:
		var entry := _catalog.find(_entries, id)
		if not entry.is_empty():
			references.append(entry)
	_host.set_references(references)
