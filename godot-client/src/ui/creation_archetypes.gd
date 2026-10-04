class_name CreationArchetypes
extends RefCounted
## The four creation-screen callings.
##
## A calling chooses the server-owned starter inventory and gives the client a
## representative equipment silhouette.  It does not restrict skills or
## progression, and it is deliberately independent of race and sex.

const CLASSES: Array[Dictionary] = [
	{
		"id": 0,
		"key": "vanguard",
		"label": "Vanguard",
		"tagline": "Hold the line",
		"description": "A steady front-line adventurer equipped to meet danger face to face.",
		"starting_items": "Militia sword, round shield, guard cape and Studded Jack",
		"equipment_visuals": {0: 114, 1: 106, 2: 105, 5: 209},
	},
	{
		"id": 1,
		"key": "ranger",
		"label": "Ranger",
		"tagline": "Choose the distant path",
		"description": "A mobile hunter who reads the land and strikes before danger closes in.",
		"starting_items": "Amberwood longbow, 20 arrows and Scout Vest",
		"equipment_visuals": {0: 164, 4: 230, 5: 225, 6: 224},
	},
	{
		"id": 2,
		"key": "arcanist",
		"label": "Arcanist",
		"tagline": "Shape the unseen",
		"description": "A student of sigils and ether prepared to solve threats with careful magic.",
		"starting_items": "Arcane focus wand, Warded Tabard and 3 mana potions",
		"equipment_visuals": {0: 142, 4: 179, 5: 216, 6: 192},
	},
	{
		"id": 3,
		"key": "warden",
		"label": "Warden",
		"tagline": "Guard the old roads",
		"description": "A resilient trail-keeper who pairs practical arms with woodland craft.",
		"starting_items": "Fighting quarterstaff, leaf cape and Furtrim Coat",
		"equipment_visuals": {0: 163, 2: 100, 5: 189},
	},
]


static func count() -> int:
	return CLASSES.size()


static func at(index: int) -> Dictionary:
	if CLASSES.is_empty():
		return {}
	return CLASSES[posmod(index, CLASSES.size())].duplicate(true)


static func id_at(index: int) -> int:
	return int(at(index).get("id", 0))


static func loadout_at(index: int) -> Dictionary:
	return (at(index).get("equipment_visuals", {}) as Dictionary).duplicate()
