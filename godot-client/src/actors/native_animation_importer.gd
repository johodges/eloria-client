class_name NativeAnimationImporter
extends RefCounted

static func import_library(owner: Node, source_path: String,
		target_skeleton: Skeleton3D, bone_aliases := {}) -> Dictionary:
	var result := {"player": null, "clips": PackedStringArray(), "errors": PackedStringArray()}
	var source_scene := _load_gltf(source_path)
	if source_scene == null:
		result.errors.append("animation library load failed: " + source_path)
		return result
	var source_player := _find_player(source_scene)
	if source_player == null:
		result.errors.append("animation library has no AnimationPlayer")
		source_scene.free()
		return result
	var target_player := AnimationPlayer.new()
	target_player.name = "NativeAnimationPlayer"
	owner.add_child(target_player)
	var library := AnimationLibrary.new()
	target_player.add_animation_library("", library)
	var skeleton_path := owner.get_path_to(target_skeleton)
	for clip_name in source_player.get_animation_list():
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
			target.track_set_path(target_track, NodePath(str(skeleton_path) + ":" + bone))
			target.track_set_interpolation_type(target_track,
				source.track_get_interpolation_type(source_track))
			for key_index in source.track_get_key_count(source_track):
				target.track_insert_key(target_track,
					source.track_get_key_time(source_track, key_index),
					source.track_get_key_value(source_track, key_index),
					source.track_get_key_transition(source_track, key_index))
		if target.get_track_count() > 0:
			library.add_animation(clip_name, target)
			result.clips.append(String(clip_name))
	source_scene.free()
	result.player = target_player
	if result.clips.is_empty():
		result.errors.append("no animation tracks matched the target skeleton")
	return result

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
