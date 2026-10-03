extends SceneTree
## The editor's reader of the server's 16-bit served grid ("ESCG version 2"),
## against the golden fixture eloria-server pins: the header, the row delta,
## the decoded codes, the CRC and SHA-256 checks, every refusal of the server's
## reader, and the decode time of a 2 km map's grid.
##
## Godot_v4.7.2-stable_win64_console.exe --headless --path . \
##     --script res://tests/test_map_authoring_served_grid.gd

const ServedGrid := preload("res://addons/map_authoring_usability/served_grid.gd")
## A byte copy of eloria-server tests/fixtures/served_grid_golden.escg.gz and
## its description. The SHA-256 is a literal here and in the server's
## tests/test_served_grid_format.py; neither test reads the other checkout, so a
## fixture changed on one side alone fails that side's suite.
const GOLDEN_PATH := "res://tests/fixtures/served_grid_golden.escg.gz"
const GOLDEN_JSON_PATH := "res://tests/fixtures/served_grid_golden.json"
const GOLDEN_SHA256 := "7e4522023885486b2a47298826b3fad1d30ba6d660dcc80249c8690d30e66c12"
## The size of a 2 km continent-v2 map, for the decode timing (target < 2 s).
const LARGE := 2046

var failures := 0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var blob := FileAccess.get_file_as_bytes(GOLDEN_PATH)
	var description: Variant = JSON.parse_string(FileAccess.get_file_as_string(GOLDEN_JSON_PATH))
	_expect(not blob.is_empty() and description is Dictionary,
		"the golden fixture and its description are in res://tests/fixtures")
	if blob.is_empty() or not description is Dictionary:
		_finish()
		return
	_test_pin(blob, description)
	var grid := ServedGrid.decode_file(blob, GOLDEN_SHA256)
	_expect(not grid.has("error"), "the golden fixture decodes (%s)" % String(grid.get("error", "ok")))
	if grid.has("error"):
		_finish()
		return
	_test_decode(grid, description)
	_test_refusals(blob)
	_test_large_grid()
	_finish()


func _test_pin(blob: PackedByteArray, description: Dictionary) -> void:
	_expect(ServedGrid.sha256_hex(blob) == GOLDEN_SHA256 and
		String(description.get("sha256", "")) == GOLDEN_SHA256,
		"the client's copy of the golden fixture is the server's, by its pinned SHA-256")


func _test_decode(grid: Dictionary, description: Dictionary) -> void:
	_expect(int(grid.width) == int(description.width) and int(grid.height) == int(description.height) and
		int(grid.datum_mm) == int(description.datumMillimetres) and int(grid.datum_mm) == -100000 and
		int(grid.unit_mm) == int(description.unitMillimetres) and int(grid.unit_mm) == 50 and
		int(grid.climb_mm) == int(description.climbMillimetres) and int(grid.climb_mm) == 1000 and
		int(grid.climb_units) == int(description.climbUnits) and int(grid.climb_units) == 20 and
		int(grid.filter) == int(description.filter) and int(grid.filter) == 1,
		"the header reads as the server wrote it: 24 x 16, datum -100 m, 50 mm, climb 1.0 m, row delta")
	var codes: PackedInt32Array = grid.codes
	_expect(ServedGrid.sha256_hex(ServedGrid.payload_bytes(codes)) ==
		String(description.decodedPayloadSha256),
		"the decoded codes hash to the server's decoded payload (little-endian u16)")
	var matching := 0
	var seen := {}
	for sample: Dictionary in description.samples:
		if codes[int(sample.y) * int(grid.width) + int(sample.x)] == int(sample.code):
			matching += 1
		seen[int(sample.code)] = true
	_expect(matching == (description.samples as Array).size() and seen.has(64) and seen.has(128) and
		seen.has(4032) and seen.has(4096) and seen.has(32704),
		"every sample tile has the server's code (%d of %d), 64, 128, 4,032, 4,096 and 32,704 among them" %
			[matching, (description.samples as Array).size()])


func _test_refusals(blob: PackedByteArray) -> void:
	var tampered := blob.duplicate()
	tampered[blob.size() / 2] = tampered[blob.size() / 2] ^ 0x01
	var refused := ServedGrid.decode_file(tampered, GOLDEN_SHA256)
	_expect(refused.has("error") and "SHA-256" in String(refused.error),
		"a tampered file is refused by its SHA-256 (%s)" % String(refused.get("error", "accepted")))
	_expect(ServedGrid.decode_file(tampered).has("error"),
		"and refused without a declared hash too, by the gzip or the grid's own CRC")
	var raw := blob.decompress_dynamic(ServedGrid.MAX_FILE_BYTES, FileAccess.COMPRESSION_GZIP)
	var keywords := ["not a served grid", "version", "header size", "filter", "flags", "reserved",
		"does not divide", "dimensions", "CRC"]
	var refusals := 0
	var notes := PackedStringArray()
	for keyword: String in keywords:
		var result := ServedGrid.decode(_mutated(raw, keyword))
		if result.has("error") and keyword in String(result.error):
			refusals += 1
		else:
			notes.append("%s: %s" % [keyword, String(result.get("error", "accepted"))])
	var truncated := ServedGrid.decode(raw.slice(0, raw.size() - 2))
	var trailing := raw.duplicate()
	trailing.append_array(PackedByteArray([0, 0]))
	var after := ServedGrid.decode(trailing)
	var high := ServedGrid.decode(_encode(PackedInt32Array([4000, 40000]), 2, 1, 0))
	_expect(refusals == keywords.size() and "truncated" in String(truncated.get("error", "")) and
		"after its payload" in String(after.get("error", "")) and
		"exceeds" in String(high.get("error", "")),
		"the header, payload and CRC refusals of the server's reader all hold%s" % (
			"" if notes.is_empty() else " except " + ", ".join(notes)))
	var raw_filter := ServedGrid.decode(_encode(PackedInt32Array([64, 4096, 0, 32704, 128, 1]), 3, 2, 0))
	_expect(not raw_filter.has("error") and int(raw_filter.filter) == 0 and
		raw_filter.codes == PackedInt32Array([64, 4096, 0, 32704, 128, 1]),
		"filter 0 (the ELM block's raw payload) decodes too")


## Decode time for a 2 km map's grid (plan target: under 2 s).
func _test_large_grid() -> void:
	var codes := PackedInt32Array()
	codes.resize(LARGE * LARGE)
	for y in LARGE:
		var row := y * LARGE
		for x in LARGE:
			# Gentle relief (under the climb) with a blocked lattice every 64 tiles.
			codes[row + x] = 0 if (x % 64 == 0 and y % 3 == 0) else 2000 + (x + 2 * y) % 400 / 25
	var blob := _encode(codes, LARGE, LARGE, 1).compress(FileAccess.COMPRESSION_GZIP)
	var sha := ServedGrid.sha256_hex(blob)
	var started := Time.get_ticks_usec()
	var decoded := ServedGrid.decode_file(blob, sha)
	var decode_ms := float(Time.get_ticks_usec() - started) / 1000.0
	var same: bool = not decoded.has("error") and decoded.codes == codes
	print("served grid %d x %d: %d KiB gzipped, decode %.0f ms (SHA-256, gunzip, row delta, CRC)" %
		[LARGE, LARGE, blob.size() / 1024, decode_ms])
	_expect(same and decode_ms < 2000.0,
		"a %d x %d grid decodes exactly in %.0f ms (target under 2 s)" % [LARGE, LARGE, decode_ms])


## The golden grid's uncompressed bytes with one header field broken, named by
## a word of the refusal it must cause.
func _mutated(raw: PackedByteArray, keyword: String) -> PackedByteArray:
	var bytes := raw.duplicate()
	match keyword:
		"not a served grid":
			bytes[0] = 0x58
		"version":
			bytes.encode_u16(4, 1)
		"header size":
			bytes.encode_u16(6, 24)
		"filter":
			bytes.encode_u8(24, 2)
		"flags":
			bytes.encode_u8(25, 1)
		"reserved":
			bytes.encode_u16(26, 1)
		"does not divide":
			bytes.encode_u16(20, 30)
		"dimensions":
			bytes.encode_u32(8, 0)
		"CRC":
			bytes.encode_u32(28, bytes.decode_u32(28) ^ 1)
	return bytes


## An uncompressed served grid as the server's codec writes it.
func _encode(codes: PackedInt32Array, width: int, height: int, filter: int) -> PackedByteArray:
	var header := PackedByteArray()
	header.resize(ServedGrid.HEADER_SIZE)
	header.encode_u32(0, 0x47435345)  # "ESCG"
	header.encode_u16(4, ServedGrid.VERSION)
	header.encode_u16(6, ServedGrid.HEADER_SIZE)
	header.encode_u32(8, width)
	header.encode_u32(12, height)
	header.encode_s32(16, ServedGrid.DATUM_MM)
	header.encode_u16(20, ServedGrid.UNIT_MM)
	header.encode_u16(22, ServedGrid.CLIMB_MM)
	header.encode_u8(24, filter)
	header.encode_u32(28, ServedGrid.crc32(ServedGrid.payload_bytes(codes)))
	var stored := codes
	if filter == ServedGrid.FILTER_ROW_DELTA:
		stored = PackedInt32Array()
		stored.resize(codes.size())
		for y in height:
			var previous := 0
			for x in width:
				var value := codes[y * width + x]
				stored[y * width + x] = (value - previous) & 0xFFFF
				previous = value
	header.append_array(ServedGrid.payload_bytes(stored))
	return header


func _expect(condition: bool, message: String) -> bool:
	if condition:
		print("PASS: ", message)
		return true
	failures += 1
	push_error("FAIL: " + message)
	return false


func _finish() -> void:
	print("map authoring served grid: ", "PASS" if failures == 0 else "FAIL (%d)" % failures)
	quit(failures)
