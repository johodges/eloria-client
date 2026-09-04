class_name AppearanceVariants
extends RefCounted

const PART_HEAD := 3
const PART_PANTS := 4
const PART_SHIRT := 5
const PART_BOOTS := 6

static func wardrobe_color(culture: String, part: int, index: int) -> Color:
	var palettes: Dictionary = {
		"luminous": {PART_SHIRT: Color8(42, 126, 142), PART_PANTS: Color8(42, 55, 72),
			PART_BOOTS: Color8(78, 55, 39), "accent": Color8(221, 190, 101)},
		"votary": {PART_SHIRT: Color8(113, 145, 164), PART_PANTS: Color8(76, 94, 108),
			PART_BOOTS: Color8(79, 91, 99), "accent": Color8(218, 232, 235)},
		"glasswarden": {PART_SHIRT: Color8(54, 48, 84), PART_PANTS: Color8(42, 44, 62),
			PART_BOOTS: Color8(83, 57, 39), "accent": Color8(187, 145, 63)},
		"orun": {PART_SHIRT: Color8(146, 76, 39), PART_PANTS: Color8(85, 64, 48),
			PART_BOOTS: Color8(82, 54, 35), "accent": Color8(49, 142, 145)},
		"greyhaven": {PART_SHIRT: Color8(225, 220, 202), PART_PANTS: Color8(41, 59, 75),
			PART_BOOTS: Color8(65, 49, 39), "accent": Color8(171, 137, 70)},
		"ssarathi": {PART_SHIRT: Color8(43, 112, 86), PART_PANTS: Color8(34, 76, 62),
			PART_BOOTS: Color8(71, 63, 42), "accent": Color8(189, 153, 67)},
		"stoneborn": {PART_SHIRT: Color8(91, 86, 80), PART_PANTS: Color8(65, 67, 68),
			PART_BOOTS: Color8(62, 55, 48), "accent": Color8(84, 189, 199)},
		"mycelari": {PART_SHIRT: Color8(88, 112, 70), PART_PANTS: Color8(62, 75, 53),
			PART_BOOTS: Color8(71, 54, 39), "accent": Color8(207, 143, 89)},
	}
	var palette: Dictionary = palettes.get(culture, palettes["luminous"]) as Dictionary
	var wardrobe_part: int = PART_SHIRT if part == PART_HEAD else part
	var base: Color = palette.get(wardrobe_part, Color.WHITE)
	var accent: Color = palette.get("accent", Color.WHITE)
	# The culture's own cloth first, then a shared dye rack: proper dyes
	# rather than shades of one colour, so a wardrobe reads chosen.
	var variants: Array[Color] = [
		base, base.lightened(0.18), base.darkened(0.22), accent,
		Color8(146, 42, 38),    # crimson
		Color8(46, 94, 52),     # forest
		Color8(38, 52, 96),     # navy
		Color8(196, 158, 62),   # gold
		Color8(96, 48, 104),    # plum
		Color8(148, 84, 38),    # rust
		Color8(222, 214, 196),  # ivory
		Color8(52, 52, 56),     # charcoal
	]
	return variants[posmod(index, variants.size())]

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
	# The base texture is a light tan, so these multiply into the real
	# tone: the first six run the realistic range from pale to deep, the
	# last four belong to Eloria.
	var tones: Array[Color] = [
		Color.WHITE,                    # 0 the authored tan
		Color(1.12, 1.04, 0.96),        # 1 pale
		Color(0.94, 0.80, 0.64),        # 2 golden
		Color(0.76, 0.56, 0.42),        # 3 tan brown
		Color(0.52, 0.36, 0.26),        # 4 deep brown
		Color(0.34, 0.24, 0.18),        # 5 near-black brown
		Color(0.62, 0.72, 0.86),        # 6 frost blue
		Color(0.58, 0.78, 0.56),        # 7 moss green
		Color(0.72, 0.58, 0.88),        # 8 dusk violet
		Color(0.58, 0.58, 0.62),        # 9 stone grey
	]
	return tones[posmod(index, tones.size())]

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
		Color(0.96, 0.78, 0.86), Color(0.14, 0.72, 0.52),
		Color(0.90, 0.86, 0.40), Color(0.06, 0.10, 0.22),
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

## 0 means bald (see ReplicatedActor3D._add_hair_variant); 1-4 select the
## race's own hairStyles[0..3], one bucket per entry.
static func hair_style(index: int) -> int:
	return posmod(index, 5)

static func head_style(index: int) -> int:
	return posmod(index, 4)
