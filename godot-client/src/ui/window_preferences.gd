class_name WindowPreferences
extends RefCounted
## Remembered sizes for the windows a player is allowed to resize.
##
## The inventory and ground-bag panels already kept their scale in the HUD
## settings file, under their own sections. The floating windows had nowhere to
## put theirs, so every open reset them to the size they shipped at and a
## resize lasted only until the window was closed. Scales recorded here go to
## the same file, so a window reopens at the size it was left in this session
## and in the next one.

const SETTINGS_PATH := "user://eloria_hud.cfg"
const SECTION := "windows"


static func stored_scale(key: String, fallback: float, minimum: float,
		maximum: float) -> float:
	var config := ConfigFile.new()
	if config.load(SETTINGS_PATH) != OK:
		return fallback
	# Clamped on the way in as well as on the way out: a settings file carried
	# over from a wider screen must not open a window larger than this one.
	return clampf(float(config.get_value(SECTION, key + "_scale", fallback)),
		minimum, maximum)


static func store_scale(key: String, scale: float) -> void:
	var config := ConfigFile.new()
	# Loaded first so writing one window's scale keeps every other setting the
	# HUD holds in this file.
	config.load(SETTINGS_PATH)
	config.set_value(SECTION, key + "_scale", scale)
	var error: Error = config.save(SETTINGS_PATH)
	if error != OK:
		push_warning("Window scale save failed: " + error_string(error))
