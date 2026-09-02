extends SceneTree

## The walk froze mid-stride between steps: glTF cannot state that a clip
## loops, so every clip a runtime import produces is one-shot until the action
## map's loopingClips list says otherwise. This runs the real importer against
## the real shared library and checks the flags land on the rebuilt clips -
## and only on the declared ones, because stand and death rely on finishing.

var failures := 0

func _init() -> void:
	var config_file := FileAccess.open(
		"res://data/animations/luminous.json", FileAccess.READ)
	var resolver := AnimationResolver.new(
		JSON.parse_string(config_file.get_as_text()) as Dictionary)
	_expect(not resolver.looping_clips.is_empty(),
		"the action map declares its looping clips")

	# The library GLB holds clips but no skinned mesh, so the rig the clips
	# are rebuilt onto comes from a race model, the same way an actor does it.
	var library_path := ProjectSettings.globalize_path(
		"res://assets/actors/native/shared/Universal_Animation_Library.glb")
	var rig_path := ProjectSettings.globalize_path(
		"res://assets/actors/native/races/luminous_male.glb")
	var document := GLTFDocument.new()
	var state := GLTFState.new()
	_expect(document.append_from_file(rig_path, state) == OK,
		"the luminous rig parses")
	var scene := document.generate_scene(state)
	var holder := Node3D.new()
	root.add_child(holder)
	holder.add_child(scene)
	var skeleton: Skeleton3D = null
	for node in scene.find_children("*", "Skeleton3D", true, false):
		skeleton = node as Skeleton3D
		break
	_expect(skeleton != null, "the race model carries a rig")

	var imported := NativeAnimationImporter.import_library(holder, library_path,
		skeleton, {}, resolver.required_clips(), resolver.looping_clips)
	var player: AnimationPlayer = imported.player as AnimationPlayer
	_expect(player != null and Array(imported.errors).is_empty(),
		"the library imports onto the rig: " + ",".join(imported.errors))
	if player != null:
		for held_action: String in ["idle", "walk", "run", "combat_idle",
				"seated_idle"]:
			var clip := resolver.clip_for_action(StringName(held_action))
			_expect(player.has_animation(clip)
				and player.get_animation(clip).loop_mode == Animation.LOOP_LINEAR,
				"the %s clip %s imports looping" % [held_action, clip])
		for finishing_action: String in ["stand", "death", "pain"]:
			var clip := resolver.clip_for_action(StringName(finishing_action))
			_expect(player.has_animation(clip)
				and player.get_animation(clip).loop_mode == Animation.LOOP_NONE,
				"the %s clip %s imports one-shot" % [finishing_action, clip])
		# The freeze itself: a walk driven well past its own length must still
		# be playing, because a route is longer than one clip. A transition
		# driven the same way must have finished, because standing up twice is
		# not standing up.
		var walk_clip := resolver.clip_for_action(&"walk")
		player.play(walk_clip)
		player.advance(player.get_animation(walk_clip).length * 2.5)
		_expect(player.is_playing(),
			"a walk outlives its clip length instead of freezing mid-stride")
		var stand_clip := resolver.clip_for_action(&"stand")
		player.play(stand_clip)
		player.advance(player.get_animation(stand_clip).length * 2.5)
		_expect(not player.is_playing(),
			"a stand transition still finishes so idle can take over")
	NativeAnimationImporter.clear()
	print("animation looping tests: ",
		"PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _expect(condition: bool, label: String) -> void:
	if not condition:
		failures += 1
		push_error(label)
