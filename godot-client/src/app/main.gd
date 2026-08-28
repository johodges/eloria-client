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
@onready var preview_viewport: SubViewport = $CreationPanel/Columns/CharacterPreview/Viewport
@onready var preview_root: Node3D = %PreviewRoot
@onready var preview_camera: Camera3D = %PreviewCamera
@onready var preview_key_light: DirectionalLight3D = %KeyLight
@onready var preview_fill_light: DirectionalLight3D = %FillLight
@onready var preview_rim_light: DirectionalLight3D = %RimLight
@onready var host_edit: LineEdit = %Host
@onready var port_edit: SpinBox = %Port
@onready var user_edit: LineEdit = %Username
@onready var password_edit: LineEdit = %Password
@onready var connect_button: Button = %Connect
@onready var login_button: Button = %Login
@onready var status_label: Label = %Status
@onready var world_root: Node3D = %WorldRoot
@onready var camera_rig: IsometricCameraController = %CameraRig

# Preloaded, and left untyped, so the script resolves without depending on
# Godot's global class-name cache -- that cache is a build artifact and is
# stale in a working copy until the editor next scans the project.
const InteriorCutawayScript := preload("res://src/world/interior_cutaway.gd")
const InvasionAssistantScript := preload("res://src/ui/invasion_assistant.gd")
var interior_cutaway: RefCounted = InteriorCutawayScript.new()
var invasion_assistant_window
@onready var gameplay_camera: Camera3D = %Camera
@onready var world_loader: WorldLoader = %WorldLoader
@onready var fallback_ground: MeshInstance3D = $GameView/ViewportContainer/Viewport/WorldRoot/Ground
@onready var world_environment: WorldEnvironment = $GameView/ViewportContainer/Viewport/WorldRoot/Environment
@onready var world_sun: DirectionalLight3D = $GameView/ViewportContainer/Viewport/WorldRoot/Sun

var ambient_population: AmbientPopulation
var map_light_root: Node3D
@onready var main_viewport: SubViewport = $GameView/ViewportContainer/Viewport
@onready var viewport_container: TextureRect = $GameView/ViewportContainer
@onready var map_viewport: SubViewport = %MapViewport
@onready var map_camera: Camera3D = %MapCamera
@onready var full_map_viewport: SubViewport = %FullMapViewport
@onready var full_map_camera: Camera3D = %FullMapCamera
@onready var minimap: TextureRect = %Minimap
@onready var minimap_frame: Panel = %MinimapFrame
@onready var full_map: Control = %FullMap
@onready var map_image: TextureRect = %MapImage
@onready var map_title: Label = %MapTitle
@onready var map_coordinates: Label = %MapCoordinates
@onready var continent_button: TextureButton = %ContinentButton
@onready var current_map_button: Button = %CurrentMapButton
@onready var region_preview: TextureRect = %RegionPreview
@onready var continent_view: Control = %ContinentView
@onready var continent_image: TextureRect = %ContinentImage
@onready var region_buttons: VBoxContainer = %RegionButtons
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
@onready var clock_face: TextureRect = %ClockFace
@onready var compass_needle: Line2D = %CompassNeedle
@onready var compass_face: TextureRect = %CompassFace
@onready var hud_logo: TextureRect = %HudLogo
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
@onready var stats_tabs: TabContainer = %StatsTabs
@onready var stats_close: Button = %StatsClose
@onready var counter_categories: ItemList = %CounterCategories
@onready var counter_text: RichTextLabel = %CounterText
@onready var session_xp_text: RichTextLabel = %SessionXpText
@onready var session_reset: Button = %SessionReset
@onready var inventory_panel: Control = %InventoryPanel
@onready var inventory_header: Control = $GameView/InventoryPanel/Content/Header
@onready var inventory_resize_grip: Control = %InventoryResizeGrip
@onready var inventory_grid: GridContainer = %InventoryGrid
@onready var equipment_grid: GridContainer = %EquipmentGrid
@onready var inventory_body: HBoxContainer = %InventoryBody
@onready var equipment_column: VBoxContainer = %EquipmentColumn
@onready var backpack_column: VBoxContainer = %BackpackColumn
@onready var inventory_description: RichTextLabel = %InventoryDescription
@onready var inventory_use_button: Button = %InventoryUse
@onready var inventory_equip_button: Button = %InventoryEquip
@onready var inventory_unequip_button: Button = %InventoryUnequip
@onready var inventory_store_all: Button = %InventoryStoreAll
@onready var inventory_get_all: Button = %InventoryGetAll
@onready var inventory_drop_all: Button = %InventoryDropAll
@onready var inventory_mix_all: Button = %InventoryMixAll
@onready var inventory_item_lists: Button = %InventoryItemLists
@onready var inventory_load: Label = %InventoryLoad
@onready var item_lists_panel: Control = %ItemListsPanel
@onready var saved_item_lists: ItemList = %SavedItemLists
@onready var item_list_name: LineEdit = %ItemListName
@onready var item_list_entries: TextEdit = %ItemListEntries
@onready var item_list_status: Label = %ItemListStatus
@onready var item_list_save: Button = %ItemListSave
@onready var item_list_delete: Button = %ItemListDelete
@onready var item_list_get: Button = %ItemListGet
@onready var item_lists_close: Button = %ItemListsClose
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
@onready var chat_panel: PanelContainer = $GameView/ChatPanel
@onready var console_panel: PanelContainer = %ConsolePanel
@onready var console_output: RichTextLabel = %ConsoleOutput
@onready var settings_panel: PanelContainer = %SettingsPanel
@onready var minimap_size: HSlider = %MinimapSize
@onready var minimap_size_value: Label = %MinimapSizeValue
@onready var ui_scale_slider: HSlider = %UiScale
@onready var ui_scale_value: Label = %UiScaleValue
@onready var equipment_side: OptionButton = %EquipmentSide
@onready var minimap_north: Label = %North
@onready var minimap_east: Label = %East
@onready var minimap_south: Label = %South
@onready var minimap_west: Label = %West
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
var cartography: Dictionary = {}
var cartography_regions: Array = []
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
var preview_distance := 2.65
var inventory_slot_buttons: Array[Button] = []
var inventory_quantity_labels: Array[Label] = []
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
var _last_chat_activity_msec := 0
var _current_map_display_name := "Unknown map"
var _minimap_scale := 1.0
var _minimap_orientation := "north_up"
var _minimap_dragging := false
var _minimap_drag_offset := Vector2.ZERO
var _inventory_scale := 1.0
var _inventory_dragging := false
var _inventory_resizing := false
var _inventory_drag_offset := Vector2.ZERO
var _inventory_resize_start_mouse := Vector2.ZERO
var _inventory_resize_start_scale := 1.0
var _equipment_side := "left"
var _ui_scale := 1.0
var _bulk_exclusions: Dictionary = {
	"store": [false, false, false, false],
	"drop": [false, false, false, false]}
var _item_lists: Dictionary = {}
var _store_options_menu: PopupMenu
var _drop_options_menu: PopupMenu
var _minimap_menu: PopupMenu
var _session_started_msec := 0
var _experience_snapshot: Dictionary = {}
var _session_xp_gain: Dictionary = {}
var _session_xp_max: Dictionary = {}
var _session_xp_last: Dictionary = {}
var _session_distance := 0
var _last_distance_tile := Vector2i(-99999, -99999)
var _session_counters: Dictionary = {}
var _total_counters: Dictionary = {}
var _keyboard_moving := false
var _keyboard_running := false
var _keyboard_direction := Vector2i.ZERO
var _keyboard_goal_tile := Vector2i(-99999, -99999)
var _keyboard_refresh_msec := 0
var _ground_bag_get_all_requested_msec := -1
var _ground_bag_get_all_bag_id := -1
var _selected_counter_category := "Kills"
var _known_perks: Array[String] = []
var _perk_capture_until_msec := 0
var _right_mouse_down := false
var _right_mouse_dragged := false
var _interaction_mode := "walk"
var _hud_icon_regions: Dictionary = {}
var _hud_active_atlas: Texture2D
var _hud_inactive_atlas: Texture2D
var _hud_button_state_mask := -1
var _hud_state_buttons: Array[Button] = []
var _minimap_refresh_msec := 0
var _full_map_refresh_msec := 0
var _preview_updates_enabled := true
var _world_sync_queued := false
var _actor_surface_samples: Dictionary = {}
var _local_placement_logged := false
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

const CHAT_FADE_DELAY_MSEC := 7000
const CHAT_FADE_DURATION_MSEC := 1800
const SETTINGS_PATH := "user://eloria_hud.cfg"
const KEYBOARD_LOOKAHEAD_TILES := 4
const KEYBOARD_REFRESH_MSEC := 360
const GROUND_BAG_GET_ALL_TIMEOUT_MSEC := 1000
const MINIMAP_DRAG_BORDER := 54.0
const UI_SCALE_MIN := 0.5
const UI_SCALE_MAX := 1.5
# The minimap and the full map are extra renders of the whole 3D world through
# their own cameras. Both used to redraw every frame, visible or not, which
# tripled the client's raster and shadow cost for two top-down views that read
# identically at a fraction of the rate.
const MINIMAP_REFRESH_MSEC := 66
const FULL_MAP_REFRESH_MSEC := 200
const INVENTORY_MIN_SCALE := 0.65
const INVENTORY_MAX_SCALE := 1.75
const TILE_DIRECTIONS: Array[Vector2i] = [
	Vector2i(0, -1), Vector2i(1, -1), Vector2i(1, 0), Vector2i(1, 1),
	Vector2i(0, 1), Vector2i(-1, 1), Vector2i(-1, 0), Vector2i(-1, -1)]
const EXPERIENCE_SKILLS: Array[String] = [
	"attack", "defense", "harvesting", "alchemy", "magic", "potion",
	"summoning", "manufacturing", "crafting", "engineering", "tailoring",
	"ranging", "overall"]
const COUNTER_CATEGORIES: Array[String] = [
	"Kills", "Deaths", "Breakages", "Crit Fails", "Used Items", "Events",
	"Harvests", "Alchemy", "Crafting", "Manufacturing", "Potions", "Spells",
	"Summons", "Engineering", "Tailoring", "Storage", "Drops"]
const PERK_NAMES: Array[String] = [
	"Power Saving", "Self Destruct", "There is no Fork", "Excavator", "Conjurer",
	"I Glow in the Dark", "Body Piercing", "Artificer", "I Eat Dead People",
	"Fatal Man", "Monster Magnetism", "Careful Guy", "Fast Regeneration",
	"Evanescence", "Mirror Skin", "Sharp Shooter", "Power Hungry", "I can't dance",
	"No More Tears", "Ethereal Ranger", "Wilhelm Hood", "Antisocial",
	"Gelatine Bones", "Godless", "Harvester of Sorrow", "One", "Underworlder",
	"Summoner", "Skeptic", "Collateral Damage", "Dedicated Harvester", "Hellspawn",
	"Scotty Died"]

func _ready() -> void:
	var model_registry: Dictionary = _json("res://data/actors/models.json")
	models = model_registry.get("models", {})
	actor_type_models = model_registry.get("actorTypes", {})
	npc_looks = model_registry.get("npcLooks", {})
	creation_options = model_registry.get("creationOptions", [])
	animation_config = _json("res://data/animations/luminous.json")
	animation_configs["res://data/animations/luminous.json"] = animation_config
	map_registry = _json("res://data/maps/registry.json").get("maps", {})
	invasion_assistant_window = InvasionAssistantScript.new()
	add_child(invasion_assistant_window)
	invasion_assistant_window.configure_registry(map_registry)
	invasion_assistant_window.command_requested.connect(
		_on_invasion_assistant_command_requested)
	cartography = _json("res://data/maps/cartography.json")
	cartography_regions = cartography.get("regions", []) as Array
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
	minimap_frame.gui_input.connect(_on_minimap_frame_gui_input)
	map_image.gui_input.connect(_on_full_map_gui_input)
	map_image.mouse_exited.connect(_on_full_map_mouse_exited)
	clock_face.gui_input.connect(_on_clock_gui_input)
	compass_face.gui_input.connect(_on_compass_gui_input)
	continent_button.pressed.connect(_show_continent_view)
	current_map_button.pressed.connect(_show_current_map_view)
	_bind_shared_world()
	viewport_container.texture = main_viewport.get_texture()
	minimap.texture = map_viewport.get_texture()
	map_image.texture = full_map_viewport.get_texture()
	full_map.hide()
	console_panel.hide()
	settings_panel.hide()
	stats_panel.hide()
	inventory_panel.hide()
	item_lists_panel.hide()
	trade_panel.hide()
	storage_panel.hide()
	ground_bag_panel.hide()
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
	_configure_window_layers()
	_configure_cartography()
	_load_hud_settings()
	_configure_inventory_menus()
	_configure_minimap_menu()
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
	stats_tabs.tab_changed.connect(_on_stats_tab_changed)
	stats_close.pressed.connect(func() -> void: stats_panel.hide())
	counter_categories.item_selected.connect(_on_counter_category_selected)
	session_reset.pressed.connect(_reset_session_tracking)
	manufacturing_list.item_selected.connect(_on_manufacturing_selected)
	manufacturing_filter.text_changed.connect(_on_manufacturing_filter_changed)
	show_overhead_health.toggled.connect(_on_overhead_option_toggled)
	show_overhead_ether.toggled.connect(_on_overhead_option_toggled)
	show_overhead_food.toggled.connect(_on_overhead_option_toggled)
	show_overhead_action.toggled.connect(_on_overhead_option_toggled)
	%Close.pressed.connect(func() -> void: actor_hud_menu.hide())
	$GameView/ChatTabs/All.pressed.connect(_on_chat_tab_pressed.bind("all"))
	$GameView/ChatTabs/History.pressed.connect(_on_chat_tab_pressed.bind("history"))
	$GameView/ChatTabs/Options.pressed.connect(_on_options_pressed)
	%ItemMode.pressed.connect(_on_quickbar_mode_pressed.bind("items"))
	%SpellMode.pressed.connect(_on_quickbar_mode_pressed.bind("spells"))
	_build_hud_layout_menu()
	_load_hud_layout()
	_connect_hud_context_inputs(%Quickbar)
	get_viewport().size_changed.connect(_on_window_size_changed)
	call_deferred("_on_window_size_changed")
	_on_quickbar_mode_pressed("items")
	for channel_index: int in range(3):
		var channel_button: Button = get_node(
			"GameView/ChatTabs/Channel%d" % (channel_index + 1)) as Button
		channel_button.pressed.connect(_on_channel_tab_pressed.bind(channel_index))
	minimap_size.value_changed.connect(_on_minimap_size_changed)
	ui_scale_slider.value_changed.connect(_on_ui_scale_changed)
	equipment_side.add_item("Left", 0)
	equipment_side.add_item("Right", 1)
	equipment_side.select(1 if _equipment_side == "right" else 0)
	equipment_side.item_selected.connect(_on_equipment_side_selected)
	inventory_store_all.pressed.connect(_on_inventory_store_all_pressed)
	inventory_get_all.pressed.connect(_on_inventory_get_all_pressed)
	inventory_drop_all.pressed.connect(_on_inventory_drop_all_pressed)
	inventory_mix_all.pressed.connect(_on_inventory_mix_all_pressed)
	inventory_item_lists.pressed.connect(_on_inventory_item_lists_pressed)
	inventory_store_all.gui_input.connect(_on_bulk_button_gui_input.bind("store"))
	inventory_drop_all.gui_input.connect(_on_bulk_button_gui_input.bind("drop"))
	inventory_header.gui_input.connect(_on_inventory_header_gui_input)
	inventory_resize_grip.gui_input.connect(_on_inventory_resize_grip_gui_input)
	saved_item_lists.item_selected.connect(_on_saved_item_list_selected)
	item_list_save.pressed.connect(_on_item_list_save_pressed)
	item_list_delete.pressed.connect(_on_item_list_delete_pressed)
	item_list_get.pressed.connect(_on_item_list_get_pressed)
	item_lists_close.pressed.connect(func() -> void: item_lists_panel.hide())
	%SettingsClose.pressed.connect(_close_settings)
	%ConsoleClose.pressed.connect(_toggle_console)
	_session_started_msec = Time.get_ticks_msec()
	for category: String in COUNTER_CATEGORIES:
		counter_categories.add_item(category)
	counter_categories.select(0)
	_apply_equipment_side()
	_sync_saved_item_lists()
	_sync_channel_tabs()
	_sync_stats()

func _bind_shared_world() -> void:
	gameplay_world = world_root.get_world_3d()
	if gameplay_world == null:
		push_error("world_binding stage=resolve error=WorldRoot_has_no_World3D")
		return
	map_viewport.world_3d = gameplay_world
	full_map_viewport.world_3d = gameplay_world
	_sync_map_viewport_activity()
	print_debug("world_binding stage=shared world=", gameplay_world)

func _process(_delta: float) -> void:
	_update_preview_viewport()
	if game_view.visible:
		_update_map_viewports()
		_update_local_actor_follow()
		interior_cutaway.update(camera_rig.yaw_degrees)
		_update_keyboard_movement()
		_update_session_distance()
		_update_legacy_clock_and_compass()
		_update_actor_resource_overlay()
		_update_chat_fade()
		var display_second: int = floori(float(Time.get_ticks_msec()) / 1000.0)
		if display_second != cooldown_display_second:
			cooldown_display_second = display_second
			_sync_quick_slots()
			if stats_panel.visible and stats_tabs.current_tab == 3:
				_sync_session_experience()
		_sync_hud_button_states()

## Drives the two map SubViewports on demand instead of leaving them on
## UPDATE_ALWAYS. Each requests a single redraw, so a hidden map costs nothing
## and a visible one refreshes fast enough to read as live.
func _update_map_viewports() -> void:
	var now: int = Time.get_ticks_msec()
	if minimap_frame.visible and now >= _minimap_refresh_msec:
		_minimap_refresh_msec = now + MINIMAP_REFRESH_MSEC
		map_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	if full_map.visible and map_image.visible and now >= _full_map_refresh_msec:
		_full_map_refresh_msec = now + FULL_MAP_REFRESH_MSEC
		full_map_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE

## The character preview renders its own 3D scene. It only needs to run while
## the creation panel is on screen.
func _update_preview_viewport() -> void:
	var wanted: bool = creation_panel.visible
	if wanted == _preview_updates_enabled:
		return
	_preview_updates_enabled = wanted
	preview_viewport.render_target_update_mode = (SubViewport.UPDATE_ALWAYS
		if wanted else SubViewport.UPDATE_DISABLED)

func _request_map_redraw() -> void:
	_minimap_refresh_msec = 0
	_full_map_refresh_msec = 0

func _text_entry_active() -> bool:
	var focus: Control = get_viewport().gui_get_focus_owner()
	return focus is LineEdit or focus is TextEdit

func _update_keyboard_movement() -> void:
	if _text_entry_active() or dialogue_panel.visible or trade_panel.visible \
			or storage_panel.visible or ground_bag_panel.visible or full_map.visible \
			or console_panel.visible or settings_panel.visible or item_lists_panel.visible \
			or Input.is_key_pressed(KEY_ALT) or Input.is_key_pressed(KEY_CTRL):
		_stop_keyboard_movement()
		return
	var actor_value: Variant = AppState.actors.get(AppState.local_actor_id)
	var actor_node_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not actor_value is Dictionary or not actor_node_value is ReplicatedActor3D \
			or not is_instance_valid(actor_node_value as ReplicatedActor3D):
		_stop_keyboard_movement()
		return
	var dto: Dictionary = actor_value as Dictionary
	var actor_node: ReplicatedActor3D = actor_node_value as ReplicatedActor3D
	var input_axes := _movement_axes_for_actions(
		Input.is_action_pressed("move_north"),
		Input.is_action_pressed("move_south"),
		Input.is_action_pressed("move_west"),
		Input.is_action_pressed("move_east"))
	var forward_input: int = input_axes.x
	var right_input: int = input_axes.y
	if forward_input == 0 and right_input == 0:
		_stop_keyboard_movement()
		return
	var direction: Vector2i = _facing_relative_tile_direction(
		actor_node.desired_facing_yaw(), forward_input, right_input)
	if direction == Vector2i.ZERO:
		_stop_keyboard_movement()
		return
	actor_node.set_facing_override(true)
	var origin := Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
	var now: int = Time.get_ticks_msec()
	var run: bool = Input.is_key_pressed(KEY_SHIFT)
	var close_to_goal: bool = maxi(absi(_keyboard_goal_tile.x - origin.x),
		absi(_keyboard_goal_tile.y - origin.y)) <= 1
	if _keyboard_moving and direction == _keyboard_direction and run == _keyboard_running \
			and not close_to_goal and now < _keyboard_refresh_msec:
		return
	var target: Vector2i = origin + direction * KEYBOARD_LOOKAHEAD_TILES
	var error: Error = Network.move_to(target, run)
	if error == OK:
		_keyboard_moving = true
		_keyboard_running = run
		_keyboard_direction = direction
		_keyboard_goal_tile = target
		_keyboard_refresh_msec = now + KEYBOARD_REFRESH_MSEC
	else:
		push_warning("keyboard MOVE_TO failed: " + error_string(error))
		_keyboard_moving = false

func _movement_axes_for_actions(north_pressed: bool, south_pressed: bool,
		west_pressed: bool, east_pressed: bool) -> Vector2i:
	var forward_input: int = (1 if north_pressed else 0) - (1 if south_pressed else 0)
	var right_input: int = (1 if west_pressed else 0) - (1 if east_pressed else 0)
	return Vector2i(forward_input, right_input)

func _facing_relative_tile_direction(yaw: float, forward_input: int,
		right_input: int) -> Vector2i:
	var forward := Vector2i.ZERO
	var smallest_angle := INF
	for candidate: Vector2i in TILE_DIRECTIONS:
		var candidate_yaw: float = adapter.direction_to_godot(candidate)
		var difference: float = absf(wrapf(candidate_yaw - yaw, -PI, PI))
		if difference < smallest_angle:
			smallest_angle = difference
			forward = candidate
	var right := Vector2i(-forward.y, forward.x)
	var combined: Vector2i = forward * clampi(forward_input, -1, 1) \
		+ right * clampi(right_input, -1, 1)
	return Vector2i(clampi(combined.x, -1, 1), clampi(combined.y, -1, 1))

func _stop_keyboard_movement() -> void:
	if not _keyboard_moving:
		return
	var actor_value: Variant = AppState.actors.get(AppState.local_actor_id)
	if actor_value is Dictionary:
		var dto: Dictionary = actor_value as Dictionary
		var origin := Vector2i(int(dto.get("x", 0)), int(dto.get("y", 0)))
		var error: Error = Network.move_to(origin, false)
		if error != OK:
			push_warning("keyboard stop failed: " + error_string(error))
	_clear_keyboard_movement_tracking()

func _clear_keyboard_movement_tracking() -> void:
	_keyboard_moving = false
	_keyboard_running = false
	_keyboard_direction = Vector2i.ZERO
	_keyboard_goal_tile = Vector2i(-99999, -99999)
	_keyboard_refresh_msec = 0

func _release_local_facing_override() -> void:
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if actor_value is ReplicatedActor3D and is_instance_valid(actor_value as ReplicatedActor3D):
		(actor_value as ReplicatedActor3D).set_facing_override(false)

func _turn_local_actor(step: int) -> void:
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if actor_value is ReplicatedActor3D and is_instance_valid(actor_value as ReplicatedActor3D):
		(actor_value as ReplicatedActor3D).turn_by(float(step) * PI / 4.0)

func _turn_step_for_key_event(key_event: InputEventKey) -> int:
	if key_event.keycode == KEY_Q or key_event.physical_keycode == KEY_Q:
		return 1
	if key_event.keycode == KEY_E or key_event.physical_keycode == KEY_E:
		return -1
	return 0

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
	# Modified 2026-08-28 for Eloria Client: the creation bytes are equipment
	# visual ids now, so the preview resolves them exactly as the world does.
	# Building the dto by hand here would preview a different wardrobe from the
	# one the character spawns wearing.
	var dto := _presentation_dto({"actor_id": 0, "x": 0, "y": 0, "rotation": 0,
		"actor_type": actor_type, "kind": 1, "name": "Preview",
		"appearance": appearance,
		"equipment_visuals": {
			AppearanceVariants.PART_PANTS: int(appearance.get("pants", 0)),
			AppearanceVariants.PART_SHIRT: int(appearance.get("shirt", 0)),
			AppearanceVariants.PART_BOOTS: int(appearance.get("boots", 0))}})
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
			preview_distance = maxf(1.8, preview_distance - 0.3)
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
	_update_preview_lights()

## Modified 2026-08-28 for Eloria Client: the creation preview used to be lit by
## one fixed shadow-casting sun in a viewport with no environment.  Whatever the
## sun pointed away from rendered black, so the face was in shadow the moment
## the panel opened and only the side the player rotated *away* from was ever
## visible.  The rig now orbits with the camera - key over the viewer's
## shoulder, fill opposite it, rim behind the model - on top of the ambient the
## preview environment contributes, so no facing is ever unlit.
func _update_preview_lights() -> void:
	_aim_preview_light(preview_key_light, preview_yaw + 0.55,
		clampf(preview_pitch + 0.50, 0.20, 1.10))
	_aim_preview_light(preview_fill_light, preview_yaw - 1.95, 0.22)
	_aim_preview_light(preview_rim_light, preview_yaw + PI, 0.42)

func _aim_preview_light(light: DirectionalLight3D, yaw: float, pitch: float) -> void:
	# A DirectionalLight3D shines down its own -Z, so aiming it at the focus
	# from a point on the orbit is the same as choosing a light direction.
	if light == null:
		return
	var horizontal: float = cos(pitch)
	var source := Vector3(sin(yaw) * horizontal, sin(pitch), cos(yaw) * horizontal)
	light.look_at_from_position(source * 4.0 + Vector3(0.0, 1.0, 0.0),
		Vector3(0.0, 1.0, 0.0), Vector3.UP)

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
	_toggle_full_map()
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
	_show_chat_input()

func _on_invasion_assistant_command_requested(command: String) -> void:
	var error := Network.send_chat(command)
	if error != OK:
		AppState.append_local_message(
			"Invasion assistant request failed: %s" % error_string(error))

func _show_chat_input() -> void:
	chat_input.show()
	chat_input.grab_focus()
	_sync_hud_button_states(true)

func _hide_chat_input() -> void:
	chat_input.release_focus()
	chat_input.hide()

## Reacts to a map panel opening or closing. _update_map_viewports() owns the
## redraw schedule; this only ever idles a hidden viewport or asks a freshly
## shown one for its first frame. Setting UPDATE_ALWAYS here put a visible
## minimap back on full-rate world rendering for up to a whole throttle
## interval, which is exactly the cost the throttle exists to remove.
func _sync_map_viewport_activity() -> void:
	map_viewport.render_target_update_mode = (
		SubViewport.UPDATE_ONCE if minimap_frame.visible
		else SubViewport.UPDATE_DISABLED)
	full_map_viewport.render_target_update_mode = (
		SubViewport.UPDATE_ONCE if full_map.visible and map_image.visible
		else SubViewport.UPDATE_DISABLED)


func _toggle_full_map() -> void:
	if full_map.visible:
		full_map.hide()
		_sync_map_viewport_activity()
		return
	console_panel.hide()
	_close_settings()
	_show_current_map_view()
	full_map.show()
	full_map.move_to_front()
	_request_map_redraw()
	_sync_map_viewport_activity()

func _toggle_minimap() -> void:
	minimap_frame.visible = not minimap_frame.visible
	_request_map_redraw()
	_sync_map_viewport_activity()

func _toggle_console() -> void:
	if console_panel.visible:
		console_panel.hide()
		return
	full_map.hide()
	_close_settings()
	_sync_console()
	console_panel.show()
	console_panel.move_to_front()

func _on_options_pressed() -> void:
	settings_panel.visible = not settings_panel.visible
	if settings_panel.visible:
		console_panel.hide()
		settings_panel.move_to_front()
	$GameView/ChatTabs/Options.button_pressed = settings_panel.visible

func _close_settings() -> void:
	settings_panel.hide()
	$GameView/ChatTabs/Options.button_pressed = false

func _on_stats_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	stats_panel.visible = not stats_panel.visible
	if stats_panel.visible:
		inventory_panel.hide()
		manufacturing_panel.hide()
		stats_tabs.current_tab = 0
		_request_perks()
		_sync_stats()
	_sync_hud_button_states(true)

func _on_inventory_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	inventory_panel.visible = not inventory_panel.visible
	if inventory_panel.visible:
		stats_panel.hide()
		manufacturing_panel.hide()
		_sync_inventory()
	_sync_hud_button_states(true)

func _on_knowledge_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))
			or bool(AppState.ground_bag.get("open", false))):
		return
	var was_knowledge_open: bool = stats_panel.visible and stats_tabs.current_tab == 1
	stats_panel.visible = not was_knowledge_open
	if stats_panel.visible:
		stats_tabs.current_tab = 1
		inventory_panel.hide()
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
		_increment_counter("Manufacturing", 1)
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
	stats_panel.hide()

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

func _configure_inventory_menus() -> void:
	_store_options_menu = PopupMenu.new()
	_drop_options_menu = PopupMenu.new()
	for menu: PopupMenu in [_store_options_menu, _drop_options_menu]:
		for label: String in ["Protect first row", "Protect last row",
				"Protect first column", "Protect last column"]:
			menu.add_check_item(label)
		inventory_panel.add_child(menu)
	_store_options_menu.id_pressed.connect(_on_bulk_option_selected.bind("store"))
	_drop_options_menu.id_pressed.connect(_on_bulk_option_selected.bind("drop"))
	_sync_bulk_option_menus()

func _sync_bulk_option_menus() -> void:
	for menu_and_key: Array in [[_store_options_menu, "store"], [_drop_options_menu, "drop"]]:
		var menu: PopupMenu = menu_and_key[0] as PopupMenu
		var values: Array = _bulk_exclusions.get(str(menu_and_key[1]), []) as Array
		for index: int in range(4):
			menu.set_item_checked(index, index < values.size() and bool(values[index]))

func _on_bulk_button_gui_input(event: InputEvent, kind: String) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse: InputEventMouseButton = event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_RIGHT:
		return
	var menu: PopupMenu = _store_options_menu if kind == "store" else _drop_options_menu
	menu.position = Vector2i(get_viewport().get_mouse_position())
	menu.popup()
	(inventory_store_all if kind == "store" else inventory_drop_all).accept_event()

func _on_bulk_option_selected(option_id: int, kind: String) -> void:
	if option_id < 0 or option_id >= 4:
		return
	var values: Array = (_bulk_exclusions.get(kind, [false, false, false, false]) as Array).duplicate()
	values[option_id] = not bool(values[option_id])
	_bulk_exclusions[kind] = values
	_sync_bulk_option_menus()
	_save_hud_settings()

func _inventory_slot_is_protected(slot: int, kind: String) -> bool:
	var values: Array = _bulk_exclusions.get(kind, [false, false, false, false]) as Array
	return ((bool(values[0]) and slot < 6)
		or (bool(values[1]) and slot >= 30)
		or (bool(values[2]) and slot % 6 == 0)
		or (bool(values[3]) and slot % 6 == 5))

func _on_inventory_store_all_pressed() -> void:
	if not bool(AppState.storage.get("open", false)):
		inventory_description.text = "Open storage before using Sto All."
		return
	var sent := 0
	var slots: Array = AppState.inventory.keys()
	slots.sort()
	for raw_slot: Variant in slots:
		var slot: int = int(raw_slot)
		if slot < 0 or slot >= 36 or _inventory_slot_is_protected(slot, "store"):
			continue
		var item: Dictionary = AppState.inventory.get(slot, {}) as Dictionary
		if not item.is_empty() and Network.deposit_storage(slot,
				int(item.get("quantity", 0))) == OK:
			sent += 1
	if sent > 0:
		_increment_counter("Storage", sent)
	inventory_description.text = "Sto All sent %d stack%s to the server." % [
		sent, "" if sent == 1 else "s"]

func _on_inventory_get_all_pressed() -> void:
	var bag_id: int = _ground_bag_below_player()
	if bag_id < 0:
		inventory_description.text = "There is no ground bag below your character."
		return
	_ground_bag_get_all_requested_msec = Time.get_ticks_msec()
	_ground_bag_get_all_bag_id = bag_id
	if bool(AppState.ground_bag.get("open", false)) \
			and int(AppState.ground_bag.get("bag_id", -1)) == bag_id:
		_ground_bag_get_all_requested_msec = -1
		_ground_bag_get_all_bag_id = -1
		var sent: int = _request_all_ground_bag_items()
		inventory_description.text = _ground_bag_get_all_message(sent)
		return
	AppState.begin_ground_bag_inspection(bag_id)
	var error: Error = Network.inspect_bag(bag_id)
	if error != OK:
		_ground_bag_get_all_requested_msec = -1
		_ground_bag_get_all_bag_id = -1
		inventory_description.text = "Could not open the ground bag: " + error_string(error)
		push_warning("Get All INSPECT_BAG failed: " + error_string(error))
	else:
		inventory_description.text = "Opening the ground bag below you…"

func _ground_bag_below_player() -> int:
	var actor_value: Variant = AppState.actors.get(AppState.local_actor_id)
	if not actor_value is Dictionary:
		return -1
	var actor: Dictionary = actor_value as Dictionary
	var actor_x: int = int(actor.get("x", -99999))
	var actor_y: int = int(actor.get("y", -99999))
	for raw_bag_id: Variant in AppState.ground_bags:
		var bag_value: Variant = AppState.ground_bags.get(raw_bag_id)
		if bag_value is Dictionary:
			var bag: Dictionary = bag_value as Dictionary
			if int(bag.get("x", -99998)) == actor_x \
					and int(bag.get("y", -99998)) == actor_y:
				return int(raw_bag_id)
	return -1

func _ground_bag_get_all_message(sent: int) -> String:
	if sent <= 0:
		return "The ground bag is empty."
	return ("Get All requested %d ground stack%s. The server will leave anything "
		+ "that exceeds your free slots or load capacity in the open bag.") % [
		sent, "" if sent == 1 else "s"]

func _on_inventory_drop_all_pressed() -> void:
	var sent := 0
	var slots: Array = AppState.inventory.keys()
	slots.sort()
	for raw_slot: Variant in slots:
		var slot: int = int(raw_slot)
		if slot < 0 or slot >= 36 or _inventory_slot_is_protected(slot, "drop"):
			continue
		var item: Dictionary = AppState.inventory.get(slot, {}) as Dictionary
		if not item.is_empty() and Network.drop_inventory_item(slot,
				int(item.get("quantity", 0))) == OK:
			sent += 1
	if sent > 0:
		_increment_counter("Drops", sent)
	inventory_description.text = "Drop All sent %d stack%s to the server." % [
		sent, "" if sent == 1 else "s"]

func _on_inventory_mix_all_pressed() -> void:
	if selected_manufacturing_recipe < 0:
		manufacturing_panel.show()
		manufacturing_panel.move_to_front()
		manufacturing_status.text = "Select a recipe, then use Mix All."
		return
	_send_manufacturing_request(255)

func _on_inventory_item_lists_pressed() -> void:
	_sync_saved_item_lists()
	item_lists_panel.show()
	item_lists_panel.move_to_front()

func _sync_saved_item_lists() -> void:
	if saved_item_lists == null:
		return
	saved_item_lists.clear()
	var names: Array = _item_lists.keys()
	names.sort_custom(func(a: Variant, b: Variant) -> bool:
		return str(a).naturalnocasecmp_to(str(b)) < 0)
	for raw_name: Variant in names:
		var name: String = str(raw_name)
		var index: int = saved_item_lists.item_count
		saved_item_lists.add_item(name)
		saved_item_lists.set_item_metadata(index, name)

func _on_saved_item_list_selected(index: int) -> void:
	if index < 0 or index >= saved_item_lists.item_count:
		return
	var name: String = str(saved_item_lists.get_item_metadata(index))
	item_list_name.text = name
	item_list_entries.text = str(_item_lists.get(name, ""))
	item_list_status.text = "Loaded %s." % name

func _parse_item_list(text: String) -> Array[Dictionary]:
	var parsed: Array[Dictionary] = []
	for raw_line: String in text.split("\n"):
		var line: String = raw_line.strip_edges().replace(",", ":")
		if line.is_empty() or line.begins_with("#"):
			continue
		var parts: PackedStringArray = line.split(":", false, 1)
		if parts.size() != 2 or not parts[0].strip_edges().is_valid_int() \
				or not parts[1].strip_edges().is_valid_int():
			return []
		var image_id: int = int(parts[0].strip_edges())
		var quantity: int = int(parts[1].strip_edges())
		if image_id < 0 or quantity <= 0:
			return []
		parsed.append({"image_id": image_id, "quantity": quantity})
	return parsed

func _on_item_list_save_pressed() -> void:
	var name: String = item_list_name.text.strip_edges()
	var entries: Array[Dictionary] = _parse_item_list(item_list_entries.text)
	if name.is_empty() or entries.is_empty():
		item_list_status.text = "Enter a name and valid image_id:quantity lines."
		return
	_item_lists[name] = item_list_entries.text.strip_edges()
	_save_hud_settings()
	_sync_saved_item_lists()
	item_list_status.text = "Saved %s (%d item types)." % [name, entries.size()]

func _on_item_list_delete_pressed() -> void:
	var name: String = item_list_name.text.strip_edges()
	if _item_lists.erase(name):
		_save_hud_settings()
		_sync_saved_item_lists()
		item_list_name.clear()
		item_list_entries.clear()
		item_list_status.text = "Deleted %s." % name

func _on_item_list_get_pressed() -> void:
	if not bool(AppState.storage.get("open", false)):
		item_list_status.text = "Open the relevant storage category first."
		return
	var wanted: Array[Dictionary] = _parse_item_list(item_list_entries.text)
	if wanted.is_empty():
		item_list_status.text = "The list has no valid entries."
		return
	var items: Dictionary = AppState.storage.get("items", {}) as Dictionary
	var request_count := 0
	var missing: Array[String] = []
	for request: Dictionary in wanted:
		var remaining: int = int(request.get("quantity", 0))
		var positions: Array = items.keys()
		positions.sort()
		positions.reverse()
		for raw_position: Variant in positions:
			var item: Dictionary = items.get(int(raw_position), {}) as Dictionary
			if int(item.get("image_id", -1)) != int(request.get("image_id", -2)):
				continue
			var quantity: int = mini(remaining, int(item.get("quantity", 0)))
			if quantity > 0 and Network.withdraw_storage(int(raw_position), quantity) == OK:
				remaining -= quantity
				request_count += 1
			if remaining <= 0:
				break
		if remaining > 0:
			missing.append("#%d ×%d" % [int(request.get("image_id", 0)), remaining])
	if request_count > 0:
		_increment_counter("Storage", request_count)
	item_list_status.text = ("Requested %d stack%s." % [request_count,
		"" if request_count == 1 else "s"]
		+ (" Missing " + ", ".join(missing) + "." if not missing.is_empty() else ""))

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
	if error == OK:
		_increment_counter("Storage", 1)
	else:
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
	if error == OK:
		_increment_counter("Storage", 1)
	else:
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
	_request_all_ground_bag_items()

func _request_all_ground_bag_items() -> int:
	var items: Dictionary = AppState.ground_bag.get("items", {}) as Dictionary
	var positions: Array = items.keys()
	positions.sort()
	var sent := 0
	for raw_position: Variant in positions:
		var position: int = int(raw_position)
		var item_value: Variant = items.get(position)
		if item_value is Dictionary:
			var quantity: int = int((item_value as Dictionary).get("quantity", 0))
			if quantity > 0:
				var error: Error = Network.pick_up_ground_item(position, quantity)
				if error != OK:
					push_warning("PICK_UP_ITEM failed: " + error_string(error))
				else:
					sent += 1
	return sent

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
	if error == OK:
		_increment_counter("Drops", 1)
	else:
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
	if is_instance_valid(map_light_root):
		map_light_root.queue_free()
	map_light_root = null
	_actor_surface_samples.clear()
	# The parsed model and animation caches are only worth holding for the
	# session they were built in.
	GlbSceneCache.clear()
	NativeAnimationImporter.clear()
	world_loader.unload_world()
	loaded_server_map = ""
	full_map.hide()
	inventory_panel.hide()
	stats_panel.hide()
	trade_panel.hide()
	storage_panel.hide()
	ground_bag_panel.hide()
	manufacturing_panel.hide()
	item_lists_panel.hide()
	dialogue_panel.hide()
	console_panel.hide()
	_close_settings()
	minimap_frame.hide()
	chat_output.clear()
	selected_target.text = "Target: none"

func _input(event: InputEvent) -> void:
	if not game_view.visible or not event is InputEventKey:
		return
	var key_event: InputEventKey = event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return
	if key_event.ctrl_pressed and (key_event.keycode == KEY_I
			or key_event.physical_keycode == KEY_I):
		_on_inventory_button_pressed()
		get_viewport().set_input_as_handled()
	elif not _text_entry_active() and key_event.is_action_pressed("recenter_viewport"):
		_recenter_viewport_on_player()
		get_viewport().set_input_as_handled()
	elif (not _text_entry_active() and not key_event.ctrl_pressed and not key_event.alt_pressed
			and (key_event.keycode in [KEY_Q, KEY_E]
			or key_event.physical_keycode in [KEY_Q, KEY_E])):
		_turn_local_actor(_turn_step_for_key_event(key_event))
		get_viewport().set_input_as_handled()
	elif key_event.keycode == KEY_TAB or key_event.physical_keycode == KEY_TAB:
		_toggle_full_map()
		get_viewport().set_input_as_handled()
	elif (key_event.alt_pressed and (key_event.keycode == KEY_M
			or key_event.physical_keycode == KEY_M)):
		_toggle_minimap()
		get_viewport().set_input_as_handled()
	elif (key_event.keycode in [96, 126]
			or key_event.physical_keycode == 96 or key_event.unicode in [96, 126]):
		_toggle_console()
		get_viewport().set_input_as_handled()
	elif key_event.keycode == KEY_ESCAPE and console_panel.visible:
		console_panel.hide()
		get_viewport().set_input_as_handled()
	elif key_event.keycode == KEY_ESCAPE and chat_input.has_focus():
		_hide_chat_input()
		get_viewport().set_input_as_handled()

func _recenter_viewport_on_player() -> void:
	camera_rig.reset_pan()
	_update_local_actor_follow()

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
	if event.is_action_pressed("toggle_map"):
		_toggle_full_map()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("toggle_minimap"):
		_toggle_minimap()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("toggle_console"):
		_toggle_console()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("chat_focus"):
		_show_chat_input()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("cancel"):
		if chat_input.has_focus():
			_hide_chat_input()
		elif settings_panel.visible:
			_close_settings()
		elif console_panel.visible:
			console_panel.hide()
		elif dialogue_panel.visible:
			AppState.close_dialogue()
		elif bool(AppState.trade.get("open", false)):
			_on_trade_cancel_pressed()
		elif bool(AppState.storage.get("open", false)):
			AppState.close_storage()
		elif bool(AppState.ground_bag.get("open", false)):
			_close_ground_bag()
		elif item_lists_panel.visible:
			item_lists_panel.hide()
		elif manufacturing_panel.visible:
			manufacturing_panel.hide()
		elif inventory_panel.visible:
			inventory_panel.hide()
		elif stats_panel.visible:
			stats_panel.hide()
		elif full_map.visible:
			full_map.hide()
		else:
			actor_hud_menu.hide()
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
			or manufacturing_panel.visible):
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
	$GameView/ChatTabs/Options.button_pressed = false
	for channel_index: int in range(3):
		var channel_button: Button = get_node(
			"GameView/ChatTabs/Channel%d" % (channel_index + 1)) as Button
		channel_button.button_pressed = tab == "channel:%d" % channel_index
	_sync_chat()
	_reveal_chat_messages()

func _on_channel_tab_pressed(channel_index: int) -> void:
	if channel_index < 0 or channel_index >= AppState.active_channels.size():
		return
	if int(AppState.active_channels[channel_index]) <= 0:
		return
	var error: Error = Network.set_active_channel(channel_index)
	if error != OK:
		push_warning("SET_ACTIVE_CHANNEL failed: " + error_string(error))
	AppState.active_channel_index = channel_index
	_on_chat_tab_pressed("channel:%d" % channel_index)

func _sync_channel_tabs() -> void:
	for channel_index: int in range(3):
		var button: Button = get_node(
			"GameView/ChatTabs/Channel%d" % (channel_index + 1)) as Button
		var channel_number: int = (int(AppState.active_channels[channel_index])
			if channel_index < AppState.active_channels.size() else 0)
		button.visible = channel_number > 0
		button.text = str(channel_number) if channel_number > 0 else str(channel_index + 1)
		button.tooltip_text = ("Active channel #%d" % channel_number
			if channel_number > 0 else "Unused channel slot")
		button.button_pressed = _chat_tab == "channel:%d" % channel_index

func _reveal_chat_messages() -> void:
	_last_chat_activity_msec = Time.get_ticks_msec()
	chat_panel.modulate.a = 1.0
	chat_panel.show()

func _update_chat_fade() -> void:
	if console_panel.visible or not chat_panel.visible:
		return
	var age_msec: int = Time.get_ticks_msec() - _last_chat_activity_msec
	if age_msec <= CHAT_FADE_DELAY_MSEC:
		chat_panel.modulate.a = 1.0
		return
	var fade_progress: float = clampf(float(age_msec - CHAT_FADE_DELAY_MSEC)
		/ float(CHAT_FADE_DURATION_MSEC), 0.0, 1.0)
	chat_panel.modulate.a = 1.0 - fade_progress
	if fade_progress >= 1.0:
		chat_panel.hide()

func _on_minimap_gui_input(event: InputEvent) -> void:
	_handle_map_gui_input(event, minimap, map_viewport, map_camera, "minimap")

func _on_full_map_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion:
		var mouse_motion: InputEventMouseMotion = event as InputEventMouseMotion
		var viewport_position_value: Variant = _texture_to_viewport_position(
			mouse_motion.position, map_image, full_map_viewport.size)
		if not viewport_position_value is Vector2:
			map_coordinates.text = "Coordinates: outside map image"
			return
		var viewport_position: Vector2 = viewport_position_value as Vector2
		var target_value: Variant = _map_target_tile(full_map_camera, viewport_position)
		if target_value is Vector2i:
			var tile: Vector2i = target_value as Vector2i
			map_coordinates.text = "Coordinates: %d, %d" % [tile.x, tile.y]
		else:
			map_coordinates.text = "Coordinates: outside walkable map"
		return
	_handle_map_gui_input(event, map_image, full_map_viewport, full_map_camera, "full_map")

func _on_full_map_mouse_exited() -> void:
	if map_image.visible:
		map_coordinates.text = "Coordinates: —"

func _on_compass_gui_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse_button: InputEventMouseButton = event as InputEventMouseButton
	if not mouse_button.pressed or mouse_button.button_index != MOUSE_BUTTON_LEFT:
		return
	if mouse_button.ctrl_pressed:
		var tile_value: Variant = _local_actor_server_tile()
		if not tile_value is Vector2i:
			AppState.append_local_message("Your position is not available yet.")
			compass_face.accept_event()
			return
		var tile: Vector2i = tile_value as Vector2i
		var location: String = "%s (%d, %d)" % [
			_current_map_display_name, tile.x, tile.y]
		if AppState.active_channel_number() <= 0:
			AppState.append_local_message(
				"Join or select a numeric channel before sharing your position.")
		else:
			var share_error: Error = Network.send_chat("@My Position: " + location)
			if share_error != OK:
				AppState.append_local_message(
					"Could not share your position: " + error_string(share_error))
	else:
		var locate_error: Error = Network.locate_me()
		if locate_error != OK:
			AppState.append_local_message(
				"Could not request your location: " + error_string(locate_error))
	compass_face.accept_event()

func _on_clock_gui_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse_button: InputEventMouseButton = event as InputEventMouseButton
	if not mouse_button.pressed or mouse_button.button_index != MOUSE_BUTTON_LEFT:
		return
	var date_error: Error = Network.request_server_date()
	var time_error: Error = Network.request_server_time()
	if date_error != OK or time_error != OK:
		AppState.append_local_message("Server date/time request failed: %s" %
			error_string(date_error if date_error != OK else time_error))
	clock_face.accept_event()

func _local_actor_server_tile() -> Variant:
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if not actor_value is Node3D or not is_instance_valid(actor_value as Node3D):
		return null
	return adapter.godot_to_server((actor_value as Node3D).global_position)

func _handle_map_gui_input(event: InputEvent, map_control: TextureRect,
		map_render_viewport: SubViewport, camera: Camera3D, source: String) -> void:
	if (not game_view.visible or dialogue_panel.visible or trade_panel.visible
			or storage_panel.visible or ground_bag_panel.visible
			or manufacturing_panel.visible):
		return
	if not event is InputEventMouseButton:
		return
	var mouse_button: InputEventMouseButton = event as InputEventMouseButton
	if not mouse_button.pressed or mouse_button.button_index != MOUSE_BUTTON_LEFT:
		return
	var viewport_position_value: Variant = _texture_to_viewport_position(
		mouse_button.position, map_control, map_render_viewport.size)
	if not viewport_position_value is Vector2:
		map_control.accept_event()
		return
	var viewport_position: Vector2 = viewport_position_value as Vector2
	var target_value: Variant = _map_target_tile(camera, viewport_position)
	print_debug("map_input source=", source, " local_click=", mouse_button.position,
		" viewport=", viewport_position, " server_tile=", target_value,
		" command=", "RUN_TO" if mouse_button.shift_pressed else "MOVE_TO")
	if target_value is Vector2i:
		_clear_keyboard_movement_tracking()
		_release_local_facing_override()
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

static func _texture_to_viewport_position(local_position: Vector2,
		texture_rect: TextureRect, target_size: Vector2i) -> Variant:
	var control_size: Vector2 = texture_rect.size
	var target: Vector2 = Vector2(target_size)
	if control_size.x <= 0.0 or control_size.y <= 0.0 or target.x <= 0.0 or target.y <= 0.0:
		return null
	if texture_rect.stretch_mode == TextureRect.STRETCH_KEEP_ASPECT_CENTERED:
		var scale: float = minf(control_size.x / target.x, control_size.y / target.y)
		var displayed_size: Vector2 = target * scale
		var displayed_origin: Vector2 = (control_size - displayed_size) * 0.5
		if not Rect2(displayed_origin, displayed_size).has_point(local_position):
			return null
		return (local_position - displayed_origin) * target / displayed_size
	return _control_to_viewport_position(local_position, control_size, target_size)

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
		_clear_keyboard_movement_tracking()
		_release_local_facing_override()
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
			# A busy map emits this once per actor packet. Rebuilding the whole
			# actor presentation for each of them repeated the same work many
			# times inside a single frame; coalescing collapses a burst into one
			# pass without delaying anything past the frame it arrived in.
			_queue_world_sync()
		&"chat":
			_capture_perks_from_chat()
			_sync_chat()
			_sync_console()
			_reveal_chat_messages()
		&"channels":
			_sync_channel_tabs()
		&"invasion_assistant":
			var kind := str(AppState.invasion_assistant.get("last_kind", ""))
			var update: Dictionary = AppState.invasion_assistant.get(kind, {}) as Dictionary
			if not update.is_empty():
				invasion_assistant_window.apply_update(update)
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

func _queue_world_sync() -> void:
	if _world_sync_queued:
		return
	_world_sync_queued = true
	_flush_world_sync.call_deferred()

func _flush_world_sync() -> void:
	if not _world_sync_queued:
		return
	_world_sync_queued = false
	_sync_world()
	_sync_selection()

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
	_actor_surface_samples.clear()
	_local_placement_logged = false
	_current_map_display_name = _friendly_map_name(AppState.current_map)
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
	# Regions and interiors may declare their own sky, sun, fog, tonemap, point
	# lights and camera framing. Maps that do not keep the client's previous
	# placeholder environment unchanged.
	WorldEnvironmentBinder.apply(manifest, world_environment, world_sun, world_root)
	WorldEnvironmentBinder.apply_camera(manifest, camera_rig)
	_bind_light_markers(manifest)
	_populate_ambient_life(manifest)
	_current_map_display_name = str(
		manifest.data.get("asset", {}).get("name", manifest.asset_id()))
	map_label.text = "Map: " + _current_map_display_name
	map_title.text = _current_map_display_name.to_upper()
	current_map_button.text = "Current: " + _current_map_display_name
	_configure_interior_cutaway(manifest)
	_configure_full_map(manifest)
	_request_map_redraw()
	_sync_world()
	_sync_ground_bags()
	_snap_all_actors_to_surface.call_deferred()
	_snap_all_ground_bags_to_surface.call_deferred()

func _bind_light_markers(manifest: WorldManifest) -> void:
	# Braziers, hearths and shrine lamps the map declares as markers. Interiors
	# rely on them for their whole lighting; outdoor maps use them as warm fill
	# after sundown. Maps that declare none are left alone.
	if is_instance_valid(map_light_root):
		map_light_root.queue_free()
	map_light_root = null
	var root_node := Node3D.new()
	root_node.name = "MapLights"
	world_root.add_child(root_node)
	var bound: int = LightMarkerBinder.apply(manifest, root_node)
	if bound == 0:
		root_node.queue_free()
		return
	map_light_root = root_node
	print_debug("light_markers map=", AppState.current_map, " bound=", bound)

func _populate_ambient_life(manifest: WorldManifest) -> void:
	# Scenery livestock declared by the map. Networked actors are untouched.
	if ambient_population == null:
		ambient_population = AmbientPopulation.new()
		ambient_population.name = "AmbientPopulation"
		world_root.add_child(ambient_population)
	await get_tree().physics_frame
	if gameplay_world == null:
		return
	var spawned: int = ambient_population.populate(manifest,
		gameplay_world.direct_space_state)
	if spawned > 0:
		print_debug("ambient_population map=", AppState.current_map, " spawned=", spawned)

func _snap_all_actors_to_surface() -> void:
	await get_tree().physics_frame
	for actor_value: Variant in actor_nodes.values():
		var actor: ReplicatedActor3D = actor_value as ReplicatedActor3D
		if is_instance_valid(actor):
			_place_actor_on_surface(actor, true)

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
			_actor_surface_samples.erase(id)
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
		_place_actor_on_surface(node, true)
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
	var minimap_heading := 0.0
	if _minimap_orientation == "player_up":
		minimap_heading = target.rotation.y
	elif _minimap_orientation == "viewport_up":
		minimap_heading = deg_to_rad(camera_rig.yaw_degrees)
	map_camera.rotation = Vector3(-PI * 0.5, minimap_heading, 0.0)
	# Repositioning the four compass letters is only observable while the
	# minimap is on screen.
	if minimap_frame.visible:
		_layout_minimap_cardinals()
	# Render above the actor and ignore depth so roofs/bridges cannot hide the
	# local-position dot in either top-down map camera.
	player_map_marker.global_position = focus_position + Vector3(0, 5.0, 0)
	player_map_marker.visible = true

## The ray sample only changes when the actor stands somewhere else, but this
## used to fire for every actor on every actor packet - hundreds of physics
## queries a second on a populated map. The sample is now cached per actor and
## repeated only when its tile moves, or when the caller forces it after a map
## load.
func _place_actor_on_surface(actor: ReplicatedActor3D, force := false) -> void:
	if not is_instance_valid(actor) or gameplay_world == null:
		return
	var actor_position: Vector3 = actor.server_target
	var sample := Vector2(actor_position.x, actor_position.z)
	if not force and _actor_surface_samples.get(actor.actor_id) == sample:
		return
	_actor_surface_samples[actor.actor_id] = sample
	var ray_start: Vector3 = Vector3(actor_position.x, 400.0, actor_position.z)
	var ray_end: Vector3 = Vector3(actor_position.x, -100.0, actor_position.z)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		ray_start, ray_end, WorldLoader.NAVIGATION_SURFACE_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var hit_position_value: Variant = hit.get("position")
	if hit_position_value is Vector3:
		var hit_position: Vector3 = hit_position_value as Vector3
		actor.set_surface_height(hit_position.y + 0.02)
		# render_diagnostics() walks the actor's whole subtree and builds a
		# dictionary per mesh. Its arguments were evaluated on every placement
		# even in release builds, so it is now a one-shot per map load.
		if actor.actor_id == AppState.local_actor_id and not _local_placement_logged:
			_local_placement_logged = true
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
	if _ground_bag_get_all_requested_msec >= 0:
		var requested_age: int = (Time.get_ticks_msec()
			- _ground_bag_get_all_requested_msec)
		var requested_bag_id: int = _ground_bag_get_all_bag_id
		_ground_bag_get_all_requested_msec = -1
		_ground_bag_get_all_bag_id = -1
		if requested_age <= GROUND_BAG_GET_ALL_TIMEOUT_MSEC \
				and int(AppState.ground_bag.get("bag_id", -1)) == requested_bag_id:
			var sent: int = _request_all_ground_bag_items()
			inventory_description.text = _ground_bag_get_all_message(sent)

func _sync_ground_bag_actions() -> void:
	ground_bag_pick_button.disabled = ground_bag_items.get_selected_items().is_empty()
	ground_bag_drop_button.disabled = ground_bag_inventory.get_selected_items().is_empty()

func _sync_knowledge() -> void:
	if not stats_panel.visible or stats_tabs.current_tab != 1:
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

## Interiors are closed boxes, so the isometric rig would render their ceiling
## and near wall. The manifest names the nodes to cut away; maps without a
## `cutaway` block (the city) are left exactly as loaded.
func _configure_interior_cutaway(manifest: WorldManifest) -> void:
	var count: int = interior_cutaway.configure(manifest, world_root)
	if count > 0:
		interior_cutaway.update(camera_rig.yaw_degrees, true)
		print_debug("interior_cutaway stage=applied map=", AppState.current_map,
			" nodes=", count)


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

func _configure_cartography() -> void:
	var continent_value: Variant = cartography.get("continent", {})
	if continent_value is Dictionary:
		var continent: Dictionary = continent_value as Dictionary
		var continent_texture: Texture2D = _external_texture(
			str(continent.get("texture", "")))
		continent_button.texture_normal = continent_texture
		continent_image.texture = continent_texture
	for child: Node in region_buttons.get_children():
		child.queue_free()
	for region_index: int in range(cartography_regions.size()):
		var region_value: Variant = cartography_regions[region_index]
		if not region_value is Dictionary:
			continue
		var region: Dictionary = region_value as Dictionary
		var button: Button = Button.new()
		button.text = str(region.get("name", "Unknown region"))
		button.tooltip_text = "Preview " + button.text
		button.focus_mode = Control.FOCUS_NONE
		button.pressed.connect(_preview_region.bind(region_index))
		region_buttons.add_child(button)

func _show_current_map_view() -> void:
	continent_view.hide()
	region_preview.hide()
	map_image.show()
	_sync_map_viewport_activity()
	map_title.text = _current_map_display_name.to_upper()
	map_coordinates.text = "Coordinates: —"

func _show_continent_view() -> void:
	map_image.hide()
	_sync_map_viewport_activity()
	region_preview.hide()
	continent_view.show()
	var continent: Dictionary = cartography.get("continent", {}) as Dictionary
	map_title.text = str(continent.get("name", "Nymara")).to_upper() + " CONTINENT"
	map_coordinates.text = "Select a region to preview. Your server map will not change."

func _preview_region(region_index: int) -> void:
	if region_index < 0 or region_index >= cartography_regions.size():
		return
	var region_value: Variant = cartography_regions[region_index]
	if not region_value is Dictionary:
		return
	var region: Dictionary = region_value as Dictionary
	var preview_texture: Texture2D = _external_texture(str(region.get("preview", "")))
	if preview_texture == null:
		map_coordinates.text = "Preview unavailable for " + str(region.get("name", "region"))
		return
	continent_view.hide()
	map_image.hide()
	region_preview.texture = preview_texture
	region_preview.show()
	map_title.text = str(region.get("name", "REGION")).to_upper() + " PREVIEW"
	map_coordinates.text = "Preview only — click Current map to return."

func _friendly_map_name(server_map: String) -> String:
	var normalized: String = MapRegistry.normalize_server_map_id(server_map)
	if normalized in ["maps/startmap.elm", "startmap.elm", "four_gates", "four-gates"]:
		return "Four Gates City"
	var file_name: String = normalized.get_file().get_basename()
	return file_name.replace("_", " ").replace("-", " ").capitalize()

func _load_hud_settings() -> void:
	var config: ConfigFile = ConfigFile.new()
	if config.load(SETTINGS_PATH) == OK:
		_minimap_scale = clampf(float(config.get_value(
			"hud", "minimap_scale", 1.0)), 0.75, 1.75)
		_ui_scale = clampf(float(config.get_value(
			"hud", "ui_scale", 1.0)), UI_SCALE_MIN, UI_SCALE_MAX)
		_minimap_orientation = str(config.get_value(
			"hud", "minimap_orientation", "north_up"))
		if _minimap_orientation not in ["north_up", "player_up", "viewport_up"]:
			_minimap_orientation = "north_up"
		var position_value: Variant = config.get_value(
			"hud", "minimap_position", Vector2(16.0, 42.0))
		if position_value is Vector2:
			minimap_frame.position = position_value as Vector2
		_inventory_scale = clampf(float(config.get_value(
			"inventory", "window_scale", 1.0)),
			INVENTORY_MIN_SCALE, INVENTORY_MAX_SCALE)
		var inventory_position_value: Variant = config.get_value(
			"inventory", "window_position", inventory_panel.position)
		if inventory_position_value is Vector2:
			inventory_panel.position = inventory_position_value as Vector2
		_equipment_side = str(config.get_value("inventory", "equipment_side", "left"))
		var bulk_value: Variant = config.get_value("inventory", "bulk_exclusions", {})
		if bulk_value is Dictionary:
			for kind: String in ["store", "drop"]:
				var options_value: Variant = (bulk_value as Dictionary).get(kind)
				if options_value is Array and (options_value as Array).size() == 4:
					_bulk_exclusions[kind] = (options_value as Array).duplicate()
		var lists_value: Variant = config.get_value("inventory", "item_lists", {})
		if lists_value is Dictionary:
			_item_lists = (lists_value as Dictionary).duplicate(true)
		var counters_value: Variant = config.get_value("statistics", "counters", {})
		if counters_value is Dictionary:
			_total_counters = (counters_value as Dictionary).duplicate(true)
	minimap_size.set_value_no_signal(_minimap_scale)
	ui_scale_slider.set_value_no_signal(_ui_scale)
	_apply_ui_scale()
	_apply_minimap_scale()
	_apply_inventory_scale(_inventory_scale)

func _on_ui_scale_changed(value: float) -> void:
	_ui_scale = clampf(value, UI_SCALE_MIN, UI_SCALE_MAX)
	_apply_ui_scale()
	_save_hud_settings()

## The window already scales the HUD with its size; this factor rides on top of
## that so players can trade HUD size for screen space. It only moves the canvas
## the HUD is laid out in - the world render target is resized to match in
## _on_window_size_changed(), so the world always renders at window resolution.
func _apply_ui_scale() -> void:
	var window: Window = get_window()
	if window != null:
		window.content_scale_factor = _ui_scale
	ui_scale_value.text = "%d%%" % roundi(_ui_scale * 100.0)
	_on_window_size_changed()

func _on_minimap_size_changed(value: float) -> void:
	_minimap_scale = clampf(value, 0.75, 1.75)
	_apply_minimap_scale()
	_save_hud_settings()

func _save_hud_settings() -> void:
	var config: ConfigFile = ConfigFile.new()
	config.load(SETTINGS_PATH)
	config.set_value("hud", "minimap_scale", _minimap_scale)
	config.set_value("hud", "ui_scale", _ui_scale)
	config.set_value("hud", "minimap_orientation", _minimap_orientation)
	config.set_value("hud", "minimap_position", minimap_frame.position)
	config.set_value("inventory", "window_scale", _inventory_scale)
	config.set_value("inventory", "window_position", inventory_panel.position)
	config.set_value("inventory", "equipment_side", _equipment_side)
	config.set_value("inventory", "bulk_exclusions", _bulk_exclusions)
	config.set_value("inventory", "item_lists", _item_lists)
	config.set_value("statistics", "counters", _total_counters)
	var error: Error = config.save(SETTINGS_PATH)
	if error != OK:
		push_warning("HUD settings save failed: " + error_string(error))

func _apply_minimap_scale() -> void:
	var frame_size: float = roundf(264.0 * _minimap_scale)
	var border_size: float = roundf(MINIMAP_DRAG_BORDER * _minimap_scale)
	minimap_frame.offset_right = minimap_frame.offset_left + frame_size
	minimap_frame.offset_bottom = minimap_frame.offset_top + frame_size
	minimap.offset_left = border_size
	minimap.offset_top = border_size
	minimap.offset_right = -border_size
	minimap.offset_bottom = -border_size
	minimap.custom_minimum_size = Vector2.ZERO
	var maximum: Vector2 = (game_view.size - Vector2.ONE * frame_size).max(Vector2.ZERO)
	minimap_frame.position = Vector2(
		clampf(minimap_frame.position.x, 0.0, maximum.x),
		clampf(minimap_frame.position.y, 30.0, maxf(30.0, maximum.y)))
	minimap_size_value.text = "%d%%" % roundi(_minimap_scale * 100.0)
	_layout_minimap_cardinals()

func _on_inventory_header_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index != MOUSE_BUTTON_LEFT:
			return
		_inventory_dragging = mouse.pressed
		if mouse.pressed:
			inventory_panel.move_to_front()
			_inventory_drag_offset = (get_viewport().get_mouse_position()
				- inventory_panel.global_position)
		else:
			_save_hud_settings()
		inventory_header.accept_event()
	elif event is InputEventMouseMotion and _inventory_dragging:
		inventory_panel.global_position = (get_viewport().get_mouse_position()
			- _inventory_drag_offset)
		_clamp_inventory_window_to_viewport()
		inventory_header.accept_event()

func _on_inventory_resize_grip_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index != MOUSE_BUTTON_LEFT:
			return
		_inventory_resizing = mouse.pressed
		if mouse.pressed:
			inventory_panel.move_to_front()
			_inventory_resize_start_mouse = get_viewport().get_mouse_position()
			_inventory_resize_start_scale = _inventory_scale
		else:
			_save_hud_settings()
		inventory_resize_grip.accept_event()
	elif event is InputEventMouseMotion and _inventory_resizing:
		var delta: Vector2 = (get_viewport().get_mouse_position()
			- _inventory_resize_start_mouse)
		var base_size: Vector2 = inventory_panel.size
		if base_size.x <= 0.0 or base_size.y <= 0.0:
			return
		var normalized := Vector2(delta.x / base_size.x, delta.y / base_size.y)
		var scale_delta: float = (normalized.x if absf(normalized.x) >= absf(normalized.y)
			else normalized.y)
		_apply_inventory_scale(_inventory_resize_start_scale + scale_delta)
		inventory_resize_grip.accept_event()

func _apply_inventory_scale(requested_scale: float) -> void:
	var maximum_scale: float = INVENTORY_MAX_SCALE
	if game_view.size.x > 0.0 and game_view.size.y > 0.0 \
			and inventory_panel.size.x > 0.0 and inventory_panel.size.y > 0.0:
		maximum_scale = minf(maximum_scale, minf(
			(game_view.size.x - 16.0) / inventory_panel.size.x,
			(game_view.size.y - 16.0) / inventory_panel.size.y))
	maximum_scale = maxf(INVENTORY_MIN_SCALE, maximum_scale)
	_inventory_scale = clampf(requested_scale, INVENTORY_MIN_SCALE, maximum_scale)
	inventory_panel.scale = Vector2.ONE * _inventory_scale
	_clamp_inventory_window_to_viewport()

func _clamp_inventory_window_to_viewport() -> void:
	if game_view.size.x <= 0.0 or game_view.size.y <= 0.0:
		return
	var visible_size: Vector2 = inventory_panel.size * _inventory_scale
	var game_origin: Vector2 = game_view.global_position
	var local_position: Vector2 = inventory_panel.global_position - game_origin
	var maximum: Vector2 = (game_view.size - visible_size - Vector2(8.0, 8.0)).max(
		Vector2(8.0, 8.0))
	local_position = Vector2(
		clampf(local_position.x, 8.0, maximum.x),
		clampf(local_position.y, 8.0, maximum.y))
	inventory_panel.global_position = game_origin + local_position

func _on_equipment_side_selected(index: int) -> void:
	_equipment_side = "right" if index == 1 else "left"
	_apply_equipment_side()
	_save_hud_settings()

func _apply_equipment_side() -> void:
	if equipment_column == null or inventory_body == null:
		return
	inventory_body.move_child(equipment_column,
		inventory_body.get_child_count() - 1 if _equipment_side == "right" else 0)

func _configure_minimap_menu() -> void:
	_minimap_menu = PopupMenu.new()
	_minimap_menu.add_radio_check_item("North always up", 0)
	_minimap_menu.add_radio_check_item("Rotate with player", 1)
	_minimap_menu.add_radio_check_item("Rotate with viewport", 2)
	_minimap_menu.id_pressed.connect(_on_minimap_orientation_selected)
	minimap_frame.add_child(_minimap_menu)
	_sync_minimap_menu()

func _sync_minimap_menu() -> void:
	if _minimap_menu == null:
		return
	_minimap_menu.set_item_checked(0, _minimap_orientation == "north_up")
	_minimap_menu.set_item_checked(1, _minimap_orientation == "player_up")
	_minimap_menu.set_item_checked(2, _minimap_orientation == "viewport_up")

func _on_minimap_orientation_selected(id: int) -> void:
	match id:
		1: _minimap_orientation = "player_up"
		2: _minimap_orientation = "viewport_up"
		_: _minimap_orientation = "north_up"
	_sync_minimap_menu()
	_save_hud_settings()

func _on_minimap_frame_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index == MOUSE_BUTTON_RIGHT and mouse.pressed:
			_minimap_menu.position = Vector2i(get_viewport().get_mouse_position())
			_minimap_menu.popup()
			minimap_frame.accept_event()
			return
		if mouse.button_index == MOUSE_BUTTON_LEFT:
			if mouse.pressed:
				var drag_border: float = MINIMAP_DRAG_BORDER * _minimap_scale
				var inner := Rect2(Vector2.ONE * drag_border,
					minimap_frame.size - Vector2.ONE * drag_border * 2.0)
				if not inner.has_point(mouse.position):
					_minimap_dragging = true
					_minimap_drag_offset = get_viewport().get_mouse_position() - minimap_frame.position
					minimap_frame.accept_event()
			else:
				if _minimap_dragging:
					_minimap_dragging = false
					_save_hud_settings()
					minimap_frame.accept_event()
	elif event is InputEventMouseMotion and _minimap_dragging:
		var target_position: Vector2 = (get_viewport().get_mouse_position()
			- _minimap_drag_offset)
		var maximum: Vector2 = (game_view.size - minimap_frame.size).max(Vector2.ZERO)
		minimap_frame.position = Vector2(
			clampf(target_position.x, 0.0, maximum.x),
			clampf(target_position.y, 30.0, maximum.y))
		minimap_frame.accept_event()

func _layout_minimap_cardinals() -> void:
	if minimap_north == null:
		return
	var center: Vector2 = minimap_frame.size * 0.5
	var radius: float = maxf(12.0, minf(minimap_frame.size.x,
		minimap_frame.size.y) * 0.5 - 9.0)
	var heading: float = map_camera.rotation.y
	var labels: Array[Label] = [minimap_north, minimap_east, minimap_south, minimap_west]
	for index: int in range(labels.size()):
		var angle: float = -PI * 0.5 + float(index) * PI * 0.5 - heading
		labels[index].position = center + Vector2(cos(angle), sin(angle)) * radius \
			- labels[index].size * 0.5

func _configure_window_layers() -> void:
	actor_resource_overlay.z_index = 1
	for panel: Control in [full_map, stats_panel, inventory_panel, dialogue_panel,
		trade_panel, storage_panel, ground_bag_panel, manufacturing_panel]:
		panel.z_index = 20
	item_lists_panel.z_index = 25
	console_panel.z_index = 25
	settings_panel.z_index = 30
	actor_hud_menu.z_index = 30

func _sync_chat() -> void:
	chat_output.clear()
	var first_line: int = (0 if _chat_tab == "history"
		else maxi(0, AppState.chat_lines.size() - 100))
	for line_value: Variant in AppState.chat_lines.slice(first_line):
		var line: Dictionary = line_value as Dictionary
		var channel: int = int(line.get("channel", 0))
		if not _chat_line_visible(channel):
			continue
		chat_output.append_text(_formatted_chat_line(line) + "\n")
	chat_output.scroll_to_line(maxi(0, chat_output.get_line_count() - 1))

func _sync_console() -> void:
	console_output.clear()
	for line_value: Variant in AppState.chat_lines:
		console_output.append_text(_formatted_chat_line(line_value as Dictionary) + "\n")

func _chat_line_visible(channel: int) -> bool:
	if not _chat_tab.begins_with("channel:"):
		return true
	var slot: int = int(_chat_tab.trim_prefix("channel:"))
	return channel == 5 + slot

func _formatted_chat_line(line: Dictionary) -> String:
	var channel: int = int(line.get("channel", 0))
	var prefix: String = ""
	match channel:
		1: prefix = "[PM] "
		3, 255: prefix = "[System] "
		5, 6, 7:
			var slot: int = channel - 5
			var channel_number: int = (int(AppState.active_channels[slot])
				if slot >= 0 and slot < AppState.active_channels.size() else 0)
			prefix = ("[#%d] " % channel_number
				if channel_number > 0 else "[Channel] ")
	return prefix + str(line.get("text", ""))

func _sync_stats() -> void:
	var stats: Dictionary = AppState.stats
	_track_experience()
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
	if inventory_load != null:
		inventory_load.text = "Load: %d / %d" % [int(stats.get("carried", 0)),
			int(stats.get("capacity", 0))]
	var abbreviated: Array[Array] = [
		["att", "attack"], ["def", "defense"], ["har", "harvesting"],
		["alc", "alchemy"], ["mag", "magic"], ["pot", "potion"],
		["sum", "summoning"], ["man", "manufacturing"], ["cra", "crafting"],
		["eng", "engineering"], ["tai", "tailoring"], ["ran", "ranging"],
		["oa", "overall"]]
	var indicator_cells: Array[String] = []
	for label_and_key: Array in abbreviated:
		var stat_value: int = int(stats.get("overall_level", 0)) \
			if label_and_key[1] == "overall" else int(stats.get(label_and_key[1], 0))
		indicator_cells.append("[cell]%s[/cell][cell]%d[/cell]" % [
			label_and_key[0], stat_value])
	skill_indicators.text = "[table=2]%s[/table]" % "".join(indicator_cells)
	if stats.is_empty():
		stats_text.text = "[center]Waiting for server statistics…[/center]"
		_sync_session_experience()
		_sync_counters()
		return
	var basic_lines: Array[String] = ["[b]Basic Attributes[/b]"]
	for label_and_key: Array in [["Physique", "physique"],
			["Coordination", "coordination"], ["Reasoning", "reasoning"],
			["Will", "will"], ["Instinct", "instinct"], ["Vitality", "vitality"]]:
		basic_lines.append("%-14s %s" % [label_and_key[0],
			_stat_pair(stats, str(label_and_key[1]))])
	basic_lines.append("\n[color=yellow][b]Cross Attributes[/b][/color]")
	for cross: Array in [["Might", "physique", "coordination"],
			["Matter", "physique", "will"], ["Toughness", "physique", "vitality"],
			["Charm", "instinct", "vitality"], ["Reaction", "instinct", "coordination"],
			["Perception", "instinct", "reasoning"], ["Rationality", "will", "reasoning"],
			["Dexterity", "coordination", "reasoning"], ["Ethereality", "will", "vitality"]]:
		basic_lines.append("%-14s %s" % [cross[0],
			_cross_pair(stats, str(cross[1]), str(cross[2]))])
	var nexus_lines: Array[String] = ["[b]Nexus[/b]"]
	for label_and_key: Array in [["Human", "human_nexus"], ["Animal", "animal_nexus"],
			["Vegetal", "vegetal_nexus"], ["Inorganic", "inorganic_nexus"],
			["Artificial", "artificial_nexus"], ["Magic", "magic_nexus"]]:
		nexus_lines.append("%-12s %s" % [label_and_key[0],
			_stat_pair(stats, str(label_and_key[1]))])
	var pickpoints: int = int(stats.get("pickpoints_earned", stats.get("overall", 0))) \
		- int(stats.get("pickpoints_spent", 0))
	nexus_lines.append("\nPickpoints       %d" % pickpoints)
	nexus_lines.append("\n[color=#d7a85b][b]Perks[/b][/color]")
	if _known_perks.is_empty():
		nexus_lines.append("None reported")
	else:
		for perk: String in _known_perks:
			nexus_lines.append("• " + perk)
	nexus_lines.append("\n[color=#9999ff]Material Points  %d/%d[/color]" % [health, max_health])
	nexus_lines.append("[color=#9999ff]Ethereal Points  %d/%d[/color]" % [ether, max_ether])
	nexus_lines.append("[color=#9999ff]Action Points    %d/%d[/color]" % [action, max_action])
	nexus_lines.append("Food Level       %d" % int(stats.get("food", 0)))
	var skill_lines: Array[String] = ["[color=#ff8a28][b]Levels and Experience[/b][/color]"]
	for skill: String in EXPERIENCE_SKILLS:
		var current_level: int = int(stats.get("overall_level", 0)) \
			if skill == "overall" else int(stats.get(skill, 0))
		var base_level: int = current_level if skill == "overall" else int(
			stats.get(skill + "_base", current_level))
		skill_lines.append("%-15s %3d/%-3d  %d / %d" % [skill.capitalize(),
			current_level, base_level,
			int(stats.get(skill + "_exp", 0)), int(stats.get(skill + "_exp_next", 0))])
	stats_text.text = "[table=3][cell]%s[/cell][cell]%s[/cell][cell]%s[/cell][/table]" % [
		"\n".join(basic_lines), "\n".join(nexus_lines), "\n".join(skill_lines)]
	_sync_session_experience()
	_sync_counters()

static func _stat_pair(stats: Dictionary, key: String) -> String:
	return "%d/%d" % [int(stats.get(key, 0)), int(stats.get(key + "_base", stats.get(key, 0)))]

static func _cross_pair(stats: Dictionary, first: String, second: String) -> String:
	var current: int = (int(stats.get(first, 0)) + int(stats.get(second, 0))) / 2
	var base: int = (int(stats.get(first + "_base", stats.get(first, 0)))
		+ int(stats.get(second + "_base", stats.get(second, 0)))) / 2
	return "%d/%d" % [current, base]

func _on_stats_tab_changed(tab: int) -> void:
	if tab == 1:
		_sync_knowledge()
	elif tab == 2:
		_sync_counters()
	elif tab == 3:
		_sync_session_experience()

func _track_experience() -> void:
	for skill: String in EXPERIENCE_SKILLS:
		var key: String = skill + "_exp"
		if not AppState.stats.has(key):
			continue
		var current: int = int(AppState.stats[key])
		if _experience_snapshot.has(skill):
			var gain: int = current - int(_experience_snapshot[skill])
			if gain > 0:
				_session_xp_gain[skill] = int(_session_xp_gain.get(skill, 0)) + gain
				_session_xp_last[skill] = gain
				_session_xp_max[skill] = maxi(int(_session_xp_max.get(skill, 0)), gain)
		_experience_snapshot[skill] = current

func _sync_session_experience() -> void:
	if session_xp_text == null:
		return
	var cells: Array[String] = ["[cell][b]Skill[/b][/cell]",
		"[cell][right][b]Total Exp[/b][/right][/cell]",
		"[cell][right][b]Max Exp[/b][/right][/cell]",
		"[cell][right][b]Last Exp[/b][/right][/cell]"]
	for skill: String in EXPERIENCE_SKILLS:
		cells.append("[cell]%s[/cell]" % skill.capitalize())
		cells.append("[cell][right]%d[/right][/cell]" % int(_session_xp_gain.get(skill, 0)))
		cells.append("[cell][right]%d[/right][/cell]" % int(_session_xp_max.get(skill, 0)))
		cells.append("[cell][right]%d[/right][/cell]" % int(_session_xp_last.get(skill, 0)))
	var seconds: int = maxi(0, (Time.get_ticks_msec() - _session_started_msec) / 1000)
	var xp_for_rate: int = int(_session_xp_gain.get("overall", 0))
	if xp_for_rate <= 0:
		for skill: String in EXPERIENCE_SKILLS:
			if skill != "overall":
				xp_for_rate += int(_session_xp_gain.get(skill, 0))
	var rate: float = float(xp_for_rate) * 60.0 / maxf(1.0, float(seconds))
	session_xp_text.text = ("[table=4]%s[/table]\n\nSession Time      %02d:%02d:%02d\n"
		+ "Exp/Min           %.2f\nDistance          %d") % ["".join(cells),
		seconds / 3600, (seconds / 60) % 60, seconds % 60, rate, _session_distance]

func _reset_session_tracking() -> void:
	_session_started_msec = Time.get_ticks_msec()
	_session_xp_gain.clear()
	_session_xp_max.clear()
	_session_xp_last.clear()
	_experience_snapshot.clear()
	_session_counters.clear()
	_session_distance = 0
	_last_distance_tile = Vector2i(-99999, -99999)
	_track_experience()
	_sync_session_experience()
	_sync_counters()

func _update_session_distance() -> void:
	var actor_value: Variant = AppState.actors.get(AppState.local_actor_id)
	if not actor_value is Dictionary:
		return
	var actor: Dictionary = actor_value as Dictionary
	var tile := Vector2i(int(actor.get("x", 0)), int(actor.get("y", 0)))
	if _last_distance_tile.x < -90000:
		_last_distance_tile = tile
		return
	var distance: int = maxi(absi(tile.x - _last_distance_tile.x),
		absi(tile.y - _last_distance_tile.y))
	if distance > 0 and distance <= 4:
		_session_distance += distance
	_last_distance_tile = tile

func _on_counter_category_selected(index: int) -> void:
	if index >= 0 and index < counter_categories.item_count:
		_selected_counter_category = counter_categories.get_item_text(index)
		_sync_counters()

func _increment_counter(category: String, amount := 1) -> void:
	_session_counters[category] = int(_session_counters.get(category, 0)) + amount
	_total_counters[category] = int(_total_counters.get(category, 0)) + amount
	_save_hud_settings()
	if stats_panel.visible and stats_tabs.current_tab == 2:
		_sync_counters()

func _sync_counters() -> void:
	if counter_text == null:
		return
	counter_text.text = ("[table=3][cell][b]Name[/b][/cell]"
		+ "[cell][right][b]This Session[/b][/right][/cell]"
		+ "[cell][right][b]Total[/b][/right][/cell]"
		+ "[cell]%s[/cell][cell][right]%d[/right][/cell]"
		+ "[cell][right]%d[/right][/cell][/table]\n\n"
		+ "Totals reflect actions observed by this client.\nDistance this session: %d tiles") % [
		_selected_counter_category, int(_session_counters.get(_selected_counter_category, 0)),
		int(_total_counters.get(_selected_counter_category, 0)), _session_distance]

func _request_perks() -> void:
	var now: int = Time.get_ticks_msec()
	if now < _perk_capture_until_msec:
		return
	_known_perks.clear()
	_perk_capture_until_msec = now + 8000
	var error: Error = Network.send_chat("#list_perks")
	if error != OK:
		_perk_capture_until_msec = 0

func _capture_perks_from_chat() -> void:
	if Time.get_ticks_msec() > _perk_capture_until_msec or AppState.chat_lines.is_empty():
		return
	var line: Dictionary = AppState.chat_lines.back() as Dictionary
	var text: String = str(line.get("text", "")).strip_edges()
	if text == "You have no perks.":
		_known_perks.clear()
	elif PERK_NAMES.has(text) and not _known_perks.has(text):
		_known_perks.append(text)
		_known_perks.sort()
	if stats_panel.visible and stats_tabs.current_tab == 0:
		_sync_stats()

func _sync_experience_meter(stats: Dictionary) -> void:
	var skill: String = _selected_experience_skill
	var current_experience: int = int(stats.get(skill + "_exp", 0))
	var next_experience: int = int(stats.get(skill + "_exp_next", 0))
	var level: int = int(stats.get(skill + "_base", stats.get(skill, 0)))
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
	if not (show_overhead_health.button_pressed or show_overhead_ether.button_pressed
			or show_overhead_food.button_pressed or show_overhead_action.button_pressed):
		if actor_resource_overlay.visible:
			actor_resource_overlay.hide()
		return
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
	# camera aspect instead of stretching a fixed 16:9 render target. The
	# container reports canvas units, which the content-scale system multiplies
	# onto the screen; rendering at that size would pin the world to the 1280x720
	# design resolution and upscale it, so the scale factor is applied here to
	# render at the window's true pixel size.
	var render_scale: Vector2 = get_viewport().get_final_transform().get_scale()
	var target_size := Vector2i(
		maxi(1, roundi(viewport_container.size.x * maxf(render_scale.x, 0.01))),
		maxi(1, roundi(viewport_container.size.y * maxf(render_scale.y, 0.01))))
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
	# Runs every frame. Resolving eleven unique-name nodes and formatting a
	# dictionary into a signature string each time allocated for nothing; the
	# buttons are resolved once and the comparison is now a bitmask.
	if _hud_state_buttons.is_empty():
		_hud_state_buttons = [%WalkButton, %MapButton, %SitButton, %AttackButton,
			%TradeButton, %InventoryButton, %StatsButton, %KnowledgeButton,
			%ManufacturingButton, %ChatButton, %DisconnectButton]
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var sitting: bool = bool(local_actor.get("sitting", false))
	var stats_open: bool = stats_panel.visible
	var stats_tab: int = stats_tabs.current_tab
	var states: Array[bool] = [
		_interaction_mode == "walk" and not sitting,
		full_map.visible,
		sitting,
		_interaction_mode == "attack",
		_interaction_mode == "trade" or bool(AppState.trade.get("open", false)),
		inventory_panel.visible,
		stats_open and stats_tab != 1,
		stats_open and stats_tab == 1,
		manufacturing_panel.visible,
		chat_input.has_focus(),
		AppState.connection_state == "connected"]
	var mask: int = 0
	for index: int in states.size():
		if states[index]:
			mask |= 1 << index
	if not force and mask == _hud_button_state_mask:
		return
	_hud_button_state_mask = mask
	for index: int in _hud_state_buttons.size():
		var button: Button = _hud_state_buttons[index]
		var active: bool = states[index]
		button.set_pressed_no_signal(active)
		var atlas: Texture2D = _hud_active_atlas if active else _hud_inactive_atlas
		if atlas != null:
			button.icon = _atlas_region(atlas, _hud_icon_regions[button] as Rect2)

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
	if config.load(SETTINGS_PATH) == OK:
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
	# Preserve settings owned by the minimap/options UI in the same config file.
	config.load(SETTINGS_PATH)
	config.set_value("lower_hud", "order", _hud_meter_order)
	for meter_key: String in _hud_meter_order:
		config.set_value("lower_hud", "show_" + meter_key,
			bool(_hud_meter_visible.get(meter_key, true)))
	config.set_value("lower_hud", "experience_skill", _selected_experience_skill)
	var error: Error = config.save(SETTINGS_PATH)
	if error != OK:
		push_warning("Unable to save lower HUD preferences: " + error_string(error))

func _build_inventory_slots() -> void:
	for slot: int in range(36):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(64.0, 56.0)
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.focus_mode = Control.FOCUS_NONE
		button.clip_contents = true
		button.text = ""
		button.tooltip_text = "Empty inventory slot %d" % (slot + 1)
		button.disabled = true
		button.pressed.connect(_on_inventory_slot_pressed.bind(slot))
		var quantity: Label = Label.new()
		quantity.name = "Quantity"
		quantity.mouse_filter = Control.MOUSE_FILTER_IGNORE
		quantity.anchor_left = 1.0
		quantity.anchor_top = 1.0
		quantity.anchor_right = 1.0
		quantity.anchor_bottom = 1.0
		quantity.offset_left = -48.0
		quantity.offset_top = -23.0
		quantity.offset_right = -4.0
		quantity.offset_bottom = -2.0
		quantity.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		quantity.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
		quantity.add_theme_color_override("font_color", Color.WHITE)
		quantity.add_theme_color_override("font_outline_color", Color(0.02, 0.02, 0.02))
		quantity.add_theme_constant_override("outline_size", 4)
		button.add_child(quantity)
		inventory_grid.add_child(button)
		inventory_slot_buttons.append(button)
		inventory_quantity_labels.append(quantity)

func _build_equipment_slots() -> void:
	for index: int in range(8):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(64.0, 56.0)
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.focus_mode = Control.FOCUS_NONE
		button.text = ""
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
			button.focus_mode = Control.FOCUS_NONE
			button.pressed.connect(_on_quick_slot_pressed.bind(slot))
			quick_slot_buttons.append(button)
			slot += 1

func _bind_spell_slots() -> void:
	var slot := 0
	for child: Node in spell_slot_container.get_children():
		if child is Button:
			var button: Button = child as Button
			button.focus_mode = Control.FOCUS_NONE
			button.pressed.connect(_cast_spell_slot.bind(slot))
			spell_slot_buttons.append(button)
			slot += 1
	_sync_spells()

func _sync_inventory() -> void:
	inventory_load.text = "Load: %d / %d" % [int(AppState.stats.get("carried", 0)),
		int(AppState.stats.get("capacity", 0))]
	for slot: int in range(inventory_slot_buttons.size()):
		var button: Button = inventory_slot_buttons[slot]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			var image_id: int = int(item.get("image_id", 0))
			button.icon = item_atlas.icon_for(image_id)
			button.text = ""
			inventory_quantity_labels[slot].text = str(int(item.get("quantity", 0)))
			button.tooltip_text = _inventory_tooltip(item)
			button.disabled = false
		else:
			button.icon = null
			button.text = ""
			inventory_quantity_labels[slot].text = ""
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
			button.text = ""
			button.tooltip_text = _inventory_tooltip(item) + "\nEquipped position %d" % (index + 1)
			button.disabled = false
		else:
			button.icon = null
			button.text = ""
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
			quick_button.text = ""
			quick_button.disabled = not usable or cooldown_seconds > 0
			var quick_tooltip: String = (_inventory_tooltip(quick_item)
				+ "\nQuick slot: %d  Quantity: %d" % [slot + 1,
					int(quick_item.get("quantity", 0))])
			if cooldown_seconds > 0:
				quick_tooltip += "\nCooldown: %d seconds" % cooldown_seconds
			elif not usable:
				quick_tooltip += "\nThis item cannot be used directly."
			quick_button.tooltip_text = quick_tooltip
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
			button.text = ""
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
		button.text = ""
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
	if error == OK:
		_increment_counter("Used Items", 1)
	else:
		push_warning("USE_INVENTORY_ITEM failed: " + error_string(error))

func _on_chat_submitted(text: String) -> void:
	var message: String = text.strip_edges()
	if message.is_empty():
		chat_input.release_focus()
		return
	var is_private: bool = message.begins_with("/") and message.length() > 1
	if not is_private and _chat_tab.begins_with("channel:") and not message.begins_with("@"):
		message = "@" + message
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
	stats_panel.hide()
	full_map.hide()
	trade_panel.hide()
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
	var logo_texture: Texture2D = _external_texture("res://assets/ui/eloria_logo_master.png")
	login_logo.texture = logo_texture
	hud_logo.texture = logo_texture
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
	var minimap_panel_style: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	minimap_panel_style.set_border_width_all(6)
	minimap_panel_style.border_color = Color(0.86, 0.64, 0.25, 1.0)
	minimap_frame.add_theme_stylebox_override("panel", minimap_panel_style)
	var map_sidebar_style: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	map_sidebar_style.bg_color = Color(0.0, 0.0, 0.0, 0.98)
	($GameView/FullMap/MapLayout/Sidebar as PanelContainer).add_theme_stylebox_override(
		"panel", map_sidebar_style)
	var empty_button: StyleBoxEmpty = StyleBoxEmpty.new()
	for child: Node in $GameView/Quickbar/QuickRows/Buttons.get_children():
		if child is Button:
			var icon_button: Button = child as Button
			icon_button.flat = true
			icon_button.focus_mode = Control.FOCUS_NONE
			for state_name: String in ["normal", "hover", "pressed", "disabled", "focus"]:
				icon_button.add_theme_stylebox_override(state_name, empty_button)
	for quick_button: Button in quick_slot_buttons + spell_slot_buttons:
		quick_button.focus_mode = Control.FOCUS_NONE
	_style_meter(health_bar, Color(0.17, 0.82, 0.22, 1.0))
	_style_meter(health_bottom, Color(0.9, 0.16, 0.14, 1.0))
	_style_meter(food_bottom, Color(0.96, 0.78, 0.16, 1.0))
	_style_meter(load_bottom, Color(0.62, 0.43, 0.34, 1.0))
	_style_meter(experience_bottom, Color(0.18, 0.76, 0.22, 1.0))
	_style_meter(overhead_health_row.get_node("Bar") as ProgressBar,
		Color(0.9, 0.16, 0.14, 1.0))
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
	# Modified 2026-08-28 for Eloria Client: the legacy visual ids below 100 are
	# real equipment now, not creation leftovers, so they are no longer dropped.
	# An authored NPC look is applied last and outranks the server's appearance
	# bytes, which is how a Four Gates guard keeps its guard gear without an
	# alias hijacking the shared legacy id for every other actor.
	var visuals: Dictionary = AppearanceVariants.equipment_visuals(
		actor_type, appearance)
	var server_visuals: Dictionary = dto.get("equipment_visuals", {}) as Dictionary
	for raw_part: Variant in server_visuals:
		visuals[int(raw_part)] = int(server_visuals[raw_part])
	var look: Dictionary = npc_looks.get(str(int(dto.get("actor_type", -1))), {}) as Dictionary
	var look_visuals: Dictionary = look.get("equipmentVisuals", {}) as Dictionary
	for raw_part: Variant in look_visuals:
		visuals[int(raw_part)] = int(look_visuals[raw_part])
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
