class_name EloriaProtocol
extends RefCounted

const HEADER_SIZE := 3
# Actor animation frames. Only the two resting frames are meaningful in an
# actor packet; the rest are transient states the server does not spawn into.
const FRAME_IDLE := 7
const FRAME_COMBAT_IDLE := 15
## The only actor-buff bit this server sets: doubled movement speed.
const ACTOR_BUFF_DOUBLE_SPEED := 1024
const MAX_PAYLOAD := 65532

enum ClientMessage {
	RAW_TEXT = 0, MOVE_TO = 1, SEND_PM = 2, GET_PLAYER_INFO = 5, RUN_TO = 6,
	SIT_DOWN = 7, SEND_ME_MY_ACTORS = 8, SEND_OPENING_SCREEN = 9, SEND_VERSION = 10,
	TURN_LEFT = 11, TURN_RIGHT = 12,
	PING = 13, HEART_BEAT = 14, LOCATE_ME = 15, USE_MAP_OBJECT = 16,
	SEND_MY_STATS = 17, SEND_MY_INVENTORY = 18, LOOK_AT_INVENTORY_ITEM = 19,
	MOVE_INVENTORY_ITEM = 20, HARVEST = 21, DROP_ITEM = 22, PICK_UP_ITEM = 23,
	LOOK_AT_GROUND_ITEM = 24, INSPECT_BAG = 25, CLOSE_BAG = 26, LOOK_AT_MAP_OBJECT = 27, TOUCH_PLAYER = 28,
	RESPOND_TO_NPC = 29, MANUFACTURE_THIS = 30, USE_INVENTORY_ITEM = 31,
	TRADE_WITH = 32, ACCEPT_TRADE = 33, REJECT_TRADE = 34, EXIT_TRADE = 35,
	PUT_OBJECT_ON_TRADE = 36, REMOVE_OBJECT_FROM_TRADE = 37,
	LOOK_AT_TRADE_ITEM = 38, CAST_SPELL = 39, ATTACK_SOMEONE = 40,
	GET_KNOWLEDGE_INFO = 41,
	# Client-to-server; 42 and 70 are also server-to-client numbers, the way
	# the storage commands below share 44-46. The direction tells them apart.
	ITEM_ON_ITEM = 42, DO_EMOTE = 70, FIRE_MISSILE_AT_OBJECT = 51,
	WHAT_QUEST_IS_THIS_ID = 63,
	GET_STORAGE_CATEGORY = 44, DEPOSIT_ITEM = 45,
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
	MISSILE_AIM_A_AT_B = 84, MISSILE_FIRE_A_TO_B = 86,
	MISSILE_AIM_A_AT_XYZ = 85, MISSILE_FIRE_A_TO_XYZ = 87,
	PLAY_SOUND = 14, PLAY_MUSIC = 54,
	START_RAIN = 15, STOP_RAIN = 16, THUNDER = 17,
	FIRE_PARTICLES = 61, REMOVE_FIRE_AT = 62, SEND_WEATHER = 100,
	NEXT_NPC_MESSAGE_IS_QUEST = 92, HERE_IS_QUEST_ID = 93, QUEST_FINISHED = 94,
	BUDDY_EVENT = 59,
	GET_TELEPORTERS_LIST = 10, TELEPORT_IN = 12, TELEPORT_OUT = 13,
	GET_3D_OBJ_LIST = 74, GET_3D_OBJ = 75, REMOVE_3D_OBJ = 76,
	DISPLAY_POPUP = 83, SEND_MAP_MARKER = 90, REMOVE_MAP_MARKER = 91,
	SEND_ACHIEVEMENTS = 95, ADD_NEW_ACTOR_EXTENDED = 247,
	ELORIA_INVASION_ASSISTANT_STATE = 233,
	ELORIA_PERKS = 234, ELORIA_ACTIVITY_COUNTERS = 235,
	ELORIA_MAP_OBJECTS = 236, ELORIA_HARVEST_STATE = 237,
	ELORIA_MARKETPLACE_STATE = 222, ELORIA_MERCHANT_STATE = 223,
	ELORIA_QUEST_JOURNAL_STATE = 224, ELORIA_ITEM_DETAIL = 225,
	ELORIA_INVENTORY_STATE = 226, ELORIA_COMBAT_STATE = 227,
	ELORIA_MAIL_STATE = 229, ELORIA_NAVIGATION_STATE = 230,
	ELORIA_SPECIAL_EVENT_STATE = 232, ELORIA_PLAYER_INFO = 228,
	ELORIA_SPELL_POWER = 231,
	ELORIA_ALMANAC_STATE = 238, ELORIA_STORAGE_STATE = 239,
	ELORIA_PARTY_STATE = 240, ELORIA_QUEST_ARCHIVE_STATE = 241,
	ELORIA_DEGRADED_ITEMS = 242, ELORIA_WORN_SLOTS = 243,
	ELORIA_ACHIEVEMENTS_STATE = 244, ELORIA_EXPERIENCE_STATE = 245,
	ELORIA_ACTOR_FOOTPRINTS = 246,
	ADD_ACTOR_ANIMATION = 89,
	LOG_IN_OK = 250, LOG_IN_NOT_OK = 251,
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

## Decodes the packet that starts at `offset`. Reading in place lets a caller
## drain a burst of packets from one receive buffer without re-slicing the
## remainder after each of them. `consumed` stays relative to `offset`.
static func try_decode(buffer: PackedByteArray, offset := 0) -> Dictionary:
	var available := buffer.size() - offset
	if available < HEADER_SIZE:
		return {"status": "incomplete"}
	var wire_length := u16(buffer, offset + 1)
	if wire_length < 1 or wire_length - 1 > MAX_PAYLOAD:
		return {"status": "error", "error": "invalid_packet_length"}
	var total := wire_length + 2
	if available < total:
		return {"status": "incomplete"}
	return {"status": "ok", "command": int(buffer[offset]),
		"payload": buffer.slice(offset + HEADER_SIZE, offset + total),
		"consumed": total}

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

## One 45 degree facing step. The command carries no payload; the server
## answers with the matching CMD_TURN_* actor command, which is what actually
## changes the rendered facing for every client including this one.
static func turn(left: bool) -> PackedByteArray:
	return encode(ClientMessage.TURN_LEFT if left else ClientMessage.TURN_RIGHT)

## Extensions this client actually implements, sent to the server on login as
## `#clientcaps a,b,c`. The server withholds each Eloria extension packet from
## a client that has not claimed it and falls back to legacy dialogue or raw
## text instead, so an inaccurate list here is worse than a short one: claiming
## a capability the client cannot decode turns a working dialogue into a packet
## that lands in the protocol diagnostics panel and nowhere else.
##
## Grow this list in the same commit that lands the window which decodes the
## packet, never before.
const CLIENT_CAPABILITIES: Array[String] = [
	"actor16_v1",
	"almanac_v1",
	"combat_hud_v1",
	"inventory_window_v1",
	"item_detail_v1",
	"mail_window_v1",
	"market_window_v1",
	"merchant_window_v1",
	"navigation_hud_v1",
	"party_window_v1",
	"player_info_v1",
	"achievements_window_v1",
	"actor_footprints_v1",
	"degraded_items_v1",
	"experience64_v1",
	"quest_archive_v1",
	"quest_journal_v1",
	"spell_power_v1",
	"special_events_v1",
	"storage_window_v1",
]

## `#clientcaps` is an ordinary chat command; the server parses it out of
## RAW_TEXT and stores the set on the session.
static func client_capabilities() -> PackedByteArray:
	return chat("#clientcaps " + ",".join(PackedStringArray(CLIENT_CAPABILITIES)))

## Ask the server to play an emote. The name rather than a legacy numeric id:
## this server has no such id namespace, and mirroring one here would be a
## second copy of a list the server owns.
## Loose an arrow at a place rather than at somebody. The server decides
## whether the shot is allowed and what it costs.
static func fire_missile_at_object(x: int, y: int) -> PackedByteArray:
	var payload := PackedByteArray()
	payload.resize(4)
	payload.encode_u16(0, x)
	payload.encode_u16(2, y)
	return encode(ClientMessage.FIRE_MISSILE_AT_OBJECT, payload)

## Ask the server what a quest id is. The client never invents a title for an
## id it has not been told about.
static func what_quest_is_this_id(quest_id: int) -> PackedByteArray:
	var payload := PackedByteArray()
	payload.resize(2)
	payload.encode_u16(0, quest_id)
	return encode(ClientMessage.WHAT_QUEST_IS_THIS_ID, payload)

static func do_emote(name: String) -> PackedByteArray:
	var payload: PackedByteArray = name.to_utf8_buffer()
	payload.append(0)
	return encode(ClientMessage.DO_EMOTE, payload)

## Put one carried item onto another. The server decides what, if anything,
## comes of it.
static func item_on_item(source_slot: int, target_slot: int) -> PackedByteArray:
	return encode(ClientMessage.ITEM_ON_ITEM,
		PackedByteArray([source_slot & 0xFF, target_slot & 0xFF]))

static func chat(text: String) -> PackedByteArray:
	var payload: PackedByteArray = text.to_utf8_buffer()
	payload.append(0)
	return encode(ClientMessage.RAW_TEXT, payload)

static func set_active_channel(slot: int) -> PackedByteArray:
	assert(slot >= 0 and slot < 3)
	# The legacy wire values CHAT_CHANNEL1..3 are 5..7. The server keeps the
	# selected public channel behind those three stable UI slots.
	return encode(ClientMessage.SET_ACTIVE_CHANNEL, PackedByteArray([5 + slot]))

static func locate_me() -> PackedByteArray:
	return encode(ClientMessage.LOCATE_ME)

static func get_date() -> PackedByteArray:
	return encode(ClientMessage.GET_DATE)

static func get_time() -> PackedByteArray:
	return encode(ClientMessage.GET_TIME)

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

## Casts a spell by its sigils. A power of zero leaves the byte off entirely,
## which is the legacy frame; anything else appends the fork's trailing power
## byte, and the server decides whether that power is allowed.
static func cast_spell(sigils: Array[int], power: int = 0) -> PackedByteArray:
	assert(sigils.size() >= 2 and sigils.size() <= 6)
	var payload: PackedByteArray = PackedByteArray([sigils.size()])
	for sigil_id: int in sigils:
		assert(sigil_id >= 0 and sigil_id <= 63)
		payload.append(sigil_id)
	if power > 0:
		payload.append(mini(power, 255))
	return encode(ClientMessage.CAST_SPELL, payload)

## Answers a server popup. `answers` maps a group id to either an integer
## option value or a string typed into a text entry; the legacy layout is
## `popup_id:u16le` then, per answered group, `group:u8 | value:u8` for a
## choice or `group:u8 | 0:u8 | length:u8 | text` for an entry. A group the
## player left unanswered is simply absent, which is how the legacy client
## reports "no selection" too.
static func popup_reply(popup_id: int, answers: Dictionary) -> PackedByteArray:
	var payload: PackedByteArray = PackedByteArray([
		popup_id & 0xff, (popup_id >> 8) & 0xff])
	var groups: Array = answers.keys()
	groups.sort()
	for raw_group: Variant in groups:
		var group: int = int(raw_group)
		assert(group >= 0 and group <= 255)
		var answer: Variant = answers[raw_group]
		if answer is String:
			var text: PackedByteArray = (answer as String).to_utf8_buffer().slice(0, 255)
			payload.append(group)
			payload.append(0)
			payload.append(text.size())
			payload.append_array(text)
		else:
			payload.append(group)
			payload.append(int(answer) & 0xff)
	return encode(ClientMessage.POPUP_REPLY, payload)

## Starts, or stops, harvesting one world object. The command is a toggle: the
## server cancels a run already in progress for the same request.
static func harvest(object_id: int) -> PackedByteArray:
	return encode(ClientMessage.HARVEST, PackedByteArray([
		object_id & 0xff, (object_id >> 8) & 0xff]))

## Asks the server to describe an item lying in the open bag. The bag packet
## carries an image id, a quantity and a slot and nothing else, so this is the
## only way to learn what is on the ground.
static func look_at_ground_item(slot: int) -> PackedByteArray:
	return encode(ClientMessage.LOOK_AT_GROUND_ITEM,
		PackedByteArray([slot & 0xff]))

## Asks the server to describe another player. The reply is command 228 for a
## client with `player_info_v1`, and the legacy text plus `SEND_ACHIEVEMENTS`
## for one without.
static func look_at_player(actor_id: int) -> PackedByteArray:
	var payload := PackedByteArray()
	payload.resize(4)
	payload.encode_u32(0, actor_id)
	return encode(ClientMessage.GET_PLAYER_INFO, payload)

## Uses a world object - a waygate, a storage cache, a crafting station. The
## legacy width for both map-object commands is 32 bits.
static func use_map_object(object_id: int) -> PackedByteArray:
	return encode(ClientMessage.USE_MAP_OBJECT, PackedByteArray([
		object_id & 0xff, (object_id >> 8) & 0xff,
		(object_id >> 16) & 0xff, (object_id >> 24) & 0xff]))

static func look_at_map_object(object_id: int) -> PackedByteArray:
	return encode(ClientMessage.LOOK_AT_MAP_OBJECT, PackedByteArray([
		object_id & 0xff, (object_id >> 8) & 0xff,
		(object_id >> 16) & 0xff, (object_id >> 24) & 0xff]))

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

## True for the eight CMD_TURN_* facing commands. A turn command is the
## server's confirmation of a local turn prediction.
static func is_turn_command(command: int) -> bool:
	return command >= 38 and command <= 45

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
		ServerMessage.ELORIA_INVASION_ASSISTANT_STATE:
			var parsed: Variant = JSON.parse_string(payload.get_string_from_utf8())
			if not parsed is Dictionary:
				return {"type": "invalid", "error": "invasion_assistant_json"}
			return {"type": "invasion_assistant", "state": parsed}
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
		ServerMessage.SYNC_CLOCK:
			return {"type": "clock_sync", "server_timestamp": u32(payload)} if payload.size() >= 4 else {"type": "invalid", "error": "clock_sync_length"}
		ServerMessage.NEW_MINUTE:
			return {"type": "new_minute", "minute": u16(payload) % 360} if payload.size() >= 2 else {"type": "invalid", "error": "new_minute_length"}
		ServerMessage.CHANGE_MAP:
			return {"type": "change_map", "map_name": nul_string(payload)}
		ServerMessage.REMOVE_ACTOR:
			# The server batches every actor that left view into one packet -
			# a pack of creatures dying together, or a whole screen of them
			# falling out of visibility range at once. Reading only the first
			# id left the rest standing on the map for good, because the
			# server considers them gone and never repeats the removal.
			if payload.size() < 2:
				return {"type": "invalid", "error": "short_payload"}
			var removed_actor_ids: Array[int] = []
			for offset: int in range(0, payload.size() - 1, 2):
				removed_actor_ids.append(u16(payload, offset))
			return {"type": "remove_actor", "actor_ids": removed_actor_ids}
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
		ServerMessage.ADD_NEW_ACTOR_EXTENDED:
			return decode_actor(payload, false, true)
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
			# The phase is on the wire. Counting accept packets desynchronised
			# the two-phase state machine from the server's view of the trade
			# the moment one was duplicated, dropped or reordered.
			if payload.size() != 2:
				return {"type": "invalid", "error": "trade_accept_length"}
			if int(payload[1]) > 2:
				return {"type": "invalid", "error": "trade_accept_phase"}
			return {"type": "trade_accept", "other": bool(payload[0]),
				"phase": int(payload[1])}
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
		ServerMessage.ELORIA_STORAGE_STATE:
			return decode_storage_state(payload)
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
			# The two raw masks are the wire form of `owned`; carrying both
			# invites two sources of truth for the same fact.
			return {"type": "sigils", "owned": owned_sigils}
		ServerMessage.SPELL_CAST:
			if payload.size() < 2 or int(payload[0]) < 1 or int(payload[0]) > 6:
				return {"type": "invalid", "error": "spell_result_length"}
			return {"type": "spell_result", "status": int(payload[0]),
				"spell_id": int(payload[1])}
		ServerMessage.MISSILE_AIM_A_AT_B, ServerMessage.MISSILE_FIRE_A_TO_B:
			# Both carry the same pair: who is shooting and what at. The
			# server sends an aim before every shot and a fire when it looses,
			# so the two together are the whole engagement.
			if payload.size() != 4:
				return {"type": "invalid", "error": "missile_length"}
			return {"type": "missile",
				"fired": command == ServerMessage.MISSILE_FIRE_A_TO_B,
				"source_actor_id": u16(payload),
				"target_actor_id": u16(payload, 2)}
		ServerMessage.GET_3D_OBJ:
			# An object placed into a map that is already being played in.
			# Everything the client knew about a map used to arrive with the
			# map, so nothing could change while anybody was looking at it.
			var placed: Dictionary = _world_object_at(payload, 0)
			if placed.is_empty() or int(placed.offset) != payload.size():
				return {"type": "invalid", "error": "world_object"}
			return {"type": "world_object", "objects": [placed.value],
				"replace": false}
		ServerMessage.GET_3D_OBJ_LIST:
			if payload.size() < 2:
				return {"type": "invalid", "error": "world_object_list_length"}
			var wanted: int = u16(payload)
			var listed: Array[Dictionary] = []
			var at: int = 2
			for _index: int in range(wanted):
				var entry: Dictionary = _world_object_at(payload, at)
				if entry.is_empty():
					return {"type": "invalid", "error": "world_object_list"}
				listed.append(entry.value as Dictionary)
				at = int(entry.offset)
			if at != payload.size():
				return {"type": "invalid", "error": "world_object_list_trailing"}
			# A list is the whole truth about a map, so it replaces what was
			# there rather than adding to it.
			return {"type": "world_object", "objects": listed, "replace": true}
		ServerMessage.REMOVE_3D_OBJ:
			if payload.size() != 2:
				return {"type": "invalid", "error": "remove_world_object"}
			return {"type": "world_object_removed", "object_id": u16(payload)}
		ServerMessage.GET_TELEPORTERS_LIST:
			if payload.size() < 2:
				return {"type": "invalid", "error": "teleporters_length"}
			var teleporter_count: int = u16(payload)
			if payload.size() != 2 + teleporter_count * 4:
				return {"type": "invalid", "error": "teleporters_trailing"}
			var tiles: Array[Vector2i] = []
			for index: int in range(teleporter_count):
				tiles.append(Vector2i(u16(payload, 2 + index * 4),
					u16(payload, 4 + index * 4)))
			return {"type": "teleporters", "tiles": tiles}
		ServerMessage.TELEPORT_IN, ServerMessage.TELEPORT_OUT:
			if payload.size() != 4:
				return {"type": "invalid", "error": "teleport_length"}
			return {"type": "teleport", "arriving":
				command == ServerMessage.TELEPORT_IN,
				"x": u16(payload), "y": u16(payload, 2)}
		ServerMessage.BUDDY_EVENT:
			# What happened, and to whom. The name travels with the event
			# because a client that had to keep its own list to read one would
			# be keeping a second copy of a list the server owns.
			if payload.size() < 2:
				return {"type": "invalid", "error": "buddy_length"}
			if int(payload[0]) >= BUDDY_EVENTS.size():
				return {"type": "invalid", "error": "buddy_event"}
			var buddy_field: Dictionary = _nul_at(payload, 1)
			if buddy_field.is_empty():
				return {"type": "invalid", "error": "buddy_text"}
			if int(buddy_field.offset) != payload.size():
				return {"type": "invalid", "error": "buddy_trailing"}
			if str(buddy_field.value).is_empty():
				return {"type": "invalid", "error": "buddy_empty"}
			return {"type": "buddy", "event": BUDDY_EVENTS[int(payload[0])],
				"name": str(buddy_field.value)}
		ServerMessage.NEXT_NPC_MESSAGE_IS_QUEST:
			# A flag with no payload: the NPC text after it is quest dialogue
			# rather than small talk. It comes first because it describes what
			# follows it.
			if payload.size() != 0:
				return {"type": "invalid", "error": "quest_flag_trailing"}
			return {"type": "quest_dialogue_next"}
		ServerMessage.HERE_IS_QUEST_ID, ServerMessage.QUEST_FINISHED:
			if payload.size() != 2:
				return {"type": "invalid", "error": "quest_id_length"}
			return {"type": "quest_id", "quest_id": u16(payload),
				"finished": command == ServerMessage.QUEST_FINISHED}
		ServerMessage.SEND_WEATHER:
			# The whole sky in one frame. Weather is the server's because two
			# players standing together have to see the same one.
			if payload.size() != 2:
				return {"type": "invalid", "error": "weather_length"}
			if int(payload[1]) > 100:
				return {"type": "invalid", "error": "weather_intensity"}
			return {"type": "weather", "kind": int(payload[0]),
				"intensity": int(payload[1])}
		ServerMessage.START_RAIN, ServerMessage.STOP_RAIN:
			# The legacy client's own rain signals, sent alongside the sky
			# frame. This client reads the sky frame and takes these as
			# confirmation, so an older server that sends only these still
			# makes it rain.
			var starting: bool = command == ServerMessage.START_RAIN
			if starting and payload.size() != 1:
				return {"type": "invalid", "error": "rain_length"}
			if not starting and payload.size() != 0:
				return {"type": "invalid", "error": "rain_trailing"}
			return {"type": "rain", "falling": starting,
				"intensity": int(payload[0]) if starting else 0}
		ServerMessage.THUNDER:
			if payload.size() != 1:
				return {"type": "invalid", "error": "thunder_length"}
			return {"type": "thunder", "severity": int(payload[0])}
		ServerMessage.FIRE_PARTICLES:
			if payload.size() != 5:
				return {"type": "invalid", "error": "fire_length"}
			return {"type": "fire", "x": u16(payload), "y": u16(payload, 2),
				"kind": int(payload[4]), "burning": true}
		ServerMessage.REMOVE_FIRE_AT:
			if payload.size() != 4:
				return {"type": "invalid", "error": "remove_fire_length"}
			return {"type": "fire", "x": u16(payload), "y": u16(payload, 2),
				"kind": -1, "burning": false}
		ServerMessage.PLAY_SOUND:
			# A sound the client could not have worked out for itself: what
			# somebody else is doing. It is named rather than numbered, so
			# there is no id table to keep in step, and a name this client has
			# no sound for is simply not heard.
			if payload.size() < 6:
				return {"type": "invalid", "error": "play_sound_length"}
			var sound_field: Dictionary = _nul_at(payload, 5)
			if sound_field.is_empty():
				return {"type": "invalid", "error": "play_sound_text"}
			if int(sound_field.offset) != payload.size():
				return {"type": "invalid", "error": "play_sound_trailing"}
			if str(sound_field.value).is_empty():
				return {"type": "invalid", "error": "play_sound_empty"}
			return {"type": "play_sound", "name": str(sound_field.value),
				"x": u16(payload), "y": u16(payload, 2),
				"gain": float(int(payload[4])) / 100.0}
		ServerMessage.PLAY_MUSIC:
			# An empty track name is the server saying "nothing here", which is
			# an answer rather than an omission.
			var track_field: Dictionary = _nul_at(payload, 0)
			if track_field.is_empty():
				return {"type": "invalid", "error": "play_music_text"}
			if int(track_field.offset) != payload.size():
				return {"type": "invalid", "error": "play_music_trailing"}
			return {"type": "play_music", "track": str(track_field.value)}
		ServerMessage.MISSILE_AIM_A_AT_XYZ, ServerMessage.MISSILE_FIRE_A_TO_XYZ:
			# An arrow going to a place rather than into somebody: a practice
			# shot, or a miss. The server decides where it lands, because the
			# server decided it was a miss - a client inventing its own
			# scatter would draw something that never happened.
			if payload.size() != 6:
				return {"type": "invalid", "error": "ground_missile_length"}
			return {"type": "ground_missile",
				"fired": command == ServerMessage.MISSILE_FIRE_A_TO_XYZ,
				"source_actor_id": u16(payload),
				"x": u16(payload, 2), "y": u16(payload, 4)}
		ServerMessage.SEND_SPECIAL_EFFECT:
			# Three or five bytes: the effect, the actor it happened to, and a
			# second actor when the effect travelled between two.
			if payload.size() != 3 and payload.size() != 5:
				return {"type": "invalid", "error": "special_effect_length"}
			return {"type": "special_effect", "effect": int(payload[0]),
				"actor_id": u16(payload, 1),
				"target_id": u16(payload, 3) if payload.size() == 5 else -1}
		ServerMessage.SEND_BUFFS:
			if payload.size() != 6:
				return {"type": "invalid", "error": "actor_buffs_length"}
			return {"type": "actor_buffs", "actor_id": u16(payload),
				"buffs": u32(payload, 2)}
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
		ServerMessage.GET_ACTIVE_CHANNELS:
			if payload.is_empty() or (payload.size() - 1) % 4 != 0:
				return {"type": "invalid", "error": "active_channels_length"}
			var active_channels: Array[int] = []
			for offset: int in range(1, payload.size(), 4):
				active_channels.append(u32(payload, offset))
			return {"type": "active_channels", "active_index": int(payload[0]),
				"channels": active_channels}
		ServerMessage.RAW_TEXT:
			if payload.is_empty():
				return {"type": "invalid", "error": "chat_length"}
			return {"type": "chat", "channel": int(payload[0]),
				"text": legacy_colored_string(payload.slice(1)),
				"colour": leading_text_colour(payload.slice(1))}
		ServerMessage.SEND_NPC_INFO:
			# The trailing byte is the legacy portrait index. Eloria has no
			# portrait art and cannot convert the Eternal Lands set, so the
			# field is deliberately not carried into the DTO rather than being
			# decoded and ignored. Add it back with the artwork, not before.
			if payload.size() < 20:
				return {"type": "invalid", "error": "npc_info_length"}
			return {"type": "npc_info", "name": nul_string(payload.slice(0, 20))}
		ServerMessage.NPC_TEXT:
			return {"type": "npc_text", "text": nul_string(payload)}
		ServerMessage.NPC_OPTIONS_LIST:
			return decode_npc_options(payload)
		ServerMessage.CLOSE_NPC_MENU:
			return {"type": "npc_close"}
		ServerMessage.DISPLAY_POPUP:
			return decode_popup(payload)
		ServerMessage.ELORIA_SPELL_POWER:
			return decode_spell_power(payload)
		ServerMessage.ELORIA_ALMANAC_STATE:
			return decode_almanac(payload)
		ServerMessage.ADD_ACTOR_ANIMATION:
			return decode_actor_animation(payload)
		ServerMessage.ELORIA_PLAYER_INFO:
			return decode_player_info(payload)
		ServerMessage.SEND_MAP_MARKER:
			return decode_map_marker(payload)
		ServerMessage.REMOVE_MAP_MARKER:
			if payload.size() != 2:
				return {"type": "invalid", "error": "remove_map_marker_length"}
			return {"type": "remove_map_marker", "marker_id": u16(payload)}
		ServerMessage.ELORIA_PARTY_STATE:
			return decode_party(payload)
		ServerMessage.ELORIA_QUEST_ARCHIVE_STATE:
			return decode_quest_archive(payload)
		ServerMessage.ELORIA_DEGRADED_ITEMS:
			return decode_degraded_items(payload)
		ServerMessage.ELORIA_ACHIEVEMENTS_STATE:
			return decode_achievements_state(payload)
		ServerMessage.ELORIA_EXPERIENCE_STATE:
			return decode_experience_state(payload)
		ServerMessage.ELORIA_ACTOR_FOOTPRINTS:
			return decode_actor_footprints(payload)
		ServerMessage.ELORIA_WORN_SLOTS:
			if payload.size() != 8:
				return {"type": "invalid", "error": "worn_slots_length"}
			var mask: int = 0
			for index: int in range(8):
				mask |= int(payload[index]) << (index * 8)
			return {"type": "worn_slots", "mask": mask}
		ServerMessage.ELORIA_MARKETPLACE_STATE:
			return decode_marketplace(payload)
		ServerMessage.ELORIA_MERCHANT_STATE:
			return decode_merchant(payload)
		ServerMessage.ELORIA_QUEST_JOURNAL_STATE:
			return decode_quest_journal(payload)
		ServerMessage.ELORIA_ITEM_DETAIL:
			return decode_item_detail(payload)
		ServerMessage.ELORIA_INVENTORY_STATE:
			return decode_inventory_state(payload)
		ServerMessage.ELORIA_COMBAT_STATE:
			return decode_combat_state(payload)
		ServerMessage.ELORIA_MAIL_STATE:
			return decode_mail(payload)
		ServerMessage.ELORIA_NAVIGATION_STATE:
			return decode_navigation(payload)
		ServerMessage.ELORIA_SPECIAL_EVENT_STATE:
			return decode_special_events(payload)
		ServerMessage.ELORIA_MAP_OBJECTS:
			return decode_map_objects(payload)
		ServerMessage.ELORIA_HARVEST_STATE:
			return decode_harvest_state(payload)
		ServerMessage.ELORIA_PERKS:
			return decode_perks(payload)
		ServerMessage.ELORIA_ACTIVITY_COUNTERS:
			return decode_activity_counters(payload)
		ServerMessage.PING_REQUEST:
			return {"type": "ping_request"}
		_:
			return {"type": "unknown", "command": command, "payload": payload}

## --- Eloria extension windows -----------------------------------------------
##
## Nine server-push state packets, each driving one window. They are the fork's
## own additions rather than upstream Eternal Lands, and the server withholds
## every one of them from a client that has not claimed the matching capability
## in `#clientcaps` - which is why this client saw none of them until Phase 1.
##
## Every one of these is a snapshot: the server states the whole window, the
## client renders it. None of them is merged with a previous value.

## A NUL-terminated UTF-8 string at `offset`. Returns the value and the offset
## just past the terminator, or an empty dictionary when the payload does not
## contain one.
static func _nul_at(payload: PackedByteArray, offset: int) -> Dictionary:
	if offset >= payload.size():
		return {}
	var end: int = payload.find(0, offset)
	if end < 0:
		return {}
	return {"value": payload.slice(offset, end).get_string_from_utf8(),
		"offset": end + 1}

## Reads `count` NUL-terminated strings in order. Returns the values and the
## offset past the last terminator, or an empty dictionary on a short payload.
static func _nul_run(payload: PackedByteArray, offset: int,
		count: int) -> Dictionary:
	var values: Array[String] = []
	for _index: int in range(count):
		var field: Dictionary = _nul_at(payload, offset)
		if field.is_empty():
			return {}
		values.append(str(field.value))
		offset = int(field.offset)
	return {"values": values, "offset": offset}

## Command 245. A skill's true lifetime experience, in 64 bits.
##
## The legacy stats packet carries experience in a 32-bit field at a fixed
## offset, so a total past four billion shows as four billion there. This is
## the same number without that ceiling, plus what it has bought since the
## skill stopped levelling. GDScript integers are signed 64-bit, which covers
## every value this can carry short of the top bit.
static func decode_experience_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "experience_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var skills: Array[Dictionary] = []
	for _index: int in range(count):
		var field: Dictionary = _nul_at(payload, offset)
		if field.is_empty():
			return {"type": "invalid", "error": "experience_skill_text"}
		offset = int(field.offset)
		if offset + 20 > payload.size():
			return {"type": "invalid", "error": "experience_skill_values"}
		skills.append({
			"skill": str(field.value),
			"experience": u64(payload, offset),
			"next_level": u64(payload, offset + 8),
			"post_cap_points": u32(payload, offset + 16)})
		offset += 20
	if offset != payload.size():
		return {"type": "invalid", "error": "experience_trailing"}
	return {"type": "experience_state", "skills": skills}

## Command 246. Which actor types stand on more than one tile.
##
## Sent once at login, because a footprint belongs to the species rather than
## to the individual. The client needs it to place a model: the tile an actor
## reports is the anchor of its box, and for an even-sized box the anchor is
## not the middle of it, so a two-by-two creature drawn on its anchor sits
## half a tile off the ground it is actually standing on.
##
## A type that is not listed is one tile, which is most of them.
static func decode_actor_footprints(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "footprints_length"}
	var count: int = u16(payload)
	if payload.size() != 2 + count * 4:
		return {"type": "invalid", "error": "footprints_count"}
	var sizes: Dictionary = {}
	for index: int in range(count):
		var offset: int = 2 + index * 4
		var width: int = int(payload[offset + 2])
		var depth: int = int(payload[offset + 3])
		if width < 1 or depth < 1:
			return {"type": "invalid", "error": "footprints_size"}
		sizes[u16(payload, offset)] = Vector2i(width, depth)
	return {"type": "actor_footprints", "footprints": sizes}

## Command 244. Every countable thing this character has done.
##
## These numbers were always tracked and the only way to read them was a chat
## command that printed a dozen lines and scrolled away.
static func decode_achievements_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 4:
		return {"type": "invalid", "error": "achievements_length"}
	var counter_count: int = u16(payload)
	var name_count: int = u16(payload, 2)
	var offset: int = 4
	var counters: Array[Dictionary] = []
	for _index: int in range(counter_count):
		var field: Dictionary = _nul_at(payload, offset)
		if field.is_empty():
			return {"type": "invalid", "error": "achievements_counter_text"}
		offset = int(field.offset)
		if offset + 4 > payload.size():
			return {"type": "invalid", "error": "achievements_counter_value"}
		counters.append({"label": str(field.value), "value": u32(payload, offset)})
		offset += 4
	var completed: Array[String] = []
	for _index: int in range(name_count):
		var name_field: Dictionary = _nul_at(payload, offset)
		if name_field.is_empty():
			return {"type": "invalid", "error": "achievements_name_text"}
		completed.append(str(name_field.value))
		offset = int(name_field.offset)
	if offset != payload.size():
		return {"type": "invalid", "error": "achievements_trailing"}
	return {"type": "achievements_state", "counters": counters,
		"completed": completed}

## Command 242. Which item names exist only because something wore out.
##
## Sent once at login. An empty list is a real answer: it means this profile
## authors no degradation chains, not that the packet went missing.
static func decode_degraded_items(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "degraded_items_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var names: Array[String] = []
	for _index: int in range(count):
		var field: Dictionary = _nul_at(payload, offset)
		if field.is_empty():
			return {"type": "invalid", "error": "degraded_items_text"}
		names.append(str(field.value))
		offset = int(field.offset)
	if offset != payload.size():
		return {"type": "invalid", "error": "degraded_items_trailing"}
	return {"type": "degraded_items", "names": names}

## Command 241. What this character has finished.
##
## The journal says what is open; this says what is done. It is server-held, so
## it survives a reinstall and a new machine - which is the whole reason it
## exists rather than being read out of a local log.
static func decode_quest_archive(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "quest_archive_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var entries: Array[Dictionary] = []
	for _index: int in range(count):
		var text: Dictionary = _nul_run(payload, offset, 3)
		if text.is_empty():
			return {"type": "invalid", "error": "quest_archive_entry_text"}
		var values: Array = text.values as Array
		entries.append({"title": values[0], "location": values[1],
			"detail": values[2]})
		offset = int(text.offset)
	if offset != payload.size():
		return {"type": "invalid", "error": "quest_archive_trailing"}
	return {"type": "quest_archive", "entries": entries}

## Command 240. Who is in the party, how they are doing, and where they are.
##
## An offline member still arrives with a row: the server states their absence
## rather than dropping them, so the window can say "offline" instead of
## quietly shrinking and leaving the player to notice on their own.
static func decode_party(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 5:
		return {"type": "invalid", "error": "party_length"}
	var in_party: bool = payload[0] != 0
	var count: int = int(payload[1])
	var offset: int = 2
	var members: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 13 > payload.size():
			return {"type": "invalid", "error": "party_entry_length"}
		var flags: int = int(payload[offset])
		var member: Dictionary = {
			"online": (flags & 1) != 0,
			"leader": (flags & 2) != 0,
			"is_self": (flags & 4) != 0,
			"health": u16(payload, offset + 1),
			"max_health": u16(payload, offset + 3),
			"ether": u16(payload, offset + 5),
			"max_ether": u16(payload, offset + 7),
			"x": u16(payload, offset + 9),
			"y": u16(payload, offset + 11)}
		offset += 13
		var text: Dictionary = _nul_run(payload, offset, 2)
		if text.is_empty():
			return {"type": "invalid", "error": "party_entry_text"}
		member["name"] = (text.values as Array)[0]
		member["map_id"] = (text.values as Array)[1]
		offset = int(text.offset)
		members.append(member)
	var invite: Dictionary = _nul_at(payload, offset)
	if invite.is_empty():
		return {"type": "invalid", "error": "party_invite_text"}
	offset = int(invite.offset)
	if offset + 2 != payload.size():
		return {"type": "invalid", "error": "party_trailing"}
	return {"type": "party", "in_party": in_party, "members": members,
		"invited_by": str(invite.value), "invite_seconds": u16(payload, offset)}

## Command 222. The Nymara Exchange: the player's gold, how many items are
## waiting in escrow, and the listings on offer.
static func decode_marketplace(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 11:
		return {"type": "invalid", "error": "marketplace_length"}
	var view: int = int(payload[0])
	var gold: int = u32(payload, 1)
	var returned_items: int = u32(payload, 5)
	var count: int = u16(payload, 9)
	var offset: int = 11
	var listings: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 18 > payload.size():
			return {"type": "invalid", "error": "marketplace_entry_length"}
		var listing: Dictionary = {
			"listing_id": u32(payload, offset),
			"quantity": u32(payload, offset + 4),
			"unit_price": u32(payload, offset + 8),
			"seconds_left": u32(payload, offset + 12),
			"image_id": u16(payload, offset + 16)}
		offset += 18
		var text: Dictionary = _nul_run(payload, offset, 2)
		if text.is_empty():
			return {"type": "invalid", "error": "marketplace_entry_text"}
		listing["item_name"] = (text.values as Array)[0]
		listing["seller"] = (text.values as Array)[1]
		offset = int(text.offset)
		listings.append(listing)
	if offset != payload.size():
		return {"type": "invalid", "error": "marketplace_trailing"}
	return {"type": "marketplace", "view": view, "gold": gold,
		"returned_items": returned_items, "listings": listings}

## Command 223. One NPC merchant's stock, with the prices in both directions
## and how many of each the player already carries.
static func decode_merchant(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 16:
		return {"type": "invalid", "error": "merchant_length"}
	var actor_id: int = u16(payload)
	var gold: int = u32(payload, 2)
	var carried: int = u32(payload, 6)
	var capacity: int = u32(payload, 10)
	var count: int = u16(payload, 14)
	var name_field: Dictionary = _nul_at(payload, 16)
	if name_field.is_empty():
		return {"type": "invalid", "error": "merchant_name"}
	var offset: int = int(name_field.offset)
	var items: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 16 > payload.size():
			return {"type": "invalid", "error": "merchant_entry_length"}
		var entry: Dictionary = {
			"index": u16(payload, offset),
			"buy_price": u32(payload, offset + 2),
			"sell_price": u32(payload, offset + 6),
			"owned": u32(payload, offset + 10),
			"image_id": u16(payload, offset + 14)}
		offset += 16
		var entry_name: Dictionary = _nul_at(payload, offset)
		if entry_name.is_empty():
			return {"type": "invalid", "error": "merchant_entry_name"}
		entry["name"] = str(entry_name.value)
		offset = int(entry_name.offset)
		items.append(entry)
	if offset != payload.size():
		return {"type": "invalid", "error": "merchant_trailing"}
	return {"type": "merchant", "actor_id": actor_id, "npc_name": str(name_field.value),
		"gold": gold, "carried": carried, "capacity": capacity, "items": items}

## Command 224. Active quest objectives with their progress.
static func decode_quest_journal(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "quest_journal_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var entries: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 9 > payload.size():
			return {"type": "invalid", "error": "quest_entry_length"}
		var entry: Dictionary = {
			"ready": int(payload[offset]) != 0,
			"current": u32(payload, offset + 1),
			"target": u32(payload, offset + 5)}
		offset += 9
		var text: Dictionary = _nul_run(payload, offset, 3)
		if text.is_empty():
			return {"type": "invalid", "error": "quest_entry_text"}
		entry["title"] = (text.values as Array)[0]
		entry["objective"] = (text.values as Array)[1]
		entry["location"] = (text.values as Array)[2]
		offset = int(text.offset)
		entries.append(entry)
	if offset != payload.size():
		return {"type": "invalid", "error": "quest_journal_trailing"}
	return {"type": "quest_journal", "entries": entries}

## Command 225. One inspected item, and the equipped item it would replace.
static func decode_item_detail(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 7:
		return {"type": "invalid", "error": "item_detail_length"}
	var text: Dictionary = _nul_run(payload, 7, 7)
	if text.is_empty():
		return {"type": "invalid", "error": "item_detail_text"}
	if int(text.offset) != payload.size():
		return {"type": "invalid", "error": "item_detail_trailing"}
	var values: Array = text.values
	return {"type": "item_detail", "image_id": u16(payload),
		"quantity": u32(payload, 2), "equipped": int(payload[6]) != 0,
		"name": values[0], "category": values[1], "equip_type": values[2],
		"description": values[3], "stats": values[4],
		"comparison_name": values[5], "comparison": values[6]}

## Command 226. The server's own view of the backpack, with the item names,
## categories and per-item weight the ordinary inventory packet cannot carry.
static func decode_inventory_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 14:
		return {"type": "invalid", "error": "inventory_state_length"}
	var count: int = u16(payload, 12)
	var offset: int = 14
	var items: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 12 > payload.size():
			return {"type": "invalid", "error": "inventory_state_entry_length"}
		var entry: Dictionary = {
			"slot": int(payload[offset]), "image_id": u16(payload, offset + 1),
			"quantity": u32(payload, offset + 3), "emu": u32(payload, offset + 7),
			"flags": int(payload[offset + 11])}
		offset += 12
		var text: Dictionary = _nul_run(payload, offset, 2)
		if text.is_empty():
			return {"type": "invalid", "error": "inventory_state_entry_text"}
		entry["name"] = (text.values as Array)[0]
		entry["category"] = (text.values as Array)[1]
		offset = int(text.offset)
		items.append(entry)
	if offset != payload.size():
		return {"type": "invalid", "error": "inventory_state_trailing"}
	return {"type": "inventory_state", "gold": u32(payload),
		"carried": u32(payload, 4), "capacity": u32(payload, 8), "items": items}

## Command 227. The combat HUD: both health bars and the most recent outcome.
## Event 0 is a state refresh; the rest name what just happened.
const COMBAT_EVENT_STATE := 0
const COMBAT_EVENT_HIT := 1
const COMBAT_EVENT_MISS := 2
const COMBAT_EVENT_DODGE := 3
const COMBAT_EVENT_DEFEAT := 4

static func decode_combat_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 14:
		return {"type": "invalid", "error": "combat_state_length"}
	var name_field: Dictionary = _nul_at(payload, 13)
	if name_field.is_empty() or int(name_field.offset) != payload.size():
		return {"type": "invalid", "error": "combat_state_name"}
	return {"type": "combat_state", "event": int(payload[0]),
		"target_id": u16(payload, 1), "player_health": u16(payload, 3),
		"player_max_health": u16(payload, 5), "target_health": u16(payload, 7),
		"target_max_health": u16(payload, 9), "recent_damage": u16(payload, 11),
		"target_name": str(name_field.value)}

## Command 229. The persistent mail inbox.
static func decode_mail(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "mail_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var messages: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 9 > payload.size():
			return {"type": "invalid", "error": "mail_entry_length"}
		var message: Dictionary = {
			"mail_id": u32(payload, offset),
			"created_at": u32(payload, offset + 4),
			"read": int(payload[offset + 8]) != 0}
		offset += 9
		var text: Dictionary = _nul_run(payload, offset, 3)
		if text.is_empty():
			return {"type": "invalid", "error": "mail_entry_text"}
		message["sender"] = (text.values as Array)[0]
		message["subject"] = (text.values as Array)[1]
		message["body"] = (text.values as Array)[2]
		offset = int(text.offset)
		messages.append(message)
	if offset != payload.size():
		return {"type": "invalid", "error": "mail_trailing"}
	return {"type": "mail", "messages": messages}

## Command 230. The waypoint HUD. `active` false means no waypoint is set, and
## the remaining fields are then meaningless rather than stale.
static func decode_navigation(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 7:
		return {"type": "invalid", "error": "navigation_length"}
	var text: Dictionary = _nul_run(payload, 7, 2)
	if text.is_empty():
		return {"type": "invalid", "error": "navigation_text"}
	if int(text.offset) != payload.size():
		return {"type": "invalid", "error": "navigation_trailing"}
	return {"type": "navigation", "active": int(payload[0]) != 0,
		"x": u16(payload, 1), "y": u16(payload, 3), "distance": u16(payload, 5),
		"map_id": (text.values as Array)[0], "label": (text.values as Array)[1]}

## Command 232. Free text lines for the specialty-event panel, NUL delimited.
static func decode_special_events(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty() or payload[payload.size() - 1] != 0:
		return {"type": "invalid", "error": "special_events_terminator"}
	var lines: Array[String] = []
	var start: int = 0
	for index: int in range(payload.size()):
		if payload[index] != 0:
			continue
		lines.append(payload.slice(start, index).get_string_from_utf8())
		start = index + 1
	# A single empty line is how the server clears the panel.
	if lines.size() == 1 and lines[0].is_empty():
		lines.clear()
	return {"type": "special_events", "lines": lines}

## Clickable world objects on the current map. The client cannot infer any of
## this: a world package renders harvestable props and buildings as ordinary
## geometry, and the legacy client matched object basenames against a lowercase
## harvestable list, a lookup that never matched anything because the packs
## wrote relative paths. Object identity is server state.
const MAP_OBJECT_HARVEST := 1
const MAP_OBJECT_INTERACTIVE := 2

static func decode_map_objects(payload: PackedByteArray) -> Dictionary:
	# A busy map has thousands of harvest nodes, which does not fit in one
	# frame, so the list arrives in chunks. The leading flag says whether a
	# chunk begins a new list or continues the one already being built.
	if payload.size() < 3:
		return {"type": "invalid", "error": "map_objects_length"}
	var first: bool = int(payload[0]) != 0
	var count: int = u16(payload, 1)
	var offset: int = 3
	var objects: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 7 > payload.size():
			return {"type": "invalid", "error": "map_object_entry_length"}
		var object_id: int = u16(payload, offset)
		var kind: int = int(payload[offset + 2])
		var x: int = u16(payload, offset + 3)
		var y: int = u16(payload, offset + 5)
		offset += 7
		var label_end: int = payload.find(0, offset)
		if label_end < 0:
			return {"type": "invalid", "error": "map_object_label"}
		var label: String = payload.slice(offset, label_end).get_string_from_utf8()
		offset = label_end + 1
		var detail_end: int = payload.find(0, offset)
		if detail_end < 0:
			return {"type": "invalid", "error": "map_object_detail"}
		var detail: String = payload.slice(offset, detail_end).get_string_from_utf8()
		offset = detail_end + 1
		if kind not in [MAP_OBJECT_HARVEST, MAP_OBJECT_INTERACTIVE]:
			return {"type": "invalid", "error": "map_object_kind"}
		objects.append({"object_id": object_id, "kind": kind, "x": x, "y": y,
			"label": label, "detail": detail})
	if offset != payload.size():
		return {"type": "invalid", "error": "map_objects_trailing"}
	return {"type": "map_objects", "first": first, "objects": objects}

## Whether the player is harvesting, and what. The stock client matched an
## exact English phrase out of the chat stream to drive this, which breaks on
## any rewording and on any translation.
static func decode_harvest_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 4:
		return {"type": "invalid", "error": "harvest_state_length"}
	var terminator: int = payload.find(0, 3)
	if terminator < 0 or terminator != payload.size() - 1:
		return {"type": "invalid", "error": "harvest_state_resource"}
	return {"type": "harvest_state", "active": int(payload[0]) != 0,
		"object_id": u16(payload, 1),
		"resource": payload.slice(3, terminator).get_string_from_utf8()}

## A server-driven modal question. Option types are the legacy popup contract:
## 0 text entry, 1 display text, 8 text option (a button that answers at once),
## 9 radio option (a choice confirmed with the popup's send button). Options
## carry a group id; one answer is returned per group.
const POPUP_TEXT_ENTRY := 0
const POPUP_DISPLAY_TEXT := 1
const POPUP_TEXT_OPTION := 8
const POPUP_RADIO_OPTION := 9

## Command 231. What power each spell effect will be cast at, and the highest
## the player's Magic level and nexus allow.
##
## Both numbers are the server's: `#sp` reports them as chat text, which a
## client must not parse, and working them out from a levels table would mean
## keeping a second copy of the server's progression rules.
static func decode_spell_power(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "spell_power_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var effects: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 2 > payload.size():
			return {"type": "invalid", "error": "spell_power_entry_length"}
		var preferred: int = int(payload[offset])
		var limit: int = int(payload[offset + 1])
		var field: Dictionary = _nul_at(payload, offset + 2)
		if field.is_empty():
			return {"type": "invalid", "error": "spell_power_entry_text"}
		effects.append({"effect": str(field.value), "preferred": preferred,
			"limit": limit})
		offset = int(field.offset)
	if offset != payload.size():
		return {"type": "invalid", "error": "spell_power_trailing"}
	return {"type": "spell_power", "effects": effects}

## Command 89. An actor is playing a named animation action.
##
## The action is a name, not a clip: which piece of art plays is this client's
## to decide from its own animation map, and an action it has no clip for is
## simply not played. The server sends the words separately and always, so an
## emote reaches the player either way.
static func decode_actor_animation(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 3:
		return {"type": "invalid", "error": "actor_animation_length"}
	var field: Dictionary = _nul_at(payload, 2)
	if field.is_empty():
		return {"type": "invalid", "error": "actor_animation_text"}
	if int(field.offset) != payload.size():
		return {"type": "invalid", "error": "actor_animation_trailing"}
	var action: String = str(field.value)
	if action.is_empty():
		return {"type": "invalid", "error": "actor_animation_empty"}
	return {"type": "actor_animation", "actor_id": u16(payload),
		"action": action}

## One object out of a placement frame: id, tile, facing and model name.
static func _world_object_at(payload: PackedByteArray, offset: int) -> Dictionary:
	if offset + 8 > payload.size():
		return {}
	var field: Dictionary = _nul_at(payload, offset + 8)
	if field.is_empty() or str(field.value).is_empty():
		return {}
	return {"value": {"object_id": u16(payload, offset),
		"x": u16(payload, offset + 2), "y": u16(payload, offset + 4),
		"rotation": u16(payload, offset + 6), "model": str(field.value)},
		"offset": int(field.offset)}

## What a buddy event says happened, in the order the server numbers them.
const BUDDY_EVENTS: Array[String] = ["offline", "online", "added", "removed"]

## The four kinds a day can be, in the order the server numbers them.
const ALMANAC_KINDS: Array[String] = ["ordinary", "good", "neutral", "bad"]

## Command 238. The game date, the day in force and what it does, and the whole
## catalogue of days this server can roll.
##
## Both halves used to be chat lines - a `GET_DATE` reply and a broadcast
## announcement - so showing either meant reading prose off the chat stream.
## The catalogue arrives with them because which days exist is the server's to
## decide; a copy shipped here would be a second source of truth.
static func decode_almanac(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 7:
		return {"type": "invalid", "error": "almanac_length"}
	var kind_index: int = int(payload[4])
	if kind_index >= ALMANAC_KINDS.size():
		return {"type": "invalid", "error": "almanac_kind"}
	var names: Dictionary = _nul_run(payload, 7, 2)
	if names.is_empty():
		return {"type": "invalid", "error": "almanac_text"}
	var offset: int = int(names.offset)
	var texts: Array = names.values as Array

	if offset >= payload.size():
		return {"type": "invalid", "error": "almanac_effect_count"}
	var effect_count: int = int(payload[offset])
	var effect_fields: Dictionary = _nul_run(payload, offset + 1, effect_count)
	if effect_fields.is_empty() and effect_count > 0:
		return {"type": "invalid", "error": "almanac_effects"}
	offset = int(effect_fields.offset) if effect_count > 0 else offset + 1
	var effects: Array[String] = []
	if effect_count > 0:
		for value: Variant in effect_fields.values as Array:
			effects.append(str(value))

	if offset >= payload.size():
		return {"type": "invalid", "error": "almanac_multiplier_count"}
	var multiplier_count: int = int(payload[offset])
	offset += 1
	var multipliers: Dictionary = {}
	for _index: int in range(multiplier_count):
		var skill: Dictionary = _nul_at(payload, offset)
		if skill.is_empty() or int(skill.offset) + 2 > payload.size():
			return {"type": "invalid", "error": "almanac_multiplier"}
		offset = int(skill.offset)
		multipliers[str(skill.value)] = float(u16(payload, offset)) / 100.0
		offset += 2

	if offset + 2 > payload.size():
		return {"type": "invalid", "error": "almanac_catalogue_count"}
	var catalogue_count: int = u16(payload, offset)
	offset += 2
	var catalogue: Array[Dictionary] = []
	for _index: int in range(catalogue_count):
		if offset >= payload.size():
			return {"type": "invalid", "error": "almanac_catalogue_kind"}
		var entry_kind: int = int(payload[offset])
		if entry_kind >= ALMANAC_KINDS.size():
			return {"type": "invalid", "error": "almanac_catalogue_kind"}
		var entry: Dictionary = _nul_run(payload, offset + 1, 2)
		if entry.is_empty():
			return {"type": "invalid", "error": "almanac_catalogue_text"}
		offset = int(entry.offset)
		var entry_values: Array = entry.values as Array
		catalogue.append({"kind": ALMANAC_KINDS[entry_kind],
			"name": str(entry_values[0]), "description": str(entry_values[1])})
	if offset != payload.size():
		return {"type": "invalid", "error": "almanac_trailing"}
	return {"type": "almanac",
		"day": int(payload[0]), "month": int(payload[1]), "year": u16(payload, 2),
		"kind": ALMANAC_KINDS[kind_index],
		"experience_bonus": float(u16(payload, 5)) / 100.0,
		"name": str(texts[0]), "description": str(texts[1]),
		"effects": effects, "multipliers": multipliers, "catalogue": catalogue}

## Command 228. Who the player just looked at, and what they have earned.
##
## The legacy reply is a "You see: <name>" chat line plus `SEND_ACHIEVEMENTS`,
## a bare 160-bit set with no actor id and no names: a client had to pair the
## bitset with its own outstanding request and carry a second copy of the
## server's achievement catalog to read it. This states all three.
static func decode_player_info(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 4:
		return {"type": "invalid", "error": "player_info_length"}
	var count: int = u16(payload, 2)
	var fields: Dictionary = _nul_run(payload, 4, count + 1)
	if fields.is_empty():
		return {"type": "invalid", "error": "player_info_text"}
	if int(fields.offset) != payload.size():
		return {"type": "invalid", "error": "player_info_trailing"}
	var values: Array = fields.values as Array
	var achievements: Array[String] = []
	for index: int in range(count):
		achievements.append(str(values[index + 1]))
	return {"type": "player_info", "actor_id": u16(payload),
		"name": str(values[0]), "achievements": achievements}

## Command 90. One map marker the server placed: a waypoint, a quest target or
## a tutorial pointer. The map name arrives as the server's own file reference
## (`./maps/four_gates.elm`); the marker belongs to that map and no other.
static func decode_map_marker(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 6:
		return {"type": "invalid", "error": "map_marker_length"}
	var text: Dictionary = _nul_run(payload, 6, 2)
	if text.is_empty():
		return {"type": "invalid", "error": "map_marker_text"}
	if int(text.offset) != payload.size():
		return {"type": "invalid", "error": "map_marker_trailing"}
	var values: Array = text.values as Array
	return {"type": "map_marker", "marker_id": u16(payload),
		"x": u16(payload, 2), "y": u16(payload, 4),
		"map_id": map_id_from_reference(str(values[0])), "label": str(values[1])}

## `./maps/four_gates.elm` is the map id `four_gates`. The server names its own
## maps this way in every marker; matching on the reference itself would tie the
## client to a path layout that has nothing to do with what it renders.
static func map_id_from_reference(reference: String) -> String:
	return reference.get_file().get_basename()

static func decode_popup(payload: PackedByteArray) -> Dictionary:
	# The legacy client rejects anything too short to hold a one-character
	# title and a one-character body.
	if payload.size() <= 5:
		return {"type": "invalid", "error": "popup_length"}
	if int(payload[2]) != 0:
		return {"type": "invalid", "error": "popup_flags"}
	var popup_id: int = u16(payload)
	var offset: int = 3
	var title_result: Dictionary = _sized_string(payload, offset)
	if title_result.is_empty():
		return {"type": "invalid", "error": "popup_title"}
	offset = int(title_result.offset)
	if offset + 2 > payload.size():
		return {"type": "invalid", "error": "popup_size_hint"}
	var size_hint: int = u16(payload, offset)
	offset += 2
	var text_result: Dictionary = _sized_string(payload, offset)
	if text_result.is_empty():
		return {"type": "invalid", "error": "popup_text"}
	offset = int(text_result.offset)
	var options: Array[Dictionary] = []
	while offset < payload.size():
		if offset + 2 > payload.size():
			return {"type": "invalid", "error": "popup_option_header"}
		var option_type: int = int(payload[offset])
		var group: int = int(payload[offset + 1])
		offset += 2
		if option_type not in [POPUP_TEXT_ENTRY, POPUP_DISPLAY_TEXT,
				POPUP_TEXT_OPTION, POPUP_RADIO_OPTION]:
			return {"type": "invalid", "error": "popup_option_type"}
		var label_result: Dictionary = _sized_string(payload, offset)
		if label_result.is_empty():
			return {"type": "invalid", "error": "popup_option_label"}
		offset = int(label_result.offset)
		var option: Dictionary = {"option_type": option_type, "group": group,
			"label": str(label_result.value)}
		if option_type in [POPUP_TEXT_OPTION, POPUP_RADIO_OPTION]:
			if offset >= payload.size():
				return {"type": "invalid", "error": "popup_option_value"}
			option["value"] = int(payload[offset])
			offset += 1
		options.append(option)
	return {"type": "popup", "popup_id": popup_id, "title": str(title_result.value),
		"size_hint": size_hint, "text": str(text_result.value), "options": options}

## A length-prefixed string: one count byte then that many bytes. Returns the
## decoded value and the offset just past it, or an empty dictionary if the
## payload cannot hold it.
static func _sized_string(payload: PackedByteArray, offset: int) -> Dictionary:
	if offset >= payload.size():
		return {}
	var length: int = int(payload[offset])
	if offset + 1 + length > payload.size():
		return {}
	return {"value": payload.slice(offset + 1, offset + 1 + length).get_string_from_utf8(),
		"offset": offset + 1 + length}

## The player's perks as server state. Names and descriptions are on the wire,
## so the client keeps no perk table: the previous implementation asked
## `#list_perks` and pattern-matched the chat reply against a hardcoded
## 33-name array inside an 8-second window, which dropped every renamed, added
## or reworded perk and dropped all of them on a slow server.
static func decode_perks(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "perks_length"}
	var count: int = u16(payload)
	var offset: int = 2
	var perks: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 3 > payload.size():
			return {"type": "invalid", "error": "perks_entry_length"}
		var from_gear: bool = int(payload[offset]) != 0
		var pickpoints: int = s16(payload, offset + 1)
		offset += 3
		var name_end: int = payload.find(0, offset)
		if name_end < 0:
			return {"type": "invalid", "error": "perks_name_terminator"}
		var perk_name: String = payload.slice(offset, name_end).get_string_from_utf8()
		offset = name_end + 1
		var description_end: int = payload.find(0, offset)
		if description_end < 0:
			return {"type": "invalid", "error": "perks_description_terminator"}
		var description: String = payload.slice(offset, description_end).get_string_from_utf8()
		offset = description_end + 1
		perks.append({"name": perk_name, "description": description,
			"pickpoints": pickpoints, "from_gear": from_gear})
	if offset != payload.size():
		return {"type": "invalid", "error": "perks_trailing"}
	return {"type": "perks", "perks": perks}

## Lifetime activity totals. `full` marks a complete snapshot; otherwise the
## packet carries only the categories that just changed. The category name
## travels with its total, so the client keeps no parallel table and the totals
## are the server's confirmed events rather than client-side guesses made when
## a request was sent.
static func decode_activity_counters(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 2:
		return {"type": "invalid", "error": "activity_counters_length"}
	var full: bool = int(payload[0]) != 0
	var count: int = int(payload[1])
	var offset: int = 2
	var counters: Array[Dictionary] = []
	for _index: int in range(count):
		if offset + 4 > payload.size():
			return {"type": "invalid", "error": "activity_counter_entry_length"}
		var total: int = u32(payload, offset)
		offset += 4
		var name_end: int = payload.find(0, offset)
		if name_end < 0:
			return {"type": "invalid", "error": "activity_counter_terminator"}
		counters.append({"name": payload.slice(offset, name_end).get_string_from_utf8(),
			"total": total})
		offset = name_end + 1
	if offset != payload.size():
		return {"type": "invalid", "error": "activity_counters_trailing"}
	return {"type": "activity_counters", "full": full, "counters": counters}

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

## The Eloria organizer packet: what each stored position actually is, so the
## window can filter a category by type and sort it by name, strength, or
## rarity. Positions match the stock STORAGE_ITEMS packet exactly.
static func decode_storage_state(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 3:
		return {"type": "invalid", "error": "storage_state_length"}
	var count: int = u16(payload, 1)
	var rows: Array[Dictionary] = []
	var offset: int = 3
	for _index: int in range(count):
		if offset + 13 > payload.size():
			return {"type": "invalid", "error": "storage_state_row"}
		var row: Dictionary = {
			"position": u16(payload, offset),
			"image_id": u16(payload, offset + 2),
			"quantity": u32(payload, offset + 4),
			"strength": s32(payload, offset + 8),
			"rarity": int(payload[offset + 12])}
		offset += 13
		for key: String in ["name", "subtype"]:
			var terminator: int = payload.find(0, offset)
			if terminator < 0:
				return {"type": "invalid", "error": "storage_state_text"}
			row[key] = payload.slice(offset, terminator).get_string_from_utf8()
			offset = terminator + 1
		rows.append(row)
	if offset != payload.size():
		return {"type": "invalid", "error": "storage_state_trailing"}
	return {"type": "storage_state", "category_id": int(payload[0]), "rows": rows}

static func decode_stats(payload: PackedByteArray) -> Dictionary:
	if payload.size() < 230:
		return {"type": "invalid", "error": "stats_length"}
	var values: Dictionary = {}
	var attribute_names: Array[String] = [
		"physique", "coordination", "reasoning", "will", "instinct", "vitality",
		"human_nexus", "animal_nexus", "vegetal_nexus", "inorganic_nexus",
		"artificial_nexus", "magic_nexus"]
	for index: int in range(attribute_names.size()):
		var key: String = attribute_names[index]
		values[key] = s16(payload, index * 4)
		values[key + "_base"] = s16(payload, index * 4 + 2)
	var skill_level_slots: Dictionary = {
		"manufacturing": 24, "harvesting": 26, "alchemy": 28, "overall": 30,
		"attack": 32, "defense": 34, "magic": 36, "potion": 38,
		"summoning": 83, "crafting": 89, "engineering": 95,
		"tailoring": 101, "ranging": 107}
	for skill_name: String in skill_level_slots:
		var level_slot: int = int(skill_level_slots[skill_name])
		values[skill_name] = s16(payload, level_slot * 2)
		values[skill_name + "_base"] = s16(payload, (level_slot + 1) * 2)
	# Eloria sends spent pickpoints in the current half of the legacy overall
	# pair and the actual overall level in the base half.
	values["overall_level"] = values["overall_base"]
	var experience_slots: Dictionary = {
		"manufacturing": 49, "harvesting": 53, "alchemy": 57,
		"overall": 61, "attack": 65, "defense": 69, "magic": 73,
		"potion": 77, "summoning": 85, "crafting": 91,
		"engineering": 97, "tailoring": 103, "ranging": 109}
	for skill_name: String in experience_slots:
		var experience_slot: int = int(experience_slots[skill_name])
		values[skill_name + "_exp"] = u32(payload, experience_slot * 2)
		values[skill_name + "_exp_next"] = u32(payload, (experience_slot + 2) * 2)
	for resource: String in ["carried", "capacity", "health", "max_health", "ether", "max_ether"]:
		var resource_index: int = ["carried", "capacity", "health", "max_health", "ether", "max_ether"].find(resource)
		values[resource] = s16(payload, (40 + resource_index) * 2)
	values["food"] = s16(payload, 46 * 2)
	values["research_completed"] = s16(payload, 47 * 2)
	values["researching"] = s16(payload, 81 * 2)
	values["research_total"] = s16(payload, 82 * 2)
	values["action_points"] = s16(payload, 113 * 2)
	values["max_action_points"] = s16(payload, 114 * 2)
	# Eloria's current server also uses these legacy tail slots for pickpoint
	# accounting. Keep the action-point aliases for older servers/HUD meters.
	values["pickpoints_spent"] = values["action_points"]
	values["pickpoints_earned"] = values["max_action_points"]
	return {"type": "stats", "values": values}

static func decode_partial_stats(payload: PackedByteArray) -> Dictionary:
	if payload.size() % 5 != 0:
		return {"type": "invalid", "error": "partial_stats_length"}
	var values: Dictionary = {}
	for offset: int in range(0, payload.size(), 5):
		var slot: int = int(payload[offset])
		var value: int = s32(payload, offset + 1)
		values[stat_key(slot)] = value
		if slot == 31 or slot == 114:
			values["overall_level"] = value
		if slot == 113:
			values["pickpoints_spent"] = value
		elif slot == 114:
			values["pickpoints_earned"] = value
	return {"type": "partial_stats", "values": values}

## Inventory entries are eight bytes. The optional legacy ten-byte form carried
## a per-item UID that this server does not emit, so decoding it produced a
## `uid` field nothing could ever contain or read. PROTOCOL.md, not
## client_serv.h, is the specification: when unique item identity goes on the
## wire it will be added deliberately, with a consumer.
static func decode_inventory(payload: PackedByteArray) -> Dictionary:
	if payload.is_empty():
		return {"type": "invalid", "error": "inventory_length"}
	var count: int = int(payload[0])
	if payload.size() != 1 + count * 8:
		return {"type": "invalid", "error": "inventory_length"}
	var items: Array[Dictionary] = []
	for index: int in range(count):
		items.append(decode_inventory_item(payload, 1 + index * 8))
	return {"type": "inventory", "items": items}

static func decode_inventory_update(payload: PackedByteArray) -> Dictionary:
	if payload.size() != 8:
		return {"type": "invalid", "error": "inventory_update_length"}
	return {"type": "inventory_update", "item": decode_inventory_item(payload, 0)}

static func decode_inventory_item(payload: PackedByteArray,
		offset: int) -> Dictionary:
	var flags: int = int(payload[offset + 7])
	var item: Dictionary = {
		"image_id": u16(payload, offset), "quantity": u32(payload, offset + 2),
		"slot": int(payload[offset + 6]), "flags": flags,
		"reagent": (flags & 1) != 0, "resource": (flags & 2) != 0,
		"stackable": (flags & 4) != 0, "inventory_usable": (flags & 8) != 0,
		"tile_usable": (flags & 16) != 0, "player_usable": (flags & 32) != 0,
		"object_usable": (flags & 64) != 0, "on_off": (flags & 128) != 0}
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

## Partial-statistic slot numbers. These are the legacy incremental-update
## identifiers and are a different namespace from the word offsets in the full
## statistics packet: research is 47/65/66 here and 47/81/82 there, and the
## server writes both from the same character fields.
static func stat_key(slot: int) -> String:
	var keys: Dictionary = {
		0: "physique", 1: "physique_base", 2: "coordination",
		3: "coordination_base", 4: "reasoning", 5: "reasoning_base",
		6: "will", 7: "will_base", 8: "instinct", 9: "instinct_base",
		10: "vitality", 11: "vitality_base", 12: "human_nexus",
		13: "human_nexus_base", 14: "animal_nexus", 15: "animal_nexus_base",
		16: "vegetal_nexus", 17: "vegetal_nexus_base", 18: "inorganic_nexus",
		19: "inorganic_nexus_base", 20: "artificial_nexus",
		21: "artificial_nexus_base", 22: "magic_nexus", 23: "magic_nexus_base",
		24: "manufacturing", 25: "manufacturing_base", 26: "harvesting",
		27: "harvesting_base", 28: "alchemy", 29: "alchemy_base",
		30: "overall", 31: "overall_base", 32: "defense", 33: "defense_base",
		34: "attack", 35: "attack_base", 36: "magic", 37: "magic_base",
		38: "potion", 39: "potion_base", 40: "carried", 41: "capacity",
		42: "health", 43: "max_health", 44: "ether", 45: "max_ether",
		46: "food", 47: "researching", 49: "manufacturing_exp",
		50: "manufacturing_exp_next", 51: "harvesting_exp",
		52: "harvesting_exp_next", 53: "alchemy_exp", 54: "alchemy_exp_next",
		55: "overall_exp", 56: "overall_exp_next", 57: "defense_exp",
		58: "defense_exp_next", 59: "attack_exp", 60: "attack_exp_next",
		61: "magic_exp", 62: "magic_exp_next", 63: "potion_exp",
		64: "potion_exp_next", 65: "research_completed", 66: "research_total",
		67: "summoning_exp", 68: "summoning_exp_next", 69: "summoning",
		70: "summoning_base", 71: "crafting_exp", 72: "crafting_exp_next",
		73: "crafting", 74: "crafting_base", 75: "engineering_exp",
		76: "engineering_exp_next", 77: "engineering", 78: "engineering_base",
		79: "ranging_exp", 80: "ranging_exp_next", 81: "ranging",
		82: "ranging_base", 83: "tailoring_exp", 84: "tailoring_exp_next",
		85: "tailoring", 86: "tailoring_base", 87: "action_points",
		88: "max_action_points", 113: "action_points", 114: "max_action_points"}
	return str(keys.get(slot, "slot_%d" % slot))

static func decode_actor(payload: PackedByteArray, enhanced: bool, extended := false) -> Dictionary:
	var minimum := 31 if enhanced else (19 if extended else 18)
	if payload.size() < minimum:
		return {"type": "invalid", "error": "actor_length"}
	var shift := 1 if extended else 0
	var actor := {
		"type": "actor_spawn", "enhanced": enhanced, "actor_id": u16(payload),
		"x": u16(payload, 2) & 0x7ff, "y": u16(payload, 4) & 0x7ff,
		"rotation": s16(payload, 8),
		"actor_type": u16(payload, 10) if extended else int(payload[10])}
	if enhanced:
		actor["appearance"] = {
			"skin": int(payload[12]), "hair": int(payload[13]), "shirt": int(payload[14]),
			"pants": int(payload[15]), "boots": int(payload[16]), "head": int(payload[17]),
			"eyes": 0,
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
		var name_end: int = payload.find(0, 28)
		if name_end < 0:
			name_end = min(payload.size(), 58)
		actor.merge(decode_actor_name(payload.slice(28, name_end)))
		# The enhanced-actor trailer follows the variable-length name: attached
		# actor id, mount type, eye style, and neck visual. Preserve eye choices
		# across the real server round trip instead of silently reverting to 0.
		var trailer_offset: int = name_end + 1
		if payload.size() >= trailer_offset + 5:
			actor["attached_actor_id"] = u16(payload, trailer_offset)
			actor["mount_type"] = int(payload[trailer_offset + 2])
			var appearance: Dictionary = actor["appearance"] as Dictionary
			appearance["eyes"] = int(payload[trailer_offset + 3])
			var neck_visual: int = int(payload[trailer_offset + 4])
			if neck_visual > 0:
				var equipment_visuals: Dictionary = actor["equipment_visuals"] as Dictionary
				equipment_visuals[7] = neck_visual
	else:
		actor["frame"] = int(payload[11 + shift])
		actor["max_health"] = u16(payload, 12 + shift)
		actor["health"] = u16(payload, 14 + shift)
		actor["kind"] = int(payload[16 + shift])
		var plain_name: PackedByteArray = payload.slice(
			17 + shift, min(payload.size(), 47 + shift))
		var plain_end: int = plain_name.find(0)
		# A plain actor packet is a creature or a scenery NPC. Neither has a
		# guild, and their names routinely contain spaces.
		actor.merge(decode_actor_name(plain_name if plain_end < 0
			else plain_name.slice(0, plain_end), false))
	actor["alive"] = int(actor.get("health", 0)) > 0
	# The frame byte is the actor's current animation state. FRAME_COMBAT_IDLE
	# is the only value that carries gameplay meaning at spawn: an actor
	# already fighting when it comes into view must not be presented as idle
	# until the next enter-combat command, which may never arrive.
	actor["in_combat"] = int(actor.get("frame", FRAME_IDLE)) == FRAME_COMBAT_IDLE
	return actor

## Eternal Lands' text palette (colors.c), in the server's own index order:
## the four shades of a hue are 7 apart, not adjacent. Only the first of each
## entry's four shades is a text colour, so only that one is kept here.
##
## Index 0 is EL's c_red1, but a colour reaches us as the byte `127 + index`
## and a leading 127 is not read as a marker, so 0 never arrives from the wire
## and doubles as "the server chose no colour for this name".
const EL_TEXT_COLOURS: Array[Color] = [
	Color("ffb3c1"), Color("f7c49f"), Color("fbfabe"), Color("c9fecb"),
	Color("a9effa"), Color("d2b4fb"), Color("ffffff"),
	Color("fa5a5a"), Color("fc7a3a"), Color("fcec38"), Color("05fa9b"),
	Color("7697f8"), Color("d95df4"), Color("999999"),
	Color("dd0202"), Color("bf6610"), Color("e7ae14"), Color("25c400"),
	Color("4448d2"), Color("8254f6"), Color("9e9e9e"),
	Color("7e0303"), Color("833003"), Color("826f06"), Color("149504"),
	Color("0f0fba"), Color("6a01ac"), Color("282828"),
]

## The colour a decoded `name_colour` or `guild_colour` asks for. Returns
## `fallback` for 0 - the server named no colour - and for anything outside the
## palette, so an unknown index degrades to the plain nameplate rather than to
## black.
static func el_text_colour(colour_index: int, fallback := Color.WHITE) -> Color:
	if colour_index <= 0 or colour_index >= EL_TEXT_COLOURS.size():
		return fallback
	return EL_TEXT_COLOURS[colour_index]

## Splits the display name an actor packet carries into the parts it is really
## made of: the name, the colour the server chose for it, and the guild tag
## with its own colour.
##
## The server builds one string - an optional colour byte, the name, then a
## space, an optional colour byte and the guild tag - and a client that takes
## the whole thing as a name renders the colour bytes as mojibake and the tag
## as part of the player's name. Both colours are the server's choice, so they
## are decoded rather than dropped, and neither is ever chosen here.
static func decode_actor_name(bytes: PackedByteArray,
		space_separates_tag := true) -> Dictionary:
	var name_colour: int = 0
	var body: PackedByteArray = bytes
	if not body.is_empty() and body[0] > 127:
		name_colour = int(body[0]) - 127
		body = body.slice(1)
	var guild_colour: int = 0
	var guild_tag: String = ""
	# The tag's own colour marker is the reliable separator, because it cannot
	# occur inside a name. The trailing space is only a fallback for a server
	# that sent an uncoloured tag, and it is never used for a creature or NPC:
	# "Mirrorfin Otter" is one name, and splitting it on the space turns every
	# two-word creature into "Mirrorfin [Otter]".
	var marker: int = -1
	for offset: int in range(body.size()):
		if body[offset] > 127:
			marker = offset
			break
	var space: int = marker - 1 if marker > 0 else (
		body.rfind(32) if space_separates_tag else -1)
	if space > 0 and body[space] == 32:
		var tag_bytes: PackedByteArray = body.slice(space + 1)
		if not tag_bytes.is_empty():
			if tag_bytes[0] > 127:
				guild_colour = int(tag_bytes[0]) - 127
				tag_bytes = tag_bytes.slice(1)
			guild_tag = tag_bytes.get_string_from_ascii()
			body = body.slice(0, space)
	return {"name": body.get_string_from_ascii(), "name_colour": name_colour,
		"guild_tag": guild_tag, "guild_colour": guild_colour}

static func nul_string(bytes: PackedByteArray) -> String:
	var end := bytes.find(0)
	var clean := bytes if end < 0 else bytes.slice(0, end)
	return clean.get_string_from_utf8()

## The palette index of the colour byte a chat line opens with, or 0 when the
## server led with plain text. Only the leading byte is read: mid-line colour
## changes are stripped by `legacy_colored_string`, so a line renders in the
## one colour the server chose for it.
static func leading_text_colour(bytes: PackedByteArray) -> int:
	if bytes.is_empty():
		return 0
	var index: int = int(bytes[0]) - 127
	if index <= 0 or index >= EL_TEXT_COLOURS.size():
		return 0
	return index

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

## Little-endian 64-bit. Read as two 32-bit halves because shifting a byte to
## bit 56 in one expression is where a signed-integer surprise would hide.
static func u64(bytes: PackedByteArray, offset := 0) -> int:
	return u32(bytes, offset) | (u32(bytes, offset + 4) << 32)

static func u32(bytes: PackedByteArray, offset := 0) -> int:
	return (int(bytes[offset]) | (int(bytes[offset + 1]) << 8)
		| (int(bytes[offset + 2]) << 16) | (int(bytes[offset + 3]) << 24))

static func s32(bytes: PackedByteArray, offset := 0) -> int:
	var value: int = u32(bytes, offset)
	return value - 4294967296 if value >= 2147483648 else value
