class_name EloriaNetworkClient
extends Node

signal connection_state_changed(state: String)
signal packet_received(command: int, payload: PackedByteArray)
signal protocol_error(message: String)

const PROTOCOL_MAJOR := 10
const PROTOCOL_MINOR := 31
static var client_version: PackedByteArray = PackedByteArray([1, 9, 7, 0])

## The legacy client sends a heartbeat every 25 seconds because a server may
## drop a connection that has been silent for 30. Eloria's server closes a
## logged-in connection after `client_idle_timeout_seconds`, which exists so a
## half-open socket cannot hold a character hostage; this is what keeps a
## parked client on the right side of it.
const HEARTBEAT_INTERVAL_MSEC := 25000
## Backoff for an unexpected drop. A deliberate disconnect never reconnects.
const RECONNECT_DELAYS_MSEC: Array[int] = [1000, 2000, 4000, 8000, 15000]

signal reconnect_progress(attempt: int, total: int, delay_msec: int)

var _peer := StreamPeerTCP.new()
var _tls := StreamPeerTLS.new()
var _rx := PackedByteArray()
var _state := "disconnected"
var _host := ""
var _port := 0
var _reconnect_enabled := false
var _reconnect_attempt := 0
var _reconnect_at_msec := 0
var _last_heartbeat_msec := 0

## Whether this session wraps the socket in TLS. The protocol is identical
## either way: only the bytes between this client and the socket change, so
## nothing above `send_frame` and `_drain_packets` knows the difference.
var _secure := false
## A certificate to trust in addition to the system store. A development
## server signs its own certificate, which no trust store will ever accept;
## pointing at that file is what lets a laptop connect without turning
## verification off for real servers too.
var _trusted_certificate_path := ""
var _handshaking := false

## True once the socket is usable for protocol traffic. With TLS that means
## the handshake finished, not merely that TCP connected.
func _link_ready() -> bool:
	if _secure:
		return _tls.get_status() == StreamPeerTLS.STATUS_CONNECTED
	return _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED

func _link() -> StreamPeer:
	return _tls if _secure else _peer

func connect_to_server(host: String, port: int, secure := false,
		trusted_certificate_path := "") -> Error:
	_host = host
	_port = port
	_secure = secure
	_trusted_certificate_path = trusted_certificate_path
	_handshaking = false
	_set_state("connecting")
	var error := _peer.connect_to_host(host, port)
	if error != OK:
		_set_state("disconnected")
	return error

func is_secure() -> bool:
	return _secure and _link_ready()

## Starts the TLS handshake over the freshly opened TCP socket.
func _begin_handshake() -> bool:
	var options: TLSOptions = null
	if not _trusted_certificate_path.is_empty():
		var certificate := X509Certificate.new()
		if certificate.load(_trusted_certificate_path) != OK:
			_drop_connection("tls_certificate_unreadable")
			return false
		options = TLSOptions.client(certificate)
	else:
		options = TLSOptions.client()
	# The common name is checked against the certificate, so a server whose
	# certificate does not name the host the player typed is refused rather
	# than silently accepted.
	if _tls.connect_to_stream(_peer, _host, options) != OK:
		_drop_connection("tls_handshake_failed")
		return false
	_handshaking = true
	_set_state("securing")
	return true

## A disconnect the player asked for. Cancels any pending reconnect, so the
## client does not fight the person who just pressed the button.
func disconnect_from_server() -> void:
	_reconnect_enabled = false
	_reconnect_attempt = 0
	_reconnect_at_msec = 0
	if _secure:
		_tls.disconnect_from_stream()
	_handshaking = false
	_peer.disconnect_from_host()
	_rx.clear()
	_set_state("disconnected")

func is_reconnecting() -> bool:
	return _reconnect_at_msec > 0

func reconnect_attempt() -> int:
	return _reconnect_attempt

## Rebuilds authoritative state on a connection whose continuity is in doubt.
## Actors, statistics and inventory are the three snapshots the server will
## resend on request; everything else follows from them.
func request_resync() -> Error:
	var actors_error: Error = send_frame(EloriaProtocol.encode(
		EloriaProtocol.ClientMessage.SEND_ME_MY_ACTORS))
	var stats_error: Error = send_frame(EloriaProtocol.encode(
		EloriaProtocol.ClientMessage.SEND_MY_STATS))
	var inventory_error: Error = send_frame(EloriaProtocol.encode(
		EloriaProtocol.ClientMessage.SEND_MY_INVENTORY))
	if actors_error != OK:
		return actors_error
	if stats_error != OK:
		return stats_error
	return inventory_error

## Called when the socket drops without the player asking for it.
func _schedule_reconnect() -> void:
	if not _reconnect_enabled or _host.is_empty():
		return
	if _reconnect_attempt >= RECONNECT_DELAYS_MSEC.size():
		_reconnect_enabled = false
		_reconnect_at_msec = 0
		return
	var delay: int = RECONNECT_DELAYS_MSEC[_reconnect_attempt]
	_reconnect_attempt += 1
	_reconnect_at_msec = Time.get_ticks_msec() + delay
	_set_state("reconnecting")
	reconnect_progress.emit(_reconnect_attempt, RECONNECT_DELAYS_MSEC.size(), delay)

func _drop_connection(reason: String) -> void:
	protocol_error.emit(reason)
	if _secure:
		_tls.disconnect_from_stream()
	_handshaking = false
	_peer.disconnect_from_host()
	_rx.clear()
	_set_state("disconnected")
	_schedule_reconnect()

func send_frame(frame: PackedByteArray, sensitive := false) -> Error:
	if not _link_ready():
		return ERR_UNCONFIGURED
	# hex_encode() allocates a string for every outgoing packet; print_debug is
	# a no-op outside debug builds but its arguments were evaluated regardless.
	if not sensitive and OS.is_debug_build():
		print_debug("protocol tx bytes=", frame.hex_encode())
	return _link().put_data(frame)

func login(username: String, password: String) -> Error:
	return send_frame(EloriaProtocol.login(username, password), true)

func move_to(tile: Vector2i, run := false) -> Error:
	return send_frame(EloriaProtocol.move_to(tile.x, tile.y, run))

func set_sitting(sitting: bool) -> Error:
	return send_frame(EloriaProtocol.set_sitting(sitting))

func turn(left: bool) -> Error:
	return send_frame(EloriaProtocol.turn(left))

func send_client_capabilities() -> Error:
	return send_frame(EloriaProtocol.client_capabilities())

func send_chat(text: String) -> Error:
	return send_frame(EloriaProtocol.chat(text))

func set_active_channel(slot: int) -> Error:
	return send_frame(EloriaProtocol.set_active_channel(slot))

func locate_me() -> Error:
	return send_frame(EloriaProtocol.locate_me())

func request_server_date() -> Error:
	return send_frame(EloriaProtocol.get_date())

func request_server_time() -> Error:
	return send_frame(EloriaProtocol.get_time())

func send_private_message(text: String) -> Error:
	return send_frame(EloriaProtocol.private_message(text))

func touch_actor(actor_id: int) -> Error:
	return send_frame(EloriaProtocol.touch_actor(actor_id))

func respond_to_npc(actor_id: int, response_id: int) -> Error:
	return send_frame(EloriaProtocol.npc_response(actor_id, response_id))

func look_at_inventory_item(slot: int) -> Error:
	return send_frame(EloriaProtocol.look_at_inventory_item(slot))

func use_inventory_item(slot: int) -> Error:
	return send_frame(EloriaProtocol.use_inventory_item(slot))

func fire_missile_at_object(x: int, y: int) -> Error:
	return send_frame(EloriaProtocol.fire_missile_at_object(x, y))

func what_quest_is_this_id(quest_id: int) -> Error:
	return send_frame(EloriaProtocol.what_quest_is_this_id(quest_id))

func do_emote(name: String) -> Error:
	return send_frame(EloriaProtocol.do_emote(name))

func item_on_item(source_slot: int, target_slot: int) -> Error:
	return send_frame(EloriaProtocol.item_on_item(source_slot, target_slot))

func move_inventory_item(source: int, destination: int) -> Error:
	return send_frame(EloriaProtocol.move_inventory_item(source, destination))

func cast_spell(sigils: Array[int], power: int = 0) -> Error:
	return send_frame(EloriaProtocol.cast_spell(sigils, power))

func popup_reply(popup_id: int, answers: Dictionary) -> Error:
	return send_frame(EloriaProtocol.popup_reply(popup_id, answers))

func harvest(object_id: int) -> Error:
	return send_frame(EloriaProtocol.harvest(object_id))

func use_map_object(object_id: int) -> Error:
	return send_frame(EloriaProtocol.use_map_object(object_id))

func look_at_ground_item(slot: int) -> Error:
	return send_frame(EloriaProtocol.look_at_ground_item(slot))

func look_at_player(actor_id: int) -> Error:
	return send_frame(EloriaProtocol.look_at_player(actor_id))

func look_at_map_object(object_id: int) -> Error:
	return send_frame(EloriaProtocol.look_at_map_object(object_id))

func attack_actor(actor_id: int) -> Error:
	return send_frame(EloriaProtocol.attack_actor(actor_id))

func trade_with(actor_id: int) -> Error:
	return send_frame(EloriaProtocol.trade_with(actor_id))

func put_inventory_on_trade(source_slot: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.put_inventory_on_trade(source_slot, quantity))

func remove_trade_item(offer_slot: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.remove_trade_item(offer_slot, quantity))

func accept_trade(destinations: PackedByteArray = PackedByteArray()) -> Error:
	return send_frame(EloriaProtocol.accept_trade(destinations))

func reject_trade() -> Error:
	return send_frame(EloriaProtocol.reject_trade())

func exit_trade() -> Error:
	return send_frame(EloriaProtocol.exit_trade())

func look_at_trade_item(offer_slot: int, other: bool) -> Error:
	return send_frame(EloriaProtocol.look_at_trade_item(offer_slot, other))

func get_storage_category(category_id: int) -> Error:
	return send_frame(EloriaProtocol.get_storage_category(category_id))

func deposit_storage(inventory_slot: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.deposit_storage(inventory_slot, quantity))

func withdraw_storage(position: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.withdraw_storage(position, quantity))

func look_at_storage_item(position: int) -> Error:
	return send_frame(EloriaProtocol.look_at_storage_item(position))

func inspect_bag(bag_id: int) -> Error:
	return send_frame(EloriaProtocol.inspect_bag(bag_id))

func close_bag() -> Error:
	return send_frame(EloriaProtocol.close_bag())

func pick_up_ground_item(position: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.pick_up_ground_item(position, quantity))

func drop_inventory_item(slot: int, quantity: int) -> Error:
	return send_frame(EloriaProtocol.drop_inventory_item(slot, quantity))

func get_knowledge_info(index: int) -> Error:
	return send_frame(EloriaProtocol.get_knowledge_info(index))

func manufacture(ingredients: Array[Dictionary], wanted: int = 1) -> Error:
	return send_frame(EloriaProtocol.manufacture(ingredients, wanted))

func create_character(username: String, password: String, appearance: Dictionary) -> Error:
	return send_frame(EloriaProtocol.create_character(username, password, appearance), true)

func _process(_delta: float) -> void:
	if _reconnect_at_msec > 0 and Time.get_ticks_msec() >= _reconnect_at_msec:
		_reconnect_at_msec = 0
		_set_state("connecting")
		# A reconnect gets a fresh TLS session. Reusing the old one would try
		# to resume a handshake against a socket that no longer exists.
		_handshaking = false
		if _secure:
			_tls.disconnect_from_stream()
		if _peer.connect_to_host(_host, _port) != OK:
			_set_state("disconnected")
			_schedule_reconnect()
			return
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerTCP.STATUS_ERROR:
		_drop_connection("socket_error")
		return
	if status != StreamPeerTCP.STATUS_CONNECTED:
		if _state == "connected" or _state == "securing":
			# The peer closed the socket without an error status.
			_drop_connection("connection_closed")
		return

	# TCP is up. A secure session is not usable until the handshake finishes,
	# so the opening frames wait behind it rather than being written in the
	# clear onto a socket that is about to become a TLS stream.
	if _secure:
		if not _handshaking and _state != "connected":
			if not _begin_handshake():
				return
		_tls.poll()
		match _tls.get_status():
			StreamPeerTLS.STATUS_HANDSHAKING:
				return
			StreamPeerTLS.STATUS_ERROR:
				_drop_connection("tls_handshake_failed")
				return
			StreamPeerTLS.STATUS_ERROR_HOSTNAME_MISMATCH:
				# Never retried: a certificate for the wrong host is the exact
				# case encryption exists to catch, so reconnecting into it
				# would be answering the alarm by silencing it.
				_reconnect_enabled = false
				_drop_connection("tls_hostname_mismatch")
				return
			StreamPeerTLS.STATUS_DISCONNECTED:
				if _state == "connected":
					_drop_connection("connection_closed")
				return

	if _state != "connected":
		_reconnect_attempt = 0
		_reconnect_enabled = true
		_handshaking = false
		_last_heartbeat_msec = Time.get_ticks_msec()
		_set_state("connected")
		# Matches the legacy connection lifecycle. Server currently tolerates/ignores version metadata.
		send_frame(EloriaProtocol.version(PROTOCOL_MAJOR, PROTOCOL_MINOR, client_version))
		send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.SEND_OPENING_SCREEN))
	_send_due_heartbeat()
	var link := _link()
	var available := link.get_available_bytes()
	if available > 0:
		var result := link.get_data(available)
		if result[0] != OK:
			protocol_error.emit("socket_read_failed")
			return
		_rx.append_array(result[1])
		_drain_packets()

func _drain_packets() -> void:
	# Slicing the receive buffer after every packet copied the whole remainder
	# once per packet, which is quadratic across a burst. The buffer is now
	# trimmed once, after the burst has been decoded.
	var consumed := 0
	while true:
		var decoded := EloriaProtocol.try_decode(_rx, consumed)
		match decoded.status:
			"incomplete":
				_trim_receive_buffer(consumed)
				return
			"error":
				_trim_receive_buffer(consumed)
				_drop_connection(decoded.error)
				return
			"ok":
				consumed += int(decoded.consumed)
				packet_received.emit(decoded.command, decoded.payload)

func _send_due_heartbeat() -> void:
	var now: int = Time.get_ticks_msec()
	if now - _last_heartbeat_msec < HEARTBEAT_INTERVAL_MSEC:
		return
	_last_heartbeat_msec = now
	send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.HEART_BEAT))

func _trim_receive_buffer(consumed: int) -> void:
	if consumed <= 0:
		return
	_rx = _rx.slice(consumed)

func _set_state(value: String) -> void:
	if _state == value:
		return
	_state = value
	connection_state_changed.emit(value)
