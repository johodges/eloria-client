extends Node3D

@onready var status: Label = %Status
@onready var clip_label: Label = %Clip
@onready var light_pivot: Node3D = %LightPivot

var actor: ReplicatedActor3D
var models: Dictionary
var animation_config: Dictionary
var equipment_config: Dictionary
var clips: Array[StringName] = []
var clip_index := 0
var model_id := "luminous_male"

func _ready() -> void:
	models = _json("res://data/actors/models.json").get("models", {})
	animation_config = _json("res://data/animations/luminous.json")
	equipment_config = _json("res://data/actors/equipment.json")
	_load_model(model_id)

func _process(delta: float) -> void:
	light_pivot.rotate_y(delta * 0.25)

func _load_model(id: String) -> void:
	if is_instance_valid(actor):
		actor.queue_free()
	model_id = id
	actor = ReplicatedActor3D.new()
	actor.name = "ValidatedActor"
	add_child(actor)
	var dto := {"actor_id": 1, "x": 0, "y": 0, "rotation": 0,
		"equipment_visuals": {0: 1, 1: 2}, "equipment_fallback_parts": [0, 1]}
	var adapter := CoordinateAdapter.new({"walkingHeight": 0.0, "invertServerY": true})
	var errors := actor.configure(dto, adapter, models[id], animation_config, equipment_config)
	var equipment_diagnostics: Dictionary = actor.equipment_diagnostics()
	if int(equipment_diagnostics.get("fallback", 0)) != 2:
		errors.append("equipment fallback bone attachments missing")
	clips.clear()
	for action in animation_config.get("actions", {}):
		var clip := StringName(animation_config.actions[action])
		if not clips.has(clip):
			clips.append(clip)
	clip_index = 0
	status.text = id + "\n" + ("PASS: source and mapped clips loaded" if errors.is_empty()
		else "ERRORS:\n" + "\n".join(errors))
	_play_current()

func _play_current() -> void:
	if clips.is_empty() or actor == null:
		return
	var clip := clips[clip_index]
	clip_label.text = "%d/%d  %s" % [clip_index + 1, clips.size(), clip]
	if actor.animation_player != null and actor.animation_player.has_animation(clip):
		actor.animation_player.play(clip)

func _on_previous_pressed() -> void:
	clip_index = wrapi(clip_index - 1, 0, clips.size())
	_play_current()

func _on_next_pressed() -> void:
	clip_index = wrapi(clip_index + 1, 0, clips.size())
	_play_current()

func _on_model_pressed() -> void:
	_load_model("luminous_female" if model_id == "luminous_male" else "luminous_male")

static func _json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}
