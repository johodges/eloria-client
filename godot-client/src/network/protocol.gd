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
	HERE_YOUR_GROUND_ITEMS = 23, REMOVE_ITEM_FROM_GROUND = 25, CLOSE_BAG = 26,
	GET_NEW_BAG = 27, GET_BAGS_LIST = 28, DESTROY_BAG = 29, NPC_TEXT = 30,
	NPC_OPTIONS_LIST = 31, CLOSE_NPC_MENU = 32, SEND_NPC_INFO = 33,
	ADD_NEW_ENHANCED_ACTOR = 51, ACTOR_WEAR_ITEM = 52, ACTOR_UNWEAR_ITEM = 53,
	PING_REQUEST = 60, GET_ACTIVE_CHANNELS = 71, GET_ACTOR_HEALTH = 73,
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

static func sit_toggle() -> PackedByteArray:
	return encode(ClientMessage.SIT_DOWN)

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
		ServerMessage.RAW_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "chat_length"}
			return {"type": "chat", "channel": int(payload[0]),
				"text": nul_string(payload.slice(1))}
		ServerMessage.PING_REQUEST:
			return {"type": "ping_request"}
		_:
			return {"type": "unknown", "command": command, "payload": payload}

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
	return actor

static func nul_string(bytes: PackedByteArray) -> String:
	var end := bytes.find(0)
	var clean := bytes if end < 0 else bytes.slice(0, end)
	return clean.get_string_from_utf8()

static func u16(bytes: PackedByteArray, offset := 0) -> int:
	return int(bytes[offset]) | (int(bytes[offset + 1]) << 8)

static func s16(bytes: PackedByteArray, offset := 0) -> int:
	var value := u16(bytes, offset)
	return value - 65536 if value >= 32768 else value
