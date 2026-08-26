# Protocol compatibility specification (baseline)

Authoritative sources: server `eloria/protocol.py`, server protocol tests, legacy client `client_serv.h`, `connection.cpp`, and `multiplayer.c` at the audited revisions.

## Transport and framing

TCP stream. Each frame is `command:u8 | wire_length:u16le | payload`. `wire_length` includes the command byte, so total bytes on the wire are `wire_length + 2`. Valid payload length is 0–65,532. Reads may be fragmented or contain multiple frames.

Strings are message-specific. Legacy authentication uses NUL-terminated byte strings; server-facing text commonly uses UTF-8, while actor names and legacy login fields require Latin-1-compatible bytes. Integer fields are little-endian unless a packet-specific audit proves otherwise.

## Connection baseline

Endpoint is configurable (legacy `servers.lst` behavior will become a data resource). States are disconnected, connecting, connected, authenticating, loading_world, in_world, and reconnecting. Password frames and credentials are always redacted. Invalid lengths terminate the connection safely.

## Verified identifiers

Client: RAW_TEXT 0, MOVE_TO 1, SEND_PM 2, GET_PLAYER_INFO 5, RUN_TO 6, SIT_DOWN 7, SEND_ME_MY_ACTORS 8, SEND_VERSION 10, PING 13, HEART_BEAT 14, LOCATE_ME 15, USE_MAP_OBJECT 16, stats 17, inventory 18, harvest 21, drop 22, pickup 23, inspect bag 25, NPC response 29, manufacture 30, item use 31, trade 32–38, cast 39, attack 40, storage 44–47, login 140, create 141, date/time 230/231.

Server: RAW_TEXT 0, actor spawn 1/51, actor command 2, YOU_ARE 3, clock 4/5, actor removal 6, map change 7, combat mode 8, clear actors 9, stats 18, inventory 19–22, ground/bags 23–29, NPC 30–33, trade 35–41, equipment 52/53, ping 60, storage 67–69, spell 70, channels 71, actor health 73, cooldowns 77, buffs 78, effects 79, popup 83, map markers 90/91, achievements 95, login results 250/251, creation results 252/253.

## Authentication

The initial implementation encodes `LOG_IN(140)` as `username\0password\0`, matching the legacy flow under audit. Before declaring authentication verified, capture the actual outgoing legacy frame and compare it byte-for-byte, including version/session fields if the selected server configuration requires them.

## Coordinate baseline

Movement payload is `x:u16le, y:u16le`. Actor packets use 11-bit tile coordinates in server serialization. Godot conversion is centralized and will be finalized from map/client inspection; no scene may implement its own conversion.

## Open verification items

Full field tables for every identifier; version sequence and capability behavior; keepalive cadence; map-change filename encoding; enhanced actor optional tail; every inventory/trade/storage variant; reconnect policy. These remain explicit blockers in traceability rather than assumed behavior.
