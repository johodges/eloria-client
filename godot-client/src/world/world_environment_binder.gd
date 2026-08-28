class_name WorldEnvironmentBinder
extends RefCounted
## Applies a map manifest's `environment` block to the scene's WorldEnvironment
## and sun.
##
## Without this a region loads under the client's generic placeholder
## environment - a flat background colour, cool ambient and no sky or fog -
## which cannot present a region whose art direction is warm daylight over
## open grassland. Maps that declare no `environment` block keep exactly the
## behaviour they had before, so this is additive.

const DEFAULT_SUN_ROTATION := Vector3(-55.0, -30.0, 0.0)
const DEFAULT_SUN_ENERGY := 1.15

static func apply(manifest: WorldManifest, world_environment: WorldEnvironment,
		sun: DirectionalLight3D) -> bool:
	if manifest == null or world_environment == null:
		return false
	var raw: Variant = manifest.data.get("environment")
	if raw is not Dictionary:
		_restore_defaults(sun)
		return false
	var declared: Dictionary = raw as Dictionary
	var environment: Environment = Environment.new()

	var sky_value: Variant = declared.get("sky")
	if sky_value is Dictionary:
		var declared_sky: Dictionary = sky_value as Dictionary
		var material: ProceduralSkyMaterial = ProceduralSkyMaterial.new()
		material.sky_top_color = _color(declared_sky.get("topColor"), Color("3d7ec2"))
		material.sky_horizon_color = _color(declared_sky.get("horizonColor"),
			Color("bcc9cd"))
		material.sky_curve = float(declared_sky.get("curve", 0.15))
		material.ground_bottom_color = _color(declared_sky.get("groundBottomColor"),
			Color("6d5c40"))
		material.ground_horizon_color = _color(declared_sky.get("groundHorizonColor"),
			Color("b3a07c"))
		material.sun_angle_max = float(declared_sky.get("sunAngleMax", 12.0))
		material.energy_multiplier = float(declared_sky.get("energy", 1.0))
		var sky: Sky = Sky.new()
		sky.sky_material = material
		environment.sky = sky
		environment.background_mode = Environment.BG_SKY
		environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	else:
		environment.background_mode = Environment.BG_COLOR
		environment.background_color = _color(declared.get("backgroundColor"),
			Color(0.10, 0.15, 0.21))
		environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR

	var ambient_value: Variant = declared.get("ambient")
	if ambient_value is Dictionary:
		var ambient: Dictionary = ambient_value as Dictionary
		if ambient.has("color"):
			# Keep the sky as a source and let skyContribution blend it against
			# the declared colour, so a warm ground bounce can temper a blue sky
			# rather than replacing it.
			environment.ambient_light_color = _color(ambient.get("color"), Color.WHITE)
			if environment.background_mode != Environment.BG_SKY:
				environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		environment.ambient_light_energy = float(ambient.get("energy", 0.85))
		environment.ambient_light_sky_contribution = float(
			ambient.get("skyContribution", 1.0))

	var fog_value: Variant = declared.get("fog")
	if fog_value is Dictionary:
		var fog: Dictionary = fog_value as Dictionary
		environment.fog_enabled = bool(fog.get("enabled", true))
		environment.fog_light_color = _color(fog.get("color"), Color("d8c9a4"))
		environment.fog_density = float(fog.get("density", 0.0016))
		environment.fog_sky_affect = float(fog.get("skyAffect", 0.4))
		environment.fog_aerial_perspective = float(fog.get("aerialPerspective", 0.0))

	var tonemap_value: Variant = declared.get("tonemap")
	if tonemap_value is Dictionary:
		var tonemap: Dictionary = tonemap_value as Dictionary
		environment.tonemap_mode = _tonemap_mode(str(tonemap.get("mode", "filmic")))
		environment.tonemap_exposure = float(tonemap.get("exposure", 1.0))
		environment.tonemap_white = float(tonemap.get("white", 1.0))

	world_environment.environment = environment

	var sun_value: Variant = declared.get("sun")
	if sun_value is Dictionary and sun != null:
		var declared_sun: Dictionary = sun_value as Dictionary
		var rotation: Variant = declared_sun.get("rotationDegrees")
		if rotation is Array and (rotation as Array).size() >= 3:
			var values: Array = rotation as Array
			sun.rotation_degrees = Vector3(float(values[0]), float(values[1]),
				float(values[2]))
		sun.light_color = _color(declared_sun.get("color"), Color.WHITE)
		sun.light_energy = float(declared_sun.get("energy", DEFAULT_SUN_ENERGY))
		sun.light_indirect_energy = float(declared_sun.get("indirectEnergy", 1.0))
		sun.shadow_enabled = bool(declared_sun.get("shadows", true))
	elif sun != null:
		_restore_defaults(sun)
	return true

static func _restore_defaults(sun: DirectionalLight3D) -> void:
	if sun == null:
		return
	sun.rotation_degrees = DEFAULT_SUN_ROTATION
	sun.light_color = Color.WHITE
	sun.light_energy = DEFAULT_SUN_ENERGY
	sun.light_indirect_energy = 1.0

static func _color(value: Variant, fallback: Color) -> Color:
	if value is Array:
		var values: Array = value as Array
		if values.size() >= 3:
			return Color(float(values[0]), float(values[1]), float(values[2]),
				float(values[3]) if values.size() > 3 else 1.0)
	elif value is String:
		return Color(str(value))
	return fallback

static func _tonemap_mode(name: String) -> int:
	match name.to_lower():
		"linear":
			return Environment.TONE_MAPPER_LINEAR
		"reinhard":
			return Environment.TONE_MAPPER_REINHARDT
		"aces":
			return Environment.TONE_MAPPER_ACES
		_:
			return Environment.TONE_MAPPER_FILMIC
