extends Control

@onready var newMapButton: Button = $NewMapButton
@onready var myMapsButton: Button = $MyMapsButton
@onready var playButton: Button = get_node_or_null("PlayButton")
@onready var multiplayerButton: Button = get_node_or_null("MultiplayerButton")
@onready var mascotNode: Node2D = get_node_or_null("MascotDog")

var ogPosition: Vector2
var ogPosition2: Vector2
var ogPosition3: Vector2


func _ready() -> void:
	_sync_positions()
	resized.connect(_sync_positions)
	if mascotNode != null and mascotNode.has_method("celebrate"):
		mascotNode.celebrate()


func _sync_positions() -> void:
	if newMapButton != null:
		ogPosition = newMapButton.position
	if myMapsButton != null:
		ogPosition2 = myMapsButton.position
	if playButton != null:
		ogPosition3 = playButton.position
	if mascotNode != null:
		mascotNode.position = Vector2(size.x * 0.5, size.y * 0.37)
		var scale_factor: float = clampf(minf(size.x / 1152.0, size.y / 648.0), 0.65, 1.8)
		if mascotNode.has_method("set_base_scale"):
			mascotNode.set_base_scale(2.6 * scale_factor)
		else:
			mascotNode.scale = Vector2(2.6, 2.6) * scale_factor


func _on_new_map_button_button_down() -> void:
	ogPosition = newMapButton.position
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(newMapButton, "position", ogPosition + Vector2(5, 5), 0.08)


func _on_new_map_button_button_up() -> void:
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(newMapButton, "position", ogPosition, 0.08)
	await tween.finished
	MazeSession.reset_session()
	get_tree().change_scene_to_file("res://scenes/map_editor_page.tscn")


func _on_my_maps_button_button_down() -> void:
	ogPosition2 = myMapsButton.position
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(myMapsButton, "position", ogPosition2 + Vector2(5, 5), 0.08)


func _on_my_maps_button_button_up() -> void:
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(myMapsButton, "position", ogPosition2, 0.08)
	await tween.finished
	get_tree().change_scene_to_file("res://scenes/my_maps.tscn")


func _on_play_button_pressed() -> void:
	MazeSession.ensure_default_maps()
	var dir := DirAccess.open(MazeSession.SAVE_DIRECTORY)
	if dir != null:
		dir.list_dir_begin()
		while true:
			var fname := dir.get_next()
			if fname == "":
				break
			if !dir.current_is_dir() and fname.ends_with(".json"):
				var path: String = MazeSession.SAVE_DIRECTORY + fname
				var data := MazeSerializer.load_maze(path)
				if !data.is_empty():
					MazeSession.loaded_maze = data
					MazeSession.editing_path = path
					dir.list_dir_end()
					get_tree().change_scene_to_file("res://scenes/gameplay_page.tscn")
					return
		dir.list_dir_end()
	get_tree().change_scene_to_file("res://scenes/my_maps.tscn")


func _on_multiplayer_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/multiplayer_page.tscn")
