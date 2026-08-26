class_name ActorReducer
extends RefCounted

static func apply_command(actor: Dictionary, actor_command: int) -> Dictionary:
	var next: Dictionary = actor.duplicate(true)
	var step: Vector2i = EloriaProtocol.actor_command_step(actor_command)
	next["x"] = int(next.get("x", 0)) + step.x
	next["y"] = int(next.get("y", 0)) + step.y
	next["command"] = actor_command
	if actor_command == 13:
		next["sitting"] = true
	elif actor_command == 14:
		next["sitting"] = false
	return next
