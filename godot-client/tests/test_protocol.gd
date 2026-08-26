extends SceneTree

var failures := 0

func _init() -> void:
	_expect_bytes("empty frame", EloriaProtocol.encode(13), PackedByteArray([13, 1, 0]))
	_expect_bytes("move fixture", EloriaProtocol.move_to(0x1234, 0x5678), PackedByteArray([1, 5, 0, 0x34, 0x12, 0x78, 0x56]))
	var combined := EloriaProtocol.encode(11)
	combined.append_array(EloriaProtocol.encode(5, PackedByteArray([9, 0])))
	var first := EloriaProtocol.try_decode(combined)
	_expect(first.status == "ok" and first.command == 11 and first.consumed == 3, "combined first")
	var fragmented := EloriaProtocol.try_decode(PackedByteArray([1, 5]))
	_expect(fragmented.status == "incomplete", "fragmented header")
	var invalid := EloriaProtocol.try_decode(PackedByteArray([1, 0, 0]))
	_expect(invalid.status == "error", "invalid length")
	print("protocol tests: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)

func _expect_bytes(label: String, actual: PackedByteArray, expected: PackedByteArray) -> void:
	_expect(actual == expected, label + ": " + actual.hex_encode())

func _expect(condition: bool, label: String) -> void:
	if not condition:
		failures += 1
		push_error(label)
