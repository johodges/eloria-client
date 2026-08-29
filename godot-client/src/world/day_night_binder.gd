class_name DayNightBinder
extends RefCounted
## Drives the environment from the server's game clock.
##
## `NEW_MINUTE(5)` has always arrived and only ever moved the clock face and the
## compass: the sun, the ambient light and the fog came from the map manifest
## and never changed, so every map was permanently at whatever hour it was
## authored for.
##
## The daylight curve is the server's own, not one invented here. `World`
## computes `daylight = (1 - cos(2*PI*minute/360)) / 2` to decide how far a
## creature can see, with minute 180 the brightest point and minute 0 the
## darkest; this uses exactly that expression, so what the player sees and what
## the server acts on cannot drift apart.
##
## The manifest stays the reference: what a package declares is full daylight,
## and this dims and warms it towards night. A package can opt out with
## `environment.dayNight: {"enabled": false}`, and an interior that declares no
## sun is left alone - its lamps are its whole lighting and dimming them by the
## hour outside would be wrong.

const MINUTES_PER_DAY := 360.0
## How far the sun's key light falls at midnight, as a fraction of noon. At
## 0.06 the moon lit nothing and the world read as flat shapes in the dark;
## this leaves enough of a key for surfaces to keep their form.
const NIGHT_SUN_ENERGY := 0.18
## Ambient never reaches zero: a pitch-black world is unplayable and the
## legacy client never went there either. 0.22 was still too near it to play
## in - the ground, the walls and the actors all fell into one silhouette.
const NIGHT_AMBIENT_ENERGY := 0.42
const NIGHT_SUN_COLOUR := Color(0.46, 0.56, 0.82)
const DAWN_SUN_COLOUR := Color(1.0, 0.72, 0.46)
## The night sky and fog are lifted with the rest: they are most of what the
## far half of an outdoor scene is made of, so leaving them near black would
## undo the ambient the ground just gained.
const NIGHT_SKY_TOP := Color(0.09, 0.12, 0.22)
const NIGHT_SKY_HORIZON := Color(0.19, 0.23, 0.34)
const NIGHT_FOG := Color(0.16, 0.20, 0.29)
## The sun's arc, in degrees of elevation at noon and below the horizon at
## midnight.
const NOON_ELEVATION := -62.0
const MIDNIGHT_ELEVATION := 12.0

## The server's own daylight curve, for a continuous minute.
static func daylight(minute: float) -> float:
	return (1.0 - cos(TAU * minute / MINUTES_PER_DAY)) * 0.5

## How much of the light is dawn or dusk rather than noon or midnight. Peaks
## where the daylight curve is changing fastest, which is sunrise and sunset.
static func twilight(minute: float) -> float:
	return absf(sin(TAU * minute / MINUTES_PER_DAY))

## True when the package wants the hour to drive its environment at all.
static func drives(manifest: WorldManifest) -> bool:
	if manifest == null:
		return false
	var environment: Variant = manifest.data.get("environment")
	if environment is not Dictionary:
		return false
	var declared: Dictionary = environment as Dictionary
	var settings: Variant = declared.get("dayNight")
	if settings is Dictionary and not bool(
			(settings as Dictionary).get("enabled", true)):
		return false
	# An interior declares no sun, or declares it disabled. Its lamps are its
	# lighting; the hour outside does not reach them.
	var sun: Variant = declared.get("sun")
	if sun is not Dictionary:
		return false
	return bool((sun as Dictionary).get("enabled", true))

## Applies the hour to an environment already bound from the manifest. The
## manifest values are read back as the noon reference, so this can run
## repeatedly without drifting.
static func apply(manifest: WorldManifest, world_environment: WorldEnvironment,
		sun: DirectionalLight3D, minute: float) -> bool:
	if not drives(manifest) or world_environment == null or sun == null:
		return false
	var environment: Environment = world_environment.environment
	if environment == null:
		return false
	var declared: Dictionary = manifest.data.get("environment", {}) as Dictionary
	var light: float = daylight(minute)
	var edge: float = twilight(minute)

	var declared_sun: Dictionary = declared.get("sun", {}) as Dictionary
	var noon_energy: float = float(declared_sun.get("energy", 1.0))
	var noon_colour: Color = _colour(declared_sun.get("color"), Color.WHITE)
	sun.light_energy = lerpf(noon_energy * NIGHT_SUN_ENERGY, noon_energy, light)
	sun.light_color = noon_colour.lerp(NIGHT_SUN_COLOUR, 1.0 - light) \
		.lerp(DAWN_SUN_COLOUR, edge * 0.55)
	sun.rotation_degrees.x = lerpf(MIDNIGHT_ELEVATION, NOON_ELEVATION, light)
	# The key light stops casting once it is below the horizon; a shadow from
	# a sun that has set is the giveaway that nothing is really moving.
	sun.shadow_enabled = bool(declared_sun.get("shadows", true)) and light > 0.08

	var declared_ambient: Dictionary = declared.get("ambient", {}) as Dictionary
	var noon_ambient: float = float(declared_ambient.get("energy", 0.85))
	environment.ambient_light_energy = lerpf(
		noon_ambient * NIGHT_AMBIENT_ENERGY, noon_ambient, light)

	var sky_material: Variant = environment.sky.sky_material if environment.sky != null else null
	if sky_material is ProceduralSkyMaterial:
		var declared_sky: Dictionary = declared.get("sky", {}) as Dictionary
		var material: ProceduralSkyMaterial = sky_material as ProceduralSkyMaterial
		material.sky_top_color = _colour(
			_either(declared_sky, "topColor", "zenith"), Color("3d7ec2")
			).lerp(NIGHT_SKY_TOP, 1.0 - light)
		material.sky_horizon_color = _colour(
			_either(declared_sky, "horizonColor", "horizon"), Color("bcc9cd")
			).lerp(NIGHT_SKY_HORIZON, 1.0 - light).lerp(DAWN_SUN_COLOUR, edge * 0.35)

	if environment.fog_enabled:
		var declared_fog: Dictionary = declared.get("fog", {}) as Dictionary
		environment.fog_light_color = _colour(declared_fog.get("color"),
			Color("d8c9a4")).lerp(NIGHT_FOG, 1.0 - light)
	return true

static func _either(source: Dictionary, first: String, second: String) -> Variant:
	return source.get(first, source.get(second))

static func _colour(value: Variant, fallback: Color) -> Color:
	if value is String:
		return Color(value as String)
	if value is Array and (value as Array).size() >= 3:
		var channels: Array = value as Array
		return Color(float(channels[0]), float(channels[1]), float(channels[2]),
			float(channels[3]) if channels.size() > 3 else 1.0)
	return fallback
