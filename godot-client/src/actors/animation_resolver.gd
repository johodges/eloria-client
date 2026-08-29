class_name AnimationResolver
extends RefCounted

var action_to_clip: Dictionary
var command_to_action: Dictionary
var playback_speeds: Dictionary
## Metres of ground each locomotion clip covers per second when it plays at
## speed 1.0, measured from its planted foot. The clips animate in place, so
## this is what tells an actor how fast to run one for its own travel speed.
var stride_speeds: Dictionary
var fallback_action: StringName

func _init(config: Dictionary) -> void:
	action_to_clip = config.get("actions", {}).duplicate(true)
	command_to_action = config.get("serverCommands", {}).duplicate(true)
	playback_speeds = config.get("playbackSpeeds", {}).duplicate(true)
	stride_speeds = config.get("strideMetresPerSecond", {}).duplicate(true)
	fallback_action = StringName(config.get("fallbackAction", "idle"))

func action_for_command(command: int, combat_mode := false) -> StringName:
	var key := str(command)
	if command_to_action.has(key):
		return StringName(command_to_action[key])
	return &"combat_idle" if combat_mode and action_to_clip.has("combat_idle") else fallback_action

func clip_for_action(action: StringName) -> StringName:
	var value = action_to_clip.get(String(action), action_to_clip.get(String(fallback_action), ""))
	return StringName(value)

func playback_speed_for_action(action: StringName) -> float:
	return maxf(0.01, float(playback_speeds.get(String(action), 1.0)))

## Zero for actions that are not travel, which is the caller's signal to use
## the fixed playback speed instead.
func stride_speed_for_action(action: StringName) -> float:
	return maxf(0.0, float(stride_speeds.get(String(action), 0.0)))

## Every clip this resolver can ever ask an AnimationPlayer to play. The native
## animation importer uses it to rebuild only the clips an actor needs instead
## of the whole shared library.
func required_clips() -> PackedStringArray:
	var clips := PackedStringArray()
	for action in action_to_clip:
		var clip := str(action_to_clip[action])
		if not clip.is_empty() and not clips.has(clip):
			clips.append(clip)
	return clips

func validate(available_clips: PackedStringArray) -> Array[String]:
	var missing: Array[String] = []
	for action in action_to_clip:
		var clip := str(action_to_clip[action])
		if clip.is_empty() or not available_clips.has(clip):
			missing.append(str(action) + " -> " + clip)
	return missing
