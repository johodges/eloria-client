class_name WorldEnvironmentApplier
extends RefCounted

## Applies the `environment` block of a world manifest to a WorldEnvironment and
## its key light, so a map ships with the sky, sun, fog and tonemapping it was
## art-directed for instead of relying on scene defaults.

static func _colour(value: Variant, fallback: Color) -> Color:
	if value is Array and (value as Array).size() >= 3:
		var parts: Array = value as Array
		return Color(float(parts[0]), float(parts[1]), float(parts[2]))
	return fallback

static func _vector(value: Variant, fallback: Vector3) -> Vector3:
	if value is Array and (value as Array).size() >= 3:
		var parts: Array = value as Array
		return Vector3(float(parts[0]), float(parts[1]), float(parts[2]))
	return fallback

static func apply(manifest: WorldManifest, world_environment: WorldEnvironment,
		sun: DirectionalLight3D) -> bool:
	if manifest == null or world_environment == null:
		return false
	var block_value: Variant = manifest.data.get("environment", {})
	if not block_value is Dictionary:
		return false
	var block: Dictionary = block_value as Dictionary
	if block.is_empty():
		return false

	var environment: Environment = world_environment.environment
	if environment == null:
		environment = Environment.new()
		world_environment.environment = environment

	var sky_value: Variant = block.get("sky", {})
	if sky_value is Dictionary and not (sky_value as Dictionary).is_empty():
		var sky_block: Dictionary = sky_value as Dictionary
		var material := ProceduralSkyMaterial.new()
		material.sky_top_color = _colour(sky_block.get("zenith"), Color(0.32, 0.55, 0.79))
		material.sky_horizon_color = _colour(sky_block.get("horizon"), Color(0.71, 0.81, 0.88))
		material.ground_bottom_color = _colour(
			sky_block.get("groundBottom"), Color(0.28, 0.27, 0.24))
		material.ground_horizon_color = _colour(
			sky_block.get("groundHorizon"), Color(0.51, 0.51, 0.46))
		material.sun_angle_max = float(sky_block.get("sunAngleMaxDegrees", 12.0))
		var sky := Sky.new()
		sky.sky_material = material
		environment.sky = sky
		environment.background_mode = Environment.BG_SKY
		environment.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	else:
		environment.background_mode = Environment.BG_COLOR

	var ambient_value: Variant = block.get("ambient", {})
	if ambient_value is Dictionary:
		var ambient: Dictionary = ambient_value as Dictionary
		if ambient.has("color"):
			environment.ambient_light_color = _colour(
				ambient.get("color"), Color(0.71, 0.77, 0.83))
			environment.ambient_light_sky_contribution = float(
				ambient.get("skyContribution", 0.75))
		if ambient.has("energy"):
			environment.ambient_light_energy = float(ambient.get("energy", 0.4))

	var fog_value: Variant = block.get("fog", {})
	if fog_value is Dictionary and bool((fog_value as Dictionary).get("enabled", false)):
		var fog: Dictionary = fog_value as Dictionary
		environment.fog_enabled = true
		environment.fog_light_color = _colour(fog.get("color"), Color(0.74, 0.82, 0.88))
		environment.fog_density = float(fog.get("density", 0.0015))
		environment.fog_sky_affect = float(fog.get("skyAffect", 0.25))
		environment.fog_aerial_perspective = float(fog.get("aerialPerspective", 0.3))
	else:
		environment.fog_enabled = false

	var tonemap_value: Variant = block.get("tonemap", {})
	if tonemap_value is Dictionary:
		var tonemap: Dictionary = tonemap_value as Dictionary
		match str(tonemap.get("mode", "filmic")):
			"linear": environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
			"reinhard": environment.tonemap_mode = Environment.TONE_MAPPER_REINHARDT
			"aces": environment.tonemap_mode = Environment.TONE_MAPPER_ACES
			_: environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
		environment.tonemap_exposure = float(tonemap.get("exposure", 1.0))
		environment.tonemap_white = float(tonemap.get("whitePoint", 6.0))

	if sun != null:
		var sun_value: Variant = block.get("sun", {})
		if sun_value is Dictionary:
			var sun_block: Dictionary = sun_value as Dictionary
			var direction: Vector3 = _vector(
				sun_block.get("direction"), Vector3(-0.42, -0.76, 0.30)).normalized()
			if direction.length() > 0.0:
				sun.look_at_from_position(Vector3.ZERO, direction, Vector3.UP)
			sun.light_color = _colour(sun_block.get("color"), Color(1.0, 0.96, 0.89))
			sun.light_energy = float(sun_block.get("energy", 1.1))
			sun.light_angular_distance = float(
				sun_block.get("angularDiameterDegrees", 0.6))
			sun.shadow_enabled = bool(sun_block.get("shadows", true))
	return true
