extends RefCounted

class_name MazeSerializer

const SAVE_DIRECTORY := "user://Mazes/"


static func save(
	grid: Array,
	maze_name: String,
	username: String
) -> bool:

	# Ensure save directory exists
	var absolute_dir := ProjectSettings.globalize_path(SAVE_DIRECTORY)

	if !DirAccess.dir_exists_absolute(absolute_dir):
		var err := DirAccess.make_dir_recursive_absolute(absolute_dir)
		if err != OK:
			push_error("Failed to create save directory: " + absolute_dir)
			return false

	# Metadata
	var metadata := {
		"maze_name": maze_name,
		"author": username,
		"created_at": Time.get_datetime_string_from_system(),
		"editor_version": 1,
		"grid_size": grid.size()
	}

	var maze := {
		"metadata": metadata,
		"grid": grid
	}

	# Clean filename
	var safe_name := maze_name.strip_edges()

	if safe_name.is_empty():
		safe_name = "UntitledMaze"

	safe_name = safe_name.replace(" ", "_")

	# Remove characters invalid in filenames
	for c in ["/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
		safe_name = safe_name.replace(c, "_")

	var path := SAVE_DIRECTORY + safe_name + ".json"

	print("Saving maze to: ", ProjectSettings.globalize_path(path))

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		push_error("Failed to open file for writing: " + ProjectSettings.globalize_path(path))
		return false

	file.store_string(JSON.stringify(maze, "\t"))
	file.close()

	print("Maze saved successfully.")

	return true


static func load(path: String) -> Dictionary:

	if !FileAccess.file_exists(path):
		push_error("Maze file not found: " + path)
		return {}

	var file := FileAccess.open(path, FileAccess.READ)

	if file == null:
		push_error("Unable to open maze: " + path)
		return {}

	var text := file.get_as_text()
	file.close()

	var json := JSON.new()

	var err := json.parse(text)

	if err != OK:
		push_error("Invalid maze JSON.")
		return {}

	return json.data
