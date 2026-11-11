extends Control

const ROW_SCENE = preload("res://scenes/mazeRow.tscn")
const SAVE_DIR = "user://Mazes/"

var pending_delete_path: String = ""


func _ready() -> void:
	MazeSession.ensure_default_maps()
	load_saved_mazes()


func load_saved_mazes() -> void:
	var container = $MarginContainer/VBoxContainer/VBoxContainer2
	for child in container.get_children():
		child.queue_free()

	var dir := DirAccess.open(SAVE_DIR)
	if dir == null:
		return

	var files: Array[String] = []
	dir.list_dir_begin()
	while true:
		var file_name := dir.get_next()
		if file_name == "":
			break
		if !dir.current_is_dir() and file_name.ends_with(".json"):
			files.append(file_name)
	dir.list_dir_end()
	files.sort()

	for file_name in files:
		var path := SAVE_DIR + file_name
		var data := MazeSerializer.load_maze(path)
		if data.is_empty():
			continue

		var row = ROW_SCENE.instantiate()
		row.maze_path = path
		if row.has_signal("play_requested"):
			row.play_requested.connect(_on_play_requested)
		row.delete_requested.connect(_on_delete_requested)
		row.edit_requested.connect(_on_edit_requested)

		var meta: Dictionary = data.get("metadata", {})
		row.get_node("MazeName").text = str(meta.get("maze_name", file_name.get_basename()))
		if row.has_node("AuthorLabel"):
			row.get_node("AuthorLabel").text = str(meta.get("author", "Player"))
		if row.has_node("GridSizeLabel"):
			var gsize := int(meta.get("grid_size", 10))
			row.get_node("GridSizeLabel").text = "%dx%d" % [gsize, gsize]

		var created_str := str(meta.get("created_at", ""))
		if created_str.is_empty():
			var modified := FileAccess.get_modified_time(path)
			created_str = Time.get_datetime_string_from_unix_time(modified)
		row.get_node("LastModified").text = created_str

		container.add_child(row)
		row.custom_minimum_size = Vector2(800, 44)


func _on_back_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/landing_page.tscn")


func _on_new_maze_button_pressed() -> void:
	MazeSession.reset_session()
	get_tree().change_scene_to_file("res://scenes/map_editor_page.tscn")


func _on_play_requested(path: String) -> void:
	var data := MazeSerializer.load_maze(path)
	if data.is_empty():
		push_error("Failed to load maze for gameplay.")
		return
	MazeSession.loaded_maze = data
	MazeSession.editing_path = path
	get_tree().change_scene_to_file("res://scenes/gameplay_page.tscn")


func _on_delete_requested(path: String) -> void:
	pending_delete_path = path
	$DeleteDialog.dialog_text = "Are you sure you want to delete this maze?\n\nThis action cannot be undone."
	$DeleteDialog.popup_centered()


func _on_edit_requested(path: String) -> void:
	var data := MazeSerializer.load_maze(path)
	if data.is_empty():
		push_error("Failed to load maze.")
		return
	MazeSession.loaded_maze = data
	MazeSession.editing_path = path
	get_tree().change_scene_to_file("res://scenes/map_editor_page.tscn")


func _on_delete_dialog_confirmed() -> void:
	if pending_delete_path.is_empty():
		return
	var error := DirAccess.remove_absolute(
		ProjectSettings.globalize_path(pending_delete_path)
	)
	if error != OK:
		push_error("Failed to delete maze.")
	pending_delete_path = ""
	load_saved_mazes()
