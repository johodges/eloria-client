class_name ManufacturingCatalog
extends RefCounted

var _recipes: Array[Dictionary] = []

func configure(config: Dictionary) -> void:
	_recipes.clear()
	var recipes_value: Variant = config.get("recipes", [])
	if not recipes_value is Array:
		return
	for recipe_value: Variant in recipes_value as Array:
		if recipe_value is Dictionary:
			_recipes.append((recipe_value as Dictionary).duplicate(true))

func count() -> int:
	return _recipes.size()

func recipe(index: int) -> Dictionary:
	if index < 0 or index >= _recipes.size():
		return {}
	return _recipes[index]

func availability(index: int, inventory: Dictionary, known_knowledge: Array[int],
		stats: Dictionary) -> Dictionary:
	var definition: Dictionary = recipe(index)
	if definition.is_empty():
		return {"selection": [], "reasons": ["Unknown recipe"]}
	var selection: Array[Dictionary] = []
	var reasons: Array[String] = []
	var ingredients_value: Variant = definition.get("ingredients", [])
	if ingredients_value is Array:
		for ingredient_value: Variant in ingredients_value as Array:
			if not ingredient_value is Dictionary:
				continue
			var ingredient: Dictionary = ingredient_value as Dictionary
			var name: String = str(ingredient.get("name", "ingredient"))
			if bool(ingredient.get("ambiguousImage", false)):
				reasons.append("%s shares legacy artwork; automatic selection is unavailable" % name)
				continue
			var required: int = maxi(1, int(ingredient.get("quantity", 1)))
			var slot: int = _inventory_slot_for_image(inventory,
				int(ingredient.get("imageId", -1)), required, false)
			if slot < 0:
				reasons.append("Missing %s ×%d" % [name, required])
			else:
				selection.append({"slot": slot, "quantity": required})
	var tools_value: Variant = definition.get("tools", [])
	if tools_value is Array:
		for tool_value: Variant in tools_value as Array:
			if not tool_value is Dictionary:
				continue
			var tool: Dictionary = tool_value as Dictionary
			var tool_name: String = str(tool.get("name", "tool"))
			if bool(tool.get("ambiguousImage", false)):
				reasons.append("%s shares legacy artwork; tool identity is uncertain" % tool_name)
				continue
			if _inventory_slot_for_image(inventory, int(tool.get("imageId", -1)), 1, true) < 0:
				reasons.append("Required tool: %s" % tool_name)
	var knowledge_index: int = int(definition.get("knowledgeIndex", -1))
	if knowledge_index >= 0 and not known_knowledge.has(knowledge_index):
		reasons.append("Unread knowledge: %s" % str(definition.get("knowledge", "required book")))
	if stats.is_empty():
		reasons.append("Waiting for server statistics")
	else:
		if int(stats.get("food", 0)) <= 0:
			reasons.append("Food must be above zero")
		var mana: int = int(definition.get("mana", 0))
		if int(stats.get("ether", 0)) < mana:
			reasons.append("Need %d ethereal points" % mana)
	return {"selection": selection, "reasons": reasons}

func _inventory_slot_for_image(inventory: Dictionary, image_id: int, quantity: int,
		include_equipment: bool) -> int:
	var slots: Array = inventory.keys()
	slots.sort()
	for slot_value: Variant in slots:
		var slot: int = int(slot_value)
		if slot < 0 or slot >= (44 if include_equipment else 36):
			continue
		var item_value: Variant = inventory.get(slot)
		if not item_value is Dictionary:
			continue
		var item: Dictionary = item_value as Dictionary
		if int(item.get("image_id", -1)) == image_id and int(item.get("quantity", 0)) >= quantity:
			return slot
	return -1
