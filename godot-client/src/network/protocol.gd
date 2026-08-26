class_name EloriaProtocol
extends RefCounted

const HEADER_SIZE := 3
const MAX_PAYLOAD := 65532

enum ClientMessage {
	RAW_TEXT = 0, MOVE_TO = 1, SEND_PM = 2, GET_PLAYER_INFO = 5, RUN_TO = 6,
	SIT_DOWN = 7, SEND_ME_MY_ACTORS = 8, SEND_VERSION = 10, PING = 13,
	HEART_BEAT = 14, LOCATE_ME = 15, USE_MAP_OBJECT = 16, SEND_MY_STATS = 17,
	SEND_MY_INVENTORY = 18, LOOK_AT_INVENTORY_ITEM = 19, MOVE_INVENTORY_ITEM = 20,
	HARVEST = 21, DROP_ITEM = 22, PICK_UP_ITEM = 23, INSPECT_BAG = 25,
	CLOSE_BAG = 26, LOOK_AT_MAP_OBJECT = 27, TOUCH_PLAYER = 28,
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
	LOG_IN_OK = 250, LOG_IN_NOT_OK = 251, CREATE_CHAR_OK = 252,
	CREATE_CHAR_NOT_OK = 253, PING_REQUEST = 60, GET_ACTIVE_CHANNELS = 71,
	GET_ACTOR_HEALTH = 73, GET_ITEMS_COOLDOWN = 77, SEND_BUFFS = 78,
	SEND_SPECIAL_EFFECT = 79, DISPLAY_POPUP = 83, SEND_MAP_MARKER = 90,
	REMOVE_MAP_MARKER = 91, SEND_ACHIEVEMENTS = 95
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
	var wire_length := int(buffer[1]) | (int(buffer[2]) << 8)
	if wire_length < 1 or wire_length - 1 > MAX_PAYLOAD:
		return {"status": "error", "error": "invalid_packet_length"}
	var total := wire_length + 2
	if buffer.size() < total:
		return {"status": "incomplete"}
	return {
		"status": "ok", "command": int(buffer[0]),
		"payload": buffer.slice(HEADER_SIZE, total),
		"consumed": total
	}

static func c_string(value: String, encoding := "latin-1") -> PackedByteArray:
	var bytes := value.to_utf8_buffer() if encoding == "utf-8" else value.to_ascii_buffer()
	bytes.append(0)
	return bytes

static func login(username: String, password: String) -> PackedByteArray:
	# Matches legacy LOG_IN payload: username NUL password NUL. Never log this frame.
	var payload := c_string(username)
	payload.append_array(c_string(password))
	return encode(ClientMessage.LOG_IN, payload)

static func move_to(x: int, y: int, run := false) -> PackedByteArray:
	var payload := PackedByteArray([x & 0xff, (x >> 8) & 0xff, y & 0xff, (y >> 8) & 0xff])
	return encode(ClientMessage.RUN_TO if run else ClientMessage.MOVE_TO, payload)
