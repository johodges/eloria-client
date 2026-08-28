# Protocol compatibility specification (baseline)

Authoritative sources: server `eloria/protocol.py`, server protocol tests, legacy client `client_serv.h`, `connection.cpp`, and `multiplayer.c` at the audited revisions.

## Transport and framing

TCP stream. Each frame is `command:u8 | wire_length:u16le | payload`. `wire_length` includes the command byte, so total bytes on the wire are `wire_length + 2`. Valid payload length is 0–65,532. Reads may be fragmented or contain multiple frames.

Strings are message-specific. Legacy authentication uses NUL-terminated byte strings; server-facing text commonly uses UTF-8, while actor names and legacy login fields require Latin-1-compatible bytes. Integer fields are little-endian unless a packet-specific audit proves otherwise.

## Connection baseline

Endpoint is configurable (legacy `servers.lst` behavior will become a data resource). States are disconnected, connecting, connected, authenticating, loading_world, in_world, and reconnecting. Password frames and credentials are always redacted. Invalid lengths terminate the connection safely.

## Verified identifiers

Client: RAW_TEXT 0, MOVE_TO 1, SEND_PM 2, GET_PLAYER_INFO 5, RUN_TO 6, SIT_DOWN 7, SEND_ME_MY_ACTORS 8, SEND_VERSION 10, TURN_LEFT 11, TURN_RIGHT 12, PING 13, HEART_BEAT 14, LOCATE_ME 15, USE_MAP_OBJECT 16, stats 17, inventory 18, harvest 21, drop 22, pickup 23, inspect bag 25, NPC response 29, manufacture 30, item use 31, trade 32–38, cast 39, attack 40, storage 44–47, login 140, create 141, date/time 230/231.

Server: RAW_TEXT 0, actor spawn 1/51, actor command 2, YOU_ARE 3, clock 4/5, actor removal 6, map change 7, combat mode 8, clear actors 9, stats 18, inventory 19–22, ground/bags 23–29, NPC 30–33, trade 35–41, equipment 52/53, ping 60, storage 67–69, spell 70, channels 71, actor health 73, cooldowns 77, buffs 78, effects 79, popup 83, map markers 90/91, achievements 95, login results 250/251, creation results 252/253.

## Authentication

LOG_IN(140) is username, one ASCII space, password, then NUL. This matches legacy send_login_info() and server _credentials(). On connection the client first sends SEND_VERSION with protocol 10.31, application 1.9.7.0, IPv4 bytes, and a network-order port, followed by SEND_OPENING_SCREEN. Password-containing frames are always redacted.

## Coordinate baseline

Movement payload is `x:u16le, y:u16le`. Actor packets use 11-bit tile coordinates in server serialization. Godot conversion is centralized and will be finalized from map/client inspection; no scene may implement its own conversion.

Actor movement is advanced by server `ADD_ACTOR_COMMAND` frames: commands 20–27
are one-tile walk steps and 30–37 are the equivalent run steps. `SIT_DOWN(7)`
carries one desired-state byte (`1` sit, `0` stand); the server broadcasts actor
commands 13/14 after accepting the state change. The legacy default is Alt+S.

Facing is server-owned. `TURN_LEFT(11)` and `TURN_RIGHT(12)` carry no payload
and each request one 45° step; left is counter-clockwise seen from above. The
server rotates the character and broadcasts the matching turn actor command
38–45 (`CMD_TURN_N` … `CMD_TURN_NW`, clockwise from north) to everyone on the
map, so a turn is visible to other players. A turn command changes facing
without moving the actor. The same facing is stored in the actor packet's
signed 16-bit `rotation` field as `direction_index × 8192`, wrapped into
−32768…32767, so a client that spawns the actor later sees the direction a
client that watched the turn sees. Walking also updates that field from the
step direction. A seated player does not turn; the server ignores the request,
because the turn animation would break the seated pose. The client may render
one predicted step while the reply is in flight, but the reply replaces it.

Chat sends `RAW_TEXT(0)` as UTF-8 plus NUL. A private message sends
`SEND_PM(2)` as `recipient ASCII-space message NUL`, omitting the leading slash
typed in the legacy input line; payloads beginning with `/` implement the
legacy `// message` reply-to-last-sender shortcut. Incoming private messages
are normal `RAW_TEXT(0)` frames on channel 1. Local, personal, server, and the
three rendered channel tabs use channel IDs 0, 1, 3, and 5–7 respectively.
Standalone legacy color-control bytes are presentation metadata and are
removed from DTO text without removing valid UTF-8 continuation bytes.
NPC activation sends
`TOUCH_PLAYER(28)` with `actor_id:u32le`. Dialogue uses `SEND_NPC_INFO(33)`,
`NPC_TEXT(30)`, and a repeated `NPC_OPTIONS_LIST(31)` entry layout of
`text_size:u16le | NUL text | response_id:u16le | actor_id:u16le`; replies send
`RESPOND_TO_NPC(29)` as `actor_id:u16le | response_id:u16le`.

Inventory snapshots use `HERE_YOUR_INVENTORY(19)` with a count byte followed
by `image_id:u16le | quantity:u32le | slot:u8 | flags:u8` entries. The optional
legacy UID capability extends each entry with `uid:u16le`. Incremental updates
use the same entry in `GET_NEW_INVENTORY_ITEM(21)`; removals are one or more
slot bytes in `REMOVE_ITEM_FROM_INVENTORY(22)`. Inspect and use send one slot
byte with commands 19 and 31. Moving/equipping sends
`MOVE_INVENTORY_ITEM(20)` as `source_slot:u8 | destination_slot:u8`; inventory
positions are 0–35 and the eight generic wear positions are 36–43. Cooldown
command 77 repeats `slot:u8 | maximum_seconds:u16le | remaining_seconds:u16le`.

Actor equipment changes are server commands 52/53. Wear is
`actor_id:u16le | part:u8 | visual_id:u8`; unwear omits the visual byte. Parts
0–7 mean weapon, shield, cape, helmet, legs, body, boots, and neck. These part
IDs are distinct from the eight generic inventory wear positions.

Spell casting sends `CAST_SPELL(39)` as `count:u8 | sigil_id:u8[count]`; the
ordered sigil sequence, not the local spell ID, identifies the spell. The
server publishes ownership with `GET_YOUR_SIGILS(42)` as two `u32le` masks and
returns `SPELL_CAST(70)` as `status:u8 | spell_id:u8`. Status 1 succeeds, 2
fails validation or the cast roll, 3 rejects an invalid/unknown spell, 4 asks
for an actor selected through `TOUCH_PLAYER(28)`, and 5 asks for a location
submitted through the normal movement packet. `GET_ACTIVE_SPELL(44)` carries
`buff_id:u8 | duration_seconds:u8`.

Melee targeting sends `ATTACK_SOMEONE(40)` as `actor_id:u32le`. The server may
approach the target before broadcasting actor command 18 (enter combat), 46
(primary attack), and 19 (leave combat); command 3 is death. Actor damage and
heal messages 47/48 carry `actor_id:u16le | amount:u16le`, while command 73
carries `actor_id:u16le | max_health:u16le`. Creature and PvP range, PK-area,
Peace Day, already-in-combat, death, and flee validation remain server-owned.

Player trade begins with `TRADE_WITH(32)` carrying `actor_id:u32le`; the target
accepts the 30-second request by sending the reciprocal command while within a
four-tile Chebyshev radius. `GET_TRADE_PARTNER_NAME(41)` carries
`storage_available:u8 | name[0..19] | NUL`, followed by
`GET_YOUR_TRADEOBJECTS(40)` using the normal inventory snapshot body. Inventory
offers send `PUT_OBJECT_ON_TRADE(36)` as
`source_type=1:u8 | source_slot:u8 | quantity:u32le`; the server immediately
removes the accepted quantity from inventory and broadcasts `GET_TRADE_OBJECT`
(35) as `image_id:u16le | quantity:u32le | source_type:u8 | offer_slot:u8 |
other:u8`. Removal sends `REMOVE_OBJECT_FROM_TRADE(37)` as
`offer_slot:u8 | quantity:u32le`; server command 39 returns
`quantity:u32le | offer_slot:u8 | other:u8`. `ACCEPT_TRADE(33)` carries sixteen
destination bytes (1 inventory, or 2 storage where allowed). Acceptance is a
server-authoritative two-phase sequence reported by `GET_TRADE_ACCEPT(36)` as
`other:u8 | phase:u8`. Phase 0 is not accepted, 1 is the first stage, and 2 is
the second stage that completes the trade; `other` names the side the phase
belongs to. The client reads the phase and never infers it by counting accept
packets, because a duplicated, dropped or reordered accept would otherwise
desynchronise the two-phase state machine from the server. The server clamps
the phase to 0-2 and the client rejects any other value. Command 37 resets the
indicated side, and command 38 closes the trade. `REJECT_TRADE(34)` only
resets acceptance. `EXIT_TRADE(35)` cancels and restores all offers.

Storage is opened only through a nearby storage NPC dialogue response. Server
command `STORAGE_LIST(67)` carries `count:u8` followed by repeated
`category_id:u8 | NUL name`; `GET_STORAGE_CATEGORY(44)` selects one category by
its `u8` identifier. `STORAGE_ITEMS(68)` starts with
`mode:u8 | category_id:u8`; mode 0 is a full snapshot and mode 255 is one
incremental entry. Each entry is `image_id:u16le | quantity:u32le |
position:u16le`. Deposits use `DEPOSIT_ITEM(45)` as
`inventory_slot:u8 | quantity:u32le`. Withdrawals use `WITHDRAW_ITEM(46)` as
`storage_position:u16le | quantity:u32le`. Inspection uses
`LOOK_AT_STORAGE_ITEM(47)` with a `u16le` position and receives
`STORAGE_TEXT(69)` as `color:u8 | NUL text`. The server validates NPC range,
category/session state, quantities, inventory slots, and carry capacity.

Ground bags are map-authoritative. `GET_NEW_BAG(27)` carries
`x:u16le | y:u16le | bag_id:u8`; `GET_BAGS_LIST(28)` prefixes repeated entries
with a count byte, and `DESTROY_BAG(29)` carries the map-local bag ID. Inspect
sends `INSPECT_BAG(25)` with that ID. The server approaches the bag when
needed, then `HERE_YOUR_GROUND_ITEMS(23)` sends `count:u8` plus repeated
`image_id:u16le | quantity:u32le | position:u8` entries. Incremental add and
remove commands are 24 and 25; command 26 closes the view. Pickup sends
`PICK_UP_ITEM(23)` as `position:u8 | quantity:u32le`; dropping sends
`DROP_ITEM(22)` as `inventory_slot:u8 | quantity:u32le`. The server owns bag
creation/destruction, interaction range, carry capacity, quantities, and the
resulting inventory snapshots.

Knowledge ownership is sent by `GET_KNOWLEDGE_LIST(55)` as a little-endian
bitset: bit `index % 8` of byte `index / 8` marks one catalog entry as read.
`GET_NEW_KNOWLEDGE(56)` carries a newly completed `index:u16le`. Selecting an
entry sends `GET_KNOWLEDGE_INFO(41)` with `index:u16le`, and the server replies
with `GET_KNOWLEDGE_TEXT(57)` as NUL-terminated UTF-8. Index-to-name mapping is
the insertion-ordered result of the server's `load_books` catalog, excluding
repeatable big books; the checked-in Godot catalog records the exact source
configuration hashes used to generate it. Reading itself remains initiated by
using a server-recognized book from inventory, and the server owns progress,
completion, recipe gating, and rejection messages.

Manufacturing sends `MANUFACTURE_THIS(30)` as `count:u8`, followed by `count`
entries of `inventory_slot:u8 | quantity:u16le`, and a trailing `wanted:u8`.
The legacy tray and imported server catalog both cap ingredient entries at six.
`wanted=1` requests one attempt and `wanted=255` requests the legacy mix-all
loop. The server matches authoritative item names and quantities to one exact
recipe; validates knowledge, tools, skills, food, ethereal points, combat,
special days, nexus, and carry capacity; then reports outcomes through the
existing inventory text (20), raw text (0), inventory (19/21/22), and
partial/full statistics (49/18) messages. The checked-in recipe catalog is
generated from the unmodified server's recipes, items, and books configuration
and records all three source hashes. Recipes whose distinct item names share a
legacy image ID are shown but automatic mixing remains disabled, because the
default inventory wire format transmits neither an item name nor UID.

## Open verification items

Full field tables for every identifier; version sequence and capability behavior; keepalive cadence; map-change filename encoding; enhanced actor optional tail; storage-backed trade positions and storage lifecycle; reconnect policy. These remain explicit blockers in traceability rather than assumed behavior.
