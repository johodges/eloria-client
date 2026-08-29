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
var _rx := PackedByteArray()
var _state := "disconnected"
var _host := ""
var _port := 0
var _reconnect_enabled := false
var _reconnect_attempt := 0
var _reconnect_at_msec := 0
var _last_heartbeat_msec := 0

func connect_to_server(host: String, port: int) -> Error:
	_host = host
	_port = port
	_set_state("connecting")
	var error := _peer.connect_to_host(host, port)
	if error != OK:
		_set_state("disconnected")
	return error

## A disconnect the player asked for. Cancels any pending reconnect, so the
## client does not fight the person who just pressed the button.
func disconnect_from_server() -> void:
	_reconnect_enabled = false
	_reconnect_attempt = 0
	_reconnect_at_msec = 0
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
	_peer.disconnect_from_host()
	_rx.clear()
	_set_state("disconnected")
	_schedule_reconnect()

func send_frame(frame: PackedByteArray, sensitive := false) -> Error:
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return ERR_UNCONFIGURED
	# hex_encode() allocates a string for every outgoing packet; print_debug is
	# a no-op outside debug builds but its arguments were evaluated regardless.
	if not sensitive and OS.is_debug_build():
		print_debug("protocol tx bytes=", frame.hex_encode())
	return _peer.put_data(frame)

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

func move_inventory_item(source: int, destination: int) -> Error:
	return send_frame(EloriaProtocol.move_inventory_item(source, destination))

func cast_spell(sigils: Array[int]) -> Error:
	return send_frame(EloriaProtocol.cast_spell(sigils))

func popup_reply(popup_id: int, answers: Dictionary) -> Error:
	return send_frame(EloriaProtocol.popup_reply(popup_id, answers))

func harvest(object_id: int) -> Error:
	return send_frame(EloriaProtocol.harvest(object_id))

func use_map_object(object_id: int) -> Error:
	return send_frame(EloriaProtocol.use_map_object(object_id))

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
		if _peer.connect_to_host(_host, _port) != OK:
			_set_state("disconnected")
			_schedule_reconnect()
			return
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED and _state != "connected":
		_reconnect_attempt = 0
		_reconnect_enabled = true
		_last_heartbeat_msec = Time.get_ticks_msec()
		_set_state("connected")
		# Matches the legacy connection lifecycle. Server currently tolerates/ignores version metadata.
		send_frame(EloriaProtocol.version(PROTOCOL_MAJOR, PROTOCOL_MINOR, client_version))
		send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.SEND_OPENING_SCREEN))
	elif status == StreamPeerTCP.STATUS_ERROR:
		_drop_connection("socket_error")
		return
	elif status != StreamPeerTCP.STATUS_CONNECTED:
		if _state == "connected":
			# The peer closed the socket without an error status.
			_drop_connection("connection_closed")
		return
	_send_due_heartbeat()
	var available := _peer.get_available_bytes()
	if available > 0:
		var result := _peer.get_data(available)
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
