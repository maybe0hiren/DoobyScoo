extends RefCounted

class_name MazeSerializer

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

const SAVE_DIRECTORY := "user://Mazes/"


static func _serialize_grid(grid: Array) -> Array:
	var save_grid = grid.duplicate(true)

	for row in range(save_grid.size()):
		for col in range(save_grid[row].size()):
			var pit = save_grid[row][col]["pit_destination"]

			if pit != null:
				save_grid[row][col]["pit_destination"] = {
					"x": pit.x,
					"y": pit.y
				}

	return save_grid


static func save(
	grid: Array,
	maze_name: String,
	username: String
) -> bool:

	var absolute_dir := ProjectSettings.globalize_path(SAVE_DIRECTORY)

	if !DirAccess.dir_exists_absolute(absolute_dir):
		var err := DirAccess.make_dir_recursive_absolute(absolute_dir)
		if err != OK:
			push_error("Failed to create save directory: " + absolute_dir)
			return false

	var metadata := {
		"maze_name": maze_name,
		"author": username,
		"created_at": Time.get_datetime_string_from_system(),
		"editor_version": 1,
		"grid_size": grid.size()
	}

	var maze := {
		"metadata": metadata,
		"grid": _serialize_grid(grid)
	}

	var safe_name := maze_name.strip_edges()

	if safe_name.is_empty():
		safe_name = "UntitledMaze"

	safe_name = safe_name.replace(" ", "_")

	for c in ["/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
		safe_name = safe_name.replace(c, "_")

	var path := SAVE_DIRECTORY + safe_name + ".json"

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		push_error("Failed to open file for writing.")
		return false

	file.store_string(JSON.stringify(maze, "\t"))
	file.close()

	return true


static func save_to_path(
	grid: Array,
	path: String
) -> bool:

	var data = load_maze(path)

	if data.is_empty():
		return false

	data["grid"] = _serialize_grid(grid)

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		push_error("Failed to overwrite maze.")
		return false

	file.store_string(JSON.stringify(data, "\t"))
	file.close()

	return true


static func load_maze(path: String) -> Dictionary:

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

	if json.parse(text) != OK:
		push_error("Invalid maze JSON.")
		return {}

	var data: Dictionary = json.data

	if data.has("grid"):
		var grid: Array = data["grid"]

		for row in range(grid.size()):
			for col in range(grid[row].size()):
				var pit = grid[row][col]["pit_destination"]

				if pit != null and pit is Dictionary:
					grid[row][col]["pit_destination"] = Vector2i(
						int(pit["x"]),
						int(pit["y"])
					)

	return data
