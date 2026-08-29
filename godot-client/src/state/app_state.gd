extends Node

signal state_changed(path: StringName)
signal login_succeeded
signal login_failed(message: String)
signal character_created
signal character_creation_failed(message: String)
signal floating_feedback_requested(feedback: Dictionary)

var connection_state := "disconnected"
var authenticated := false
var local_actor_id := -1
var current_map := ""
var actors: Dictionary = {}
var inventory: Dictionary = {}
var inventory_text := ""
var inventory_cooldowns: Dictionary = {}
var owned_sigils: Array[int] = []
var active_spells: Dictionary = {}
var last_spell_result: Dictionary = {}
var pending_spell_target := ""
var stats: Dictionary = {}
var game_minute := 0
var game_minute_anchor_msec := 0
var server_timestamp := 0
var chat_lines: Array[Dictionary] = []
var active_channels: Array[int] = [0, 0, 0]
var active_channel_index := 0
var selected_actor_id := -1
var npc_dialogue: Dictionary = {"open": false, "name": "", "text": "",
	"options": []}
var trade: Dictionary = {"open": false, "partner": "", "storage_available": false,
	"source_inventory": {}, "own_offers": {}, "other_offers": {},
	"own_accepts": 0, "other_accepts": 0}
var storage: Dictionary = {"open": false, "categories": [], "category_id": -1,
	"items": {}, "text": ""}
var ground_bags: Dictionary = {}
var ground_bag: Dictionary = {"open": false, "bag_id": -1, "items": {}}
var known_knowledge: Array[int] = []
var selected_knowledge: int = -1
var knowledge_text: String = ""
var perks: Array[Dictionary] = []
## Lifetime activity totals keyed by the server's own category name, plus the
## order the server listed them in so the window needs no local table.
var activity_counters: Dictionary = {}
var activity_counter_order: Array[String] = []
## Protocol diagnostics. Every undecoded packet and every decode failure used
## to be reduced here and emitted with no listener, so a gap in the client's
## coverage was completely silent. The diagnostics panel reads these.
var unknown_packet_count := 0
var unknown_packets: Dictionary = {}
var recent_protocol_errors: Array[Dictionary] = []
var last_clock_sync_msec := 0
var invasion_assistant: Dictionary = {"open": false}

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
		owned_sigils.clear()
		active_spells.clear()
		last_spell_result.clear()
		pending_spell_target = ""
		stats.clear()
		game_minute = 0
		game_minute_anchor_msec = 0
		server_timestamp = 0
		chat_lines.clear()
		active_channels = [0, 0, 0]
		active_channel_index = 0
		current_map = ""
		selected_actor_id = -1
		npc_dialogue = {"open": false, "name": "", "text": "", "options": []}
		trade = _empty_trade_state()
		storage = _empty_storage_state()
		ground_bags.clear()
		ground_bag = _empty_ground_bag_state()
		known_knowledge.clear()
		selected_knowledge = -1
		knowledge_text = ""
		perks.clear()
		activity_counters.clear()
		activity_counter_order.clear()
		invasion_assistant = {"open": false}
	state_changed.emit(&"connection")

func _on_packet(command: int, payload: PackedByteArray) -> void:
	var event := EloriaProtocol.decode_server(command, payload)
	match event.type:
		"invasion_assistant":
			var update: Dictionary = (event.state as Dictionary).duplicate(true)
			var kind: String = str(update.get("kind", ""))
			invasion_assistant["open"] = true
			invasion_assistant[kind] = update
			invasion_assistant["last_kind"] = kind
			state_changed.emit(&"invasion_assistant")
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
		"clock_sync":
			server_timestamp = int(event.server_timestamp)
			last_clock_sync_msec = Time.get_ticks_msec()
			state_changed.emit(&"clock")
		"new_minute":
			game_minute = int(event.minute)
			game_minute_anchor_msec = Time.get_ticks_msec()
			state_changed.emit(&"clock")
		"change_map":
			current_map = event.map_name
			actors.clear()
			selected_actor_id = -1
			npc_dialogue = {"open": false, "name": "", "text": "",
				"options": []}
			pending_spell_target = ""
			trade = _empty_trade_state()
			storage = _empty_storage_state()
			ground_bags.clear()
			ground_bag = _empty_ground_bag_state()
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
		"actor_damage":
			_apply_actor_health_delta(int(event.actor_id), -int(event.amount))
		"actor_heal":
			_apply_actor_health_delta(int(event.actor_id), int(event.amount))
		"actor_max_health":
			var health_actor_id: int = int(event.actor_id)
			if actors.has(health_actor_id):
				var health_actor: Dictionary = actors[health_actor_id]
				health_actor["max_health"] = int(event.max_health)
				health_actor["health"] = mini(int(health_actor.get("health", 0)),
					int(event.max_health))
				actors[health_actor_id] = health_actor
				state_changed.emit(&"actors")
				if health_actor_id == local_actor_id:
					stats["max_health"] = int(event.max_health)
					stats["health"] = int(health_actor.get("health", 0))
					state_changed.emit(&"stats")
		"stats":
			stats = (event.values as Dictionary).duplicate(true)
			state_changed.emit(&"stats")
		"partial_stats":
			for stat_key_value: Variant in event.values:
				var stat_key: String = str(stat_key_value)
				var next_value: int = int(event.values[stat_key_value])
				var had_previous: bool = stats.has(stat_key)
				var previous_value: int = int(stats.get(stat_key, next_value))
				stats[stat_key] = next_value
				if had_previous:
					_emit_stat_feedback(stat_key, previous_value, next_value)
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
		"ground_bag":
			var bag: Dictionary = {"bag_id": int(event.bag_id),
				"x": int(event.x), "y": int(event.y)}
			ground_bags[int(event.bag_id)] = bag
			state_changed.emit(&"ground_bags")
		"ground_bags":
			ground_bags.clear()
			for raw_bag: Variant in event.bags:
				var listed_bag: Dictionary = raw_bag as Dictionary
				ground_bags[int(listed_bag.get("bag_id", -1))] = listed_bag.duplicate(true)
			state_changed.emit(&"ground_bags")
		"ground_bag_destroy":
			var destroyed_bag_id: int = int(event.bag_id)
			ground_bags.erase(destroyed_bag_id)
			if int(ground_bag.get("bag_id", -1)) == destroyed_bag_id:
				ground_bag = _empty_ground_bag_state()
				state_changed.emit(&"ground_bag")
			state_changed.emit(&"ground_bags")
		"ground_items":
			var ground_items: Dictionary = {}
			for raw_ground_item: Variant in event.items:
				var ground_item: Dictionary = raw_ground_item as Dictionary
				ground_items[int(ground_item.get("position", -1))] = ground_item
			ground_bag["items"] = ground_items
			ground_bag["open"] = true
			state_changed.emit(&"ground_bag")
		"ground_item":
			var new_ground_item: Dictionary = event.item as Dictionary
			var current_ground_items: Dictionary = (ground_bag.get("items", {}) as Dictionary).duplicate(true)
			current_ground_items[int(new_ground_item.get("position", -1))] = new_ground_item
			ground_bag["items"] = current_ground_items
			ground_bag["open"] = true
			state_changed.emit(&"ground_bag")
		"ground_item_remove":
			var remaining_ground_items: Dictionary = (ground_bag.get("items", {}) as Dictionary).duplicate(true)
			remaining_ground_items.erase(int(event.position))
			ground_bag["items"] = remaining_ground_items
			state_changed.emit(&"ground_bag")
		"ground_bag_close":
			ground_bag = _empty_ground_bag_state()
			state_changed.emit(&"ground_bag")
		"knowledge_list":
			known_knowledge.clear()
			for raw_index: Variant in event.known:
				known_knowledge.append(int(raw_index))
			state_changed.emit(&"knowledge")
		"new_knowledge":
			var new_knowledge_index: int = int(event.index)
			if not known_knowledge.has(new_knowledge_index):
				known_knowledge.append(new_knowledge_index)
				known_knowledge.sort()
			state_changed.emit(&"knowledge")
		"knowledge_text":
			knowledge_text = str(event.text)
			state_changed.emit(&"knowledge")
		"trade_partner":
			trade["open"] = true
			trade["partner"] = str(event.name)
			trade["storage_available"] = bool(event.storage_available)
			trade["own_offers"] = {}
			trade["other_offers"] = {}
			trade["own_accepts"] = 0
			trade["other_accepts"] = 0
			state_changed.emit(&"trade")
		"trade_inventory":
			var source_inventory: Dictionary = {}
			for raw_trade_item: Variant in event.items:
				var trade_item: Dictionary = raw_trade_item as Dictionary
				source_inventory[int(trade_item.get("slot", -1))] = trade_item
			trade["source_inventory"] = source_inventory
			trade["open"] = true
			state_changed.emit(&"trade")
		"trade_object":
			var offers_key: String = "other_offers" if bool(event.other) else "own_offers"
			var offers: Dictionary = (trade.get(offers_key, {}) as Dictionary).duplicate(true)
			var offer_slot: int = int(event.slot)
			var prior_quantity: int = 0
			var prior_offer_value: Variant = offers.get(offer_slot)
			if prior_offer_value is Dictionary:
				prior_quantity = int((prior_offer_value as Dictionary).get("quantity", 0))
			offers[offer_slot] = {"image_id": int(event.image_id),
				"quantity": prior_quantity + int(event.quantity),
				"source_type": int(event.source_type), "slot": offer_slot}
			trade[offers_key] = offers
			state_changed.emit(&"trade")
		"trade_remove":
			var remove_key: String = "other_offers" if bool(event.other) else "own_offers"
			var remove_offers: Dictionary = (trade.get(remove_key, {}) as Dictionary).duplicate(true)
			var remove_slot: int = int(event.slot)
			var remove_value: Variant = remove_offers.get(remove_slot)
			if remove_value is Dictionary:
				var remove_offer: Dictionary = (remove_value as Dictionary).duplicate(true)
				var remaining: int = int(remove_offer.get("quantity", 0)) - int(event.quantity)
				if remaining > 0:
					remove_offer["quantity"] = remaining
					remove_offers[remove_slot] = remove_offer
				else:
					remove_offers.erase(remove_slot)
			trade[remove_key] = remove_offers
			state_changed.emit(&"trade")
		"trade_accept":
			# The server reports the phase; the client does not infer it by
			# counting packets. A duplicate or reordered accept therefore
			# cannot leave the two sides disagreeing about the trade.
			var accept_key: String = "other_accepts" if bool(event.other) else "own_accepts"
			trade[accept_key] = clampi(int(event.phase), 0, 2)
			state_changed.emit(&"trade")
		"trade_reject":
			var reject_key: String = "other_accepts" if bool(event.other) else "own_accepts"
			trade[reject_key] = 0
			state_changed.emit(&"trade")
		"trade_exit":
			trade = _empty_trade_state()
			state_changed.emit(&"trade")
		"storage_categories":
			storage["open"] = true
			storage["categories"] = (event.categories as Array).duplicate(true)
			storage["text"] = ""
			state_changed.emit(&"storage")
		"storage_items":
			var storage_items: Dictionary = (storage.get("items", {}) as Dictionary).duplicate(true)
			if not bool(event.update):
				storage_items.clear()
			for raw_storage_item: Variant in event.items:
				var storage_item: Dictionary = raw_storage_item as Dictionary
				var storage_position: int = int(storage_item.get("position", -1))
				if int(storage_item.get("quantity", 0)) > 0:
					storage_items[storage_position] = storage_item
				else:
					storage_items.erase(storage_position)
			storage["items"] = storage_items
			storage["category_id"] = int(event.category_id)
			storage["open"] = true
			state_changed.emit(&"storage")
		"storage_text":
			storage["text"] = str(event.text)
			state_changed.emit(&"storage")
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
		"sigils":
			owned_sigils.clear()
			for raw_sigil: Variant in event.owned:
				owned_sigils.append(int(raw_sigil))
			state_changed.emit(&"spells")
		"spell_result":
			last_spell_result = {"status": int(event.status), "spell_id": int(event.spell_id)}
			match int(event.status):
				4:
					pending_spell_target = "actor"
				5:
					pending_spell_target = "location"
				_:
					pending_spell_target = ""
			state_changed.emit(&"spells")
		"active_spell":
			active_spells[int(event.buff_id)] = {
				"end_msec": Time.get_ticks_msec() + int(event.duration_seconds) * 1000}
			state_changed.emit(&"spells")
		"active_spell_list":
			active_spells.clear()
			for raw_buff: Variant in event.buffs:
				active_spells[int(raw_buff)] = {"end_msec": 0}
			state_changed.emit(&"spells")
		"remove_active_spell":
			active_spells.erase(int(event.buff_id))
			state_changed.emit(&"spells")
		"active_channels":
			active_channels = [0, 0, 0]
			var incoming_channels: Array = event.channels as Array
			for index: int in range(mini(3, incoming_channels.size())):
				active_channels[index] = int(incoming_channels[index])
			active_channel_index = clampi(int(event.active_index), 0, 2)
			state_changed.emit(&"channels")
		"chat":
			chat_lines.append({"channel": event.channel, "text": event.text})
			if chat_lines.size() > 1000:
				chat_lines.pop_front()
			state_changed.emit(&"chat")
		"npc_info":
			npc_dialogue["open"] = true
			npc_dialogue["name"] = event.name
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
		"perks":
			perks.clear()
			for raw_perk: Variant in event.perks:
				perks.append((raw_perk as Dictionary).duplicate(true))
			state_changed.emit(&"perks")
		"activity_counters":
			if bool(event.full):
				activity_counters.clear()
				activity_counter_order.clear()
			for raw_counter: Variant in event.counters:
				var counter: Dictionary = raw_counter as Dictionary
				var counter_name: String = str(counter.get("name", ""))
				if counter_name.is_empty():
					continue
				if not activity_counters.has(counter_name):
					activity_counter_order.append(counter_name)
				activity_counters[counter_name] = int(counter.get("total", 0))
			state_changed.emit(&"counters")
		"ping_request":
			Network.send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.PING_RESPONSE))
		"invalid":
			recent_protocol_errors.append({"command": command,
				"error": str(event.error), "size": payload.size(),
				"msec": Time.get_ticks_msec()})
			if recent_protocol_errors.size() > 50:
				recent_protocol_errors.pop_front()
			state_changed.emit(&"protocol_errors")
		"unknown":
			unknown_packet_count += 1
			var record: Dictionary = unknown_packets.get(command,
				{"count": 0, "size": 0, "msec": 0})
			record["count"] = int(record.get("count", 0)) + 1
			record["size"] = payload.size()
			record["msec"] = Time.get_ticks_msec()
			unknown_packets[command] = record
			state_changed.emit(&"protocol_unknown")

func append_local_message(text: String, channel: int = 255) -> void:
	chat_lines.append({"channel": channel, "text": text})
	if chat_lines.size() > 1000:
		chat_lines.pop_front()
	state_changed.emit(&"chat")

func active_channel_number() -> int:
	if active_channel_index < 0 or active_channel_index >= active_channels.size():
		return 0
	return active_channels[active_channel_index]

func select_actor(actor_id: int) -> void:
	selected_actor_id = actor_id if actors.has(actor_id) else -1
	state_changed.emit(&"selection")

func _apply_actor_health_delta(actor_id: int, amount: int) -> void:
	if not actors.has(actor_id):
		return
	var actor: Dictionary = actors[actor_id]
	var maximum: int = maxi(0, int(actor.get("max_health", 0)))
	var health: int = clampi(int(actor.get("health", 0)) + amount, 0, maximum)
	actor["health"] = health
	actor["alive"] = health > 0
	actors[actor_id] = actor
	state_changed.emit(&"actors")
	if actor_id == local_actor_id:
		stats["health"] = health
		state_changed.emit(&"stats")

func _emit_stat_feedback(stat_key: String, previous_value: int,
		next_value: int) -> void:
	if next_value <= previous_value:
		return
	if stat_key.ends_with("_exp_next"):
		return
	if stat_key.ends_with("_exp"):
		var skill_key: String = stat_key.trim_suffix("_exp")
		floating_feedback_requested.emit({
			"kind": "experience", "skill": skill_key,
			"amount": next_value - previous_value, "value": next_value})
	elif stat_key.ends_with("_base"):
		var skill_key: String = stat_key.trim_suffix("_base")
		if not skill_key in ["attack", "defense", "harvesting", "alchemy",
				"magic", "potion", "summoning", "manufacturing", "crafting",
				"engineering", "tailoring", "ranging", "overall"]:
			return
		floating_feedback_requested.emit({
			"kind": "level", "skill": skill_key, "level": next_value})

func close_dialogue() -> void:
	npc_dialogue["open"] = false
	npc_dialogue["options"] = []
	state_changed.emit(&"npc_dialogue")

func _empty_trade_state() -> Dictionary:
	return {"open": false, "partner": "", "storage_available": false,
		"source_inventory": {}, "own_offers": {}, "other_offers": {},
		"own_accepts": 0, "other_accepts": 0}

func close_storage() -> void:
	storage = _empty_storage_state()
	state_changed.emit(&"storage")

func _empty_storage_state() -> Dictionary:
	return {"open": false, "categories": [], "category_id": -1,
		"items": {}, "text": ""}

func begin_ground_bag_inspection(bag_id: int) -> void:
	ground_bag["bag_id"] = bag_id
	ground_bag["open"] = false
	ground_bag["items"] = {}
	state_changed.emit(&"ground_bag")

func close_ground_bag() -> void:
	ground_bag = _empty_ground_bag_state()
	state_changed.emit(&"ground_bag")

func _empty_ground_bag_state() -> Dictionary:
	return {"open": false, "bag_id": -1, "items": {}}

func select_knowledge(index: int) -> void:
	selected_knowledge = index
	knowledge_text = ""
	state_changed.emit(&"knowledge")
