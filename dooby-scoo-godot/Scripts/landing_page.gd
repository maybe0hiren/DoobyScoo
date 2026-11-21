extends Control

@onready var main_vbox: VBoxContainer = $ContentMargin/MainVBox
@onready var newMapButton: Button = $ContentMargin/MainVBox/MenuVBox/TopButtonsRow/NewMapButton
@onready var myMapsButton: Button = $ContentMargin/MainVBox/MenuVBox/TopButtonsRow/MyMapsButton
@onready var multiplayerButton: Button = $ContentMargin/MainVBox/MenuVBox/ArenaRow/MultiplayerButton
@onready var mascotSpacer: Control = $ContentMargin/MainVBox/MascotSpacer
@onready var mascotNode: Node2D = $ContentMargin/MainVBox/MascotSpacer/MascotDog


func _ready() -> void:
	_apply_theme()
	resized.connect(_sync_mascot_position)
	mascotSpacer.resized.connect(_sync_mascot_position)
	main_vbox.sort_children.connect(_sync_mascot_position)
	_sync_mascot_position()
	call_deferred("_sync_mascot_position")
	if mascotNode != null and mascotNode.has_method("celebrate"):
		mascotNode.celebrate()


func _notification(what: int) -> void:
	if what == NOTIFICATION_RESIZED and is_node_ready():
		_sync_mascot_position()


func _apply_theme() -> void:
	DoobyUI.style_lavender_button(myMapsButton, 25, 32)
	DoobyUI.style_lavender_button(newMapButton, 25, 32)
	DoobyUI.style_gold_button(multiplayerButton, 26, 34)


func _sync_mascot_position() -> void:
	if mascotNode == null or mascotSpacer == null:
		return
	var sp_size: Vector2 = mascotSpacer.size
	if sp_size.x > 1.0 and sp_size.y > 1.0:
		mascotNode.position = Vector2(sp_size.x * 0.5, sp_size.y * 0.54)
	var scale_factor: float = clampf(minf(size.x / 1152.0, size.y / 648.0), 0.72, 1.65)
	if mascotNode.has_method("set_base_scale"):
		mascotNode.set_base_scale(2.55 * scale_factor)
	else:
		mascotNode.scale = Vector2(2.55, 2.55) * scale_factor


func _on_new_map_button_pressed() -> void:
	MazeSession.reset_session()
	MazeSession.transition_to("res://scenes/map_editor_page.tscn")


func _on_my_maps_button_pressed() -> void:
	MazeSession.transition_to("res://scenes/my_maps.tscn")


func _on_multiplayer_button_pressed() -> void:
	MazeSession.transition_to("res://scenes/multiplayer_page.tscn")
