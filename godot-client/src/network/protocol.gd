class_name EloriaProtocol
extends RefCounted

const HEADER_SIZE := 3
const MAX_PAYLOAD := 65532

enum ClientMessage {
	RAW_TEXT = 0, MOVE_TO = 1, SEND_PM = 2, GET_PLAYER_INFO = 5, RUN_TO = 6,
	SIT_DOWN = 7, SEND_ME_MY_ACTORS = 8, SEND_OPENING_SCREEN = 9, SEND_VERSION = 10,
	PING = 13, HEART_BEAT = 14, LOCATE_ME = 15, USE_MAP_OBJECT = 16,
	SEND_MY_STATS = 17, SEND_MY_INVENTORY = 18, LOOK_AT_INVENTORY_ITEM = 19,
	MOVE_INVENTORY_ITEM = 20, HARVEST = 21, DROP_ITEM = 22, PICK_UP_ITEM = 23,
	INSPECT_BAG = 25, CLOSE_BAG = 26, LOOK_AT_MAP_OBJECT = 27, TOUCH_PLAYER = 28,
	RESPOND_TO_NPC = 29, MANUFACTURE_THIS = 30, USE_INVENTORY_ITEM = 31,
	TRADE_WITH = 32, ACCEPT_TRADE = 33, REJECT_TRADE = 34, EXIT_TRADE = 35,
	PUT_OBJECT_ON_TRADE = 36, REMOVE_OBJECT_FROM_TRADE = 37,
	LOOK_AT_TRADE_ITEM = 38, CAST_SPELL = 39, ATTACK_SOMEONE = 40,
	GET_KNOWLEDGE_INFO = 41, GET_STORAGE_CATEGORY = 44, DEPOSIT_ITEM = 45,
	WITHDRAW_ITEM = 46, LOOK_AT_STORAGE_ITEM = 47, POPUP_REPLY = 50,
	PING_RESPONSE = 60, SET_ACTIVE_CHANNEL = 61, LOG_IN = 140,
	CREATE_CHAR = 141, GET_DATE = 230, GET_TIME = 231
}

enum ServerMessage {
	RAW_TEXT = 0, ADD_NEW_ACTOR = 1, ADD_ACTOR_COMMAND = 2, YOU_ARE = 3,
	SYNC_CLOCK = 4, NEW_MINUTE = 5, REMOVE_ACTOR = 6, CHANGE_MAP = 7,
	COMBAT_MODE = 8, KILL_ALL_ACTORS = 9, PONG = 11, HERE_YOUR_STATS = 18,
	HERE_YOUR_INVENTORY = 19, INVENTORY_ITEM_TEXT = 20,
	GET_NEW_INVENTORY_ITEM = 21, REMOVE_ITEM_FROM_INVENTORY = 22,
	HERE_YOUR_GROUND_ITEMS = 23, GET_NEW_GROUND_ITEM = 24,
	REMOVE_ITEM_FROM_GROUND = 25, CLOSE_BAG = 26,
	GET_NEW_BAG = 27, GET_BAGS_LIST = 28, DESTROY_BAG = 29, NPC_TEXT = 30,
	NPC_OPTIONS_LIST = 31, CLOSE_NPC_MENU = 32, SEND_NPC_INFO = 33,
	GET_TRADE_OBJECT = 35, GET_TRADE_ACCEPT = 36, GET_TRADE_REJECT = 37,
	GET_TRADE_EXIT = 38, REMOVE_TRADE_OBJECT = 39, GET_YOUR_TRADEOBJECTS = 40,
	GET_TRADE_PARTNER_NAME = 41,
	GET_YOUR_SIGILS = 42, GET_ACTIVE_SPELL = 44,
	GET_ACTIVE_SPELL_LIST = 45, REMOVE_ACTIVE_SPELL = 46,
	GET_ACTOR_DAMAGE = 47, GET_ACTOR_HEAL = 48, SEND_PARTIAL_STAT = 49,
	ADD_NEW_ENHANCED_ACTOR = 51, ACTOR_WEAR_ITEM = 52, ACTOR_UNWEAR_ITEM = 53,
	GET_KNOWLEDGE_LIST = 55, GET_NEW_KNOWLEDGE = 56, GET_KNOWLEDGE_TEXT = 57,
	STORAGE_LIST = 67, STORAGE_ITEMS = 68, STORAGE_TEXT = 69,
	PING_REQUEST = 60, SPELL_CAST = 70, GET_ACTIVE_CHANNELS = 71, GET_ACTOR_HEALTH = 73,
	GET_ITEMS_COOLDOWN = 77, SEND_BUFFS = 78, SEND_SPECIAL_EFFECT = 79,
	DISPLAY_POPUP = 83, SEND_MAP_MARKER = 90, REMOVE_MAP_MARKER = 91,
	SEND_ACHIEVEMENTS = 95, LOG_IN_OK = 250, LOG_IN_NOT_OK = 251,
	CREATE_CHAR_OK = 252, CREATE_CHAR_NOT_OK = 253
}

static func encode(command: int, payload := PackedByteArray()) -> PackedByteArray:
	assert(command >= 0 and command <= 255)
	assert(payload.size() <= MAX_PAYLOAD)
	var frame := PackedByteArray([command])
	var wire_length := payload.size() + 1
	frame.append(wire_length & 0xff)
	frame.append((wire_length >> 8) & 0xff)
	frame.append_array(payload)
	return frame

static func try_decode(buffer: PackedByteArray) -> Dictionary:
	if buffer.size() < HEADER_SIZE:
		return {"status": "incomplete"}
	var wire_length := u16(buffer, 1)
	if wire_length < 1 or wire_length - 1 > MAX_PAYLOAD:
		return {"status": "error", "error": "invalid_packet_length"}
	var total := wire_length + 2
	if buffer.size() < total:
		return {"status": "incomplete"}
	return {"status": "ok", "command": int(buffer[0]),
		"payload": buffer.slice(HEADER_SIZE, total), "consumed": total}

static func login(username: String, password: String) -> PackedByteArray:
	# Legacy send_login_info(): "username password\0".
	var payload := (username + " " + password).to_utf8_buffer()
	payload.append(0)
	return encode(ClientMessage.LOG_IN, payload)

static func create_character(username: String, password: String, appearance: Dictionary) -> PackedByteArray:
	var payload := (username + " " + password).to_utf8_buffer()
	payload.append(0)
	# Exact legacy order: skin, hair, shirt, pants, boots, actor type, head, eyes.
	for key in ["skin", "hair", "shirt", "pants", "boots", "actor_type", "head", "eyes"]:
		payload.append(clampi(int(appearance.get(key, 0)), 0, 255))
	return encode(ClientMessage.CREATE_CHAR, payload)

static func version(protocol_major: int, protocol_minor: int,
		client_version: PackedByteArray, host := PackedByteArray([0, 0, 0, 0]),
		port := 0) -> PackedByteArray:
	assert(client_version.size() == 4)
	assert(host.size() == 4)
	var payload := PackedByteArray([
		protocol_major & 0xff, (protocol_major >> 8) & 0xff,
		protocol_minor & 0xff, (protocol_minor >> 8) & 0xff])
	payload.append_array(client_version)
	payload.append_array(host)
	# Legacy wire order for this field is network byte order.
	payload.append((port >> 8) & 0xff)
	payload.append(port & 0xff)
	return encode(ClientMessage.SEND_VERSION, payload)

static func move_to(x: int, y: int, run := false) -> PackedByteArray:
	return encode(ClientMessage.RUN_TO if run else ClientMessage.MOVE_TO,
		PackedByteArray([x & 0xff, (x >> 8) & 0xff, y & 0xff, (y >> 8) & 0xff]))

static func set_sitting(sitting: bool) -> PackedByteArray:
	return encode(ClientMessage.SIT_DOWN, PackedByteArray([1 if sitting else 0]))

static func chat(text: String) -> PackedByteArray:
	var payload: PackedByteArray = text.to_utf8_buffer()
	payload.append(0)
	return encode(ClientMessage.RAW_TEXT, payload)

static func private_message(text: String) -> PackedByteArray:
	# Legacy send_input_text_line() removes exactly one leading slash before
	# SEND_PM. Callers provide "name message" or "/message" for reply-last.
	var payload: PackedByteArray = text.to_utf8_buffer()
	payload.append(0)
	return encode(ClientMessage.SEND_PM, payload)

static func touch_actor(actor_id: int) -> PackedByteArray:
	return encode(ClientMessage.TOUCH_PLAYER, PackedByteArray([
		actor_id & 0xff, (actor_id >> 8) & 0xff,
		(actor_id >> 16) & 0xff, (actor_id >> 24) & 0xff]))

static func npc_response(actor_id: int, response_id: int) -> PackedByteArray:
	return encode(ClientMessage.RESPOND_TO_NPC, PackedByteArray([
		actor_id & 0xff, (actor_id >> 8) & 0xff,
		response_id & 0xff, (response_id >> 8) & 0xff]))

static func look_at_inventory_item(slot: int) -> PackedByteArray:
	return encode(ClientMessage.LOOK_AT_INVENTORY_ITEM,
		PackedByteArray([clampi(slot, 0, 255)]))

static func use_inventory_item(slot: int) -> PackedByteArray:
	return encode(ClientMessage.USE_INVENTORY_ITEM,
		PackedByteArray([clampi(slot, 0, 255)]))

static func move_inventory_item(source: int, destination: int) -> PackedByteArray:
	return encode(ClientMessage.MOVE_INVENTORY_ITEM, PackedByteArray([
		clampi(source, 0, 255), clampi(destination, 0, 255)]))

static func cast_spell(sigils: Array[int]) -> PackedByteArray:
	assert(sigils.size() >= 2 and sigils.size() <= 6)
	var payload: PackedByteArray = PackedByteArray([sigils.size()])
	for sigil_id: int in sigils:
		assert(sigil_id >= 0 and sigil_id <= 63)
		payload.append(sigil_id)
	return encode(ClientMessage.CAST_SPELL, payload)

static func attack_actor(actor_id: int) -> PackedByteArray:
	return encode(ClientMessage.ATTACK_SOMEONE, PackedByteArray([
		actor_id & 0xff, (actor_id >> 8) & 0xff,
		(actor_id >> 16) & 0xff, (actor_id >> 24) & 0xff]))

static func trade_with(actor_id: int) -> PackedByteArray:
	return encode(ClientMessage.TRADE_WITH, PackedByteArray([
		actor_id & 0xff, (actor_id >> 8) & 0xff,
		(actor_id >> 16) & 0xff, (actor_id >> 24) & 0xff]))

static func put_inventory_on_trade(source_slot: int, quantity: int) -> PackedByteArray:
	var payload: PackedByteArray = PackedByteArray([
		1, clampi(source_slot, 0, 255),
		quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff])
	return encode(ClientMessage.PUT_OBJECT_ON_TRADE, payload)

static func remove_trade_item(offer_slot: int, quantity: int) -> PackedByteArray:
	var payload: PackedByteArray = PackedByteArray([
		clampi(offer_slot, 0, 15), quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff])
	return encode(ClientMessage.REMOVE_OBJECT_FROM_TRADE, payload)

static func accept_trade(destinations: PackedByteArray = PackedByteArray()) -> PackedByteArray:
	var payload: PackedByteArray = destinations.slice(0, 16)
	while payload.size() < 16:
		payload.append(1)
	for index: int in range(payload.size()):
		payload[index] = 2 if int(payload[index]) == 2 else 1
	return encode(ClientMessage.ACCEPT_TRADE, payload)

static func reject_trade() -> PackedByteArray:
	return encode(ClientMessage.REJECT_TRADE)

static func exit_trade() -> PackedByteArray:
	return encode(ClientMessage.EXIT_TRADE)

static func look_at_trade_item(offer_slot: int, other: bool) -> PackedByteArray:
	return encode(ClientMessage.LOOK_AT_TRADE_ITEM,
		PackedByteArray([clampi(offer_slot, 0, 15), 1 if other else 0]))

static func get_storage_category(category_id: int) -> PackedByteArray:
	return encode(ClientMessage.GET_STORAGE_CATEGORY,
		PackedByteArray([clampi(category_id, 0, 255)]))

static func deposit_storage(inventory_slot: int, quantity: int) -> PackedByteArray:
	return encode(ClientMessage.DEPOSIT_ITEM, PackedByteArray([
		clampi(inventory_slot, 0, 255), quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff]))

static func withdraw_storage(position: int, quantity: int) -> PackedByteArray:
	return encode(ClientMessage.WITHDRAW_ITEM, PackedByteArray([
		position & 0xff, (position >> 8) & 0xff,
		quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff]))

static func look_at_storage_item(position: int) -> PackedByteArray:
	return encode(ClientMessage.LOOK_AT_STORAGE_ITEM,
		PackedByteArray([position & 0xff, (position >> 8) & 0xff]))

static func inspect_bag(bag_id: int) -> PackedByteArray:
	return encode(ClientMessage.INSPECT_BAG,
		PackedByteArray([clampi(bag_id, 0, 255)]))

static func close_bag() -> PackedByteArray:
	return encode(ClientMessage.CLOSE_BAG)

static func pick_up_ground_item(position: int, quantity: int) -> PackedByteArray:
	return encode(ClientMessage.PICK_UP_ITEM, PackedByteArray([
		clampi(position, 0, 255), quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff]))

static func drop_inventory_item(slot: int, quantity: int) -> PackedByteArray:
	return encode(ClientMessage.DROP_ITEM, PackedByteArray([
		clampi(slot, 0, 255), quantity & 0xff, (quantity >> 8) & 0xff,
		(quantity >> 16) & 0xff, (quantity >> 24) & 0xff]))

static func get_knowledge_info(index: int) -> PackedByteArray:
	return encode(ClientMessage.GET_KNOWLEDGE_INFO,
		PackedByteArray([index & 0xff, (index >> 8) & 0xff]))

static func manufacture(ingredients: Array[Dictionary], wanted: int = 1) -> PackedByteArray:
	# Legacy mix_handler(): count:u8, repeated slot:u8 + quantity:u16le,
	# then wanted:u8. The six-entry cap is the legacy manufacture tray size.
	assert(ingredients.size() >= 1 and ingredients.size() <= 6)
	assert(wanted >= 1 and wanted <= 255)
	var payload: PackedByteArray = PackedByteArray([ingredients.size()])
	for ingredient: Dictionary in ingredients:
		var slot: int = int(ingredient.get("slot", -1))
		var quantity: int = int(ingredient.get("quantity", 0))
		assert(slot >= 0 and slot <= 35)
		assert(quantity >= 1 and quantity <= 0xffff)
		payload.append(slot)
		payload.append(quantity & 0xff)
		payload.append((quantity >> 8) & 0xff)
	payload.append(wanted)
	return encode(ClientMessage.MANUFACTURE_THIS, payload)

static func actor_command_step(command: int) -> Vector2i:
	# Server movement frames are the authoritative one-tile updates used by the
	# legacy client. Walk and run use the same tile delta; timing differs.
	var direction: int = command
	if command >= 30 and command <= 37:
		direction = command - 10
	match direction:
		20: return Vector2i(0, 1)
		21: return Vector2i(1, 1)
		22: return Vector2i(1, 0)
		23: return Vector2i(1, -1)
		24: return Vector2i(0, -1)
		25: return Vector2i(-1, -1)
		26: return Vector2i(-1, 0)
		27: return Vector2i(-1, 1)
		_: return Vector2i.ZERO

static func actor_command_direction(command: int) -> Vector2i:
	var direction: int = command
	if command >= 30 and command <= 37:
		direction = command - 10
	elif command >= 38 and command <= 45:
		direction = command - 18
	match direction:
		20: return Vector2i(0, 1)
		21: return Vector2i(1, 1)
		22: return Vector2i(1, 0)
		23: return Vector2i(1, -1)
		24: return Vector2i(0, -1)
		25: return Vector2i(-1, -1)
		26: return Vector2i(-1, 0)
		27: return Vector2i(-1, 1)
		_: return Vector2i.ZERO

static func decode_server(command: int, payload: PackedByteArray) -> Dictionary:
	match command:
		ServerMessage.LOG_IN_OK:
			return {"type": "login_ok"}
		ServerMessage.LOG_IN_NOT_OK:
			return {"type": "login_error", "message": nul_string(payload)}
		ServerMessage.CREATE_CHAR_OK:
			return {"type": "create_character_ok"}
		ServerMessage.CREATE_CHAR_NOT_OK:
			return {"type": "create_character_error", "message": nul_string(payload)}
		ServerMessage.YOU_ARE:
			return {"type": "you_are", "actor_id": u16(payload)} if payload.size() >= 2 else {"type": "invalid", "error": "short_payload"}
		ServerMessage.CHANGE_MAP:
			return {"type": "change_map", "map_name": nul_string(payload)}
		ServerMessage.REMOVE_ACTOR:
			return {"type": "remove_actor", "actor_id": u16(payload)} if payload.size() >= 2 else {"type": "invalid", "error": "short_payload"}
		ServerMessage.KILL_ALL_ACTORS:
			return {"type": "clear_actors"}
		ServerMessage.ADD_ACTOR_COMMAND:
			if payload.size() % 3 != 0:
				return {"type": "invalid", "error": "actor_command_length"}
			var commands: Array[Dictionary] = []
			for offset in range(0, payload.size(), 3):
				commands.append({"actor_id": u16(payload, offset), "command": int(payload[offset + 2])})
			return {"type": "actor_commands", "commands": commands}
		ServerMessage.ADD_NEW_ACTOR:
			return decode_actor(payload, false)
		ServerMessage.ADD_NEW_ENHANCED_ACTOR:
			return decode_actor(payload, true)
		ServerMessage.HERE_YOUR_STATS:
			return decode_stats(payload)
		ServerMessage.SEND_PARTIAL_STAT:
			return decode_partial_stats(payload)
		ServerMessage.HERE_YOUR_INVENTORY:
			return decode_inventory(payload)
		ServerMessage.GET_NEW_INVENTORY_ITEM:
			return decode_inventory_update(payload)
		ServerMessage.REMOVE_ITEM_FROM_INVENTORY:
			if payload.is_empty():
				return {"type": "invalid", "error": "inventory_remove_length"}
			var removed_slots: Array[int] = []
			for slot_value: int in payload:
				removed_slots.append(slot_value)
			return {"type": "inventory_remove", "slots": removed_slots}
		ServerMessage.INVENTORY_ITEM_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "inventory_text_length"}
			return {"type": "inventory_text", "color": int(payload[0]),
				"text": nul_string(payload.slice(1))}
		ServerMessage.GET_NEW_BAG:
			return decode_ground_bag(payload)
		ServerMessage.GET_BAGS_LIST:
			return decode_ground_bags(payload)
		ServerMessage.DESTROY_BAG:
			if payload.size() != 1:
				return {"type": "invalid", "error": "ground_bag_destroy_length"}
			return {"type": "ground_bag_destroy", "bag_id": int(payload[0])}
		ServerMessage.HERE_YOUR_GROUND_ITEMS:
			return decode_ground_items(payload)
		ServerMessage.GET_NEW_GROUND_ITEM:
			if payload.size() != 7:
				return {"type": "invalid", "error": "ground_item_length"}
			return {"type": "ground_item", "item": decode_ground_item(payload)}
		ServerMessage.REMOVE_ITEM_FROM_GROUND:
			if payload.size() != 1:
				return {"type": "invalid", "error": "ground_item_remove_length"}
			return {"type": "ground_item_remove", "position": int(payload[0])}
		ServerMessage.CLOSE_BAG:
			if not payload.is_empty():
				return {"type": "invalid", "error": "ground_bag_close_length"}
			return {"type": "ground_bag_close"}
		ServerMessage.GET_KNOWLEDGE_LIST:
			var known: Array[int] = []
			for byte_index: int in range(payload.size()):
				for bit_index: int in range(8):
					if (int(payload[byte_index]) & (1 << bit_index)) != 0:
						known.append(byte_index * 8 + bit_index)
			return {"type": "knowledge_list", "known": known,
				"capacity": payload.size() * 8}
		ServerMessage.GET_NEW_KNOWLEDGE:
			if payload.size() != 2:
				return {"type": "invalid", "error": "new_knowledge_length"}
			return {"type": "new_knowledge", "index": u16(payload)}
		ServerMessage.GET_KNOWLEDGE_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "knowledge_text_length"}
			return {"type": "knowledge_text", "text": nul_string(payload)}
		ServerMessage.GET_ITEMS_COOLDOWN:
			return decode_item_cooldowns(payload)
		ServerMessage.GET_TRADE_PARTNER_NAME:
			if payload.size() < 2:
				return {"type": "invalid", "error": "trade_partner_length"}
			return {"type": "trade_partner", "storage_available": bool(payload[0]),
				"name": nul_string(payload.slice(1))}
		ServerMessage.GET_YOUR_TRADEOBJECTS:
			var trade_inventory: Dictionary = decode_inventory(payload)
			if trade_inventory.get("type", "") == "inventory":
				trade_inventory["type"] = "trade_inventory"
			return trade_inventory
		ServerMessage.GET_TRADE_OBJECT:
			if payload.size() != 9:
				return {"type": "invalid", "error": "trade_object_length"}
			return {"type": "trade_object", "image_id": u16(payload),
				"quantity": u32(payload, 2), "source_type": int(payload[6]),
				"slot": int(payload[7]), "other": bool(payload[8])}
		ServerMessage.REMOVE_TRADE_OBJECT:
			if payload.size() != 6:
				return {"type": "invalid", "error": "trade_remove_length"}
			return {"type": "trade_remove", "quantity": u32(payload),
				"slot": int(payload[4]), "other": bool(payload[5])}
		ServerMessage.GET_TRADE_ACCEPT:
			if payload.size() != 1:
				return {"type": "invalid", "error": "trade_accept_length"}
			return {"type": "trade_accept", "other": bool(payload[0])}
		ServerMessage.GET_TRADE_REJECT:
			if payload.size() != 1:
				return {"type": "invalid", "error": "trade_reject_length"}
			return {"type": "trade_reject", "other": bool(payload[0])}
		ServerMessage.GET_TRADE_EXIT:
			if not payload.is_empty():
				return {"type": "invalid", "error": "trade_exit_length"}
			return {"type": "trade_exit"}
		ServerMessage.STORAGE_LIST:
			return decode_storage_categories(payload)
		ServerMessage.STORAGE_ITEMS:
			return decode_storage_items(payload)
		ServerMessage.STORAGE_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "storage_text_length"}
			return {"type": "storage_text", "color": int(payload[0]),
				"text": nul_string(payload.slice(1))}
		ServerMessage.GET_YOUR_SIGILS:
			if payload.size() != 8:
				return {"type": "invalid", "error": "sigils_length"}
			var owned_sigils: Array[int] = []
			for sigil_id: int in range(64):
				var mask_offset: int = 0 if sigil_id < 32 else 4
				var mask_bit: int = sigil_id if sigil_id < 32 else sigil_id - 32
				if (u32(payload, mask_offset) & (1 << mask_bit)) != 0:
					owned_sigils.append(sigil_id)
			return {"type": "sigils", "owned": owned_sigils,
				"low_mask": u32(payload), "high_mask": u32(payload, 4)}
		ServerMessage.SPELL_CAST:
			if payload.size() < 2 or int(payload[0]) < 1 or int(payload[0]) > 6:
				return {"type": "invalid", "error": "spell_result_length"}
			return {"type": "spell_result", "status": int(payload[0]),
				"spell_id": int(payload[1])}
		ServerMessage.GET_ACTIVE_SPELL:
			if payload.size() != 2:
				return {"type": "invalid", "error": "active_spell_length"}
			return {"type": "active_spell", "buff_id": int(payload[0]),
				"duration_seconds": int(payload[1])}
		ServerMessage.GET_ACTIVE_SPELL_LIST:
			if payload.size() != 10:
				return {"type": "invalid", "error": "active_spell_list_length"}
			var active_buffs: Array[int] = []
			for buff_id: int in payload:
				if buff_id != 255:
					active_buffs.append(buff_id)
			return {"type": "active_spell_list", "buffs": active_buffs}
		ServerMessage.REMOVE_ACTIVE_SPELL:
			if payload.size() != 1:
				return {"type": "invalid", "error": "remove_active_spell_length"}
			return {"type": "remove_active_spell", "buff_id": int(payload[0])}
		ServerMessage.ACTOR_WEAR_ITEM:
			if payload.size() != 4:
				return {"type": "invalid", "error": "actor_wear_length"}
			return {"type": "actor_wear", "actor_id": u16(payload),
				"part": int(payload[2]), "visual_id": int(payload[3])}
		ServerMessage.ACTOR_UNWEAR_ITEM:
			if payload.size() != 3:
				return {"type": "invalid", "error": "actor_unwear_length"}
			return {"type": "actor_unwear", "actor_id": u16(payload),
				"part": int(payload[2])}
		ServerMessage.GET_ACTOR_DAMAGE:
			if payload.size() != 4:
				return {"type": "invalid", "error": "actor_damage_length"}
			return {"type": "actor_damage", "actor_id": u16(payload),
				"amount": u16(payload, 2)}
		ServerMessage.GET_ACTOR_HEAL:
			if payload.size() != 4:
				return {"type": "invalid", "error": "actor_heal_length"}
			return {"type": "actor_heal", "actor_id": u16(payload),
				"amount": u16(payload, 2)}
		ServerMessage.GET_ACTOR_HEALTH:
			if payload.size() != 4:
				return {"type": "invalid", "error": "actor_health_length"}
			return {"type": "actor_max_health", "actor_id": u16(payload),
				"max_health": u16(payload, 2)}
		ServerMessage.RAW_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "chat_length"}
			return {"type": "chat", "channel": int(payload[0]),
				"text": legacy_colored_string(payload.slice(1))}
		ServerMessage.SEND_NPC_INFO:
			if payload.size() < 20:
				return {"type": "invalid", "error": "npc_info_length"}
			return {"type": "npc_info", "name": nul_string(payload.slice(0, 20)),
				"portrait": int(payload[20]) if payload.size() > 20 else 0}
		ServerMessage.NPC_TEXT:
			return {"type": "npc_text", "text": nul_string(payload)}
		ServerMessage.NPC_OPTIONS_LIST:
			return decode_npc_options(payload)
		ServerMessage.CLOSE_NPC_MENU:
			return {"type": "npc_close"}
		ServerMessage.PING_REQUEST:
			return {"type": "ping_request"}
		_:
			return {"type": "unknown", "command": command, "payload": payload}

static func decode_npc_options(payload: PackedByteArray) -> Dictionary:
	var options: Array[Dictionary] = []
	var offset: int = 0
	while offset < payload.size():
		if offset + 2 > payload.size():
			return {"type": "invalid", "error": "npc_option_size"}
		var text_size: int = u16(payload, offset)
		offset += 2
		if text_size < 1 or offset + text_size + 4 > payload.size():
			return {"type": "invalid", "error": "npc_option_length"}
		var label: String = nul_string(payload.slice(offset, offset + text_size))
		offset += text_size
		var response_id: int = u16(payload, offset)
		var actor_id: int = u16(payload, offset + 2)
		offset += 4
		options.append({"label": label, "response_id": response_id, "actor_id": actor_id})
	return {"type": "npc_options", "options": options}

static func decode_storage_categories(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty():
		return {"type": "invalid", "error": "storage_categories_length"}
	var categories: Array[Dictionary] = []
	var offset: int = 1
	for _index: int in range(int(payload[0])):
		if offset >= payload.size():
			return {"type": "invalid", "error": "storage_category_length"}
		var category_id: int = int(payload[offset])
		offset += 1
		var terminator: int = payload.find(0, offset)
		if terminator < 0:
			return {"type": "invalid", "error": "storage_category_name"}
		categories.append({"id": category_id,
			"name": payload.slice(offset, terminator).get_string_from_utf8()})
		offset = terminator + 1
	if offset != payload.size():
		return {"type": "invalid", "error": "storage_categories_trailing"}
	return {"type": "storage_categories", "categories": categories}

static func decode_ground_bag(payload: PackedByteArray) -> Dictionary:
	if payload.size() != 5:
		return {"type": "invalid", "error": "ground_bag_length"}
	return {"type": "ground_bag", "x": u16(payload), "y": u16(payload, 2),
		"bag_id": int(payload[4])}

static func decode_ground_bags(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty() or payload.size() != 1 + int(payload[0]) * 5:
		return {"type": "invalid", "error": "ground_bags_length"}
	var bags: Array[Dictionary] = []
	for index: int in range(int(payload[0])):
		var offset: int = 1 + index * 5
		bags.append({"x": u16(payload, offset), "y": u16(payload, offset + 2),
			"bag_id": int(payload[offset + 4])})
	return {"type": "ground_bags", "bags": bags}

static func decode_ground_items(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty() or payload.size() != 1 + int(payload[0]) * 7:
		return {"type": "invalid", "error": "ground_items_length"}
	var items: Array[Dictionary] = []
	for index: int in range(int(payload[0])):
		items.append(decode_ground_item(payload, 1 + index * 7))
	return {"type": "ground_items", "items": items}

static func decode_ground_item(payload: PackedByteArray, offset: int = 0) -> Dictionary:
	return {"image_id": u16(payload, offset), "quantity": u32(payload, offset + 2),
		"position": int(payload[offset + 6])}

static func decode_storage_items(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2 or (payload.size() - 2) % 8 != 0:
		return {"type": "invalid", "error": "storage_items_length"}
	var update: bool = int(payload[0]) == 255
	if int(payload[0]) not in [0, 255]:
		return {"type": "invalid", "error": "storage_items_mode"}
	var items: Array[Dictionary] = []
	for offset: int in range(2, payload.size(), 8):
		items.append({"image_id": u16(payload, offset),
			"quantity": u32(payload, offset + 2),
			"position": u16(payload, offset + 6)})
	return {"type": "storage_items", "category_id": int(payload[1]),
		"update": update, "items": items}

static func decode_stats(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 230:
		return {"type": "invalid", "error": "stats_length"}
	var values: Dictionary = {}
	var attribute_names: Array[String] = [
		"physique", "coordination", "reasoning", "will", "instinct", "vitality",
		"human_nexus", "animal_nexus", "vegetal_nexus", "inorganic_nexus",
		"artificial_nexus", "magic_nexus"]
	for index: int in range(attribute_names.size()):
		values[attribute_names[index]] = s16(payload, index * 4)
	var skills: Dictionary = {
		"manufacturing": 24, "harvesting": 26, "alchemy": 28, "overall": 30,
		"attack": 32, "defense": 34, "magic": 36, "potion": 38,
		"summoning": 83, "crafting": 89, "engineering": 95,
		"tailoring": 101, "ranging": 107}
	for skill_name: String in skills:
		values[skill_name] = s16(payload, int(skills[skill_name]) * 2)
	for resource: String in ["carried", "capacity", "health", "max_health", "ether", "max_ether"]:
		var resource_index: int = ["carried", "capacity", "health", "max_health", "ether", "max_ether"].find(resource)
		values[resource] = s16(payload, (40 + resource_index) * 2)
	values["food"] = s16(payload, 46 * 2)
	return {"type": "stats", "values": values}

static func decode_partial_stats(payload: PackedByteArray) -> Dictionary:
	if payload.size() % 5 != 0:
		return {"type": "invalid", "error": "partial_stats_length"}
	var values: Dictionary = {}
	for offset: int in range(0, payload.size(), 5):
		var slot: int = int(payload[offset])
		values[stat_key(slot)] = s32(payload, offset + 1)
	return {"type": "partial_stats", "values": values}

static func decode_inventory(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty():
		return {"type": "invalid", "error": "inventory_length"}
	var count: int = int(payload[0])
	var entry_size: int = 8
	if payload.size() == 1 + count * 10:
		entry_size = 10
	elif payload.size() != 1 + count * 8:
		return {"type": "invalid", "error": "inventory_length"}
	var items: Array[Dictionary] = []
	for index: int in range(count):
		var offset: int = 1 + index * entry_size
		items.append(decode_inventory_item(payload, offset, entry_size == 10))
	return {"type": "inventory", "items": items}

static func decode_inventory_update(payload: PackedByteArray) -> Dictionary:
	if payload.size() != 8 and payload.size() != 10:
		return {"type": "invalid", "error": "inventory_update_length"}
	return {"type": "inventory_update",
		"item": decode_inventory_item(payload, 0, payload.size() == 10)}

static func decode_inventory_item(payload: PackedByteArray, offset: int,
		with_uid: bool) -> Dictionary:
	var flags: int = int(payload[offset + 7])
	var item: Dictionary = {
		"image_id": u16(payload, offset), "quantity": u32(payload, offset + 2),
		"slot": int(payload[offset + 6]), "flags": flags,
		"reagent": (flags & 1) != 0, "resource": (flags & 2) != 0,
		"stackable": (flags & 4) != 0, "inventory_usable": (flags & 8) != 0,
		"tile_usable": (flags & 16) != 0, "player_usable": (flags & 32) != 0,
		"object_usable": (flags & 64) != 0, "on_off": (flags & 128) != 0}
	if with_uid:
		item["uid"] = u16(payload, offset + 8)
	return item

static func decode_item_cooldowns(payload: PackedByteArray) -> Dictionary:
	if payload.size() % 5 != 0:
		return {"type": "invalid", "error": "item_cooldown_length"}
	var cooldowns: Array[Dictionary] = []
	for offset: int in range(0, payload.size(), 5):
		cooldowns.append({"slot": int(payload[offset]),
			"maximum_seconds": u16(payload, offset + 1),
			"remaining_seconds": u16(payload, offset + 3)})
	return {"type": "item_cooldowns", "cooldowns": cooldowns}

static func stat_key(slot: int) -> String:
	var keys: Dictionary = {
		40: "carried", 41: "capacity", 42: "health", 43: "max_health",
		44: "ether", 45: "max_ether", 46: "food",
		24: "manufacturing", 26: "harvesting", 28: "alchemy", 30: "overall",
		32: "attack", 34: "defense", 36: "magic", 38: "potion",
		83: "summoning", 89: "crafting", 95: "engineering",
		101: "tailoring", 107: "ranging"}
	return str(keys.get(slot, "slot_%d" % slot))

static func decode_actor(payload: PackedByteArray, enhanced: bool) -> Dictionary:
	var minimum := 31 if enhanced else 18
	if payload.size() < minimum:
		return {"type": "invalid", "error": "actor_length"}
	var actor := {
		"type": "actor_spawn", "enhanced": enhanced, "actor_id": u16(payload),
		"x": u16(payload, 2) & 0x7ff, "y": u16(payload, 4) & 0x7ff,
		"rotation": s16(payload, 8), "actor_type": int(payload[10])}
	if enhanced:
		actor["appearance"] = {
			"skin": int(payload[12]), "hair": int(payload[13]), "shirt": int(payload[14]),
			"pants": int(payload[15]), "boots": int(payload[16]), "head": int(payload[17]),
			"shield": int(payload[18]), "weapon": int(payload[19]),
			"cape": int(payload[20]), "helmet": int(payload[21])}
		actor["equipment_visuals"] = {
			0: int(payload[19]), 1: int(payload[18]), 2: int(payload[20]),
			3: int(payload[21]), 4: int(payload[15]), 5: int(payload[14]),
			6: int(payload[16])}
		actor["equipment_fallback_parts"] = []
		actor["frame"] = int(payload[22])
		actor["max_health"] = u16(payload, 23)
		actor["health"] = u16(payload, 25)
		actor["kind"] = int(payload[27])
		actor["name"] = nul_string(payload.slice(28, min(payload.size(), 58)))
	else:
		actor["frame"] = int(payload[11])
		actor["max_health"] = u16(payload, 12)
		actor["health"] = u16(payload, 14)
		actor["kind"] = int(payload[16])
		actor["name"] = nul_string(payload.slice(17, min(payload.size(), 47)))
	actor["alive"] = int(actor.get("health", 0)) > 0
	actor["in_combat"] = false
	return actor

static func nul_string(bytes: PackedByteArray) -> String:
	var end := bytes.find(0)
	var clean := bytes if end < 0 else bytes.slice(0, end)
	return clean.get_string_from_utf8()

static func legacy_colored_string(bytes: PackedByteArray) -> String:
	# EL color markers occupy the C1-control range. Preserve bytes in valid
	# UTF-8 multibyte sequences so non-ASCII chat is not damaged while removing
	# standalone presentation controls from the text DTO.
	var end: int = bytes.find(0)
	var source: PackedByteArray = bytes if end < 0 else bytes.slice(0, end)
	var clean: PackedByteArray = PackedByteArray()
	var continuation_bytes: int = 0
	for byte_value: int in source:
		if continuation_bytes > 0:
			if byte_value >= 0x80 and byte_value <= 0xbf:
				clean.append(byte_value)
				continuation_bytes -= 1
				continue
			continuation_bytes = 0
		if byte_value >= 0x7f and byte_value <= 0x9f:
			continue
		clean.append(byte_value)
		if byte_value >= 0xc2 and byte_value <= 0xdf:
			continuation_bytes = 1
		elif byte_value >= 0xe0 and byte_value <= 0xef:
			continuation_bytes = 2
		elif byte_value >= 0xf0 and byte_value <= 0xf4:
			continuation_bytes = 3
	return clean.get_string_from_utf8()

static func u16(bytes: PackedByteArray, offset := 0) -> int:
	return int(bytes[offset]) | (int(bytes[offset + 1]) << 8)

static func s16(bytes: PackedByteArray, offset := 0) -> int:
	var value := u16(bytes, offset)
	return value - 65536 if value >= 32768 else value

static func u32(bytes: PackedByteArray, offset := 0) -> int:
	return (int(bytes[offset]) | (int(bytes[offset + 1]) << 8)
		| (int(bytes[offset + 2]) << 16) | (int(bytes[offset + 3]) << 24))

static func s32(bytes: PackedByteArray, offset := 0) -> int:
	var value: int = u32(bytes, offset)
	return value - 4294967296 if value >= 2147483648 else value
