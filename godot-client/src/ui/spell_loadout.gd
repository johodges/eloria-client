extends RefCounted
## Local preferences only: the server still decides eligibility and cost.
signal changed
const SLOT_COUNT := 12
var catalog: SpellCatalog
var slots: Array[Dictionary] = []
var powers: Dictionary = {}
var mode := "prepared"
var profile := ""
var path := "user://magic_loadouts.cfg"

func configure(value: SpellCatalog) -> void:
	catalog = value
	_reset()

func _reset() -> void:
	slots.clear()
	powers.clear()
	for index in range(SLOT_COUNT):
		var id := catalog.default_quick_slots[index] if index < catalog.default_quick_slots.size() else -1
		slots.append({"id": id, "power": 1})

func load_profile(key: String) -> void:
	profile = key.sha256_text()
	_reset()
	var config := ConfigFile.new()
	if config.load(path) == OK:
		var saved: Variant = config.get_value(profile, "slots", [])
		if saved is Array:
			for index in range(mini(saved.size(), SLOT_COUNT)):
				if saved[index] is Dictionary:
					var id := int(saved[index].get("id", -1))
					if id == -1 or id in catalog.spell_ids():
						slots[index] = {"id": id, "power": clampi(int(saved[index].get("power", 1)), 1, 10)}
		var saved_powers: Variant = config.get_value(profile, "powers", {})
		if saved_powers is Dictionary:
			for id in catalog.spell_ids():
				powers[id] = clampi(int(saved_powers.get(id, 1)), 1, 10)
	changed.emit()

func assign_slot(index: int, spell_id: int, power: int) -> void:
	if index < 0 or index >= SLOT_COUNT or (spell_id != -1 and spell_id not in catalog.spell_ids()):
		return
	slots[index] = {"id": spell_id, "power": clampi(power, 1, 10)}
	_save()
	changed.emit()

func power_for(spell_id: int) -> int:
	return int(powers.get(spell_id, 1))

func remember_power(spell_id: int, power: int) -> void:
	powers[spell_id] = clampi(power, 1, 10)
	_save()
	changed.emit()

func set_mode(value: String) -> void:
	mode = value if value in ["prepared", "aimed", "wheel"] else "prepared"
	changed.emit()

func targeting_mode() -> String:
	return "aimed" if mode == "aimed" else "prepared"

func _save() -> void:
	if profile.is_empty(): return
	var config := ConfigFile.new()
	config.load(path)
	config.set_value(profile, "slots", slots)
	config.set_value(profile, "powers", powers)
	var error := config.save(path)
	if error != OK:
		push_warning("Could not save spell loadout: " + error_string(error))
