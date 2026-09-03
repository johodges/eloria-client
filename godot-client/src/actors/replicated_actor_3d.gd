class_name ReplicatedActor3D
extends CharacterBody3D

@export var walk_presentation_speed := 6.0
@export var run_presentation_speed := 9.0
@export var turn_speed_radians := 12.0
## The server's walking interval, so the very first step of a session is
## paced correctly before any packet cadence has been observed. Every burst
## after that keeps the cadence it last measured.
@export var initial_server_interval := 0.6
@export var interval_smoothing := 0.5
## How much longer than the observed server cadence one step is allowed to
## take. At 1.05 any jitter in the packet stream finished the step before the
## next one arrived, and the actor stopped and restarted on every tile.
@export var arrival_margin := 1.25
@export var minimum_segment_duration := 0.06
## Long enough to hold a walking step - 0.6 s a tile plus the arrival
## margin - so a walk is not driven faster than the server sends it.
@export var maximum_segment_duration := 1.0
## Kept walking for this long after a step lands before falling back to idle,
## again so a late packet does not flick the pose to idle and back.
@export var movement_coast_seconds := 0.12
## Crossfade between two clips. Playing them cold snapped the whole skeleton
## into the new pose, which is what a walk/idle flicker looked like.
@export var action_blend_seconds := 0.15

var actor_id := -1
var server_target := Vector3.ZERO
## How many tiles this actor stands on, across by along. The server
## reserves that box around the tile the actor reports and measures reach
## from its edges, so the model is drawn in the middle of the box rather
## than on the anchor tile - they differ by half a tile whenever an extent
## is even. One tile, the overwhelming majority, is unaffected.
var footprint := Vector2i.ONE
## How large this actor is drawn, as a multiple of its model's own size.
## The species' scale from the server profile, times whatever an invasion
## boss or another per-actor effect asks for. One is the model as authored,
## which is every actor unless a packet says otherwise.
var server_scale := 1.0
## The client's own import scale for this model, kept so the two can be
## multiplied rather than one overwriting the other.
var _import_scale := 1.0
## The ground marker, kept rather than looked up: it is counter-rotated
## every physics frame and a node path lookup per frame per actor is
## not what that should cost.
var _selection_ring: MeshInstance3D = null
## Metres per tile on the map this actor is on, so the marker can be
## the size of the ground the server reserved rather than a guess.
var _metres_per_tile := 1.0
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
var _smoothed_server_interval := 0.6
## The direction the body is actually crossing the ground in, which is not the
## tile direction the server named. See `_rendered_target_yaw`.
var _travel_yaw_active := false
var _travel_yaw := 0.0
## The body faces the direction of the step it is crossing on, taken fresh each
## step so a change of direction turns it at once. A straight click-path that is
## not one of the eight tile directions is walked as a zigzag of orthogonal and
## diagonal steps, so this can swing a little to either side of that line - the
## cost of committing to each step rather than averaging a window of them, which
## lagged every turn. The turn the body actually renders is rate-limited in
## `_physics_process`, which takes most of that swing back out.
## Whether the server says this actor is under the double-speed buff. The
## server paces a hastened actor at half the move interval but still names the
## ordinary walk commands, so the buff is the only thing that says an actor is
## covering ground fast enough to be running.
var _hastened := false
## Part 2 in the equipment registry: the cape, and the only part with cloth.
const CAPE_PART := 2
## The wardrobe meshes are shells fitted straight onto the skin they cover, so
## the body surface underneath pokes through them wherever the skeleton bends -
## which is what skin showing through the shirt is. Pushing each garment out a
## few millimetres along its own normals puts the skin behind it for good
## without changing the silhouette. Trims and seams grow slightly more so they
## stay on top of the garment they edge.
## Four millimetres closed the flat panels but not the shoulders, where the
## deltoid swings furthest from the shell it was fitted to, nor the waist,
## where the shirt hem and the pants waistband meet over the same skin. The
## shirt is given the most room, the waistband enough more than the shirt hem
## to read as a separate garment over it, and the boots enough to swallow the
## foot they are pulled over.
const WARDROBE_GROW := {
	"wardrobe_shirt": 0.011, "wardrobe_shirt_trim": 0.013,
	"wardrobe_pants": 0.009, "wardrobe_pants_seam": 0.016,
	"wardrobe_boots": 0.014, "wardrobe_boots_seam": 0.017,
	"wardrobe_head_band": 0.006, "wardrobe_head_cap": 0.009,
}

## The one facing an actor renders that the server did not state: the single
## 45 degree step shown while the answer to TURN_LEFT/TURN_RIGHT is in flight.
var _predicted_turn_pending := false
var _predicted_turn_yaw := 0.0
var _movement_coast_remaining := 0.0
var _native_skeleton: Skeleton3D
## The imported visual root and the yaw the import gave it. Several library clips
## are authored with the body turned off the rig's forward: the locomotion ones
## carry the whole pelvis about 23 degrees round, so a walk or a run faces that
## far off the way it travels though the node points exactly right. The action
## map states a per-action yaw that cancels it, applied on top of the base import
## yaw here and eased in over the animation crossfade so starting or stopping a
## walk does not snap the body. Poses meant to face off - a bladed combat idle, a
## sword lunge - declare nothing and are left as authored.
var _native_model: Node3D
var _base_model_yaw := 0.0
var _facing_offset := 0.0
var _facing_offset_from := 0.0
var _facing_offset_to := 0.0
var _facing_offset_elapsed := 0.0
var _cape_cloth: SkeletonModifier3D = null
var _attachment_bones: Dictionary = {}
var _model_config: Dictionary = {}
var _equipment_config: Dictionary = {}
var _equipment_visuals: Dictionary = {}
var _equipment_nodes: Dictionary = {}
var _equipment_hides: Dictionary = {}
var _hidden_body_surfaces: Dictionary = {}
var _nameplate: Label3D
var _speech_bubble: Label3D
var _speech_bubble_expiry_msec := 0
var _health_bar_background: MeshInstance3D
var _health_bar_fill: MeshInstance3D
var _health_label: Label3D
var _health_current := -1
var _health_maximum := -1
var _overhead_visible := true
var _settled := false
var _silhouette: OccludedSilhouette

# Visual layer 2. The gameplay camera renders layers 1 and 2; the full-map
# camera renders layers 1 and 3, and the minimap camera renders layer 1 alone.
const GAMEPLAY_ONLY_VISUAL_LAYER := 2
## Layer 3, which only the full-map camera renders. An actor's own body is a
## third of a pixel on a map that frames 1600 metres, so everyone standing on
## it needs a dot sized for the map rather than for the world. The minimap
## draws its own marks in pixels over its render, so that they hold their size
## through a zoom; see `minimap_marker_overlay.gd`.
const MAP_MARKER_LAYER := 4
const MAP_DOT_RADIUS := 6.0
## The light blue the full map's legend calls Player / NPC, written the way it
## writes it so a reader comparing the swatch to the map is comparing one
## colour to itself rather than to a rounding of it.
const MAP_DOT_COLOUR := Color("9fd2ff")
## An invasion creature's dot, and an ordinary creature's. Both are read off
## the map at a glance while something is coming for the player, so they are
## the two colours a map already means danger with: an invasion is the red one
## and the wildlife is the yellow one. Written the way the legend writes them,
## for the same reason MAP_DOT_COLOUR is.
const INVASION_MAP_DOT_COLOUR := Color("fa5a5a")
const CREATURE_MAP_DOT_COLOUR := Color("fcec38")
## The actor kind the server gives every creature - EL's
## PKABLE_COMPUTER_CONTROLLED. Players are HUMAN and scenery NPCs are NPC, so
## this is what separates the two creature dots from everybody else's.
const CREATURE_ACTOR_KIND := 5
## EL red3, the colour the server prefixes an invasion creature's name with.
## Nothing else on the wire says "invasion": the name's colour is how the
## legacy client knew to draw the banner red, and it is how this knows to draw
## the dot red. A summoned creature carries EL blue1 instead and is neither an
## invasion nor wildlife, so it keeps the ordinary actor dot.
const INVASION_NAME_COLOUR := 14
## EL blue1, the colour the server prefixes a summoned creature's name with.
## Like the invasion red above, the name's colour is the only thing on the
## wire that says what this creature is, and it is what tells a click on a
## summon apart from a click on wildlife.
const SUMMON_NAME_COLOUR := 4
const SETTLED_YAW_EPSILON := 0.0005

# Overhead health bar geometry, in world units, measured downwards from the
# nameplate so the name, the bar and the numbers read as one block.
const NAMEPLATE_HEIGHT := 2.15
const HEALTH_BAR_HEIGHT := 2.0
const HEALTH_LABEL_HEIGHT := 1.85
const HEALTH_BAR_WIDTH := 0.9
const HEALTH_BAR_THICKNESS := 0.085
const HEALTH_BAR_BORDER := 0.02

## Click target and selection ring for an actor standing on one tile.
## Both are scaled by the widest side of the footprint: a giant that can
## only be clicked on the middle tile of the nine it stands on is a giant
## players will keep missing, and a ring drawn around that one tile says
## the wrong thing about what is standing there.
const SELECTION_RADIUS := 0.45
## Width of the selection outline's border, in metres.
const RING_THICKNESS := 0.09
## How far a single-tile outline is inset from its tile's edges, so a
## rabbit's marker does not read as a solid square of floor.
const RING_INSET := 0.06

func configure(dto: Dictionary, adapter: CoordinateAdapter,
		model_config: Dictionary, animation_config: Dictionary,
		equipment_config: Dictionary = {}) -> Array[String]:
	actor_id = int(dto.actor_id)
	_metres_per_tile = maxf(0.01, adapter.metres_per_tile)
	footprint = dto.get("footprint", Vector2i.ONE) as Vector2i
	server_scale = maxf(0.01, float(dto.get("scale", 1.0)))
	server_target = adapter.footprint_center(
		int(dto.x), int(dto.y), footprint)
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
	capsule_shape.radius = SELECTION_RADIUS
	capsule_shape.height = 1.9
	selection_shape.shape = capsule_shape
	selection_shape.position.y = 0.95
	add_child(selection_shape)
	var selection_ring: MeshInstance3D = MeshInstance3D.new()
	selection_ring.name = "SelectionRing"
	var ring_material: StandardMaterial3D = StandardMaterial3D.new()
	ring_material.albedo_color = Color(0.95, 0.76, 0.18, 0.9)
	ring_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	ring_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	# Both faces: this is a flat decal on the ground and the winding
	# it is built with should not decide whether it can be seen.
	ring_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	selection_ring.material_override = ring_material
	selection_ring.position.y = 0.05
	selection_ring.visible = false
	# Gameplay-only visual layer. The minimap and full-map cameras cull it, so
	# neither top-down viewport pays for selection rings or nameplates it never
	# shows at their scale.
	selection_ring.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(selection_ring)
	_selection_ring = selection_ring
	_resize_selection()
	_add_nameplate(dto)
	_add_map_dot(dto)
	resolver = AnimationResolver.new(animation_config)
	_model_config = model_config.duplicate(true)
	_attachment_bones = (model_config.get("attachments", {}) as Dictionary).duplicate(true)
	_equipment_config = (equipment_config as Dictionary).duplicate(true)
	var source_path := _external_path(str(model_config.get("scene", "")))
	var errors := _load_native_scene(source_path)
	if not errors.is_empty():
		_add_fallback_visual(dto)
		# The native model never loaded, so the import adapter below will not
		# run and the scale would never be applied. A stand-in for a giant
		# should still be giant, and its nameplate still above it.
		_apply_model_scale()
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
			_attach_cape_cloth(skeleton)
			apply_appearance_variants(dto.get("appearance", {}) as Dictionary)
			var animation_path := _external_path(str(model_config.get("animationLibrary", "")))
			var imported := NativeAnimationImporter.import_library(self,
					animation_path, skeleton, model_config.get("boneAliases", {}),
					PackedStringArray(), resolver.looping_clips)
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
	# hair_color is independent of "hair", which now picks the style only.
	# Falls back to the style index when hair_color is absent -- an actor
	# from a server built before the field existed -- rather than to a
	# fixed colour, so hair still varies instead of every such actor
	# reading as the same near-black.
	var hair_tint: Color = AppearanceVariants.hair_color(
		int(appearance.get("hair_color", appearance.get("hair", 0))))
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
		elif mesh_name == "hair":
			_tint_mesh(mesh_node, hair_tint)
		elif mesh_name == "scalp":
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
		if WARDROBE_GROW.has(mesh_name):
			_grow_mesh(mesh_node, float(WARDROBE_GROW[mesh_name]))
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

## Lifts a garment off the skin it is fitted to. Reuses the override the tint
## pass already installed so a garment keeps its colour.
func _grow_mesh(mesh_node: MeshInstance3D, amount: float) -> void:
	if mesh_node.mesh == null or mesh_node.mesh.get_surface_count() == 0:
		return
	var material: StandardMaterial3D = (mesh_node.material_override
		as StandardMaterial3D)
	if material == null:
		var source: Material = mesh_node.get_active_material(0)
		if source is not StandardMaterial3D:
			return
		material = (source as StandardMaterial3D).duplicate()
		mesh_node.material_override = material
	material.grow = true
	material.grow_amount = amount

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
	# The chosen style replaces the sculpted hair, not sits on top of it:
	# the split body carries that hair as its own surface, so it hides.
	for node_value: Node in find_children("hair", "MeshInstance3D", true, false):
		(node_value as MeshInstance3D).visible = false
	attachment.name = "AppearanceHair_%d" % style
	native_hair.name = "NativeHair"
	# No scale compensation here: a bone attachment inherits whatever rest
	# scale its bone carries, and the head's size lives in its vertices
	# now, so a hairstyle mounted plainly is already the right size.  The
	# version that scaled by the head bone squared the growth and pushed
	# the style off the skull.
	attachment.add_child(native_hair)
	for node_value: Node in native_hair.find_children("*", "MeshInstance3D", true, false):
		_tint_mesh(node_value as MeshInstance3D, color)

func render_diagnostics() -> Dictionary:
	var meshes: Array[Dictionary] = []
	for node_value: Node in find_children("*", "MeshInstance3D", true, false):
		var mesh_node: MeshInstance3D = node_value as MeshInstance3D
		# Silhouette clones are copies of meshes already listed here; counting
		# them would double every surface the actor reports.
		if mesh_node.has_meta(OccludedSilhouette.CLONE_META):
			continue
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

## The dot this actor shows on the minimap and the full map. Every actor gets
## one: a player standing somewhere is the same kind of thing to read off a map
## as an NPC is, and the local player already has its own white mark drawn over
## the top of this one. Creatures are the exception, because what a player
## wants off a map during an invasion is where the invasion is - so a creature
## takes a colour of its own, and an invasion creature a third.
func _add_map_dot(dto: Dictionary) -> void:
	var dot: MeshInstance3D = MapMarkerDisc.build(
		"MapDot", MAP_DOT_RADIUS, map_dot_colour(dto))
	dot.position.y = 3.0
	add_child(dot)

## The map-dot colour a spawn packet asks for. Static and public so the map
## legend and the tests can name the same three colours this does rather than
## copies of them.
static func map_dot_colour(dto: Dictionary) -> Color:
	if int(dto.get("kind", 0)) != CREATURE_ACTOR_KIND:
		return MAP_DOT_COLOUR
	var name_colour: int = int(dto.get("name_colour", 0))
	if name_colour == INVASION_NAME_COLOUR:
		return INVASION_MAP_DOT_COLOUR
	# Only an uncoloured creature is wildlife. A summon is a creature the
	# server coloured, and it stays on the ordinary dot.
	return CREATURE_MAP_DOT_COLOUR if name_colour == 0 else MAP_DOT_COLOUR

## Whether a spawn packet describes a summoned creature. Static and public for
## the same reason `map_dot_colour` is: the world input and the tests should
## ask one question rather than each re-deriving it from the colour byte.
##
## It says a summon, not *whose* summon: the packet carries no owner. The
## server owns that answer and refuses a summon that is not yours, so a click
## only has to get this far to be worth sending.
static func is_summon(dto: Dictionary) -> bool:
	return (int(dto.get("kind", 0)) == CREATURE_ACTOR_KIND
		and int(dto.get("name_colour", 0)) == SUMMON_NAME_COLOUR)

## The nameplate. A guild tag arrives as part of the display name in the actor
## packet - "Alice ELO" - so a client that takes the whole string as a
## name renders the colour byte as mojibake and the tag as part of the player's
## name. The decoder splits them; this draws the tag as a tag.
##
## The name's colour is the server's, and it is how a field is read without
## selecting anything: a demigod's name is green, an invasion creature's red, a
## summon's light blue. A Label3D tints as one piece, so a guild tag takes the
## name's colour rather than its own.
func _add_nameplate(dto: Dictionary) -> void:
	var label: Label3D = Label3D.new()
	label.name = "Nameplate"
	var guild_tag: String = str(dto.get("guild_tag", ""))
	label.text = (str(dto.get("name", "Unknown actor"))
		+ ("  [%s]" % guild_tag if not guild_tag.is_empty() else ""))
	label.position.y = NAMEPLATE_HEIGHT
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.font_size = 28
	label.outline_size = 6
	label.modulate = EloriaProtocol.el_text_colour(int(dto.get("name_colour", 0)))
	label.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(label)
	_nameplate = label
	_add_health_bar()
	apply_vitals(int(dto.get("health", 0)), int(dto.get("max_health", 0)))

## The overhead health bar and its numbers. Every actor packet already carries
## the pair, so a creature's condition is knowable without selecting it: the
## combat HUD only ever describes the one target the player is fighting.
func _add_health_bar() -> void:
	var background: MeshInstance3D = MeshInstance3D.new()
	background.name = "HealthBarBackground"
	var background_quad: QuadMesh = QuadMesh.new()
	background_quad.size = Vector2(HEALTH_BAR_WIDTH + HEALTH_BAR_BORDER,
		HEALTH_BAR_THICKNESS + HEALTH_BAR_BORDER)
	background_quad.material = _overhead_material(Color(0.05, 0.04, 0.03, 0.78), 1)
	background.mesh = background_quad
	background.position.y = HEALTH_BAR_HEIGHT
	background.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(background)
	_health_bar_background = background
	var fill: MeshInstance3D = MeshInstance3D.new()
	fill.name = "HealthBarFill"
	var fill_quad: QuadMesh = QuadMesh.new()
	fill_quad.size = Vector2(HEALTH_BAR_WIDTH, HEALTH_BAR_THICKNESS)
	fill_quad.material = _overhead_material(Color(0.24, 0.78, 0.29, 1.0), 2)
	fill.mesh = fill_quad
	fill.position.y = HEALTH_BAR_HEIGHT
	fill.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(fill)
	_health_bar_fill = fill
	var numbers: Label3D = Label3D.new()
	numbers.name = "HealthNumbers"
	numbers.position.y = HEALTH_LABEL_HEIGHT
	numbers.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	numbers.no_depth_test = true
	numbers.render_priority = 3
	numbers.outline_render_priority = 2
	numbers.font_size = 24
	numbers.outline_size = 6
	numbers.layers = GAMEPLAY_ONLY_VISUAL_LAYER
	add_child(numbers)
	_health_label = numbers

## Billboarded, unshaded and depth-test free, so the bar reads the same against
## terrain, water and another actor standing in front of it. Draw order is the
## render priority rather than a depth offset: the quads share a plane and a
## z nudge would swap sides as the camera orbits.
func _overhead_material(colour: Color, priority: int) -> StandardMaterial3D:
	var material: StandardMaterial3D = StandardMaterial3D.new()
	material.albedo_color = colour
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	material.billboard_keep_scale = true
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.no_depth_test = true
	material.disable_receive_shadows = true
	material.render_priority = priority
	return material

## Redraws the bar for a health pair the server sent. An actor the server gives
## no maximum for - most scenery NPCs - has nothing to draw, so it keeps the
## bare name rather than an empty bar that would read as "about to die".
func apply_vitals(current: int, maximum: int) -> void:
	if current == _health_current and maximum == _health_maximum:
		return
	_health_current = current
	_health_maximum = maximum
	if not is_instance_valid(_health_bar_background) or not is_instance_valid(_health_bar_fill) \
			or not is_instance_valid(_health_label):
		return
	if maximum <= 0:
		_health_bar_background.visible = false
		_health_bar_fill.visible = false
		_health_label.visible = false
		return
	var clamped: int = clampi(current, 0, maximum)
	var ratio: float = float(clamped) / float(maximum)
	_health_bar_background.visible = _overhead_visible
	_health_label.visible = _overhead_visible
	_health_label.text = "%d/%d" % [clamped, maximum]
	var fill_quad: QuadMesh = _health_bar_fill.mesh as QuadMesh
	if clamped <= 0:
		_health_bar_fill.visible = false
	else:
		_health_bar_fill.visible = _overhead_visible
		var width: float = HEALTH_BAR_WIDTH * ratio
		fill_quad.size = Vector2(width, HEALTH_BAR_THICKNESS)
		# A QuadMesh is centred on its origin, so a shrinking bar would drain
		# from both ends. The offset pins the left edge instead, and it is a
		# mesh offset rather than a node position because the billboard shader
		# discards the node basis and would leave the nudge pointing at the
		# world axis the camera happened to start on.
		fill_quad.center_offset = Vector3(
			-(HEALTH_BAR_WIDTH - width) * 0.5, 0.0, 0.0)
		var material: StandardMaterial3D = fill_quad.material as StandardMaterial3D
		material.albedo_color = _health_colour(ratio)

static func _health_colour(ratio: float) -> Color:
	if ratio > 0.6:
		return Color(0.24, 0.78, 0.29, 1.0)
	if ratio > 0.3:
		return Color(0.93, 0.76, 0.16, 1.0)
	return Color(0.86, 0.21, 0.16, 1.0)

func set_nameplate_visible(enabled: bool) -> void:
	_overhead_visible = enabled
	if is_instance_valid(_nameplate):
		_nameplate.visible = enabled
	var has_health: bool = _health_maximum > 0
	if is_instance_valid(_health_bar_background):
		_health_bar_background.visible = enabled and has_health
	if is_instance_valid(_health_bar_fill):
		_health_bar_fill.visible = enabled and has_health and _health_current > 0
	if is_instance_valid(_health_label):
		_health_label.visible = enabled and has_health

## Eternal Lands repeats local chat over the speaker's head while "Show Speech
## Bubbles" is on (text.c check_chat_text_to_overtext), sitting above the
## banner rather than replacing it.
func show_speech_bubble(speech: String, duration_msec: int) -> void:
	if not is_instance_valid(_speech_bubble):
		var label: Label3D = Label3D.new()
		label.name = "SpeechBubble"
		label.position.y = 2.62
		label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		label.no_depth_test = true
		label.font_size = 24
		label.outline_size = 8
		label.width = 760.0
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.modulate = Color(0.86, 1.0, 0.86, 1.0)
		label.layers = GAMEPLAY_ONLY_VISUAL_LAYER
		add_child(label)
		_speech_bubble = label
	_speech_bubble.text = speech
	_speech_bubble.show()
	_speech_bubble_expiry_msec = Time.get_ticks_msec() + duration_msec

func clear_speech_bubble() -> void:
	_speech_bubble_expiry_msec = 0
	if is_instance_valid(_speech_bubble):
		_speech_bubble.hide()

## Restate how large this actor is drawn. Separate from `configure` for the
## same reason the footprint's setter is: the size can change after the
## model is built - an ordinary creature is promoted to an invasion boss
## and is redrawn larger without being respawned.
func set_server_scale(value: float) -> void:
	var next := maxf(0.01, value)
	if is_equal_approx(next, server_scale):
		return
	server_scale = next
	_apply_model_scale()

## The model's size is the two multipliers together: the client's import
## scale for this GLB, and what the server says this actor is. Applied to
## the model node rather than to the actor, so the nameplate, health bar,
## selection ring and map dot keep their own sizes - a giant's name should
## not be drawn in giant letters. Their heights do follow, below, or they
## would end up inside its head.
func _apply_model_scale() -> void:
	var total: float = _import_scale * server_scale
	for node_name: String in ["NativeModel", "MissingModelFallback"]:
		var model := get_node_or_null(node_name) as Node3D
		if model != null:
			model.scale = Vector3.ONE * total
	_lift_overhead(server_scale)

## Keep the overhead furniture above the model as it grows.
func _lift_overhead(factor: float) -> void:
	var heights := {
		"Nameplate": NAMEPLATE_HEIGHT,
		"HealthBarBackground": HEALTH_BAR_HEIGHT,
		"HealthBarFill": HEALTH_BAR_HEIGHT,
		"HealthNumbers": HEALTH_LABEL_HEIGHT,
	}
	for node_name: Variant in heights:
		var node := get_node_or_null(str(node_name)) as Node3D
		if node != null:
			node.position.y = float(heights[node_name]) * factor

## Restate how much ground this actor stands on, resizing what depends on
## it. Separate from `configure` because the footprint table is a login
## packet: if it lands after an actor has already been built, that actor
## corrects itself on the next state update instead of staying the wrong
## size until it walks out of view.
func set_footprint(value: Vector2i) -> void:
	var next := Vector2i(maxi(1, value.x), maxi(1, value.y))
	if next == footprint:
		return
	footprint = next
	_resize_selection()

## Grow the click target and the ground marker to the actor's own size.
func _resize_selection() -> void:
	var span: float = float(maxi(footprint.x, footprint.y))
	var shape: CollisionShape3D = get_node_or_null(
		"SelectionCollision") as CollisionShape3D
	if shape != null and shape.shape is CapsuleShape3D:
		(shape.shape as CapsuleShape3D).radius = SELECTION_RADIUS * span
	if _selection_ring != null:
		_selection_ring.mesh = footprint_outline(
			float(footprint.x) * _metres_per_tile,
			float(footprint.y) * _metres_per_tile)

## The ground an actor is standing on, drawn as the box the server
## actually reserved rather than as a circle around its middle.
##
## A circle could only ever suggest one tile: it says nothing about which
## way a rectangle lies, and for anything larger than a single tile it
## either overhangs the ground the creature holds or sits inside it. The
## outline is the box, so what is drawn under a creature is the same set
## of tiles the server will not let you walk through.
##
## Static so a test can build the same mesh and measure it without
## standing up an actor.
## Hold the marker square to the world while the actor turns inside it.
##
## A footprint is axis-aligned in world space and does not rotate - that
## is deliberate, because combat turns a creature on the spot and a box
## that swept round with it would have to be able to fail to turn. The
## marker is a child of the actor, so it inherits a yaw the ground it
## describes never has, and has to give it back. A circle never showed
## this; a rectangle shows it immediately.
func _level_selection_ring() -> void:
	if _selection_ring != null and _selection_ring.visible:
		_selection_ring.rotation.y = -rotation.y

static func footprint_outline(width_m: float, depth_m: float) -> ArrayMesh:
	var half_x: float = maxf(0.1, width_m * 0.5 - RING_INSET)
	var half_z: float = maxf(0.1, depth_m * 0.5 - RING_INSET)
	var thickness: float = minf(RING_THICKNESS,
		minf(half_x, half_z) * 0.9)
	var outer: Array[Vector3] = [
		Vector3(-half_x, 0.0, -half_z), Vector3(half_x, 0.0, -half_z),
		Vector3(half_x, 0.0, half_z), Vector3(-half_x, 0.0, half_z)]
	var inner_x: float = half_x - thickness
	var inner_z: float = half_z - thickness
	var inner: Array[Vector3] = [
		Vector3(-inner_x, 0.0, -inner_z), Vector3(inner_x, 0.0, -inner_z),
		Vector3(inner_x, 0.0, inner_z), Vector3(-inner_x, 0.0, inner_z)]
	var vertices := PackedVector3Array()
	var normals := PackedVector3Array()
	for side: int in range(4):
		var next: int = (side + 1) % 4
		for point: Vector3 in [outer[side], outer[next], inner[next],
				outer[side], inner[next], inner[side]]:
			vertices.append(point)
			normals.append(Vector3.UP)
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = vertices
	arrays[Mesh.ARRAY_NORMAL] = normals
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	return mesh

func apply_server_state(dto: Dictionary, adapter: CoordinateAdapter, teleport := false) -> void:
	if not is_equal_approx(_metres_per_tile, adapter.metres_per_tile):
		_metres_per_tile = maxf(0.01, adapter.metres_per_tile)
		_resize_selection()
	if dto.has("footprint"):
		set_footprint(dto.get("footprint") as Vector2i)
	if dto.has("scale"):
		set_server_scale(float(dto.get("scale")))
	var next_target: Vector3 = adapter.footprint_center(
		int(dto.x), int(dto.y), footprint)
	# Server movement contains tile coordinates only. Keep the last sampled
	# rendered-surface height until Main performs the ray sample for the new tile;
	# otherwise each packet temporarily pushes actors back to the flat manifest
	# fallback and can leave them visibly embedded in sculpted terrain.
	next_target.y = server_target.y
	var target_changed: bool = server_target.distance_squared_to(next_target) > 0.000001
	server_target = next_target
	var actor_command: int = int(dto.get("command", -1))
	# Which command the facing comes from, and which it does not. Everything
	# arriving in one socket read is reduced to a single state and rendered
	# once, so the last command of a frame is rarely the one that named a
	# direction: a creature sends the turn that puts it on its target and the
	# swing that follows it in the same flush, and reading the facing off the
	# last command threw the turn away every round. The reducer keeps the last
	# directional command of the burst apart for exactly this.
	var facing_command: int = int(dto.get("facing_command", actor_command))
	# The server has answered a predicted turn. Drop the prediction so the
	# rendered facing is the authoritative one from here on.
	if _predicted_turn_pending and EloriaProtocol.is_turn_command(facing_command):
		_predicted_turn_pending = false
	var authoritative_yaw: float = target_yaw_for_state(
		_target_yaw, facing_command, int(dto.rotation), adapter)
	_target_yaw = _predicted_turn_yaw if _predicted_turn_pending else authoritative_yaw
	_hastened = (int(dto.get("buffs", 0))
		& EloriaProtocol.ACTOR_BUFF_DOUBLE_SPEED) != 0
	_presentation_speed = walk_presentation_speed
	if _hastened or (actor_command >= 30 and actor_command <= 37):
		_presentation_speed = run_presentation_speed
	if teleport or global_position.distance_to(server_target) > 8.0:
		global_position = server_target
		rotation.y = _target_yaw
		_segment_start = server_target
		_segment_elapsed = 0.0
		_segment_duration = 0.0
		_last_movement_update_msec = -1
		_smoothed_server_interval = initial_server_interval
		_movement_coast_remaining = 0.0
		_snap_pending = false
		_travel_yaw_active = false
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
			# A long stationary pause is idle time, not a cadence. Folding it
			# in would pace the next burst by how long the player stood still,
			# and resetting to the constant lurched the first step of every
			# burst at any pace but the walking one. The measured pace is kept
			# instead: standing still is not what changes it - #run and #walk
			# are, and the step after those corrects it.
		_last_movement_update_msec = now_msec
		_segment_start = global_position
		_segment_elapsed = 0.0
		_movement_coast_remaining = 0.0
		_segment_duration = presentation_segment_duration(
			global_position.distance_to(server_target), _presentation_speed,
			_smoothed_server_interval, arrival_margin,
			minimum_segment_duration, maximum_segment_duration)
		_travel_yaw = travel_yaw(_segment_start, server_target, _target_yaw)
		_travel_yaw_active = true
	_wake()
	if dto.has("command") and resolver != null:
		play_action(_movement_aware_action(
			_paced_travel_action(resolver.action_for_command(actor_command)),
			target_changed))
	apply_equipment_visuals(dto.get("equipment_visuals", {}) as Dictionary,
		dto.get("equipment_fallback_parts", []) as Array)

## A movement command that moves the actor nowhere is the server restating the
## last one, not a step. Taken at face value it restarted the walk clip on every
## such packet, so an actor that had stopped kept walking on the spot forever.
func _movement_aware_action(action: StringName,
		target_changed: bool) -> StringName:
	if action not in [&"walk", &"run"]:
		return action
	if target_changed or _segment_duration > 0.0 or _movement_coast_remaining > 0.0:
		return action
	return &"idle"

## Walking is the ordinary pace, so the walk commands the server sends for every
## step resolve to the walk clip. Speed Hax is what makes an actor run: it halves
## the server's move interval without ever naming a run command, so the buff -
## not the command - is what promotes the travel action to a run.
func _paced_travel_action(action: StringName) -> StringName:
	if _hastened and action == &"walk":
		return &"run"
	return action

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
	# Equipment adds and removes mesh instances, so the silhouette's clone set
	# has to be built again against what the actor is now made of.
	if _silhouette != null and _silhouette.is_enabled():
		_silhouette.rebuild()

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
	if part == CAPE_PART:
		_set_cape_cloth_active(false)

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
	# Visual 0 is "nothing equipped".  On a wardrobe slot that used to mean a
	# generic shirt, pants or boots, because the shipped bodies were nude
	# under their Wardrobe_* meshes.  The race bodies now carry their clothing
	# in their own texture, so an empty slot is the body itself -- and drawing
	# the generic garment would put a second set of clothes over a painted one.
	# Marked per part in equipment.json, so a slot that must always show
	# something is unaffected.  Returning here also skips the fallback: bare is
	# the intended result, not a missing model.
	if visual_id == 0 and bool(part_config.get("bareWhenEmpty", false)):
		return
	var model_config: Dictionary = _equipment_model_config(part, visual_id)
	var created: Array[Node] = []
	if not model_config.is_empty():
		var scene_path: String = str(model_config.get("scene", ""))
		if str(model_config.get("attach", "socket")) == "skinned":
			created.append_array(_attach_skinned_equipment(scene_path, part, visual_id,
				model_config.get("tint", []) as Array,
				str(model_config.get("authoredFor", "")),
				str(model_config.get("skinRegion", ""))))
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
	if part == CAPE_PART:
		_set_cape_cloth_active(not created.is_empty())

## Cloth for the cape chains. A SkeletonModifier3D so the engine runs it once
## the animation has posed the skeleton - writing bone poses from _process
## would race the AnimationPlayer - and inactive, and therefore free, until a
## cape is actually worn.
func _attach_cape_cloth(skeleton: Skeleton3D) -> void:
	if skeleton.find_bone("cape_c_01") < 0:
		return
	if skeleton.get_node_or_null("CapeCloth") != null:
		return
	var cloth: SkeletonModifier3D = (
		load("res://src/actors/cape_cloth.gd") as Script).new()
	cloth.name = "CapeCloth"
	cloth.active = false
	skeleton.add_child(cloth)
	_cape_cloth = cloth

func _set_cape_cloth_active(enabled: bool) -> void:
	if _cape_cloth == null:
		return
	if enabled and not _cape_cloth.active:
		_cape_cloth.call("reset")
	_cape_cloth.active = enabled

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
	if _silhouette != null:
		_silhouette.sync()

## Draws the actor's shape over anything hiding it from the camera. Only ever
## switched on for the local player - see OccludedSilhouette.
func set_occlusion_silhouette_enabled(enabled: bool) -> void:
	if _silhouette == null:
		if not enabled:
			return
		_silhouette = OccludedSilhouette.new(self, _native_skeleton)
	_silhouette.set_enabled(enabled)

func occlusion_silhouette_enabled() -> bool:
	return _silhouette != null and _silhouette.is_enabled()

func get_skeleton() -> Skeleton3D:
	return _native_skeleton

func _equipment_model_config(part: int, visual_id: int) -> Dictionary:
	var aliases: Dictionary = _equipment_config.get("aliases", {}) as Dictionary
	var model_key: String = "%d:%d" % [part, visual_id]
	model_key = str(aliases.get(model_key, model_key))
	var models: Dictionary = _equipment_config.get("models", {}) as Dictionary
	var model: Dictionary = models.get(model_key, {}) as Dictionary
	return _fit_variant(model)

## The race this actor's body was built as, which is what the registry keys its
## fit groups and its body measurements on.
func rig_name() -> String:
	return str(_model_config.get("scene", "")).get_file().get_basename()

## The fit groups this actor's race belongs to, in precedence order.
##
## Modified 2026-08-29 for Eloria Client: this used to be a single name. A race
## can differ from the reference body in more than one way - a Ssarathi female
## has both a digitigrade leg and a bust, and the two are authored on different
## rigs - so a race now names every group it is in and a garment resolves the
## first one it actually ships a variant for. A registry written the old way,
## with one name per race, still reads correctly.
func fit_groups() -> PackedStringArray:
	var groups: Dictionary = _equipment_config.get("fitGroups", {}) as Dictionary
	var mine: Variant = groups.get(rig_name(), "")
	if mine is Array:
		var names := PackedStringArray()
		for value: Variant in mine as Array:
			names.append(str(value))
		return names
	var single := str(mine)
	return PackedStringArray() if single.is_empty() else PackedStringArray([single])

func _fit_variant(model: Dictionary) -> Dictionary:
	# Modified 2026-08-28 for Eloria Client: some builds cannot be reached by
	# resizing a garment, only by authoring one.  A race in a fit group wears
	# the copy of the piece built on its own rig where one exists, and the
	# reference piece everywhere else, so a group only costs the kinds it
	# actually changes.
	if model.is_empty():
		return model
	var variants: Dictionary = model.get("variants", {}) as Dictionary
	for group: String in fit_groups():
		var variant: Dictionary = variants.get(group, {}) as Dictionary
		if variant.is_empty():
			continue
		var resolved: Dictionary = model.duplicate(true)
		resolved.erase("variants")
		resolved.merge(variant, true)
		return resolved
	return model

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
		tint: Array = [], author_rig: String = "",
		skin_region: String = "") -> Array[Node]:
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
	var ground: Dictionary = _ground_drops(author_rig, skin_region)
	for piece_value: Variant in _equipment_pieces(scene_path):
		var piece: Dictionary = piece_value as Dictionary
		var surface_key: String = "%s|%s" % [cache_key, str(piece.get("name", ""))]
		var rebound: Skin = _rebound_skins.get(surface_key) as Skin
		if rebound == null:
			rebound = _rebound_skin(piece.get("bones", PackedStringArray()) as PackedStringArray,
				piece.get("binds", [] as Array[Transform3D]) as Array[Transform3D],
				fit_basis, _girth_ratios(author_rig), ground)
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

## How much wider this actor is than the body a garment was lofted around, bone
## by bone. Empty when the two are the same rig, or when either is unmeasured -
## an unknown body is worn as authored rather than guessed at.
##
## Only ever a widening. A garment is cut close to the reference body, so
## letting it out for a broader wearer is safe while taking it in is not: the
## measurement is one number for a whole bone, and a chest it underestimates
## would come straight through the shirt.
func _girth_ratios(author_rig: String) -> Dictionary:
	var mine: String = rig_name()
	if author_rig.is_empty() or author_rig == mine:
		return {}
	var table: Dictionary = _equipment_config.get("bodyGirth", {}) as Dictionary
	var author: Dictionary = table.get(author_rig, {}) as Dictionary
	var wearer: Dictionary = table.get(mine, {}) as Dictionary
	if author.is_empty() or wearer.is_empty():
		return {}
	var ratios: Dictionary = {}
	for bone: String in author:
		var from: float = float(author[bone])
		var to: float = float(wearer.get(bone, 0.0))
		if from > 0.0005 and to > 0.0005:
			ratios[bone] = clampf(to / from, 1.0, 2.0)
	return ratios

## How far this actor's foot joints stand above the floor, against the body a
## boot was lofted around. Empty for everything that is not footwear.
##
## The rest of the refit scales each bone about its own origin, and for the foot
## chain that origin is the ankle - which is not a fixed height above the
## ground. It stands 91 to 103 mm up on every male rig in the cast and only 78.6
## to 83.4 mm on every female one. Stature does not predict that: the female
## rigs are three per cent shorter overall and twenty per cent shorter from
## ankle to sole, so a sole authored on the reference body and scaled by height
## landed 14 mm through the floor on all seven of them, and no single authored
## mesh could have fixed it.
##
## A vector, and a move rather than a scale, which is the whole point.
##
## Measured across the cast the foot barely varies: every female foot is within
## four per cent of its male counterpart's width and seven per cent of its
## length. What varies is where it sits relative to the joint that carries it -
## the ankle stands 91 to 103 mm above the floor on the male rigs and 78.6 to
## 83.4 on the female ones, and the Orun ankle sits 26 mm further inboard than
## the reference's with the foot still under the body. Scaling a boot to close
## the first would take eighteen per cent off a shell that has to contain a foot
## four per cent *wider*, and no scale at all reaches the second. Moving the
## shell instead lands it and leaves the fit alone.
func _ground_drops(author_rig: String, skin_region: String) -> Dictionary:
	if skin_region != "boots":
		return {}
	var mine: String = rig_name()
	if author_rig.is_empty() or author_rig == mine:
		return {}
	var table: Dictionary = _equipment_config.get("footAnchor", {}) as Dictionary
	var author: Dictionary = table.get(author_rig, {}) as Dictionary
	var wearer: Dictionary = table.get(mine, {}) as Dictionary
	if author.is_empty() or wearer.is_empty():
		return {}
	# Per bone, not one datum for the whole chain. Collapsing them onto the
	# ankle's figure was tried, on the reasoning that a boot is rigid and should
	# travel as one piece; measured, it was five times worse - 951 body vertices
	# outside the shell against 185. The shell is skinned rather than rigid, and
	# letting each bone carry its own offset is what lands the ankle and the ball
	# of the foot in the right place at once.
	var drops: Dictionary = {}
	for bone: String in author:
		var from: Vector3 = _vector3(author[bone] as Array, Vector3.ZERO)
		var to: Vector3 = _vector3(wearer.get(bone, []) as Array, Vector3.ZERO)
		if from != Vector3.ZERO and to != Vector3.ZERO:
			# The pair, not the difference: how far the boot has to move depends
			# on how much it has been widened first, and that is decided in
			# `_bone_fit` where the girth ratio is known.
			drops[bone] = [from, to]
	return drops

func _rebound_skin(bone_names: PackedStringArray, binds: Array[Transform3D],
		fit: Transform3D, girth: Dictionary = {},
		ground: Dictionary = {}) -> Skin:
	# Modified 2026-08-28 for Eloria Client: this used to hand every bone the
	# bind `this_rest.inverse() * fit`.  Skinning then evaluates
	# `pose * bind`, and at rest `pose` *is* `this_rest`, so the whole thing
	# collapsed to `fit` - a uniform scale about the floor.  A garment was never
	# retargeted at all, only resized, which is why boots authored on a
	# plantigrade leg stayed at ankle height on the Ssarathi's digitigrade one
	# and left their feet outside the boot.  Keeping the garment's *authored*
	# bind instead makes `pose * bind` carry each vertex from the bone it was
	# modelled on to the same bone here, so the piece follows this rig's rest
	# pose.  The fit scale stays, applied in bone space, so a shorter race still
	# wears a proportionally slimmer garment.
	#
	# The mesh's JOINTS_0 values index this bind array, so a bind may never be
	# skipped: dropping one would shift every later bone by a slot. A garment
	# whose rig this actor does not carry is refused outright instead.
	if bone_names.is_empty():
		return null
	var author_rest: Dictionary = {}
	for index: int in range(bone_names.size()):
		if index < binds.size():
			author_rest[bone_names[index]] = binds[index].affine_inverse()
	var rebound: Skin = Skin.new()
	for index: int in range(bone_names.size()):
		var bone_name: String = bone_names[index]
		var target: int = _native_skeleton.find_bone(bone_name)
		if bone_name.is_empty() or target < 0:
			return null
		if index < binds.size():
			rebound.add_named_bind(bone_name,
				_bone_fit(target, bone_name, author_rest, fit,
					float(girth.get(bone_name, 1.0)),
					ground.get(bone_name, []) as Array,
					_native_skeleton.get_bone_global_rest(target)) * binds[index])
		else:
			# No authored bind survived the import: fall back to the resize so
			# the piece still appears rather than collapsing onto the origin.
			rebound.add_named_bind(bone_name,
				_native_skeleton.get_bone_global_rest(target).affine_inverse() * fit)
	return rebound

func _bone_fit(target: int, bone_name: String, author_rest: Dictionary,
		fit: Transform3D, girth: float = 1.0, ground: Array = [],
		wearer_rest: Transform3D = Transform3D.IDENTITY) -> Transform3D:
	# Carrying a garment onto another rig by rotation alone leaves it the length
	# it was authored, which is fine while the two rigs agree and wrong when
	# they do not: the Ssarathi metatarsal is nearly half again as long as the
	# one the boots were built on, so the boot ran out partway along the foot
	# and the rest of it - toes and claws - came out the front.  Each bone's
	# span is compared against the span it was authored with and the garment is
	# stretched along that bone to match.  Bones the two rigs agree on get a
	# ratio of one and are left exactly as authored.
	var rest: Transform3D = author_rest.get(bone_name, Transform3D.IDENTITY)
	var author_tip: Vector3 = _mean_child_origin(target, author_rest, true)
	var target_tip: Vector3 = _mean_child_origin(target, author_rest, false)
	var ratio: float = 1.0
	var axis := Vector3(0.0, 1.0, 0.0)
	var measured := false
	if author_tip != Vector3.INF and target_tip != Vector3.INF:
		var local: Vector3 = rest.affine_inverse() * author_tip
		var author_span: float = local.length()
		var target_span: float = (target_tip
			- _native_skeleton.get_bone_global_rest(target).origin).length()
		if author_span > 0.0005 and target_span > 0.0005:
			ratio = clampf(target_span / author_span, 0.4, 2.5)
			axis = local / author_span
			measured = true
	# A foot bone carrying a ground ratio takes it instead of the span-and-girth
	# result, and takes it whether it widens or narrows. Everything else here is
	# a guess at how much bigger this body is than the authored one; that is the
	# measured distance between the joint and the floor it has to stand on, and
	# the floor is not negotiable - the actor is placed on the ground by its
	# body, so a boot that disagrees is a boot underneath it. It stays isotropic:
	# the ground ratio is chosen to land the sole, and splitting it would move
	# the sole off the plane it was solved for.
	# A foot bone carrying a ground datum is *moved* onto this body rather than
	# scaled onto it. It is still widened first, because some feet genuinely are
	# broader - an Orun's is twelve per cent wider than the reference - and a
	# shell that does not grow for them leaves the outside of the foot showing.
	# Widening and then moving is why the anchor arrives as a pair rather than a
	# difference: how far the boot has to travel depends on how much bigger it
	# has just been made.
	if ground.size() == 2:
		var wide: float = clampf(maxf(ratio, girth), 1.0, 2.0)
		var scaled: float = fit.basis.get_scale().y * wide
		# The anchor is a signed offset from the joint to the foot, so all three
		# axes read the same way: where the authored foot lands once scaled onto
		# this body, subtracted from where this body's foot actually is. Y is
		# measured to the floor because standing on the ground has to be exact;
		# X and Z to the middle of the foot, which is what puts an Orun's boot
		# around an Orun's foot rather than around the joint it hangs from.
		var landed: Vector3 = (ground[0] as Vector3) * scaled
		var wanted: Vector3 = ground[1] as Vector3
		return Transform3D(fit.basis.scaled(Vector3.ONE * wide),
			wearer_rest.basis.inverse() * (wanted - landed))

	# Widening and lengthening are two different questions and used to be
	# answered with one number.
	#
	# Modified 2026-08-29 for Eloria Client. The scale below is applied in the
	# authored bone's own space, which anchors it at the bone origin, and
	# `calf`'s origin is the knee. Letting an Orun's calf out by the thirty per
	# cent its girth asks for therefore also made the calf thirty per cent
	# longer, and every trouser hem hangs near the far end of that bone: the
	# hems landed 118 to 124 mm below where they belong on the two broadest
	# races, and a boot's sole vertex inheriting the body's own heel weighting -
	# 31 per cent `calf` - was dragged 62 mm under the floor by the same term.
	#
	# The obvious repair, translating the bone's contribution back along its own
	# axis until the joint below lands correctly, moves the error rather than
	# removing it: a translation displaces the bone origin as much as its tip,
	# so the hem is fixed and the knee - where this bone's geometry is blended
	# with its parent's, which was never displaced - opens up by the same amount.
	# The seam moves instead of the hem.
	#
	# So the two questions are answered separately. Along the bone the garment
	# follows the span ratio, which puts the joint below exactly where the
	# wearer's own skeleton puts it and leaves the bone origin fixed. Around the
	# bone it follows girth, and still only ever widens.
	#
	# This is the anisotropy the previous note here refused, and the reason it
	# is safe now is that the axis is the bone's, not the world's. Skinning
	# carries normals through this same matrix, and a scale that is uniform in
	# the plane perpendicular to the bone leaves every radial normal - which is
	# very nearly all of them on a sleeve, a trouser leg or a boot shaft -
	# pointing exactly where it did. What tilts is the oblique minority, by at
	# most eight degrees at the widest girth in the cast. The black band that
	# came of the earlier attempt came of stretching *along* the spine, which is
	# the direction this one deliberately leaves alone.
	var across: float = clampf(maxf(ratio, girth), 1.0, 2.0)
	# A leaf bone has no joint below it to measure a span against, so there is
	# no axis to separate along from across and it stays isotropic.
	var along: float = across if not measured else clampf(ratio, 0.4, 2.5)
	if absf(across - 1.0) < 0.02 and absf(along - 1.0) < 0.02:
		return fit
	# across * I, corrected along the bone axis by (along - across).
	var basis := Basis.IDENTITY.scaled(Vector3.ONE * across)
	var shaped := Basis(
		basis.x + axis * (along - across) * axis.x,
		basis.y + axis * (along - across) * axis.y,
		basis.z + axis * (along - across) * axis.z)
	return Transform3D(fit.basis * shaped, Vector3.ZERO)

func _mean_child_origin(target: int, author_rest: Dictionary,
		authored: bool) -> Vector3:
	# The bone's tip: where its children sit, on whichever rig was asked for.
	# Vector3.INF means the bone is a leaf on one of the two rigs, and a leaf
	# has no span to compare.
	var total := Vector3.ZERO
	var found: int = 0
	for child: int in _native_skeleton.get_bone_children(target):
		var child_name: String = _native_skeleton.get_bone_name(child)
		if not author_rest.has(child_name):
			continue
		total += ((author_rest[child_name] as Transform3D).origin if authored
			else _native_skeleton.get_bone_global_rest(child).origin)
		found += 1
	return total / float(found) if found > 0 else Vector3.INF

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
	animation_player.speed_scale = _playback_speed_for(action)
	if current_action == action and animation_player.is_playing():
		return
	current_action = action
	animation_player.play(clip, action_blend_seconds)
	# Retarget the facing correction to this action and ease to it over the same
	# crossfade the clips blend across, so the body's turn tracks the pose change
	# rather than snapping ahead of or behind it.
	var target: float = deg_to_rad(resolver.facing_offset_for_action(action))
	if not is_equal_approx(target, _facing_offset_to):
		_facing_offset_from = _facing_offset
		_facing_offset_to = target
		_facing_offset_elapsed = 0.0
		_wake()

## Walk and run clips animate in place, so the feet only stay planted when the
## clip runs at the speed the actor is actually travelling. Anything else -
## and a fixed 1.45 on a clip that covers 0.61 m/s while the server walks an
## actor at 1.86 m/s was a long way else - reads as sliding.
##
## The ceiling is 3.5 so nothing in ordinary play reaches it. `Walk` covers
## 0.685 m/s at speed 1.0 against a walking pace of 1.67 m/s (2.43x), and
## `Run_Female` covers 2.666 against a running 5.0 m/s (1.88x). Only Speed Hax
## on top of a run - 10 m/s - asks for more than the ceiling.
func _playback_speed_for(action: StringName) -> float:
	var stride: float = resolver.stride_speed_for_action(action)
	if stride <= 0.0:
		return resolver.playback_speed_for_action(action)
	return clampf(_travel_speed() / stride, 0.35, 3.5)

## Metres per second the presentation is currently moving this actor. Falls
## back to the nominal speed for the command before the first step is timed.
func _travel_speed() -> float:
	if _segment_duration <= 0.0:
		return _presentation_speed
	return _segment_start.distance_to(server_target) / _segment_duration

func _on_animation_finished(_animation_name: StringName) -> void:
	# The server sends transition commands, not a second command for the resting
	# pose. Keep this explicit and data-driven through the action map.
	if current_action == &"sit":
		play_action(&"seated_idle")
	elif current_action == &"stand":
		play_action(&"idle")

## Shows one 45 degree step immediately while the server's answer to
## TURN_LEFT/TURN_RIGHT is in flight. This is prediction, not authority: the
## first turn actor command the server broadcasts clears it and the
## authoritative facing takes over. Nothing here decides an outcome.
func predict_turn(radians: float) -> void:
	_wake()
	_target_yaw = wrapf(_target_yaw + radians, -PI, PI)
	_predicted_turn_yaw = _target_yaw
	_predicted_turn_pending = true
	play_action(&"turn")

func desired_facing_yaw() -> float:
	return _target_yaw

## Abandons a predicted turn the server has not answered. A route ordered
## before the answer arrives supersedes it: the step commands that route
## broadcasts state the facing, and holding the prediction over them would keep
## the actor pointing where it was asked to look rather than where it walks.
func clear_turn_prediction() -> void:
	_predicted_turn_pending = false

static func target_yaw_for_state(current_yaw: float, actor_command: int,
		server_rotation: int, adapter: CoordinateAdapter) -> float:
	var command_direction: Vector2i = EloriaProtocol.actor_command_direction(actor_command)
	if command_direction != Vector2i.ZERO:
		return adapter.direction_to_godot(command_direction)
	# Every other actor command - sitting, standing, entering combat, swinging
	# at someone - carries no rotation of its own. The rotation on the state is
	# the one the actor was last spawned with, so reading it here threw away
	# the facing the actor had been turned to: a creature that turned to face
	# the player it was attacking snapped back to its spawn facing on the very
	# next attack command it sent. Only a spawn packet, which carries no
	# command at all, states a facing this way.
	if actor_command >= 0:
		return current_yaw
	return adapter.rotation_to_godot(server_rotation)

## The yaw of the ground the body is about to cross, which is what "facing the
## way you are walking" means on screen. It is not the tile direction the
## server named: the rendered actor is deliberately a fraction of a tile behind
## its authoritative position (`arrival_margin`), and every step that lands in
## the same frame as another is folded into one segment before the actor node
## sees it, so a segment routinely spans a different bearing - and, across a
## folded burst, several tiles - than the single command that arrived with it.
static func travel_yaw(from: Vector3, to: Vector3, fallback: float) -> float:
	var travel := Vector3(to.x - from.x, 0.0, to.z - from.z)
	if travel.length_squared() < 0.000001:
		return fallback
	return atan2(-travel.x, -travel.z)

## Where the body is pointed this frame. The authoritative facing is still
## `_target_yaw`; this only decides what is drawn while the actor is crossing
## ground, and it hands back to the authoritative value the moment it stops, so
## a resting actor faces exactly where the server says it does. An unanswered
## turn prediction outranks it: that actor is turning on the spot rather than
## travelling, and the step it is asked to show is the whole point of it.
func _rendered_target_yaw() -> float:
	if _predicted_turn_pending or not _travel_yaw_active:
		return _target_yaw
	return _travel_yaw

func _finish_movement_presentation() -> void:
	if current_action in [&"walk", &"run"]:
		_movement_coast_remaining = maxf(movement_coast_seconds,
			_smoothed_server_interval * 0.75)

func set_selected(value: bool) -> void:
	if _selection_ring != null:
		_selection_ring.visible = value
		_level_selection_ring()

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
	if (_speech_bubble_expiry_msec > 0
			and Time.get_ticks_msec() >= _speech_bubble_expiry_msec):
		clear_speech_bubble()
	if _snap_pending:
		global_position = server_target
		rotation.y = _target_yaw
		_level_selection_ring()
		_segment_start = server_target
		_snap_pending = false
		_travel_yaw_active = false
		_settle_if_idle()
		return
	if _segment_duration > 0.0:
		_segment_elapsed = minf(_segment_elapsed + delta, _segment_duration)
		var progress: float = _segment_elapsed / _segment_duration
		global_position = _segment_start.lerp(server_target, progress)
		if progress >= 1.0:
			global_position = server_target
			_segment_duration = 0.0
			_travel_yaw_active = false
			_finish_movement_presentation()
	else:
		global_position = server_target
		_travel_yaw_active = false
	rotation.y = rotate_toward(rotation.y, _rendered_target_yaw(),
		turn_speed_radians * delta)
	_level_selection_ring()
	_advance_facing_offset(delta)
	if _movement_coast_remaining > 0.0:
		_movement_coast_remaining = maxf(0.0, _movement_coast_remaining - delta)
		if _movement_coast_remaining <= 0.0 and current_action in [&"walk", &"run"]:
			play_action(&"idle")
	_settle_if_idle()

## A standing actor reproduced the same transform 60 times a second. Once the
## interpolation segment has finished and the actor faces where the server says
## it should, the node is snapped exactly onto its target and physics processing
## stops until the next packet, keypress or surface sample wakes it. Nothing
## about the resulting pose differs from the value the loop kept rewriting.
func _settle_if_idle() -> void:
	if _snap_pending or _segment_duration > 0.0 or _movement_coast_remaining > 0.0:
		return
	if absf(wrapf(_target_yaw - rotation.y, -PI, PI)) > SETTLED_YAW_EPSILON:
		return
	# Do not stop processing until the facing correction has finished easing to
	# the resting action's value, or an actor caught mid-ease from a walk would
	# freeze holding the walk's turn.
	if not is_equal_approx(_facing_offset, _facing_offset_to):
		return
	global_position = server_target
	rotation.y = _target_yaw
	_settled = true
	set_physics_process(false)

## Eases the model's facing correction toward the current action's value across
## the animation crossfade and writes it onto the visual root. A no-op once the
## two agree, so a resting actor pays nothing for it.
func _advance_facing_offset(delta: float) -> void:
	if _native_model == null or is_equal_approx(_facing_offset, _facing_offset_to):
		return
	_facing_offset_elapsed += delta
	var progress: float = 1.0 if action_blend_seconds <= 0.0 else clampf(
		_facing_offset_elapsed / action_blend_seconds, 0.0, 1.0)
	_facing_offset = lerp_angle(_facing_offset_from, _facing_offset_to, progress)
	if progress >= 1.0:
		_facing_offset = _facing_offset_to
	_native_model.rotation.y = _base_model_yaw + _facing_offset

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
					"binds": _skin_bind_poses(mesh_node.skin),
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

static func _skin_bind_poses(skin: Skin) -> Array[Transform3D]:
	# The garment's own inverse bind poses: where each bone stood on the rig the
	# garment was authored against.  Retargeting needs them; the old rebind threw
	# them away and so could only ever scale the garment.
	var poses: Array[Transform3D] = []
	if skin == null:
		return poses
	for index: int in range(skin.get_bind_count()):
		poses.append(skin.get_bind_pose(index))
	return poses

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
	_import_scale = float(config.get("scale", 1.0))
	_apply_model_scale()
	# The two rig families are authored facing opposite ways: the race rigs
	# down +Z to face the creation-preview camera, the creature rigs down -Z,
	# which is already Godot's logical forward axis. Each model states its own
	# correction, so a creature is not turned round and walked backwards. The
	# 180 fallback is only for a model that predates the key. Correct only the
	# imported visual root so server yaw, click targets, keyboard-relative
	# movement, and equipment attachments continue to share one canonical
	# logical heading.
	var forward_axis_correction: float = float(
		config.get("forwardAxisCorrectionDegreesY", 180.0))
	model.rotation_degrees = Vector3(
		float(config.get("rotationDegreesX", 0.0)),
		float(config.get("rotationDegreesY", 0.0)) + forward_axis_correction,
		float(config.get("rotationDegreesZ", 0.0)))
	# The base the per-action facing correction is measured from. Kept in radians
	# because `_physics_process` adds the eased offset to it every frame.
	_native_model = model
	_base_model_yaw = deg_to_rad(model.rotation_degrees.y)
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
