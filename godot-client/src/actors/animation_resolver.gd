class_name AnimationResolver
extends RefCounted

var action_to_clip: Dictionary
var command_to_action: Dictionary
var fallback_action: StringName

func _init(config: Dictionary) -> void:
	action_to_clip = config.get("actions", {}).duplicate(true)
	command_to_action = config.get("serverCommands", {}).duplicate(true)
	fallback_action = StringName(config.get("fallbackAction", "idle"))

func action_for_command(command: int, combat_mode := false) -> StringName:
	var key := str(command)
	if command_to_action.has(key):
		return StringName(command_to_action[key])
	return &"combat_idle" if combat_mode and action_to_clip.has("combat_idle") else fallback_action

func clip_for_action(action: StringName) -> StringName:
	var value = action_to_clip.get(String(action), action_to_clip.get(String(fallback_action), ""))
	return StringName(value)

func validate(available_clips: PackedStringArray) -> Array[String]:
	var missing: Array[String] = []
	for action in action_to_clip:
		var clip := str(action_to_clip[action])
		if clip.is_empty() or not available_clips.has(clip):
			missing.append(str(action) + " -> " + clip)
	return missing
