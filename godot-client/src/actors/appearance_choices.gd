class_name AppearanceChoices
extends RefCounted

# Display order is independent of the persistent appearance byte.
static func options(category: String, culture := "luminous", part := 0) -> Array[Dictionary]:
	var names: Array = []
	var order: Array = []
	var colors: Array[Color] = []
	match category:
		"hair":
			names = ["Bald", "Parted", "Long", "Buns", "Buzzcut"]
			order = [0, 4, 1, 2, 3]
		"skin":
			names = ["Natural", "Pale", "Golden", "Tan", "Deep brown", "Ebony", "Frost blue", "Moss green", "Dusk violet", "Stone grey"]
			order = [1, 0, 2, 3, 4, 5, 9, 7, 6, 8]
			for id: int in range(names.size()):
				colors.append(AppearanceVariants.skin_tint(id))
		"eyes":
			names = ["Blue", "Green", "Brown", "Amber", "Violet", "Teal", "Red", "Silver", "Slate", "Orange", "Lime", "Pink"]
			order = [7, 8, 2, 3, 9, 6, 10, 1, 5, 0, 4, 11]
			for id: int in range(names.size()):
				colors.append(AppearanceVariants.eye_color(id))
		"hair_color":
			names = ["Black", "Dark brown", "Brown", "Blond", "Red", "Silver", "White", "Blue", "Green", "Violet", "Rose", "Teal", "Sandy brown", "Charcoal", "Copper", "Auburn", "Pink", "Jade", "Pale gold", "Midnight blue"]
			order = [6, 5, 13, 0, 18, 3, 12, 2, 1, 14, 15, 4, 17, 8, 11, 7, 19, 9, 16, 10]
			for id: int in range(names.size()):
				colors.append(AppearanceVariants.hair_color(id))
		"wardrobe":
			names = ["Traditional", "Light traditional", "Dark traditional", "Accent", "Crimson", "Forest", "Navy", "Gold", "Plum", "Rust", "Ivory", "Charcoal"]
			order = range(names.size())
			for id: int in order:
				colors.append(AppearanceVariants.wardrobe_color(culture, part, id))
	var result: Array[Dictionary] = []
	for id: int in order:
		var entry: Dictionary = {"id": id, "label": names[id]}
		if not colors.is_empty():
			var color := colors[id]
			# The culture palette can repeat a common dye (e.g. Greyhaven ivory).
			# Keep the original ID as the representative so the default stays valid.
			var threshold := 0.075 if category == "wardrobe" else 0.001
			if result.any(func(row: Dictionary) -> bool:
				var previous: Color = row.color
				return Vector3(color.r - previous.r, color.g - previous.g, color.b - previous.b).length() < threshold):
				continue
			entry["color"] = color
		result.append(entry)
	if category == "wardrobe":
		result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			var ca: Color = a.color
			var cb: Color = b.color
			var family_a := -1 if ca.s < 0.16 else int(ca.h * 12.0)
			var family_b := -1 if cb.s < 0.16 else int(cb.h * 12.0)
			return ca.v > cb.v if family_a == family_b else family_a < family_b)
	return result

static func populate(control: OptionButton, choices: Array[Dictionary]) -> void:
	var previous := control.get_selected_id() if control.item_count > 0 else 0
	control.clear()
	for entry: Dictionary in choices:
		if entry.has("color"):
			var swatch := Image.create(16, 16, false, Image.FORMAT_RGBA8)
			swatch.fill(entry.color)
			control.add_icon_item(ImageTexture.create_from_image(swatch), entry.label, entry.id)
		else:
			control.add_item(entry.label, entry.id)
	var selected := control.get_item_index(previous)
	control.select(selected if selected >= 0 else control.get_item_index(0))
