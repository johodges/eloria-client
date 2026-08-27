class_name AppearanceVariants
extends RefCounted

const PART_HEAD := 3
const PART_PANTS := 4
const PART_SHIRT := 5
const PART_BOOTS := 6

const PART_KEYS := {
	PART_HEAD: "head",
	PART_PANTS: "pants",
	PART_SHIRT: "shirt",
	PART_BOOTS: "boots",
}

const PART_VISUALS := {
	PART_HEAD: [100, 101, 102, 103, 104, 105, 106, 107, 108],
	PART_PANTS: [100, 101, 102, 103, 104, 105],
	PART_SHIRT: [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
	PART_BOOTS: [100, 101, 102, 103, 104, 105],
}

const CULTURE_VISUALS := {
	"luminous": {PART_HEAD: 105, PART_SHIRT: 105},
	"votary": {PART_HEAD: 106, PART_PANTS: 105, PART_SHIRT: 106, PART_BOOTS: 105},
	"glasswarden": {PART_HEAD: 101, PART_PANTS: 101, PART_SHIRT: 101, PART_BOOTS: 101},
	"orun": {PART_HEAD: 103, PART_PANTS: 103, PART_SHIRT: 103, PART_BOOTS: 103},
	"greyhaven": {PART_HEAD: 102, PART_PANTS: 102, PART_SHIRT: 102, PART_BOOTS: 102},
	"ssarathi": {PART_HEAD: 104, PART_PANTS: 104, PART_SHIRT: 104, PART_BOOTS: 104},
	"stoneborn": {PART_HEAD: 107, PART_SHIRT: 107},
	"mycelari": {PART_HEAD: 108, PART_SHIRT: 108},
}

static func equipment_visuals(actor_type: int, appearance: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	var culture: String = culture_for_actor_type(actor_type)
	var preferred: Dictionary = CULTURE_VISUALS.get(culture, {}) as Dictionary
	for raw_part: Variant in PART_KEYS:
		var part: int = int(raw_part)
		var key: String = str(PART_KEYS[part])
		var choice: int = int(appearance.get(key, 0))
		if choice <= 0:
			continue
		var available: Array = (PART_VISUALS[part] as Array).duplicate()
		var preferred_visual: int = int(preferred.get(part, -1))
		if available.has(preferred_visual):
			available.erase(preferred_visual)
			available.push_front(preferred_visual)
		result[part] = int(available[posmod(choice - 1, available.size())])
	return result

static func culture_for_actor_type(actor_type: int) -> String:
	match actor_type:
		0, 1:
			return "luminous"
		2, 3:
			return "votary"
		4, 5:
			return "glasswarden"
		37, 38:
			return "orun"
		39, 40:
			return "greyhaven"
		41, 42:
			return "ssarathi"
		79, 80:
			return "stoneborn"
		81, 82:
			return "mycelari"
		_:
			return ""

static func skin_tint(index: int) -> Color:
	match posmod(index, 6):
		1:
			return Color(0.88, 0.78, 0.70)
		2:
			return Color(1.10, 1.02, 0.92)
		3:
			return Color(0.72, 0.84, 0.96)
		4:
			return Color(0.78, 0.96, 0.78)
		5:
			return Color(0.88, 0.76, 1.02)
		_:
			return Color.WHITE

static func hair_color(index: int) -> Color:
	var colors: Array[Color] = [
		Color(0.08, 0.06, 0.05), Color(0.24, 0.10, 0.04),
		Color(0.48, 0.25, 0.08), Color(0.82, 0.64, 0.26),
		Color(0.72, 0.16, 0.08), Color(0.62, 0.66, 0.72),
		Color(0.92, 0.92, 0.88), Color(0.18, 0.34, 0.62),
		Color(0.20, 0.52, 0.38), Color(0.48, 0.24, 0.62),
		Color(0.74, 0.30, 0.54), Color(0.10, 0.56, 0.62),
		Color(0.58, 0.42, 0.24), Color(0.32, 0.32, 0.34),
		Color(0.84, 0.46, 0.18), Color(0.36, 0.14, 0.08),
	]
	return colors[posmod(index, colors.size())]

static func eye_color(index: int) -> Color:
	var colors: Array[Color] = [
		Color(0.28, 0.55, 0.82), Color(0.24, 0.68, 0.42),
		Color(0.56, 0.32, 0.16), Color(0.82, 0.68, 0.22),
		Color(0.50, 0.30, 0.72), Color(0.20, 0.76, 0.78),
		Color(0.72, 0.18, 0.16), Color(0.76, 0.76, 0.80),
		Color(0.14, 0.20, 0.26), Color(0.90, 0.48, 0.16),
		Color(0.56, 0.78, 0.28), Color(0.82, 0.34, 0.64),
	]
	return colors[posmod(index, colors.size())]

static func hair_style(index: int) -> int:
	return posmod(index, 4)
