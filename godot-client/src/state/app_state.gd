extends Node

signal state_changed(path: StringName)
signal login_succeeded
signal login_failed(message: String)
signal character_created
signal character_creation_failed(message: String)
signal floating_feedback_requested(feedback: Dictionary)
## Something the server said happened in the world, at an actor and sometimes
## towards another. It is an event rather than state - there is nothing to be
## true a moment later - so it is announced and not stored.
signal special_effect_requested(effect: Dictionary)
## An actor is playing a named animation action - an emote, or anything else
## the server asks for that is not one of the actor commands. An event rather
## than state: it happens once and is over, so nothing keeps it.
signal actor_animation_requested(animation: Dictionary)
## An arrow the server said was loosed, between the two actors it named. Like
## an effect it is an event rather than state: the shot is already resolved by
## the time it arrives, and the damage comes in its own packet.
signal missile_fired(shot: Dictionary)
## An arrow on its way to a tile rather than to an actor - a practice shot, or
## a miss the server placed. Carries the tile because that is where it lands.
signal ground_missile_fired(shot: Dictionary)

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
## How long the server actually takes between two game minutes, measured
## rather than assumed, so the client can carry the clock forward smoothly
## between packets without hard-coding the server's tick.
var game_minute_interval_msec := 0
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
## What the character is currently reading. The server models a book as
## research: pages remaining tick down and the knowledge bit is set on
## completion, so this is derived from the authoritative statistics rather than
## from a page-turning protocol the server has no content for.
var reading: Dictionary = {"active": false, "index": -1, "pages_read": 0,
	"pages_total": 0}
var known_knowledge: Array[int] = []
var selected_knowledge: int = -1
var knowledge_text: String = ""
## The nine Eloria extension windows. Each is a server-push snapshot: the
## server states the whole window and the client renders it, so none of these
## is merged with a previous value or reconstructed from anything else.
var marketplace: Dictionary = {"open": false, "gold": 0, "returned_items": 0,
	"listings": []}
var merchant: Dictionary = {"open": false, "actor_id": -1, "npc_name": "",
	"gold": 0, "carried": 0, "capacity": 0, "items": []}
var quest_journal: Array[Dictionary] = []
var item_detail: Dictionary = {"open": false}
var inventory_state: Dictionary = {"gold": 0, "carried": 0, "capacity": 0,
	"items": []}
var combat_state: Dictionary = {"active": false, "event": 0, "target_id": -1,
	"target_name": "", "player_health": 0, "player_max_health": 0,
	"target_health": 0, "target_max_health": 0, "recent_damage": 0,
	"updated_msec": 0}
var mail: Array[Dictionary] = []
var navigation: Dictionary = {"active": false, "x": 0, "y": 0, "distance": 0,
	"map_id": "", "label": ""}
var special_events: Array[String] = []

## What power each spell effect will be cast at, and the highest the server
## allows, keyed by the server's effect name. Entirely server-stated: the
## client never works a limit out from a level.
var spell_power: Dictionary = {}
## The game date, the special day in force and what it does, and the whole
## catalogue of days the server can roll. Command 238; empty until it arrives.
var almanac: Dictionary = {}

## The player the server last described, in its own words: who was inspected
## and what they have earned. Never assembled from a request the client
## remembers making.
var player_info: Dictionary = {"open": false, "actor_id": -1, "name": "",
	"achievements": []}

## Map markers the server placed, keyed by its marker id. Purely server-stated:
## the client never invents one and never removes one the server still holds.
var map_markers: Dictionary = {}

## Adds a line the client wrote for itself - a console command's answer, not
## something the server said. Channel 254 keeps it out of the channel tabs and
## marks it as local wherever chat is rendered.
const LOCAL_CHAT_CHANNEL := 254

func append_local_line(text: String) -> void:
	chat_lines.append({"channel": LOCAL_CHAT_CHANNEL, "text": text})
	if chat_lines.size() > 1000:
		chat_lines.pop_front()
	state_changed.emit(&"chat")

## The game minute carried forward to now. The server states a whole minute at
## a time; this is the same minute plus however far through it the client is,
## measured against the observed interval between two of them, so the sky moves
## instead of stepping once a minute. Falls back to the stated minute until
## two have been seen.
func continuous_game_minute() -> float:
	if game_minute_interval_msec <= 0 or game_minute_anchor_msec <= 0:
		return float(game_minute)
	var elapsed: int = Time.get_ticks_msec() - game_minute_anchor_msec
	var fraction: float = clampf(
		float(elapsed) / float(game_minute_interval_msec), 0.0, 1.0)
	return float(game_minute) + fraction

## Clickable world objects on the current map, keyed by server object id, and
## the authoritative harvesting state. Both are server-declared: nothing here
## is matched by filename or scraped out of chat.
var map_objects: Dictionary = {}
var harvest: Dictionary = {"active": false, "object_id": -1, "resource": ""}

## A server-driven modal question. The server had no way to ask the player
## anything: DISPLAY_POPUP(83) fell through to {"type":"unknown"} and
## POPUP_REPLY(50) had no encoder.
var popup: Dictionary = {"open": false, "popup_id": -1, "title": "", "text": "",
	"options": []}
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
	# "reconnecting" is a waiting state between a drop and the next attempt.
	# The world was already cleared by the "disconnected" that preceded it, so
	# it must not clear anything a second time.
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
		game_minute_interval_msec = 0
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
		reading = _empty_reading_state()
		known_knowledge.clear()
		selected_knowledge = -1
		knowledge_text = ""
		marketplace = _empty_marketplace_state()
		merchant = _empty_merchant_state()
		quest_journal.clear()
		item_detail = {"open": false}
		almanac = {}
		inventory_state = {"gold": 0, "carried": 0, "capacity": 0, "items": []}
		combat_state = _empty_combat_state()
		mail.clear()
		navigation = _empty_navigation_state()
		special_events.clear()
		map_objects.clear()
		map_markers.clear()
		player_info = _empty_player_info()
		spell_power.clear()
		harvest = _empty_harvest_state()
		popup = _empty_popup_state()
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
			var minute_arrived_msec: int = Time.get_ticks_msec()
			if game_minute_anchor_msec > 0 and int(event.minute) != game_minute:
				game_minute_interval_msec = (minute_arrived_msec
					- game_minute_anchor_msec)
			game_minute = int(event.minute)
			game_minute_anchor_msec = minute_arrived_msec
			state_changed.emit(&"clock")
		"change_map":
			current_map = event.map_name
			# The new map's objects arrive in their own packet; anything held
			# for the old map is stale the moment the change lands.
			map_objects.clear()
			harvest = _empty_harvest_state()
			marketplace = _empty_marketplace_state()
			merchant = _empty_merchant_state()
			combat_state = _empty_combat_state()
			actors.clear()
			selected_actor_id = -1
			npc_dialogue = {"open": false, "name": "", "text": "",
				"options": []}
			pending_spell_target = ""
			trade = _empty_trade_state()
			storage = _empty_storage_state()
			ground_bags.clear()
			ground_bag = _empty_ground_bag_state()
			state_changed.emit(&"map_objects")
			state_changed.emit(&"harvest")
			state_changed.emit(&"marketplace")
			state_changed.emit(&"merchant")
			state_changed.emit(&"combat_state")
			state_changed.emit(&"map")
		"actor_spawn":
			actors[event.actor_id] = event
			state_changed.emit(&"actors")
		"remove_actor":
			for removed_actor_value: Variant in event.actor_ids:
				var removed_actor_id: int = int(removed_actor_value)
				actors.erase(removed_actor_id)
				if selected_actor_id == removed_actor_id:
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
			_refresh_reading()
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
			_refresh_reading()
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
		"missile":
			# Aiming is state - the shooter is still drawing - and it lives on
			# the actor it describes, so it disappears with them. Loosing is
			# an event, and it ends the aim the server stated before it.
			var shooter_id: int = int(event.source_actor_id)
			if actors.has(shooter_id):
				var shooter: Dictionary = actors[shooter_id] as Dictionary
				shooter["aiming_at"] = (-1 if bool(event.fired)
					else int(event.target_actor_id))
				actors[shooter_id] = shooter
				state_changed.emit(&"actors")
			if bool(event.fired):
				missile_fired.emit({"source_actor_id": shooter_id,
					"target_actor_id": int(event.target_actor_id)})
		"ground_missile":
			# Aiming at a place is state on the shooter, the same as aiming at
			# an actor, so it clears the same way and disappears with them.
			var ground_shooter_id: int = int(event.source_actor_id)
			if actors.has(ground_shooter_id):
				var ground_shooter: Dictionary = actors[ground_shooter_id] as Dictionary
				ground_shooter["aiming_at"] = -1
				ground_shooter["aiming_at_tile"] = (Vector2i(-1, -1)
					if bool(event.fired)
					else Vector2i(int(event.x), int(event.y)))
				actors[ground_shooter_id] = ground_shooter
				state_changed.emit(&"actors")
			if bool(event.fired):
				ground_missile_fired.emit({
					"source_actor_id": ground_shooter_id,
					"x": int(event.x), "y": int(event.y)})
		"actor_animation":
			actor_animation_requested.emit({"actor_id": int(event.actor_id),
				"action": str(event.action)})
		"special_effect":
			special_effect_requested.emit({"effect": int(event.effect),
				"actor_id": int(event.actor_id),
				"target_id": int(event.target_id)})
		"actor_buffs":
			# Which visible effects an actor is under, stated per actor. Kept on
			# the actor rather than in a table of its own, so it disappears with
			# the actor it describes.
			var buffed_id: int = int(event.actor_id)
			if actors.has(buffed_id):
				var buffed: Dictionary = actors[buffed_id] as Dictionary
				buffed["buffs"] = int(event.buffs)
				actors[buffed_id] = buffed
				state_changed.emit(&"actors")
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
		"marketplace":
			marketplace = {"open": true, "gold": int(event.gold),
				"returned_items": int(event.returned_items),
				"listings": (event.listings as Array).duplicate(true)}
			state_changed.emit(&"marketplace")
		"merchant":
			merchant = {"open": true, "actor_id": int(event.actor_id),
				"npc_name": str(event.npc_name), "gold": int(event.gold),
				"carried": int(event.carried), "capacity": int(event.capacity),
				"items": (event.items as Array).duplicate(true)}
			state_changed.emit(&"merchant")
		"quest_journal":
			quest_journal.clear()
			for raw_quest: Variant in event.entries:
				quest_journal.append((raw_quest as Dictionary).duplicate(true))
			state_changed.emit(&"quest_journal")
		"almanac":
			almanac = (event as Dictionary).duplicate(true)
			almanac.erase("type")
			state_changed.emit(&"almanac")
		"item_detail":
			item_detail = (event as Dictionary).duplicate(true)
			item_detail["open"] = true
			item_detail.erase("type")
			state_changed.emit(&"item_detail")
		"inventory_state":
			inventory_state = {"gold": int(event.gold),
				"carried": int(event.carried), "capacity": int(event.capacity),
				"items": (event.items as Array).duplicate(true)}
			state_changed.emit(&"inventory_state")
		"combat_state":
			# A defeat ends the engagement; every other event refreshes it.
			var defeated: bool = (int(event.event)
				== EloriaProtocol.COMBAT_EVENT_DEFEAT)
			combat_state = {"active": not defeated, "event": int(event.event),
				"target_id": int(event.target_id),
				"target_name": str(event.target_name),
				"player_health": int(event.player_health),
				"player_max_health": int(event.player_max_health),
				"target_health": int(event.target_health),
				"target_max_health": int(event.target_max_health),
				"recent_damage": int(event.recent_damage),
				"updated_msec": Time.get_ticks_msec()}
			state_changed.emit(&"combat_state")
		"mail":
			mail.clear()
			for raw_message: Variant in event.messages:
				mail.append((raw_message as Dictionary).duplicate(true))
			state_changed.emit(&"mail")
		"navigation":
			navigation = {"active": bool(event.active), "x": int(event.x),
				"y": int(event.y), "distance": int(event.distance),
				"map_id": str(event.map_id), "label": str(event.label)}
			state_changed.emit(&"navigation")
		"special_events":
			special_events.clear()
			for raw_line: Variant in event.lines:
				special_events.append(str(raw_line))
			state_changed.emit(&"special_events")
		"spell_power":
			spell_power.clear()
			for raw_effect: Variant in event.effects:
				var described: Dictionary = raw_effect as Dictionary
				spell_power[str(described.get("effect", ""))] = {
					"preferred": int(described.get("preferred", 1)),
					"limit": int(described.get("limit", 1))}
			state_changed.emit(&"spell_power")
		"player_info":
			player_info = {"open": true, "actor_id": int(event.actor_id),
				"name": str(event.name),
				"achievements": (event.achievements as Array).duplicate()}
			state_changed.emit(&"player_info")
		"map_marker":
			map_markers[int(event.marker_id)] = {
				"marker_id": int(event.marker_id), "x": int(event.x),
				"y": int(event.y), "map_id": str(event.map_id),
				"label": str(event.label)}
			state_changed.emit(&"map_markers")
		"remove_map_marker":
			# Removing one the server never placed is not an error: the server
			# clears a range of ids whenever it resyncs quest markers.
			if map_markers.erase(int(event.marker_id)):
				state_changed.emit(&"map_markers")
		"map_objects":
			# The list arrives in chunks; only the first clears what was there.
			if bool(event.first):
				map_objects.clear()
			for raw_object: Variant in event.objects:
				var map_object: Dictionary = (raw_object as Dictionary).duplicate(true)
				map_objects[int(map_object.get("object_id", -1))] = map_object
			state_changed.emit(&"map_objects")
		"harvest_state":
			harvest = {"active": bool(event.active),
				"object_id": int(event.object_id), "resource": str(event.resource)}
			state_changed.emit(&"harvest")
		"popup":
			# Only one popup at a time, matching the legacy client's refusal to
			# open a second window for an id it is already showing.
			var same_popup: bool = (bool(popup.get("open", false))
				and int(popup.get("popup_id", -1)) == int(event.popup_id))
			if not same_popup:
				popup = {"open": true, "popup_id": int(event.popup_id),
					"title": str(event.title), "text": str(event.text),
					"options": (event.options as Array).duplicate(true)}
				state_changed.emit(&"popup")
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

## The popup is closed by the client once its answer is on the wire, or when
## the player dismisses it. The server does not send a close packet.
func close_popup() -> void:
	popup = _empty_popup_state()
	state_changed.emit(&"popup")

## The reading slice is a typed reduction of the three research statistics, so
## the window never re-reads raw slot numbers. Index 1024 is the server's
## "reading nothing" value.
func _refresh_reading() -> void:
	var index: int = int(stats.get("researching", 1024))
	var total: int = maxi(0, int(stats.get("research_total", 0)))
	var completed: int = clampi(int(stats.get("research_completed", 0)), 0, total)
	var next_reading: Dictionary = {
		"active": index >= 0 and index < 1024 and total > 0,
		"index": index, "pages_read": completed, "pages_total": total}
	if next_reading == reading:
		return
	reading = next_reading
	state_changed.emit(&"reading")

func _empty_reading_state() -> Dictionary:
	return {"active": false, "index": -1, "pages_read": 0, "pages_total": 0}

func close_marketplace() -> void:
	marketplace = _empty_marketplace_state()
	state_changed.emit(&"marketplace")

func close_merchant() -> void:
	merchant = _empty_merchant_state()
	state_changed.emit(&"merchant")

func close_item_detail() -> void:
	item_detail = {"open": false}
	state_changed.emit(&"item_detail")

func close_player_info() -> void:
	player_info = _empty_player_info()
	state_changed.emit(&"player_info")

func _empty_player_info() -> Dictionary:
	return {"open": false, "actor_id": -1, "name": "", "achievements": []}

func _empty_marketplace_state() -> Dictionary:
	return {"open": false, "gold": 0, "returned_items": 0, "listings": []}

func _empty_merchant_state() -> Dictionary:
	return {"open": false, "actor_id": -1, "npc_name": "", "gold": 0,
		"carried": 0, "capacity": 0, "items": []}

func _empty_combat_state() -> Dictionary:
	return {"active": false, "event": 0, "target_id": -1, "target_name": "",
		"player_health": 0, "player_max_health": 0, "target_health": 0,
		"target_max_health": 0, "recent_damage": 0, "updated_msec": 0}

func _empty_navigation_state() -> Dictionary:
	return {"active": false, "x": 0, "y": 0, "distance": 0, "map_id": "",
		"label": ""}

func _empty_harvest_state() -> Dictionary:
	return {"active": false, "object_id": -1, "resource": ""}

func _empty_popup_state() -> Dictionary:
	return {"open": false, "popup_id": -1, "title": "", "text": "", "options": []}

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
