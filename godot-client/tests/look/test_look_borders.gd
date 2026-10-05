extends SceneTree
## Guards the look pass's region borders (LookBorders), which fade a region's
## ground trims and grass palette into its neighbour's instead of stepping at
## the border.
##
## Both sides of a border must evaluate the same blend at the same spot (the
## neighbour's weight on one side is the other's own share), so a road or a
## field running across it never steps; the blend must reach a half on the
## border line and nothing a feather inside either region; and the continent's
## real regions must find the borders they share.

var failures := 0

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var feather := LookProfile.BORDER_FEATHER_METRES

	# --- Two squares side by side on the 2 m grid, one wound backwards -------
	LookBorders.define({
		"west": [[0, 0], [100, 0], [100, 100], [0, 100]],
		"east": [[100, 0], [100, 100], [200, 100], [200, 0]],
	})
	_expect(LookBorders.neighbours_of("west") == PackedStringArray(["east"])
		and LookBorders.neighbours_of("east") == PackedStringArray(["west"]),
		"two regions that share an edge are each other's neighbours")
	var area := Rect2(40, 0, 120, 100)
	var west := LookBorders.near("west", area, feather)
	var east := LookBorders.near("east", area, feather)
	_expect(west.segments.size() > 0 and east.segments.size() == west.segments.size(),
		"both sides are handed the border (%d, %d segments)"
		% [west.segments.size(), east.segments.size()])
	var worst := 0.0
	for x: float in [60.0, 80.0, 90.0, 99.0, 100.0, 101.0, 110.0, 130.0, 150.0]:
		for z: float in [10.0, 50.0, 90.0]:
			var here := Vector2(x, z)
			var west_other := _weight(here, west)
			var east_other := _weight(here, east)
			# West paints west * (1 - w) + east * w; east paints east * (1 - v)
			# + west * v. They agree when w = 1 - v.
			worst = maxf(worst, absf(west_other - (1.0 - east_other)))
	_expect(worst < 0.0001, "both sides blend to the same colour anywhere (worst %.5f)" % worst)
	_expect(absf(_weight(Vector2(100, 50), west) - 0.5) < 0.0001,
		"the two meet at their mean on the border line")
	_expect(_weight(Vector2(100.0 - feather, 50), west) < 0.0001
		and _weight(Vector2(100.0 + feather, 50), east) < 0.0001,
		"each is wholly its own a feather inside")
	_expect(_weight(Vector2(100.0 + feather, 50), west) > 0.9999,
		"a region's material inside its neighbour takes the neighbour's look")
	_expect(LookBorders.near("west", Rect2(0, 0, 20, 100), feather).segments.is_empty(),
		"a chunk away from every border is handed none")
	_expect(LookBorders.near("nowhere", area, feather).segments.is_empty(),
		"a map off the continent is handed none")

	# --- A staircase border, as the ownership polygons draw them ------------
	var stairs_west: Array = [[0, 0]]
	var stairs_east: Array = []
	for step: int in 20:
		stairs_west.append([60 + step * 2, step * 2])
		stairs_west.append([60 + step * 2, step * 2 + 2])
	stairs_west.append([0, 40])
	stairs_east.append([200, 0])
	stairs_east.append([200, 40])
	for step: int in range(19, -1, -1):
		stairs_east.append([60 + step * 2, step * 2 + 2])
		stairs_east.append([60 + step * 2, step * 2])
	LookBorders.define({"west": stairs_west, "east": stairs_east})
	var stair_area := Rect2(40, 0, 80, 40)
	west = LookBorders.near("west", stair_area, feather)
	east = LookBorders.near("east", stair_area, feather)
	_expect(west.segments.size() >= 1 and west.segments.size() <= 4,
		"a staircase border is simplified to a few segments (%d)" % west.segments.size())
	worst = 0.0
	for x: float in range(50, 110, 3):
		for z: float in range(1, 40, 3):
			worst = maxf(worst, absf(_weight(Vector2(x, z), west)
				- (1.0 - _weight(Vector2(x, z), east))))
	_expect(worst < 0.0001, "a staircase border blends the same from both sides (worst %.5f)"
		% worst)

	# --- Regions in different continent frames never share a border ---------
	LookBorders.define({
		"west": [[0, 0], [100, 0], [100, 100], [0, 100]],
		"east": [[100, 0], [100, 100], [200, 100], [200, 0]],
		"v2_east": [[100, 0], [100, 100], [200, 100], [200, 0]],
	}, {"v2_east": "continent-v2"})
	_expect(LookBorders.neighbours_of("west") == PackedStringArray(["east"])
		and LookBorders.neighbours_of("v2_east").is_empty(),
		"a region of another continent frame on the same ground borders nothing there")

	# --- The continent's own regions ----------------------------------------
	LookBorders.reload()
	var neighbours := LookBorders.neighbours_of("four_gates")
	_expect(neighbours.has("amberwood") and neighbours.has("westhaven")
		and neighbours.has("manymouth_delta") and neighbours.has("mirrorhold"),
		"Four Gates borders Amberwood, Westhaven, Manymouth and Mirrorhold (%s)"
		% ", ".join(neighbours))
	_expect(LookBorders.neighbours_of("verdant_stair").has("ssarathi_ruins"),
		"Verdant Stair borders Ssarathi")
	_expect(LookBorders.neighbours_of("lantern_reach").is_empty(),
		"Lantern Reach, an island off the continent, borders nothing")
	# The continent-v2 island group: sw_isle borders its second map, The Tollholms (task A3), across the seam at
	# x 2437, and its third, The Gull Skerries (task A3b), along z 8259 and x 399; the two new maps do not touch, and
	# none of the three borders the old continent's regions (another frame).
	var isle := LookBorders.neighbours_of("sw_isle")
	isle.sort()
	_expect(isle == PackedStringArray(["gull_skerries", "tollholms"])
		and not LookBorders.neighbours_of("westhaven").has("sw_isle"),
		"sw_isle, in the continent-v2 frame, borders The Gull Skerries and The Tollholms and none of the old "
		+ "continent's regions (%s)" % ", ".join(isle))
	_expect(LookBorders.neighbours_of("tollholms") == PackedStringArray(["sw_isle"]),
		"The Tollholms border sw_isle only (%s)" % ", ".join(LookBorders.neighbours_of("tollholms")))
	_expect(LookBorders.neighbours_of("gull_skerries") == PackedStringArray(["sw_isle"]),
		"The Gull Skerries border sw_isle only (%s)" % ", ".join(LookBorders.neighbours_of("gull_skerries")))

	print("test_look_borders: %s (%d failures)" % ["PASS" if failures == 0 else "FAIL", failures])
	quit(1 if failures > 0 else 0)

## How much of the (one) neighbour `selection` holds the look takes at `xz`.
func _weight(xz: Vector2, selection: Dictionary) -> float:
	var weights := LookBorders.weights(xz, selection)
	return weights[0] if weights.size() > 0 else 0.0

func _expect(ok: bool, what: String) -> void:
	print(("PASS " if ok else "FAIL ") + what)
	if not ok:
		failures += 1
