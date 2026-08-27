class_name SpellCatalog
extends RefCounted

var default_quick_slots: Array[int] = []
var _spells: Dictionary = {}
var _atlas_path := ""
var _atlas_texture: Texture2D
var _columns := 8
var _cell_size := Vector2(64.0, 64.0)

func configure(config: Dictionary) -> void:
	default_quick_slots.clear()
	_spells.clear()
	_atlas_texture = null
	_atlas_path = str(config.get("atlas", ""))
	_columns = maxi(1, int(config.get("columns", 8)))
	var cell_value: Variant = config.get("cellSize", [64, 64])
	if cell_value is Array:
		var cell_values: Array = cell_value as Array
		if cell_values.size() >= 2:
			_cell_size = Vector2(float(cell_values[0]), float(cell_values[1]))
	var default_value: Variant = config.get("defaultQuickSlots", [])
	if default_value is Array:
		for raw_id: Variant in default_value:
			default_quick_slots.append(int(raw_id))
	var spells_value: Variant = config.get("spells", [])
	if spells_value is Array:
		for raw_spell: Variant in spells_value:
			if raw_spell is Dictionary:
				var spell: Dictionary = raw_spell as Dictionary
				_spells[int(spell.get("id", -1))] = spell

func spell(spell_id: int) -> Dictionary:
	var value: Variant = _spells.get(spell_id)
	return value as Dictionary if value is Dictionary else {}

func icon_for(spell_id: int) -> Texture2D:
	var definition: Dictionary = spell(spell_id)
	if definition.is_empty():
		return null
	if _atlas_texture == null:
		var resource: Resource = load(_atlas_path)
		if not resource is Texture2D:
			return null
		_atlas_texture = resource as Texture2D
	var icon_id: int = int(definition.get("icon", -1))
	if icon_id < 0:
		return null
	var atlas_texture: AtlasTexture = AtlasTexture.new()
	atlas_texture.atlas = _atlas_texture
	atlas_texture.region = Rect2(float(icon_id % _columns) * _cell_size.x,
		float(floori(float(icon_id) / float(_columns))) * _cell_size.y,
		_cell_size.x, _cell_size.y)
	return atlas_texture

func unavailable_reasons(spell_id: int, owned_sigils: Array[int], stats: Dictionary,
		inventory: Dictionary) -> Array[String]:
	var definition: Dictionary = spell(spell_id)
	if definition.is_empty():
		return ["Unknown spell"]
	var reasons: Array[String] = []
	var missing_sigils: Array[String] = []
	var sigils_value: Variant = definition.get("sigils", [])
	if sigils_value is Array:
		for raw_sigil: Variant in sigils_value:
			var sigil_id: int = int(raw_sigil)
			if not owned_sigils.has(sigil_id):
				missing_sigils.append(str(sigil_id))
	if not missing_sigils.is_empty():
		reasons.append("Missing sigils: " + ", ".join(missing_sigils))
	var required_level: int = int(definition.get("level", 0))
	var current_level: int = int(stats.get("magic", 0))
	if current_level < required_level:
		reasons.append("Requires Magic %d (current %d)" % [required_level, current_level])
	var required_mana: int = int(definition.get("mana", 0))
	var current_mana: int = int(stats.get("ether", 0))
	if current_mana < required_mana:
		reasons.append("Requires %d mana (current %d)" % [required_mana, current_mana])
	var reagents_value: Variant = definition.get("reagents", [])
	if reagents_value is Array:
		for raw_reagent: Variant in reagents_value:
			if not raw_reagent is Dictionary:
				continue
			var reagent: Dictionary = raw_reagent as Dictionary
			var image_id: int = int(reagent.get("image_id", -1))
			var required_quantity: int = int(reagent.get("quantity", 0))
			var available_quantity: int = inventory_quantity(image_id, inventory)
			if available_quantity < required_quantity:
				reasons.append("Requires reagent #%d ×%d (have %d)" % [
					image_id, required_quantity, available_quantity])
	return reasons

func inventory_quantity(image_id: int, inventory: Dictionary) -> int:
	var total := 0
	for raw_slot: Variant in inventory:
		if int(raw_slot) >= 36:
			continue
		var raw_item: Variant = inventory[raw_slot]
		if raw_item is Dictionary:
			var item: Dictionary = raw_item as Dictionary
			if int(item.get("image_id", -1)) == image_id:
				total += int(item.get("quantity", 0))
	return total
