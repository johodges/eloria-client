class_name ReplicatedActor3D
extends CharacterBody3D

@export var walk_presentation_speed := 6.0
@export var run_presentation_speed := 9.0
@export var turn_speed_radians := 12.0
@export var initial_server_interval := 0.25
@export var interval_smoothing := 0.5
@export var arrival_margin := 1.05
@export var minimum_segment_duration := 0.06
@export var maximum_segment_duration := 0.75

var actor_id := -1
var server_target := Vector3.ZERO
var resolver: AnimationResolver
var animation_player: AnimationPlayer
var current_action: StringName = &"idle"
var _snap_pending := true
var _target_yaw := 0.0
var _presentation_speed := 6.0
var _segment_start := Vector3.ZERO
var _segment_elapsed := 0.0
var _segment_duration := 0.0
var _last_movement_update_msec := -1
var _smoothed_server_interval := 0.25
var _facing_override_active := false
var _facing_override_yaw := 0.0
var _native_skeleton: Skeleton3D
var _attachment_bones: Dictionary = {}
var _model_config: Dictionary = {}
var _equipment_config: Dictionary = {}
var _equipment_visuals: Dictionary = {}
var _equipment_nodes: Dictionary = {}
var _equipment_hides: Dictionary = {}
var _hidden_body_surfaces: Dictionary = {}
var _nameplate: Label3D
var _settled := false

# Visual layer 2. The gameplay camera renders layers 1 and 2; the minimap and
# full-map cameras render layers 1 and 3.
const GAMEPLAY_ONLY_VISUAL_LAYER := 2
const SETTLED_YAW_EPSILON := 0.0005

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		model_config: Dictionary, animation_config: Dictionary,
		equipment_config: Dictionary = {}) -> Array[String]:
	actor_id = int(dto.actor_id)
	server_target = adapter.tile_center(int(dto.x), int(dto.y))
	position = server_target
	_segment_start = position
	_smoothed_server_interval = initial_server_interval
	rotation.y = adapter.rotation_to_godot(int(dto.rotation))
	_target_yaw = rotation.y
	collision_layer = 2
	collision_mask = 0
	var selection_shape: CollisionShape3D = CollisionShape3D.new()
	selection_shape.name = "SelectionCollision"
	var capsule_shape: CapsuleShape3D = CapsuleShape3D.new()
	capsule_shape.radius = 0.45
	capsule_shape.height = 1.9
	selection_shape.shape = capsule_shape
	selection_shape.position.y = 0.95
	add_child(selection_shape)
	var selection_ring: MeshInstance3D = MeshInstance3D.new()
	selection_ring.name = "SelectionRing"
	var ring: TorusMesh = TorusMesh.new()
	ring.inner_radius = 0.48
	ring.outer_radius = 0.58
	var ring_material: StandardMaterial3D = StandardMaterial3D.new()
	ring_material.albedo_color = Color(0.95, 0.76, 0.18, 0.9)
	ring_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	ring.material = ring_material
	selection_ring.mesh = ring
	selection_ring.position.y = 0.05
	selection_ring.visible = false
	# Gameplay-only visual layer. The minimap and full-map cameras cull it, so
	# neither top-down viewport pays for selection rings or nameplates it never
	# shows at their scale.
	selection_ring.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(selection_ring)
	_add_nameplate(dto)
	resolver = AnimationResolver.new(animation_config)
	_model_config = model_config.duplicate(true)
	_attachment_bones = (model_config.get("attachments", {}) as Dictionary).duplicate(true)
	_equipment_config = (equipment_config as Dictionary).duplicate(true)
	var source_path := _external_path(str(model_config.get("scene", "")))
	var errors := _load_native_scene(source_path)
	if not errors.is_empty():
		_add_fallback_visual(dto)
	if errors.is_empty():
		_apply_import_adapter(model_config.get("import", {}))
		var visual_error: String = _validate_native_visual()
		if not visual_error.is_empty():
			errors.append(visual_error)
			_add_fallback_visual(dto)
		var skeleton: Skeleton3D = null
		for node in find_children("*", "Skeleton3D", true, false):
			skeleton = node as Skeleton3D
			break
		if skeleton == null:
			errors.append("Skeleton3D missing")
		else:
			_native_skeleton = skeleton
			apply_appearance_variants(dto.get("appearance", {}) as Dictionary)
			var animation_path := _external_path(str(model_config.get("animationLibrary", "")))
			var imported := NativeAnimationImporter.import_library(self, animation_path, skeleton, model_config.get("boneAliases", {}))
			animation_player = imported.player
			errors.append_array(Array(imported.errors))
			if animation_player != null:
				if not animation_player.animation_finished.is_connected(
						_on_animation_finished):
					animation_player.animation_finished.connect(_on_animation_finished)
				errors.append_array(resolver.validate(imported.clips))
				play_action(&"idle")
	apply_equipment_visuals(dto.get("equipment_visuals", {}) as Dictionary,
		dto.get("equipment_fallback_parts", []) as Array)
	return errors

func apply_appearance_variants(appearance: Dictionary) -> void:
	if _native_skeleton == null:
		return
	var culture: String = str(_model_config.get("culture", "luminous"))
	var skin_tint: Color = AppearanceVariants.skin_tint(int(appearance.get("skin", 0)))
	var hair_tint: Color = AppearanceVariants.hair_color(int(appearance.get("hair", 0)))
	var eye_tint: Color = AppearanceVariants.eye_color(int(appearance.get("eyes", 0)))
	var head_style: int = AppearanceVariants.head_style(int(appearance.get("head", 0)))
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	if native_model == null:
		return
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		var mesh_name: String = mesh_node.name.to_lower()
		if mesh_name == "eyes":
			_tint_mesh(mesh_node, eye_tint, true)
		elif mesh_name == "eyebrows":
			_tint_mesh(mesh_node, hair_tint)
		elif mesh_name == "body":
			_tint_mesh(mesh_node, skin_tint)
		elif mesh_name == "wardrobe_shirt":
			_set_mesh_color(mesh_node, AppearanceVariants.wardrobe_color(
				culture, AppearanceVariants.PART_SHIRT, int(appearance.get("shirt", 0))))
		elif mesh_name == "wardrobe_pants":
			_set_mesh_color(mesh_node, AppearanceVariants.wardrobe_color(
				culture, AppearanceVariants.PART_PANTS, int(appearance.get("pants", 0))))
		elif mesh_name == "wardrobe_boots":
			_set_mesh_color(mesh_node, AppearanceVariants.wardrobe_color(
				culture, AppearanceVariants.PART_BOOTS, int(appearance.get("boots", 0))))
		elif mesh_name == "wardrobe_head_band":
			_set_appearance_visible(mesh_node, head_style == 1 or head_style == 3)
			_set_mesh_color(mesh_node, AppearanceVariants.wardrobe_color(
				culture, AppearanceVariants.PART_HEAD, int(appearance.get("head", 0))))
		elif mesh_name == "wardrobe_head_cap":
			_set_appearance_visible(mesh_node, head_style == 2 or head_style == 3)
			_set_mesh_color(mesh_node, AppearanceVariants.wardrobe_color(
				culture, AppearanceVariants.PART_HEAD, int(appearance.get("head", 0))))
	_add_hair_variant(AppearanceVariants.hair_style(
		int(appearance.get("hair", 0))), hair_tint)
	_refresh_body_surface_visibility()

func _set_appearance_visible(mesh_node: MeshInstance3D, visible_by_style: bool) -> void:
	# Appearance owns whether a wardrobe surface exists at all; equipment only
	# covers one that does. Recording the appearance choice keeps unequipping a
	# helmet from revealing a headband the character never chose.
	if visible_by_style:
		if mesh_node.has_meta("appearance_hidden"):
			mesh_node.remove_meta("appearance_hidden")
	else:
		mesh_node.set_meta("appearance_hidden", true)
	mesh_node.visible = visible_by_style

func _tint_mesh(mesh_node: MeshInstance3D, tint: Color,
		emissive: bool = false) -> void:
	if mesh_node.mesh == null or mesh_node.mesh.get_surface_count() == 0:
		return
	var source: Material = mesh_node.get_active_material(0)
	if source is not StandardMaterial3D:
		return
	var material: StandardMaterial3D = (source as StandardMaterial3D).duplicate()
	material.albedo_color = (source as StandardMaterial3D).albedo_color * tint
	if emissive:
		material.emission_enabled = true
		material.emission = tint * 0.28
	mesh_node.material_override = material

func _set_mesh_color(mesh_node: MeshInstance3D, color: Color) -> void:
	if mesh_node.mesh == null or mesh_node.mesh.get_surface_count() == 0:
		return
	var source: Material = mesh_node.get_active_material(0)
	if source is not StandardMaterial3D:
		return
	var material: StandardMaterial3D = (source as StandardMaterial3D).duplicate()
	material.albedo_color = color
	mesh_node.material_override = material

func _add_hair_variant(style: int, color: Color) -> void:
	for old_attachment: Node in _native_skeleton.get_children():
		if old_attachment.name.begins_with("AppearanceHair_"):
			old_attachment.queue_free()
	var styles_value: Variant = _model_config.get("hairStyles", [])
	if styles_value is not Array or (styles_value as Array).is_empty():
		return
	var styles: Array = styles_value as Array
	var path: String = str(styles[posmod(style, styles.size())])
	var native_hair: Node3D = _equipment_instance(path)
	if native_hair == null:
		push_warning("Native hairstyle failed to load: " + path)
		return
	var attachment: BoneAttachment3D = _bone_attachment("Head", 9, style)
	if attachment == null:
		native_hair.queue_free()
		return
	attachment.name = "AppearanceHair_%d" % style
	native_hair.name = "NativeHair"
	attachment.add_child(native_hair)
	for node_value: Node in native_hair.find_children("*", "MeshInstance3D", true, false):
		_tint_mesh(node_value as MeshInstance3D, color)

func render_diagnostics() -> Dictionary:
	var meshes: Array[Dictionary] = []
	for node_value: Node in find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		meshes.append({
			"path": str(mesh_node.get_path()),
			"visible": mesh_node.visible,
			"visible_in_tree": mesh_node.is_visible_in_tree(),
			"layers": mesh_node.layers,
			"aabb": mesh_node.get_aabb(),
			"material_override": mesh_node.material_override != null,
		})
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	return {
		"actor_id": actor_id,
		"server_target": server_target,
		"final_global_position": global_position,
		"native_model_transform": native_model.transform if native_model != null else Transform3D.IDENTITY,
		"meshes": meshes,
	}

func _add_fallback_visual(dto: Dictionary) -> void:
	var mesh_instance: MeshInstance3D = MeshInstance3D.new()
	mesh_instance.name = "MissingModelFallback"
	var capsule: CapsuleMesh = CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.7
	var material: StandardMaterial3D = StandardMaterial3D.new()
	var kind: int = int(dto.get("kind", 0))
	material.albedo_color = Color(0.92, 0.56, 0.18) if kind == 2 else Color(0.75, 0.18, 0.78)
	capsule.material = material
	mesh_instance.mesh = capsule
	mesh_instance.position.y = 0.85
	add_child(mesh_instance)

func _add_nameplate(dto: Dictionary) -> void:
	var label: Label3D = Label3D.new()
	label.name = "Nameplate"
	label.text = str(dto.get("name", "Unknown actor"))
	label.position.y = 2.15
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.font_size = 28
	label.outline_size = 6
	label.modulate = Color(1.0, 1.0, 1.0, 1.0)
	label.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(label)
	_nameplate = label

func set_nameplate_visible(enabled: bool) -> void:
	if is_instance_valid(_nameplate):
		_nameplate.visible = enabled

func apply_server_state(dto: Dictionary, adapter: CoordinateAdapter, teleport := false) -> void:
	var next_target: Vector3 = adapter.tile_center(int(dto.x), int(dto.y))
	# Server movement contains tile coordinates only. Keep the last sampled
	# rendered-surface height until Main performs the ray sample for the new tile;
	# otherwise each packet temporarily pushes actors back to the flat manifest
	# fallback and can leave them visibly embedded in sculpted terrain.
	next_target.y = server_target.y
	var target_changed: bool = server_target.distance_squared_to(next_target) > 0.000001
	server_target = next_target
	var actor_command: int = int(dto.get("command", -1))
	var authoritative_yaw: float = target_yaw_for_state(
		_target_yaw, actor_command, int(dto.rotation), adapter)
	_target_yaw = _facing_override_yaw if _facing_override_active else authoritative_yaw
	_presentation_speed = walk_presentation_speed
	if actor_command >= 30 and actor_command <= 37:
		_presentation_speed = run_presentation_speed
	if teleport or global_position.distance_to(server_target) > 8.0:
		global_position = server_target
		rotation.y = _target_yaw
		_segment_start = server_target
		_segment_elapsed = 0.0
		_segment_duration = 0.0
		_last_movement_update_msec = -1
		_smoothed_server_interval = initial_server_interval
		_snap_pending = false
	elif target_changed:
		var now_msec: int = Time.get_ticks_msec()
		if _last_movement_update_msec >= 0:
			var observed_interval: float = float(
				now_msec - _last_movement_update_msec) / 1000.0
			if observed_interval <= maximum_segment_duration * 2.0:
				observed_interval = clampf(observed_interval, 0.05,
					maximum_segment_duration)
				_smoothed_server_interval = lerpf(_smoothed_server_interval,
					observed_interval, interval_smoothing)
			else:
				# A long stationary pause begins a new movement burst; do not
				# treat the idle time as the next step's network cadence.
				_smoothed_server_interval = initial_server_interval
		_last_movement_update_msec = now_msec
		_segment_start = global_position
		_segment_elapsed = 0.0
		_segment_duration = presentation_segment_duration(
			global_position.distance_to(server_target), _presentation_speed,
			_smoothed_server_interval, arrival_margin,
			minimum_segment_duration, maximum_segment_duration)
	_wake()
	if dto.has("command") and resolver != null:
		play_action(resolver.action_for_command(actor_command))
	apply_equipment_visuals(dto.get("equipment_visuals", {}) as Dictionary,
		dto.get("equipment_fallback_parts", []) as Array)

func apply_equipment_visuals(visuals: Dictionary, fallback_parts: Array = []) -> void:
	for raw_part: Variant in _equipment_visuals.keys():
		var old_part: int = int(raw_part)
		if not visuals.has(old_part) and not visuals.has(str(old_part)):
			_clear_equipment_part(old_part)
	for raw_part: Variant in visuals:
		var part: int = int(raw_part)
		var visual_id: int = int(visuals[raw_part])
		var allow_fallback: bool = fallback_parts.has(part)
		if int(_equipment_visuals.get(part, -1)) == visual_id and (
				not allow_fallback or _equipment_nodes.has(part)):
			continue
		_clear_equipment_part(part)
		_equipment_visuals[part] = visual_id
		_create_equipment_part(part, visual_id, allow_fallback)

func equipment_diagnostics() -> Dictionary:
	# Modified 2026-08-28 for Eloria Client: garments are now skinned to this
	# actor's skeleton rather than parented to a bone, so the two attachment
	# paths are reported separately and a regression in either one is visible.
	var native_count: int = 0
	var fallback_count: int = 0
	var skinned_count: int = 0
	var socket_count: int = 0
	for nodes_value: Variant in _equipment_nodes.values():
		for node_value: Variant in nodes_value:
			var node: Node = node_value as Node
			if not is_instance_valid(node):
				continue
			if node.has_meta("native_equipment"):
				native_count += 1
				if node is MeshInstance3D:
					skinned_count += 1
				else:
					socket_count += 1
			else:
				fallback_count += 1
	return {"visuals": _equipment_visuals.duplicate(), "native": native_count,
		"fallback": fallback_count, "skinned": skinned_count,
		"socket": socket_count, "rigFitScale": rig_fit_scale()}

func _clear_equipment_part(part: int) -> void:
	var nodes_value: Variant = _equipment_nodes.get(part, [])
	if nodes_value is Array:
		for node_value: Variant in nodes_value:
			var node: Node = node_value as Node
			if is_instance_valid(node):
				node.queue_free()
	_equipment_nodes.erase(part)
	_equipment_visuals.erase(part)
	_release_equipment_hides(part)

func _create_equipment_part(part: int, visual_id: int, allow_fallback: bool) -> void:
	# Modified 2026-08-28 for Eloria Client: equipment used to be parented to a
	# raw bone with an identity transform.  Bone rest bases are not axis aligned,
	# so every hilt left the hand sideways, and a rigid child of one bone could
	# never follow the spine or the knees.  Props now resolve a character-space
	# socket through the bone rest, and garments rebind to this actor's skeleton.
	if _native_skeleton == null:
		return
	var parts: Dictionary = _equipment_config.get("parts", {}) as Dictionary
	var part_config: Dictionary = parts.get(str(part), {}) as Dictionary
	if part_config.is_empty():
		return
	var model_config: Dictionary = _equipment_model_config(part, visual_id)
	var created: Array[Node] = []
	if not model_config.is_empty():
		var scene_path: String = str(model_config.get("scene", ""))
		if str(model_config.get("attach", "socket")) == "skinned":
			created.append_array(_attach_skinned_equipment(scene_path, part, visual_id,
				model_config.get("tint", []) as Array))
		else:
			var socket: Dictionary = _equipment_socket(part, model_config)
			var attachment: BoneAttachment3D = _attach_socketed_equipment(
				socket, scene_path, model_config, part, visual_id)
			if attachment != null:
				created.append(attachment)
	if created.is_empty() and allow_fallback:
		created.append_array(_attach_fallback_equipment(part, visual_id, part_config))
	if created.is_empty():
		_equipment_nodes.erase(part)
	else:
		_equipment_nodes[part] = created
		_apply_equipment_hides(part, part_config, model_config)

func _apply_equipment_hides(part: int, part_config: Dictionary,
		model_config: Dictionary) -> void:
	# Garments are lofted with clearance over the reference body, but a bulkier
	# wardrobe would still poke through, so the surfaces a piece covers are
	# switched off while it is worn and counted so overlapping parts unwind.
	var names_value: Variant = model_config.get("hides", part_config.get("hides", []))
	var names: Array[String] = []
	if names_value is Array:
		for raw_name: Variant in names_value:
			names.append(str(raw_name).to_lower())
	if names.is_empty():
		return
	_equipment_hides[part] = names
	for surface: String in names:
		_hidden_body_surfaces[surface] = int(_hidden_body_surfaces.get(surface, 0)) + 1
	_refresh_body_surface_visibility()

func _release_equipment_hides(part: int) -> void:
	var names_value: Variant = _equipment_hides.get(part, [])
	if names_value is Array:
		for raw_name: Variant in names_value:
			var surface: String = str(raw_name)
			var remaining: int = int(_hidden_body_surfaces.get(surface, 0)) - 1
			if remaining > 0:
				_hidden_body_surfaces[surface] = remaining
			else:
				_hidden_body_surfaces.erase(surface)
	_equipment_hides.erase(part)
	_refresh_body_surface_visibility()

func _refresh_body_surface_visibility() -> void:
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	if native_model == null:
		return
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		var surface: String = mesh_node.name.to_lower()
		if not surface.begins_with("wardrobe_"):
			continue
		if _hidden_body_surfaces.has(surface):
			mesh_node.visible = false
		elif not mesh_node.has_meta("appearance_hidden"):
			mesh_node.visible = true
	if _native_skeleton != null:
		var hide_hair: bool = _hidden_body_surfaces.has("hair")
		for node_value: Node in _native_skeleton.get_children():
			if node_value.name.begins_with("AppearanceHair_"):
				(node_value as Node3D).visible = not hide_hair

func _equipment_model_config(part: int, visual_id: int) -> Dictionary:
	var aliases: Dictionary = _equipment_config.get("aliases", {}) as Dictionary
	var model_key: String = "%d:%d" % [part, visual_id]
	model_key = str(aliases.get(model_key, model_key))
	var models: Dictionary = _equipment_config.get("models", {}) as Dictionary
	return models.get(model_key, {}) as Dictionary

func _equipment_socket(part: int, model_config: Dictionary) -> Dictionary:
	# A model may override the shared part socket, which is how a two-handed
	# haft can ride differently from a one-handed hilt on the same bone.
	var override: Dictionary = model_config.get("socket", {}) as Dictionary
	if not override.is_empty():
		return override
	var sockets: Dictionary = _equipment_config.get("sockets", {}) as Dictionary
	return sockets.get(str(part), {}) as Dictionary

func rig_fit_scale() -> float:
	# Equipment is authored once against the canonical rest pose. Rigs built
	# shorter wear the same asset scaled about the floor, so one GLB fits every
	# race and both body variants.
	if _native_skeleton == null:
		return 1.0
	var canonical: float = float(_equipment_config.get("canonicalHeadRestY", 0.0))
	if canonical <= 0.0:
		return 1.0
	var head: int = _native_skeleton.find_bone("Head")
	if head < 0:
		return 1.0
	return _native_skeleton.get_bone_global_rest(head).origin.y / canonical

func _attach_socketed_equipment(socket: Dictionary, scene_path: String,
		model_config: Dictionary, part: int, visual_id: int) -> BoneAttachment3D:
	if socket.is_empty():
		return null
	var bone: String = str(socket.get("bone", ""))
	var attachment: BoneAttachment3D = _bone_attachment(bone, part, visual_id)
	if attachment == null:
		return null
	var native_model: Node3D = _equipment_instance(scene_path)
	if native_model == null:
		attachment.queue_free()
		return null
	var bone_index: int = _native_skeleton.find_bone(bone)
	var rest: Transform3D = _native_skeleton.get_bone_global_rest(bone_index)
	var fit: float = rig_fit_scale()
	var scale: float = fit * float(model_config.get("scale", 1.0))
	var placement: Transform3D = Transform3D(
		Basis.from_euler(_vector3(socket.get("rotationDegrees", []),
			Vector3.ZERO) * (PI / 180.0)).scaled(Vector3.ONE * scale),
		rest.origin + _vector3(socket.get("offset", []), Vector3.ZERO) * fit)
	# The socket is authored in character space; cancelling the bone rest keeps
	# it readable while still riding the bone once the clip plays.
	native_model.transform = rest.affine_inverse() * placement
	_tint_equipment(native_model, model_config.get("tint", []) as Array)
	attachment.add_child(native_model)
	attachment.set_meta("native_equipment", true)
	return attachment

func _attach_skinned_equipment(scene_path: String, part: int, visual_id: int,
		tint: Array = []) -> Array[Node]:
	# The garment ships with the shared joint hierarchy so it is a valid skinned
	# glTF on its own. Replacing its bind poses with this skeleton's rest poses
	# retargets the garment and applies the rig fit scale in one step.
	var created: Array[Node] = []
	var fit: float = rig_fit_scale()
	var fit_basis: Transform3D = Transform3D(
		Basis.IDENTITY.scaled(Vector3.ONE * fit), Vector3.ZERO)
	# Bind poses depend only on the rig, and every actor built from one model
	# shares a rest pose, so the rebound skin is cached per model and garment
	# instead of rebuilt from 65 named binds for each actor that wears one.
	var cache_key: String = "%s|%s" % [str(_model_config.get("scene", "")), scene_path]
	for piece_value: Variant in _equipment_pieces(scene_path):
		var piece: Dictionary = piece_value as Dictionary
		var surface_key: String = "%s|%s" % [cache_key, str(piece.get("name", ""))]
		var rebound: Skin = _rebound_skins.get(surface_key) as Skin
		if rebound == null:
			rebound = _rebound_skin(piece.get("bones", PackedStringArray()) as PackedStringArray,
				fit_basis)
			if rebound != null:
				_rebound_skins[surface_key] = rebound
		if rebound == null:
			continue
		var clone: MeshInstance3D = MeshInstance3D.new()
		clone.name = "EquipmentSkin_%d_Visual_%d_%s" % [part, visual_id,
			str(piece.get("name", "Mesh"))]
		clone.mesh = piece.get("mesh") as Mesh
		clone.skin = rebound
		_tint_surfaces(clone, tint)
		_native_skeleton.add_child(clone)
		clone.skeleton = NodePath("..")
		clone.set_meta("native_equipment", true)
		created.append(clone)
	return created

func _equipment_instance(scene_path: String) -> Node3D:
	var pieces: Array = _equipment_pieces(scene_path)
	if pieces.is_empty():
		return null
	var holder: Node3D = Node3D.new()
	holder.name = "NativeEquipment"
	for piece_value: Variant in pieces:
		var piece: Dictionary = piece_value as Dictionary
		var mesh_node: MeshInstance3D = MeshInstance3D.new()
		mesh_node.name = str(piece.get("name", "Mesh"))
		mesh_node.mesh = piece.get("mesh") as Mesh
		mesh_node.transform = piece.get("transform", Transform3D.IDENTITY)
		holder.add_child(mesh_node)
	return holder

const TINT_SLOTS := {"base": 0, "trim": 1, "detail": 2}

func _tint_equipment(root: Node3D, tint: Array) -> void:
	if tint.is_empty():
		return
	for node_value: Node in root.find_children("*", "MeshInstance3D", true, false):
		_tint_surfaces(node_value as MeshInstance3D, tint)

func _tint_surfaces(mesh_node: MeshInstance3D, tint: Array) -> void:
	# One authored mesh serves a whole material ladder, so an iron and a steel
	# helm are the same scene under different tints. The slot is read from the
	# material name rather than the surface index, because a piece that uses no
	# trim geometry would otherwise shift its detail colour onto the trim.
	if tint.is_empty() or mesh_node.mesh == null:
		return
	for surface: int in range(mesh_node.mesh.get_surface_count()):
		var source: Material = mesh_node.mesh.surface_get_material(surface)
		if source is not StandardMaterial3D:
			continue
		var slot: int = _tint_slot(source.resource_name, surface)
		if slot < 0 or slot >= tint.size():
			continue
		var origin: StandardMaterial3D = source as StandardMaterial3D
		var material: StandardMaterial3D = origin.duplicate()
		material.albedo_color = _tint_colour(tint[slot], origin.albedo_color)
		if origin.emission_enabled:
			# An enchanted finish carries its glow on the same slot, so a shared
			# mesh would otherwise keep the first variant's light: a Crown of
			# Life tinted green but still glowing the Crown of Mana's blue.
			var glow: Color = _tint_colour(tint[slot], origin.emission)
			var authored: float = maxf(origin.emission.r, maxf(
				origin.emission.g, origin.emission.b))
			var tinted: float = maxf(glow.r, maxf(glow.g, glow.b))
			material.emission = glow * (authored / maxf(tinted, 0.001))
		mesh_node.set_surface_override_material(surface, material)

static func _tint_slot(material_name: String, fallback: int) -> int:
	var suffix: String = material_name.get_slice(" ", material_name.count(" ")).to_lower()
	return int(TINT_SLOTS.get(suffix, fallback))

static func _tint_colour(value: Variant, fallback: Color) -> Color:
	# Tints are authored as sRGB bytes and albedo_color is sRGB, so they pass
	# through unconverted. The generator converts the same bytes to linear on
	# its way into the glTF factor, which the importer converts back, so a
	# tinted piece and the mesh it was authored from land on the same colour.
	if value is Array and (value as Array).size() >= 3:
		var channels: Array = value as Array
		return Color(float(channels[0]) / 255.0, float(channels[1]) / 255.0,
			float(channels[2]) / 255.0, fallback.a)
	return fallback

func _rebound_skin(bone_names: PackedStringArray, fit: Transform3D) -> Skin:
	# The mesh's JOINTS_0 values index this bind array, so a bind may never be
	# skipped: dropping one would shift every later bone by a slot. A garment
	# whose rig this actor does not carry is refused outright instead.
	if bone_names.is_empty():
		return null
	var rebound: Skin = Skin.new()
	for bone_name: String in bone_names:
		var target: int = _native_skeleton.find_bone(bone_name)
		if bone_name.is_empty() or target < 0:
			return null
		rebound.add_named_bind(bone_name,
			_native_skeleton.get_bone_global_rest(target).affine_inverse() * fit)
	return rebound

func _attach_fallback_equipment(part: int, visual_id: int,
		part_config: Dictionary) -> Array[Node]:
	var created: Array[Node] = []
	var socket: Dictionary = _equipment_socket(part, {})
	var bones: Array[String] = []
	var fallback_bone: String = str(socket.get("bone", ""))
	if not fallback_bone.is_empty():
		bones.append(fallback_bone)
	var semantic: String = str(part_config.get("attachment", ""))
	var bones_value: Variant = _attachment_bones.get(semantic, "")
	if bones_value is Array:
		for raw_bone: Variant in bones_value:
			if not bones.has(str(raw_bone)):
				bones.append(str(raw_bone))
	elif not str(bones_value).is_empty() and not bones.has(str(bones_value)):
		bones.append(str(bones_value))
	for bone: String in bones:
		var attachment: BoneAttachment3D = _bone_attachment(bone, part, visual_id)
		if attachment == null:
			continue
		attachment.add_child(_equipment_fallback_mesh(
			str(part_config.get("fallback", "body"))))
		created.append(attachment)
	return created

static func _vector3(value: Variant, fallback: Vector3) -> Vector3:
	if value is Array and (value as Array).size() >= 3:
		var values: Array = value as Array
		return Vector3(float(values[0]), float(values[1]), float(values[2]))
	return fallback

func _bone_attachment(bone: String, part: int, visual_id: int) -> BoneAttachment3D:
	if _native_skeleton == null or _native_skeleton.find_bone(bone) < 0:
		return null
	var attachment: BoneAttachment3D = BoneAttachment3D.new()
	attachment.name = "EquipmentPart_%d_Visual_%d_%s" % [part, visual_id, bone]
	attachment.bone_name = bone
	_native_skeleton.add_child(attachment)
	return attachment

func _equipment_fallback_mesh(shape: String) -> MeshInstance3D:
	var instance: MeshInstance3D = MeshInstance3D.new()
	instance.name = "MissingNativeEquipmentFallback"
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = Color(1.0, 0.1, 0.85, 0.85)
	material.emission_enabled = true
	material.emission = Color(0.7, 0.0, 0.5)
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	match shape:
		"weapon":
			var weapon: BoxMesh = BoxMesh.new()
			weapon.size = Vector3(0.08, 0.7, 0.08)
			instance.mesh = weapon
		"shield":
			var shield: CylinderMesh = CylinderMesh.new()
			shield.top_radius = 0.28
			shield.bottom_radius = 0.28
			shield.height = 0.06
			instance.mesh = shield
		"head":
			var head: SphereMesh = SphereMesh.new()
			head.radius = 0.2
			head.height = 0.35
			instance.mesh = head
		"feet":
			var foot: BoxMesh = BoxMesh.new()
			foot.size = Vector3(0.18, 0.12, 0.32)
			instance.mesh = foot
		_:
			var body: BoxMesh = BoxMesh.new()
			body.size = Vector3(0.32, 0.22, 0.18)
			instance.mesh = body
	instance.material_override = material
	return instance

func play_action(action: StringName) -> void:
	if animation_player == null or resolver == null:
		return
	var clip := resolver.clip_for_action(action)
	if clip.is_empty() or not animation_player.has_animation(clip):
		return
	animation_player.speed_scale = resolver.playback_speed_for_action(action)
	if current_action == action and animation_player.is_playing():
		return
	current_action = action
	animation_player.play(clip)

func _on_animation_finished(_animation_name: StringName) -> void:
	# The server sends transition commands, not a second command for the resting
	# pose. Keep this explicit and data-driven through the action map.
	if current_action == &"sit":
		play_action(&"seated_idle")
	elif current_action == &"stand":
		play_action(&"idle")

func turn_by(radians: float) -> void:
	_wake()
	_target_yaw = wrapf(_target_yaw + radians, -PI, PI)
	_facing_override_active = true
	_facing_override_yaw = _target_yaw
	play_action(&"turn")

func desired_facing_yaw() -> float:
	return _target_yaw

func set_facing_override(enabled: bool) -> void:
	_facing_override_active = enabled
	if enabled:
		_facing_override_yaw = _target_yaw

static func target_yaw_for_state(current_yaw: float, actor_command: int,
		server_rotation: int, adapter: CoordinateAdapter) -> float:
	var command_direction: Vector2i = EloriaProtocol.actor_command_direction(actor_command)
	if command_direction != Vector2i.ZERO:
		return adapter.direction_to_godot(command_direction)
	# Sitting and standing are pose transitions. Their packet rotation can be
	# stale, so preserve the direction the actor was already facing.
	if actor_command in [13, 14]:
		return current_yaw
	return adapter.rotation_to_godot(server_rotation)

func _finish_movement_presentation() -> void:
	if current_action in [&"walk", &"run"]:
		play_action(&"idle")

func set_selected(value: bool) -> void:
	var ring: Node3D = get_node_or_null("SelectionRing") as Node3D
	if ring != null:
		ring.visible = value

func set_surface_height(value: float) -> void:
	if not _snap_pending and is_equal_approx(server_target.y, value):
		return
	server_target.y = value
	if _snap_pending or absf(global_position.y - value) > 0.5:
		global_position.y = value
	_wake()

static func presentation_segment_duration(distance: float, nominal_speed: float,
		observed_interval: float, margin: float, minimum_duration: float,
		maximum_duration: float) -> float:
	var nominal_duration: float = distance / maxf(nominal_speed, 0.001)
	var cadence_duration: float = observed_interval * margin
	return clampf(maxf(nominal_duration, cadence_duration),
		minimum_duration, maximum_duration)

func _physics_process(delta: float) -> void:
	if _snap_pending:
		global_position = server_target
		rotation.y = _target_yaw
		_segment_start = server_target
		_snap_pending = false
		_settle_if_idle()
		return
	if _segment_duration > 0.0:
		_segment_elapsed = minf(_segment_elapsed + delta, _segment_duration)
		var progress: float = _segment_elapsed / _segment_duration
		global_position = _segment_start.lerp(server_target, progress)
		if progress >= 1.0:
			global_position = server_target
			_segment_duration = 0.0
			_finish_movement_presentation()
	else:
		global_position = server_target
	rotation.y = rotate_toward(rotation.y, _target_yaw, turn_speed_radians * delta)
	_settle_if_idle()

## A standing actor reproduced the same transform 60 times a second. Once the
## interpolation segment has finished and the actor faces where the server says
## it should, the node is snapped exactly onto its target and physics processing
## stops until the next packet, keypress or surface sample wakes it. Nothing
## about the resulting pose differs from the value the loop kept rewriting.
func _settle_if_idle() -> void:
	if _snap_pending or _segment_duration > 0.0:
		return
	if absf(wrapf(_target_yaw - rotation.y, -PI, PI)) > SETTLED_YAW_EPSILON:
		return
	global_position = server_target
	rotation.y = _target_yaw
	_settled = true
	set_physics_process(false)

func _wake() -> void:
	if not _settled:
		return
	_settled = false
	set_physics_process(true)

func _load_native_scene(path: String) -> Array[String]:
	if path.is_empty():
		return ["model scene path missing"]
	var model := GlbSceneCache.instantiate(path)
	if model == null:
		return ["model glTF import failed", path]
	model.name = "NativeModel"
	add_child(model)
	return []

# Parsed equipment geometry, cached for the session. Only resources and plain
# data are held: caching the imported Node3D scenes instead would keep hundreds
# of nodes alive with no owner to free them.
static var _equipment_pieces_cache: Dictionary = {}
static var _rebound_skins: Dictionary = {}

static func _equipment_pieces(path: String) -> Array:
	# One parse per scene per session. The generic tier means every actor now
	# wears a shirt, leggings and boots by default, so re-importing a GLB for
	# each actor would cost hundreds of parses on a populated map.
	if _equipment_pieces_cache.has(path):
		return _equipment_pieces_cache[path] as Array
	var pieces: Array = []
	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	if document.append_from_file(_external_path(path), state) == OK:
		var generated: Node = document.generate_scene(state)
		var root: Node3D = generated as Node3D
		if root != null:
			var skeleton: Skeleton3D = null
			for node_value: Node in root.find_children("*", "Skeleton3D", true, false):
				skeleton = node_value as Skeleton3D
				break
			for node_value: Node in root.find_children("*", "MeshInstance3D", true, false):
				var mesh_node: MeshInstance3D = node_value as MeshInstance3D
				if mesh_node.mesh == null:
					continue
				pieces.append({
					"mesh": mesh_node.mesh,
					"name": str(mesh_node.name),
					"transform": _relative_transform(mesh_node, root),
					"bones": _skin_bone_names(mesh_node.skin, skeleton),
				})
		if generated != null:
			generated.free()
	if not pieces.is_empty():
		_equipment_pieces_cache[path] = pieces
	return pieces

static func _relative_transform(node: Node3D, root: Node3D) -> Transform3D:
	# Accumulated by hand: global_transform is only meaningful inside the tree,
	# and the imported scene is parsed without ever being added to one.
	var accumulated: Transform3D = Transform3D.IDENTITY
	var walker: Node3D = node
	while walker != null and walker != root:
		accumulated = walker.transform * accumulated
		walker = walker.get_parent() as Node3D
	return accumulated

static func _skin_bone_names(skin: Skin, skeleton: Skeleton3D) -> PackedStringArray:
	var names: PackedStringArray = PackedStringArray()
	if skin == null:
		return names
	for index: int in range(skin.get_bind_count()):
		var bone_name: String = skin.get_bind_name(index)
		if bone_name.is_empty() and skeleton != null:
			var source_bone: int = skin.get_bind_bone(index)
			if source_bone >= 0 and source_bone < skeleton.get_bone_count():
				bone_name = skeleton.get_bone_name(source_bone)
		names.append(bone_name)
	return names

func _apply_import_adapter(config: Dictionary) -> void:
	var model := get_node_or_null("NativeModel") as Node3D
	if model == null:
		return
	model.scale = Vector3.ONE * float(config.get("scale", 1.0))
	# Native glTF actors are authored facing +Z, while Godot's logical forward
	# axis is -Z. Correct only the imported visual root so server yaw, click
	# targets, keyboard-relative movement, and equipment attachments continue
	# to share one canonical logical heading.
	var forward_axis_correction: float = float(
		config.get("forwardAxisCorrectionDegreesY", 180.0))
	model.rotation_degrees = Vector3(
		float(config.get("rotationDegreesX", 0.0)),
		float(config.get("rotationDegreesY", 0.0)) + forward_axis_correction,
		float(config.get("rotationDegreesZ", 0.0)))
	# The protocol position is a foot point. Normalize the imported visual at
	# its root without flattening or rewriting the glTF hierarchy/skeleton.
	var bounds: AABB = _native_visual_bounds(model)
	if bounds.size.y > 0.0:
		model.position.y = -bounds.position.y

func _validate_native_visual() -> String:
	var native_model: Node3D = get_node_or_null("NativeModel") as Node3D
	if native_model == null:
		return "native model root missing"
	var visible_meshes: int = 0
	for node_value: Node in native_model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh != null and mesh_node.visible and mesh_node.layers != 0:
			visible_meshes += 1
	return "native model has no renderable meshes" if visible_meshes == 0 else ""

func _native_visual_bounds(model: Node3D) -> AABB:
	var combined: AABB = AABB()
	var initialized: bool = false
	var to_model: Transform3D = model.global_transform.affine_inverse()
	for node_value: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		if mesh_node.mesh == null:
			continue
		var relative: Transform3D = to_model * mesh_node.global_transform
		var mesh_bounds: AABB = relative * mesh_node.get_aabb()
		combined = combined.merge(mesh_bounds) if initialized else mesh_bounds
		initialized = true
	return combined

static func _external_path(path: String) -> String:
	return ProjectSettings.globalize_path(path) if path.begins_with("res://") else path
