class_name EloriaNetworkClient
extends Node

signal connection_state_changed(state: String)
signal packet_received(command: int, payload: PackedByteArray)
signal protocol_error(message: String)

const PROTOCOL_MAJOR := 10
const PROTOCOL_MINOR := 31
static var client_version: PackedByteArray = PackedByteArray([1, 9, 7, 0])

var _peer := StreamPeerTCP.new()
var _rx := PackedByteArray()
var _state := "disconnected"

func connect_to_server(host: String, port: int) -> Error:
	_set_state("connecting")
	var error := _peer.connect_to_host(host, port)
	if error != OK:
		_set_state("disconnected")
	return error

func disconnect_from_server() -> void:
	_peer.disconnect_from_host()
	_rx.clear()
	_set_state("disconnected")

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
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED and _state != "connected":
		_set_state("connected")
		# Matches the legacy connection lifecycle. Server currently tolerates/ignores version metadata.
		send_frame(EloriaProtocol.version(PROTOCOL_MAJOR, PROTOCOL_MINOR, client_version))
		send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.SEND_OPENING_SCREEN))
	elif status == StreamPeerTCP.STATUS_ERROR:
		protocol_error.emit("socket_error")
		disconnect_from_server()
		return
	elif status != StreamPeerTCP.STATUS_CONNECTED:
		return
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
				protocol_error.emit(decoded.error)
				disconnect_from_server()
				return
			"ok":
				consumed += int(decoded.consumed)
				packet_received.emit(decoded.command, decoded.payload)

func _trim_receive_buffer(consumed: int) -> void:
	if consumed <= 0:
		return
	_rx = _rx.slice(consumed)

func _set_state(value: String) -> void:
	if _state == value:
		return
	_state = value
	connection_state_changed.emit(value)
