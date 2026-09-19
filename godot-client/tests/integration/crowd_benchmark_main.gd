extends "res://src/app/main.gd"
## Benchmark-only instrumentation around the existing presentation pipeline.
## Nothing in the shipping client pays for these timers.

var benchmark_ground_enabled := true
var benchmark_overhead_enabled := true
var benchmark_animation_enabled := true
var _benchmark_usec: Dictionary = {}
var _benchmark_calls: Dictionary = {}


func benchmark_reset_frame() -> void:
	_benchmark_usec.clear()
	_benchmark_calls.clear()


func benchmark_take_frame() -> Dictionary:
	return {
		"microseconds": _benchmark_usec.duplicate(),
		"calls": _benchmark_calls.duplicate(),
	}


func _benchmark_add(label: StringName, started: int) -> void:
	_benchmark_usec[label] = int(_benchmark_usec.get(label, 0)) \
		+ Time.get_ticks_usec() - started
	_benchmark_calls[label] = int(_benchmark_calls.get(label, 0)) + 1


func _sync_world(changed: Variant = null) -> void:
	var started := Time.get_ticks_usec()
	super._sync_world(changed)
	_benchmark_add(&"sync_world_inclusive", started)


func _present_actor(id: Variant) -> void:
	var ground_before := int(_benchmark_usec.get(&"ground", 0))
	var started := Time.get_ticks_usec()
	super._present_actor(id)
	var actor_value: Variant = actor_nodes.get(id)
	if not benchmark_overhead_enabled:
		if is_instance_valid(actor_value):
			(actor_value as ReplicatedActor3D).set_nameplate_visible(false)
			(actor_value as ReplicatedActor3D).set_health_visible(false)
	if not benchmark_animation_enabled:
		_benchmark_freeze_actor(actor_value as ReplicatedActor3D)
	var inclusive := Time.get_ticks_usec() - started
	var ground_delta := int(_benchmark_usec.get(&"ground", 0)) - ground_before
	_benchmark_usec[&"present_inclusive"] = int(
		_benchmark_usec.get(&"present_inclusive", 0)) + inclusive
	_benchmark_usec[&"present_excluding_ground"] = int(
		_benchmark_usec.get(&"present_excluding_ground", 0)) \
		+ maxi(0, inclusive - ground_delta)
	_benchmark_calls[&"present"] = int(_benchmark_calls.get(&"present", 0)) + 1


func _place_actor_on_surface(actor: ReplicatedActor3D, force := false,
		fallback_height := NAN) -> void:
	if not benchmark_ground_enabled:
		return
	var started := Time.get_ticks_usec()
	super._place_actor_on_surface(actor, force, fallback_height)
	_benchmark_add(&"ground", started)


func _sync_overhead_health() -> void:
	if not benchmark_overhead_enabled:
		return
	var started := Time.get_ticks_usec()
	super._sync_overhead_health()
	_benchmark_add(&"overhead", started)


func _update_animation_gate(delta: float) -> void:
	var refresh_before := _animation_gate_refresh_msec
	var started := Time.get_ticks_usec()
	super._update_animation_gate(delta)
	if not benchmark_animation_enabled and refresh_before != _animation_gate_refresh_msec:
		for actor_value: Variant in actor_nodes.values():
			if is_instance_valid(actor_value):
				_benchmark_freeze_actor(actor_value as ReplicatedActor3D)
	_benchmark_add(&"animation_gate", started)


func _benchmark_freeze_actor(actor: ReplicatedActor3D) -> void:
	if actor != null and is_instance_valid(actor.animation_player):
		actor.animation_player.active = false


func _on_actor_animation_requested(animation: Dictionary) -> void:
	super._on_actor_animation_requested(animation)
	if not benchmark_animation_enabled:
		_benchmark_freeze_actor(actor_nodes.get(
			int(animation.get("actor_id", -1))) as ReplicatedActor3D)


func _on_special_effect_requested(effect: Dictionary) -> void:
	super._on_special_effect_requested(effect)
	if not benchmark_animation_enabled:
		_benchmark_freeze_actor(actor_nodes.get(
			int(effect.get("actor_id", -1))) as ReplicatedActor3D)
