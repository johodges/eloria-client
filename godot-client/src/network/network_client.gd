extends Node

signal connection_state_changed(state: String)
signal packet_received(command: int, payload: PackedByteArray)
signal protocol_error(message: String)

const PROTOCOL_MAJOR := 9
const PROTOCOL_MINOR := 5
const CLIENT_VERSION := PackedByteArray([0, 1, 0, 0])

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
	if not sensitive:
		print_debug("protocol tx bytes=", frame.hex_encode())
	return _peer.put_data(frame)

func login(username: String, password: String) -> Error:
	return send_frame(EloriaProtocol.login(username, password), true)

func _process(_delta: float) -> void:
	_peer.poll()
	var status := _peer.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED and _state != "connected":
		_set_state("connected")
		# Matches the legacy connection lifecycle. Server currently tolerates/ignores version metadata.
		send_frame(EloriaProtocol.version(PROTOCOL_MAJOR, PROTOCOL_MINOR, CLIENT_VERSION))
		send_frame(EloriaProtocol.encode(EloriaProtocol.ClientMessage.SEND_OPENING_SCREEN))
	elif status == StreamPeerTCP.STATUS_ERROR:
		protocol_error.emit("socket_error")
		disconnect_from_server()
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
	while true:
		var decoded := EloriaProtocol.try_decode(_rx)
		match decoded.status:
			"incomplete":
				return
			"error":
				protocol_error.emit(decoded.error)
				disconnect_from_server()
				return
			"ok":
				_rx = _rx.slice(decoded.consumed)
				packet_received.emit(decoded.command, decoded.payload)

func _set_state(value: String) -> void:
	if _state == value:
		return
	_state = value
	connection_state_changed.emit(value)
