extends Node

signal state_changed(path: StringName)
signal login_succeeded
signal login_failed(message: String)
signal character_created
signal character_creation_failed(message: String)

var connection_state := "disconnected"
var authenticated := false
var local_actor_id := -1
var current_map := ""
var actors: Dictionary = {}
var inventory: Dictionary = {}
var inventory_text := ""
var inventory_cooldowns: Dictionary = {}
var stats: Dictionary = {}
var chat_lines: Array[Dictionary] = []
var selected_actor_id := -1
var npc_dialogue: Dictionary = {"open": false, "name": "", "portrait": 0,
	"text": "", "options": []}
var unknown_packet_count := 0
var recent_protocol_errors: Array[String] = []

func _ready() -> void:
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.packet_received.connect(_on_packet)

func _on_connection_state_changed(value: String) -> void:
	connection_state = value
	if value == "disconnected":
		authenticated = false
		local_actor_id = -1
		actors.clear()
		inventory.clear()
		inventory_text = ""
		inventory_cooldowns.clear()
		stats.clear()
		chat_lines.clear()
		current_map = ""
		selected_actor_id = -1
		npc_dialogue = {"open": false, "name": "", "portrait": 0, "text": "", "options": []}
	state_changed.emit(&"connection")

func _on_packet(command: int, payload: PackedByteArray) -> void:
	var event := EloriaProtocol.decode_server(command, payload)
	match event.type:
		"login_ok":
			authenticated = true
			login_succeeded.emit()
			state_changed.emit(&"authentication")
		"login_error":
			authenticated = false
			login_failed.emit(event.message)
			state_changed.emit(&"authentication")
		"create_character_ok":
			character_created.emit()
		"create_character_error":
			character_creation_failed.emit(event.message)
		"you_are":
			local_actor_id = event.actor_id
			state_changed.emit(&"local_actor")
		"change_map":
			current_map = event.map_name
			actors.clear()
			selected_actor_id = -1
			npc_dialogue = {"open": false, "name": "", "portrait": 0,
				"text": "", "options": []}
			state_changed.emit(&"map")
		"actor_spawn":
			actors[event.actor_id] = event
			state_changed.emit(&"actors")
		"remove_actor":
			actors.erase(event.actor_id)
			if selected_actor_id == int(event.actor_id):
				selected_actor_id = -1
				state_changed.emit(&"selection")
			state_changed.emit(&"actors")
		"clear_actors":
			actors.clear()
			state_changed.emit(&"actors")
		"actor_commands":
			for raw_command_event: Variant in event.commands:
				var command_event: Dictionary = raw_command_event as Dictionary
				var actor_id: int = int(command_event.get("actor_id", -1))
				if actors.has(actor_id):
					var actor_command: int = int(command_event.get("command", 0))
					var actor: Dictionary = actors[actor_id]
					actors[actor_id] = ActorReducer.apply_command(actor, actor_command)
			state_changed.emit(&"actors")
		"actor_wear":
			var wear_actor_id: int = int(event.actor_id)
			if actors.has(wear_actor_id):
				var wear_actor: Dictionary = actors[wear_actor_id]
				var wear_visuals: Dictionary = (wear_actor.get("equipment_visuals", {}) as Dictionary).duplicate()
				wear_visuals[int(event.part)] = int(event.visual_id)
				wear_actor["equipment_visuals"] = wear_visuals
				var wear_fallback_parts: Array = (wear_actor.get("equipment_fallback_parts", []) as Array).duplicate()
				if not wear_fallback_parts.has(int(event.part)):
					wear_fallback_parts.append(int(event.part))
				wear_actor["equipment_fallback_parts"] = wear_fallback_parts
				actors[wear_actor_id] = wear_actor
				state_changed.emit(&"actors")
		"actor_unwear":
			var unwear_actor_id: int = int(event.actor_id)
			if actors.has(unwear_actor_id):
				var unwear_actor: Dictionary = actors[unwear_actor_id]
				var unwear_visuals: Dictionary = (unwear_actor.get("equipment_visuals", {}) as Dictionary).duplicate()
				unwear_visuals.erase(int(event.part))
				unwear_actor["equipment_visuals"] = unwear_visuals
				var unwear_fallback_parts: Array = (unwear_actor.get("equipment_fallback_parts", []) as Array).duplicate()
				unwear_fallback_parts.erase(int(event.part))
				unwear_actor["equipment_fallback_parts"] = unwear_fallback_parts
				actors[unwear_actor_id] = unwear_actor
				state_changed.emit(&"actors")
		"stats":
			stats = (event.values as Dictionary).duplicate(true)
			state_changed.emit(&"stats")
		"partial_stats":
			for stat_key_value: Variant in event.values:
				var stat_key: String = str(stat_key_value)
				stats[stat_key] = event.values[stat_key_value]
			state_changed.emit(&"stats")
		"inventory":
			inventory.clear()
			for raw_item: Variant in event.items:
				var item: Dictionary = raw_item as Dictionary
				inventory[int(item.get("slot", -1))] = item
			state_changed.emit(&"inventory")
		"inventory_update":
			var updated_item: Dictionary = event.item as Dictionary
			inventory[int(updated_item.get("slot", -1))] = updated_item
			state_changed.emit(&"inventory")
		"inventory_remove":
			for raw_slot: Variant in event.slots:
				inventory.erase(int(raw_slot))
			state_changed.emit(&"inventory")
		"inventory_text":
			inventory_text = str(event.text)
			state_changed.emit(&"inventory_text")
		"item_cooldowns":
			inventory_cooldowns.clear()
			var received_msec: int = Time.get_ticks_msec()
			for raw_cooldown: Variant in event.cooldowns:
				var cooldown: Dictionary = raw_cooldown as Dictionary
				var slot: int = int(cooldown.get("slot", -1))
				var maximum_seconds: int = int(cooldown.get("maximum_seconds", 0))
				var remaining_seconds: int = int(cooldown.get("remaining_seconds", 0))
				inventory_cooldowns[slot] = {
					"maximum_msec": maximum_seconds * 1000,
					"end_msec": received_msec + remaining_seconds * 1000}
			state_changed.emit(&"inventory_cooldowns")
		"chat":
			chat_lines.append({"channel": event.channel, "text": event.text})
			if chat_lines.size() > 1000:
				chat_lines.pop_front()
			state_changed.emit(&"chat")
		"npc_info":
			npc_dialogue["open"] = true
			npc_dialogue["name"] = event.name
			npc_dialogue["portrait"] = event.portrait
			state_changed.emit(&"npc_dialogue")
		"npc_text":
			npc_dialogue["open"] = true
			npc_dialogue["text"] = event.text
			state_changed.emit(&"npc_dialogue")
		"npc_options":
			npc_dialogue["open"] = true
			npc_dialogue["options"] = event.options
			state_changed.emit(&"npc_dialogue")
		"npc_close":
			npc_dialogue["open"] = false
			npc_dialogue["options"] = []
			state_changed.emit(&"npc_dialogue")
		"ping_request":
			Network.send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.PING_RESPONSE))
		"invalid":
			recent_protocol_errors.append(event.error)
			if recent_protocol_errors.size() > 50:
				recent_protocol_errors.pop_front()
			state_changed.emit(&"protocol_errors")
		"unknown":
			unknown_packet_count += 1
			state_changed.emit(&"protocol_unknown")

func select_actor(actor_id: int) -> void:
	selected_actor_id = actor_id if actors.has(actor_id) else -1
	state_changed.emit(&"selection")

func close_dialogue() -> void:
	npc_dialogue["open"] = false
	npc_dialogue["options"] = []
	state_changed.emit(&"npc_dialogue")
