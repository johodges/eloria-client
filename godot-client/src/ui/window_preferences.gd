class_name WindowPreferences
extends RefCounted
## Remembered sizes for the windows a player is allowed to resize.
##
## The inventory and ground-bag panels already kept their scale in the HUD
## settings file, under their own sections. The floating windows had nowhere to
## put theirs, so every open reset them to the size they shipped at and a
## resize lasted only until the window was closed. Sizes recorded here go to
## the same file, so a window reopens at the size it was left in this session
## and in the next one.

const SETTINGS_PATH := "user://eloria_hud.cfg"
const SECTION := "windows"


static func stored_size(key: String, fallback: Vector2i) -> Vector2i:
	var config := ConfigFile.new()
	if config.load(SETTINGS_PATH) != OK:
		return fallback
	var value: Variant = config.get_value(SECTION, key + "_size", fallback)
	if value is Vector2i:
		return value as Vector2i
	# ConfigFile round-trips a Vector2i faithfully, but a settings file hand
	# edited into floats must not reset the window to its shipped size.
	if value is Vector2:
		return Vector2i(value as Vector2)
	return fallback


static func store_size(key: String, size: Vector2i) -> void:
	var config := ConfigFile.new()
	# Loaded first so writing one window's size keeps every other setting the
	# HUD holds in this file.
	config.load(SETTINGS_PATH)
	config.set_value(SECTION, key + "_size", size)
	var error: Error = config.save(SETTINGS_PATH)
	if error != OK:
		push_warning("Window size save failed: " + error_string(error))
