class_name NativeAnimationImporter
extends RefCounted
## Retargets a native glTF animation library onto an actor's skeleton.
##
## The shared universal library ships 162 clips built from roughly 226 000
## keyframes. Rebuilding all of them for every actor - once through the glTF
## parser and once again key by key through GDScript - was by far the largest
## cost of spawning an actor, and it was paid again for every duplicate of the
## same model.
##
## Two changes remove that cost without altering a single frame of playback:
##
##   * only the clips the actor's action map can actually request are rebuilt,
##     which is 18 of the 162 for the current maps, and
##   * the finished AnimationLibrary is cached and shared by every actor using
##     the same source file, skeleton path and bone aliases, and the parsed
##     source file itself is kept, so a second rig never re-parses it.
##
## Animation resources are immutable during playback, so one library backing
## many AnimationPlayers is safe; per-actor playback state (current clip,
## speed_scale, seek position) lives on the player, not the library.

static var _libraries: Dictionary = {}
## The parsed library scenes, one per source file, kept for the session. A
## retarget used to parse the 11 MB file again for every rig it met and free
## the result. The parse now happens once - on a worker thread when `prewarm`
## had the chance - and every rig reads from it.
static var _sources: Dictionary = {}
static var _prewarming: Dictionary = {}

static func import_library(owner: Node, source_path: String,
		target_skeleton: Skeleton3D, bone_aliases := {},
		wanted_clips: PackedStringArray = PackedStringArray(),
		looping_clips: PackedStringArray = PackedStringArray()) -> Dictionary:
	var result := {"player": null, "clips": PackedStringArray(),
		"errors": PackedStringArray()}
	if target_skeleton == null:
		result.errors.append("animation retarget skeleton missing")
		return result
	var skeleton_path := String(owner.get_path_to(target_skeleton))
	# The rig itself is part of the key: two models can sit at the same node
	# path and still expose different bones, and a retargeted library is only
	# reusable by a skeleton with the same bones in the same order.
	var cache_key := "%s|%s|%s|%s|%s|%s" % [source_path, skeleton_path,
		_skeleton_signature(target_skeleton), JSON.stringify(bone_aliases),
		",".join(wanted_clips), ",".join(looping_clips)]
	var cached: Dictionary = _libraries.get(cache_key, {}) as Dictionary
	if cached.is_empty():
		cached = _build(source_path, skeleton_path, target_skeleton, bone_aliases,
			wanted_clips, looping_clips)
		_libraries[cache_key] = cached
	result.errors.append_array(cached.get("errors", PackedStringArray()))
	var library: AnimationLibrary = cached.get("library") as AnimationLibrary
	if library == null:
		return result
	var target_player := AnimationPlayer.new()
	target_player.name = "NativeAnimationPlayer"
	owner.add_child(target_player)
	target_player.add_animation_library("", library)
	result.player = target_player
	result.clips = cached.get("clips", PackedStringArray())
	return result

## Drops every cached library and parsed source. Call when leaving a session.
static func clear() -> void:
	_libraries.clear()
	for path_value: Variant in _prewarming:
		var parsed: Variant = (_prewarming[path_value] as Thread).wait_to_finish()
		if parsed is Node:
			(parsed as Node).free()
	_prewarming.clear()
	for scene_value: Variant in _sources.values():
		if is_instance_valid(scene_value):
			(scene_value as Node).free()
	_sources.clear()

## Parses `source_path` on a worker thread, so the first actor to need it
## finds the scene ready instead of paying for the parse on the main thread
## the moment it arrives. Nothing is parsed twice: a path already parsed, or
## already parsing, is left alone.
static func prewarm(source_path: String) -> void:
	if source_path.is_empty() or _sources.has(source_path) or _prewarming.has(source_path):
		return
	var thread := Thread.new()
	if thread.start(_parse_library.bind(source_path)) == OK:
		_prewarming[source_path] = thread

static func is_prewarming(source_path: String) -> bool:
	return _prewarming.has(source_path)

static func has_source(source_path: String) -> bool:
	return is_instance_valid(_sources.get(source_path))

## The parsed scene for `source_path`: the prewarm's result, waited for if it
## is still running, or a parse on the spot. Owned here; callers must not
## free it.
static func _source_scene(source_path: String) -> Node:
	var held: Variant = _sources.get(source_path)
	if is_instance_valid(held):
		return held as Node
	var scene: Node = null
	if _prewarming.has(source_path):
		var thread: Thread = _prewarming[source_path] as Thread
		_prewarming.erase(source_path)
		scene = thread.wait_to_finish() as Node
	if scene == null:
		scene = _parse_library(source_path)
	if scene != null:
		_sources[source_path] = scene
	return scene

## The glTF parse itself. Safe off the main thread: it builds resources and
## nodes that belong to no tree.
static func _parse_library(path: String) -> Node:
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_file(path, state) != OK:
		return null
	return document.generate_scene(state)

static func _skeleton_signature(skeleton: Skeleton3D) -> String:
	var names := PackedStringArray()
	for bone: int in skeleton.get_bone_count():
		names.append(skeleton.get_bone_name(bone))
	return "%d:%d" % [names.size(), hash(names)]

static func cached_library_count() -> int:
	return _libraries.size()

static func _build(source_path: String, skeleton_path: String,
		target_skeleton: Skeleton3D, bone_aliases: Dictionary,
		wanted_clips: PackedStringArray,
		looping_clips: PackedStringArray) -> Dictionary:
	var built := {"library": null, "clips": PackedStringArray(),
		"errors": PackedStringArray()}
	var source_scene := _source_scene(source_path)
	if source_scene == null:
		built.errors.append("animation library load failed: " + source_path)
		return built
	var source_player := _find_player(source_scene)
	if source_player == null:
		built.errors.append("animation library has no AnimationPlayer")
		return built
	var library := AnimationLibrary.new()
	# An empty request means "everything the file offers"; the actor path always
	# passes the clips its action map can reach.
	var filter_clips := not wanted_clips.is_empty()
	for clip_name in source_player.get_animation_list():
		if filter_clips and not wanted_clips.has(String(clip_name)):
			continue
		var source := source_player.get_animation(clip_name)
		var target := Animation.new()
		target.length = source.length
		# glTF cannot state that a clip loops, so every runtime-parsed clip
		# arrives one-shot; the action map is where the cycles are declared.
		target.loop_mode = Animation.LOOP_LINEAR \
			if looping_clips.has(String(clip_name)) else source.loop_mode
		for source_track in source.get_track_count():
			var source_bone := _track_bone(source.track_get_path(source_track))
			var bone := str(bone_aliases.get(source_bone, source_bone))
			if bone.is_empty() or target_skeleton.find_bone(bone) < 0:
				continue
			var target_track := target.add_track(source.track_get_type(source_track))
			target.track_set_path(target_track, NodePath(skeleton_path + ":" + bone))
			target.track_set_interpolation_type(target_track,
				source.track_get_interpolation_type(source_track))
			for key_index in source.track_get_key_count(source_track):
				target.track_insert_key(target_track,
					source.track_get_key_time(source_track, key_index),
					source.track_get_key_value(source_track, key_index),
					source.track_get_key_transition(source_track, key_index))
		if target.get_track_count() > 0:
			library.add_animation(clip_name, target)
			built.clips.append(String(clip_name))
	built.library = library
	if built.clips.is_empty():
		built.errors.append("no animation tracks matched the target skeleton")
	return built

static func _find_player(root: Node) -> AnimationPlayer:
	if root is AnimationPlayer:
		return root
	for node in root.find_children("*", "AnimationPlayer", true, false):
		return node as AnimationPlayer
	return null

static func _track_bone(path: NodePath) -> String:
	var subnames := path.get_concatenated_subnames()
	if not subnames.is_empty():
		return subnames.get_slice(":", subnames.get_slice_count(":") - 1)
	var node_path := String(path).get_slice(":", 0)
	return node_path.get_file()
