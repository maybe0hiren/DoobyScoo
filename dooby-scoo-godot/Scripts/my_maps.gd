extends Control

const ROW_SCENE = preload("res://scenes/mazeRow.tscn")
const SAVE_DIR = "user://Mazes/"


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

		print("Before load")
		var data = MazeSerializer.load(path)
		print("After load")

		print(data)

		if data.is_empty():
			print("Loaded data is empty.")
			continue

		print("Setting labels...")

		#row.get_node("MazeName").text = data["metadata"]["maze_name"]

		var modified = FileAccess.get_modified_time(path)
		row.get_node("MazeName").text = "Test1"
		row.get_node("LastModified").text = "Today"

		#row.get_node("LastModified").text = Time.get_datetime_string_from_unix_time(modified)

		print("Adding child...")
		container.add_child(row)
		row.custom_minimum_size = Vector2(800, 40)

		print("Children:", container.get_child_count())

	dir.list_dir_end()

	print("========== DONE ==========")
