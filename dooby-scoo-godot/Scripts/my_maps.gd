extends Control

const ROW_SCENE = preload("res://scenes/mazeRow.tscn")
const SAVE_DIR = "user://Mazes/"
var pending_delete_path: String = ""

func _ready() -> void:
	load_saved_mazes()
	print("my_maps ready")
	print(get_tree().current_scene.scene_file_path)


func load_saved_mazes() -> void:

	print("========== LOAD SAVED MAZES ==========")

	var container = $MarginContainer/VBoxContainer/VBoxContainer2
	print("Container:", container)

	# Clear existing rows
	for child in container.get_children():
		child.queue_free()

	print("Directory:", ProjectSettings.globalize_path(SAVE_DIR))

	var dir = DirAccess.open(SAVE_DIR)
	print("Dir:", dir)

	if dir == null:
		print("Failed to open directory.")
		return

	dir.list_dir_begin()

	while true:

		var file_name = dir.get_next()

		if file_name == "":
			print("End of directory.")
			break

		print("--------------------------------")
		print("Found:", file_name)

		if dir.current_is_dir():
			print("Skipping directory.")
			continue

		if !file_name.ends_with(".json"):
			print("Skipping non-json.")
			continue

		print("Instantiating row...")
		var row = ROW_SCENE.instantiate()
		print(row)

		var path = SAVE_DIR + file_name
		print("Loading:", path)

		# Give the row its file path
		row.maze_path = path

		# Connect row signals
		row.delete_requested.connect(_on_delete_requested)
		row.edit_requested.connect(_on_edit_requested)

		print("Before load")
		var data = MazeSerializer.load_maze(path)
		print("After load")

		print(data)

		if data.is_empty():
			print("Loaded data is empty.")
			continue

		print("Setting labels...")

		row.get_node("MazeName").text = data["metadata"]["maze_name"]

		var modified = FileAccess.get_modified_time(path)
		row.get_node("LastModified").text = Time.get_datetime_string_from_unix_time(modified)

		print("Adding child...")
		container.add_child(row)
		row.custom_minimum_size = Vector2(800, 40)

		print("Children:", container.get_child_count())

	dir.list_dir_end()

	print("========== DONE ==========")


func _on_back_button_pressed() -> void:
	get_tree().change_scene_to_file("res://scenes/landing_page.tscn")


func _on_delete_requested(path: String) -> void:
	pending_delete_path = path
	$DeleteDialog.dialog_text = "Are you sure you want to delete this maze?\n\nThis action cannot be undone."
	$DeleteDialog.popup_centered()


func _on_edit_requested(path: String) -> void:

	var data = MazeSerializer.load_maze(path)

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
	else:
		print("Maze deleted.")
	pending_delete_path = ""
	load_saved_mazes()
