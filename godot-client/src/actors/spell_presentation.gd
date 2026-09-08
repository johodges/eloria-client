class_name SpellPresentation
extends RefCounted
## Effect ids mirror eloria/world.py effect_by_spell. Harvest effects 14/17
## deliberately have no casting action. Unknown effects stay generic.
const EFFECT_ACTIONS := {0: &"cast_aggressive", 1: &"heal", 2: &"cast_aggressive",
	3: &"cast_defensive", 4: &"heal", 5: &"cast_aggressive",
	6: &"cast_defensive", 9: &"heal", 10: &"cast_aggressive", 12: &"heal",
	72: &"cast_defensive", 73: &"cast_aggressive", 74: &"cast_defensive"}
static var _spells: Dictionary = {}

static func action_for_effect(effect: int) -> StringName:
	return EFFECT_ACTIONS.get(effect, &"")

static func action_for_spell(spell_id: int) -> StringName:
	if _spells.is_empty():
		var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/spells/catalog.json"))
		for spell: Dictionary in catalog.get("spells", []):
			_spells[int(spell.id)] = str(spell.get("effect", ""))
	var effect: String = _spells.get(spell_id, "")
	if effect in ["heal", "remote_heal", "restoration", "heal_summoned", "group_heal"]:
		return &"heal"
	if effect in ["harm", "poison", "life_drain", "mana_drain", "smite_summoned"]:
		return &"cast_aggressive"
	return &"cast_defensive"
