extends "res://src/app/main.gd"
## Benchmark-only instrumentation around the existing presentation pipeline.
## Nothing in the shipping client pays for these timers.

var benchmark_ground_enabled := true
var benchmark_overhead_enabled := true
var benchmark_animation_enabled := true
var benchmark_attribution_enabled := false
var _benchmark_usec: Dictionary = {}
var _benchmark_calls: Dictionary = {}
var _benchmark_values: Dictionary = {}
var _benchmark_skeleton_frames: Dictionary = {}
var _benchmark_max_skeleton_updates_per_actor := 0
var _benchmark_attribution_attachment: Dictionary = {}


func benchmark_reset_frame() -> void:
	_benchmark_usec.clear()
	_benchmark_calls.clear()
	_benchmark_values.clear()
	_benchmark_max_skeleton_updates_per_actor = 0


func benchmark_take_frame() -> Dictionary:
	return {
		"microseconds": _benchmark_usec.duplicate(),
		"calls": _benchmark_calls.duplicate(),
		"values": _benchmark_values.duplicate(),
		"attribution": {
			"maximumSkeletonUpdatesPerActor":
				_benchmark_max_skeleton_updates_per_actor,
		},
	}


func _benchmark_add(label: StringName, started: int) -> void:
	_benchmark_usec[label] = int(_benchmark_usec.get(label, 0)) \
		+ Time.get_ticks_usec() - started
	_benchmark_calls[label] = int(_benchmark_calls.get(label, 0)) + 1


func _process(delta: float) -> void:
	if not benchmark_attribution_enabled:
		super._process(delta)
		return
	var started := Time.get_ticks_usec()
	super._process(delta)
	_benchmark_values[&"process_delta_milliseconds"] = delta * 1000.0
	_benchmark_add(&"main_process_inclusive", started)


## Installs diagnostic observers only after a benchmark fixture is complete.
## The production combat callback may be replaced only when it is the final
## connection, so disconnect/reconnect leaves its relative order unchanged.
func benchmark_attach_attribution(nodes: Dictionary) -> Dictionary:
	_benchmark_skeleton_frames.clear()
	var plans: Array[Dictionary] = []
	# Preflight the complete fixture before touching any connection. A failure
	# therefore leaves production callback ordering and targets unchanged.
	for raw_id: Variant in nodes:
		var actor := nodes[raw_id] as ReplicatedActor3D
		if not is_instance_valid(actor):
			continue
		var skeleton := actor.get_skeleton()
		if skeleton == null:
			continue
		var id := int(raw_id)
		var combat := actor.combat_presentation
		var plan := {"id": id, "skeleton": skeleton, "combat": combat,
			"direct": Callable(), "flags": 0}
		if combat != null:
			var direct := Callable(combat, "update_pose")
			var connections := skeleton.skeleton_updated.get_connections()
			var direct_index := -1
			var direct_flags := 0
			for index: int in range(connections.size()):
				var connection := connections[index] as Dictionary
				if connection.get("callable") == direct:
					direct_index = index
					direct_flags = int(connection.get("flags", 0))
					break
			if direct_index < 0:
				return {"ok": false,
					"error": "actor %d combat callback is not connected" % id}
			if direct_index != connections.size() - 1:
				return {"ok": false,
					"error": ("actor %d combat callback is connection %d of %d; "
						+ "refusing to change signal order") % [
						id, direct_index, connections.size()]}
			plan["direct"] = direct
			plan["flags"] = direct_flags
		plans.append(plan)

	var combat_delegates := 0
	var passive_observers := 0
	var applied: Array[Dictionary] = []
	for plan: Dictionary in plans:
		var skeleton := plan["skeleton"] as Skeleton3D
		var id := int(plan["id"])
		var combat := plan["combat"] as CombatPresentation3D
		if combat != null:
			var direct := plan["direct"] as Callable
			skeleton.skeleton_updated.disconnect(direct)
			var delegated := Callable(self,
				"_benchmark_combat_skeleton_updated").bind(id, combat)
			var connected := skeleton.skeleton_updated.connect(
				delegated, int(plan["flags"]))
			if connected != OK:
				skeleton.skeleton_updated.connect(direct, int(plan["flags"]))
				_benchmark_rollback_attribution(applied)
				return {"ok": false,
					"error": "actor %d timed combat delegate failed: %d" % [
						id, connected]}
			applied.append({"skeleton": skeleton, "installed": delegated,
				"direct": direct, "flags": int(plan["flags"])})
			combat_delegates += 1
		else:
			var observer := Callable(self,
				"_benchmark_skeleton_updated").bind(id)
			var connected := skeleton.skeleton_updated.connect(observer)
			if connected != OK:
				_benchmark_rollback_attribution(applied)
				return {"ok": false,
					"error": "actor %d skeleton observer failed: %d" % [id, connected]}
			applied.append({"skeleton": skeleton, "installed": observer,
				"direct": Callable(), "flags": 0})
			passive_observers += 1
	_benchmark_attribution_attachment = {
		"ok": true, "actors": plans.size(),
		"combatSignalDelegates": combat_delegates,
		"passiveSkeletonObservers": passive_observers,
		"combatSignalOrderPolicy":
			"replace only a final direct callback with a final timed delegate",
	}
	return _benchmark_attribution_attachment.duplicate(true)


func _benchmark_rollback_attribution(applied: Array[Dictionary]) -> void:
	for index: int in range(applied.size() - 1, -1, -1):
		var record := applied[index]
		var skeleton := record["skeleton"] as Skeleton3D
		var installed := record["installed"] as Callable
		if skeleton.skeleton_updated.is_connected(installed):
			skeleton.skeleton_updated.disconnect(installed)
		var direct := record["direct"] as Callable
		if direct.is_valid():
			skeleton.skeleton_updated.connect(direct, int(record["flags"]))


func _benchmark_note_skeleton(actor_id: int) -> void:
	var frame := Engine.get_process_frames()
	var previous := _benchmark_skeleton_frames.get(actor_id, {}) as Dictionary
	var count := int(previous.get("count", 0)) + 1 \
		if int(previous.get("frame", -1)) == frame else 1
	_benchmark_skeleton_frames[actor_id] = {"frame": frame, "count": count}
	_benchmark_calls[&"skeleton_updated"] = int(
		_benchmark_calls.get(&"skeleton_updated", 0)) + 1
	if count == 1:
		_benchmark_calls[&"unique_skeletons_updated"] = int(
			_benchmark_calls.get(&"unique_skeletons_updated", 0)) + 1
	_benchmark_max_skeleton_updates_per_actor = maxi(
		_benchmark_max_skeleton_updates_per_actor, count)


func _benchmark_skeleton_updated(actor_id: int) -> void:
	_benchmark_note_skeleton(actor_id)


func _benchmark_combat_skeleton_updated(actor_id: int,
		combat: CombatPresentation3D) -> void:
	_benchmark_note_skeleton(actor_id)
	var started := Time.get_ticks_usec()
	combat.update_pose()
	_benchmark_add(&"combat_pose_from_skeleton", started)


func _benchmark_count_event(label: StringName) -> void:
	if benchmark_attribution_enabled:
		_benchmark_calls[label] = int(_benchmark_calls.get(label, 0)) + 1


func _on_missile_fired(shot: Dictionary) -> void:
	if benchmark_attribution_enabled:
		var source := actor_nodes.get(int(shot.get("source_actor_id", -1)))
		if is_instance_valid(source):
			_benchmark_count_event(&"mirrored_effect_setter_missile")
	super._on_missile_fired(shot)


func _on_ground_missile_fired(shot: Dictionary) -> void:
	if benchmark_attribution_enabled:
		var source := actor_nodes.get(int(shot.get("source_actor_id", -1)))
		if is_instance_valid(source):
			_benchmark_count_event(&"mirrored_effect_setter_ground_missile")
	super._on_ground_missile_fired(shot)


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
	if not benchmark_attribution_enabled:
		super._on_actor_animation_requested(animation)
		if not benchmark_animation_enabled:
			_benchmark_freeze_actor(actor_nodes.get(
				int(animation.get("actor_id", -1))) as ReplicatedActor3D)
		return
	var actor_id := int(animation.get("actor_id", -1))
	var actor := actor_nodes.get(actor_id) as ReplicatedActor3D
	var accepted := is_instance_valid(actor) and not (
		str(animation.get("action", "")) == "cast_exit"
		and actor.current_action not in [&"cast_channel", &"cast_channel_enter"])
	if accepted:
		_benchmark_count_event(&"mirrored_effect_setter_animation")
	super._on_actor_animation_requested(animation)
	if accepted and animation.has("power") and actor.combat_presentation != null:
		_benchmark_count_event(&"mirrored_spell_power")
	if not benchmark_animation_enabled:
		_benchmark_freeze_actor(actor_nodes.get(
			actor_id) as ReplicatedActor3D)


func _on_special_effect_requested(effect: Dictionary) -> void:
	if not benchmark_attribution_enabled:
		super._on_special_effect_requested(effect)
		if not benchmark_animation_enabled:
			_benchmark_freeze_actor(actor_nodes.get(
				int(effect.get("actor_id", -1))) as ReplicatedActor3D)
		return
	var actor_id := int(effect.get("actor_id", -1))
	var source := actor_nodes.get(actor_id) as ReplicatedActor3D
	var action := SpellPresentation.action_for_effect(int(effect.get("effect", -1)))
	if is_instance_valid(source) and not action.is_empty():
		_benchmark_count_event(&"mirrored_effect_setter_special")
	super._on_special_effect_requested(effect)
	if _effects_enabled and is_instance_valid(source) \
			and source.combat_presentation != null \
			and super._actor_effect_position(actor_id) is Vector3 \
			and action == source.current_action:
		_benchmark_count_event(&"mirrored_spell_palette")
	if not benchmark_animation_enabled:
		_benchmark_freeze_actor(actor_nodes.get(
			actor_id) as ReplicatedActor3D)
