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
const OccluderFadeScript := preload("res://src/world/occluder_fade.gd")
const InvasionAssistantScript := preload("res://src/ui/invasion_assistant.gd")
const ExtensionWindowsScript := preload("res://src/ui/extension_windows.gd")
const MapMarkerOverlayScript := preload("res://src/ui/map_marker_overlay.gd")
const PlayerInfoPanelScript := preload("res://src/ui/player_info_panel.gd")
const AudioDirectorScript := preload("res://src/audio/audio_director.gd")
const SigilWindowScript := preload("res://src/ui/sigil_window.gd")
const SpellsWindowScript := preload("res://src/ui/spells_window.gd")
const EmotesWindowScript := preload("res://src/ui/emotes_window.gd")
const RangingWindowScript := preload("res://src/ui/ranging_window.gd")
const SettingsWindowScript := preload("res://src/ui/settings_window.gd")
const ReferenceWindowScript := preload("res://src/ui/reference_window.gd")
const ActiveBuffBarScript := preload("res://src/ui/active_buff_bar.gd")
var interior_cutaway: RefCounted = InteriorCutawayScript.new()
var occluder_fade: RefCounted = OccluderFadeScript.new()
var invasion_assistant_window
var extension_windows: Control
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
@onready var map_marker_title: Label = %MapMarkerTitle
@onready var map_marker_list: RichTextLabel = %MapMarkerList
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
@onready var skill_rows: VBoxContainer = %SkillRows
@onready var experience_skill_label: Label = %ExperienceSkillLabel
@onready var hud_timer_label: Label = %HudTimer
@onready var knowledge_bar: ProgressBar = %KnowledgeBar
@onready var knowledge_text: Label = %KnowledgeText
@onready var fps_label: Label = %FpsLabel
@onready var hud_indicators: HBoxContainer = %HudIndicators
@onready var clock_text: Label = %ClockText
@onready var clock_hand: Line2D = %ClockHand
@onready var clock_face: TextureRect = %ClockFace
@onready var compass_needle: Line2D = %CompassNeedle
@onready var compass_face: TextureRect = %CompassFace
@onready var hud_logo: TextureRect = %HudLogo
@onready var right_rail: Panel = %RightRail
@onready var actor_resource_overlay: PanelContainer = %ActorResourceOverlay
@onready var actor_hud_menu: PanelContainer = %ActorHudMenu
@onready var overhead_player_name: Label = %OverheadPlayerName
@onready var overhead_health_row: HBoxContainer = %HealthRow
@onready var overhead_ether_row: HBoxContainer = %EtherRow
@onready var overhead_food_row: HBoxContainer = %FoodRow
@onready var overhead_action_row: HBoxContainer = %ActionRow
@onready var banner_menu_enabled: CheckButton = %BannerMenuEnabled
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
@onready var inventory_inspect_button: Button = %InventoryInspect
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
@onready var sit_button: Button = %SitButton
@onready var attack_button: Button = %AttackButton
@onready var trade_button: Button = %TradeButton
@onready var look_button: Button = %LookButton
@onready var spell_power_down: Button = %SpellPowerDown
@onready var spell_power_value: Label = %SpellPowerValue
@onready var spell_power_up: Button = %SpellPowerUp
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
@onready var inventory_quantity_bar: HBoxContainer = %InventoryQuantityBar
@onready var inventory_quantity_edit: LineEdit = %InventoryQuantityEdit
@onready var carried_item: TextureRect = %CarriedItem
@onready var ground_bag_header: Control = %GroundBagHeader
@onready var ground_bag_grid: GridContainer = %GroundBagGrid
@onready var ground_bag_drop_button: Button = %GroundBagDrop
@onready var ground_bag_resize_grip: Button = %GroundBagResizeGrip
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
@onready var connection_banner: Label = %ConnectionBanner
@onready var harvest_banner: Label = %HarvestBanner
@onready var reading_panel: PanelContainer = %ReadingPanel
@onready var reading_title: Label = %ReadingTitle
@onready var reading_close: Button = %ReadingClose
@onready var reading_progress: ProgressBar = %ReadingProgress
@onready var reading_detail: RichTextLabel = %ReadingDetail
@onready var popup_panel: PanelContainer = %PopupPanel
@onready var popup_title: Label = %PopupTitle
@onready var popup_text: RichTextLabel = %PopupText
@onready var popup_options: VBoxContainer = %PopupOptions
@onready var popup_confirm: Button = %PopupConfirm
@onready var popup_dismiss: Button = %PopupDismiss
@onready var console_output: RichTextLabel = %ConsoleOutput
@onready var console_diagnostics_button: Button = %ConsoleDiagnostics
@onready var diagnostics_output: RichTextLabel = %DiagnosticsOutput
@onready var settings_panel: PanelContainer = %SettingsPanel
@onready var sound_enabled: CheckButton = %SoundEnabled
@onready var sound_volume: HSlider = %SoundVolume
@onready var sound_volume_value: Label = %SoundVolumeValue
@onready var minimap_size: HSlider = %MinimapSize
@onready var minimap_size_value: Label = %MinimapSizeValue
@onready var show_through_obstacles: CheckButton = %ShowThroughObstacles
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
var map_object_nodes: Dictionary = {}
## Server-placed map markers on the current map, keyed by the server's marker id.
var map_marker_nodes: Dictionary = {}
var map_marker_overlay: Control
## Short-lived world effects the server announced. Kept only so a test can see
## what is on screen; each one frees itself when it finishes.
var world_effects: Array = []
## The sky and the fires the server placed on this map.
var weather_layer: Weather3D
## Objects the server placed into this map after it loaded, by object id.
var placed_object_nodes: Dictionary = {}
var audio_director: Node
var map_ambience_root: Node3D
var sigil_window: Control
var spells_window: Control
var emotes_window: Control
var ranging_window: Control
var settings_window: Control
var reference_window: Control
## Client-side presentation switches. None of them changes what the server
## decides; they change what this machine draws.
var _shadows_enabled := true
var _effects_enabled := true
var _nameplates_enabled := true
var _camera_follows_player := true
var _player_notes := ""
## True while the loaded package lets the hour drive its environment. An
## interior does not, and neither does a package that opts out.
var console_commands := ConsoleCommands.new()
var _console_history: Array[String] = []
var _console_history_index := 0
var _day_night_active := false
var _day_night_refresh_msec := 0
## The power the next cast asks for. Presentational: the server states what
## each effect may reach and refuses anything it will not allow.
var requested_spell_power := 1
var player_info_panel: Control
var active_buff_bar: Control
## Server map objects whose tile has no navigation surface beneath it on the
## rendered map. Misplaced content rather than a client fault, but silent
## unless somebody counts it.
var _ungrounded_map_objects: Dictionary = {}
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
var _minimap_zoom := MINIMAP_ZOOM_DEFAULT
var _map_environment: Environment
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
var _show_through_obstacles := true
var _bulk_exclusions: Dictionary = {
	"store": [false, false, false, false],
	"drop": [false, false, false, false]}
var _item_lists: Dictionary = {}
var _store_options_menu: PopupMenu
var _drop_options_menu: PopupMenu
var _minimap_menu: PopupMenu
var _minimap_visible := false
## Set when the socket dropped without the player asking. The next successful
## login resynchronises rather than trusting anything from before the drop.
var _resync_after_reconnect := false
var _reading_completed_index := -1
var _reading_shown_index := -1
var _reading_hidden := false
var _popup_radio_groups: Dictionary = {}
var _popup_radio_buttons: Dictionary = {}
var _popup_entries: Dictionary = {}
var _session_started_msec := 0
var _experience_snapshot: Dictionary = {}
var _session_xp_gain: Dictionary = {}
var _session_xp_max: Dictionary = {}
var _session_xp_last: Dictionary = {}
var _session_distance := 0
var _last_distance_tile := Vector2i(-99999, -99999)
## The server owns every lifetime total. The "this session" column is the
## difference against the totals as they stood when the session or the reset
## started, which is presentation of authoritative numbers, not a second count.
var _counter_session_baseline: Dictionary = {}
var _keyboard_moving := false
var _keyboard_running := false
var _keyboard_direction := Vector2i.ZERO
var _keyboard_goal_tile := Vector2i(-99999, -99999)
var _keyboard_refresh_msec := 0
## The heading WASD resolves against, latched when a keyboard burst begins and
## held until it ends.
var _keyboard_reference_yaw := 0.0
var _ground_bag_get_all_requested_msec := -1
var _ground_bag_get_all_bag_id := -1
## The inventory slot riding on the cursor in walk mode, or -1. Eternal Lands
## picks an item up on the first click and puts it down on the second; the
## slot number is the whole of the state, because the item itself never leaves
## the server's inventory until the placing click is answered.
var _carried_slot := -1
var _inventory_quantities: Array[int] = INVENTORY_QUANTITY_DEFAULTS.duplicate()
var _inventory_tool := "grab"
## Whether the next item description may open the detail window. The short line
## and the detail window are two readings of the same server reply, so which
## one the player gets is decided here rather than by asking the server twice.
var _detail_popup_allowed := false
var _ground_bag_scale := 1.0
var _ground_bag_resizing := false
var _ground_bag_resize_start_mouse := Vector2.ZERO
var _ground_bag_resize_start_scale := 1.0
var _selected_quantity_box := 0
var _editing_quantity_box := -1
var inventory_quantity_buttons: Array[Button] = []
var ground_bag_slot_buttons: Array[Button] = []
var ground_bag_quantity_labels: Array[Label] = []
var _ground_bag_dragging := false
var _ground_bag_drag_offset := Vector2.ZERO
var _selected_counter_category := ""
var _right_mouse_down := false
var _right_mouse_dragged := false
var _interaction_mode := "walk"
## Alt held down. While it is, an ordinary click attacks whatever it lands on,
## so the move icon shows the attack icon to say so. It is a preview and not a
## mode: letting Alt go puts the move icon back, and it never disturbs an
## attack mode the player chose from the HUD.
var _alt_attack_preview := false
var _encyclopedia_bookmarks: Array = []
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
## The rail's countdown/stopwatch, kept to Eternal Lands' behaviour: click to
## start or stop, shift+click to change mode, middle-click to reset, wheel to
## set the countdown start. The value only ever lives here - it is a kitchen
## timer, not game state.
var _hud_timer_stopwatch := false
var _hud_timer_running := false
var _hud_timer_seconds := 90
var _hud_timer_start_seconds := 90
var _hud_timer_last_tick_msec := 0
## Which parts of the legacy HUD are drawn, in Eternal Lands' terms. Persisted
## under [hud] and toggled from the settings window's HUD tab.
var _hud_element_options: Dictionary = {
	"show_fps": true, "show_game_seconds": true, "hud_timer": true,
	"knowledge_bar": true, "side_stats": true, "indicators": true,
	"analog_clock": true, "digital_clock": true, "chat_timestamps": true}
## The per-skill rail rows, keyed by stat name, each holding bar + labels.
var _skill_row_nodes: Dictionary = {}
## The indicator letters, keyed by their Eternal Lands letter.
var _indicator_labels: Dictionary = {}
## Private messages that arrived and have not been acknowledged by clicking
## the M indicator, which is exactly what Eternal Lands' M indicator counts.
var _unseen_pm_count := 0
var _fps_refresh_msec := 0
var _hud_layout_menu: PopupPanel
var _hud_layout_list: ItemList
var _hud_layout_visible: CheckButton
var _hud_skill_selector: OptionButton
var _floating_feedback_layer: Control
var _pending_floating_feedback: Array[Dictionary] = []
var _floating_feedback_flush_queued := false
var _active_floating_labels: Array[Label] = []
var _last_skill_experience_msec := -100000
## Config key -> CheckBox on the right-click banner menu, filled in _ready().
var _banner_option_boxes: Dictionary = {}
var _banner_background_style: StyleBoxFlat

const FLOATING_FEEDBACK_BASE_OFFSET := 78.0
const FLOATING_FEEDBACK_ROW_HEIGHT := 21.0
const FLOATING_FEEDBACK_MAX_ROWS := 4
const FLOATING_FEEDBACK_RISE := 58.0
const FLOATING_FEEDBACK_LIFETIME := 1.5
const FLOATING_FEEDBACK_FADE_DELAY := 0.5
const FLOATING_FEEDBACK_OVERALL_GRACE_MSEC := 250

const HUD_SKILLS: Array[String] = [
	"attack", "defense", "harvesting", "alchemy", "magic", "potion",
	"summoning", "manufacturing", "crafting", "engineering", "tailoring",
	"ranging", "overall"]

## Eternal Lands drives its overhead banner from the right-click menu built in
## gamewin.c, and every entry there is its own switch. The menu keeps EL's
## wording and order, with the action-point pair Eloria adds appended to the
## bar/number block. Keys are what eloria_hud.cfg stores.
const BANNER_OPTION_NODES := {
	"show_names": "ShowNames",
	"health_bar": "ShowHealthBar", "health_numbers": "ShowHealthNumbers",
	"ether_bar": "ShowEtherBar", "ether_numbers": "ShowEtherNumbers",
	"food_bar": "ShowFoodBar", "food_numbers": "ShowFoodNumbers",
	"action_bar": "ShowActionBar", "action_numbers": "ShowActionNumbers",
	"instance_mode": "InstanceMode", "speech_bubbles": "SpeechBubbles",
	"banner_background": "BannerBackground", "sit_lock": "SitLock",
	"ranging_lock": "RangingLock", "menu_disabled": "DisableMenu"}

const BANNER_OPTION_DEFAULTS := {
	"show_names": true,
	"health_bar": true, "health_numbers": true,
	"ether_bar": true, "ether_numbers": true,
	"food_bar": true, "food_numbers": true,
	"action_bar": true, "action_numbers": true,
	"instance_mode": false, "speech_bubbles": false,
	"banner_background": false, "sit_lock": false,
	"ranging_lock": false, "menu_disabled": false}

## Row name, the switch that shows its bar, the switch that shows its numbers,
## and the colour ramp actors.c uses for it.
const BANNER_ROWS := [
	["HealthRow", "health_bar", "health_numbers", "health"],
	["EtherRow", "ether_bar", "ether_numbers", "ether"],
	["FoodRow", "food_bar", "food_numbers", "food"],
	["ActionRow", "action_bar", "action_numbers", "action"]]

const BANNER_BAR_MIN_WIDTH := 46.0
## client_serv.h: BOW_LONG through BOW_CROSS are the ranged weapon visuals, and
## gamewin.c gates Ranging Lock on exactly that span.
const RANGE_WEAPON_FIRST := 64
const RANGE_WEAPON_LAST := 68
## interface.c defaults instance_mode_banner_height to five banner lines.
const BANNER_INSTANCE_LIFT_ROWS := 5.0
const SPEECH_BUBBLE_MSEC := 6000

const CHAT_FADE_DELAY_MSEC := 7000
const CHAT_FADE_DURATION_MSEC := 1800
const SETTINGS_PATH := "user://eloria_hud.cfg"
const KEYBOARD_LOOKAHEAD_TILES := 4
const KEYBOARD_REFRESH_MSEC := 360
const GROUND_BAG_GET_ALL_TIMEOUT_MSEC := 1000
const GROUND_BAG_SLOT_COUNT := 20
## The legacy client's six editable quantity boxes and their defaults. The
## selected one is the amount every drop and every pick-up uses.
const INVENTORY_QUANTITY_DEFAULTS: Array[int] = [1, 5, 10, 20, 50, 100]
## Seven digits: a stack can run into the millions on a long-lived character,
## and a box that cannot hold the number cannot be used to move it.
const INVENTORY_QUANTITY_MAX := 9999999
const INVENTORY_QUANTITY_DIGITS := 7

## What a left click on an item does. Right-clicking an item steps through
## these in order, and the Use, Equip, Unequip and Inspect buttons each select
## one, so the buttons and the click do the same thing by the same names.
const INVENTORY_TOOLS: Array[String] = ["grab", "use", "inspect"]
const INVENTORY_TOOL_LABELS := {
	"grab": "Move", "use": "Use", "equip": "Equip", "unequip": "Unequip",
	"inspect": "Inspect",
}
## Doubles as the black margin around the minimap render and the band that
## drags the window. 54 left more empty frame than map; half of it still
## grabs comfortably and hands the render the rest.
const MINIMAP_DRAG_BORDER := 27.0
## The floor under the ambient light the two map cameras render with, so a
## minimap at midnight is still a map.
const MAP_MINIMUM_AMBIENT := 0.9
## Breathing room inside each bottom-rail icon button, so the painted frame the
## icon carries does not touch its neighbour or the panel border.
const HUD_ICON_PADDING := 2.0

## Eternal Lands' indicator letters, their meanings, and how each state is
## honestly known here. G (glow perk) and A (summon attack-at-will) have no
## server signal on this fork, so they render as unavailable rather than
## pretending a state.
const HUD_INDICATORS: Array[Array] = [
	["S", "Special Day", "Ordinary Day"],
	["H", "Harvesting", "Not Harvesting"],
	["P", "Poison (not stated by this server)", "Poison (not stated by this server)"],
	["M", "Recent Messages", "No Messages"],
	["R", "Ranging Lock On", "Ranging Lock Off"],
	["G", "Glow Perk (not on this server)", "Glow Perk (not on this server)"],
	["A", "Attack at Will (not on this server)", "Attack at Will (not on this server)"]]

## One rail stat row. The rail's font is ten pixels and its line box is
## thirteen, so a twelve-pixel row cut every descender in half; fourteen holds
## the line with the text centred in it.
const SKILL_ROW_HEIGHT := 14.0

## The rail's stat rows, in Eternal Lands' order and abbreviations.
const SKILL_ROW_SPECS: Array[Array] = [
	["att", "attack"], ["def", "defense"], ["har", "harvesting"],
	["alc", "alchemy"], ["mag", "magic"], ["pot", "potion"],
	["sum", "summoning"], ["man", "manufacturing"], ["cra", "crafting"],
	["eng", "engineering"], ["tai", "tailoring"], ["ran", "ranging"],
	["oa", "overall"]]
## Cell 24 of the HUD atlas: the standing figure the sit icon wears while the
## player is seated.
const STAND_ICON_REGION := Rect2(0, 96, 32, 32)

const INDICATOR_ACTIVE_COLOUR := Color(0.95, 0.76, 0.52)
const INDICATOR_INACTIVE_COLOUR := Color(0.40, 0.30, 0.20)
const INDICATOR_UNAVAILABLE_COLOUR := Color(0.20, 0.15, 0.10)

## Nothing may cover the fixed resource rail down the right-hand edge; this is
## the margin draggable scene windows are clamped against.
const RESERVED_RIGHT_RAIL_MARGIN := 96.0

## The GUI palette Eternal Lands paints every window with (elwindows.c):
## borders, frames and title text in gui_color, hover fills in the inverse.
const EL_GUI_COLOUR := Color(0.77, 0.57, 0.39)
const EL_GUI_INVERT_COLOUR := Color(0.32, 0.23, 0.15)
const EL_GUI_BRIGHT_COLOUR := Color(0.95, 0.76, 0.52)
## How many metres of ground the minimap camera covers, and the bounds the
## scroll wheel moves it between.
const MINIMAP_ZOOM_DEFAULT := 180.0
const MINIMAP_ZOOM_MIN := 60.0
const MINIMAP_ZOOM_MAX := 480.0
const MINIMAP_ZOOM_STEP := 1.25
const UI_SCALE_MIN := 0.5
const UI_SCALE_MAX := 1.5
# The minimap and the full map are extra renders of the whole 3D world through
# their own cameras. Both used to redraw every frame, visible or not, which
# tripled the client's raster and shadow cost for two top-down views that read
# identically at a fraction of the rate.
const MINIMAP_REFRESH_MSEC := 66
const FULL_MAP_REFRESH_MSEC := 200
## The sky only has to keep up with a six-hour day; twice a second is already
## finer than the eye can follow and costs a handful of property writes.
const DAY_NIGHT_REFRESH_MSEC := 500
## How many submitted lines the console remembers for its up/down history.
const CONSOLE_HISTORY_LIMIT := 60
## The fork's spell quickbar. Twelve slots, shifted 1-0 then Ctrl+1/Ctrl+2 -
## the legacy client's six were never enough for the catalog's 22 spells.
const SPELL_QUICK_SLOTS := 12
const INVENTORY_MIN_SCALE := 0.65
const INVENTORY_MAX_SCALE := 1.75
const TILE_DIRECTIONS: Array[Vector2i] = [
	Vector2i(0, -1), Vector2i(1, -1), Vector2i(1, 0), Vector2i(1, 1),
	Vector2i(0, 1), Vector2i(-1, 1), Vector2i(-1, 0), Vector2i(-1, -1)]
const EXPERIENCE_SKILLS: Array[String] = [
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
	# The nine Eloria extension windows live in their own script: main.gd is
	# already long enough that nine more windows would make it unreadable, and
	# they share one seam - the fork's extension protocol.
	map_marker_overlay = MapMarkerOverlayScript.new()
	map_marker_overlay.name = "MapMarkerOverlay"
	map_marker_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	map_image.add_child(map_marker_overlay)
	map_marker_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	map_marker_overlay.configure(full_map_camera, adapter, full_map_viewport.size)
	audio_director = AudioDirectorScript.new()
	add_child(audio_director)
	player_info_panel = PlayerInfoPanelScript.new()
	game_view.add_child(player_info_panel)
	sigil_window = SigilWindowScript.new()
	game_view.add_child(sigil_window)
	sigil_window.configure(spell_catalog)
	# The three legacy windows Eternal Lands opens from its icon row: the spell
	# book, the emote picker and the ranging readout. Each lives in its own
	# script; main.gd only opens them and lends them a network seam.
	spells_window = SpellsWindowScript.new()
	game_view.add_child(spells_window)
	# Configured further down, once the spell catalog has read its data file:
	# the window builds its group rows from the catalog it is handed.
	emotes_window = EmotesWindowScript.new()
	game_view.add_child(emotes_window)
	emotes_window.call("configure", _perform_emote)
	ranging_window = RangingWindowScript.new()
	game_view.add_child(ranging_window)
	settings_window = SettingsWindowScript.new()
	game_view.add_child(settings_window)
	settings_window.setting_changed.connect(_on_client_setting_changed)
	settings_window.binding_changed.connect(_on_binding_changed)
	reference_window = ReferenceWindowScript.new()
	game_view.add_child(reference_window)
	reference_window.notes_changed.connect(_on_notes_changed)
	reference_window.bookmarks_changed.connect(_on_encyclopedia_bookmarks_changed)
	active_buff_bar = ActiveBuffBarScript.new()
	game_view.add_child(active_buff_bar)
	active_buff_bar.configure(spell_catalog)
	extension_windows = ExtensionWindowsScript.new()
	game_view.add_child(extension_windows)
	extension_windows.configure(item_atlas)
	extension_windows.combat_hud_preference_changed.connect(_save_hud_settings)
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
	spells_window.call("configure", spell_catalog, _cast_spell_by_id)
	manufacturing_catalog.configure(_json("res://data/manufacturing/recipes.json"))
	var knowledge_catalog_value: Variant = _json(
		"res://data/knowledge/catalog.json").get("entries", [])
	if knowledge_catalog_value is Array:
		for raw_knowledge_name: Variant in knowledge_catalog_value as Array:
			knowledge_catalog.append(str(raw_knowledge_name))
	# The encyclopedia builds half its pages out of these, so a recipe, spell,
	# book, region or skill the client does not have cannot appear on a page.
	reference_window.call("configure_catalogues", {
		"manufacturing": manufacturing_catalog, "spells": spell_catalog,
		"books": knowledge_catalog, "regions": cartography_regions,
		"items": item_atlas, "skills": EXPERIENCE_SKILLS})
	Network.connection_state_changed.connect(_on_connection_state_changed)
	Network.protocol_error.connect(func(message: String): status_label.text = "Protocol error: " + message)
	Network.reconnect_progress.connect(_on_reconnect_progress)
	AppState.login_succeeded.connect(_on_login_succeeded)
	AppState.login_failed.connect(_on_login_failed)
	AppState.character_created.connect(_on_character_created)
	AppState.character_creation_failed.connect(_on_character_creation_failed)
	AppState.state_changed.connect(_on_state_changed)
	AppState.floating_feedback_requested.connect(_on_floating_feedback_requested)
	AppState.special_effect_requested.connect(_on_special_effect_requested)
	AppState.actor_animation_requested.connect(_on_actor_animation_requested)
	AppState.missile_fired.connect(_on_missile_fired)
	AppState.ground_missile_fired.connect(_on_ground_missile_fired)
	AppState.thunder_struck.connect(_on_thunder_struck)
	AppState.teleport_seen.connect(_on_teleport_seen)
	weather_layer = Weather3D.new()
	world_root.add_child(weather_layer)
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
	_configure_banner_menu()
	_apply_eloria_theme()
	_configure_window_layers()
	_configure_cartography()
	_load_hud_settings()
	_configure_inventory_menus()
	_configure_minimap_menu()
	_build_inventory_slots()
	_build_equipment_slots()
	_build_ground_bag_slots()
	_build_inventory_quantity_boxes()
	_bind_quick_slots()
	_bind_spell_slots()
	_reset_trade_destinations()
	trade_source.item_selected.connect(_on_trade_source_selected)
	trade_own_offers.item_selected.connect(_on_trade_own_selected)
	trade_other_offers.item_selected.connect(_on_trade_other_selected)
	storage_categories.item_selected.connect(_on_storage_category_selected)
	storage_items.item_selected.connect(_on_storage_item_selected)
	storage_inventory.item_selected.connect(_on_storage_inventory_selected)
	ground_bag_header.gui_input.connect(_on_ground_bag_header_gui_input)
	knowledge_list.item_selected.connect(_on_knowledge_selected)
	knowledge_known_only.toggled.connect(_on_knowledge_filter_toggled)
	stats_tabs.tab_changed.connect(_on_stats_tab_changed)
	stats_close.pressed.connect(func() -> void: stats_panel.hide())
	counter_categories.item_selected.connect(_on_counter_category_selected)
	session_reset.pressed.connect(_reset_session_tracking)
	manufacturing_list.item_selected.connect(_on_manufacturing_selected)
	manufacturing_filter.text_changed.connect(_on_manufacturing_filter_changed)
	banner_menu_enabled.toggled.connect(_on_banner_menu_enabled_toggled)
	$GameView/ChatTabs/All.pressed.connect(_on_chat_tab_pressed.bind("all"))
	$GameView/ChatTabs/History.pressed.connect(_on_chat_tab_pressed.bind("history"))
	$GameView/ChatTabs/Options.pressed.connect(_on_options_pressed)
	_build_hud_layout_menu()
	_load_hud_layout()
	_connect_hud_context_inputs(%Quickbar)
	_build_skill_rows()
	_build_hud_indicators()
	hud_timer_label.gui_input.connect(_on_hud_timer_gui_input)
	knowledge_bar.gui_input.connect(_on_knowledge_bar_gui_input)
	if reference_window.has_signal("buddy_add_requested"):
		reference_window.connect("buddy_add_requested", _on_buddy_add_requested)
	_apply_hud_element_options()
	get_viewport().size_changed.connect(_on_window_size_changed)
	call_deferred("_on_window_size_changed")
	for channel_index: int in range(3):
		var channel_button: Button = get_node(
			"GameView/ChatTabs/Channel%d" % (channel_index + 1)) as Button
		channel_button.pressed.connect(_on_channel_tab_pressed.bind(channel_index))
	sound_enabled.toggled.connect(_on_sound_enabled_toggled)
	sound_volume.value_changed.connect(_on_sound_volume_changed)
	minimap_size.value_changed.connect(_on_minimap_size_changed)
	ui_scale_slider.value_changed.connect(_on_ui_scale_changed)
	show_through_obstacles.toggled.connect(_on_show_through_obstacles_toggled)
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
	ground_bag_resize_grip.gui_input.connect(_on_ground_bag_resize_grip_gui_input)
	for tool_button: Button in [inventory_use_button, inventory_equip_button,
			inventory_unequip_button, inventory_inspect_button]:
		tool_button.toggle_mode = true
	_sync_inventory_tool_buttons()
	saved_item_lists.item_selected.connect(_on_saved_item_list_selected)
	item_list_save.pressed.connect(_on_item_list_save_pressed)
	item_list_delete.pressed.connect(_on_item_list_delete_pressed)
	item_list_get.pressed.connect(_on_item_list_get_pressed)
	item_lists_close.pressed.connect(func() -> void: item_lists_panel.hide())
	%SettingsClose.pressed.connect(_close_settings)
	%ConsoleClose.pressed.connect(_toggle_console)
	console_diagnostics_button.toggled.connect(_on_console_diagnostics_toggled)
	popup_confirm.pressed.connect(_on_popup_confirm_pressed)
	popup_dismiss.pressed.connect(_on_popup_dismiss_pressed)
	popup_panel.hide()
	harvest_banner.hide()
	reading_panel.hide()
	reading_close.pressed.connect(_on_reading_close_pressed)
	_session_started_msec = Time.get_ticks_msec()
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

func _process(delta: float) -> void:
	_update_preview_viewport()
	if game_view.visible:
		_update_carried_item()
		_update_map_viewports()
		_update_local_actor_follow()
		# Rain is everywhere, so only the box the player is standing in is
		# drawn. Left at the world origin it fell a hundred metres away from
		# whoever was watching it.
		if weather_layer != null:
			weather_layer.follow(camera_rig.global_position)
		interior_cutaway.update(camera_rig.yaw_degrees)
		_update_occluder_fade(delta)
		_update_keyboard_movement()
		_update_session_distance()
		_update_legacy_clock_and_compass()
		_update_actor_resource_overlay()
		_update_cooldown_overlays()
		_update_chat_fade()
		_update_hud_timer()
		_update_fps_label()
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
	if _day_night_active and now >= _day_night_refresh_msec:
		_day_night_refresh_msec = now + DAY_NIGHT_REFRESH_MSEC
		_apply_day_night()
	if full_map.visible and map_image.visible and now >= _full_map_refresh_msec:
		_full_map_refresh_msec = now + FULL_MAP_REFRESH_MSEC
		full_map_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
		# The map camera follows the player, so the marker overlay is projected
		# again whenever the image beneath it is - and never while it is hidden.
		map_marker_overlay.queue_redraw()

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
			or storage_panel.visible or full_map.visible \
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
	if _movement_locked(Input.is_key_pressed(KEY_CTRL)):
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
	# WASD is resolved against the heading the burst started from, not against
	# the actor's live facing: the actor turns to face each step it takes, and
	# reading a turning actor back would swing a held diagonal round on itself.
	if not _keyboard_moving:
		_keyboard_reference_yaw = actor_node.desired_facing_yaw()
	var direction: Vector2i = _facing_relative_tile_direction(
		_keyboard_reference_yaw, forward_input, right_input)
	if direction == Vector2i.ZERO:
		_stop_keyboard_movement()
		return
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

func _clear_local_turn_prediction() -> void:
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if actor_value is ReplicatedActor3D and is_instance_valid(actor_value as ReplicatedActor3D):
		(actor_value as ReplicatedActor3D).clear_turn_prediction()

## Q and E ask the server to turn. The rendered facing comes from the actor
## command the server broadcasts in reply, which is also what makes the turn
## visible to every other player; the local rotation below is only a prediction
## that reply confirms. Nothing is decided here.
func _turn_local_actor(left: bool) -> void:
	var error: Error = Network.turn(left)
	if error != OK:
		push_warning("turn failed: " + error_string(error))
		return
	var actor_value: Variant = actor_nodes.get(AppState.local_actor_id)
	if actor_value is ReplicatedActor3D and is_instance_valid(actor_value as ReplicatedActor3D):
		(actor_value as ReplicatedActor3D).predict_turn(PI / 4.0 if left else -PI / 4.0)

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
	# It is showing the attack icon, so it does what the attack icon does.
	if _alt_attack_preview and _interaction_mode != "attack":
		_on_attack_button_pressed()
		return
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

## Asks the server to describe the selected player. The window that opens is
## the server's reply and nothing else: the client does not remember what it
## asked about, because the reply names the actor itself.
func _on_look_button_pressed() -> void:
	var actor_id: int = AppState.selected_actor_id
	if not _is_tradeable_player(actor_id, AppState.actors.get(actor_id, {})):
		return
	var error: Error = Network.look_at_player(actor_id)
	if error != OK:
		push_warning("GET_PLAYER_INFO failed: " + error_string(error))

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
	_minimap_visible = not minimap_frame.visible
	minimap_frame.visible = _minimap_visible
	_request_map_redraw()
	_sync_map_viewport_activity()
	_save_hud_settings()

func _toggle_console() -> void:
	if console_panel.visible:
		console_panel.hide()
		return
	full_map.hide()
	_close_settings()
	_sync_console()
	_sync_diagnostics()
	console_panel.show()
	console_panel.move_to_front()

## The console panel shows either the session message history or the protocol
## diagnostics. Undecoded packets and decode errors were reduced into AppState
## and emitted with no listener at all, so every gap in the client's protocol
## coverage failed completely silently; this is where they surface.
func _on_console_diagnostics_toggled(enabled: bool) -> void:
	console_output.visible = not enabled
	diagnostics_output.visible = enabled
	if enabled:
		_sync_diagnostics()

func _sync_diagnostics() -> void:
	if diagnostics_output == null or not diagnostics_output.visible:
		return
	var lines: Array[String] = []
	lines.append("[b]Undecoded server opcodes this session[/b]")
	if AppState.unknown_packets.is_empty():
		lines.append("  none")
	else:
		var opcodes: Array = AppState.unknown_packets.keys()
		opcodes.sort()
		for raw_opcode: Variant in opcodes:
			var record: Dictionary = AppState.unknown_packets[raw_opcode] as Dictionary
			lines.append("  %3d  x%-5d  last payload %d bytes, %s ago" % [
				int(raw_opcode), int(record.get("count", 0)),
				int(record.get("size", 0)),
				_elapsed_text(int(record.get("msec", 0)))])
		lines.append("  total undecoded packets: %d" % AppState.unknown_packet_count)
	lines.append("
[b]Recent decode errors[/b]")
	if AppState.recent_protocol_errors.is_empty():
		lines.append("  none")
	else:
		for index: int in range(AppState.recent_protocol_errors.size() - 1, -1, -1):
			var failure: Dictionary = AppState.recent_protocol_errors[index]
			lines.append("  %3d  %s  (%d bytes, %s ago)" % [
				int(failure.get("command", -1)), str(failure.get("error", "")),
				int(failure.get("size", 0)),
				_elapsed_text(int(failure.get("msec", 0)))])
	lines.append("
[b]World objects[/b]")
	lines.append("  server objects on this map: %d" % AppState.map_objects.size())
	if _ungrounded_map_objects.is_empty():
		lines.append("  all of them sit on the rendered navigation surface")
	else:
		lines.append("  [color=#ffb066]%d have no navigation surface beneath them[/color]"
			% _ungrounded_map_objects.size())
		var listed: int = 0
		for raw_object_id: Variant in _ungrounded_map_objects:
			if listed >= 8:
				lines.append("    …")
				break
			lines.append("    %d  %s" % [int(raw_object_id),
				str(_ungrounded_map_objects[raw_object_id])])
			listed += 1
	lines.append("
[b]Connection[/b]")
	lines.append("  state: %s%s" % [AppState.connection_state,
		"  (reconnect attempt %d)" % Network.reconnect_attempt()
		if Network.is_reconnecting() else ""])
	lines.append("  server clock: %s" % (
		"%d (synchronised %s ago)" % [AppState.server_timestamp,
			_elapsed_text(AppState.last_clock_sync_msec)]
		if AppState.last_clock_sync_msec > 0 else "never synchronised"))
	lines.append("  game minute: %d (%02d:%02d)" % [AppState.game_minute,
		AppState.game_minute / 60, AppState.game_minute % 60])
	diagnostics_output.text = "
".join(lines)

func _elapsed_text(msec: int) -> String:
	if msec <= 0:
		return "unknown"
	var seconds: int = maxi(0, (Time.get_ticks_msec() - msec) / 1000)
	if seconds < 60:
		return "%ds" % seconds
	return "%dm%02ds" % [seconds / 60, seconds % 60]

func _on_options_pressed() -> void:
	settings_panel.visible = not settings_panel.visible
	if settings_panel.visible:
		console_panel.hide()
		settings_panel.move_to_front()
	else:
		settings_window.close()
	$GameView/ChatTabs/Options.button_pressed = settings_panel.visible

## The tabbed window: graphics, camera, gameplay and the key bindings. The
## small panel keeps the settings that were already there.
func _on_more_settings_pressed() -> void:
	settings_window.toggle()
	audio_director.play("ui_click" if settings_window.is_open() else "ui_close")

func _close_settings() -> void:
	settings_panel.hide()
	$GameView/ChatTabs/Options.button_pressed = false

func _on_stats_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))):
		return
	stats_panel.visible = not stats_panel.visible
	if stats_panel.visible:
		inventory_panel.hide()
		manufacturing_panel.hide()
		stats_tabs.current_tab = 0
		_sync_stats()
	_sync_hud_button_states(true)

func _on_inventory_button_pressed() -> void:
	if bool(AppState.trade.get("open", false)):
		return
	inventory_panel.visible = not inventory_panel.visible
	if inventory_panel.visible:
		stats_panel.hide()
		manufacturing_panel.hide()
		# Ask for the enriched view of what the ordinary inventory packet
		# already told us. Command 226 never replaces that inventory: it only
		# names the items the icon ids stand for.
		Network.send_chat("#inventory")
		_sync_inventory()
	_sync_hud_button_states(true)

func _on_knowledge_button_pressed() -> void:
	if (bool(AppState.trade.get("open", false))
			or bool(AppState.storage.get("open", false))):
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
			or bool(AppState.storage.get("open", false))):
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
	_choose_inventory_tool("use")

func _on_inventory_equip_pressed() -> void:
	_choose_inventory_tool("equip")

func _on_inventory_unequip_pressed() -> void:
	_choose_inventory_tool("unequip")

func _on_inventory_inspect_pressed() -> void:
	_choose_inventory_tool("inspect")

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

## The bag grid mirrors Eternal Lands: a left click takes the quantity in the
## box below, so picking something up is one gesture rather than select-then-
## press. A right click asks the server what the stack is instead.
func _on_ground_bag_slot_pressed(index: int) -> void:
	var position: int = _ground_bag_slot_position(index)
	if position < 0:
		return
	var items: Dictionary = AppState.ground_bag.get("items", {}) as Dictionary
	var item_value: Variant = items.get(position)
	if not item_value is Dictionary:
		return
	var available: int = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
	var quantity: int = (available if Input.is_key_pressed(KEY_CTRL)
		else mini(available, _selected_quantity()))
	var error: Error = Network.pick_up_ground_item(position, quantity)
	if error != OK:
		push_warning("PICK_UP_ITEM failed: " + error_string(error))

func _ground_bag_slot_position(index: int) -> int:
	if index < 0 or index >= ground_bag_slot_buttons.size():
		return -1
	return int(ground_bag_slot_buttons[index].get_meta("bag_position", -1))

func _on_ground_bag_slot_gui_input(event: InputEvent, index: int) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse: InputEventMouseButton = event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_RIGHT:
		return
	_on_ground_bag_look_pressed(index)
	ground_bag_slot_buttons[index].accept_event()

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
	var slot: int = selected_inventory_slot
	if slot < 0 or slot >= 36:
		return
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var available: int = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
	var quantity: int = (available if Input.is_key_pressed(KEY_CTRL)
		else mini(available, _selected_quantity()))
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
	# Tell the server which Eloria extensions this client implements. Without
	# it the server serves the legacy dialogue and raw-text fallback for every
	# extension, which is what it had been doing for this client since it was
	# written.
	var capabilities_error: Error = Network.send_client_capabilities()
	if capabilities_error != OK:
		push_warning("#clientcaps failed: " + error_string(capabilities_error))
	if _resync_after_reconnect:
		# This session follows a dropped connection, so nothing that arrived
		# before the drop can be trusted. Ask for the three authoritative
		# snapshots everything else is derived from.
		_resync_after_reconnect = false
		var resync_error: Error = Network.request_resync()
		if resync_error != OK:
			push_warning("resync failed: " + error_string(resync_error))
		else:
			AppState.append_local_message(
				"Reconnected. Rebuilding world state from the server.", 3)
	login_panel.hide()
	creation_panel.hide()
	game_view.show()
	_sync_connection_banner()
	# Restore the saved minimap visibility. _clear_world_presentation() hides
	# the frame on disconnect, so this is what brings it back for the next
	# session rather than leaving the player to press Alt+M every time.
	minimap_frame.visible = _minimap_visible
	_request_map_redraw()
	_sync_map_viewport_activity()
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
	var was_in_world: bool = game_view.visible
	if value == "disconnected" and was_in_world:
		_clear_world_presentation()
		game_view.hide()
		login_panel.show()
		status_label.text = "Disconnected"
	if value == "connected" and _resync_after_reconnect:
		# The socket came back on its own. The password was never retained, so
		# the player authenticates again; the resync happens once they are back
		# in the world.
		status_label.text = "Reconnected. Enter your password to resume."
		password_edit.grab_focus()
	_sync_connection_banner()

## The connection state, wherever the player is looking. Anything other than a
## live authenticated session is worth saying out loud: a silently dead socket
## looks exactly like a quiet server.
func _sync_connection_banner() -> void:
	if connection_banner == null:
		return
	var state: String = AppState.connection_state
	if state == "connected" and AppState.authenticated:
		connection_banner.hide()
		return
	var text: String = ""
	match state:
		"reconnecting":
			text = "Connection lost - reconnecting (attempt %d of %d)…" % [
				Network.reconnect_attempt(), Network.RECONNECT_DELAYS_MSEC.size()]
		"connecting":
			text = "Connecting…"
		"connected":
			text = "Connected - not signed in"
		_:
			text = "Disconnected"
	connection_banner.text = text
	connection_banner.show()

func _on_reconnect_progress(attempt: int, total: int, delay_msec: int) -> void:
	_resync_after_reconnect = true
	status_label.text = "Connection lost. Reconnecting in %.1fs (attempt %d of %d)…" % [
		float(delay_msec) / 1000.0, attempt, total]
	AppState.append_local_message(
		"Connection lost. Reconnecting in %.1f seconds (attempt %d of %d)."
			% [float(delay_msec) / 1000.0, attempt, total], 3)
	_sync_connection_banner()

func _clear_world_presentation() -> void:
	for raw_node: Variant in actor_nodes.values():
		if is_instance_valid(raw_node):
			(raw_node as Node).queue_free()
	actor_nodes.clear()
	for raw_bag_node: Variant in ground_bag_nodes.values():
		if is_instance_valid(raw_bag_node):
			(raw_bag_node as Node).queue_free()
	ground_bag_nodes.clear()
	for raw_object_node: Variant in map_object_nodes.values():
		if is_instance_valid(raw_object_node):
			(raw_object_node as Node).queue_free()
	map_object_nodes.clear()
	_ungrounded_map_objects.clear()
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
	if event is InputEventKey and (event as InputEventKey).echo:
		return
	_track_attack_modifier(event)
	if _handle_bound_action(event):
		get_viewport().set_input_as_handled()

## Watches Alt so the move icon can say what a click would do. Every key and
## mouse event carries the modifier state it was sent with, and Alt itself
## arrives as a key event of its own, so both are read here rather than polled.
func _track_attack_modifier(event: InputEvent) -> void:
	if event is InputEventKey:
		var key: InputEventKey = event as InputEventKey
		if key.physical_keycode == KEY_ALT or key.keycode == KEY_ALT:
			_set_attack_modifier(key.pressed)
		else:
			_set_attack_modifier(key.alt_pressed)
	elif event is InputEventWithModifiers:
		_set_attack_modifier((event as InputEventWithModifiers).alt_pressed)

func _set_attack_modifier(held: bool) -> void:
	if _alt_attack_preview == held:
		return
	_alt_attack_preview = held
	_sync_hud_button_states(true)

## Alt-tabbing away leaves the key down as far as this client is concerned,
## and the release lands in another window. The icon would stay on attack.
func _notification(what: int) -> void:
	if what == NOTIFICATION_APPLICATION_FOCUS_OUT 			or what == NOTIFICATION_WM_WINDOW_FOCUS_OUT:
		_set_attack_modifier(false)

## Bindings that have to beat a focused HUD control, which is why they are
## resolved here instead of in _unhandled_input().
##
## Every branch is an InputMap action. Raw keycode comparisons used to shadow
## `toggle_inventory`, `turn_left` and `turn_right`, so rebinding those actions
## appeared to work and changed nothing, while `toggle_map`, `toggle_minimap`
## and `toggle_console` were resolved twice - once by keycode here and once by
## action in _unhandled_input(). Returns true when the event was consumed.
func _handle_bound_action(event: InputEvent) -> bool:
	# A focused text field owns its own characters and its own clipboard
	# shortcuts. Several of these actions default to bare printable keys, so
	# without this a backtick typed into chat would also open the console.
	if _text_entry_active():
		if event.is_action_pressed("cancel") and chat_input.has_focus():
			_hide_chat_input()
			return true
		return false
	# Connection control is reachable before the world exists, so it is
	# resolved ahead of the game-view gate below.
	if event.is_action_pressed("connect"):
		_on_connect_pressed()
		return true
	if event.is_action_pressed("disconnect"):
		_on_disconnect_pressed()
		return true
	if not game_view.visible:
		return false
	if event.is_action_pressed("toggle_inventory"):
		_on_inventory_button_pressed()
		return true
	if event.is_action_pressed("toggle_map"):
		_toggle_full_map()
		return true
	if event.is_action_pressed("toggle_minimap"):
		_toggle_minimap()
		return true
	if event.is_action_pressed("toggle_console"):
		_toggle_console()
		return true
	# Exact match, and ahead of turn_right: turning is a bare E, and Godot
	# matches an action without comparing modifiers unless it is asked to, so
	# Ctrl+E would otherwise turn the player as well as open the encyclopedia.
	if event.is_action_pressed("toggle_encyclopedia", false, true):
		_on_encyclopedia_button_pressed()
		return true
	if event.is_action_pressed("recenter_viewport"):
		_recenter_viewport_on_player()
		return true
	if event.is_action_pressed("turn_left"):
		_turn_local_actor(true)
		return true
	if event.is_action_pressed("turn_right"):
		_turn_local_actor(false)
		return true
	if event.is_action_pressed("cancel") and console_panel.visible:
		console_panel.hide()
		return true
	return false

func _recenter_viewport_on_player() -> void:
	camera_rig.reset_pan()
	_update_local_actor_follow()

func _unhandled_input(event: InputEvent) -> void:
	if not game_view.visible:
		return
	# While the settings window is waiting for a key, every key press belongs
	# to it: otherwise rebinding "attack" would attack.
	if settings_window != null and not str(settings_window.get("capturing")).is_empty():
		if event is InputEventKey and (event as InputEventKey).pressed:
			settings_window.call("apply_capture", event)
			get_viewport().set_input_as_handled()
		return
	for spell_slot: int in range(SPELL_QUICK_SLOTS):
		if event.is_action_pressed("quick_spell_%d" % (spell_slot + 1)):
			_cast_spell_slot(spell_slot)
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("screenshot"):
		_save_screenshot()
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
	# toggle_map, toggle_minimap and toggle_console are deliberately absent:
	# _handle_bound_action() owns them so they can be rebound. Seeing through
	# obstacles is not offered for rebinding, so it is still resolved here.
	if event.is_action_pressed("toggle_show_through_obstacles"):
		_toggle_show_through_obstacles()
		get_viewport().set_input_as_handled()
		return
	# The legacy window keys, each opening the window Eternal Lands binds it
	# to. They are resolved here rather than in _handle_bound_action() so a
	# focused text field keeps its own Ctrl shortcuts (Ctrl+A selects text
	# before it opens the statistics). They must also run before chat_focus:
	# that action is a bare T, Godot's inexact matching lets a bare binding
	# claim a modified press, and Ctrl+T would focus the chat instead of
	# opening the ranging window - the turn_right/Ctrl+E collision over again.
	var window_actions: Array[Array] = [
		["toggle_spells", _on_spells_button_pressed],
		["toggle_manufacture", _on_manufacturing_button_pressed],
		["toggle_emotes", _on_emotes_button_pressed],
		["toggle_quest_journal", _on_quest_button_pressed],
		["toggle_buddy", _on_buddy_button_pressed],
		["toggle_stats", _on_stats_button_pressed],
		["toggle_ranging", _on_ranging_button_pressed],
		["toggle_help", _on_help_button_pressed],
		["toggle_notepad", _on_info_button_pressed],
		["toggle_options", _on_options_pressed],
		["toggle_mail", func() -> void: extension_windows.call("toggle_mail")]]
	for action_and_handler: Array in window_actions:
		if event.is_action_pressed(str(action_and_handler[0])):
			(action_and_handler[1] as Callable).call()
			get_viewport().set_input_as_handled()
			return
	if event.is_action_pressed("chat_focus"):
		_show_chat_input()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("cancel"):
		if popup_panel.visible:
			# The popup is modal: it takes the cancel before anything under it.
			_on_popup_dismiss_pressed()
		elif extension_windows != null and extension_windows.close_top():
			pass
		elif player_info_panel != null and player_info_panel.is_open():
			player_info_panel.close()
		elif spells_window != null and bool(spells_window.call("is_open")):
			spells_window.call("close")
		elif emotes_window != null and bool(emotes_window.call("is_open")):
			emotes_window.call("close")
		elif ranging_window != null and bool(ranging_window.call("is_open")):
			ranging_window.call("close")
		elif sigil_window != null and sigil_window.is_open():
			sigil_window.close()
		elif settings_window != null and settings_window.is_open():
			settings_window.close()
		elif reference_window != null and reference_window.is_open():
			reference_window.close()
		elif _carried_slot >= 0:
			_cancel_carry()
		elif chat_input.has_focus():
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
			or trade_panel.visible or storage_panel.visible
			or manufacturing_panel.visible):
		return
	if event is InputEventMouseButton:
		var mouse_button: InputEventMouseButton = event as InputEventMouseButton
		if mouse_button.pressed and actor_hud_menu.visible:
			actor_hud_menu.hide()
		if mouse_button.button_index == MOUSE_BUTTON_RIGHT:
			if mouse_button.pressed:
				_right_mouse_down = true
				_right_mouse_dragged = false
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
	if _banner_option("menu_disabled"):
		return
	actor_hud_menu.show()
	actor_hud_menu.reset_size()
	var menu_size: Vector2 = actor_hud_menu.size
	var boundary: Vector2 = game_view.size - menu_size - Vector2(8.0, 8.0)
	actor_hud_menu.position = Vector2(
		clampf(position.x, 8.0, maxf(8.0, boundary.x)),
		clampf(position.y, 8.0, maxf(8.0, boundary.y)))
	actor_hud_menu.move_to_front()

func _configure_banner_menu() -> void:
	for key: String in BANNER_OPTION_NODES:
		var box: CheckBox = get_node("%" + str(BANNER_OPTION_NODES[key])) as CheckBox
		box.set_pressed_no_signal(bool(BANNER_OPTION_DEFAULTS[key]))
		box.toggled.connect(_on_banner_option_toggled)
		_banner_option_boxes[key] = box

func _banner_option(key: String) -> bool:
	var box_value: Variant = _banner_option_boxes.get(key)
	if box_value is CheckBox:
		return (box_value as CheckBox).button_pressed
	return bool(BANNER_OPTION_DEFAULTS.get(key, false))

func _on_banner_option_toggled(_enabled: bool) -> void:
	_apply_banner_options()
	# The R indicator letter reads the ranging-lock switch, so it follows the
	# toggle rather than waiting for the next unrelated state change.
	_sync_hud_indicators()
	_save_hud_settings()

## Kept so the HUD settings window can undo the menu's own "Disable This Menu"
## entry, which would otherwise lock the menu away for good.
func _on_banner_menu_enabled_toggled(pressed: bool) -> void:
	var box: CheckBox = _banner_option_boxes["menu_disabled"] as CheckBox
	box.set_pressed_no_signal(not pressed)
	_apply_banner_options()
	_save_hud_settings()

## Called for every switch on the banner menu because EL's options are not
## independent of one another: a row disappears once both its bar and its
## numbers are off, the panel is only as tall as the rows left standing, and
## instance mode overrides what other actors show regardless of "Show Names".
func _apply_banner_options() -> void:
	banner_menu_enabled.set_pressed_no_signal(not _banner_option("menu_disabled"))
	if _banner_option("menu_disabled"):
		actor_hud_menu.hide()
	overhead_player_name.visible = _banner_option("show_names")
	for row_spec: Array in BANNER_ROWS:
		var row: HBoxContainer = _banner_row(str(row_spec[0]))
		var show_bar: bool = _banner_option(str(row_spec[1]))
		var show_numbers: bool = _banner_option(str(row_spec[2]))
		(row.get_node("Bar") as ProgressBar).visible = show_bar
		(row.get_node("Number") as Label).visible = show_numbers
		row.visible = show_bar or show_numbers
	_apply_banner_background()
	for id: Variant in actor_nodes:
		var node_value: Variant = actor_nodes[id]
		if node_value is ReplicatedActor3D and is_instance_valid(node_value as ReplicatedActor3D):
			var actor: ReplicatedActor3D = node_value as ReplicatedActor3D
			actor.set_nameplate_visible(_nameplate_visible_for(int(id)))
			if not _banner_option("speech_bubbles"):
				actor.clear_speech_bubble()
	_layout_actor_resource_overlay()
	_update_actor_resource_overlay()

## EL draws a flat black rectangle behind the banner when the alpha background
## is on (actors.c) and nothing at all when it is off, so the switch swaps the
## panel style rather than hiding the panel.
func _apply_banner_background() -> void:
	if _banner_background_style == null:
		var style := StyleBoxFlat.new()
		style.bg_color = Color(0.0, 0.0, 0.0, 0.6)
		style.set_content_margin_all(2.0)
		style.content_margin_left = 6.0
		style.content_margin_right = 6.0
		_banner_background_style = style
	if _banner_option("banner_background"):
		actor_resource_overlay.add_theme_stylebox_override(
			"panel", _banner_background_style)
		return
	var empty := StyleBoxEmpty.new()
	empty.set_content_margin_all(2.0)
	empty.content_margin_left = 6.0
	empty.content_margin_right = 6.0
	actor_resource_overlay.add_theme_stylebox_override("panel", empty)

## Local chat arrives already formatted as "Speaker: what they said", which is
## the same shape EL parses in text.c before handing the remainder to the
## speaker's overtext. Anything without a name that matches a visible actor is
## left in the chat log alone.
func _capture_speech_bubble_from_chat() -> void:
	if not _banner_option("speech_bubbles") or AppState.chat_lines.is_empty():
		return
	var line: Dictionary = AppState.chat_lines.back() as Dictionary
	if int(line.get("channel", -1)) != 0:
		return
	var text: String = str(line.get("text", ""))
	var separator: int = text.find(": ")
	if separator <= 0:
		return
	var speaker: String = text.substr(0, separator).strip_edges()
	var spoken: String = text.substr(separator + 2).strip_edges()
	if spoken.is_empty():
		return
	for id: Variant in AppState.actors:
		var dto: Dictionary = AppState.actors[id] as Dictionary
		if str(dto.get("name", "")) != speaker:
			continue
		var node_value: Variant = actor_nodes.get(id)
		if node_value is ReplicatedActor3D and is_instance_valid(
				node_value as ReplicatedActor3D):
			(node_value as ReplicatedActor3D).show_speech_bubble(
				spoken, SPEECH_BUBBLE_MSEC)
		return

## Eternal Lands drops the click rather than walking you out of position when
## either lock applies: Sit Lock while you are actually sitting, with Ctrl as
## the deliberate override, and Ranging Lock while a bow is in hand
## (gamewin.c, CURSOR_WALK and CURSOR_ATTACK).
func _movement_locked(ctrl_pressed: bool) -> bool:
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	if (_banner_option("sit_lock") and not ctrl_pressed
			and bool(local_actor.get("sitting", false))):
		return true
	return _banner_option("ranging_lock") and _range_weapon_equipped()

func _range_weapon_equipped() -> bool:
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var appearance: Dictionary = local_actor.get("appearance", {}) as Dictionary
	var weapon: int = int(appearance.get("weapon", 0))
	return weapon >= RANGE_WEAPON_FIRST and weapon <= RANGE_WEAPON_LAST

func _banner_row(row_name: String) -> HBoxContainer:
	return actor_resource_overlay.get_node("Rows/" + row_name) as HBoxContainer

## Every visible actor except you, and only while instance mode is off - EL
## blanks other actors' banners in instance mode so a crowded fight stays
## readable (im_other_player_view_names and friends all default off).
func _nameplate_visible_for(actor_id: int) -> bool:
	if actor_id == AppState.local_actor_id:
		return false
	if not _nameplates_enabled:
		return false
	if _banner_option("instance_mode"):
		return false
	return _banner_option("show_names")

## Eternal Lands makes every bar as long as the widest number string beside it
## so the rows line up, then sizes the banner to whatever is left switched on.
## Godot keeps a container at whatever size it was last given, so the explicit
## reset_size() is what actually shrinks the box when a row goes away.
func _layout_actor_resource_overlay() -> void:
	var widest := BANNER_BAR_MIN_WIDTH
	for row_spec: Array in BANNER_ROWS:
		var row: HBoxContainer = _banner_row(str(row_spec[0]))
		if not row.visible:
			continue
		var number: Label = row.get_node("Number") as Label
		widest = maxf(widest, number.get_theme_font("font").get_string_size(
			number.text, HORIZONTAL_ALIGNMENT_LEFT, -1.0,
			number.get_theme_font_size("font_size")).x)
	var bar_width: float = ceilf(widest)
	for row_spec: Array in BANNER_ROWS:
		var row: HBoxContainer = _banner_row(str(row_spec[0]))
		var bar: ProgressBar = row.get_node("Bar") as ProgressBar
		var number: Label = row.get_node("Number") as Label
		bar.custom_minimum_size.x = bar_width
		number.custom_minimum_size.x = bar_width
	actor_resource_overlay.reset_size()

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
	if event is InputEventMouseButton:
		var wheel: InputEventMouseButton = event as InputEventMouseButton
		if wheel.pressed and (wheel.button_index == MOUSE_BUTTON_WHEEL_UP
				or wheel.button_index == MOUSE_BUTTON_WHEEL_DOWN):
			_zoom_minimap(wheel.button_index == MOUSE_BUTTON_WHEEL_UP)
			minimap.accept_event()
			return
	_handle_map_gui_input(event, minimap, map_viewport, map_camera, "minimap")

## The scroll wheel over the minimap changes how much ground it frames. The
## camera is orthographic, so its size is the width in metres directly.
func _zoom_minimap(closer: bool) -> void:
	var previous: float = _minimap_zoom
	var step: float = 1.0 / MINIMAP_ZOOM_STEP if closer else MINIMAP_ZOOM_STEP
	_minimap_zoom = clampf(_minimap_zoom * step,
		MINIMAP_ZOOM_MIN, MINIMAP_ZOOM_MAX)
	if is_equal_approx(previous, _minimap_zoom):
		return
	_apply_minimap_zoom()
	_save_hud_settings()

func _apply_minimap_zoom() -> void:
	map_camera.size = _minimap_zoom
	# The minimap render is throttled, so a zoom would otherwise not be seen
	# until the next scheduled frame.
	if minimap_frame.visible:
		map_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE

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
			or storage_panel.visible
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
		_clear_local_turn_prediction()
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
	if _carried_slot >= 0:
		_drop_carry()
		return
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
			if _movement_locked(event.ctrl_pressed):
				return
			_send_attack(picked_actor_id)
			return
		if _interaction_mode == "trade" and _is_tradeable_player(
				picked_actor_id, selected_dto):
			var trade_error: Error = Network.trade_with(picked_actor_id)
			if trade_error != OK:
				push_warning("TRADE_WITH failed: " + error_string(trade_error))
			return
		if event.alt_pressed and _is_attackable_actor(picked_actor_id, selected_dto):
			if _movement_locked(event.ctrl_pressed):
				return
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
	var picked_object: MapObject3D = _pick_map_object(viewport_position)
	if picked_object != null:
		_activate_map_object(picked_object, event.alt_pressed)
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
		if _movement_locked(event.ctrl_pressed):
			return
		var tile: Vector2i = adapter.godot_to_server(point as Vector3)
		print_debug("world_input godot=", point, " server_tile=", tile,
			" command=", "RUN_TO" if event.shift_pressed else "MOVE_TO")
		_clear_keyboard_movement_tracking()
		_clear_local_turn_prediction()
		var move_error: Error = Network.move_to(tile, event.shift_pressed)
		if move_error != OK:
			push_warning("MOVE_TO failed: " + error_string(move_error))

func _on_state_changed(path: StringName) -> void:
	# Protocol diagnostics are the one path that must work before login: a
	# decode failure during the handshake is exactly what the panel exists to
	# show, and the session is not authenticated when it happens.
	if path == &"protocol_unknown" or path == &"protocol_errors":
		_sync_diagnostics()
		return
	if not AppState.authenticated:
		return
	match path:
		&"map":
			_load_server_map()
			_sync_world()
			_update_console_location()
			# Markers survive a map change; which of them belong here does not.
			_sync_map_markers()
		&"actors", &"local_actor":
			# A busy map emits this once per actor packet. Rebuilding the whole
			# actor presentation for each of them repeated the same work many
			# times inside a single frame; coalescing collapses a burst into one
			# pass without delaying anything past the frame it arrived in.
			_queue_world_sync()
		&"chat":
			_capture_speech_bubble_from_chat()
			_count_unseen_private_messages()
			_sync_chat()
			_sync_console()
			_reveal_chat_messages()
		&"almanac":
			_sync_hud_indicators()
		&"channels":
			_sync_channel_tabs()
		&"invasion_assistant":
			var kind := str(AppState.invasion_assistant.get("last_kind", ""))
			var update: Dictionary = AppState.invasion_assistant.get(kind, {}) as Dictionary
			if not update.is_empty():
				invasion_assistant_window.apply_update(update)
		&"clock":
			_update_legacy_clock_and_compass()
			_apply_day_night()
			_sync_diagnostics()
		&"perks":
			_sync_stats()
		&"counters":
			_sync_counter_categories()
			_sync_counters()
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
		&"world_objects":
			_sync_placed_objects()
		&"weather":
			_sync_weather()
		&"fires":
			_sync_fires()
		&"item_detail":
			# The description is written whichever tool asked for it; only the
			# window is withheld. See `_describe_slot`.
			var short_line: String = _short_item_line()
			if not short_line.is_empty():
				inventory_description.text = short_line
		&"inventory_cooldowns":
			_sync_quick_slots()
		&"spells":
			_sync_spells()
		&"selection":
			_sync_selection()
		&"npc_dialogue":
			_sync_dialogue()
		&"popup":
			_sync_popup()
		&"trade":
			_sync_trade()
		&"storage":
			_sync_storage()
		&"map_objects":
			_sync_map_objects()
			_snap_all_map_objects_to_surface.call_deferred()
		&"map_markers":
			_sync_map_markers()
		&"spell_power":
			_sync_spells()
		&"harvest":
			_sync_harvest_indicator()
		&"reading":
			_sync_reading()
		&"ground_bags":
			_sync_ground_bags()
		&"ground_bag":
			_sync_ground_bag()
		&"knowledge":
			_sync_knowledge()
			_sync_manufacturing()
			_sync_reading()

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
	# The overlay was handed the placeholder adapter _ready() builds before any
	# map exists - one metre per tile from a (0, 0) origin - and never heard
	# about the real one, so every marker projected as though its server tile
	# were a position in metres. The plaza, then at tile (768, 768) on the
	# 1536-tile grid Four Gates used before it went to a metre a tile, drew
	# in the far corner
	# of the map instead of the middle of it.
	map_marker_overlay.configure(full_map_camera, adapter, full_map_viewport.size)
	for raw_actor_node: Variant in actor_nodes.values():
		if is_instance_valid(raw_actor_node):
			(raw_actor_node as Node).queue_free()
	actor_nodes.clear()
	for bag_node_value: Variant in ground_bag_nodes.values():
		if is_instance_valid(bag_node_value):
			(bag_node_value as Node).queue_free()
	ground_bag_nodes.clear()
	for object_node_value: Variant in map_object_nodes.values():
		if is_instance_valid(object_node_value):
			(object_node_value as Node).queue_free()
	map_object_nodes.clear()
	_ungrounded_map_objects.clear()
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
	_apply_day_night()
	_bind_ambient_audio(manifest)
	_populate_ambient_life(manifest)
	_current_map_display_name = str(
		manifest.data.get("asset", {}).get("name", manifest.asset_id()))
	map_label.text = "Map: " + _current_map_display_name
	map_title.text = _current_map_display_name.to_upper()
	current_map_button.text = "Current: " + _current_map_display_name
	_configure_interior_cutaway(manifest)
	_configure_occluder_fade(manifest)
	_configure_full_map(manifest)
	_request_map_redraw()
	_sync_world()
	_sync_ground_bags()
	_sync_map_objects()
	_snap_all_actors_to_surface.call_deferred()
	_snap_all_ground_bags_to_surface.call_deferred()
	_snap_all_map_objects_to_surface.call_deferred()

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

## Moves the environment to the hour the server is keeping. The manifest is
## the noon reference and the daylight curve is the server's own, so the sky
## the player sees and the visibility the server acts on cannot drift apart.
##
## Runs on every clock packet and on a slow timer between them, because the
## server states a whole minute at a time and one minute of real time is a
## visible jump if nothing carries it forward.
## Tells the console where the player is, so `#mark` has a tile to record.
func _update_console_location() -> void:
	console_commands.current_map = EloriaProtocol.map_id_from_reference(
		AppState.current_map)
	var actor: Variant = AppState.actors.get(AppState.local_actor_id)
	console_commands.current_tile = (Vector2i(
		int((actor as Dictionary).get("x", 0)),
		int((actor as Dictionary).get("y", 0)))
		if actor is Dictionary else Vector2i(-1, -1))

func _apply_day_night() -> void:
	if world_loader.manifest == null:
		return
	_day_night_active = DayNightBinder.apply(world_loader.manifest,
		world_environment, world_sun, AppState.continuous_game_minute())
	_sync_map_environment()

## The maps are navigation aids, not scenery. Rendered through the world's own
## environment they went as dark as the world did, and a minimap nobody can
## read at night is a minimap that only works half the time. Both map cameras
## get their own copy of the environment with a floor under the ambient, so
## night still reads as night on them but the streets stay legible.
func _sync_map_environment() -> void:
	var source: Environment = world_environment.environment
	if source == null:
		for uncovered: Camera3D in [map_camera, full_map_camera]:
			uncovered.environment = null
		return
	if _map_environment == null or _map_environment.sky != source.sky:
		_map_environment = source.duplicate() as Environment
	_map_environment.background_mode = source.background_mode
	_map_environment.sky = source.sky
	_map_environment.ambient_light_source = source.ambient_light_source
	_map_environment.ambient_light_color = source.ambient_light_color
	_map_environment.ambient_light_energy = maxf(
		source.ambient_light_energy, MAP_MINIMUM_AMBIENT)
	_map_environment.fog_enabled = false
	for lit: Camera3D in [map_camera, full_map_camera]:
		lit.environment = _map_environment

## The ambience a package declares for itself. Four Gates has named a civic
## murmur and its waterfalls since it was authored and nothing played them.
func _bind_ambient_audio(manifest: WorldManifest) -> void:
	if is_instance_valid(map_ambience_root):
		map_ambience_root.queue_free()
	map_ambience_root = null
	if not bool(audio_director.enabled):
		return
	var root_node := Node3D.new()
	root_node.name = "MapAmbience"
	world_root.add_child(root_node)
	var bound: int = AmbientAudioBinder.apply(manifest, root_node,
		world_loader.world_root, PackedStringArray(
			audio_director.call("sound_names") as Array))
	if bound == 0:
		root_node.queue_free()
		return
	map_ambience_root = root_node
	print_debug("ambient_audio map=", AppState.current_map, " bound=", bound)

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
	for id: Variant in actor_nodes.keys():
		if AppState.actors.has(id):
			continue
		# An entry can already be dangling: anything that frees an actor node
		# without going through this map leaves the dictionary holding a freed
		# object, and calling queue_free() on that crashes the engine rather
		# than raising. Guarding here is what makes a map change safe while
		# actors are still being torn down.
		# Casting first is not safe: `as Node` on a freed object raises and
		# aborts the whole function, so the entry would never be erased.
		var stale_actor: Variant = actor_nodes[id]
		if is_instance_valid(stale_actor):
			(stale_actor as Node).queue_free()
		actor_nodes.erase(id)
		_actor_surface_samples.erase(id)
	for id in AppState.actors:
		var dto: Dictionary = _presentation_dto(AppState.actors[id])
		if actor_nodes.has(id):
			var existing_actor: ReplicatedActor3D = actor_nodes[id] as ReplicatedActor3D
			existing_actor.apply_server_state(dto, adapter)
			existing_actor.apply_vitals(int(dto.get("health", 0)),
				int(dto.get("max_health", 0)))
			existing_actor.set_nameplate_visible(_nameplate_visible_for(int(id)))
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
		node.set_nameplate_visible(_nameplate_visible_for(int(id)))
		_place_actor_on_surface(node, true)
	actor_label.text = "Actors: %d" % AppState.actors.size()
	if AppState.local_actor_id >= 0 and actor_nodes.has(AppState.local_actor_id):
		_update_local_actor_follow()
		var local_dto: Dictionary = AppState.actors[AppState.local_actor_id]
		overhead_player_name.text = str(local_dto.get("name", "Player"))
		# You get no nameplate of your own - _nameplate_visible_for skips the
		# local actor - so this banner is the only place your own name colour
		# can show. Demigod mode is the one that turns it green.
		overhead_player_name.add_theme_color_override("font_color",
			EloriaProtocol.el_text_colour(int(local_dto.get("name_colour", 0))))
		var current_health := int(local_dto.get("health", 0))
		var maximum_health := maxi(1, int(local_dto.get("max_health", 1)))
		if AppState.stats.is_empty():
			_set_meter(health_bar, health_text, current_health, maximum_health, "Health")
			_set_meter(health_bottom, health_bottom_text,
				current_health, maximum_health, "Health")
			_set_overhead_meter(overhead_health_row, current_health,
				maximum_health, "health")
			_layout_actor_resource_overlay()

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
			if is_instance_valid(stale_value):
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
	# Both windows stay up together so items can move either way, and the world
	# underneath stays visible and clickable while they are open.
	if not inventory_panel.visible:
		inventory_panel.show()
		_sync_hud_button_states(true)
	_fill_ground_bag_grid(AppState.ground_bag.get("items", {}) as Dictionary)
	_sync_ground_bag_actions()
	_clamp_ground_bag_window_to_viewport()
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
	var slot: int = selected_inventory_slot
	var droppable: bool = (slot >= 0 and slot < 36
		and AppState.inventory.get(slot) is Dictionary)
	ground_bag_drop_button.disabled = not droppable
	if droppable:
		var item: Dictionary = AppState.inventory.get(slot) as Dictionary
		ground_bag_drop_button.tooltip_text = ("Drop %d of the %d in inventory slot %d"
			% [mini(int(item.get("quantity", 1)), _selected_quantity()),
			int(item.get("quantity", 1)), slot + 1])
	else:
		ground_bag_drop_button.tooltip_text = ("Select an item in the inventory window"
			+ " to drop it here")

## Asks the server what the selected ground item is. The bag packet carries an
## image id and a quantity, so the description can only come from the server.
func _on_ground_bag_look_pressed(index: int) -> void:
	var slot: int = _ground_bag_slot_position(index)
	if slot < 0:
		return
	var error: Error = Network.look_at_ground_item(slot)
	if error != OK:
		push_warning("LOOK_AT_GROUND_ITEM failed: " + error_string(error))

## The reading window. The server models a book as research rather than as
## pages of text: using a book from the backpack consumes it and starts a
## timer, pages tick down, and the knowledge bit is set on completion. There is
## no page content on the wire to turn through, so this reports the thing that
## actually exists - which book, how far through, and what it unlocks - instead
## of a page-turning window with nothing behind it.
func _sync_reading() -> void:
	if reading_panel == null:
		return
	var active: bool = bool(AppState.reading.get("active", false))
	var index: int = int(AppState.reading.get("index", -1))
	if not active:
		if _reading_completed_index >= 0:
			_present_completed_reading()
			return
		reading_panel.hide()
		return
	_reading_completed_index = index
	_reading_hidden = _reading_hidden and index == _reading_shown_index
	_reading_shown_index = index
	if _reading_hidden:
		reading_panel.hide()
		return
	var total: int = maxi(1, int(AppState.reading.get("pages_total", 1)))
	var read: int = clampi(int(AppState.reading.get("pages_read", 0)), 0, total)
	reading_title.text = "Reading %s" % _knowledge_title(index)
	reading_progress.max_value = total
	reading_progress.value = read
	reading_detail.text = ("%d of %d pages read (%d%%)
"
		+ "Reading finishes on its own; food keeps it going.") % [
		read, total, roundi(100.0 * float(read) / float(total))]
	reading_panel.show()

## Reading finished. The knowledge bit arrives as its own packet, so this shows
## what was actually gained rather than assuming completion implies it.
func _present_completed_reading() -> void:
	var index: int = _reading_completed_index
	_reading_completed_index = -1
	_reading_shown_index = -1
	_reading_hidden = false
	if not AppState.known_knowledge.has(index):
		reading_panel.hide()
		return
	reading_title.text = "Finished %s" % _knowledge_title(index)
	reading_progress.max_value = 1
	reading_progress.value = 1
	reading_detail.text = ("[color=#8fdc8f]Knowledge gained.[/color]
"
		+ "Recipes that needed it are now available.")
	reading_panel.show()

func _knowledge_title(index: int) -> String:
	if index >= 0 and index < knowledge_catalog.size():
		return knowledge_catalog[index]
	return "knowledge #%d" % index

func _on_reading_close_pressed() -> void:
	# Hiding the window does not stop the reading: the server owns that, and
	# there is no command to interrupt research.
	_reading_hidden = true
	reading_panel.hide()

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

## Anything the camera has to look through to see the player is blended towards
## glass. Indexed against the imported world rather than `world_root`, so actors,
## ground bags and the camera rig are never candidates.
func _configure_occluder_fade(manifest: WorldManifest) -> void:
	var count: int = occluder_fade.configure(manifest, world_loader.world_root)
	occluder_fade.set_enabled(_show_through_obstacles)
	print_debug("occluder_fade stage=indexed map=", AppState.current_map,
		" meshes=", count)

## The probe needs both ends of the sight line, and the local actor is absent
## between a map change and the first actor list, so a frame without one simply
## lets whatever is faded blend back to solid.
func _update_occluder_fade(delta: float) -> void:
	var target_value: Variant = actor_nodes.get(AppState.local_actor_id)
	var target: Node3D = target_value as Node3D if target_value is Node3D else null
	occluder_fade.update(delta, gameplay_camera, target)

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
		_show_through_obstacles = bool(config.get_value(
			"hud", "show_through_obstacles", true))
		_minimap_orientation = str(config.get_value(
			"hud", "minimap_orientation", "north_up"))
		if _minimap_orientation not in ["north_up", "player_up", "viewport_up"]:
			_minimap_orientation = "north_up"
		_minimap_zoom = clampf(float(config.get_value(
			"hud", "minimap_zoom", MINIMAP_ZOOM_DEFAULT)),
			MINIMAP_ZOOM_MIN, MINIMAP_ZOOM_MAX)
		extension_windows.call("set_combat_hud_enabled",
			bool(config.get_value("hud", "combat_hud", true)))
		extension_windows.call("set_combat_hud_pinned",
			bool(config.get_value("hud", "combat_hud_pinned", false)))
		var combat_hud_where: Variant = config.get_value(
			"hud", "combat_hud_position", null)
		if combat_hud_where is Vector2:
			extension_windows.call("set_combat_hud_position",
				combat_hud_where as Vector2)
		var position_value: Variant = config.get_value(
			"hud", "minimap_position", Vector2(16.0, 42.0))
		if position_value is Vector2:
			minimap_frame.position = position_value as Vector2
		# The minimap's position and scale persisted but its visibility did
		# not, so every session started with the map hidden and nothing but
		# Alt+M would show it again.
		_minimap_visible = bool(config.get_value("hud", "minimap_visible", false))
		for option_key: String in _hud_element_options:
			_hud_element_options[option_key] = bool(config.get_value(
				"hud", option_key, _hud_element_options[option_key]))
		_hud_timer_stopwatch = bool(config.get_value("hud", "timer_stopwatch", false))
		_hud_timer_start_seconds = clampi(int(config.get_value(
			"hud", "timer_start_seconds", 90)), 0, 9 * 60 + 59)
		_hud_timer_seconds = 0 if _hud_timer_stopwatch else _hud_timer_start_seconds
		_ground_bag_scale = clampf(float(config.get_value(
			"ground_bag", "window_scale", 1.0)),
			INVENTORY_MIN_SCALE, INVENTORY_MAX_SCALE)
		_inventory_scale = clampf(float(config.get_value(
			"inventory", "window_scale", 1.0)),
			INVENTORY_MIN_SCALE, INVENTORY_MAX_SCALE)
		var inventory_position_value: Variant = config.get_value(
			"inventory", "window_position", inventory_panel.position)
		if inventory_position_value is Vector2:
			inventory_panel.position = inventory_position_value as Vector2
		_equipment_side = str(config.get_value("inventory", "equipment_side", "left"))
		var bag_position_value: Variant = config.get_value(
			"inventory", "bag_window_position", ground_bag_panel.position)
		if bag_position_value is Vector2:
			ground_bag_panel.position = bag_position_value as Vector2
		var quantities_value: Variant = config.get_value("inventory", "quantities", [])
		if quantities_value is Array 				and (quantities_value as Array).size() == _inventory_quantities.size():
			for index: int in range(_inventory_quantities.size()):
				_inventory_quantities[index] = clampi(
					int((quantities_value as Array)[index]), 1, INVENTORY_QUANTITY_MAX)
		_selected_quantity_box = clampi(int(config.get_value(
			"inventory", "selected_quantity", 0)), 0, _inventory_quantities.size() - 1)
		var bulk_value: Variant = config.get_value("inventory", "bulk_exclusions", {})
		if bulk_value is Dictionary:
			for kind: String in ["store", "drop"]:
				var options_value: Variant = (bulk_value as Dictionary).get(kind)
				if options_value is Array and (options_value as Array).size() == 4:
					_bulk_exclusions[kind] = (options_value as Array).duplicate()
		var lists_value: Variant = config.get_value("inventory", "item_lists", {})
		if lists_value is Dictionary:
			_item_lists = (lists_value as Dictionary).duplicate(true)
		_player_notes = str(config.get_value("notes", "text", ""))
		var stored_bookmarks: Variant = config.get_value(
			"encyclopedia", "bookmarks", [])
		if stored_bookmarks is Array:
			_encyclopedia_bookmarks = (stored_bookmarks as Array).duplicate(true)
		_shadows_enabled = bool(config.get_value("graphics", "shadows", true))
		_effects_enabled = bool(config.get_value("graphics", "particles", true))
		_nameplates_enabled = bool(
			config.get_value("graphics", "nameplates", true))
		camera_rig.rotation_sensitivity = float(config.get_value(
			"camera", "rotation_sensitivity", camera_rig.rotation_sensitivity))
		camera_rig.pan_sensitivity = float(config.get_value(
			"camera", "pan_sensitivity", camera_rig.pan_sensitivity))
		_camera_follows_player = bool(
			config.get_value("camera", "follow_player", true))
		var stored_bindings: Variant = config.get_value("controls", "bindings", {})
		if stored_bindings is Dictionary:
			settings_window.call("restore_bindings", stored_bindings)
		var stored_marks: Variant = config.get_value("console", "marks", [])
		if stored_marks is Array:
			for raw_mark: Variant in stored_marks as Array:
				if raw_mark is Dictionary:
					console_commands.marks.append(raw_mark as Dictionary)
		for key_and_list: Array in [["ignored", console_commands.ignored],
				["filters", console_commands.filters]]:
			var stored: Variant = config.get_value("console",
				str(key_and_list[0]), [])
			if stored is Array:
				for entry: Variant in stored as Array:
					(key_and_list[1] as Array[String]).append(str(entry))
		var stored_aliases: Variant = config.get_value("console", "aliases", {})
		if stored_aliases is Dictionary:
			console_commands.aliases = (stored_aliases as Dictionary).duplicate()
		audio_director.enabled = bool(config.get_value("audio", "enabled", true))
		audio_director.volume_linear = clampf(float(config.get_value(
			"audio", "volume", 0.7)), 0.0, 1.0)
		for banner_key: String in BANNER_OPTION_NODES:
			var box: CheckBox = _banner_option_boxes[banner_key] as CheckBox
			box.set_pressed_no_signal(bool(config.get_value(
				"banner", banner_key, BANNER_OPTION_DEFAULTS[banner_key])))
	reference_window.call("configure", console_commands,
		settings_window.get("BINDABLE"), _player_notes, _encyclopedia_bookmarks)
	sound_enabled.set_pressed_no_signal(bool(audio_director.enabled))
	sound_volume.set_value_no_signal(float(audio_director.volume_linear))
	sound_volume_value.text = "%d%%" % roundi(
		float(audio_director.volume_linear) * 100.0)
	minimap_size.set_value_no_signal(_minimap_scale)
	ui_scale_slider.set_value_no_signal(_ui_scale)
	show_through_obstacles.set_pressed_no_signal(_show_through_obstacles)
	settings_window.call("restore_toggle", "combat_hud",
		bool(extension_windows.get("combat_hud_enabled")))
	for option_key: String in _hud_element_options:
		settings_window.call("restore_toggle", option_key,
			bool(_hud_element_options[option_key]))
	_apply_ui_scale()
	_apply_minimap_scale()
	_apply_minimap_zoom()
	_apply_inventory_scale(_inventory_scale)
	_apply_ground_bag_scale(_ground_bag_scale)
	_apply_banner_options()

func _on_ui_scale_changed(value: float) -> void:
	_ui_scale = clampf(value, UI_SCALE_MIN, UI_SCALE_MAX)
	_apply_ui_scale()
	_save_hud_settings()

## The window already scales the HUD with its size; this factor rides on top of
## that so players can trade HUD size for screen space. It only moves the canvas
## the HUD is laid out in - the world render target is resized to match in
## _on_window_size_changed(), so the world always renders at window resolution.
func _on_show_through_obstacles_toggled(pressed: bool) -> void:
	_show_through_obstacles = pressed
	_apply_show_through_obstacles()
	_save_hud_settings()

func _toggle_show_through_obstacles() -> void:
	show_through_obstacles.button_pressed = not show_through_obstacles.button_pressed

## The local player's sight line only. Fading every obstacle in front of every
## actor would strip the map bare and would be a wallhack rather than a
## convenience, so the probe is deliberately never aimed at the rest of
## `actor_nodes`.
func _apply_show_through_obstacles() -> void:
	occluder_fade.set_enabled(_show_through_obstacles)

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

## Sound is the player's own choice about their own machine, so it is kept in
## the same settings file as the rest of the HUD preferences.
func _on_sound_enabled_toggled(pressed: bool) -> void:
	audio_director.enabled = pressed
	if is_instance_valid(map_ambience_root):
		# Ambience is a scene node rather than a voice on the director, so it
		# has to be silenced here as well.
		map_ambience_root.queue_free()
		map_ambience_root = null
	if pressed:
		audio_director.play("ui_click")
		if world_loader.manifest != null:
			_bind_ambient_audio(world_loader.manifest)
	_save_hud_settings()

func _on_sound_volume_changed(value: float) -> void:
	audio_director.volume_linear = value
	sound_volume_value.text = "%d%%" % roundi(value * 100.0)
	_save_hud_settings()

func _save_hud_settings() -> void:
	var config: ConfigFile = ConfigFile.new()
	config.load(SETTINGS_PATH)
	config.set_value("notes", "text", _player_notes)
	config.set_value("encyclopedia", "bookmarks", _encyclopedia_bookmarks)
	config.set_value("graphics", "shadows", _shadows_enabled)
	config.set_value("graphics", "particles", _effects_enabled)
	config.set_value("graphics", "nameplates", _nameplates_enabled)
	config.set_value("hud", "combat_hud",
		bool(extension_windows.get("combat_hud_enabled")))
	config.set_value("hud", "combat_hud_pinned",
		bool(extension_windows.get("combat_hud_pinned")))
	config.set_value("hud", "combat_hud_position",
		extension_windows.call("combat_hud_position"))
	config.set_value("camera", "rotation_sensitivity",
		float(camera_rig.rotation_sensitivity))
	config.set_value("camera", "pan_sensitivity",
		float(camera_rig.pan_sensitivity))
	config.set_value("camera", "follow_player", _camera_follows_player)
	config.set_value("controls", "bindings",
		settings_window.call("stored_bindings"))
	config.set_value("console", "marks", console_commands.marks)
	config.set_value("console", "ignored", console_commands.ignored)
	config.set_value("console", "filters", console_commands.filters)
	config.set_value("console", "aliases", console_commands.aliases)
	config.set_value("audio", "enabled", bool(audio_director.enabled))
	config.set_value("audio", "volume", float(audio_director.volume_linear))
	config.set_value("hud", "minimap_scale", _minimap_scale)
	config.set_value("hud", "ui_scale", _ui_scale)
	config.set_value("hud", "show_through_obstacles", _show_through_obstacles)
	config.set_value("hud", "minimap_orientation", _minimap_orientation)
	config.set_value("hud", "minimap_zoom", _minimap_zoom)
	config.set_value("hud", "minimap_position", minimap_frame.position)
	config.set_value("hud", "minimap_visible", _minimap_visible)
	for option_key: String in _hud_element_options:
		config.set_value("hud", option_key, bool(_hud_element_options[option_key]))
	config.set_value("hud", "timer_stopwatch", _hud_timer_stopwatch)
	config.set_value("hud", "timer_start_seconds", _hud_timer_start_seconds)
	config.set_value("inventory", "window_scale", _inventory_scale)
	config.set_value("ground_bag", "window_scale", _ground_bag_scale)
	config.set_value("inventory", "window_position", inventory_panel.position)
	config.set_value("inventory", "equipment_side", _equipment_side)
	config.set_value("inventory", "bag_window_position", ground_bag_panel.position)
	config.set_value("inventory", "quantities", _inventory_quantities)
	config.set_value("inventory", "selected_quantity", _selected_quantity_box)
	config.set_value("inventory", "bulk_exclusions", _bulk_exclusions)
	config.set_value("inventory", "item_lists", _item_lists)
	for banner_key: String in BANNER_OPTION_NODES:
		config.set_value("banner", banner_key, _banner_option(banner_key))
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

func _on_ground_bag_header_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index != MOUSE_BUTTON_LEFT:
			return
		_ground_bag_dragging = mouse.pressed
		if mouse.pressed:
			ground_bag_panel.move_to_front()
			_ground_bag_drag_offset = (get_viewport().get_mouse_position()
				- ground_bag_panel.global_position)
		else:
			_save_hud_settings()
		ground_bag_header.accept_event()
	elif event is InputEventMouseMotion and _ground_bag_dragging:
		ground_bag_panel.global_position = (get_viewport().get_mouse_position()
			- _ground_bag_drag_offset)
		_clamp_ground_bag_window_to_viewport()
		ground_bag_header.accept_event()

func _clamp_ground_bag_window_to_viewport() -> void:
	if game_view.size.x <= 0.0 or game_view.size.y <= 0.0:
		return
	var game_origin: Vector2 = game_view.global_position
	var local_position: Vector2 = ground_bag_panel.global_position - game_origin
	var maximum: Vector2 = (game_view.size
		- ground_bag_panel.size * _ground_bag_scale
		- Vector2(8.0, 8.0)).max(Vector2(8.0, 8.0))
	ground_bag_panel.global_position = game_origin + Vector2(
		clampf(local_position.x, 8.0, maximum.x),
		clampf(local_position.y, 8.0, maximum.y))

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

func _on_ground_bag_resize_grip_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mouse: InputEventMouseButton = event as InputEventMouseButton
		if mouse.button_index != MOUSE_BUTTON_LEFT:
			return
		_ground_bag_resizing = mouse.pressed
		if mouse.pressed:
			ground_bag_panel.move_to_front()
			_ground_bag_resize_start_mouse = get_viewport().get_mouse_position()
			_ground_bag_resize_start_scale = _ground_bag_scale
		else:
			_save_hud_settings()
		ground_bag_resize_grip.accept_event()
	elif event is InputEventMouseMotion and _ground_bag_resizing:
		var delta: Vector2 = (get_viewport().get_mouse_position()
			- _ground_bag_resize_start_mouse)
		var base_size: Vector2 = ground_bag_panel.size
		if base_size.x <= 0.0 or base_size.y <= 0.0:
			return
		var normalized := Vector2(delta.x / base_size.x, delta.y / base_size.y)
		var scale_delta: float = (normalized.x if absf(normalized.x) >= absf(normalized.y)
			else normalized.y)
		_apply_ground_bag_scale(_ground_bag_resize_start_scale + scale_delta)
		ground_bag_resize_grip.accept_event()

func _apply_ground_bag_scale(requested_scale: float) -> void:
	var maximum_scale: float = INVENTORY_MAX_SCALE
	if game_view.size.x > 0.0 and game_view.size.y > 0.0 \
			and ground_bag_panel.size.x > 0.0 and ground_bag_panel.size.y > 0.0:
		maximum_scale = minf(maximum_scale, minf(
			(game_view.size.x - 16.0) / ground_bag_panel.size.x,
			(game_view.size.y - 16.0) / ground_bag_panel.size.y))
	maximum_scale = maxf(INVENTORY_MIN_SCALE, maximum_scale)
	_ground_bag_scale = clampf(requested_scale, INVENTORY_MIN_SCALE, maximum_scale)
	ground_bag_panel.scale = Vector2.ONE * _ground_bag_scale
	_clamp_ground_bag_window_to_viewport()

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
	# The right margin keeps the window off the fixed resource rail, which
	# nothing may cover; every script-built window already respects the same
	# reserve.
	var maximum: Vector2 = (game_view.size - visible_size
		- Vector2(RESERVED_RIGHT_RAIL_MARGIN, 8.0)).max(Vector2(8.0, 8.0))
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
	carried_item.z_index = 40
	item_lists_panel.z_index = 25
	console_panel.z_index = 25
	settings_panel.z_index = 30
	actor_hud_menu.z_index = 30
	for window_layer: Control in [spells_window, emotes_window, ranging_window]:
		if window_layer != null:
			window_layer.z_index = 26
	_make_scene_windows_draggable()

## Every window moves by its title bar, as Eternal Lands moves all of its own.
## The inventory and the ground bag keep their own handlers: those two also
## carry a resize grip and remember where they were left, and the shared
## dragger has no business in either. The console and the full map are not
## popups but full-screen views, so neither is offered a handle it would only
## use to slide itself off the edge.
func _make_scene_windows_draggable() -> void:
	for panel_and_handle: Array in [
			[stats_panel, "Content/Header"],
			[trade_panel, "Content/Title"],
			[storage_panel, "Content/Title"],
			[manufacturing_panel, "Content/Title"],
			[item_lists_panel, "Content/Header"],
			[dialogue_panel, "DialogueContent/DialogueName"],
			[popup_panel, "PopupContent/PopupTitle"],
			[settings_panel, "Content/Title"],
			[reading_panel, "ReadingContent/ReadingHeader"]]:
		var panel: Control = panel_and_handle[0] as Control
		if panel == null:
			continue
		var handle: Control = panel.get_node_or_null(
			str(panel_and_handle[1])) as Control
		if handle == null:
			push_warning("window drag handle missing: " + str(panel_and_handle[1]))
			continue
		WindowDrag.attach(panel, handle)

func _sync_chat() -> void:
	chat_output.clear()
	var first_line: int = (0 if _chat_tab == "history"
		else maxi(0, AppState.chat_lines.size() - 100))
	for line_value: Variant in AppState.chat_lines.slice(first_line):
		var line: Dictionary = line_value as Dictionary
		var channel: int = int(line.get("channel", 0))
		if not _chat_line_visible(channel):
			continue
		if not _chat_line_allowed(line):
			continue
		chat_output.append_text(_formatted_chat_line(line) + "\n")
	chat_output.scroll_to_line(maxi(0, chat_output.get_line_count() - 1))

func _sync_console() -> void:
	console_output.clear()
	for line_value: Variant in AppState.chat_lines:
		console_output.append_text(_formatted_chat_line(line_value as Dictionary) + "\n")

## The player's own ignore and filter lists. The line still arrived and is
## still in state - this only decides whether they are shown it - so nothing
## the server said is lost, and the console tab still shows everything.
func _chat_line_allowed(line: Dictionary) -> bool:
	if int(line.get("channel", 0)) == AppState.LOCAL_CHAT_CHANNEL:
		return true
	var text: String = str(line.get("text", ""))
	var speaker: String = text.split(":", false, 1)[0] if text.contains(":") else ""
	return console_commands.allows(speaker, text)

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
		AppState.LOCAL_CHAT_CHANNEL: prefix = "[Client] "
		5, 6, 7:
			var slot: int = channel - 5
			var channel_number: int = (int(AppState.active_channels[slot])
				if slot >= 0 and slot < AppState.active_channels.size() else 0)
			prefix = ("[#%d] " % channel_number
				if channel_number > 0 else "[Channel] ")
	# Eternal Lands stamps every line "[12:14:49]", ahead of any tag. A line
	# from before the stamps existed simply has none.
	if bool(_hud_element_options.get("chat_timestamps", true)):
		var stamp: String = str(line.get("stamp", ""))
		if not stamp.is_empty():
			prefix = "[%s] %s" % [stamp, prefix]
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
	_set_overhead_meter(overhead_health_row, health, max_health, "health")
	_set_overhead_meter(overhead_ether_row, ether, max_ether, "ether")
	_set_overhead_meter(overhead_food_row, food, max_food, "food")
	_set_overhead_meter(overhead_action_row, action, max_action, "action")
	_layout_actor_resource_overlay()
	if inventory_load != null:
		inventory_load.text = "Load: %d / %d" % [int(stats.get("carried", 0)),
			int(stats.get("capacity", 0))]
	_sync_skill_rows(stats)
	_sync_hud_indicators()
	_sync_knowledge_bar()
	if stats.is_empty():
		stats_text.text = "[center]Waiting for server statistics…[/center]"
		_sync_session_experience()
		_sync_counters()
		return
	# Each section is its own table with the values in their own cells. Space
	# padding cannot line these up: the client ships one proportional font, so
	# "%-14s" is fourteen spaces of varying width and every number lands
	# wherever its label happened to end.
	# Every section header is the same quiet green Eternal Lands paints its
	# statistics headings in, so the window reads as one document.
	var basic_lines: Array[String] = [_stat_heading(
		"[color=#7fd87f][b]Basic Attributes[/b][/color]")]
	for label_and_key: Array in [["Physique", "physique"],
			["Coordination", "coordination"], ["Reasoning", "reasoning"],
			["Will", "will"], ["Instinct", "instinct"], ["Vitality", "vitality"]]:
		basic_lines.append(_stat_row(str(label_and_key[0]),
			_stat_pair(stats, str(label_and_key[1]))))
	basic_lines.append(_stat_heading(
		"[color=#7fd87f][b]Cross Attributes[/b][/color]", true))
	for cross: Array in [["Might", "physique", "coordination"],
			["Matter", "physique", "will"], ["Toughness", "physique", "vitality"],
			["Charm", "instinct", "vitality"], ["Reaction", "instinct", "coordination"],
			["Perception", "instinct", "reasoning"], ["Rationality", "will", "reasoning"],
			["Dexterity", "coordination", "reasoning"], ["Ethereality", "will", "vitality"]]:
		basic_lines.append(_stat_row(str(cross[0]),
			_cross_pair(stats, str(cross[1]), str(cross[2]))))
	var nexus_lines: Array[String] = [_stat_heading(
		"[color=#7fd87f][b]Nexus[/b][/color]")]
	for label_and_key: Array in [["Human", "human_nexus"], ["Animal", "animal_nexus"],
			["Vegetal", "vegetal_nexus"], ["Inorganic", "inorganic_nexus"],
			["Artificial", "artificial_nexus"], ["Magic", "magic_nexus"]]:
		nexus_lines.append(_stat_row(str(label_and_key[0]),
			_stat_pair(stats, str(label_and_key[1]))))
	var pickpoints: int = int(stats.get("pickpoints_earned", stats.get("overall", 0))) \
		- int(stats.get("pickpoints_spent", 0))
	nexus_lines.append(_stat_row("Pickpoints", _grouped(pickpoints), true))
	nexus_lines.append(_stat_heading("[color=#7fd87f][b]Perks[/b][/color]", true))
	if AppState.perks.is_empty():
		nexus_lines.append(_stat_row("None", ""))
	else:
		for raw_perk: Variant in AppState.perks:
			var perk: Dictionary = raw_perk as Dictionary
			var suffix: String = " (from equipment)" if bool(
				perk.get("from_gear", false)) else ""
			nexus_lines.append(_stat_row(
				"• %s%s" % [str(perk.get("name", "")), suffix], ""))
	nexus_lines.append(_stat_row("[color=#9999ff]Material Points[/color]",
		"[color=#9999ff]%d/%d[/color]" % [health, max_health], true))
	nexus_lines.append(_stat_row("[color=#9999ff]Ethereal Points[/color]",
		"[color=#9999ff]%d/%d[/color]" % [ether, max_ether]))
	nexus_lines.append(_stat_row("[color=#9999ff]Action Points[/color]",
		"[color=#9999ff]%d/%d[/color]" % [action, max_action]))
	nexus_lines.append(_stat_row("Food Level", str(int(stats.get("food", 0)))))
	nexus_lines.append_array(_research_rows(stats))
	var skill_lines: Array[String] = [_stat_heading(
		"[color=#7fd87f][b]Levels and Experience[/b][/color]", false, 3)]
	for skill: String in EXPERIENCE_SKILLS:
		var current_level: int = int(stats.get("overall_level", 0)) \
			if skill == "overall" else int(stats.get(skill, 0))
		var base_level: int = current_level if skill == "overall" else int(
			stats.get(skill + "_base", current_level))
		skill_lines.append("[cell]%s[/cell][cell]%s[/cell][cell]%s[/cell]" % [
			skill.capitalize(),
			"[right]%d/%d[/right]" % [current_level, base_level],
			"[right]%s / %s[/right]" % [
				_grouped(int(stats.get(skill + "_exp", 0))),
				_grouped(int(stats.get(skill + "_exp_next", 0)))]])
	# Each section opens with a heading, so its inner table starts closed and
	# the heading tag reopens it; the leading "[table=2]" here is the one the
	# first heading closes. The skills column is given the larger share of the
	# width because its rows carry two number pairs rather than one.
	stats_text.text = ("[table=3][cell expand=2]%s[/table][/cell]"
		+ "[cell expand=2]%s[/table][/cell][cell expand=3]%s[/table][/cell][/table]") % [
			"[table=2]" + "".join(basic_lines),
			"[table=2]" + "".join(nexus_lines),
			"[table=3]" + "".join(skill_lines)]
	_sync_session_experience()
	_sync_counters()

## One row of a statistics section: the label on the left and the value right
## aligned in its own cell, so every value in that section lines up whatever
## the labels happen to measure.
static func _stat_row(label: String, value: String, spaced := false) -> String:
	var gap: String = "\n" if spaced else ""
	# Cells are left to size themselves to their contents. Fixed expand ratios
	# were tried and made it worse: they narrow the value column until
	# "1000/1000" wraps mid-number.
	return "[cell]%s%s[/cell][cell]%s[/cell]" % [gap, label,
		"[right]%s[/right]" % value if not value.is_empty() else ""]

## A heading across a section's columns.
static func _stat_heading(text: String, spaced := false,
		columns := 2) -> String:
	var gap: String = "\n" if spaced else ""
	var cells: String = "[cell]%s%s[/cell]" % [gap, text]
	for _column: int in range(columns - 1):
		cells += "[cell] [/cell]"
	return cells

## Thousands separators. A seven-figure experience total is unreadable as a
## bare run of digits, and these columns now carry several of them.
static func _grouped(value: int) -> String:
	var digits: String = str(absi(value))
	var grouped: String = ""
	while digits.length() > 3:
		grouped = "," + digits.substr(digits.length() - 3) + grouped
		digits = digits.substr(0, digits.length() - 3)
	grouped = digits + grouped
	return ("-" + grouped) if value < 0 else grouped

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
	_counter_session_baseline = AppState.activity_counters.duplicate()
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

## The category list is whatever the server sent, in the server's order. The
## client used to keep its own 17-name constant and increment it when a request
## was sent, so a rejected deposit or a failed mix still counted and seven of
## the categories were never incremented at all.
func _sync_counter_categories() -> void:
	if counter_categories == null:
		return
	var names: Array[String] = AppState.activity_counter_order
	var unchanged: bool = counter_categories.item_count == names.size()
	if unchanged:
		for index: int in range(names.size()):
			if counter_categories.get_item_text(index) != names[index]:
				unchanged = false
				break
	if unchanged:
		return
	counter_categories.clear()
	for counter_name: String in names:
		counter_categories.add_item(counter_name)
	var selected: int = names.find(_selected_counter_category)
	if selected < 0 and not names.is_empty():
		selected = 0
		_selected_counter_category = names[0]
	if selected >= 0:
		counter_categories.select(selected)

func _sync_counters() -> void:
	if counter_text == null:
		return
	if _selected_counter_category.is_empty():
		counter_text.text = "[center]Waiting for server counters[/center]"
		return
	var total: int = int(AppState.activity_counters.get(_selected_counter_category, 0))
	var session_total: int = maxi(0, total - int(
		_counter_session_baseline.get(_selected_counter_category, 0)))
	counter_text.text = ("[table=3][cell][b]Name[/b][/cell]"
		+ "[cell][right][b]This Session[/b][/right][/cell]"
		+ "[cell][right][b]Total[/b][/right][/cell]"
		+ "[cell]%s[/cell][cell][right]%d[/right][/cell]"
		+ "[cell][right]%d[/right][/cell][/table]

"
		+ "Totals are the server's confirmed events.
Distance this session: %d tiles") % [
		_selected_counter_category, session_total, total, _session_distance]


## Reading progress. `researching` is the knowledge index the character has
## open, 1024 meaning none; `research_completed` and `research_total` are pages.
## All three were decoded into the statistics slice and read by nothing, so a
## player researching a book had no way to see how far through it they were.
## What the server says is being read, as statistics-table rows. The title can
## be long, so it gets a row of its own rather than being squeezed into the
## value column beside the page count.
func _research_rows(stats: Dictionary) -> Array[String]:
	var index: int = int(stats.get("researching", 1024))
	var total: int = int(stats.get("research_total", 0))
	if index >= 1024 or total <= 0:
		return [_stat_row("Researching", "nothing")]
	var completed: int = clampi(int(stats.get("research_completed", 0)), 0, total)
	var title: String = (knowledge_catalog[index]
		if index >= 0 and index < knowledge_catalog.size() else "knowledge #%d" % index)
	return [_stat_row("Researching", "%d%%" % roundi(
			100.0 * float(completed) / float(total))),
		_stat_row("  " + title, "%d/%d pages" % [completed, total])]

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
	# Eternal Lands writes the experience still to go left of the bar and the
	# watched skill's name at its right end; the full pair lives in the tooltip.
	experience_bottom_text.text = _grouped(maxi(0, next_experience - current_experience))
	experience_skill_label.text = skill.capitalize()
	var experience_tooltip: String = "%s experience: %s / %s" % [skill.capitalize(),
		_grouped(current_experience), _grouped(next_experience)]
	experience_bottom_text.tooltip_text = experience_tooltip
	experience_bottom.tooltip_text = experience_tooltip
	experience_skill_label.tooltip_text = experience_tooltip

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

## The rail's side stats list, built the way Eternal Lands draws it: one thin
## row per skill, a green fill behind the text showing how far through the
## level the skill is, the watched skill's name in the GUI gold. Clicking a row
## watches that skill on the bottom experience bar, as the legacy client does.
func _build_skill_rows() -> void:
	for spec: Array in SKILL_ROW_SPECS:
		var key: String = str(spec[1])
		var row := ProgressBar.new()
		row.name = "SkillRow" + key.capitalize()
		# Tall enough for the whole line box, not just the x-height: at twelve
		# pixels the descender of "eng" was sliced off by the row's own frame.
		row.custom_minimum_size = Vector2(0.0, SKILL_ROW_HEIGHT)
		row.max_value = 1.0
		row.show_percentage = false
		row.mouse_filter = Control.MOUSE_FILTER_STOP
		var background := StyleBoxFlat.new()
		background.bg_color = Color(0.02, 0.02, 0.02, 0.6)
		background.border_color = EL_GUI_COLOUR
		background.set_border_width_all(1)
		var fill := StyleBoxFlat.new()
		# The side-stats bar colour hud_misc_window.c uses: a quiet green that
		# stays behind white text without swallowing it.
		fill.bg_color = Color(0.24, 0.40, 0.16, 0.9)
		row.add_theme_stylebox_override("background", background)
		row.add_theme_stylebox_override("fill", fill)
		var name_label := Label.new()
		name_label.name = "Name"
		name_label.text = str(spec[0])
		name_label.add_theme_font_size_override("font_size", 10)
		name_label.add_theme_color_override("font_color", Color.WHITE)
		name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		name_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		name_label.offset_left = 3.0
		name_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		row.add_child(name_label)
		var value_label := Label.new()
		value_label.name = "Value"
		value_label.text = "0"
		value_label.add_theme_font_size_override("font_size", 10)
		value_label.add_theme_color_override("font_color", Color.WHITE)
		value_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		value_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		value_label.offset_right = -3.0
		value_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		value_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		row.add_child(value_label)
		row.gui_input.connect(_on_skill_row_gui_input.bind(key))
		skill_rows.add_child(row)
		_skill_row_nodes[key] = row

func _sync_skill_rows(stats: Dictionary) -> void:
	for spec: Array in SKILL_ROW_SPECS:
		var key: String = str(spec[1])
		var row_value: Variant = _skill_row_nodes.get(key)
		if not row_value is ProgressBar:
			continue
		var row: ProgressBar = row_value as ProgressBar
		var level: int = int(stats.get("overall_level", 0)) \
			if key == "overall" else int(stats.get(key, 0))
		(row.get_node("Value") as Label).text = str(level)
		var name_label: Label = row.get_node("Name") as Label
		name_label.add_theme_color_override("font_color",
			EL_GUI_BRIGHT_COLOUR if key == _selected_experience_skill else Color.WHITE)
		var current_experience: int = int(stats.get(key + "_exp", 0))
		var next_experience: int = int(stats.get(key + "_exp_next", 0))
		var base_level: int = int(stats.get(key + "_base", level))
		var level_floor: int = _experience_floor_for_level(base_level)
		if next_experience <= level_floor:
			level_floor = 0
		var span: int = maxi(1, next_experience - level_floor)
		row.value = clampf(float(current_experience - level_floor) / float(span), 0.0, 1.0)
		row.tooltip_text = ("%s %d - %s experience to go"
			+ "\nClick to watch this skill on the experience bar") % [
			key.capitalize(), level,
			_grouped(maxi(0, next_experience - current_experience))]

func _on_skill_row_gui_input(event: InputEvent, key: String) -> void:
	if not (event is InputEventMouseButton
			and (event as InputEventMouseButton).pressed
			and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT):
		return
	_selected_experience_skill = key
	_sync_experience_meter(AppState.stats)
	_sync_skill_rows(AppState.stats)
	_save_hud_layout()

## The Eternal Lands indicator letters at the bottom right: lit letters are
## states the server has actually stated this session; letters the fork has no
## signal for stay at the "unavailable" shade instead of guessing.
func _build_hud_indicators() -> void:
	for spec: Array in HUD_INDICATORS:
		var letter := Label.new()
		letter.name = "Indicator" + str(spec[0])
		letter.text = str(spec[0])
		letter.custom_minimum_size = Vector2(14.0, 0.0)
		letter.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		letter.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		letter.add_theme_font_size_override("font_size", 14)
		letter.add_theme_color_override("font_color", INDICATOR_INACTIVE_COLOUR)
		letter.mouse_filter = Control.MOUSE_FILTER_STOP
		letter.gui_input.connect(_on_indicator_gui_input.bind(str(spec[0])))
		hud_indicators.add_child(letter)
		_indicator_labels[str(spec[0])] = letter
	_sync_hud_indicators()

func _sync_hud_indicators() -> void:
	if _indicator_labels.is_empty():
		return
	var available: Dictionary = {
		"S": not AppState.almanac.is_empty(),
		"H": true, "P": false, "M": true, "R": true, "G": false, "A": false}
	var active: Dictionary = {
		"S": str(AppState.almanac.get("kind", "ordinary")) != "ordinary",
		"H": bool(AppState.harvest.get("active", false)),
		"P": false,
		"M": _unseen_pm_count > 0,
		"R": _banner_option("ranging_lock"),
		"G": false, "A": false}
	for spec: Array in HUD_INDICATORS:
		var letter_key: String = str(spec[0])
		var letter: Label = _indicator_labels[letter_key] as Label
		var is_available: bool = bool(available.get(letter_key, false))
		var is_active: bool = bool(active.get(letter_key, false))
		var colour: Color = INDICATOR_UNAVAILABLE_COLOUR
		if is_available:
			colour = INDICATOR_ACTIVE_COLOUR if is_active else INDICATOR_INACTIVE_COLOUR
		letter.add_theme_color_override("font_color", colour)
		var described: String = str(spec[1]) if is_active else str(spec[2])
		if letter_key == "M" and _unseen_pm_count > 0:
			described += " [%d]" % _unseen_pm_count
		letter.tooltip_text = described

func _on_indicator_gui_input(event: InputEvent, letter_key: String) -> void:
	if not (event is InputEventMouseButton
			and (event as InputEventMouseButton).pressed
			and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT):
		return
	match letter_key:
		"S":
			# What Eternal Lands' #day prints: the day in force, from the
			# almanac packet the server already sent.
			if AppState.almanac.is_empty():
				AppState.append_local_message("The server has not stated the day yet.")
			else:
				AppState.append_local_message("Today: %s - %s" % [
					str(AppState.almanac.get("name", "an ordinary day")),
					str(AppState.almanac.get("description", ""))])
		"M":
			_unseen_pm_count = 0
			_sync_hud_indicators()

## The countdown/stopwatch line in the rail, as hud_timer.cpp behaves: click
## starts and stops, shift+click swaps mode, middle-click resets, the wheel
## sets the countdown start (Ctrl fine steps, Alt coarse). Green while it
## runs, red while it stands.
func _update_hud_timer() -> void:
	if not _hud_timer_running:
		return
	var now: int = Time.get_ticks_msec()
	if now - _hud_timer_last_tick_msec < 1000:
		return
	_hud_timer_last_tick_msec = now
	if _hud_timer_stopwatch:
		_hud_timer_seconds = mini(_hud_timer_seconds + 1, 9 * 60 + 59)
	else:
		_hud_timer_seconds -= 1
		if _hud_timer_seconds <= 0:
			_hud_timer_seconds = 0
			_hud_timer_running = false
			audio_director.play("ui_close")
	_sync_hud_timer_label()

func _sync_hud_timer_label() -> void:
	hud_timer_label.text = "%s%d:%02d" % [
		"S" if _hud_timer_stopwatch else "C",
		_hud_timer_seconds / 60, _hud_timer_seconds % 60]
	hud_timer_label.add_theme_color_override("font_color",
		Color(0.5, 1.0, 0.5) if _hud_timer_running else Color(1.0, 0.5, 0.5))

func _on_hud_timer_gui_input(event: InputEvent) -> void:
	if not event is InputEventMouseButton:
		return
	var click: InputEventMouseButton = event as InputEventMouseButton
	if not click.pressed:
		return
	match click.button_index:
		MOUSE_BUTTON_LEFT:
			if click.shift_pressed:
				_hud_timer_stopwatch = not _hud_timer_stopwatch
				_hud_timer_running = false
				_hud_timer_seconds = 0 if _hud_timer_stopwatch \
					else _hud_timer_start_seconds
				_save_hud_settings()
			else:
				if not _hud_timer_stopwatch and _hud_timer_seconds <= 0:
					_hud_timer_seconds = _hud_timer_start_seconds
				_hud_timer_running = not _hud_timer_running
				_hud_timer_last_tick_msec = Time.get_ticks_msec()
		MOUSE_BUTTON_MIDDLE:
			_hud_timer_running = false
			_hud_timer_seconds = 0 if _hud_timer_stopwatch else _hud_timer_start_seconds
		MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN:
			if _hud_timer_stopwatch:
				return
			var step: int = 5
			if click.ctrl_pressed:
				step = 1
			elif click.alt_pressed:
				step = 30
			if click.button_index == MOUSE_BUTTON_WHEEL_DOWN:
				step = -step
			_hud_timer_start_seconds = clampi(
				_hud_timer_start_seconds + step, 0, 9 * 60 + 59)
			if not _hud_timer_running:
				_hud_timer_seconds = _hud_timer_start_seconds
			_save_hud_settings()
		_:
			return
	_sync_hud_timer_label()

## The knowledge bar under the stats list: research progress as the server
## states it in the statistics packet, "Idle" when it states none.
func _sync_knowledge_bar() -> void:
	var stats: Dictionary = AppState.stats
	var index: int = int(stats.get("researching", 1024))
	var total: int = int(stats.get("research_total", 0))
	if index >= 1024 or total <= 0:
		knowledge_bar.value = 0.0
		knowledge_text.text = "Idle"
		knowledge_bar.tooltip_text = "Researching nothing"
		return
	var completed: int = clampi(int(stats.get("research_completed", 0)), 0, total)
	var percent: int = roundi(100.0 * float(completed) / float(total))
	knowledge_bar.value = float(percent)
	knowledge_text.text = "%d%%" % percent
	knowledge_bar.tooltip_text = "Researching %s: %d of %d pages" % [
		(knowledge_catalog[index] if index >= 0 and index < knowledge_catalog.size()
			else "knowledge #%d" % index), completed, total]

func _on_knowledge_bar_gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton
			and (event as InputEventMouseButton).pressed
			and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT):
		return
	var stats: Dictionary = AppState.stats
	var index: int = int(stats.get("researching", 1024))
	var total: int = int(stats.get("research_total", 0))
	if index >= 1024 or total <= 0:
		AppState.append_local_message(
			"You are not researching anything for the time being")
		return
	AppState.append_local_message("Researching %s: %d of %d pages" % [
		(knowledge_catalog[index] if index >= 0 and index < knowledge_catalog.size()
			else "knowledge #%d" % index),
		clampi(int(stats.get("research_completed", 0)), 0, total), total])

## Which of the legacy HUD elements are drawn. The switches live on the
## settings window's HUD tab and persist under [hud], the way Eternal Lands
## keeps them in el.ini.
func _apply_hud_element_options() -> void:
	fps_label.visible = bool(_hud_element_options.get("show_fps", true))
	_sync_chat()
	hud_timer_label.visible = bool(_hud_element_options.get("hud_timer", true))
	knowledge_bar.visible = bool(_hud_element_options.get("knowledge_bar", true))
	skill_rows.visible = bool(_hud_element_options.get("side_stats", true))
	hud_indicators.visible = bool(_hud_element_options.get("indicators", true))
	clock_text.visible = bool(_hud_element_options.get("digital_clock", true))
	clock_face.visible = bool(_hud_element_options.get("analog_clock", true))
	_sync_hud_timer_label()
	_sync_knowledge_bar()

func _update_fps_label() -> void:
	if not fps_label.visible:
		return
	var now: int = Time.get_ticks_msec()
	if now < _fps_refresh_msec:
		return
	_fps_refresh_msec = now + 500
	fps_label.text = "FPS: %d" % roundi(Engine.get_frames_per_second())

## Every &"chat" emit is exactly one appended line (the three append sites in
## AppState each emit once), so only the tail needs looking at. Counting by a
## remembered index broke the moment the 1000-line cap started dropping the
## head: the size stops moving while lines keep arriving. Clicking M is the
## acknowledgement that clears the count.
func _count_unseen_private_messages() -> void:
	var lines: Array = AppState.chat_lines
	if lines.is_empty():
		return
	if int((lines[lines.size() - 1] as Dictionary).get("channel", 0)) == 1:
		_unseen_pm_count += 1
		_sync_hud_indicators()

## Eternal Lands writes only the current value, left of the bar, and names the
## attribute on hover; the overhead banner rows keep the full pair. The rail's
## legacy vertical bars pass their own labels through here too, so the format
## is decided once.
static func _set_meter(bar: ProgressBar, label: Label, value: int,
		maximum: int, title: String) -> void:
	bar.max_value = maxi(1, maximum)
	bar.value = clampi(value, 0, maxi(1, maximum))
	label.text = str(value)
	var described: String = "%s: %d / %d" % [title, value, maximum]
	label.tooltip_text = described
	bar.tooltip_text = described

static func _set_overhead_meter(row: HBoxContainer, value: int, maximum: int,
		colour_kind: String) -> void:
	var bar: ProgressBar = row.get_node("Bar") as ProgressBar
	var label: Label = row.get_node("Number") as Label
	var safe_maximum: int = maxi(1, maximum)
	bar.max_value = safe_maximum
	bar.value = clampi(value, 0, safe_maximum)
	label.text = "%d/%d" % [value, maximum]
	var colour: Color = _banner_colour(colour_kind,
		float(value) / float(safe_maximum))
	var fill: StyleBoxFlat = bar.get_theme_stylebox("fill") as StyleBoxFlat
	if fill != null:
		fill.bg_color = colour
	label.add_theme_color_override("font_color", colour)

## Eternal Lands recolours a banner meter as it drains rather than fixing one
## colour per stat: actors.c set_health_color() ramps green to red, and
## set_banner_colour_general() walks ether and food between the named
## banner.*.zero and banner.*.full colours. Action points are Eloria's own, so
## they follow the same shape between the two ends of the HUD purple.
static func _banner_colour(kind: String, percent: float) -> Color:
	var fraction: float = clampf(percent, 0.0, 1.0)
	match kind:
		"health":
			return Color(clampf((1.0 - fraction) * 2.0, 0.0, 1.0),
				clampf(fraction / 1.25 * 2.0, 0.0, 1.0), 0.0)
		"ether":
			return Color(0.7, 0.7, 1.0).lerp(Color(0.4, 0.4, 1.0), fraction)
		"food":
			return Color(1.0, 0.5, 0.0).lerp(Color(1.0, 1.0, 0.0), fraction)
	return Color(1.0, 0.55, 0.9).lerp(Color(0.73, 0.28, 0.86), fraction)

func _update_legacy_clock_and_compass() -> void:
	var elapsed_seconds := 0.0
	if AppState.game_minute_anchor_msec > 0:
		elapsed_seconds = maxf(0.0,
			float(Time.get_ticks_msec() - AppState.game_minute_anchor_msec) / 1000.0)
	var minute_fraction: float = fmod(float(AppState.game_minute) + elapsed_seconds / 60.0, 360.0)
	var display_minute: int = floori(minute_fraction)
	# Eternal Lands' digital clock is H:MM, with seconds behind an option; its
	# analog dial is the whole 360-minute day - one degree per game minute - so
	# the sun-and-moon face reads as day and night.
	if bool(_hud_element_options.get("show_game_seconds", true)):
		var display_game_second: int = floori(fmod(minute_fraction, 1.0) * 60.0)
		clock_text.text = "%d:%02d:%02d" % [display_minute / 60,
			display_minute % 60, display_game_second]
	else:
		clock_text.text = "%d:%02d" % [display_minute / 60, display_minute % 60]
	clock_hand.rotation = deg_to_rad(minute_fraction)
	compass_needle.rotation = deg_to_rad(-camera_rig.yaw_degrees)

func _update_actor_resource_overlay() -> void:
	if not _banner_has_content():
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
	# Instance mode lifts your own banner clear of the melee so it stays legible
	# in a crowd, the way EL raises it by instance_mode_banner_height lines.
	var instance_lift: float = (BANNER_INSTANCE_LIFT_ROWS * _banner_row_height()
		if _banner_option("instance_mode") else 0.0)
	var overlay_position: Vector2 = screen_position - Vector2(
		actor_resource_overlay.size.x * 0.5,
		actor_resource_overlay.size.y + 8.0 + instance_lift)
	actor_resource_overlay.position = Vector2(
		clampf(overlay_position.x, 4.0,
			maxf(4.0, game_view.size.x - actor_resource_overlay.size.x - 90.0)),
		clampf(overlay_position.y, 34.0,
			maxf(34.0, game_view.size.y - actor_resource_overlay.size.y - 86.0)))
	actor_resource_overlay.show()

func _banner_has_content() -> bool:
	if _banner_option("show_names"):
		return true
	for row_spec: Array in BANNER_ROWS:
		if _banner_option(str(row_spec[1])) or _banner_option(str(row_spec[2])):
			return true
	return false

func _banner_row_height() -> float:
	return maxf(1.0, _banner_row("HealthRow").get_combined_minimum_size().y)

## Draws the arrow the server said was loosed. The shot is already resolved -
## the damage arrives in its own packet - so this decides nothing, and an
## actor the client has not been told about is not guessed at.
func _on_missile_fired(shot: Dictionary) -> void:
	if not _effects_enabled:
		return
	var from_value: Variant = _actor_effect_position(
		int(shot.get("source_actor_id", -1)))
	var to_value: Variant = _actor_effect_position(
		int(shot.get("target_actor_id", -1)))
	if not from_value is Vector3 or not to_value is Vector3:
		return
	var missile := MissileFlight3D.new()
	world_root.add_child(missile)
	missile.configure(from_value as Vector3, to_value as Vector3)
	world_effects.append(missile)
	world_effects = world_effects.filter(func(node: Variant) -> bool:
		return is_instance_valid(node))

## Objects the server put into this map after it loaded. Everything the client
## knew about a map used to arrive with the map, so nothing could change while
## anybody was looking at it.
func _sync_placed_objects() -> void:
	for raw_id: Variant in AppState.world_objects:
		var object_id: int = int(raw_id)
		if placed_object_nodes.has(object_id):
			continue
		var placed: Dictionary = AppState.world_objects[object_id] as Dictionary
		var node := PlacedObject3D.new()
		world_root.add_child(node)
		node.configure(placed, adapter.server_to_godot(
			int(placed.get("x", 0)), int(placed.get("y", 0))))
		placed_object_nodes[object_id] = node
	for object_id: Variant in placed_object_nodes.keys():
		if AppState.world_objects.has(object_id):
			continue
		var stale: Variant = placed_object_nodes[object_id]
		if is_instance_valid(stale):
			(stale as Node).queue_free()
		placed_object_nodes.erase(object_id)

## Somebody arrived or left by a portal. The actor packets already say who
## moved; this says where the two ends were, which is the part a client cannot
## work out - by the time it hears about an arrival the departure has gone.
func _on_teleport_seen(teleport: Dictionary) -> void:
	if not _effects_enabled:
		return
	var effect := WorldEffect3D.new()
	world_root.add_child(effect)
	# 1 is the beneficial class, which rises; 0 falls. Arriving rises out of
	# the ground and leaving sinks into it.
	effect.configure(1 if bool(teleport.get("arriving", true)) else 0,
		adapter.server_to_godot(int(teleport.get("x", 0)),
			int(teleport.get("y", 0))))
	world_effects.append(effect)
	world_effects = world_effects.filter(func(node: Variant) -> bool:
		return is_instance_valid(node))

## The sky the server said is over this map. Nothing here decides anything:
## what is falling and how hard is on the wire, because two players standing
## together have to see the same sky.
func _sync_weather() -> void:
	if weather_layer == null:
		return
	if not _effects_enabled:
		weather_layer.set_weather(0, 0)
		return
	weather_layer.set_weather(int(AppState.weather.get("kind", 0)),
		int(AppState.weather.get("intensity", 0)))

## The fires burning on this map, placed by tile. A fire the server removes
## goes out; one it has not mentioned was never lit.
func _sync_fires() -> void:
	if weather_layer == null:
		return
	for tile: Variant in AppState.fires:
		var fire_tile: Vector2i = tile as Vector2i
		if not weather_layer.has_fire_at(fire_tile):
			weather_layer.place_fire(
				adapter.server_to_godot(fire_tile.x, fire_tile.y),
				int(AppState.fires[fire_tile]), fire_tile)
	for tile: Variant in weather_layer.fire_tiles():
		if not AppState.fires.has(tile):
			weather_layer.remove_fire(tile as Vector2i)

func _on_thunder_struck(severity: int) -> void:
	if weather_layer != null and _effects_enabled:
		weather_layer.strike(severity)
	audio_director.play("world_effect")

## An arrow on its way to a tile rather than into an actor: a practice shot,
## or a miss.
##
## A miss used to be drawn as a shot at the target it missed, which is the one
## thing it was not - so every miss looked like a hit. The tile is the server's
## decision, arriving on the wire, so two clients watching one shot draw the
## same arrow instead of each inventing a scatter.
func _on_ground_missile_fired(shot: Dictionary) -> void:
	if not _effects_enabled:
		return
	var from_value: Variant = _actor_effect_position(
		int(shot.get("source_actor_id", -1)))
	if not from_value is Vector3:
		return
	var landing: Vector3 = adapter.server_to_godot(
		int(shot.get("x", 0)), int(shot.get("y", 0)))
	var missile := MissileFlight3D.new()
	world_root.add_child(missile)
	missile.configure(from_value as Vector3, landing)
	world_effects.append(missile)
	world_effects = world_effects.filter(func(node: Variant) -> bool:
		return is_instance_valid(node))

## Draws what the server said just happened, where it happened.
##
## Nothing is inferred about the effect: an actor the client has never been
## told about has no position, so nothing is drawn for it rather than a guess
## at the middle of the map.
func _on_special_effect_requested(effect: Dictionary) -> void:
	var origin_value: Variant = _actor_effect_position(int(effect.get("actor_id", -1)))
	if not origin_value is Vector3:
		return
	var target_value: Variant = _actor_effect_position(int(effect.get("target_id", -1)))
	if not _effects_enabled:
		return
	var world_effect := WorldEffect3D.new()
	world_root.add_child(world_effect)
	world_effect.configure(int(effect.get("effect", -1)),
		origin_value as Vector3, target_value)
	world_effects.append(world_effect)
	world_effects = world_effects.filter(func(node: Variant) -> bool:
		return is_instance_valid(node))

## The server asked an actor to play a named action. An action this client has
## no clip for plays nothing: `play_action` looks the name up in the animation
## map and returns if it finds nothing, so an unknown action is ignored rather
## than guessed at. The words that came with an emote arrive as chat either
## way, so nothing is lost by staying still.
func _on_actor_animation_requested(animation: Dictionary) -> void:
	var node: Variant = actor_nodes.get(int(animation.get("actor_id", -1)))
	if not is_instance_valid(node):
		return
	(node as ReplicatedActor3D).play_action(
		StringName(str(animation.get("action", ""))))

func _actor_effect_position(actor_id: int) -> Variant:
	if actor_id < 0:
		return null
	var node: Variant = actor_nodes.get(actor_id)
	if not is_instance_valid(node):
		return null
	return (node as Node3D).global_position

func _on_floating_feedback_requested(feedback: Dictionary) -> void:
	# Gains that land together (a skill plus the overall total, or several stats
	# in one partial stats packet) are collected for the frame so the group can
	# be filtered and stacked instead of every entry spawning on its own.
	_pending_floating_feedback.append(feedback)
	if _floating_feedback_flush_queued:
		return
	_floating_feedback_flush_queued = true
	_flush_floating_feedback.call_deferred()

func _flush_floating_feedback() -> void:
	_floating_feedback_flush_queued = false
	var pending: Array[Dictionary] = _pending_floating_feedback
	_pending_floating_feedback = []
	var has_skill_experience := false
	for feedback: Dictionary in pending:
		if _is_skill_experience(feedback):
			has_skill_experience = true
			break
	if has_skill_experience:
		_last_skill_experience_msec = Time.get_ticks_msec()
	for feedback: Dictionary in pending:
		# Overall experience is the sum of the skill gains, so repeating it next
		# to the skill that produced it says nothing new. The timestamp covers
		# the case where the server splits the two gains across frames.
		if str(feedback.get("kind", "")) == "experience" \
				and str(feedback.get("skill", "")) == "overall":
			if has_skill_experience:
				continue
			if Time.get_ticks_msec() - _last_skill_experience_msec \
					< FLOATING_FEEDBACK_OVERALL_GRACE_MSEC:
				continue
		_spawn_floating_feedback(feedback)

static func _is_skill_experience(feedback: Dictionary) -> bool:
	return str(feedback.get("kind", "")) == "experience" \
		and str(feedback.get("skill", "")) != "overall"

func _spawn_floating_feedback(feedback: Dictionary) -> void:
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
	label.add_theme_font_size_override("font_size", 17 if kind == "level" else 14)
	label.add_theme_color_override("font_outline_color", Color(0.015, 0.02, 0.025, 0.98))
	label.add_theme_constant_override("outline_size", 4)
	if kind == "level":
		label.text = "Level %d %s" % [int(feedback.get("level", 0)), skill.capitalize()]
		label.add_theme_color_override("font_color", Color(1.0, 0.78, 0.22, 1.0))
	else:
		label.text = "+%d %s" % [int(feedback.get("amount", 0)), skill.capitalize()]
		label.add_theme_color_override("font_color", Color(0.45, 1.0, 0.38, 1.0))
	_floating_feedback_layer.add_child(label)
	label.reset_size()
	label.position = Vector2(screen_position.x - label.size.x * 0.5,
		_floating_feedback_row(screen_position.y - FLOATING_FEEDBACK_BASE_OFFSET))
	_active_floating_labels.append(label)
	var tween: Tween = create_tween().set_parallel(true)
	tween.tween_property(label, "position",
		label.position - Vector2(0.0, FLOATING_FEEDBACK_RISE),
		FLOATING_FEEDBACK_LIFETIME).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.tween_property(label, "modulate:a", 0.0,
		FLOATING_FEEDBACK_LIFETIME - FLOATING_FEEDBACK_FADE_DELAY).set_delay(
		FLOATING_FEEDBACK_FADE_DELAY)
	tween.finished.connect(func() -> void:
		_active_floating_labels.erase(label)
		label.queue_free())

func _floating_feedback_row(preferred_y: float) -> float:
	# Messages drift upwards, so a new one takes the first free row at or below
	# the preferred height rather than landing on top of one still on screen.
	var occupied: Array[float] = []
	for index: int in range(_active_floating_labels.size() - 1, -1, -1):
		var other: Label = _active_floating_labels[index]
		if is_instance_valid(other):
			occupied.append(other.position.y)
		else:
			_active_floating_labels.remove_at(index)
	occupied.sort()
	var row_y: float = preferred_y
	var lowest_row: float = preferred_y + FLOATING_FEEDBACK_ROW_HEIGHT * float(
		FLOATING_FEEDBACK_MAX_ROWS)
	for y: float in occupied:
		if row_y > lowest_row:
			break
		if absf(y - row_y) < FLOATING_FEEDBACK_ROW_HEIGHT:
			row_y = y + FLOATING_FEEDBACK_ROW_HEIGHT
	return minf(row_y, lowest_row)

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

func _sync_hud_button_states(force := false) -> void:
	if _hud_icon_regions.is_empty():
		return
	# Runs every frame. Resolving every unique-name node and formatting a
	# dictionary into a signature string each time allocated for nothing; the
	# buttons are resolved once and the comparison is now a bitmask.
	if _hud_state_buttons.is_empty():
		_hud_state_buttons = [%WalkButton, %MapButton, %SitButton, %AttackButton,
			%TradeButton, %LookButton, %InventoryButton, %StatsButton,
			%KnowledgeButton, %ManufacturingButton, %ChatButton, %DisconnectButton,
			%EncyclopediaButton, %SpellsButton, %EmotesButton, %QuestButton,
			%InfoButton, %BuddyButton, %ConsoleButton, %HelpButton,
			%RangingButton, %MinimapButton, %OptionsButton]
	var local_actor: Dictionary = AppState.actors.get(AppState.local_actor_id, {})
	var sitting: bool = bool(local_actor.get("sitting", false))
	var stats_open: bool = stats_panel.visible
	var stats_tab: int = stats_tabs.current_tab
	var quest_panel_value: Variant = extension_windows.get("quest_panel")
	var states: Array[bool] = [
		_interaction_mode == "walk" and not sitting,
		full_map.visible,
		sitting,
		_interaction_mode == "attack",
		_interaction_mode == "trade" or bool(AppState.trade.get("open", false)),
		bool(AppState.player_info.get("open", false)),
		inventory_panel.visible,
		stats_open and stats_tab != 1,
		stats_open and stats_tab == 1,
		manufacturing_panel.visible,
		chat_input.has_focus(),
		AppState.connection_state == "connected",
		reference_window != null and bool(reference_window.call("is_encyclopedia_open")),
		spells_window != null and bool(spells_window.call("is_open")),
		emotes_window != null and bool(emotes_window.call("is_open")),
		quest_panel_value is Control and (quest_panel_value as Control).visible,
		_reference_tab_open(1),
		_reference_tab_open(5),
		console_panel.visible,
		_reference_tab_open(0),
		ranging_window != null and bool(ranging_window.call("is_open")),
		minimap_frame.visible,
		settings_panel.visible]
	# Only while the player has not chosen attack mode from the HUD: a mode
	# they picked stays picked, and Alt must not appear to be what put it there.
	var attack_preview: bool = _alt_attack_preview and _interaction_mode != "attack"
	var mask: int = 0
	for index: int in states.size():
		if states[index]:
			mask |= 1 << index
	if attack_preview:
		mask |= 1 << states.size()
	# Availability rides in the same signature. An icon's colour now follows
	# whether its action can be taken at all, and that changes when the
	# selection changes without any of the states above moving.
	for index: int in _hud_state_buttons.size():
		if not _hud_state_buttons[index].disabled:
			mask |= 1 << (states.size() + 1 + index)
	if not force and mask == _hud_button_state_mask:
		return
	_hud_button_state_mask = mask
	for index: int in _hud_state_buttons.size():
		var button: Button = _hud_state_buttons[index]
		var active: bool = states[index]
		button.set_pressed_no_signal(active)
		# Eternal Lands greys only what it will not let you use. Everything
		# available is drawn in colour whether or not its window is open, and
		# an open window says so with the lit frame its pressed style carries.
		var atlas: Texture2D = (_hud_inactive_atlas if button.disabled
			else _hud_active_atlas)
		if atlas != null:
			button.icon = _atlas_region(atlas, _icon_region_for(button, sitting))
	_apply_attack_preview(attack_preview)

## The sit icon is a pair, the way icon_window.cpp's sit/stand multi-icon is:
## seated, it shows the stand icon, because standing is what pressing it does.
func _icon_region_for(button: Button, sitting: bool) -> Rect2:
	if button == sit_button and sitting:
		return STAND_ICON_REGION
	return _hud_icon_regions[button] as Rect2

## The move icon while Alt is held: it wears the attack icon and does what the
## attack icon does, and goes back to itself the moment Alt is let go. Nothing
## about the interaction mode changes, so an attack mode chosen from the HUD is
## untouched by holding Alt or letting it go.
func _apply_attack_preview(previewing: bool) -> void:
	var walk_button: Button = %WalkButton
	if previewing:
		if _hud_active_atlas != null:
			walk_button.icon = _atlas_region(_hud_active_atlas,
				_hud_icon_regions[%AttackButton] as Rect2)
		walk_button.tooltip_text = ("Alt is held: a click attacks what it lands"
			+ " on. Let Alt go for walk mode")
	else:
		walk_button.tooltip_text = "Walk mode; hold Shift while clicking to run"

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

## Writes a stack count over a slot at the largest size that still fits it.
static func _set_slot_quantity(label: Label, quantity: int) -> void:
	var text: String = str(quantity)
	label.text = text
	label.add_theme_font_size_override("font_size",
		11 if text.length() <= 4 else (9 if text.length() <= 6 else 8))

func _add_slot_quantity_label(button: Button) -> Label:
	var quantity: Label = Label.new()
	quantity.name = "Quantity"
	quantity.mouse_filter = Control.MOUSE_FILTER_IGNORE
	quantity.anchor_left = 0.0
	quantity.anchor_top = 1.0
	quantity.anchor_right = 1.0
	quantity.anchor_bottom = 1.0
	quantity.offset_left = 2.0
	quantity.offset_top = -17.0
	quantity.offset_right = -3.0
	quantity.offset_bottom = -2.0
	quantity.clip_text = false
	quantity.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	quantity.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	quantity.add_theme_font_size_override("font_size", 11)
	quantity.add_theme_color_override("font_color", Color.WHITE)
	quantity.add_theme_color_override("font_outline_color", Color(0.02, 0.02, 0.02))
	quantity.add_theme_constant_override("outline_size", 3)
	button.add_child(quantity)
	return quantity

func _ground_bag_tooltip(item: Dictionary) -> String:
	var image_id: int = int(item.get("image_id", 0))
	var tooltip: String = "Item image #%d — quantity %d" % [image_id,
		int(item.get("quantity", 0))]
	if item_atlas.uses_substitute(image_id):
		tooltip += "
Independent Eloria icon substitute for legacy image #%d." % image_id
	return tooltip + ("
Left click picks up the inventory quantity (Ctrl for all);"
		+ " right click asks the server what it is.")

func _build_ground_bag_slots() -> void:
	for index: int in range(GROUND_BAG_SLOT_COUNT):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(44.0, 44.0)
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.focus_mode = Control.FOCUS_NONE
		button.clip_contents = true
		button.text = ""
		button.tooltip_text = "Empty bag slot"
		button.disabled = true
		button.set_meta("bag_position", -1)
		button.pressed.connect(_on_ground_bag_slot_pressed.bind(index))
		button.gui_input.connect(_on_ground_bag_slot_gui_input.bind(index))
		ground_bag_grid.add_child(button)
		ground_bag_slot_buttons.append(button)
		ground_bag_quantity_labels.append(_add_slot_quantity_label(button))

func _fill_ground_bag_grid(items: Dictionary) -> void:
	var positions: Array = items.keys()
	positions.sort()
	var index := 0
	for raw_position: Variant in positions:
		if index >= ground_bag_slot_buttons.size():
			break
		var item_value: Variant = items.get(raw_position)
		if not item_value is Dictionary:
			continue
		var item: Dictionary = item_value as Dictionary
		var button: Button = ground_bag_slot_buttons[index]
		button.set_meta("bag_position", int(raw_position))
		button.icon = item_atlas.icon_for(int(item.get("image_id", 0)))
		button.disabled = false
		button.tooltip_text = _ground_bag_tooltip(item)
		ground_bag_quantity_labels[index].text = str(int(item.get("quantity", 0)))
		index += 1
	if index >= ground_bag_slot_buttons.size() and positions.size() > index:
		push_warning("Ground bag holds more stacks than the grid can show: %d of %d"
			% [index, positions.size()])
	for empty_index: int in range(index, ground_bag_slot_buttons.size()):
		var empty_button: Button = ground_bag_slot_buttons[empty_index]
		empty_button.set_meta("bag_position", -1)
		empty_button.icon = null
		empty_button.disabled = true
		empty_button.tooltip_text = "Empty bag slot"
		ground_bag_quantity_labels[empty_index].text = ""

func _build_inventory_slots() -> void:
	for slot: int in range(36):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(44.0, 44.0)
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.focus_mode = Control.FOCUS_NONE
		button.clip_contents = true
		button.text = ""
		button.tooltip_text = "Empty inventory slot %d" % (slot + 1)
		button.disabled = true
		button.pressed.connect(_on_inventory_slot_pressed.bind(slot))
		button.gui_input.connect(_on_inventory_slot_gui_input.bind(slot))
		inventory_grid.add_child(button)
		inventory_slot_buttons.append(button)
		inventory_quantity_labels.append(_add_slot_quantity_label(button))

func _build_equipment_slots() -> void:
	for index: int in range(8):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(44.0, 44.0)
		button.expand_icon = true
		button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
		button.focus_mode = Control.FOCUS_NONE
		button.text = ""
		button.tooltip_text = "Generic legacy equipment position %d" % (index + 1)
		button.disabled = true
		button.pressed.connect(_on_equipment_slot_pressed.bind(36 + index))
		button.gui_input.connect(_on_inventory_slot_gui_input.bind(36 + index))
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
			_set_slot_quantity(inventory_quantity_labels[slot],
				int(item.get("quantity", 0)))
			button.tooltip_text = _inventory_tooltip(item, slot)
			button.disabled = false
		else:
			button.icon = null
			button.text = ""
			inventory_quantity_labels[slot].text = ""
			var can_place: bool = (_carried_slot >= 0
				or (selected_inventory_slot >= 0
				and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot)))
			button.tooltip_text = ("Move selected item to slot %d" % (slot + 1)
				if can_place else "Empty inventory slot %d" % (slot + 1))
			# An empty slot stays enabled so that its frame is drawn. Godot
			# renders a disabled button flat, which made the grid vanish
			# whenever nothing was selected: the slots are the shape of the
			# window and belong on screen whether or not they hold anything.
			# Pressing an empty one is already a no-op below.
			button.disabled = false
	_sync_equipment_slots()
	_sync_quick_slots()
	if selected_inventory_slot >= 0:
		var selected_value: Variant = AppState.inventory.get(selected_inventory_slot)
		if selected_value is Dictionary:
			var selected_item: Dictionary = selected_value as Dictionary
			inventory_use_button.tooltip_text = ("Left click uses the item"
				if bool(selected_item.get("inventory_usable", false))
				and _inventory_cooldown_remaining(selected_inventory_slot) <= 0
				else "The selected item cannot be used right now")
		else:
			selected_inventory_slot = -1
	if not AppState.inventory_text.is_empty():
		inventory_description.text = AppState.inventory_text
	if ground_bag_panel.visible:
		_sync_ground_bag_actions()

func _sync_equipment_slots() -> void:
	for index: int in range(equipment_slot_buttons.size()):
		var slot: int = 36 + index
		var button: Button = equipment_slot_buttons[index]
		var item_value: Variant = AppState.inventory.get(slot)
		if item_value is Dictionary:
			var item: Dictionary = item_value as Dictionary
			button.icon = item_atlas.icon_for(int(item.get("image_id", 0)))
			button.text = ""
			button.tooltip_text = _inventory_tooltip(item, slot) + "\nEquipped position %d" % (index + 1)
			button.disabled = false
		else:
			button.icon = null
			button.text = ""
			var can_equip_here: bool = (_carried_slot >= 0
				or (selected_inventory_slot >= 0
				and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot)))
			button.tooltip_text = ("Equip selected item in generic wear position %d" % (index + 1)
				if can_equip_here else "Empty generic equipment position %d" % (index + 1))
			button.disabled = false
	_sync_inventory_tool_buttons()

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
			var quick_tooltip: String = (_inventory_tooltip(quick_item, slot)
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
			inventory_use_button.tooltip_text = ("Left click uses the item"
				if bool(selected_item.get("inventory_usable", false))
				and _inventory_cooldown_remaining(selected_inventory_slot) <= 0
				else "The selected item cannot be used right now")

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
	_sync_spell_power_controls()
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
	var effect: String = str(definition.get("effect", ""))
	if AppState.spell_power.has(effect):
		var stated: Dictionary = AppState.spell_power[effect] as Dictionary
		lines.append("Power %d of %d allowed" % [
			mini(requested_spell_power, int(stated.get("limit", 1))),
			int(stated.get("limit", 1))])
	if reasons.is_empty():
		lines.append("Ready; the server validates the cast")
	else:
		lines.append_array(reasons)
	return "\n".join(lines)

## The power stepper. Its ceiling is the highest limit the server stated for
## any effect: the client never works a limit out from a Magic level, and a
## cast is clamped to the limit the server stated for that effect.
func _sync_spell_power_controls() -> void:
	var ceiling: int = 1
	for raw_effect: Variant in AppState.spell_power:
		var stated: Dictionary = AppState.spell_power[raw_effect] as Dictionary
		ceiling = maxi(ceiling, int(stated.get("limit", 1)))
	requested_spell_power = clampi(requested_spell_power, 1, ceiling)
	spell_power_value.text = "P%d" % requested_spell_power
	spell_power_down.disabled = requested_spell_power <= 1
	spell_power_up.disabled = requested_spell_power >= ceiling

## Saves what is on screen. The legacy client bound this to a dedicated key
## and so does this one; the file goes to the user directory, because a client
## may be installed somewhere it cannot write.
func _save_screenshot() -> String:
	var image: Image = get_viewport().get_texture().get_image()
	if image == null:
		AppState.append_local_line(tr("ELORIA_SCREENSHOT_FAILED").format(
			{"reason": "there is nothing rendered yet"}))
		return ""
	var directory := "user://screenshots"
	DirAccess.make_dir_recursive_absolute(directory)
	var path: String = "%s/eloria-%s.png" % [directory,
		Time.get_datetime_string_from_system(false, true).replace(":", "-")]
	var error: Error = image.save_png(path)
	if error != OK:
		AppState.append_local_line(tr("ELORIA_SCREENSHOT_FAILED").format(
			{"reason": error_string(error)}))
		return ""
	AppState.append_local_line(tr("ELORIA_SCREENSHOT_SAVED").format(
		{"path": ProjectSettings.globalize_path(path)}))
	audio_director.play("ui_click")
	return path

## A client setting the player changed. Everything under Graphics and Camera
## is about this machine; everything under Gameplay is a command the server
## owns, sent as the player's own words rather than applied here.
func _on_client_setting_changed(section: String, key: String,
		value: Variant) -> void:
	if _hud_element_options.has(key) and section == "HUD":
		_hud_element_options[key] = bool(value)
		_apply_hud_element_options()
		_save_hud_settings()
		return
	match key:
		"shadows":
			_shadows_enabled = bool(value)
			world_sun.shadow_enabled = _shadows_enabled and world_sun.visible
		"particles":
			_effects_enabled = bool(value)
		"nameplates":
			_nameplates_enabled = bool(value)
			_apply_banner_options()
		"combat_hud":
			extension_windows.call("set_combat_hud_enabled", bool(value))
		"rotation_sensitivity":
			camera_rig.rotation_sensitivity = float(value)
		"pan_sensitivity":
			camera_rig.pan_sensitivity = float(value)
		"follow_player":
			_camera_follows_player = bool(value)
		"target_mode_strong":
			Network.send_chat("#targetmode strong")
		"target_mode_weak":
			Network.send_chat("#targetmode weak")
		"autogather":
			Network.send_chat("#autogather")
	if section != "Gameplay":
		_save_hud_settings()

func _on_binding_changed(_action: String) -> void:
	_save_hud_settings()
	# The help page is generated from the bindings, so it follows a rebind.
	reference_window.call("_refresh_help")

func _on_notes_changed(text: String) -> void:
	_player_notes = text
	_save_hud_settings()

## A bookmark is the player's own, like a note: it is kept in the client's
## settings file and never goes near the server.
func _on_encyclopedia_bookmarks_changed(bookmarks: Array) -> void:
	_encyclopedia_bookmarks = bookmarks
	_save_hud_settings()

## The encyclopedia icon on the lower HUD, and Ctrl+E. Both open the reference
## window on its encyclopedia page, and close it again from that page.
func _on_encyclopedia_button_pressed() -> void:
	var was_open: bool = bool(reference_window.call("is_encyclopedia_open"))
	reference_window.call("toggle_encyclopedia")
	audio_director.play("ui_close" if was_open else "ui_click")
	_sync_hud_button_states(true)

## Help, the player's notes, the addresses the server has linked, and the
## encyclopedia. Opened from the settings panel beside the other windows.
func _on_reference_pressed() -> void:
	reference_window.toggle()
	audio_director.play("ui_click" if reference_window.is_open() else "ui_close")

## The sigils window. It is opened from the spell quickbar because that is
## where a player finds out they are missing one.
func _on_sigil_button_pressed() -> void:
	sigil_window.toggle()
	audio_director.play("ui_click" if sigil_window.is_open() else "ui_close")

## The Eternal Lands spell book: the icon-row window with the catalog grouped
## the way the legacy client groups it. Casting goes through the same seam the
## quickbar uses, so the two can never disagree about what a cast sends.
func _on_spells_button_pressed() -> void:
	spells_window.toggle()
	audio_director.play("ui_click" if spells_window.is_open() else "ui_close")
	_sync_hud_button_states(true)

func _on_emotes_button_pressed() -> void:
	emotes_window.toggle()
	audio_director.play("ui_click" if emotes_window.is_open() else "ui_close")
	_sync_hud_button_states(true)

func _on_quest_button_pressed() -> void:
	extension_windows.call("toggle_quest_journal")
	_sync_hud_button_states(true)

func _on_ranging_button_pressed() -> void:
	ranging_window.toggle()
	audio_director.play("ui_click" if ranging_window.is_open() else "ui_close")
	_sync_hud_button_states(true)

func _on_console_button_pressed() -> void:
	_toggle_console()
	_sync_hud_button_states(true)

func _on_minimap_button_pressed() -> void:
	_toggle_minimap()
	_sync_hud_button_states(true)

## The reference window's pages behind their Eternal Lands icons: Info is the
## notepad and the link list, Buddy the list the server states, Help the keys
## and commands. Each icon opens its page, or closes the window from that page,
## exactly the way the encyclopedia icon already treats its own.
func _on_info_button_pressed() -> void:
	_toggle_reference_tab(1)

func _on_buddy_button_pressed() -> void:
	_toggle_reference_tab(5)

func _on_help_button_pressed() -> void:
	_toggle_reference_tab(0)

func _toggle_reference_tab(tab: int) -> void:
	var tabs: TabContainer = reference_window.get("tabs") as TabContainer
	var was_here: bool = reference_window.call("is_open") and tabs.current_tab == tab
	if was_here:
		reference_window.call("close")
	else:
		if not reference_window.call("is_open"):
			reference_window.call("toggle")
		tabs.current_tab = tab
	audio_director.play("ui_close" if was_here else "ui_click")
	_sync_hud_button_states(true)

func _reference_tab_open(tab: int) -> bool:
	if reference_window == null or not bool(reference_window.call("is_open")):
		return false
	return (reference_window.get("tabs") as TabContainer).current_tab == tab

## Casts one catalogued spell: the spells window's seam onto the network. The
## same checks the quickbar makes, because it is the same cast.
func _cast_spell_by_id(spell_id: int) -> void:
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
	var error: Error = Network.cast_spell(sigils, _cast_power_for(spell_id))
	if error != OK:
		push_warning("CAST_SPELL failed: " + error_string(error))
	else:
		spell_status.text = "Casting %s…" % str(definition.get("name", "spell"))

## The emote picker's seam onto the network: the same packet `#emote <name>`
## already sends. The server stays the judge of what the name means.
func _perform_emote(emote_name: String) -> void:
	var error: Error = Network.do_emote(emote_name)
	if error != OK:
		push_warning("DO_EMOTE failed: " + error_string(error))

## The reference window's Add buddy button. Asking is a chat command the
## server answers; the list itself only ever changes when the server restates it.
func _on_buddy_add_requested(buddy_name: String) -> void:
	var error: Error = Network.send_chat("#add_buddy " + buddy_name)
	if error != OK:
		push_warning("add_buddy failed: " + error_string(error))

func _on_spell_power_down_pressed() -> void:
	requested_spell_power = maxi(1, requested_spell_power - 1)
	_sync_spells()

func _on_spell_power_up_pressed() -> void:
	requested_spell_power += 1
	_sync_spells()

## The power this cast asks for: the stepper, clamped to what the server said
## this effect may reach. With no stated limit the legacy frame is sent, which
## is the frame without a power byte at all.
func _cast_power_for(spell_id: int) -> int:
	var effect: String = spell_catalog.effect_for(spell_id)
	if not AppState.spell_power.has(effect):
		return 0
	var stated: Dictionary = AppState.spell_power[effect] as Dictionary
	return mini(requested_spell_power, maxi(1, int(stated.get("limit", 1))))

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
	var error: Error = Network.cast_spell(sigils, _cast_power_for(spell_id))
	if error != OK:
		push_warning("CAST_SPELL failed: " + error_string(error))
	else:
		spell_status.text = "Casting %s…" % str(definition.get("name", "spell"))

## Draws each item cooldown as a proportional drain over its quick slot.
## `maximum_msec` came off the wire in every cooldown packet and was stored and
## never read, so a cooldown was a disabled button with a number in a tooltip
## and no sense of how far through it was. Runs every frame: it only moves an
## anchor and sets a label, and a chunky one-second step would defeat the
## point of showing progress at all.
func _update_cooldown_overlays() -> void:
	for slot: int in range(quick_slot_buttons.size()):
		var overlay: Control = _cooldown_overlay(quick_slot_buttons[slot])
		var cooldown_value: Variant = AppState.inventory_cooldowns.get(slot)
		if not cooldown_value is Dictionary:
			overlay.visible = false
			continue
		var cooldown: Dictionary = cooldown_value as Dictionary
		var remaining_msec: int = int(cooldown.get("end_msec", 0)) - Time.get_ticks_msec()
		var maximum_msec: int = maxi(1, int(cooldown.get("maximum_msec", 0)))
		if remaining_msec <= 0:
			overlay.visible = false
			continue
		overlay.visible = true
		# The shade drains from full to empty as the cooldown runs out.
		overlay.anchor_top = 1.0 - clampf(float(remaining_msec) / float(maximum_msec),
			0.0, 1.0)
		var seconds_label: Label = overlay.get_node("Seconds") as Label
		seconds_label.text = str(maxi(1, ceili(float(remaining_msec) / 1000.0)))

func _cooldown_overlay(button: Button) -> Control:
	var existing: Control = button.get_node_or_null("Cooldown") as Control
	if existing != null:
		return existing
	var overlay := ColorRect.new()
	overlay.name = "Cooldown"
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	overlay.color = Color(0.05, 0.06, 0.09, 0.66)
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.visible = false
	button.add_child(overlay)
	var seconds := Label.new()
	seconds.name = "Seconds"
	seconds.mouse_filter = Control.MOUSE_FILTER_IGNORE
	seconds.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	seconds.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	seconds.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(seconds)
	return overlay

func _inventory_cooldown_remaining(slot: int) -> int:
	var cooldown_value: Variant = AppState.inventory_cooldowns.get(slot)
	if not cooldown_value is Dictionary:
		return 0
	var cooldown: Dictionary = cooldown_value as Dictionary
	var remaining_msec: int = int(cooldown.get("end_msec", 0)) - Time.get_ticks_msec()
	return maxi(0, ceili(float(remaining_msec) / 1000.0))

## Builds a slot tooltip. The quantity and the traits always come from the
## authoritative inventory packet; command 226 only adds the names, categories
## and weights that packet has no room for, and is ignored where the two
## disagree about how much is in the slot.
func _inventory_tooltip(item: Dictionary, slot: int) -> String:
	var traits: Array[String] = []
	for flag_and_label: Array in [
		["inventory_usable", "usable"], ["stackable", "stackable"],
		["resource", "resource"], ["reagent", "reagent"]]:
		if bool(item.get(flag_and_label[0], false)):
			traits.append(str(flag_and_label[1]))
	var image_id: int = int(item.get("image_id", 0))
	var described: Dictionary = _inventory_description_for(slot)
	var heading: String = (str(described.get("name", ""))
		if not str(described.get("name", "")).is_empty()
		else "Item image #%d" % image_id)
	var tooltip: String = "%s — quantity %d%s" % [heading,
		int(item.get("quantity", 0)), " — " + ", ".join(traits) if not traits.is_empty() else ""]
	if not str(described.get("category", "")).is_empty():
		tooltip += "
%s — %d EMU each" % [str(described.get("category", "")),
			int(described.get("emu", 0))]
	if item_atlas.uses_substitute(image_id):
		tooltip += "\nIndependent Eloria icon substitute for legacy image #%d." % image_id
	return tooltip

## The command 226 entry for a slot, or an empty dictionary when the server has
## not described that slot.
func _inventory_description_for(slot: int) -> Dictionary:
	for entry: Variant in AppState.inventory_state.get("items", []):
		var described: Dictionary = entry as Dictionary
		if int(described.get("slot", -1)) == slot:
			return described
	return {}

## Walk mode is Eternal Lands' move action, so a click there lifts the item
## onto the cursor instead of only selecting it. Every other mode keeps the
## select-and-inspect behaviour.
## The six quantity boxes along the bottom of the inventory, as the legacy
## client has them: a left click selects one, a right click edits it, and an
## edit left empty falls back to that box's default.
func _build_inventory_quantity_boxes() -> void:
	for index: int in range(INVENTORY_QUANTITY_DEFAULTS.size()):
		var button: Button = Button.new()
		button.custom_minimum_size = Vector2(0.0, 26.0)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.focus_mode = Control.FOCUS_NONE
		button.toggle_mode = true
		button.pressed.connect(_on_quantity_box_pressed.bind(index))
		button.gui_input.connect(_on_quantity_box_gui_input.bind(index))
		inventory_quantity_bar.add_child(button)
		inventory_quantity_buttons.append(button)
	inventory_quantity_edit.max_length = INVENTORY_QUANTITY_DIGITS
	inventory_quantity_edit.text_submitted.connect(_on_quantity_edit_submitted)
	inventory_quantity_edit.focus_exited.connect(_commit_quantity_edit)
	_sync_inventory_quantity_boxes()

func _sync_inventory_quantity_boxes() -> void:
	for index: int in range(inventory_quantity_buttons.size()):
		var button: Button = inventory_quantity_buttons[index]
		button.text = str(_inventory_quantities[index])
		button.set_pressed_no_signal(index == _selected_quantity_box)
		button.tooltip_text = ("Use %d for drops and pick-ups. Right click to change it."
			% _inventory_quantities[index])

## The amount every drop and pick-up uses until the player picks another box.
func _selected_quantity() -> int:
	if _selected_quantity_box < 0 or _selected_quantity_box >= _inventory_quantities.size():
		return 1
	return maxi(1, _inventory_quantities[_selected_quantity_box])

func _on_quantity_box_pressed(index: int) -> void:
	_commit_quantity_edit()
	_selected_quantity_box = index
	_sync_inventory_quantity_boxes()
	_save_hud_settings()

func _on_quantity_box_gui_input(event: InputEvent, index: int) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse: InputEventMouseButton = event as InputEventMouseButton
	if not mouse.pressed or mouse.button_index != MOUSE_BUTTON_RIGHT:
		return
	_begin_quantity_edit(index)
	inventory_quantity_buttons[index].accept_event()

func _begin_quantity_edit(index: int) -> void:
	var button: Button = inventory_quantity_buttons[index]
	_editing_quantity_box = index
	inventory_quantity_edit.text = str(_inventory_quantities[index])
	inventory_quantity_edit.size = button.size
	inventory_quantity_edit.global_position = button.global_position
	inventory_quantity_edit.visible = true
	inventory_quantity_edit.grab_focus()
	inventory_quantity_edit.select_all()

func _on_quantity_edit_submitted(_text: String) -> void:
	_commit_quantity_edit()

## An empty or unreadable box resets to its default rather than becoming zero,
## which would make every later drop a no-op.
func _commit_quantity_edit() -> void:
	var index: int = _editing_quantity_box
	if index < 0:
		return
	_editing_quantity_box = -1
	var typed: String = inventory_quantity_edit.text.strip_edges()
	var value: int = (int(typed) if typed.is_valid_int()
		else INVENTORY_QUANTITY_DEFAULTS[index])
	_inventory_quantities[index] = clampi(value, 1, INVENTORY_QUANTITY_MAX)
	_selected_quantity_box = index
	inventory_quantity_edit.visible = false
	inventory_quantity_edit.release_focus()
	_sync_inventory_quantity_boxes()
	_save_hud_settings()

func _carry_enabled() -> bool:
	return _interaction_mode == "walk"

func _begin_carry(slot: int) -> void:
	var item_value: Variant = AppState.inventory.get(slot)
	if not item_value is Dictionary:
		return
	var item: Dictionary = item_value as Dictionary
	_carried_slot = slot
	carried_item.texture = item_atlas.icon_for(int(item.get("image_id", 0)))
	var quantity: int = int(item.get("quantity", 0))
	(carried_item.get_node("Quantity") as Label).text = (str(quantity)
		if quantity > 1 else "")
	carried_item.visible = true
	_update_carried_item()

func _cancel_carry() -> void:
	_carried_slot = -1
	carried_item.visible = false
	carried_item.texture = null
	_sync_inventory()

func _update_carried_item() -> void:
	if _carried_slot < 0:
		return
	# The server may empty the slot underneath us - a stack consumed, a trade
	# settled - and a cursor still holding a phantom would place nothing.
	if not AppState.inventory.has(_carried_slot):
		_cancel_carry()
		return
	carried_item.global_position = (get_viewport().get_mouse_position()
		- carried_item.size * 0.5)

## Answers the placing click. Equipping, unequipping and reordering are all the
## same authoritative move; only the destination slot differs, and the server
## decides whether it is allowed.
func _place_carry(destination: int) -> void:
	var source: int = _carried_slot
	if source < 0 or source == destination:
		_cancel_carry()
		return
	_carried_slot = -1
	carried_item.visible = false
	carried_item.texture = null
	_move_inventory_item(source, destination)
	_sync_inventory()

## Clicking the world puts the stack down. The server answers by creating a
## bag on the tile, or by adding to the bag already standing there.
func _drop_carry() -> void:
	var source: int = _carried_slot
	if source < 0:
		return
	var item_value: Variant = AppState.inventory.get(source)
	_carried_slot = -1
	carried_item.visible = false
	carried_item.texture = null
	if not item_value is Dictionary:
		_sync_inventory()
		return
	var available: int = maxi(1, int((item_value as Dictionary).get("quantity", 1)))
	var quantity: int = (available if Input.is_key_pressed(KEY_CTRL)
		else mini(available, _selected_quantity()))
	var error: Error = Network.drop_inventory_item(source, quantity)
	if error != OK:
		push_warning("DROP_ITEM failed: " + error_string(error))
	_sync_inventory()

func _on_inventory_slot_pressed(slot: int) -> void:
	if _carried_slot >= 0:
		_place_carry(slot)
		return
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 44
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	_apply_inventory_tool(slot)
	_sync_equipment_slots()
	_sync_inventory()

## Carries out the current tool on a slot. Every tool ends by asking the server
## what the item is, because the line along the bottom of the window should say
## what was last touched whichever tool was in hand; only Inspect lets the
## answer open the detail window.
func _apply_inventory_tool(slot: int) -> void:
	match _inventory_tool:
		"use":
			if slot < 36:
				_use_inventory_slot(slot)
		"equip":
			if slot < 36:
				var wear: int = _first_empty_slot(36, 44)
				if wear >= 0:
					_move_inventory_item(slot, wear)
		"unequip":
			if slot >= 36:
				var carry: int = _first_empty_slot(0, 36)
				if carry >= 0:
					_move_inventory_item(slot, carry)
		"grab":
			if _carry_enabled():
				_begin_carry(slot)
	_describe_slot(slot, _inventory_tool == "inspect")

## Asks the server what an item is. `with_window` decides whether the reply is
## allowed to open the detail window; the short line is written either way.
func _describe_slot(slot: int, with_window: bool) -> void:
	_detail_popup_allowed = with_window
	if extension_windows != null:
		extension_windows.set("detail_popup_allowed", with_window)
	inventory_description.text = "[%s]  Asking about slot %d…" % [
		str(INVENTORY_TOOL_LABELS.get(_inventory_tool, _inventory_tool)), slot + 1]
	var error: Error = Network.look_at_inventory_item(slot)
	if error != OK:
		push_warning("LOOK_AT_INVENTORY_ITEM failed: " + error_string(error))

## Right-clicking an item takes the next tool and describes what is under the
## cursor without opening anything, so the player can see what the new tool
## would act on before using it.
func _cycle_inventory_tool(slot: int) -> void:
	var index: int = INVENTORY_TOOLS.find(_inventory_tool)
	_set_inventory_tool(INVENTORY_TOOLS[(index + 1) % INVENTORY_TOOLS.size()])
	if AppState.inventory.has(slot):
		selected_inventory_slot = slot
		_describe_slot(slot, false)
	_sync_inventory()

## The four action buttons are the same mechanism as the right-click cycle:
## each one takes its tool, and applies it at once to whatever is already
## selected, so a player can work either way round.
func _choose_inventory_tool(tool: String) -> void:
	_set_inventory_tool(tool)
	if selected_inventory_slot >= 0 and AppState.inventory.has(selected_inventory_slot):
		_apply_inventory_tool(selected_inventory_slot)
	_sync_inventory()

func _set_inventory_tool(tool: String) -> void:
	_inventory_tool = tool
	_sync_inventory_tool_buttons()

## The buttons show which tool is in hand, since the cursor does not change.
func _sync_inventory_tool_buttons() -> void:
	for pair: Array in [[inventory_use_button, "use"],
			[inventory_equip_button, "equip"],
			[inventory_unequip_button, "unequip"],
			[inventory_inspect_button, "inspect"]]:
		var button: Button = pair[0] as Button
		if button != null:
			button.button_pressed = _inventory_tool == str(pair[1])

func _on_inventory_slot_gui_input(event: InputEvent, slot: int) -> void:
	if not event is InputEventMouseButton:
		return
	var mouse: InputEventMouseButton = event as InputEventMouseButton
	if mouse.button_index != MOUSE_BUTTON_RIGHT or not mouse.pressed:
		return
	_cycle_inventory_tool(slot)
	get_viewport().set_input_as_handled()

## Composes the one-line summary written along the bottom of the inventory when
## the server describes an item. It reports only what arrived in the reply.
func _short_item_line() -> String:
	var detail: Dictionary = AppState.item_detail
	var parts: Array[String] = []
	var item_name: String = str(detail.get("name", ""))
	if not item_name.is_empty():
		parts.append(item_name)
	var category: String = str(detail.get("category", ""))
	if not category.is_empty():
		parts.append(category)
	var quantity: int = int(detail.get("quantity", 0))
	if quantity > 1:
		parts.append("x%s" % _grouped(quantity))
	if bool(detail.get("equipped", false)):
		parts.append("equipped")
	if parts.is_empty():
		return ""
	return "[%s]  %s" % [
		str(INVENTORY_TOOL_LABELS.get(_inventory_tool, _inventory_tool)),
		"  -  ".join(parts)]

func _on_equipment_slot_pressed(slot: int) -> void:
	if _carried_slot >= 0:
		_place_carry(slot)
		return
	if not AppState.inventory.has(slot):
		if (selected_inventory_slot >= 0 and selected_inventory_slot < 36
				and AppState.inventory.has(selected_inventory_slot)):
			_move_inventory_item(selected_inventory_slot, slot)
		return
	selected_inventory_slot = slot
	_apply_inventory_tool(slot)
	_sync_equipment_slots()
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

## Console history and tab completion. Up and down walk what has been sent,
## Tab completes a command this client answers itself - a name the server owns
## is not completed here, because the client does not have that list.
func _on_chat_input_gui_input(event: InputEvent) -> void:
	if not event is InputEventKey or not (event as InputEventKey).pressed:
		return
	var key: InputEventKey = event as InputEventKey
	match key.physical_keycode:
		KEY_UP:
			_recall_console_history(-1)
		KEY_DOWN:
			_recall_console_history(1)
		KEY_TAB:
			_complete_console_command()
		_:
			return
	chat_input.accept_event()

func _recall_console_history(step: int) -> void:
	if _console_history.is_empty():
		return
	_console_history_index = clampi(_console_history_index + step, 0,
		_console_history.size())
	chat_input.text = ("" if _console_history_index >= _console_history.size()
		else _console_history[_console_history_index])
	chat_input.caret_column = chat_input.text.length()

func _complete_console_command() -> void:
	var typed: String = chat_input.text.strip_edges()
	if not typed.begins_with("#") or typed.contains(" "):
		return
	var matches: Array[String] = console_commands.completions(typed)
	if matches.is_empty():
		return
	if matches.size() == 1:
		chat_input.text = matches[0] + " "
		chat_input.caret_column = chat_input.text.length()
		return
	# More than one: complete as far as they agree and show the choices.
	var shared: String = matches[0]
	for candidate: String in matches:
		while not candidate.begins_with(shared) and shared.length() > typed.length():
			shared = shared.substr(0, shared.length() - 1)
	chat_input.text = shared
	chat_input.caret_column = shared.length()
	AppState.append_local_line("  ".join(matches))

func _on_chat_submitted(text: String) -> void:
	var message: String = text.strip_edges()
	if message.is_empty():
		chat_input.release_focus()
		return
	_console_history.append(message)
	if _console_history.size() > CONSOLE_HISTORY_LIMIT:
		_console_history.remove_at(0)
	_console_history_index = _console_history.size()
	message = console_commands.expand(message)
	# A command this client answers itself never reaches the server: the
	# server has no opinion about who the player is ignoring.
	var local: ConsoleCommands.Result = console_commands.run(
		message, AppState.chat_lines)
	if local.handled:
		for line: String in local.lines:
			AppState.append_local_line(line)
		if local.changed:
			_save_hud_settings()
			_sync_map_markers()
		chat_input.clear()
		return
	# `#emote <name>` is the server's command, but it has a packet of its own,
	# so the client sends that rather than the text. The server answers the
	# typed form too, for a client that has no `DO_EMOTE`.
	if message.begins_with("#emote "):
		var wanted: String = message.substr(7).strip_edges()
		if not wanted.is_empty():
			var emote_error: Error = Network.do_emote(wanted)
			if emote_error == OK:
				chat_input.clear()
			else:
				push_warning("DO_EMOTE failed: " + error_string(emote_error))
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
		# Source type 1 is the offering player's backpack and 2 is their
		# storage, which is only offered where a storage NPC is in range for
		# both sides. Saying which it came from is the whole point of the
		# server sending it.
		var source: String = "  (storage)" if int(item.get("source_type", 1)) == 2 else ""
		list_control.add_item("%s %d  •  item #%d  ×%d%s" % [
			prefix, slot + 1, image_id, int(item.get("quantity", 0)), source])
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
			("  [combat]" if bool(dto.get("in_combat", false)) else "")
				+ ("  [hastened]" if (int(dto.get("buffs", 0))
					& EloriaProtocol.ACTOR_BUFF_DOUBLE_SPEED) != 0 else "")]
	var local_actor: Dictionary = AppState.actors.get(
		AppState.local_actor_id, {}) as Dictionary
	var aiming_at: int = int(local_actor.get("aiming_at", -1))
	if aiming_at >= 0:
		var aimed: Dictionary = AppState.actors.get(aiming_at, {}) as Dictionary
		selected_target.text = "Aiming at %s%s" % [
			str(aimed.get("name", "actor %d" % aiming_at)),
			"  Health: %d / %d" % [int(aimed.get("health", 0)),
				int(aimed.get("max_health", 0))] if not aimed.is_empty() else ""]
	var can_attack: bool = _is_attackable_actor(AppState.selected_actor_id, dto)
	attack_button.disabled = not can_attack
	attack_button.tooltip_text = ("Attack selected target [A] or Alt-click; the server approaches and validates combat"
		if can_attack else "Select a living player or creature to attack")
	var can_trade: bool = _is_tradeable_player(AppState.selected_actor_id, dto)
	look_button.disabled = not can_trade
	look_button.tooltip_text = ("Ask the server to describe the selected player"
		if can_trade else "Select a player to look at")
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

## A server-driven modal question. The server had no way to ask the player
## anything at all: DISPLAY_POPUP(83) fell through to an unknown packet and
## POPUP_REPLY(50) had no encoder.
##
## The legacy contract decides the shape: a popup that contains a radio option
## or a text entry gets a send button and answers when it is pressed; one
## built only from text options answers the moment a button is clicked and
## closes, because each option *is* the action.
func _sync_popup() -> void:
	for child: Node in popup_options.get_children():
		if is_instance_valid(child):
			child.queue_free()
	_popup_radio_groups.clear()
	_popup_entries.clear()
	if not bool(AppState.popup.get("open", false)):
		popup_panel.hide()
		return
	popup_title.text = str(AppState.popup.get("title", "")).strip_edges()
	popup_text.text = str(AppState.popup.get("text", ""))
	var needs_confirm := false
	var radio_buttons: Dictionary = {}
	for raw_option: Variant in AppState.popup.get("options", []) as Array:
		var option: Dictionary = raw_option as Dictionary
		var option_type: int = int(option.get("option_type", -1))
		var group: int = int(option.get("group", 0))
		var label: String = str(option.get("label", ""))
		match option_type:
			EloriaProtocol.POPUP_DISPLAY_TEXT:
				var display := Label.new()
				display.text = label
				display.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
				popup_options.add_child(display)
			EloriaProtocol.POPUP_TEXT_OPTION:
				var action := Button.new()
				action.text = label
				action.pressed.connect(_on_popup_option_pressed.bind(
					group, int(option.get("value", 0))))
				popup_options.add_child(action)
			EloriaProtocol.POPUP_RADIO_OPTION:
				needs_confirm = true
				var choice := CheckBox.new()
				choice.text = label
				choice.toggled.connect(_on_popup_radio_toggled.bind(
					group, int(option.get("value", 0))))
				popup_options.add_child(choice)
				var siblings: Array = radio_buttons.get(group, []) as Array
				siblings.append(choice)
				radio_buttons[group] = siblings
			EloriaProtocol.POPUP_TEXT_ENTRY:
				needs_confirm = true
				var prompt := Label.new()
				prompt.text = label
				popup_options.add_child(prompt)
				var entry := LineEdit.new()
				entry.max_length = 255
				popup_options.add_child(entry)
				_popup_entries[group] = entry
	_popup_radio_buttons = radio_buttons
	popup_confirm.visible = needs_confirm
	# A dismissable popup is not the same as an answered one: dismissing sends
	# nothing, which is what the legacy client does when a popup is closed.
	popup_dismiss.visible = true
	_close_panels_for_popup()
	popup_panel.show()
	popup_panel.move_to_front()

## The popup is modal, so the windows that own the keyboard or the pointer are
## closed underneath it rather than left fighting for input.
func _close_panels_for_popup() -> void:
	full_map.hide()
	console_panel.hide()
	_close_settings()
	item_lists_panel.hide()
	_sync_map_viewport_activity()

func _on_popup_radio_toggled(pressed: bool, group: int, value: int) -> void:
	if not pressed:
		if int(_popup_radio_groups.get(group, -1)) == value:
			_popup_radio_groups.erase(group)
		return
	_popup_radio_groups[group] = value
	# One selection per group: the wire carries exactly one answer per group.
	var index := 0
	for raw_button: Variant in _popup_radio_buttons.get(group, []) as Array:
		var button: CheckBox = raw_button as CheckBox
		var option_value: int = _popup_radio_value(group, index)
		if option_value != value and button.button_pressed:
			button.set_pressed_no_signal(false)
		index += 1

func _popup_radio_value(group: int, index: int) -> int:
	var seen := 0
	for raw_option: Variant in AppState.popup.get("options", []) as Array:
		var option: Dictionary = raw_option as Dictionary
		if int(option.get("option_type", -1)) != EloriaProtocol.POPUP_RADIO_OPTION:
			continue
		if int(option.get("group", 0)) != group:
			continue
		if seen == index:
			return int(option.get("value", 0))
		seen += 1
	return -1

func _on_popup_option_pressed(group: int, value: int) -> void:
	_send_popup_reply({group: value})

func _on_popup_confirm_pressed() -> void:
	var answers: Dictionary = {}
	for raw_group: Variant in _popup_radio_groups:
		answers[int(raw_group)] = int(_popup_radio_groups[raw_group])
	for raw_group: Variant in _popup_entries:
		var entry: LineEdit = _popup_entries[raw_group] as LineEdit
		if is_instance_valid(entry):
			answers[int(raw_group)] = entry.text
	_send_popup_reply(answers)

## Dismissing answers nothing. The server asked; declining to answer is a
## legitimate outcome and must not be reported as a choice.
func _on_popup_dismiss_pressed() -> void:
	AppState.close_popup()

func _send_popup_reply(answers: Dictionary) -> void:
	var popup_id: int = int(AppState.popup.get("popup_id", -1))
	if popup_id < 0:
		return
	var error: Error = Network.popup_reply(popup_id, answers)
	if error != OK:
		push_warning("POPUP_REPLY failed: " + error_string(error))
		return
	AppState.close_popup()

func _sync_dialogue() -> void:
	var dialogue: Dictionary = AppState.npc_dialogue
	dialogue_panel.visible = bool(dialogue.get("open", false))
	if not dialogue_panel.visible:
		return
	# Dialogue the server flagged as belonging to a quest is marked as such,
	# which is the whole point of the flag: a player could not previously tell
	# a quest line from small talk, and neither could this client.
	var quest_id: int = int(dialogue.get("quest_id", 0))
	dialogue_name.text = ("%s  [Quest %d]" % [str(dialogue.get("name", "NPC")),
		quest_id] if bool(dialogue.get("quest", false)) and quest_id > 0
		else str(dialogue.get("name", "NPC")))
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

## World objects the server declared for this map. This is the pick layer the
## client never had: the world click handler tried actors, then ground bags,
## then the navigation surface, and stopped, so no rendered prop was ever
## clickable and the whole harvestable layer was unreachable.
func _pick_map_object(viewport_position: Vector2) -> MapObject3D:
	if gameplay_world == null:
		return null
	var origin: Vector3 = camera_rig.ray_origin(viewport_position)
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		origin, origin + camera_rig.ray_direction(viewport_position) * 2000.0,
		MapObject3D.PICK_LAYER)
	var hit: Dictionary = gameplay_world.direct_space_state.intersect_ray(query)
	var collider_value: Variant = hit.get("collider")
	return collider_value as MapObject3D if collider_value is MapObject3D else null

## A plain click acts on the object; Alt inspects it instead. Every outcome is
## a request: the server decides range, tools, level and whether anything
## happens at all.
func _activate_map_object(map_object: MapObject3D, inspect: bool) -> void:
	if inspect:
		var look_error: Error = Network.look_at_map_object(map_object.object_id)
		if look_error != OK:
			push_warning("LOOK_AT_MAP_OBJECT failed: " + error_string(look_error))
		return
	if map_object.is_harvestable():
		# HARVEST is a toggle on the server: sending it for the node already
		# being harvested stops the run.
		var harvest_error: Error = Network.harvest(map_object.object_id)
		if harvest_error != OK:
			push_warning("HARVEST failed: " + error_string(harvest_error))
		return
	var use_error: Error = Network.use_map_object(map_object.object_id)
	if use_error != OK:
		push_warning("USE_MAP_OBJECT failed: " + error_string(use_error))

func _sync_map_objects() -> void:
	for raw_id: Variant in map_object_nodes.keys():
		var object_id: int = int(raw_id)
		if not AppState.map_objects.has(object_id):
			var stale: Variant = map_object_nodes.get(object_id)
			if is_instance_valid(stale):
				(stale as Node).queue_free()
			map_object_nodes.erase(object_id)
	for raw_id: Variant in AppState.map_objects:
		var object_id: int = int(raw_id)
		var dto_value: Variant = AppState.map_objects.get(object_id)
		if not dto_value is Dictionary:
			continue
		if map_object_nodes.has(object_id):
			continue
		var map_object := MapObject3D.new()
		map_object.configure(dto_value as Dictionary, adapter)
		world_root.add_child(map_object)
		map_object_nodes[object_id] = map_object
		_place_map_object_on_surface(map_object)
	_sync_harvest_indicator()

## Draws the markers the server placed for the map the player is standing on.
##
## A marker keeps its map: the server states which map each belongs to and never
## withdraws one because the player walked elsewhere, so a marker for another
## map is held and hidden rather than discarded and guessed at again later.
func _sync_map_markers() -> void:
	# Both sides are reduced the same way: the marker names its map as the
	# server's own file reference, and CHANGE_MAP names the current one the
	# same way, so neither is compared to a path the other never uses.
	var here: String = EloriaProtocol.map_id_from_reference(AppState.current_map)
	for raw_id: Variant in map_marker_nodes.keys():
		var marker_id: int = int(raw_id)
		var marker_value: Variant = AppState.map_markers.get(marker_id)
		var still_here: bool = (marker_value is Dictionary
			and str((marker_value as Dictionary).get("map_id", "")) == here)
		if still_here:
			continue
		var stale: Variant = map_marker_nodes.get(marker_id)
		if is_instance_valid(stale):
			(stale as Node).queue_free()
		map_marker_nodes.erase(marker_id)
	for raw_id: Variant in AppState.map_markers:
		var marker_id: int = int(raw_id)
		if map_marker_nodes.has(marker_id):
			continue
		var dto_value: Variant = AppState.map_markers.get(marker_id)
		if not dto_value is Dictionary:
			continue
		var dto: Dictionary = dto_value as Dictionary
		if str(dto.get("map_id", "")) != here:
			continue
		var marker := MapMarker3D.new()
		marker.configure(dto, adapter)
		world_root.add_child(marker)
		map_marker_nodes[marker_id] = marker
		_place_map_marker_on_surface(marker)
	_sync_map_marker_list()

## The pins are readable as shapes on both map cameras, but a full map covers a
## whole map: no label drawn at that scale can be read. The sidebar lists what
## each pin is, in the server's own words, beside the legend that explains the
## rest of the map.
func _sync_map_marker_list() -> void:
	var lines: Array[String] = []
	for raw_id: Variant in map_marker_nodes:
		var marker: Variant = map_marker_nodes[raw_id]
		if not is_instance_valid(marker):
			continue
		var pin: MapMarker3D = marker as MapMarker3D
		lines.append("[color=#fac638]◆[/color] %s  (%d, %d)" % [
			pin.label if not pin.label.is_empty() else "Marker",
			pin.server_tile.x, pin.server_tile.y])
	for mark: Dictionary in console_commands.marks:
		if str(mark.get("map", "")) != EloriaProtocol.map_id_from_reference(
				AppState.current_map):
			continue
		lines.append("[color=#7fd4ff]*[/color] %s  (%d, %d)" % [
			str(mark.get("label", "Mark")), int(mark.get("x", 0)),
			int(mark.get("y", 0))])
	map_marker_list.text = "
".join(lines)
	map_marker_title.visible = not lines.is_empty()
	map_marker_list.visible = not lines.is_empty()
	map_marker_overlay.set_markers(_current_map_markers())
	map_marker_overlay.set_player_marks(_current_player_marks())

## The marks the player made for themselves on this map. Presentational: they
## are the player's own annotation of their own screen, they never leave the
## client, and the server is not told about them.
func _current_player_marks() -> Array[Dictionary]:
	var here: String = EloriaProtocol.map_id_from_reference(AppState.current_map)
	var mine: Array[Dictionary] = []
	for mark: Dictionary in console_commands.marks:
		if str(mark.get("map", "")) == here:
			mine.append(mark)
	return mine

## The markers the server placed on the map the player is standing on.
func _current_map_markers() -> Array[Dictionary]:
	var here: String = EloriaProtocol.map_id_from_reference(AppState.current_map)
	var markers: Array[Dictionary] = []
	for raw_id: Variant in AppState.map_markers:
		var marker_value: Variant = AppState.map_markers[raw_id]
		if not marker_value is Dictionary:
			continue
		var marker: Dictionary = marker_value as Dictionary
		if str(marker.get("map_id", "")) == here:
			markers.append(marker)
	return markers

func _place_map_marker_on_surface(marker: MapMarker3D) -> void:
	if not is_instance_valid(marker):
		return
	var sampled: Variant = _navigation_ray_position(
		marker.global_position + Vector3(0.0, 200.0, 0.0), Vector3.DOWN)
	if sampled is Vector3:
		marker.set_surface_height((sampled as Vector3).y)

## Grounds one world object, and notices when it cannot be grounded at all.
##
## A server object whose tile has no navigation surface under it is misplaced
## content: the server is describing somewhere the rendered map does not have.
## That is worth counting rather than leaving as an invisible marker hanging in
## the air, so it appears in the protocol diagnostics panel.
func _place_map_object_on_surface(map_object: MapObject3D) -> void:
	if not is_instance_valid(map_object):
		return
	var sampled: Variant = _navigation_ray_position(
		map_object.global_position + Vector3(0.0, 200.0, 0.0), Vector3.DOWN)
	if sampled is Vector3:
		map_object.set_surface_height((sampled as Vector3).y)
		_ungrounded_map_objects.erase(map_object.object_id)
		return
	_ungrounded_map_objects[map_object.object_id] = map_object.label

func _snap_all_map_objects_to_surface() -> void:
	await get_tree().physics_frame
	for raw_object: Variant in map_object_nodes.values():
		_place_map_object_on_surface(raw_object as MapObject3D)
	for raw_marker: Variant in map_marker_nodes.values():
		_place_map_marker_on_surface(raw_marker as MapMarker3D)

## The "now harvesting" indicator. The stock client drove this by matching an
## exact English phrase out of the chat stream; this reads the authoritative
## harvest-state packet instead, so it survives a reworded message and cannot
## be left stuck on when the server stops the run for its own reasons - moving,
## a full backpack, or combat.
func _sync_harvest_indicator() -> void:
	_sync_hud_indicators()
	var active: bool = bool(AppState.harvest.get("active", false))
	var active_object: int = int(AppState.harvest.get("object_id", -1))
	for raw_object: Variant in map_object_nodes.values():
		var map_object: MapObject3D = raw_object as MapObject3D
		if is_instance_valid(map_object):
			map_object.set_active(active and map_object.object_id == active_object)
	if harvest_banner == null:
		return
	if not active:
		harvest_banner.hide()
		return
	harvest_banner.text = "Harvesting %s" % str(AppState.harvest.get("resource", ""))
	harvest_banner.show()

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
	# The master leaves 76 transparent pixels down each side of its 512-wide
	# canvas. Drawn whole into the rail's 62-pixel frame the crest came out at
	# three quarters width with the frame looking half empty, so the HUD copy
	# is cropped to the painted area and fills the frame edge to edge.
	if logo_texture == null:
		hud_logo.texture = null
	else:
		hud_logo.texture = _atlas_region(logo_texture, Rect2(76, 0, 360, 256))
	_hud_active_atlas = _external_texture("res://assets/ui/eloria_gamebuttons.png")
	_hud_inactive_atlas = _external_texture("res://assets/ui/eloria_gamebuttons_inactive.png")
	if _hud_active_atlas != null:
		# The Godot HUD atlas uses one canonical row-major icon order.  Keeping
		# these regions contiguous makes the art easy to audit and prevents the
		# legacy atlas's highlighted-state pairs from being mistaken for actions.
		_hud_icon_regions = {
			%WalkButton: Rect2(0, 0, 32, 32), %ChatButton: Rect2(32, 0, 32, 32),
			%LookButton: Rect2(64, 0, 32, 32),
			%KnowledgeButton: Rect2(96, 0, 32, 32), %AttackButton: Rect2(128, 0, 32, 32),
			%StatsButton: Rect2(160, 0, 32, 32),
			%DisconnectButton: Rect2(192, 0, 32, 32), %SitButton: Rect2(224, 0, 32, 32),
			%TradeButton: Rect2(0, 32, 32, 32), %InventoryButton: Rect2(32, 32, 32, 32),
			%ManufacturingButton: Rect2(64, 32, 32, 32),
			%EncyclopediaButton: Rect2(96, 32, 32, 32),
			%MapButton: Rect2(128, 32, 32, 32),
			%SpellsButton: Rect2(192, 32, 32, 32), %EmotesButton: Rect2(224, 32, 32, 32),
			%QuestButton: Rect2(0, 64, 32, 32), %InfoButton: Rect2(32, 64, 32, 32),
			%BuddyButton: Rect2(64, 64, 32, 32), %ConsoleButton: Rect2(96, 64, 32, 32),
			%HelpButton: Rect2(128, 64, 32, 32), %OptionsButton: Rect2(160, 64, 32, 32),
			%RangingButton: Rect2(192, 64, 32, 32), %MinimapButton: Rect2(224, 64, 32, 32)}
		for button_value: Variant in _hud_icon_regions:
			var icon_button: Button = button_value as Button
			icon_button.icon = _atlas_region(_hud_active_atlas,
				_hud_icon_regions[button_value] as Rect2)
			icon_button.text = ""
			icon_button.expand_icon = true
			icon_button.icon_alignment = HORIZONTAL_ALIGNMENT_CENTER
			icon_button.vertical_icon_alignment = VERTICAL_ALIGNMENT_CENTER
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

## The window chrome is Eternal Lands' (elwindows.c): near-black bodies, a
## one-pixel gui_color border, hover fills in the inverse colour. The old
## blue-teal boxes read as another game's UI next to the legacy client.
##
## The bodies are opaque, which is Eternal Lands' own "Use Opaque Window
## Backgrounds" option rather than its default. Nameplates are Label3D drawn
## inside the world viewport, so a translucent window cannot cover one: every
## name and health bar behind a window read straight through it and fought
## with the text on top. Opaque is what puts a window in front of them.
func _apply_eloria_theme() -> void:
	var eloria_theme: Theme = Theme.new()
	var panel: StyleBoxFlat = StyleBoxFlat.new()
	panel.bg_color = Color(0.043, 0.034, 0.024, 1.0)
	panel.border_color = Color(EL_GUI_COLOUR, 0.95)
	panel.set_border_width_all(1)
	panel.corner_radius_top_left = 1
	panel.corner_radius_top_right = 1
	panel.corner_radius_bottom_left = 1
	panel.corner_radius_bottom_right = 1
	panel.set_content_margin_all(4.0)
	eloria_theme.set_stylebox("panel", "PanelContainer", panel)
	var button: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	button.bg_color = Color(0.03, 0.02, 0.01, 0.55)
	button.set_border_width_all(1)
	button.set_content_margin_all(4.0)
	eloria_theme.set_stylebox("normal", "Button", button)
	var button_hover: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	button_hover.bg_color = Color(EL_GUI_INVERT_COLOUR, 0.95)
	button_hover.border_color = EL_GUI_BRIGHT_COLOUR
	eloria_theme.set_stylebox("hover", "Button", button_hover)
	eloria_theme.set_stylebox("pressed", "Button", button_hover)
	var field: StyleBoxFlat = button.duplicate() as StyleBoxFlat
	field.bg_color = Color(0.02, 0.015, 0.01, 0.85)
	eloria_theme.set_stylebox("normal", "LineEdit", field)
	eloria_theme.set_color("font_color", "Label", Color(0.91, 0.86, 0.70))
	eloria_theme.set_color("font_color", "Button", Color(0.93, 0.80, 0.58))
	theme = eloria_theme
	# Eternal Lands draws chat straight over the world with no box at all;
	# each line carries its own outline for legibility instead.
	chat_panel.add_theme_stylebox_override("panel", StyleBoxEmpty.new())
	chat_output.add_theme_constant_override("outline_size", 3)
	chat_output.add_theme_color_override("font_outline_color", Color(0.0, 0.0, 0.0, 0.9))
	chat_output.add_theme_color_override("default_color", Color(0.95, 0.94, 0.9))
	_style_right_rail(panel)
	var minimap_panel_style: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	minimap_panel_style.set_border_width_all(6)
	minimap_panel_style.border_color = Color(0.86, 0.64, 0.25, 1.0)
	minimap_frame.add_theme_stylebox_override("panel", minimap_panel_style)
	var map_sidebar_style: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	map_sidebar_style.bg_color = Color(0.0, 0.0, 0.0, 0.98)
	($GameView/FullMap/MapLayout/Sidebar as PanelContainer).add_theme_stylebox_override(
		"panel", map_sidebar_style)
	# Each icon carries its own painted frame right up to the edge of its
	# 32-pixel cell, so with no margin at all the frames butted against each
	# other and against the panel border, and the end ones read as cut off.
	var empty_button: StyleBoxEmpty = StyleBoxEmpty.new()
	empty_button.set_content_margin_all(HUD_ICON_PADDING)
	# An open window used to be told apart by its icon being the coloured one.
	# Now that every icon the player can actually use is coloured, the open
	# window needs a mark of its own, so it takes the lit frame Eternal Lands
	# gives a highlighted icon.
	var active_icon := StyleBoxFlat.new()
	active_icon.bg_color = Color(EL_GUI_INVERT_COLOUR, 0.95)
	active_icon.border_color = EL_GUI_BRIGHT_COLOUR
	active_icon.set_border_width_all(1)
	active_icon.set_content_margin_all(HUD_ICON_PADDING)
	var hover_icon: StyleBoxFlat = active_icon.duplicate() as StyleBoxFlat
	hover_icon.bg_color = Color(EL_GUI_INVERT_COLOUR, 0.5)
	hover_icon.border_color = Color(EL_GUI_COLOUR, 0.75)
	for child: Node in $GameView/Quickbar/QuickRows/Buttons.get_children():
		if child is Button:
			var icon_button: Button = child as Button
			icon_button.flat = true
			icon_button.focus_mode = Control.FOCUS_NONE
			# Twenty-three icons share the bar now, so each cell is trimmed to
			# what fits; the icons are still 40px against Eternal Lands' 32.
			icon_button.custom_minimum_size = Vector2(
				40.0 + HUD_ICON_PADDING * 2.0, 40.0 + HUD_ICON_PADDING * 2.0)
			for state_name: String in ["normal", "disabled", "focus"]:
				icon_button.add_theme_stylebox_override(state_name, empty_button)
			icon_button.add_theme_stylebox_override("hover", hover_icon)
			for state_name: String in ["pressed", "hover_pressed"]:
				icon_button.add_theme_stylebox_override(state_name, active_icon)
	for quick_button: Button in quick_slot_buttons + spell_slot_buttons:
		quick_button.focus_mode = Control.FOCUS_NONE
	_style_meter(health_bar, Color(0.17, 0.82, 0.22, 1.0))
	_style_meter(health_bottom, Color(0.9, 0.16, 0.14, 1.0))
	_style_meter(food_bottom, Color(0.96, 0.78, 0.16, 1.0))
	_style_meter(load_bottom, Color(0.62, 0.43, 0.34, 1.0))
	_style_meter(experience_bottom, Color(0.18, 0.76, 0.22, 1.0))
	for ether_bar: ProgressBar in [mana_bar, ether_bottom]:
		_style_meter(ether_bar, Color(0.24, 0.31, 1.0, 1.0))
	for points_bar: ProgressBar in [action_bar, action_bottom]:
		_style_meter(points_bar, Color(0.73, 0.28, 0.86, 1.0))
	for row_spec: Array in BANNER_ROWS:
		_style_banner_meter(_banner_row(str(row_spec[0])).get_node("Bar") as ProgressBar)
	_style_actor_hud_menu(panel)

## The right rail used to be six separate boxes with gaps between them, so its
## left edge was six short lines rather than one. One panel now spans the whole
## height behind them and owns the only border; everything sitting in it is
## given a flat, marginless box so the rail reads as a single connected bar and
## the offsets in the scene place content exactly.
func _style_right_rail(panel: StyleBoxFlat) -> void:
	# The rail and the bottom bar are the two opaque fixtures of Eternal
	# Lands' HUD - its wooden frame - so unlike the windows they get a solid
	# warm brown rather than the see-through black.
	var rail_style: StyleBoxFlat = panel.duplicate() as StyleBoxFlat
	rail_style.bg_color = Color(0.16, 0.12, 0.075, 0.99)
	rail_style.set_content_margin_all(4.0)
	right_rail.add_theme_stylebox_override("panel", rail_style)
	(%Quickbar as PanelContainer).add_theme_stylebox_override(
		"panel", rail_style.duplicate() as StyleBoxFlat)
	var seamless: StyleBoxEmpty = StyleBoxEmpty.new()
	for framed: Control in [$GameView/EloriaLogoFrame as Control,
			$GameView/SpellQuickbar as Control, $GameView/ItemQuickbar as Control,
			$GameView/ResourceHud as Control, $GameView/RailMeters as Control,
			$GameView/ClockFrame as Control,
			$GameView/CompassFrame as Control]:
		framed.add_theme_stylebox_override("panel", seamless)
	# A rail 62 pixels wide has no room for the theme's 4-pixel button padding
	# four times over: the power row measured 67 and pushed the whole spell
	# column back out of the rail it is supposed to sit in.
	var tight: StyleBoxEmpty = StyleBoxEmpty.new()
	tight.set_content_margin_all(1.0)
	for control: Button in [%SigilButton as Button, %SpellPowerDown as Button,
			%SpellPowerUp as Button]:
		for state: String in ["normal", "hover", "pressed", "disabled", "focus"]:
			control.add_theme_stylebox_override(state, tight)
	# The slot placeholders are "S12" and "8", not labels anyone reads. At the
	# theme size they filled a 26-pixel cell on their own. Read off the scene
	# rather than the bound arrays, which are filled after the theme is applied.
	for column: Node in [quick_slot_container as Node, spell_slot_container as Node]:
		for slot: Node in column.get_children():
			if slot is Button:
				(slot as Button).add_theme_font_size_override("font_size", 9)

## The overhead bars are not the HUD's bars. Eternal Lands draws only the
## filled part and a one-pixel black frame, leaving the world visible through
## whatever is missing, so these get their own transparent-backed style instead
## of the bordered wells the bottom meters use. The fill colour is repainted
## per update by _set_overhead_meter().
static func _style_banner_meter(bar: ProgressBar) -> void:
	var background := StyleBoxFlat.new()
	background.bg_color = Color(0.0, 0.0, 0.0, 0.0)
	background.border_color = Color(0.0, 0.0, 0.0, 0.95)
	background.set_border_width_all(1)
	var fill := StyleBoxFlat.new()
	fill.bg_color = Color(0.17, 0.82, 0.22, 1.0)
	bar.add_theme_stylebox_override("background", background)
	bar.add_theme_stylebox_override("fill", fill)

## Eternal Lands' banner menu is a plain dark strip of single-line entries with
## barely any padding around them. Godot's stock CheckBox is roughly twice as
## tall, so the menu carries its own compact styling rather than inheriting the
## window chrome the rest of the HUD uses.
func _style_actor_hud_menu(panel_style: StyleBoxFlat) -> void:
	var menu_style: StyleBoxFlat = panel_style.duplicate() as StyleBoxFlat
	menu_style.bg_color = Color(0.02, 0.03, 0.035, 0.95)
	menu_style.set_border_width_all(1)
	menu_style.set_content_margin_all(2.0)
	actor_hud_menu.add_theme_stylebox_override("panel", menu_style)
	var entry_style := StyleBoxEmpty.new()
	entry_style.content_margin_top = 1.0
	entry_style.content_margin_bottom = 1.0
	entry_style.content_margin_left = 3.0
	entry_style.content_margin_right = 8.0
	var hover_style := StyleBoxFlat.new()
	hover_style.bg_color = Color(0.16, 0.24, 0.23, 0.95)
	hover_style.content_margin_top = 1.0
	hover_style.content_margin_bottom = 1.0
	hover_style.content_margin_left = 3.0
	hover_style.content_margin_right = 8.0
	for box_value: Variant in _banner_option_boxes.values():
		var box: CheckBox = box_value as CheckBox
		box.focus_mode = Control.FOCUS_NONE
		box.add_theme_font_size_override("font_size", 13)
		box.add_theme_constant_override("h_separation", 4)
		box.add_theme_color_override("font_color", Color(0.91, 0.86, 0.70))
		box.add_theme_color_override("font_hover_color", Color(1.0, 0.94, 0.76))
		box.add_theme_color_override("font_pressed_color", Color(0.91, 0.86, 0.70))
		box.add_theme_color_override("font_hover_pressed_color", Color(1.0, 0.94, 0.76))
		for state: String in ["normal", "pressed", "disabled", "focus"]:
			box.add_theme_stylebox_override(state, entry_style)
		for state: String in ["hover", "hover_pressed"]:
			box.add_theme_stylebox_override(state, hover_style)

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
	# Creation bytes (skin, hair, shirt, pants, boots, head, eyes) select skinned
	# surfaces already authored into each actor GLB, so they are deliberately
	# never reinterpreted as rigid BoneAttachment3D equipment and contribute
	# nothing here. AppearanceVariants used to expose a function for that which
	# returned {} unconditionally and was still called on every actor build; the
	# refusal is stated here instead of hidden behind a call.
	#
	# The legacy visual ids below 100 are real equipment, not creation
	# leftovers, so they are not dropped. An authored NPC look is applied last
	# and outranks the server's appearance bytes, which is how a Four Gates
	# guard keeps its guard gear without an alias hijacking the shared legacy id
	# for every other actor.
	var visuals: Dictionary = {}
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
