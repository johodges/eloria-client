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
##     the same source file, skeleton path and bone aliases.
##
## Animation resources are immutable during playback, so one library backing
## many AnimationPlayers is safe; per-actor playback state (current clip,
## speed_scale, seek position) lives on the player, not the library.

static var _libraries: Dictionary = {}

static func import_library(owner: Node, source_path: String,
		target_skeleton: Skeleton3D, bone_aliases := {},
		wanted_clips: PackedStringArray = PackedStringArray()) -> Dictionary:
	var result := {"player": null, "clips": PackedStringArray(),
		"errors": PackedStringArray()}
	if target_skeleton == null:
		result.errors.append("animation retarget skeleton missing")
		return result
	var skeleton_path := String(owner.get_path_to(target_skeleton))
	# The rig itself is part of the key: two models can sit at the same node
	# path and still expose different bones, and a retargeted library is only
	# reusable by a skeleton with the same bones in the same order.
	var cache_key := "%s|%s|%s|%s|%s" % [source_path, skeleton_path,
		_skeleton_signature(target_skeleton), JSON.stringify(bone_aliases),
		",".join(wanted_clips)]
	var cached: Dictionary = _libraries.get(cache_key, {}) as Dictionary
	if cached.is_empty():
		cached = _build(source_path, skeleton_path, target_skeleton, bone_aliases,
			wanted_clips)
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

## Drops every cached library. Call when leaving a session.
static func clear() -> void:
	_libraries.clear()

static func _skeleton_signature(skeleton: Skeleton3D) -> String:
	var names := PackedStringArray()
	for bone: int in skeleton.get_bone_count():
		names.append(skeleton.get_bone_name(bone))
	return "%d:%d" % [names.size(), hash(names)]

static func cached_library_count() -> int:
	return _libraries.size()

static func _build(source_path: String, skeleton_path: String,
		target_skeleton: Skeleton3D, bone_aliases: Dictionary,
		wanted_clips: PackedStringArray) -> Dictionary:
	var built := {"library": null, "clips": PackedStringArray(),
		"errors": PackedStringArray()}
	var source_scene := _load_gltf(source_path)
	if source_scene == null:
		built.errors.append("animation library load failed: " + source_path)
		return built
	var source_player := _find_player(source_scene)
	if source_player == null:
		built.errors.append("animation library has no AnimationPlayer")
		source_scene.free()
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
		target.loop_mode = source.loop_mode
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
	source_scene.free()
	built.library = library
	if built.clips.is_empty():
		built.errors.append("no animation tracks matched the target skeleton")
	return built

static func _load_gltf(path: String) -> Node:
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	if document.append_from_file(path, state) != OK:
		return null
	return document.generate_scene(state)

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
