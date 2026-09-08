extends SceneTree
## Exercise every playable skin/eye combination on actual imported actors.

var checks := 0
var failures := 0

func _init() -> void:
	call_deferred("run")

func expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func run() -> void:
	var models: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/models.json"))["models"]
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/equipment.json"))
	var variants := 0
	for slug: String in models:
		var config: Dictionary = models[slug]
		if not config.has("bodyTemplate"):
			continue
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var errors := actor.configure({"actor_id": 989, "x": 0, "y": 0, "rotation": 0, "kind": 1, "name": "", "appearance": {}, "equipment_visuals": {}}, CoordinateAdapter.new({"walkingHeight": 0.0}), config, JSON.parse_string(FileAccess.get_file_as_string(config["animationMap"])), equipment)
		expect(errors.is_empty(), slug + " configures")
		actor.set_process(false)
		actor.set_physics_process(false)
		var body := actor.find_child("body", true, false) as MeshInstance3D
		var source := body.mesh.surface_get_material(1) as StandardMaterial3D
		var original_color := source.albedo_color
		var original_texture := source.albedo_texture
		var face := body.get_active_material(1) as ShaderMaterial
		expect(face != null, slug + " uses face mask")
		if face == null:
			actor.free()
			continue
		expect(face.get_shader_parameter("base_texture") == original_texture, slug + " retains source head atlas")
		expect(face.get_shader_parameter("region_texture") is Texture2D, slug + " mask loads")
		for skin in range(10):
			for eyes in range(12):
				actor.apply_appearance_variants({"skin": skin, "eyes": eyes, "hair": 0})
				expect(face.get_shader_parameter("skin_tint") == AppearanceVariants.skin_tint(skin), slug + " skin selection")
				expect(face.get_shader_parameter("eye_tint") == AppearanceVariants.eye_color(eyes), slug + " eye selection")
				for part: String in ["eyes", "eyebrows", "scalp"]:
					var mesh := actor.find_child(part, true, false) as MeshInstance3D
					if mesh != null:
						expect(mesh.get_active_material(0) == face, slug + " " + part + " shares continuous skin/eye mapping")
				var trunk := body.get_active_material(0) as StandardMaterial3D
				var trunk_source := body.mesh.surface_get_material(0) as StandardMaterial3D
				expect(trunk.albedo_color.is_equal_approx(trunk_source.albedo_color * AppearanceVariants.skin_tint(skin)), slug + " body tint does not accumulate")
		actor.apply_appearance_variants({"skin": 0, "eyes": 0, "hair": 0})
		for hair in range(10):
			actor.apply_appearance_variants({"skin": 0, "eyes": 0, "hair": hair})
			expect(face.get_shader_parameter("hair_tint") == AppearanceVariants.hair_color(hair), slug + " eyebrow colour follows hair selection")
		actor.apply_appearance_variants({"skin": 0, "eyes": 0, "hair": 0})
		expect(face.get_shader_parameter("skin_tint") == Color.WHITE, slug + " scalp returns to original tone")
		expect(source.albedo_color == original_color and source.albedo_texture == original_texture, slug + " shared source material remains immutable")
		actor.apply_equipment_visuals({3: 133})
		actor.apply_equipment_visuals({})
		expect(body.get_active_material(1) == face, slug + " helmet cycle retains face material")
		actor.apply_equipment_visuals({0: 114, 5: 208, 6: 248})
		actor.apply_appearance_variants({"skin": 3, "eyes": 4, "hair": 0})
		expect(body.get_active_material(1) == face, slug + " armour and dye retain face material")
		actor.apply_equipment_visuals({})
		expect(body.get_active_material(1) == face, slug + " armour removal retains face material")
		if config["faceAppearance"].has("neckTexture"):
			var neck := body.get_active_material(2) as StandardMaterial3D
			expect(neck.albedo_texture.resource_path == config["faceAppearance"]["neckTexture"], slug + " neck texture survives equipment and dye")
		actor.free()
		await process_frame
		variants += 1
		print("FACE_MAPPING ", slug, " complete")
	# Independent regression for the single-surface tint path used by legacy
	# actors: returning to a colour must not multiply the old override again.
	var legacy := ReplicatedActor3D.new()
	var mesh := MeshInstance3D.new()
	var sphere := SphereMesh.new()
	var source := StandardMaterial3D.new()
	source.albedo_color = Color(0.8, 0.7, 0.6)
	sphere.material = source
	mesh.mesh = sphere
	for i in range(10):
		legacy._tint_mesh(mesh, Color(0.3, 0.4, 0.5))
		legacy._tint_mesh(mesh, Color.WHITE)
		expect((mesh.get_active_material(0) as StandardMaterial3D).albedo_color.is_equal_approx(source.albedo_color), "single surface restores authored tone")
	mesh.free()
	legacy.free()
	expect(variants == 16, "all sixteen playable variants")
	print("FACE_MAPPING: %d variants, 1920 skin/eye combinations, %d checks, %d failures" % [variants, checks, failures])
	NativeAnimationImporter.clear()
	quit(1 if failures else 0)
