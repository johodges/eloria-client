extends Control

@onready var login_panel: Control = %LoginPanel
@onready var game_view: Control = %GameView
@onready var creation_panel: Control = %CreationPanel
@onready var new_character_button: Button = %NewCharacter
@onready var create_name: LineEdit = %CreateName
@onready var create_password: LineEdit = %CreatePassword
@onready var create_confirm: LineEdit = %CreateConfirm
@onready var create_gender: OptionButton = %CreateGender
@onready var create_status: Label = %CreateStatus
@onready var preview_container: SubViewportContainer = %CharacterPreview
@onready var preview_root: Node3D = %PreviewRoot
@onready var preview_camera: Camera3D = %PreviewCamera
@onready var host_edit: LineEdit = %Host
@onready var port_edit: SpinBox = %Port
@onready var user_edit: LineEdit = %Username
@onready var password_edit: LineEdit = %Password
@onready var connect_button: Button = %Connect
@onready var login_button: Button = %Login
@onready var status_label: Label = %Status
@onready var world_root: Node3D = %WorldRoot
@onready var camera_rig: IsometricCameraController = %CameraRig
@onready var gameplay_camera: Camera3D = %Camera
@onready var world_loader: WorldLoader = %WorldLoader
@onready var fallback_ground: MeshInstance3D = $GameView/ViewportContainer/Viewport/WorldRoot/Ground
@onready var main_viewport: SubViewport = $GameView/ViewportContainer/Viewport
@onready var viewport_container: SubViewportContainer = $GameView/ViewportContainer
@onready var map_viewport: SubViewport = %MapViewport
@onready var map_camera: Camera3D = %MapCamera
@onready var full_map_viewport: SubViewport = %FullMapViewport
@onready var full_map_camera: Camera3D = %FullMapCamera
@onready var minimap: TextureRect = %Minimap
@onready var full_map: Control = %FullMap
@onready var map_image: TextureRect = %MapImage
@onready var health_bar: ProgressBar = %Health
@onready var health_text: Label = %HealthText
@onready var mana_bar: ProgressBar = %Mana
@onready var mana_text: Label = %ManaText
@onready var action_bar: ProgressBar = %Action
@onready var action_text: Label = %ActionText
@onready var health_bottom: ProgressBar = %HealthBottom
@onready var health_bottom_text: Label = %HealthBottomText
@onready var ether_bottom: ProgressBar = %EtherBottom
@onready var ether_bottom_text: Label = %EtherBottomText
@onready var food_bottom: ProgressBar = %FoodBottom
@onready var food_bottom_text: Label = %FoodBottomText
@onready var load_bottom: ProgressBar = %LoadBottom
@onready var load_bottom_text: Label = %LoadBottomText
@onready var action_bottom: ProgressBar = %ActionBottom
@onready var action_bottom_text: Label = %ActionBottomText
@onready var experience_bottom: ProgressBar = %ExperienceBottom
@onready var experience_bottom_text: Label = %ExperienceBottomText
@onready var bottom_meters: HBoxContainer = %BottomMeters
@onready var skill_indicators: RichTextLabel = %SkillIndicators
@onready var clock_text: Label = %ClockText
@onready var clock_hand: Line2D = %ClockHand
@onready var compass_needle: Line2D = %CompassNeedle
@onready var actor_resource_overlay: PanelContainer = %ActorResourceOverlay
@onready var actor_hud_menu: PanelContainer = %ActorHudMenu
@onready var overhead_player_name: Label = %OverheadPlayerName
@onready var overhead_health_row: HBoxContainer = %HealthRow
@onready var overhead_ether_row: HBoxContainer = %EtherRow
@onready var overhead_food_row: HBoxContainer = %FoodRow
@onready var overhead_action_row: HBoxContainer = %ActionRow
@onready var show_overhead_health: CheckButton = %ShowHealth
@onready var show_overhead_ether: CheckButton = %ShowEther
@onready var show_overhead_food: CheckButton = %ShowFood
@onready var show_overhead_action: CheckButton = %ShowAction
@onready var stats_panel: Control = %StatsPanel
@onready var stats_text: RichTextLabel = %StatsText
@onready var inventory_panel: Control = %InventoryPanel
@onready var inventory_grid: GridContainer = %InventoryGrid
@onready var equipment_grid: GridContainer = %EquipmentGrid
@onready var inventory_description: RichTextLabel = %InventoryDescription
@onready var inventory_use_button: Button = %InventoryUse
@onready var inventory_equip_button: Button = %InventoryEquip
@onready var inventory_unequip_button: Button = %InventoryUnequip
@onready var attack_button: Button = %AttackButton
@onready var trade_button: Button = %TradeButton
@onready var trade_panel: Control = %TradePanel
@onready var trade_partner: Label = %TradePartner
@onready var trade_source: ItemList = %TradeSource
@onready var trade_own_offers: ItemList = %TradeOwnOffers
@onready var trade_other_offers: ItemList = %TradeOtherOffers
@onready var trade_quantity: SpinBox = %TradeQuantity
@onready var trade_status: Label = %TradeStatus
@onready var trade_offer_button: Button = %TradeOffer
@onready var trade_remove_button: Button = %TradeRemove
@onready var trade_accept_button: Button = %TradeAccept
@onready var trade_reject_button: Button = %TradeReject
@onready var trade_storage_destination: CheckBox = %TradeStorageDestination
@onready var storage_panel: Control = %StoragePanel
@onready var storage_categories: ItemList = %StorageCategories
@onready var storage_items: ItemList = %StorageItems
@onready var storage_inventory: ItemList = %StorageInventory
@onready var storage_quantity: SpinBox = %StorageQuantity
@onready var storage_status: Label = %StorageStatus
@onready var storage_deposit_button: Button = %StorageDeposit
@onready var storage_withdraw_button: Button = %StorageWithdraw
@onready var storage_inspect_button: Button = %StorageInspect
@onready var ground_bag_panel: Control = %GroundBagPanel
@onready var ground_bag_items: ItemList = %GroundBagItems
@onready var ground_bag_inventory: ItemList = %GroundBagInventory
@onready var ground_bag_quantity: SpinBox = %GroundBagQuantity
@onready var ground_bag_pick_button: Button = %GroundBagPick
@onready var ground_bag_drop_button: Button = %GroundBagDrop
@onready var knowledge_panel: Control = %KnowledgePanel
@onready var knowledge_list: ItemList = %KnowledgeList
@onready var knowledge_detail: RichTextLabel = %KnowledgeDetail
@onready var knowledge_known_only: CheckBox = %KnowledgeKnownOnly
@onready var manufacturing_panel: Control = %ManufacturingPanel
@onready var manufacturing_filter: LineEdit = %ManufacturingFilter
@onready var manufacturing_list: ItemList = %ManufacturingList
@onready var manufacturing_detail: RichTextLabel = %ManufacturingDetail
@onready var manufacturing_status: Label = %ManufacturingStatus
@onready var manufacturing_mix_one: Button = %ManufacturingMixOne
@onready var manufacturing_mix_all: Button = %ManufacturingMixAll
@onready var quick_slot_container: GridContainer = %ItemSlots
@onready var spell_slot_container: GridContainer = %SpellSlots
@onready var spell_status: Label = %SpellStatus
@onready var player_map_marker: MeshInstance3D = %PlayerMapMarker
@onready var map_label: Label = %MapLabel
@onready var actor_label: Label = %ActorLabel
@onready var chat_output: RichTextLabel = %ChatOutput
@onready var chat_input: LineEdit = %ChatInput
@onready var selected_target: Label = %SelectedTarget
@onready var dialogue_panel: Control = %DialoguePanel
@onready var dialogue_name: Label = %DialogueName
@onready var dialogue_text: RichTextLabel = %DialogueText
@onready var dialogue_options: VBoxContainer = %DialogueOptions
@onready var login_background: TextureRect = %LoginBackground
@onready var login_logo: TextureRect = %LoginLogo

var actor_nodes: Dictionary = {}
var ground_bag_nodes: Dictionary = {}
var models: Dictionary = {}
var actor_type_models: Dictionary = {}
var npc_looks: Dictionary = {}
var creation_options: Array = []
var animation_config: Dictionary = {}
var animation_configs: Dictionary = {}
var map_registry: Dictionary = {}
var equipment_config: Dictionary = {}
var item_atlas := ItemAtlas.new()
var spell_catalog := SpellCatalog.new()
var manufacturing_catalog := ManufacturingCatalog.new()
var knowledge_catalog: Array[String] = []
var gameplay_world: World3D
var loaded_server_map := ""
var adapter := CoordinateAdapter.new({"walkingHeight": 0.0, "invertServerY": true})
var preview_actor: ReplicatedActor3D
var pending_create_username := ""
var pending_create_password := ""
var preview_yaw := 0.0
var preview_pitch := 0.12
var preview_distance := 4.2
var inventory_slot_buttons: Array[Button] = []
var equipment_slot_buttons: Array[Button] = []
var quick_slot_buttons: Array[Button] = []
var spell_slot_buttons: Array[Button] = []
var selected_inventory_slot := -1
var selected_trade_side := ""
var trade_destinations: PackedByteArray = PackedByteArray()
var trade_was_open := false
var selected_storage_side := ""
var selected_manufacturing_recipe := -1
var manufacturing_server_status := "Select a recipe."
var cooldown_display_second := -1
var _chat_tab := "all"
var _right_mouse_down := false
var _right_mouse_dragged := false
var _interaction_mode := "walk"
var _hud_icon_regions: Dictionary = {}
var _hud_active_atlas: Texture2D
var _hud_inactive_atlas: Texture2D
var _hud_button_state_signature := ""
var _hud_meter_order: Array[String] = ["mana", "food", "health", "load", "action", "experience"]
var _hud_meter_visible: Dictionary = {
	"mana": true, "food": true, "health": true,
	"load": true, "action": true, "experience": true}
var _selected_experience_skill := "harvesting"
var _hud_layout_menu: PopupPanel
var _hud_layout_list: ItemList
var _hud_layout_visible: CheckButton
var _hud_skill_selector: OptionButton
var _floating_feedback_layer: Control
var _floating_feedback_offset := 0

const HUD_SKILLS: Array[String] = [
	"attack", "defense", "harvesting", "alchemy", "magic", "potion",
	"summoning", "manufacturing", "crafting", "engineering", "tailoring",
	"ranging", "overall"]

func _ready() -> void:
	var model_registry: Dictionary = _json("res://data/actors/models.json")
	models = model_registry.get("models", {})
	actor_type_models = model_registry.get("actorTypes", {})
	npc_looks = model_registry.get("npcLooks", {})
	creation_options = model_registry.get("creationOptions", [])
	animation_config = _json("res://data/animations/luminous.json")
	animation_configs["res://data/animations/luminous.json"] = animation_config
	map_registry = _json("res://data/maps/registry.json").get("maps", {})
	equipment_config = _json("res://data/actors/equipment.json")
	item_atlas.configure(_json("res://data/items/atlases.json"))
	spell_catalog.configure(_json("res://data/spells/catalog.json"))
	manufacturing_catalog.configure(_json("res://data/manufacturing/recipes.json"))
	var knowledge_catalog_value: Variant = _json(
		"res://data/knowledge/catalog.json").get("entries", [])
	if knowledge_catalog_value is Array:
		for raw_knowledge_name: Variant in knowledge_catalog_value as Array:
			knowledge_catalog.append(str(raw_knowledge_name))
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)
	AppState.login_succeeded.connect(_on_login_succeeded)
	AppState.login_failed.connect(_on_login_failed)
	AppState.character_created.connect(_on_character_created)
	AppState.character_creation_failed.connect(_on_character_creation_failed)
	AppState.state_changed.connect(_on_state_changed)
	AppState.floating_feedback_requested.connect(_on_floating_feedback_requested)
	world_loader.load_completed.connect(_on_world_loaded)
	world_loader.load_failed.connect(_on_world_load_failed)
	viewport_container.gui_input.connect(_on_world_gui_input)
	minimap.gui_input.connect(_on_minimap_gui_input)
	map_image.gui_input.connect(_on_full_map_gui_input)
	_bind_shared_world()
	minimap.texture = map_viewport.get_texture()
	map_image.texture = full_map_viewport.get_texture()
	full_map.hide()
	stats_panel.hide()
	inventory_panel.hide()
	trade_panel.hide()
	storage_panel.hide()
	ground_bag_panel.hide()
	knowledge_panel.hide()
	manufacturing_panel.hide()
	game_view.hide()
	creation_panel.hide()
	for raw_option: Variant in creation_options:
		if raw_option is not Dictionary:
			continue
		var option: Dictionary = raw_option as Dictionary
		create_gender.add_item(str(option.get("label", "Unknown appearance")),
			int(option.get("actorType", 1)))
	_update_preview_camera()
	_apply_eloria_art()
	_apply_eloria_theme()
	_build_inventory_slots()
	_build_equipment_slots()
	_bind_quick_slots()
	_bind_spell_slots()
	_reset_trade_destinations()
	trade_source.item_selected.connect(_on_trade_source_selected)
	trade_own_offers.item_selected.connect(_on_trade_own_selected)
	trade_other_offers.item_selected.connect(_on_trade_other_selected)
	storage_categories.item_selected.connect(_on_storage_category_selected)
	storage_items.item_selected.connect(_on_storage_item_selected)
	storage_inventory.item_selected.connect(_on_storage_inventory_selected)
	ground_bag_items.item_selected.connect(_on_ground_bag_item_selected)
	ground_bag_inventory.item_selected.connect(_on_ground_bag_inventory_selected)
	knowledge_list.item_selected.connect(_on_knowledge_selected)
	knowledge_known_only.toggled.connect(_on_knowledge_filter_toggled)
	manufacturing_list.item_selected.connect(_on_manufacturing_selected)
	manufacturing_filter.text_changed.connect(_on_manufacturing_filter_changed)
	show_overhead_health.toggled.connect(_on_overhead_option_toggled)
	show_overhead_ether.toggled.connect(_on_overhead_option_toggled)
	show_overhead_food.toggled.connect(_on_overhead_option_toggled)
	show_overhead_action.toggled.connect(_on_overhead_option_toggled)
	%Close.pressed.connect(func() -> void: actor_hud_menu.hide())
	$GameView/ChatTabs/All.pressed.connect(_on_chat_tab_pressed.bind("all"))
	$GameView/ChatTabs/History.pressed.connect(_on_chat_tab_pressed.bind("history"))
	$GameView/ChatTabs/Options.pressed.connect(_on_chat_tab_pressed.bind("options"))
	%ItemMode.pressed.connect(_on_quickbar_mode_pressed.bind("items"))
	%SpellMode.pressed.connect(_on_quickbar_mode_pressed.bind("spells"))
	_build_hud_layout_menu()
	_load_hud_layout()
	_connect_hud_context_inputs(%Quickbar)
	get_viewport().size_changed.connect(_on_window_size_changed)
	call_deferred("_on_window_size_changed")
	_on_quickbar_mode_pressed("items")
	_sync_stats()

func _bind_shared_world() -> void:
	gameplay_world = world_root.get_world_3d()
	if gameplay_world == null:
		push_error("world_binding stage=resolve error=WorldRoot_has_no_World3D")
		return
	map_viewport.world_3d = gameplay_world
	full_map_viewport.world_3d = gameplay_world
	print_debug("world_binding stage=shared world=", gameplay_world)

func _process(_delta: float) -> void:
	if game_view.visible:
		_update_local_actor_follow()
		_update_legacy_clock_and_compass()
		_update_actor_resource_overlay()
		var display_second: int = floori(float(Time.get_ticks_msec()) / 1000.0)
		if display_second != cooldown_display_second:
			cooldown_display_second = display_second
			_sync_quick_slots()
		_sync_hud_button_states()

func _on_connect_pressed() -> void:
	if AppState.connection_state != "disconnected":
		Network.disconnect_from_server()
		return
	connect_button.disabled = true
	login_button.disabled = true
	status_label.text = "Connecting…"
	var error := Network.connect_to_server(host_edit.text.strip_edges(), int(port_edit.value))
	if error != OK:
		status_label.text = "Connection failed: " + error_string(error)
		connect_button.disabled = false

func _on_new_character_pressed() -> void:
	if AppState.connection_state != "connected":
		status_label.text = "Connect to the server before creating a character."
		return
	login_panel.hide()
	creation_panel.show()
	_refresh_creation_preview()

func _on_creation_back_pressed() -> void:
	_clear_pending_creation()
	creation_panel.hide()
	login_panel.show()

func _on_create_gender_item_selected(_index: int) -> void:
	_refresh_creation_preview()

func _on_create_appearance_changed(_value: float) -> void:
	_refresh_creation_preview()

func _on_create_pressed() -> void:
	var username := create_name.text.strip_edges()
	var password := create_password.text
	if username.length() < 3 or username.length() > 20:
		create_status.text = "Name must contain 3–20 characters."
		return
	if password.length() < 4:
		create_status.text = "Password must contain at least 4 characters."
		return
	if password != create_confirm.text:
		create_status.text = "Passwords do not match."
		return
	pending_create_username = username
	pending_create_password = password
	create_status.text = "Creating character…"
	var appearance: Dictionary = _creation_appearance()
	appearance["actor_type"] = create_gender.get_selected_id()
	var error := Network.create_character(username, password, appearance)
	if error != OK:
		create_status.text = "Creation request failed: " + error_string(error)
		_clear_pending_creation()

func _on_character_created() -> void:
	create_status.text = "Character created. Entering Eloria…"
	user_edit.text = pending_create_username
	var username := pending_create_username
	var password := pending_create_password
	create_password.clear()
	create_confirm.clear()
	_clear_pending_creation()
	var error := Network.login(username, password)
	if error != OK:
		create_status.text = "Created, but login failed to send: " + error_string(error)
		creation_panel.hide()
		login_panel.show()

func _on_character_creation_failed(message: String) -> void:
	create_status.text = "Creation failed: " + message
	_clear_pending_creation()

func _clear_pending_creation() -> void:
	pending_create_username = ""
	pending_create_password = ""

func _refresh_creation_preview() -> void:
	if is_instance_valid(preview_actor):
		preview_actor.queue_free()
	preview_actor = ReplicatedActor3D.new()
	preview_root.add_child(preview_actor)
	var actor_type: int = create_gender.get_selected_id()
	var appearance: Dictionary = _creation_appearance()
	var dto := {"actor_id": 0, "x": 0, "y": 0, "rotation": 0,
		"actor_type": actor_type, "kind": 1, "name": "Preview",
		"appearance": appearance,
		"equipment_visuals": AppearanceVariants.equipment_visuals(
			actor_type, appearance)}
	var model_id := _model_for_actor(dto)
	var model_config: Dictionary = models.get(model_id, {}) as Dictionary
	var errors := preview_actor.configure(dto,
		CoordinateAdapter.new({"walkingHeight": 0.0}), model_config,
		_animation_for_model(model_config), equipment_config)
	if not errors.is_empty():
		create_status.text = "Preview warnings: " + "; ".join(errors)
	else:
		create_status.text = "Drag the preview to rotate; use the mouse wheel to zoom."

func _creation_appearance() -> Dictionary:
	return {
		"skin": int(%CreateSkin.value), "hair": int(%CreateHair.value),
		"eyes": int(%CreateEyes.value), "shirt": int(%CreateShirt.value),
		"pants": int(%CreatePants.value), "boots": int(%CreateBoots.value),
		"head": int(%CreateHead.value),
	}

func _on_character_preview_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse_button: InputEventMouseButton = event as InputEventMouseButton
		if not mouse_button.pressed:
			return
		if mouse_button.button_index == MOUSE_BUTTON_WHEEL_UP:
			preview_distance = maxf(2.4, preview_distance - 0.3)
		elif mouse_button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			preview_distance = minf(7.0, preview_distance + 0.3)
		else:
			return
		_update_preview_camera()
		preview_container.accept_event()
	elif event is InputEventMouseMotion:
		var mouse_motion: InputEventMouseMotion = event as InputEventMouseMotion
		if (mouse_motion.button_mask & (MOUSE_BUTTON_MASK_LEFT |
				MOUSE_BUTTON_MASK_RIGHT)) == 0:
			return
		preview_yaw -= mouse_motion.relative.x * 0.01
		preview_pitch = clampf(preview_pitch + mouse_motion.relative.y * 0.008,
			-0.35, 0.65)
		_update_preview_camera()
		preview_container.accept_event()

func _update_preview_camera() -> void:
	if preview_camera == null:
		return
	var focus := Vector3(0.0, 1.0, 0.0)
	var horizontal: float = cos(preview_pitch) * preview_distance
	preview_camera.position = focus + Vector3(sin(preview_yaw) * horizontal,
		sin(preview_pitch) * preview_distance, cos(preview_yaw) * horizontal)
	preview_camera.look_at(focus)

func _on_login_pressed() -> void:
	if AppState.authenticated:
		return
	if AppState.connection_state != "connected":
		status_label.text = "Connect to the server first."
		return
	if user_edit.text.is_empty() or password_edit.text.is_empty():
		status_label.text = "Enter username and password."
		return
	login_button.disabled = true
	status_label.text = "Authenticating…"
	var error := Network.login(user_edit.text, password_edit.text)
	password_edit.clear()
	if error != OK:
		status_label.text = "Login send failed: " + error_string(error)
		login_button.disabled = false

func _on_login_submitted(_text: String) -> void:
	if AppState.connection_state == "disconnected":
		_on_connect_pressed()
	elif AppState.connection_state == "connected":
		_on_login_pressed()

func _on_map_button_pressed() -> void:
	full_map.visible = not full_map.visible
	_sync_hud_button_states(true)

func _on_walk_button_pressed() -> void:
	_interaction_mode = "walk"
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	if bool(local_actor.get("sitting", false)):
		var error: Error = Network.set_sitting(false)
		if error != OK:
			push_warning("STAND_UP failed: " + error_string(error))
	_sync_hud_button_states(true)

func _on_sit_button_pressed() -> void:
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var error: Error = Network.set_sitting(not bool(local_actor.get("sitting", false)))
	if error != OK:
		push_warning("SIT_DOWN failed: " + error_string(error))

func _on_attack_button_pressed() -> void:
	_interaction_mode = "attack"
	_attack_selected_actor()
	_sync_hud_button_states(true)

func _on_trade_button_pressed() -> void:
	_interaction_mode = "trade"
	var actor_id: int = AppState.selected_actor_id
	var dto: Dictionary = AppState.actors.get(actor_id, {})
	if not _is_tradeable_player(actor_id, dto):
		return
	print_debug("trade_input command=TRADE_WITH target_actor_id=", actor_id,
		" redacted_bytes=not_sensitive")
	var error: Error = Network.trade_with(actor_id)
	if error != OK:
		push_warning("TRADE_WITH failed: " + error_string(error))
	_sync_hud_button_states(true)

func _on_chat_button_pressed() -> void:
	chat_input.grab_focus()
	_sync_hud_button_states(true)

func _on_stats_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	stats_panel.visible = not stats_panel.visible
	if stats_panel.visible:
		inventory_panel.hide()
		knowledge_panel.hide()
		manufacturing_panel.hide()
		_sync_stats()
	_sync_hud_button_states(true)

func _on_inventory_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	inventory_panel.visible = not inventory_panel.visible
	if inventory_panel.visible:
		stats_panel.hide()
		knowledge_panel.hide()
		manufacturing_panel.hide()
		_sync_inventory()
	_sync_hud_button_states(true)

func _on_knowledge_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	knowledge_panel.visible = not knowledge_panel.visible
	if knowledge_panel.visible:
		inventory_panel.hide()
		stats_panel.hide()
		manufacturing_panel.hide()
		full_map.hide()
		_sync_knowledge()
	_sync_hud_button_states(true)

func _on_manufacturing_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	manufacturing_panel.visible = not manufacturing_panel.visible
	if manufacturing_panel.visible:
		inventory_panel.hide()
		stats_panel.hide()
		knowledge_panel.hide()
		full_map.hide()
		_sync_manufacturing()
	_sync_hud_button_states(true)

func _on_manufacturing_selected(index: int) -> void:
	selected_manufacturing_recipe = _list_metadata_int(manufacturing_list, index)
	manufacturing_server_status = "Ready for server validation."
	_sync_manufacturing_detail()

func _on_manufacturing_filter_changed(_text: String) -> void:
	_sync_manufacturing()

func _on_manufacturing_mix_one_pressed() -> void:
	_send_manufacturing_request(1)

func _on_manufacturing_mix_all_pressed() -> void:
	_send_manufacturing_request(255)

func _on_manufacturing_close_pressed() -> void:
	manufacturing_panel.hide()

func _send_manufacturing_request(wanted: int) -> void:
	var availability: Dictionary = manufacturing_catalog.availability(
		selected_manufacturing_recipe, AppState.inventory, AppState.known_knowledge,
		AppState.stats)
	var reasons: Array = availability.get("reasons", []) as Array
	var selection: Array = availability.get("selection", []) as Array
	if not reasons.is_empty() or selection.is_empty():
		return
	var typed_selection: Array[Dictionary] = []
	for selection_value: Variant in selection:
		if selection_value is Dictionary:
			typed_selection.append(selection_value as Dictionary)
	print_debug("manufacturing_input command=MANUFACTURE_THIS recipe_id=",
		selected_manufacturing_recipe, " wanted=", wanted,
		" ingredients=", typed_selection, " redacted_bytes=not_sensitive")
	var error: Error = Network.manufacture(typed_selection, wanted)
	if error == OK:
		manufacturing_server_status = ("Mix-all request sent; awaiting the server."
			if wanted == 255 else "Mix request sent; awaiting the server.")
	else:
		manufacturing_server_status = "MANUFACTURE_THIS failed: " + error_string(error)
	_sync_manufacturing_detail()

func _on_knowledge_selected(index: int) -> void:
	var knowledge_index: int = _list_metadata_int(knowledge_list, index)
	if knowledge_index < 0 or knowledge_index >= knowledge_catalog.size():
		return
	AppState.select_knowledge(knowledge_index)
	var error: Error = Network.get_knowledge_info(knowledge_index)
	if error != OK:
		push_warning("GET_KNOWLEDGE_INFO failed: " + error_string(error))

func _on_knowledge_filter_toggled(_enabled: bool) -> void:
	_sync_knowledge()

func _on_knowledge_close_pressed() -> void:
	knowledge_panel.hide()

func _on_inventory_close_pressed() -> void:
	inventory_panel.hide()

func _on_inventory_use_pressed() -> void:
	_use_inventory_slot(selected_inventory_slot)

func _on_inventory_equip_pressed() -> void:
	if selected_inventory_slot < 0 or selected_inventory_slot >= 36:
		return
	var destination: int = _first_empty_slot(36, 44)
	if destination >= 0:
		_move_inventory_item(selected_inventory_slot, destination)

func _on_inventory_unequip_pressed() -> void:
	if selected_inventory_slot < 36 or selected_inventory_slot >= 44:
		return
	var destination: int = _first_empty_slot(0, 36)
	if destination >= 0:
		_move_inventory_item(selected_inventory_slot, destination)

func _on_inventory_inspect_pressed() -> void:
	if selected_inventory_slot < 0:
		return
	var error: Error = Network.look_at_inventory_item(selected_inventory_slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))

func _on_trade_source_selected(index: int) -> void:
	selected_trade_side = "source"
	var slot: int = _trade_list_slot(trade_source, index)
	var source_inventory: Dictionary = AppState.trade.get("source_inventory", {}) as Dictionary
	var item_value: Variant = source_inventory.get(slot)
	if item_value is Dictionary:
		trade_quantity.max_value = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
		trade_quantity.value = mini(int(trade_quantity.value), int(trade_quantity.max_value))
	_sync_trade_actions()

func _on_trade_own_selected(_index: int) -> void:
	selected_trade_side = "own"
	_sync_trade_actions()

func _on_trade_other_selected(_index: int) -> void:
	selected_trade_side = "other"
	_sync_trade_actions()

func _on_trade_storage_destination_toggled(enabled: bool) -> void:
	if not bool(AppState.trade.get("storage_available", false)):
		return
	var selected: PackedInt32Array = trade_other_offers.get_selected_items()
	if selected.is_empty():
		return
	var offer_slot: int = _trade_list_slot(trade_other_offers, int(selected[0]))
	if offer_slot >= 0 and offer_slot < trade_destinations.size():
		trade_destinations[offer_slot] = 2 if enabled else 1

func _on_trade_offer_pressed() -> void:
	var selected: PackedInt32Array = trade_source.get_selected_items()
	if selected.is_empty():
		return
	var slot: int = _trade_list_slot(trade_source, int(selected[0]))
	var source_inventory: Dictionary = AppState.trade.get("source_inventory", {}) as Dictionary
	var item_value: Variant = source_inventory.get(slot)
	if not item_value is Dictionary:
		return
	var item: Dictionary = item_value as Dictionary
	var quantity: int = clampi(int(trade_quantity.value), 1, int(item.get("quantity", 1)))
	var error: Error = Network.put_inventory_on_trade(slot, quantity)
	if error != OK:
		push_warning("PUT_OBJECT_ON_TRADE failed: " + error_string(error))

func _on_trade_remove_pressed() -> void:
	var selected: PackedInt32Array = trade_own_offers.get_selected_items()
	if selected.is_empty():
		return
	var offer_slot: int = _trade_list_slot(trade_own_offers, int(selected[0]))
	var own_offers: Dictionary = AppState.trade.get("own_offers", {}) as Dictionary
	var offer_value: Variant = own_offers.get(offer_slot)
	if not offer_value is Dictionary:
		return
	var offer: Dictionary = offer_value as Dictionary
	var quantity: int = clampi(int(trade_quantity.value), 1, int(offer.get("quantity", 1)))
	var error: Error = Network.remove_trade_item(offer_slot, quantity)
	if error != OK:
		push_warning("REMOVE_OBJECT_FROM_TRADE failed: " + error_string(error))

func _on_trade_inspect_pressed() -> void:
	var list: ItemList = trade_other_offers if selected_trade_side == "other" else trade_own_offers
	var selected: PackedInt32Array = list.get_selected_items()
	if selected.is_empty():
		return
	var offer_slot: int = _trade_list_slot(list, int(selected[0]))
	var error: Error = Network.look_at_trade_item(offer_slot, list == trade_other_offers)
	if error != OK:
		push_warning("LOOK_AT_TRADE_ITEM failed: " + error_string(error))

func _on_trade_accept_pressed() -> void:
	if not bool(AppState.trade.get("open", false)):
		return
	var error: Error = Network.accept_trade(trade_destinations)
	if error != OK:
		push_warning("ACCEPT_TRADE failed: " + error_string(error))

func _on_trade_reject_pressed() -> void:
	if not bool(AppState.trade.get("open", false)):
		return
	var error: Error = Network.reject_trade()
	if error != OK:
		push_warning("REJECT_TRADE failed: " + error_string(error))

func _on_trade_cancel_pressed() -> void:
	if not bool(AppState.trade.get("open", false)):
		return
	trade_status.text = "Cancelling trade and restoring offers…"
	var error: Error = Network.exit_trade()
	if error != OK:
		push_warning("EXIT_TRADE failed: " + error_string(error))

func _on_storage_category_selected(index: int) -> void:
	var category_id: int = _list_metadata_int(storage_categories, index)
	if category_id < 0:
		return
	var error: Error = Network.get_storage_category(category_id)
	if error != OK:
		push_warning("GET_STORAGE_CATEGORY failed: " + error_string(error))

func _on_storage_item_selected(index: int) -> void:
	selected_storage_side = "storage"
	var position: int = _list_metadata_int(storage_items, index)
	var items: Dictionary = AppState.storage.get("items", {}) as Dictionary
	var item_value: Variant = items.get(position)
	if item_value is Dictionary:
		storage_quantity.max_value = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
		storage_quantity.value = mini(int(storage_quantity.value), int(storage_quantity.max_value))
	_sync_storage_actions()

func _on_storage_inventory_selected(index: int) -> void:
	selected_storage_side = "inventory"
	var slot: int = _list_metadata_int(storage_inventory, index)
	var item_value: Variant = AppState.inventory.get(slot)
	if item_value is Dictionary:
		storage_quantity.max_value = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
		storage_quantity.value = mini(int(storage_quantity.value), int(storage_quantity.max_value))
	_sync_storage_actions()

func _on_storage_deposit_pressed() -> void:
	var selected: PackedInt32Array = storage_inventory.get_selected_items()
	if selected.is_empty():
		return
	var slot: int = _list_metadata_int(storage_inventory, int(selected[0]))
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var quantity: int = clampi(int(storage_quantity.value), 1,
		int((item_value as Dictionary).get("quantity", 1)))
	var error: Error = Network.deposit_storage(slot, quantity)
	if error != OK:
		push_warning("DEPOSIT_ITEM failed: " + error_string(error))

func _on_storage_withdraw_pressed() -> void:
	var selected: PackedInt32Array = storage_items.get_selected_items()
	if selected.is_empty():
		return
	var position: int = _list_metadata_int(storage_items, int(selected[0]))
	var items: Dictionary = AppState.storage.get("items", {}) as Dictionary
	var item_value: Variant = items.get(position)
	if not item_value is Dictionary:
		return
	var quantity: int = clampi(int(storage_quantity.value), 1,
		int((item_value as Dictionary).get("quantity", 1)))
	var error: Error = Network.withdraw_storage(position, quantity)
	if error != OK:
		push_warning("WITHDRAW_ITEM failed: " + error_string(error))

func _on_storage_inspect_pressed() -> void:
	var selected: PackedInt32Array = storage_items.get_selected_items()
	if selected.is_empty():
		return
	var position: int = _list_metadata_int(storage_items, int(selected[0]))
	var error: Error = Network.look_at_storage_item(position)
	if error != OK:
		push_warning("LOOK_AT_STORAGE_ITEM failed: " + error_string(error))

func _on_storage_close_pressed() -> void:
	AppState.close_storage()

func _on_ground_bag_item_selected(index: int) -> void:
	var position: int = _list_metadata_int(ground_bag_items, index)
	var items: Dictionary = AppState.ground_bag.get("items", {}) as Dictionary
	var item_value: Variant = items.get(position)
	if item_value is Dictionary:
		ground_bag_quantity.max_value = maxi(1,
			int((item_value as Dictionary).get("quantity", 1)))
		ground_bag_quantity.value = mini(int(ground_bag_quantity.value),
			int(ground_bag_quantity.max_value))
	_sync_ground_bag_actions()

func _on_ground_bag_inventory_selected(index: int) -> void:
	var slot: int = _list_metadata_int(ground_bag_inventory, index)
	var item_value: Variant = AppState.inventory.get(slot)
	if item_value is Dictionary:
		ground_bag_quantity.max_value = maxi(1,
			int((item_value as Dictionary).get("quantity", 1)))
		ground_bag_quantity.value = mini(int(ground_bag_quantity.value),
			int(ground_bag_quantity.max_value))
	_sync_ground_bag_actions()

func _on_ground_bag_pick_pressed() -> void:
	var selected: PackedInt32Array = ground_bag_items.get_selected_items()
	if selected.is_empty():
		return
	var position: int = _list_metadata_int(ground_bag_items, int(selected[0]))
	var items: Dictionary = AppState.ground_bag.get("items", {}) as Dictionary
	var item_value: Variant = items.get(position)
	if not item_value is Dictionary:
		return
	var quantity: int = clampi(int(ground_bag_quantity.value), 1,
		int((item_value as Dictionary).get("quantity", 1)))
	var error: Error = Network.pick_up_ground_item(position, quantity)
	if error != OK:
		push_warning("PICK_UP_ITEM failed: " + error_string(error))

func _on_ground_bag_pick_all_pressed() -> void:
	var items: Dictionary = AppState.ground_bag.get("items", {}) as Dictionary
	var positions: Array = items.keys()
	positions.sort()
	for raw_position: Variant in positions:
		var position: int = int(raw_position)
		var item_value: Variant = items.get(position)
		if item_value is Dictionary:
			var quantity: int = int((item_value as Dictionary).get("quantity", 0))
			if quantity > 0:
				var error: Error = Network.pick_up_ground_item(position, quantity)
				if error != OK:
					push_warning("PICK_UP_ITEM failed: " + error_string(error))

func _on_ground_bag_drop_pressed() -> void:
	var selected: PackedInt32Array = ground_bag_inventory.get_selected_items()
	if selected.is_empty():
		return
	var slot: int = _list_metadata_int(ground_bag_inventory, int(selected[0]))
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var quantity: int = clampi(int(ground_bag_quantity.value), 1,
		int((item_value as Dictionary).get("quantity", 1)))
	var error: Error = Network.drop_inventory_item(slot, quantity)
	if error != OK:
		push_warning("DROP_ITEM failed: " + error_string(error))

func _on_ground_bag_close_pressed() -> void:
	_close_ground_bag()

func _close_ground_bag() -> void:
	var error: Error = Network.close_bag()
	if error != OK:
		push_warning("CLOSE_BAG failed: " + error_string(error))
	AppState.close_ground_bag()

func _on_disconnect_pressed() -> void:
	Network.disconnect_from_server()

func _on_login_succeeded() -> void:
	login_panel.hide()
	creation_panel.hide()
	game_view.show()
	map_label.text = "Entering world…"
	_load_server_map()
	_sync_world()

func _on_login_failed(message: String) -> void:
	status_label.text = "Login failed: " + message
	login_button.disabled = false

func _on_connection_state_changed(value: String) -> void:
	status_label.text = value.capitalize()
	connect_button.text = "Disconnect" if value == "connected" else "Connect"
	connect_button.disabled = value == "connecting"
	login_button.disabled = value != "connected" or AppState.authenticated
	new_character_button.disabled = value != "connected" or AppState.authenticated
	if value == "disconnected" and game_view.visible:
		_clear_world_presentation()
		game_view.hide()
		login_panel.show()
		status_label.text = "Disconnected"

func _clear_world_presentation() -> void:
	for raw_node: Variant in actor_nodes.values():
		var actor_node: Node = raw_node as Node
		if is_instance_valid(actor_node):
			actor_node.queue_free()
	actor_nodes.clear()
	for raw_bag_node: Variant in ground_bag_nodes.values():
		var bag_node: Node = raw_bag_node as Node
		if is_instance_valid(bag_node):
			bag_node.queue_free()
	ground_bag_nodes.clear()
	world_loader.unload_world()
	loaded_server_map = ""
	full_map.hide()
	inventory_panel.hide()
	stats_panel.hide()
	trade_panel.hide()
	storage_panel.hide()
	ground_bag_panel.hide()
	knowledge_panel.hide()
	manufacturing_panel.hide()
	dialogue_panel.hide()
	chat_output.clear()
	selected_target.text = "Target: none"

func _unhandled_input(event: InputEvent) -> void:
	if not game_view.visible:
		return
	for spell_slot: int in range(6):
		if event.is_action_pressed("quick_spell_%d" % (spell_slot + 1)):
			_cast_spell_slot(spell_slot)
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("attack_selected"):
		_attack_selected_actor()
		get_viewport().set_input_as_handled()
		return
	for slot: int in range(8):
		if event.is_action_pressed("quick_item_%d" % (slot + 1)):
			_use_inventory_slot(slot)
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("toggle_map") or (event is InputEventKey and event.pressed and event.keycode == KEY_TAB):
		full_map.visible = not full_map.visible
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("chat_focus"):
		chat_input.grab_focus()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("cancel"):
		if dialogue_panel.visible:
			AppState.close_dialogue()
		elif bool(AppState.trade.get("open", false)):
			_on_trade_cancel_pressed()
		elif bool(AppState.storage.get("open", false)):
			AppState.close_storage()
		elif bool(AppState.ground_bag.get("open", false)):
			_close_ground_bag()
		elif knowledge_panel.visible:
			knowledge_panel.hide()
		elif manufacturing_panel.visible:
			manufacturing_panel.hide()
		elif inventory_panel.visible:
			inventory_panel.hide()
		elif stats_panel.visible:
			stats_panel.hide()
		elif full_map.visible:
			full_map.hide()
		else:
			chat_input.release_focus()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("toggle_sit"):
		var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
		var wants_to_sit: bool = not bool(local_actor.get("sitting", false))
		var sit_error: Error = Network.set_sitting(wants_to_sit)
		if sit_error != OK:
			push_warning("SIT_DOWN failed: " + error_string(sit_error))
		get_viewport().set_input_as_handled()
		return

func _on_world_gui_input(event: InputEvent) -> void:
	if (not game_view.visible or full_map.visible or dialogue_panel.visible
			or trade_panel.visible or storage_panel.visible or ground_bag_panel.visible
			or knowledge_panel.visible or manufacturing_panel.visible):
		return
	if event is InputEventMouseButton:
		var mouse_button: InputEventMouseButton = event as InputEventMouseButton
		if mouse_button.button_index == MOUSE_BUTTON_RIGHT:
			if mouse_button.pressed:
				_right_mouse_down = true
				_right_mouse_dragged = false
				actor_hud_menu.hide()
			camera_rig.handle_mouse_button(mouse_button)
			if not mouse_button.pressed:
				_right_mouse_down = false
				if not _right_mouse_dragged:
					var local_position: Vector2 = _local_viewport_position(mouse_button.position)
					if _pick_actor(local_position) == AppState.local_actor_id:
						_open_actor_hud_menu(mouse_button.position + viewport_container.position)
			viewport_container.accept_event()
			return
		if camera_rig.handle_mouse_button(mouse_button):
			viewport_container.accept_event()
			return
		if mouse_button.pressed and mouse_button.button_index == MOUSE_BUTTON_LEFT:
			_handle_world_click(mouse_button, _local_viewport_position(mouse_button.position))
			viewport_container.accept_event()
	elif event is InputEventMouseMotion:
		var mouse_motion: InputEventMouseMotion = event as InputEventMouseMotion
		if _right_mouse_down and mouse_motion.relative.length_squared() > 4.0:
			_right_mouse_dragged = true
		if camera_rig.handle_mouse_motion(mouse_motion):
			viewport_container.accept_event()

func _open_actor_hud_menu(position: Vector2) -> void:
	actor_hud_menu.show()
	actor_hud_menu.reset_size()
	var menu_size: Vector2 = actor_hud_menu.size
	var boundary: Vector2 = game_view.size - menu_size - Vector2(8.0, 8.0)
	actor_hud_menu.position = Vector2(
		clampf(position.x, 8.0, maxf(8.0, boundary.x)),
		clampf(position.y, 8.0, maxf(8.0, boundary.y)))
	actor_hud_menu.move_to_front()

func _on_overhead_option_toggled(_enabled: bool) -> void:
	overhead_health_row.visible = show_overhead_health.button_pressed
	overhead_ether_row.visible = show_overhead_ether.button_pressed
	overhead_food_row.visible = show_overhead_food.button_pressed
	overhead_action_row.visible = show_overhead_action.button_pressed
	_update_actor_resource_overlay()

func _on_chat_tab_pressed(tab: String) -> void:
	_chat_tab = tab
	$GameView/ChatTabs/All.button_pressed = tab == "all"
	$GameView/ChatTabs/History.button_pressed = tab == "history"
	$GameView/ChatTabs/Options.button_pressed = tab == "options"
	_sync_chat()

func _on_minimap_gui_input(event: InputEvent) -> void:
	_handle_map_gui_input(event, minimap, map_viewport, map_camera, "minimap")

func _on_full_map_gui_input(event: InputEvent) -> void:
	_handle_map_gui_input(event, map_image, full_map_viewport, full_map_camera, "full_map")

func _handle_map_gui_input(event: InputEvent, map_control: Control,
		map_render_viewport: SubViewport, camera: Camera3D, source: String) -> void:
	if (not game_view.visible or dialogue_panel.visible or trade_panel.visible
			or storage_panel.visible or ground_bag_panel.visible
			or knowledge_panel.visible or manufacturing_panel.visible):
		return
	if not event is InputEventMouseButton:
		return
	var mouse_button: InputEventMouseButton = event as InputEventMouseButton
	if not mouse_button.pressed or mouse_button.button_index != MOUSE_BUTTON_LEFT:
		return
	var viewport_position: Vector2 = _control_to_viewport_position(
		mouse_button.position, map_control.size, map_render_viewport.size)
	var target_value: Variant = _map_target_tile(camera, viewport_position)
	print_debug("map_input source=", source, " local_click=", mouse_button.position,
		" viewport=", viewport_position, " server_tile=", target_value,
		" command=", "RUN_TO" if mouse_button.shift_pressed else "MOVE_TO")
	if target_value is Vector2i:
		var move_error: Error = Network.move_to(target_value as Vector2i,
			mouse_button.shift_pressed)
		if move_error != OK:
			push_warning("%s MOVE_TO failed: %s" % [source, error_string(move_error)])
	map_control.accept_event()

func _map_target_tile(camera: Camera3D, viewport_position: Vector2) -> Variant:
	if not is_instance_valid(camera):
		return null
	var ray_origin: Vector3 = camera.project_ray_origin(viewport_position)
	var ray_direction: Vector3 = camera.project_ray_normal(viewport_position)
	var point: Variant = _navigation_ray_position(ray_origin, ray_direction)
	if not point is Vector3:
		if absf(ray_direction.y) < 0.0001:
			return null
		var distance_to_ground: float = (adapter.walking_height - ray_origin.y) / ray_direction.y
		if distance_to_ground < 0.0:
			return null
		point = ray_origin + ray_direction * distance_to_ground
	return adapter.godot_to_server(point as Vector3)

static func _control_to_viewport_position(local_position: Vector2,
		control_size: Vector2, target_size: Vector2i) -> Vector2:
	if control_size.x <= 0.0 or control_size.y <= 0.0:
		return local_position
	return local_position * Vector2(target_size) / control_size

func _handle_world_click(event: InputEventMouseButton, viewport_position: Vector2) -> void:
	var picked_actor_id: int = _pick_actor(viewport_position)
	if picked_actor_id >= 0:
		AppState.select_actor(picked_actor_id)
		var selected_dto: Dictionary = AppState.actors.get(picked_actor_id, {})
		if AppState.pending_spell_target == "actor":
			var spell_touch_error: Error = Network.touch_actor(picked_actor_id)
			if spell_touch_error != OK:
				push_warning("TOUCH_PLAYER spell target failed: " + error_string(spell_touch_error))
			return
		if _interaction_mode == "attack" and _is_attackable_actor(
				picked_actor_id, selected_dto):
			_send_attack(picked_actor_id)
			return
		if _interaction_mode == "trade" and _is_tradeable_player(
				picked_actor_id, selected_dto):
			var trade_error: Error = Network.trade_with(picked_actor_id)
			if trade_error != OK:
				push_warning("TRADE_WITH failed: " + error_string(trade_error))
			return
		if event.alt_pressed and _is_attackable_actor(picked_actor_id, selected_dto):
			_send_attack(picked_actor_id)
			return
		if int(selected_dto.get("kind", 0)) == 2:
			var touch_error: Error = Network.touch_actor(picked_actor_id)
			if touch_error != OK:
				push_warning("TOUCH_PLAYER failed: " + error_string(touch_error))
		return
	var picked_bag_id: int = _pick_ground_bag(viewport_position)
	if picked_bag_id >= 0:
		print_debug("ground_bag_input command=INSPECT_BAG bag_id=", picked_bag_id,
			" redacted_bytes=not_sensitive")
		AppState.begin_ground_bag_inspection(picked_bag_id)
		var inspect_error: Error = Network.inspect_bag(picked_bag_id)
		if inspect_error != OK:
			push_warning("INSPECT_BAG failed: " + error_string(inspect_error))
		return
	var ray_origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var ray_direction: Vector3 = camera_rig.ray_direction(viewport_position)
	var point: Variant = _navigation_ray_position(ray_origin, ray_direction)
	if not point is Vector3:
		var ground_height: float = adapter.walking_height
		if actor_nodes.has(AppState.local_actor_id):
			var local_actor_node: Node3D = actor_nodes.get(AppState.local_actor_id) as Node3D
			if is_instance_valid(local_actor_node):
				ground_height = local_actor_node.global_position.y
		point = camera_rig.screen_to_ground(viewport_position, ground_height)
	print_debug("world_input local_click=", event.position, " viewport=", viewport_position,
		" ray_origin=", ray_origin, " ray_direction=", ray_direction, " intersection=", point)
	if point is Vector3:
		var tile: Vector2i = adapter.godot_to_server(point as Vector3)
		print_debug("world_input godot=", point, " server_tile=", tile,
			" command=", "RUN_TO" if event.shift_pressed else "MOVE_TO")
		var move_error: Error = Network.move_to(tile, event.shift_pressed)
		if move_error != OK:
			push_warning("MOVE_TO failed: " + error_string(move_error))

func _on_state_changed(path: StringName) -> void:
	if not AppState.authenticated:
		return
	match path:
		&"map":
			_load_server_map()
			_sync_world()
		&"actors", &"local_actor":
			_sync_world()
			_sync_selection()
		&"chat":
			_sync_chat()
		&"stats":
			_sync_stats()
			_sync_spells()
			_sync_manufacturing()
		&"inventory", &"inventory_text":
			if path == &"inventory_text" and manufacturing_panel.visible:
				manufacturing_server_status = AppState.inventory_text
			_sync_inventory()
			_sync_spells()
			_sync_manufacturing()
			if bool(AppState.storage.get("open", false)):
				_sync_storage()
			if bool(AppState.ground_bag.get("open", false)):
				_sync_ground_bag()
		&"inventory_cooldowns":
			_sync_quick_slots()
		&"spells":
			_sync_spells()
		&"selection":
			_sync_selection()
		&"npc_dialogue":
			_sync_dialogue()
		&"trade":
			_sync_trade()
		&"storage":
			_sync_storage()
		&"ground_bags":
			_sync_ground_bags()
		&"ground_bag":
			_sync_ground_bag()
		&"knowledge":
			_sync_knowledge()
			_sync_manufacturing()

func _load_server_map() -> void:
	if AppState.current_map.is_empty() or loaded_server_map == AppState.current_map:
		return
	var normalized_map: String = MapRegistry.normalize_server_map_id(AppState.current_map)
	var entry: Dictionary = MapRegistry.resolve(map_registry, AppState.current_map)
	if entry.is_empty():
		map_label.text = "Map: " + AppState.current_map + " (GLB package unavailable)"
		push_error("map_registry_miss server_id=%s normalized=%s keys=%s" % [
			AppState.current_map, normalized_map, map_registry.keys()])
		return
	loaded_server_map = AppState.current_map
	adapter = CoordinateAdapter.new(entry.get("coordinateTransform", {}))
	for node in actor_nodes.values():
		node.queue_free()
	actor_nodes.clear()
	for bag_node_value: Variant in ground_bag_nodes.values():
		var bag_node: Node = bag_node_value as Node
		if is_instance_valid(bag_node):
			bag_node.queue_free()
	ground_bag_nodes.clear()
	var manifest_resource: String = str(entry.get("manifest", ""))
	var manifest_path: String = ProjectSettings.globalize_path(manifest_resource)
	print_debug("map_resolved server_id=", AppState.current_map,
		" normalized=", normalized_map, " registry_key=", entry.get("registryKey", ""),
		" manifest_resource=", manifest_resource, " manifest_path=", manifest_path)
	world_loader.load_world(manifest_path)
	map_label.text = "Loading " + AppState.current_map + "…"

func _on_world_loaded(manifest: WorldManifest) -> void:
	_bind_shared_world()
	fallback_ground.hide()
	map_label.text = "Map: " + manifest.data.get("asset", {}).get("name", manifest.asset_id())
	_configure_full_map(manifest)
	_sync_world()
	_sync_ground_bags()
	_snap_all_actors_to_surface.call_deferred()
	_snap_all_ground_bags_to_surface.call_deferred()

func _snap_all_actors_to_surface() -> void:
	await get_tree().physics_frame
	for actor_value: Variant in actor_nodes.values():
		var actor: ReplicatedActor3D = actor_value as ReplicatedActor3D
		if is_instance_valid(actor):
			_place_actor_on_surface(actor)

func _snap_all_ground_bags_to_surface() -> void:
	await get_tree().physics_frame
	for bag_value: Variant in ground_bag_nodes.values():
		var bag: GroundBag3D = bag_value as GroundBag3D
		if is_instance_valid(bag):
			_place_ground_bag_on_surface(bag)

func _on_world_load_failed(errors: Array[String]) -> void:
	fallback_ground.show()
	map_label.text = "Map load failed: " + "; ".join(errors)

func _sync_world() -> void:
	map_label.text = "Map: " + (AppState.current_map if not AppState.current_map.is_empty() else "loading")
	for id in actor_nodes.keys():
		if not AppState.actors.has(id):
			actor_nodes[id].queue_free()
			actor_nodes.erase(id)
	for id in AppState.actors:
		var dto: Dictionary = _presentation_dto(AppState.actors[id])
		if actor_nodes.has(id):
			var existing_actor: ReplicatedActor3D = actor_nodes[id] as ReplicatedActor3D
			existing_actor.apply_server_state(dto, adapter)
			existing_actor.set_nameplate_visible(int(id) != AppState.local_actor_id)
			_place_actor_on_surface(existing_actor)
			continue
		var node := ReplicatedActor3D.new()
		node.name = "Actor_%d" % id
		world_root.add_child(node)
		actor_nodes[id] = node
		var model_id := _model_for_actor(dto)
		var model_config: Dictionary = models.get(model_id, {}) as Dictionary
		var errors := node.configure(dto, adapter, model_config,
			_animation_for_model(model_config), equipment_config)
		if not errors.is_empty():
			push_warning("Actor %d: %s" % [id, "; ".join(errors)])
		node.apply_server_state(dto, adapter, true)
		node.set_nameplate_visible(int(id) != AppState.local_actor_id)
		_place_actor_on_surface(node)
	actor_label.text = "Actors: %d" % AppState.actors.size()
	if AppState.local_actor_id >= 0 and actor_nodes.has(AppState.local_actor_id):
		_update_local_actor_follow()
		var local_dto: Dictionary = AppState.actors[AppState.local_actor_id]
		overhead_player_name.text = str(local_dto.get("name", "Player"))
		var current_health := int(local_dto.get("health", 0))
		var maximum_health := maxi(1, int(local_dto.get("max_health", 1)))
		if AppState.stats.is_empty():
			_set_meter(health_bar, health_text, current_health, maximum_health, "Health")
			_set_meter(health_bottom, health_bottom_text,
				current_health, maximum_health, "Health")
			_set_overhead_meter(overhead_health_row, current_health, maximum_health)

func _update_local_actor_follow() -> void:
	if AppState.local_actor_id < 0:
		return
	var target_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not target_value is Node3D:
		return
	var target: Node3D = target_value as Node3D
	if not is_instance_valid(target):
		return
	var focus_position: Vector3 = target.global_position
	camera_rig.set_focus(focus_position)
	map_camera.global_position = focus_position + Vector3(0, 220, 0)
	map_camera.rotation_degrees = Vector3(-90, 0, 0)
	# Render above the actor and ignore depth so roofs/bridges cannot hide the
	# local-position dot in either top-down map camera.
	player_map_marker.global_position = focus_position + Vector3(0, 5.0, 0)
	player_map_marker.visible = true

func _place_actor_on_surface(actor: ReplicatedActor3D) -> void:
	if not is_instance_valid(actor) or gameplay_world == null:
		return
	var actor_position: Vector3 = actor.server_target
	var ray_start: Vector3 = Vector3(actor_position.x, 400.0, actor_position.z)
	var ray_end: Vector3 = Vector3(actor_position.x, -100.0, actor_position.z)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		ray_start, ray_end, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var hit_position_value: Variant = hit.get("position")
	if hit_position_value is Vector3:
		var hit_position: Vector3 = hit_position_value as Vector3
		actor.set_surface_height(hit_position.y + 0.02)
		if actor.actor_id == AppState.local_actor_id:
			print_debug("local_actor_placement map=", AppState.current_map,
				" actor_id=", actor.actor_id, " server_target=", actor_position,
				" navigation_hit=", hit_position, " render=", actor.render_diagnostics(),
				" camera=", camera_rig.camera_diagnostics())
	else:
		actor.set_surface_height(adapter.walking_height + 0.02)
		if actor.actor_id == AppState.local_actor_id:
			push_warning("local_actor_placement navigation_miss map=%s actor_id=%d target=%s fallback_y=%.3f" % [
				AppState.current_map, actor.actor_id, actor_position, adapter.walking_height + 0.02])

func _navigation_ray_position(origin: Vector3, direction: Vector3) -> Variant:
	if gameplay_world == null:
		return null
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + direction * 2000.0, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var position_value: Variant = hit.get("position")
	return position_value if position_value is Vector3 else null

func _sync_ground_bags() -> void:
	for raw_id: Variant in ground_bag_nodes.keys():
		var bag_id: int = int(raw_id)
		if not AppState.ground_bags.has(bag_id):
			var stale_value: Variant = ground_bag_nodes.get(bag_id)
			if stale_value is Node:
				(stale_value as Node).queue_free()
			ground_bag_nodes.erase(bag_id)
	for raw_id: Variant in AppState.ground_bags:
		var bag_id: int = int(raw_id)
		var dto_value: Variant = AppState.ground_bags.get(bag_id)
		if not dto_value is Dictionary:
			continue
		var dto: Dictionary = dto_value as Dictionary
		if ground_bag_nodes.has(bag_id):
			var existing: GroundBag3D = ground_bag_nodes.get(bag_id) as GroundBag3D
			if is_instance_valid(existing):
				existing.global_position = adapter.server_to_godot(
					int(dto.get("x", 0)), int(dto.get("y", 0)))
				_place_ground_bag_on_surface(existing)
			continue
		var bag: GroundBag3D = GroundBag3D.new()
		bag.configure(dto, adapter)
		world_root.add_child(bag)
		ground_bag_nodes[bag_id] = bag
		_place_ground_bag_on_surface(bag)

func _place_ground_bag_on_surface(bag: GroundBag3D) -> void:
	if not is_instance_valid(bag) or gameplay_world == null:
		return
	var ray_start: Vector3 = Vector3(bag.global_position.x, 400.0, bag.global_position.z)
	var ray_end: Vector3 = Vector3(bag.global_position.x, -100.0, bag.global_position.z)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		ray_start, ray_end, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var position_value: Variant = hit.get("position")
	if position_value is Vector3:
		bag.set_surface_height((position_value as Vector3).y)
	else:
		bag.set_surface_height(adapter.walking_height)

func _sync_ground_bag() -> void:
	var is_open: bool = bool(AppState.ground_bag.get("open", false))
	ground_bag_panel.visible = is_open
	if not is_open:
		return
	inventory_panel.hide()
	stats_panel.hide()
	full_map.hide()
	trade_panel.hide()
	storage_panel.hide()
	knowledge_panel.hide()
	manufacturing_panel.hide()
	_fill_storage_item_list(ground_bag_items,
		AppState.ground_bag.get("items", {}) as Dictionary, "Ground")
	var backpack: Dictionary = {}
	for raw_slot: Variant in AppState.inventory:
		var slot: int = int(raw_slot)
		if slot >= 0 and slot < 36:
			backpack[slot] = AppState.inventory[raw_slot]
	_fill_storage_item_list(ground_bag_inventory, backpack, "Inventory")
	_sync_ground_bag_actions()

func _sync_ground_bag_actions() -> void:
	ground_bag_pick_button.disabled = ground_bag_items.get_selected_items().is_empty()
	ground_bag_drop_button.disabled = ground_bag_inventory.get_selected_items().is_empty()

func _sync_knowledge() -> void:
	if not knowledge_panel.visible:
		return
	knowledge_list.clear()
	var known_only: bool = knowledge_known_only.button_pressed
	for knowledge_index: int in range(knowledge_catalog.size()):
		var is_known: bool = AppState.known_knowledge.has(knowledge_index)
		if known_only and not is_known:
			continue
		var item_index: int = knowledge_list.item_count
		knowledge_list.add_item("%s  %s" % ["[Read]" if is_known else "[Unread]",
			knowledge_catalog[knowledge_index]])
		knowledge_list.set_item_metadata(item_index, knowledge_index)
		knowledge_list.set_item_tooltip(item_index,
			"Knowledge #%d — %s" % [knowledge_index, "read" if is_known else "unread"])
		if knowledge_index == AppState.selected_knowledge:
			knowledge_list.select(item_index)
	var owned_count: int = AppState.known_knowledge.size()
	if AppState.selected_knowledge < 0 or AppState.selected_knowledge >= knowledge_catalog.size():
		knowledge_detail.text = ("Select an entry to request its server description.\n"
			+ "Read %d of %d knowledge entries." % [owned_count, knowledge_catalog.size()])
		return
	var selected_index: int = AppState.selected_knowledge
	var status: String = "Read" if AppState.known_knowledge.has(selected_index) else "Unread"
	var server_text: String = AppState.knowledge_text
	knowledge_detail.text = "%s\nStatus: %s\nKnowledge ID: %d\n\n%s" % [
		knowledge_catalog[selected_index], status, selected_index,
		server_text if not server_text.is_empty() else "Waiting for the server description…"]

func _sync_manufacturing() -> void:
	if not manufacturing_panel.visible:
		return
	manufacturing_list.clear()
	var filter_text: String = manufacturing_filter.text.strip_edges().to_lower()
	for recipe_index: int in range(manufacturing_catalog.count()):
		var definition: Dictionary = manufacturing_catalog.recipe(recipe_index)
		var searchable: String = (str(definition.get("output", "")) + " "
			+ str(definition.get("skill", ""))).to_lower()
		var ingredients_value: Variant = definition.get("ingredients", [])
		if ingredients_value is Array:
			for ingredient_value: Variant in ingredients_value as Array:
				if ingredient_value is Dictionary:
					searchable += " " + str((ingredient_value as Dictionary).get("name", "")).to_lower()
		if not filter_text.is_empty() and not searchable.contains(filter_text):
			continue
		var availability: Dictionary = manufacturing_catalog.availability(recipe_index,
			AppState.inventory, AppState.known_knowledge, AppState.stats)
		var reasons: Array = availability.get("reasons", []) as Array
		var reason_lines: Array[String] = []
		for reason_value: Variant in reasons:
			reason_lines.append(str(reason_value))
		var prefix: String = "[Ready]" if reasons.is_empty() else "[Blocked]"
		var item_index: int = manufacturing_list.item_count
		manufacturing_list.add_item("%s  %s — %s %d" % [prefix,
			str(definition.get("output", "Unknown")),
			str(definition.get("skill", "skill")).capitalize(),
			int(definition.get("level", 0))])
		manufacturing_list.set_item_metadata(item_index, recipe_index)
		manufacturing_list.set_item_tooltip(item_index,
			"Ready for server validation" if reasons.is_empty() else "\n".join(reason_lines))
		var output_icon: Texture2D = item_atlas.icon_for(int(definition.get("outputImageId", -1)))
		if output_icon != null:
			manufacturing_list.set_item_icon(item_index, output_icon)
		if recipe_index == selected_manufacturing_recipe:
			manufacturing_list.select(item_index)
	_sync_manufacturing_detail()

func _sync_manufacturing_detail() -> void:
	var definition: Dictionary = manufacturing_catalog.recipe(selected_manufacturing_recipe)
	if definition.is_empty():
		manufacturing_detail.text = "Select a server recipe to review exact ingredients."
		manufacturing_status.text = manufacturing_server_status
		manufacturing_mix_one.disabled = true
		manufacturing_mix_all.disabled = true
		return
	var lines: Array[String] = ["[b]%s[/b]" % str(definition.get("output", "Unknown")),
		"%s level %d  •  %d experience  •  food %d  •  mana %d" % [
			str(definition.get("skill", "skill")).capitalize(),
			int(definition.get("level", 0)), int(definition.get("experience", 0)),
			int(definition.get("food", 0)), int(definition.get("mana", 0))], "", "Ingredients:"]
	var ingredients_value: Variant = definition.get("ingredients", [])
	if ingredients_value is Array:
		for ingredient_value: Variant in ingredients_value as Array:
			if ingredient_value is Dictionary:
				var ingredient: Dictionary = ingredient_value as Dictionary
				lines.append("  • %s ×%d" % [str(ingredient.get("name", "Unknown")),
					int(ingredient.get("quantity", 0))])
	var tools_value: Variant = definition.get("tools", [])
	if tools_value is Array and not (tools_value as Array).is_empty():
		lines.append("Tools:")
		for tool_value: Variant in tools_value as Array:
			if tool_value is Dictionary:
				lines.append("  • " + str((tool_value as Dictionary).get("name", "Unknown")))
	var knowledge: String = str(definition.get("knowledge", ""))
	if not knowledge.is_empty():
		lines.append("Knowledge: " + knowledge)
	var availability: Dictionary = manufacturing_catalog.availability(
		selected_manufacturing_recipe, AppState.inventory, AppState.known_knowledge,
		AppState.stats)
	var reasons: Array = availability.get("reasons", []) as Array
	if reasons.is_empty():
		lines.append("\nReady. The server remains authoritative for skill chance, special days, combat, capacity, and ingredient state.")
	else:
		lines.append("\nUnavailable:")
		for reason_value: Variant in reasons:
			lines.append("  • " + str(reason_value))
	manufacturing_detail.text = "\n".join(lines)
	manufacturing_status.text = manufacturing_server_status
	manufacturing_mix_one.disabled = not reasons.is_empty()
	manufacturing_mix_all.disabled = not reasons.is_empty()

func _configure_full_map(manifest: WorldManifest) -> void:
	var asset_value: Variant = manifest.data.get("asset", {})
	if not asset_value is Dictionary:
		return
	var asset: Dictionary = asset_value as Dictionary
	var bounds_value: Variant = asset.get("bounds", {})
	if not bounds_value is Dictionary:
		return
	var bounds: Dictionary = bounds_value as Dictionary
	var min_value: Variant = bounds.get("min", [])
	var max_value: Variant = bounds.get("max", [])
	if not min_value is Array or not max_value is Array:
		return
	var minimum: Array = min_value as Array
	var maximum: Array = max_value as Array
	if minimum.size() < 3 or maximum.size() < 3:
		return
	var center: Vector3 = Vector3(
		(float(minimum[0]) + float(maximum[0])) * 0.5,
		maxf(float(maximum[1]) + 100.0, 300.0),
		(float(minimum[2]) + float(maximum[2])) * 0.5)
	var extent: float = maxf(float(maximum[0]) - float(minimum[0]),
		float(maximum[2]) - float(minimum[2]))
	full_map_camera.global_position = center
	full_map_camera.rotation_degrees = Vector3(-90, 0, 0)
	full_map_camera.size = extent * 1.05
	full_map_camera.far = maxf(2500.0, center.y + 500.0)

func _sync_chat() -> void:
	chat_output.clear()
	if _chat_tab == "options":
		chat_output.append_text("All: recent messages\nHistory: complete session log\n")
		return
	var first_line := 0 if _chat_tab == "history" else maxi(0, AppState.chat_lines.size() - 100)
	for line in AppState.chat_lines.slice(first_line):
		var channel: int = int(line.get("channel", 0))
		var prefix: String = ""
		match channel:
			1: prefix = "[PM] "
			3, 255: prefix = "[System] "
			5, 6, 7: prefix = "[Channel] "
		chat_output.append_text(prefix + str(line.get("text", "")) + "\n")
	chat_output.scroll_to_line(maxi(0, chat_output.get_line_count() - 1))

func _sync_stats() -> void:
	var stats: Dictionary = AppState.stats
	var health: int = int(stats.get("health", 0))
	var max_health: int = maxi(1, int(stats.get("max_health", 1)))
	var ether: int = int(stats.get("ether", 0))
	var max_ether: int = maxi(1, int(stats.get("max_ether", 1)))
	var food: int = int(stats.get("food", 0))
	var max_food: int = maxi(45, food)
	var carried: int = int(stats.get("carried", 0))
	var capacity: int = maxi(1, int(stats.get("capacity", 1)))
	var action: int = int(stats.get("action_points", 0))
	var max_action: int = maxi(1, int(stats.get("max_action_points", 1)))
	_set_meter(health_bar, health_text, health, max_health, "Health")
	_set_meter(mana_bar, mana_text, ether, max_ether, "Ethereality")
	_set_meter(action_bar, action_text, action, max_action, "Action")
	_set_meter(health_bottom, health_bottom_text, health, max_health, "Health")
	_set_meter(ether_bottom, ether_bottom_text, ether, max_ether, "Mana")
	_set_meter(food_bottom, food_bottom_text, food, max_food, "Food")
	_set_meter(load_bottom, load_bottom_text, carried, capacity, "Load")
	_set_meter(action_bottom, action_bottom_text, action, max_action, "Action")
	_sync_experience_meter(stats)
	_set_overhead_meter(overhead_health_row, health, max_health)
	_set_overhead_meter(overhead_ether_row, ether, max_ether)
	_set_overhead_meter(overhead_food_row, food, max_food)
	_set_overhead_meter(overhead_action_row, action, max_action)
	var abbreviated: Array[Array] = [
		["att", "attack"], ["def", "defense"], ["har", "harvesting"],
		["alc", "alchemy"], ["mag", "magic"], ["pot", "potion"],
		["sum", "summoning"], ["man", "manufacturing"], ["cra", "crafting"],
		["eng", "engineering"], ["tai", "tailoring"], ["ran", "ranging"],
		["oa", "overall"]]
	var indicator_cells: Array[String] = []
	for label_and_key: Array in abbreviated:
		indicator_cells.append("[cell]%s[/cell][cell]%d[/cell]" % [
			label_and_key[0], int(stats.get(label_and_key[1], 0))])
	skill_indicators.text = "[table=2]%s[/table]" % "".join(indicator_cells)
	if stats.is_empty():
		return
	var lines: Array[String] = ["[center][b]CHARACTER STATISTICS[/b][/center]"]
	var displayed_stats: Array[Array] = [
		["Physique", "physique"], ["Coordination", "coordination"],
		["Reasoning", "reasoning"], ["Will", "will"],
		["Instinct", "instinct"], ["Vitality", "vitality"],
		["Attack", "attack"], ["Defense", "defense"], ["Magic", "magic"],
		["Harvesting", "harvesting"], ["Alchemy", "alchemy"],
		["Manufacturing", "manufacturing"], ["Summoning", "summoning"],
		["Crafting", "crafting"], ["Engineering", "engineering"],
		["Tailoring", "tailoring"], ["Ranging", "ranging"], ["Overall", "overall"]]
	for label_and_key: Array in displayed_stats:
		lines.append("%s: %d" % [label_and_key[0], int(stats.get(label_and_key[1], 0))])
	stats_text.text = "\n".join(lines)

func _sync_experience_meter(stats: Dictionary) -> void:
	var skill: String = _selected_experience_skill
	var current_experience: int = int(stats.get(skill + "_experience", 0))
	var next_experience: int = int(stats.get(skill + "_experience_next", 0))
	var level: int = int(stats.get(skill + "_base_level", stats.get(skill, 0)))
	var level_floor: int = _experience_floor_for_level(level)
	if next_experience <= level_floor:
		level_floor = 0
	var progress_maximum: int = maxi(1, next_experience - level_floor)
	var progress_value: int = clampi(current_experience - level_floor, 0, progress_maximum)
	experience_bottom.max_value = progress_maximum
	experience_bottom.value = progress_value
	experience_bottom_text.text = "%s %d / %d" % [
		skill.capitalize(), current_experience, next_experience]

static func _experience_floor_for_level(level: int) -> int:
	if level <= 0:
		return 0
	var experience: int = 100
	for index: int in range(1, level + 1):
		if index <= 10:
			experience += experience * 40 / 100
		elif index <= 20:
			experience += experience * 30 / 100
		elif index <= 30:
			experience += experience * 20 / 100
		elif index <= 40:
			experience += experience * 14 / 100
		elif index <= 90:
			experience += experience * 7 / 100
		else:
			experience += experience * 5 / 100
	return experience

static func _set_meter(bar: ProgressBar, label: Label, value: int,
		maximum: int, title: String) -> void:
	bar.max_value = maxi(1, maximum)
	bar.value = clampi(value, 0, maxi(1, maximum))
	label.text = "%s %d / %d" % [title, value, maximum]

static func _set_overhead_meter(row: HBoxContainer, value: int, maximum: int) -> void:
	var bar: ProgressBar = row.get_node("Bar") as ProgressBar
	var label: Label = row.get_node("Number") as Label
	bar.max_value = maxi(1, maximum)
	bar.value = clampi(value, 0, maxi(1, maximum))
	label.text = "%d/%d" % [value, maximum]

func _update_legacy_clock_and_compass() -> void:
	var elapsed_seconds := 0.0
	if AppState.game_minute_anchor_msec > 0:
		elapsed_seconds = maxf(0.0,
			float(Time.get_ticks_msec() - AppState.game_minute_anchor_msec) / 1000.0)
	var minute_fraction: float = fmod(float(AppState.game_minute) + elapsed_seconds / 60.0, 360.0)
	var display_minute: int = floori(minute_fraction)
	clock_text.text = "%d:%02d" % [display_minute / 60, display_minute % 60]
	clock_hand.rotation = fmod(minute_fraction, 60.0) / 60.0 * TAU
	compass_needle.rotation = deg_to_rad(-camera_rig.yaw_degrees)

func _update_actor_resource_overlay() -> void:
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not actor_value is Node3D or not is_instance_valid(actor_value as Node3D):
		actor_resource_overlay.hide()
		return
	var actor_node: Node3D = actor_value as Node3D
	var world_position: Vector3 = actor_node.global_position + Vector3(0.0, 2.8, 0.0)
	if gameplay_camera.is_position_behind(world_position):
		actor_resource_overlay.hide()
		return
	var viewport_position: Vector2 = gameplay_camera.unproject_position(world_position)
	var viewport_scale := Vector2.ONE
	if main_viewport.size.x > 0 and main_viewport.size.y > 0:
		viewport_scale = viewport_container.size / Vector2(main_viewport.size)
	var screen_position: Vector2 = viewport_container.position + viewport_position * viewport_scale
	var overlay_position: Vector2 = screen_position - Vector2(
		actor_resource_overlay.size.x * 0.5, actor_resource_overlay.size.y + 8.0)
	actor_resource_overlay.position = Vector2(
		clampf(overlay_position.x, 4.0,
			maxf(4.0, game_view.size.x - actor_resource_overlay.size.x - 90.0)),
		clampf(overlay_position.y, 34.0,
			maxf(34.0, game_view.size.y - actor_resource_overlay.size.y - 86.0)))
	actor_resource_overlay.visible = (show_overhead_health.button_pressed
		or show_overhead_ether.button_pressed or show_overhead_food.button_pressed
		or show_overhead_action.button_pressed)

func _on_floating_feedback_requested(feedback: Dictionary) -> void:
	if not game_view.visible or AppState.local_actor_id < 0:
		return
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not actor_value is Node3D or not is_instance_valid(actor_value as Node3D):
		return
	var actor_node: Node3D = actor_value as Node3D
	var world_position: Vector3 = actor_node.global_position + Vector3(0.0, 3.15, 0.0)
	if gameplay_camera.is_position_behind(world_position):
		return
	var viewport_position: Vector2 = gameplay_camera.unproject_position(world_position)
	var viewport_scale := Vector2.ONE
	if main_viewport.size.x > 0 and main_viewport.size.y > 0:
		viewport_scale = viewport_container.size / Vector2(main_viewport.size)
	var screen_position: Vector2 = viewport_container.position + viewport_position * viewport_scale
	var kind: String = str(feedback.get("kind", "experience"))
	var skill: String = str(feedback.get("skill", "skill"))
	var label: Label = Label.new()
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.custom_minimum_size = Vector2(190.0, 26.0)
	label.add_theme_font_size_override("font_size", 17 if kind == "level" else 15)
	label.add_theme_color_override("font_outline_color", Color(0.015, 0.02, 0.025, 0.98))
	label.add_theme_constant_override("outline_size", 5)
	if kind == "level":
		label.text = "Level %d %s" % [int(feedback.get("level", 0)), skill.capitalize()]
		label.add_theme_color_override("font_color", Color(1.0, 0.78, 0.22, 1.0))
	else:
		label.text = "+%d %s experience" % [
			int(feedback.get("amount", 0)), skill.capitalize()]
		label.add_theme_color_override("font_color", Color(0.45, 1.0, 0.38, 1.0))
	_floating_feedback_offset = (_floating_feedback_offset + 1) % 4
	label.position = screen_position - Vector2(95.0,
		84.0 + float(_floating_feedback_offset) * 20.0)
	_floating_feedback_layer.add_child(label)
	var tween: Tween = create_tween().set_parallel(true)
	tween.tween_property(label, "position", label.position - Vector2(0.0, 76.0), 1.8).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "modulate:a", 0.0, 1.8).set_delay(0.55)
	tween.finished.connect(label.queue_free)

func _on_window_size_changed() -> void:
	# Match the render viewport to the actual drawable area so resizing changes
	# camera aspect instead of stretching a fixed 16:9 render target.
	var target_size := Vector2i(maxi(1, roundi(viewport_container.size.x)),
		maxi(1, roundi(viewport_container.size.y)))
	if main_viewport.size != target_size:
		main_viewport.size = target_size

func _on_quickbar_mode_pressed(mode: String) -> void:
	var showing_items: bool = mode == "items"
	quick_slot_container.visible = showing_items
	spell_slot_container.visible = not showing_items
	%ItemMode.set_pressed_no_signal(showing_items)
	%SpellMode.set_pressed_no_signal(not showing_items)

func _sync_hud_button_states(force := false) -> void:
	if _hud_icon_regions.is_empty():
		return
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var sitting: bool = bool(local_actor.get("sitting", false))
	var states: Dictionary = {
		%WalkButton: _interaction_mode == "walk" and not sitting,
		%MapButton: full_map.visible,
		%SitButton: sitting,
		%AttackButton: _interaction_mode == "attack",
		%TradeButton: _interaction_mode == "trade" or bool(AppState.trade.get("open", false)),
		%InventoryButton: inventory_panel.visible,
		%StatsButton: stats_panel.visible,
		%KnowledgeButton: knowledge_panel.visible,
		%ManufacturingButton: manufacturing_panel.visible,
		%ChatButton: chat_input.has_focus(),
		%DisconnectButton: AppState.connection_state == "connected"}
	var signature: String = str(states.values())
	if not force and signature == _hud_button_state_signature:
		return
	_hud_button_state_signature = signature
	for button_value: Variant in states:
		var button: Button = button_value as Button
		var active: bool = bool(states[button_value])
		button.set_pressed_no_signal(active)
		var atlas: Texture2D = _hud_active_atlas if active else _hud_inactive_atlas
		if atlas != null:
			button.icon = _atlas_region(atlas, _hud_icon_regions[button_value] as Rect2)

func _build_hud_layout_menu() -> void:
	_floating_feedback_layer = Control.new()
	_floating_feedback_layer.name = "FloatingFeedbackLayer"
	_floating_feedback_layer.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_floating_feedback_layer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_floating_feedback_layer.z_index = 18
	game_view.add_child(_floating_feedback_layer)

	_hud_layout_menu = PopupPanel.new()
	_hud_layout_menu.name = "HudLayoutMenu"
	_hud_layout_menu.size = Vector2i(330, 390)
	add_child(_hud_layout_menu)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 6)
	_hud_layout_menu.add_child(content)
	var title := Label.new()
	title.text = "LOWER HUD INDICATORS"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	content.add_child(title)
	var help := Label.new()
	help.text = "Select a bar, then reorder or hide it."
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content.add_child(help)
	_hud_layout_list = ItemList.new()
	_hud_layout_list.custom_minimum_size = Vector2(310.0, 185.0)
	_hud_layout_list.item_selected.connect(_on_hud_layout_item_selected)
	content.add_child(_hud_layout_list)
	var order_actions := HBoxContainer.new()
	var move_up := Button.new()
	move_up.text = "Move up"
	move_up.pressed.connect(_on_hud_layout_move.bind(-1))
	order_actions.add_child(move_up)
	var move_down := Button.new()
	move_down.text = "Move down"
	move_down.pressed.connect(_on_hud_layout_move.bind(1))
	order_actions.add_child(move_down)
	content.add_child(order_actions)
	_hud_layout_visible = CheckButton.new()
	_hud_layout_visible.text = "Show selected indicator"
	_hud_layout_visible.toggled.connect(_on_hud_layout_visibility_toggled)
	content.add_child(_hud_layout_visible)
	var skill_row := HBoxContainer.new()
	var skill_label := Label.new()
	skill_label.text = "Experience skill"
	skill_row.add_child(skill_label)
	_hud_skill_selector = OptionButton.new()
	_hud_skill_selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	for skill: String in HUD_SKILLS:
		_hud_skill_selector.add_item(skill.capitalize())
		_hud_skill_selector.set_item_metadata(_hud_skill_selector.item_count - 1, skill)
	_hud_skill_selector.item_selected.connect(_on_hud_skill_selected)
	skill_row.add_child(_hud_skill_selector)
	content.add_child(skill_row)
	var close_button := Button.new()
	close_button.text = "Close"
	close_button.pressed.connect(_hud_layout_menu.hide)
	content.add_child(close_button)

func _connect_hud_context_inputs(control: Control) -> void:
	if not control.gui_input.is_connected(_on_lower_hud_gui_input):
		control.gui_input.connect(_on_lower_hud_gui_input)
	for child: Node in control.get_children():
		if child is Control:
			_connect_hud_context_inputs(child as Control)

func _on_lower_hud_gui_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse_event: InputEventMouseButton = event as InputEventMouseButton
	if not mouse_event.pressed or mouse_event.button_index != MOUSE_BUTTON_RIGHT:
		return
	_refresh_hud_layout_menu()
	_hud_layout_menu.position = Vector2i(get_viewport().get_mouse_position())
	_hud_layout_menu.popup()
	get_viewport().set_input_as_handled()

func _refresh_hud_layout_menu() -> void:
	var previous_selection: int = 0
	var selected: PackedInt32Array = _hud_layout_list.get_selected_items()
	if not selected.is_empty():
		previous_selection = int(selected[0])
	_hud_layout_list.clear()
	for meter_key: String in _hud_meter_order:
		var index: int = _hud_layout_list.item_count
		_hud_layout_list.add_item(meter_key.capitalize())
		_hud_layout_list.set_item_metadata(index, meter_key)
		_hud_layout_list.set_item_custom_fg_color(index,
			Color(0.91, 0.86, 0.70) if bool(_hud_meter_visible.get(meter_key, true))
			else Color(0.48, 0.48, 0.48))
	if _hud_layout_list.item_count > 0:
		_hud_layout_list.select(clampi(previous_selection, 0,
			_hud_layout_list.item_count - 1))
		_on_hud_layout_item_selected(int(_hud_layout_list.get_selected_items()[0]))
	for option_index: int in range(_hud_skill_selector.item_count):
		if str(_hud_skill_selector.get_item_metadata(option_index)) == _selected_experience_skill:
			_hud_skill_selector.select(option_index)
			break

func _on_hud_layout_item_selected(index: int) -> void:
	if index < 0 or index >= _hud_layout_list.item_count:
		return
	var meter_key: String = str(_hud_layout_list.get_item_metadata(index))
	_hud_layout_visible.set_pressed_no_signal(bool(_hud_meter_visible.get(meter_key, true)))

func _on_hud_layout_move(direction: int) -> void:
	var selected: PackedInt32Array = _hud_layout_list.get_selected_items()
	if selected.is_empty():
		return
	var source: int = int(selected[0])
	var destination: int = clampi(source + direction, 0, _hud_meter_order.size() - 1)
	if source == destination:
		return
	var meter_key: String = _hud_meter_order[source]
	_hud_meter_order.remove_at(source)
	_hud_meter_order.insert(destination, meter_key)
	_apply_hud_meter_layout()
	_refresh_hud_layout_menu()
	_hud_layout_list.select(destination)
	_save_hud_layout()

func _on_hud_layout_visibility_toggled(enabled: bool) -> void:
	var selected: PackedInt32Array = _hud_layout_list.get_selected_items()
	if selected.is_empty():
		return
	var meter_key: String = str(_hud_layout_list.get_item_metadata(int(selected[0])))
	_hud_meter_visible[meter_key] = enabled
	_apply_hud_meter_layout()
	_refresh_hud_layout_menu()
	_save_hud_layout()

func _on_hud_skill_selected(index: int) -> void:
	if index < 0 or index >= _hud_skill_selector.item_count:
		return
	_selected_experience_skill = str(_hud_skill_selector.get_item_metadata(index))
	_sync_stats()
	_save_hud_layout()

func _meter_node(meter_key: String) -> Control:
	match meter_key:
		"mana": return %ManaMeter
		"food": return %FoodMeter
		"health": return %HealthMeter
		"load": return %LoadMeter
		"action": return %ActionMeter
		"experience": return %ExperienceMeter
		_: return null

func _apply_hud_meter_layout() -> void:
	for index: int in range(_hud_meter_order.size()):
		var meter_key: String = _hud_meter_order[index]
		var meter: Control = _meter_node(meter_key)
		if meter == null:
			continue
		bottom_meters.move_child(meter, index)
		meter.visible = bool(_hud_meter_visible.get(meter_key, true))

func _load_hud_layout() -> void:
	var config := ConfigFile.new()
	if config.load("user://eloria_hud.cfg") == OK:
		var saved_order_value: Variant = config.get_value("lower_hud", "order", _hud_meter_order)
		if saved_order_value is Array:
			var saved_order: Array = saved_order_value as Array
			var validated: Array[String] = []
			for raw_key: Variant in saved_order:
				var key: String = str(raw_key)
				if _hud_meter_order.has(key) and not validated.has(key):
					validated.append(key)
			if validated.size() == _hud_meter_order.size():
				_hud_meter_order = validated
		for meter_key: String in _hud_meter_order:
			_hud_meter_visible[meter_key] = bool(config.get_value(
				"lower_hud", "show_" + meter_key, true))
		var saved_skill: String = str(config.get_value(
			"lower_hud", "experience_skill", _selected_experience_skill))
		if HUD_SKILLS.has(saved_skill):
			_selected_experience_skill = saved_skill
	_apply_hud_meter_layout()

func _save_hud_layout() -> void:
	var config := ConfigFile.new()
	config.set_value("lower_hud", "order", _hud_meter_order)
	for meter_key: String in _hud_meter_order:
		config.set_value("lower_hud", "show_" + meter_key,
			bool(_hud_meter_visible.get(meter_key, true)))
	config.set_value("lower_hud", "experience_skill", _selected_experience_skill)
	var error: Error = config.save("user://eloria_hud.cfg")
	if error != OK:
		push_warning("Unable to save lower HUD preferences: " + error_string(error))

func _build_inventory_slots() -> void:
	for slot: int in range(36):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(64.0, 52.0)
		button.expand_icon = true
		button.text = str(slot + 1)
		button.tooltip_text = "Empty inventory slot %d" % (slot + 1)
		button.disabled = true
		button.pressed.connect(_on_inventory_slot_pressed.bind(slot))
		inventory_grid.add_child(button)
		inventory_slot_buttons.append(button)

func _build_equipment_slots() -> void:
	for index: int in range(8):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(92.0, 48.0)
		button.expand_icon = true
		button.text = "Wear %d" % (index + 1)
		button.tooltip_text = "Generic legacy equipment position %d" % (index + 1)
		button.disabled = true
		button.pressed.connect(_on_equipment_slot_pressed.bind(36 + index))
		equipment_grid.add_child(button)
		equipment_slot_buttons.append(button)

func _bind_quick_slots() -> void:
	var slot: int = 0
	for child: Node in quick_slot_container.get_children():
		if child is Button:
			var button: Button = child as Button
			button.pressed.connect(_on_quick_slot_pressed.bind(slot))
			quick_slot_buttons.append(button)
			slot += 1

func _bind_spell_slots() -> void:
	var slot := 0
	for child: Node in spell_slot_container.get_children():
		if child is Button:
			var button: Button = child as Button
			button.pressed.connect(_cast_spell_slot.bind(slot))
			spell_slot_buttons.append(button)
			slot += 1
	_sync_spells()

func _sync_inventory() -> void:
	for slot: int in range(inventory_slot_buttons.size()):
		var button: Button = inventory_slot_buttons[slot]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			var image_id: int = int(item.get("image_id", 0))
			button.icon = item_atlas.icon_for(image_id)
			button.text = "×%d" % int(item.get("quantity", 0))
			button.tooltip_text = _inventory_tooltip(item)
			button.disabled = false
		else:
			button.icon = null
			button.text = str(slot + 1)
			var can_place: bool = (selected_inventory_slot >= 0
				and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot))
			button.tooltip_text = ("Move selected item to slot %d" % (slot + 1)
				if can_place else "Empty inventory slot %d" % (slot + 1))
			button.disabled = not can_place
	_sync_equipment_slots()
	_sync_quick_slots()
	if selected_inventory_slot >= 0:
		var selected_value: Variant = AppState.inventory.get(selected_inventory_slot)
		if selected_value is Dictionary:
			var selected_item: Dictionary = selected_value as Dictionary
			inventory_use_button.disabled = (not bool(selected_item.get("inventory_usable", false))
				or _inventory_cooldown_remaining(selected_inventory_slot) > 0)
		else:
			selected_inventory_slot = -1
			inventory_use_button.disabled = true
	if not AppState.inventory_text.is_empty():
		inventory_description.text = AppState.inventory_text

func _sync_equipment_slots() -> void:
	for index: int in range(equipment_slot_buttons.size()):
		var slot: int = 36 + index
		var button: Button = equipment_slot_buttons[index]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			button.icon = item_atlas.icon_for(int(item.get("image_id", 0)))
			button.text = "Wear %d ×%d" % [index + 1, int(item.get("quantity", 1))]
			button.tooltip_text = _inventory_tooltip(item) + "\nEquipped position %d" % (index + 1)
			button.disabled = false
		else:
			button.icon = null
			button.text = "Wear %d" % (index + 1)
			var can_equip_here: bool = (selected_inventory_slot >= 0
				and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot))
			button.tooltip_text = ("Equip selected item in generic wear position %d" % (index + 1)
				if can_equip_here else "Empty generic equipment position %d" % (index + 1))
			button.disabled = not can_equip_here
	inventory_equip_button.disabled = (selected_inventory_slot < 0
		or selected_inventory_slot >= 36 or _first_empty_slot(36, 44) < 0)
	inventory_unequip_button.disabled = (selected_inventory_slot < 36
		or selected_inventory_slot >= 44 or _first_empty_slot(0, 36) < 0)

func _sync_quick_slots() -> void:
	for slot: int in range(quick_slot_buttons.size()):
		var quick_button: Button = quick_slot_buttons[slot]
		var quick_item_value: Variant = AppState.inventory.get(slot)
		if quick_item_value is Dictionary:
			var quick_item: Dictionary = quick_item_value as Dictionary
			var usable: bool = bool(quick_item.get("inventory_usable", false))
			var cooldown_seconds: int = _inventory_cooldown_remaining(slot)
			quick_button.icon = item_atlas.icon_for(int(quick_item.get("image_id", 0)))
			quick_button.expand_icon = true
			quick_button.text = "%d  ×%d%s" % [slot + 1, int(quick_item.get("quantity", 0)),
				"\n%ds" % cooldown_seconds if cooldown_seconds > 0 else ""]
			quick_button.disabled = not usable or cooldown_seconds > 0
			quick_button.tooltip_text = ((_inventory_tooltip(quick_item)
				+ "\nCooldown: %d seconds" % cooldown_seconds) if cooldown_seconds > 0 else
				_inventory_tooltip(quick_item) if usable else
				_inventory_tooltip(quick_item) + "\nThis item cannot be used directly.")
		else:
			quick_button.icon = null
			quick_button.text = str(slot + 1)
			quick_button.disabled = true
			quick_button.tooltip_text = "Empty item quick slot"
	if selected_inventory_slot >= 0:
		var selected_value: Variant = AppState.inventory.get(selected_inventory_slot)
		if selected_value is Dictionary:
			var selected_item: Dictionary = selected_value as Dictionary
			inventory_use_button.disabled = (not bool(selected_item.get("inventory_usable", false))
				or _inventory_cooldown_remaining(selected_inventory_slot) > 0)

func _sync_spells() -> void:
	for slot: int in range(spell_slot_buttons.size()):
		var button: Button = spell_slot_buttons[slot]
		if slot >= spell_catalog.default_quick_slots.size():
			button.icon = null
			button.text = "S%d" % (slot + 1)
			button.tooltip_text = "Empty spell quick slot"
			button.disabled = true
			continue
		var spell_id: int = spell_catalog.default_quick_slots[slot]
		var definition: Dictionary = spell_catalog.spell(spell_id)
		var reasons: Array[String] = spell_catalog.unavailable_reasons(
			spell_id, AppState.owned_sigils, AppState.stats, AppState.inventory)
		if not AppState.pending_spell_target.is_empty():
			reasons.append("Complete the pending spell target first")
		button.icon = spell_catalog.icon_for(spell_id)
		button.expand_icon = true
		button.text = "S%d" % (slot + 1)
		button.disabled = not reasons.is_empty()
		button.tooltip_text = _spell_tooltip(definition, reasons, slot)
	match AppState.pending_spell_target:
		"actor":
			spell_status.text = "Select an actor for the spell"
		"location":
			spell_status.text = "Select a ground location for the spell"
		_:
			spell_status.text = _spell_result_text(AppState.last_spell_result)

func _spell_tooltip(definition: Dictionary, reasons: Array[String], slot: int) -> String:
	var lines: Array[String] = [str(definition.get("name", "Unknown spell")),
		str(definition.get("description", "")), "Mana: %d  Magic: %d" % [
			int(definition.get("mana", 0)), int(definition.get("level", 0))],
		"Shortcut: Shift+%d" % (slot + 1)]
	if reasons.is_empty():
		lines.append("Ready; the server validates the cast")
	else:
		lines.append_array(reasons)
	return "\n".join(lines)

func _spell_result_text(result: Dictionary) -> String:
	if result.is_empty():
		return "Spells synchronize with the server"
	var spell_id: int = int(result.get("spell_id", -1))
	var definition: Dictionary = spell_catalog.spell(spell_id)
	var spell_name: String = str(definition.get("name", "spell"))
	match int(result.get("status", 0)):
		1: return "%s cast successfully" % spell_name
		2: return "%s was rejected" % spell_name
		3: return "Invalid or unknown spell"
		4: return "Select an actor for %s" % spell_name
		5: return "Select a location for %s" % spell_name
		_: return "Spell response received"

func _cast_spell_slot(slot: int) -> void:
	if slot < 0 or slot >= spell_catalog.default_quick_slots.size():
		return
	var spell_id: int = spell_catalog.default_quick_slots[slot]
	var reasons: Array[String] = spell_catalog.unavailable_reasons(
		spell_id, AppState.owned_sigils, AppState.stats, AppState.inventory)
	if not reasons.is_empty() or not AppState.pending_spell_target.is_empty():
		return
	var definition: Dictionary = spell_catalog.spell(spell_id)
	var sigils_value: Variant = definition.get("sigils", [])
	if not sigils_value is Array:
		return
	var sigils: Array[int] = []
	for raw_sigil: Variant in sigils_value:
		sigils.append(int(raw_sigil))
	var error: Error = Network.cast_spell(sigils)
	if error != OK:
		push_warning("CAST_SPELL failed: " + error_string(error))
	else:
		spell_status.text = "Casting %s…" % str(definition.get("name", "spell"))

func _inventory_cooldown_remaining(slot: int) -> int:
	var cooldown_value: Variant = AppState.inventory_cooldowns.get(slot)
	if not cooldown_value is Dictionary:
		return 0
	var cooldown: Dictionary = cooldown_value as Dictionary
	var remaining_msec: int = int(cooldown.get("end_msec", 0)) - Time.get_ticks_msec()
	return maxi(0, ceili(float(remaining_msec) / 1000.0))

func _inventory_tooltip(item: Dictionary) -> String:
	var traits: Array[String] = []
	for flag_and_label: Array in [
		["inventory_usable", "usable"], ["stackable", "stackable"],
		["resource", "resource"], ["reagent", "reagent"]]:
		if bool(item.get(flag_and_label[0], false)):
			traits.append(str(flag_and_label[1]))
	var image_id: int = int(item.get("image_id", 0))
	var tooltip: String = "Item image #%d — quantity %d%s" % [image_id,
		int(item.get("quantity", 0)), " — " + ", ".join(traits) if not traits.is_empty() else ""]
	if item_atlas.uses_substitute(image_id):
		tooltip += "\nIndependent Eloria icon substitute for legacy image #%d." % image_id
	return tooltip

func _on_inventory_slot_pressed(slot: int) -> void:
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	var item: Dictionary = AppState.inventory.get(slot, {}) as Dictionary
	inventory_use_button.disabled = not bool(item.get("inventory_usable", false))
	_sync_equipment_slots()
	inventory_description.text = "Inspecting item image #%d…" % int(item.get("image_id", 0))
	var error: Error = Network.look_at_inventory_item(slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))
	_sync_inventory()

func _on_equipment_slot_pressed(slot: int) -> void:
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	inventory_use_button.disabled = true
	_sync_equipment_slots()
	var error: Error = Network.look_at_inventory_item(slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))
	_sync_inventory()

func _first_empty_slot(start: int, end: int) -> int:
	for slot: int in range(start, end):
		if not AppState.inventory.has(slot):
			return slot
	return -1

func _move_inventory_item(source: int, destination: int) -> void:
	var error: Error = Network.move_inventory_item(source, destination)
	if error != OK:
		push_warning("MOVE_INVENTORY_ITEM failed: " + error_string(error))

func _on_quick_slot_pressed(slot: int) -> void:
	_use_inventory_slot(slot)

func _use_inventory_slot(slot: int) -> void:
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var item: Dictionary = item_value as Dictionary
	if not bool(item.get("inventory_usable", false)) or _inventory_cooldown_remaining(slot) > 0:
		return
	var error: Error = Network.use_inventory_item(slot)
	if error != OK:
		push_warning("USE_INVENTORY_ITEM failed: " + error_string(error))

func _on_chat_submitted(text: String) -> void:
	var message: String = text.strip_edges()
	if message.is_empty():
		chat_input.release_focus()
		return
	var is_private: bool = message.begins_with("/") and message.length() > 1
	var error: Error = (Network.send_private_message(message.substr(1))
		if is_private else Network.send_chat(message))
	if error == OK:
		chat_input.clear()
	else:
		push_warning(("SEND_PM" if is_private else "RAW_TEXT")
			+ " failed: " + error_string(error))

func _sync_trade() -> void:
	var is_open: bool = bool(AppState.trade.get("open", false))
	trade_panel.visible = is_open
	if not is_open:
		selected_trade_side = ""
		trade_was_open = false
		_reset_trade_destinations()
		return
	if not trade_was_open:
		trade_was_open = true
		_reset_trade_destinations()
	if not bool(AppState.trade.get("storage_available", false)):
		_reset_trade_destinations()
	inventory_panel.hide()
	stats_panel.hide()
	full_map.hide()
	storage_panel.hide()
	knowledge_panel.hide()
	manufacturing_panel.hide()
	trade_partner.text = "Trading with %s%s" % [
		str(AppState.trade.get("partner", "another player")),
		" — storage destinations available" if bool(
			AppState.trade.get("storage_available", false)) else ""]
	_fill_trade_list(trade_source,
		AppState.trade.get("source_inventory", {}) as Dictionary, "Inventory")
	_fill_trade_list(trade_own_offers,
		AppState.trade.get("own_offers", {}) as Dictionary, "Offer")
	_fill_trade_list(trade_other_offers,
		AppState.trade.get("other_offers", {}) as Dictionary, "Offer")
	var own_accepts: int = int(AppState.trade.get("own_accepts", 0))
	var other_accepts: int = int(AppState.trade.get("other_accepts", 0))
	trade_status.text = "You: %s  •  %s: %s" % [
		_trade_acceptance_text(own_accepts), str(AppState.trade.get("partner", "Partner")),
		_trade_acceptance_text(other_accepts)]
	if own_accepts == 0:
		trade_accept_button.text = "Accept offer (1/2)"
		trade_accept_button.disabled = false
	elif own_accepts == 1 and other_accepts >= 1:
		trade_accept_button.text = "Confirm trade (2/2)"
		trade_accept_button.disabled = false
	elif own_accepts == 1:
		trade_accept_button.text = "Waiting for partner"
		trade_accept_button.disabled = true
	else:
		trade_accept_button.text = "Confirmed — waiting"
		trade_accept_button.disabled = true
	trade_reject_button.disabled = own_accepts == 0 and other_accepts == 0
	_sync_trade_actions()

func _fill_trade_list(list_control: ItemList, items: Dictionary, prefix: String) -> void:
	list_control.clear()
	var slots: Array = items.keys()
	slots.sort()
	for raw_slot: Variant in slots:
		var slot: int = int(raw_slot)
		var item_value: Variant = items.get(slot)
		if not item_value is Dictionary:
			continue
		var item: Dictionary = item_value as Dictionary
		var image_id: int = int(item.get("image_id", 0))
		var index: int = list_control.item_count
		list_control.add_item("%s %d  •  item #%d  ×%d" % [
			prefix, slot + 1, image_id, int(item.get("quantity", 0))])
		list_control.set_item_metadata(index, slot)
		var icon: Texture2D = item_atlas.icon_for(image_id)
		if icon != null:
			list_control.set_item_icon(index, icon)

func _trade_list_slot(list_control: ItemList, index: int) -> int:
	if index < 0 or index >= list_control.item_count:
		return -1
	var metadata: Variant = list_control.get_item_metadata(index)
	return int(metadata) if metadata != null else -1

func _sync_trade_actions() -> void:
	trade_offer_button.disabled = trade_source.get_selected_items().is_empty()
	trade_remove_button.disabled = trade_own_offers.get_selected_items().is_empty()
	var selected_other: PackedInt32Array = trade_other_offers.get_selected_items()
	var destination_available: bool = (bool(AppState.trade.get("storage_available", false))
		and not selected_other.is_empty())
	trade_storage_destination.disabled = not destination_available
	var destination_is_storage: bool = false
	if destination_available:
		var offer_slot: int = _trade_list_slot(trade_other_offers, int(selected_other[0]))
		destination_is_storage = (offer_slot >= 0 and offer_slot < trade_destinations.size()
			and int(trade_destinations[offer_slot]) == 2)
	trade_storage_destination.set_pressed_no_signal(destination_is_storage)

func _reset_trade_destinations() -> void:
	trade_destinations.resize(16)
	trade_destinations.fill(1)

func _trade_acceptance_text(value: int) -> String:
	match value:
		1: return "accepted"
		2: return "confirmed"
		_: return "reviewing"

func _sync_storage() -> void:
	var is_open: bool = bool(AppState.storage.get("open", false))
	storage_panel.visible = is_open
	if not is_open:
		selected_storage_side = ""
		return
	inventory_panel.hide()
	stats_panel.hide()
	full_map.hide()
	trade_panel.hide()
	knowledge_panel.hide()
	manufacturing_panel.hide()
	storage_categories.clear()
	var active_category: int = int(AppState.storage.get("category_id", -1))
	var raw_categories: Variant = AppState.storage.get("categories", [])
	if raw_categories is Array:
		for raw_category: Variant in raw_categories:
			if not raw_category is Dictionary:
				continue
			var category: Dictionary = raw_category as Dictionary
			var index: int = storage_categories.item_count
			storage_categories.add_item(str(category.get("name", "Category")))
			storage_categories.set_item_metadata(index, int(category.get("id", -1)))
			if int(category.get("id", -1)) == active_category:
				storage_categories.select(index)
	_fill_storage_item_list(storage_items,
		AppState.storage.get("items", {}) as Dictionary, "Stored")
	var backpack: Dictionary = {}
	for raw_slot: Variant in AppState.inventory:
		var slot: int = int(raw_slot)
		if slot >= 0 and slot < 36:
			backpack[slot] = AppState.inventory[raw_slot]
	_fill_storage_item_list(storage_inventory, backpack, "Inventory")
	var message: String = str(AppState.storage.get("text", ""))
	storage_status.text = (message if not message.is_empty() else
		"Select an inventory item to deposit or a stored item to withdraw.")
	_sync_storage_actions()

func _fill_storage_item_list(list_control: ItemList, items: Dictionary, prefix: String) -> void:
	list_control.clear()
	var positions: Array = items.keys()
	positions.sort()
	for raw_position: Variant in positions:
		var position: int = int(raw_position)
		var item_value: Variant = items.get(position)
		if not item_value is Dictionary:
			continue
		var item: Dictionary = item_value as Dictionary
		var image_id: int = int(item.get("image_id", 0))
		var index: int = list_control.item_count
		list_control.add_item("%s %d  •  item #%d  ×%d" % [prefix,
			position + 1, image_id, int(item.get("quantity", 0))])
		list_control.set_item_metadata(index, position)
		var icon: Texture2D = item_atlas.icon_for(image_id)
		if icon != null:
			list_control.set_item_icon(index, icon)

func _list_metadata_int(list_control: ItemList, index: int) -> int:
	if index < 0 or index >= list_control.item_count:
		return -1
	var metadata: Variant = list_control.get_item_metadata(index)
	return int(metadata) if metadata != null else -1

func _sync_storage_actions() -> void:
	var inventory_selected: bool = not storage_inventory.get_selected_items().is_empty()
	var storage_selected: bool = not storage_items.get_selected_items().is_empty()
	storage_deposit_button.disabled = not inventory_selected
	storage_withdraw_button.disabled = not storage_selected
	storage_inspect_button.disabled = not storage_selected

func _sync_selection() -> void:
	var dto: Dictionary = AppState.actors.get(AppState.selected_actor_id, {})
	if dto.is_empty():
		selected_target.text = "Target: none"
	else:
		selected_target.text = "Target: %s  Health: %d / %d%s" % [
			str(dto.get("name", "Actor %d" % AppState.selected_actor_id)),
			int(dto.get("health", 0)), int(dto.get("max_health", 0)),
			"  [combat]" if bool(dto.get("in_combat", false)) else ""]
	var can_attack: bool = _is_attackable_actor(AppState.selected_actor_id, dto)
	attack_button.disabled = not can_attack
	attack_button.tooltip_text = ("Attack selected target [A] or Alt-click; the server approaches and validates combat"
		if can_attack else "Select a living player or creature to attack")
	var can_trade: bool = _is_tradeable_player(AppState.selected_actor_id, dto)
	trade_button.disabled = not can_trade
	trade_button.tooltip_text = ("Request or accept trade with the selected player; both players must be within four tiles"
		if can_trade else "Select a living player to trade")
	for raw_id: Variant in actor_nodes.keys():
		var id: int = int(raw_id)
		var actor: ReplicatedActor3D = actor_nodes.get(id) as ReplicatedActor3D
		if is_instance_valid(actor):
			actor.set_selected(id == AppState.selected_actor_id)

func _is_attackable_actor(actor_id: int, dto: Dictionary) -> bool:
	if actor_id < 0 or actor_id == AppState.local_actor_id or dto.is_empty():
		return false
	var kind: int = int(dto.get("kind", 0))
	return kind in [1, 3, 4, 5] and bool(dto.get("alive", int(dto.get("health", 0)) > 0))

func _is_tradeable_player(actor_id: int, dto: Dictionary) -> bool:
	if actor_id < 0 or actor_id == AppState.local_actor_id or dto.is_empty():
		return false
	var kind: int = int(dto.get("kind", 0))
	return kind in [1, 4] and bool(dto.get("alive", int(dto.get("health", 0)) > 0))

func _attack_selected_actor() -> void:
	var actor_id: int = AppState.selected_actor_id
	var dto: Dictionary = AppState.actors.get(actor_id, {})
	if _is_attackable_actor(actor_id, dto):
		_send_attack(actor_id)

func _send_attack(actor_id: int) -> void:
	print_debug("combat_input command=ATTACK_SOMEONE target_actor_id=", actor_id,
		" redacted_bytes=not_sensitive")
	var error: Error = Network.attack_actor(actor_id)
	if error != OK:
		push_warning("ATTACK_SOMEONE failed: " + error_string(error))

func _sync_dialogue() -> void:
	var dialogue: Dictionary = AppState.npc_dialogue
	dialogue_panel.visible = bool(dialogue.get("open", false))
	if not dialogue_panel.visible:
		return
	dialogue_name.text = str(dialogue.get("name", "NPC"))
	dialogue_text.text = str(dialogue.get("text", ""))
	for child: Node in dialogue_options.get_children():
		child.queue_free()
	var raw_options: Variant = dialogue.get("options", [])
	if raw_options is Array:
		for raw_option: Variant in raw_options:
			if not raw_option is Dictionary:
				continue
			var option: Dictionary = raw_option as Dictionary
			var button: Button = Button.new()
			button.text = str(option.get("label", "Continue"))
			button.pressed.connect(_on_dialogue_option.bind(
				int(option.get("actor_id", -1)), int(option.get("response_id", -1))))
			dialogue_options.add_child(button)

func _on_dialogue_option(actor_id: int, response_id: int) -> void:
	if actor_id < 0 or response_id < 0:
		return
	var error: Error = Network.respond_to_npc(actor_id, response_id)
	if error != OK:
		push_warning("RESPOND_TO_NPC failed: " + error_string(error))

func _viewport_position(global_position: Vector2) -> Vector2:
	var local_position: Vector2 = viewport_container.get_global_transform().affine_inverse() * global_position
	return _local_viewport_position(local_position)

func _local_viewport_position(local_position: Vector2) -> Vector2:
	if viewport_container.size.x <= 0.0 or viewport_container.size.y <= 0.0:
		return local_position
	return local_position * Vector2(main_viewport.size) / viewport_container.size

func _pick_actor(viewport_position: Vector2) -> int:
	if gameplay_world == null:
		push_warning("world_input actor_pick skipped: World3D unavailable")
		return -1
	var origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + camera_rig.ray_direction(viewport_position) * 2000.0, 2)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var collider_value: Variant = hit.get("collider")
	if collider_value is ReplicatedActor3D:
		return (collider_value as ReplicatedActor3D).actor_id
	return -1

func _pick_ground_bag(viewport_position: Vector2) -> int:
	if gameplay_world == null:
		return -1
	var origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + camera_rig.ray_direction(viewport_position) * 2000.0,
		GroundBag3D.PICK_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var collider_value: Variant = hit.get("collider")
	if collider_value is GroundBag3D:
		return (collider_value as GroundBag3D).bag_id
	return -1

func _apply_eloria_art() -> void:
	login_background.texture = _external_texture("res://assets/ui/eloria_login_background.jpg")
	login_logo.texture = _external_texture("res://assets/ui/eloria_logo_master.png")
	_hud_active_atlas = _external_texture("res://assets/ui/eloria_gamebuttons.png")
	_hud_inactive_atlas = _external_texture("res://assets/ui/eloria_gamebuttons_inactive.png")
	if _hud_active_atlas != null:
		_hud_icon_regions = {
			%WalkButton: Rect2(0, 0, 32, 32), %ChatButton: Rect2(32, 0, 32, 32),
			%KnowledgeButton: Rect2(96, 0, 32, 32), %AttackButton: Rect2(160, 0, 32, 32),
			%StatsButton: Rect2(192, 0, 32, 32), %SitButton: Rect2(0, 32, 32, 32),
			%TradeButton: Rect2(64, 32, 32, 32), %InventoryButton: Rect2(96, 32, 32, 32),
			%ManufacturingButton: Rect2(128, 32, 32, 32),
			%DisconnectButton: Rect2(224, 0, 32, 32), %MapButton: Rect2(128, 128, 32, 32)}
		for button_value: Variant in _hud_icon_regions:
			var icon_button: Button = button_value as Button
			icon_button.icon = _atlas_region(_hud_active_atlas,
				_hud_icon_regions[button_value] as Rect2)
			icon_button.text = ""
			icon_button.expand_icon = true
			icon_button.toggle_mode = true
		_sync_hud_button_states(true)
	var hud_atlas: Texture2D = _external_texture("res://assets/ui/eloria_hud_atlas.png")
	if hud_atlas != null:
		%ClockFace.texture = _atlas_region(hud_atlas, Rect2(0, 128, 64, 64))
		%CompassFace.texture = _atlas_region(hud_atlas, Rect2(32, 192, 64, 64))

static func _atlas_region(atlas: Texture2D, region: Rect2) -> AtlasTexture:
	var texture: AtlasTexture = AtlasTexture.new()
	texture.atlas = atlas
	texture.region = region
	return texture

func _apply_eloria_theme() -> void:
	var eloria_theme: Theme = Theme.new()
	var panel: StyleBoxFlat = StyleBoxFlat.new()
	panel.bg_color = Color(0.045, 0.075, 0.09, 0.92)
	panel.border_color = Color(0.72, 0.53, 0.22, 0.95)
	panel.set_border_width_all(2)
	panel.corner_radius_top_left = 1
	panel.corner_radius_top_right = 1
	panel.corner_radius_bottom_left = 1
	panel.corner_radius_bottom_right = 1
	panel.set_content_margin_all(4.0)
	eloria_theme.set_stylebox("panel", "PanelContainer", panel)
	var button: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	button.bg_color = Color(0.11, 0.18, 0.19, 0.96)
	button.set_border_width_all(1)
	button.set_content_margin_all(4.0)
	eloria_theme.set_stylebox("normal", "Button", button)
	var button_hover: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	button_hover.bg_color = Color(0.23, 0.31, 0.28, 0.98)
	button_hover.border_color = Color(0.94, 0.72, 0.30, 1.0)
	eloria_theme.set_stylebox("hover", "Button", button_hover)
	eloria_theme.set_stylebox("pressed", "Button", button_hover)
	var field: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	field.bg_color = Color(0.025, 0.045, 0.055, 0.98)
	eloria_theme.set_stylebox("normal", "LineEdit", field)
	eloria_theme.set_color("font_color", "Label", Color(0.91, 0.86, 0.70))
	eloria_theme.set_color("font_color", "Button", Color(0.96, 0.88, 0.66))
	theme = eloria_theme
	_style_meter(health_bar, Color(0.17, 0.82, 0.22, 1.0))
	_style_meter(health_bottom, Color(0.9, 0.16, 0.14, 1.0))
	_style_meter(food_bottom, Color(0.96, 0.78, 0.16, 1.0))
	_style_meter(load_bottom, Color(0.62, 0.43, 0.34, 1.0))
	_style_meter(experience_bottom, Color(0.18, 0.76, 0.22, 1.0))
	_style_meter(overhead_health_row.get_node("Bar") as ProgressBar,
		Color(0.12, 0.9, 0.18, 1.0))
	for ether_bar: ProgressBar in [mana_bar, ether_bottom,
		overhead_ether_row.get_node("Bar") as ProgressBar]:
		_style_meter(ether_bar, Color(0.24, 0.31, 1.0, 1.0))
	_style_meter(overhead_food_row.get_node("Bar") as ProgressBar,
		Color(0.96, 0.78, 0.16, 1.0))
	for points_bar: ProgressBar in [action_bar, action_bottom,
		overhead_action_row.get_node("Bar") as ProgressBar]:
		_style_meter(points_bar, Color(0.73, 0.28, 0.86, 1.0))

static func _style_meter(bar: ProgressBar, color: Color) -> void:
	var background := StyleBoxFlat.new()
	background.bg_color = Color(0.015, 0.02, 0.025, 0.96)
	background.border_color = Color(0.72, 0.53, 0.22, 0.9)
	background.set_border_width_all(1)
	var fill := background.duplicate() as StyleBoxFlat
	fill.bg_color = color
	fill.border_color = color.lightened(0.18)
	bar.add_theme_stylebox_override("background", background)
	bar.add_theme_stylebox_override("fill", fill)

static func _external_texture(path: String) -> Texture2D:
	if path.begins_with("res://assets/"):
		var imported: Resource = ResourceLoader.load(path)
		if imported is Texture2D:
			return imported as Texture2D
		push_warning("Imported UI texture load failed: " + path)
		return null
	var absolute_path: String = ProjectSettings.globalize_path(path)
	var image: Image = Image.new()
	var error: Error
	if path.get_extension().to_lower() == "dds":
		var bytes: PackedByteArray = FileAccess.get_file_as_bytes(absolute_path)
		error = image.load_dds_from_buffer(bytes)
	else:
		error = image.load(absolute_path)
	if error != OK or image.is_empty():
		push_warning("UI texture load failed: " + path)
		return null
	return ImageTexture.create_from_image(image)

func _model_for_actor(dto: Dictionary) -> String:
	var actor_type_value := int(dto.get("actor_type", 1))
	var actor_type := str(actor_type_value)
	var kind := int(dto.get("kind", 0))
	# Player actor IDs are not safe for NPC wire records: the server may send an
	# enhanced packet for an NPC while keeping the legacy actor_type byte at 1.
	# Nymara NPC/creature/enemy IDs occupy the dedicated 200+ registry range.
	if actor_type_models.has(actor_type) and (kind in [1, 4] or actor_type_value >= 200):
		return str(actor_type_models[actor_type])
	# The server uses the enhanced wire layout for most NPCs so their appearance
	# bytes survive replication. Registry actor type wins for native NPCs and
	# creatures; actor kind decides the fallback for unknown records.
	if kind not in [1, 4]:
		return ""
	return "luminous_female" if actor_type_value == 0 else "luminous_male"

func _presentation_dto(dto: Dictionary) -> Dictionary:
	var result: Dictionary = dto.duplicate(true)
	var actor_type: int = int(dto.get("actor_type", -1))
	var appearance: Dictionary = dto.get("appearance", {}) as Dictionary
	var visuals: Dictionary = AppearanceVariants.equipment_visuals(
		actor_type, appearance)
	var look: Dictionary = npc_looks.get(str(int(dto.get("actor_type", -1))), {}) as Dictionary
	var look_visuals: Dictionary = look.get("equipmentVisuals", {}) as Dictionary
	for raw_part: Variant in look_visuals:
		visuals[raw_part] = look_visuals[raw_part]
	var server_visuals: Dictionary = dto.get("equipment_visuals", {}) as Dictionary
	for raw_part: Variant in server_visuals:
		var part: int = int(raw_part)
		var visual_id: int = int(server_visuals[raw_part])
		# Enhanced actor records repeat the legacy creation bytes in parts 3–6.
		# Values below 100 are choices, not native equipment visual IDs.
		if part not in [AppearanceVariants.PART_HEAD,
				AppearanceVariants.PART_PANTS, AppearanceVariants.PART_SHIRT,
				AppearanceVariants.PART_BOOTS] or visual_id >= 100:
			visuals[raw_part] = visual_id
	result["equipment_visuals"] = visuals
	return result

func _animation_for_model(model_config: Dictionary) -> Dictionary:
	var path := str(model_config.get("animationMap", "res://data/animations/luminous.json"))
	if not animation_configs.has(path):
		animation_configs[path] = _json(path)
	return animation_configs[path] as Dictionary

static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}
