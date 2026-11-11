extends RefCounted

class_name MazeSerializer

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

const SAVE_DIRECTORY := "user://Mazes/"

static var last_saved_path: String = ""


static func sanitize_name(maze_name: String) -> String:
	var safe_name := maze_name.strip_edges()
	if safe_name.is_empty():
		safe_name = "UntitledMaze"
	safe_name = safe_name.replace(" ", "_")
	for c in ["/", "\\", ":", "*", "?", "\"", "<", ">", "|"]:
		safe_name = safe_name.replace(c, "_")
	return safe_name


static func serialize_grid(grid: Array) -> Array:
	var save_grid := grid.duplicate(true)
	for row in range(save_grid.size()):
		for col in range(save_grid[row].size()):
			var cell: Dictionary = save_grid[row][col]
			cell["element"] = int(cell.get("element", EMPTY))
			cell["top"] = bool(cell.get("top", false))
			cell["bottom"] = bool(cell.get("bottom", false))
			cell["left"] = bool(cell.get("left", false))
			cell["right"] = bool(cell.get("right", false))
			cell["visited"] = bool(cell.get("visited", false))
			var pit = cell.get("pit_destination", null)
			if pit != null:
				if pit is Vector2i or pit is Vector2:
					cell["pit_destination"] = {
						"x": int(pit.x),
						"y": int(pit.y)
					}
				elif pit is Dictionary and pit.has("x") and pit.has("y"):
					cell["pit_destination"] = {
						"x": int(pit["x"]),
						"y": int(pit["y"])
					}
				else:
					cell["pit_destination"] = null
			else:
				cell["pit_destination"] = null
	return save_grid


static func _serialize_grid(grid: Array) -> Array:
	return serialize_grid(grid)


static func deserialize_grid(raw_grid: Array) -> Array:
	var grid := raw_grid.duplicate(true)
	for row in range(grid.size()):
		for col in range(grid[row].size()):
			var cell: Dictionary = grid[row][col]
			cell["element"] = int(cell.get("element", EMPTY))
			cell["top"] = bool(cell.get("top", false))
			cell["bottom"] = bool(cell.get("bottom", false))
			cell["left"] = bool(cell.get("left", false))
			cell["right"] = bool(cell.get("right", false))
			cell["visited"] = bool(cell.get("visited", false))
			var pit = cell.get("pit_destination", null)
			if pit != null:
				if pit is Dictionary and pit.has("x") and pit.has("y"):
					cell["pit_destination"] = Vector2i(int(pit["x"]), int(pit["y"]))
				elif pit is Vector2i:
					cell["pit_destination"] = pit
				elif pit is Array and pit.size() >= 2:
					cell["pit_destination"] = Vector2i(int(pit[0]), int(pit[1]))
				else:
					cell["pit_destination"] = null
			else:
				cell["pit_destination"] = null
	return grid


static func get_unique_save_path(maze_name: String, base_dir: String = SAVE_DIRECTORY) -> String:
	var safe_name := sanitize_name(maze_name)
	var candidate := base_dir + safe_name + ".json"
	var suffix := 1
	while FileAccess.file_exists(candidate):
		candidate = base_dir + "%s_%d.json" % [safe_name, suffix]
		suffix += 1
	return candidate


static func save(
	grid: Array,
	maze_name: String,
	username: String,
	allow_overwrite: bool = false
) -> bool:
	var absolute_dir := ProjectSettings.globalize_path(SAVE_DIRECTORY)
	if !DirAccess.dir_exists_absolute(absolute_dir):
		var err := DirAccess.make_dir_recursive_absolute(absolute_dir)
		if err != OK:
			push_error("Failed to create save directory: " + absolute_dir)
			return false

	var clean_name := maze_name.strip_edges()
	if clean_name.is_empty():
		clean_name = "UntitledMaze"
	var clean_author := username.strip_edges()
	if clean_author.is_empty():
		clean_author = "Player"

	var path: String
	if allow_overwrite:
		path = SAVE_DIRECTORY + sanitize_name(clean_name) + ".json"
	else:
		path = get_unique_save_path(clean_name, SAVE_DIRECTORY)

	var metadata := {
		"maze_name": clean_name,
		"author": clean_author,
		"created_at": Time.get_datetime_string_from_system(),
		"editor_version": 1,
		"grid_size": grid.size()
	}

	var maze := {
		"metadata": metadata,
		"grid": serialize_grid(grid)
	}

	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to open file for writing: " + path)
		return false

	file.store_string(JSON.stringify(maze, "\t"))
	file.close()
	last_saved_path = path
	return true


static func save_to_path(grid: Array, path: String) -> bool:
	var data := load_maze(path)
	if data.is_empty():
		return false

	data["grid"] = serialize_grid(grid)
	if data.has("metadata") and data["metadata"] is Dictionary:
		data["metadata"]["updated_at"] = Time.get_datetime_string_from_system()

	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("Failed to overwrite maze: " + path)
		return false

	file.store_string(JSON.stringify(data, "\t"))
	file.close()
	last_saved_path = path
	return true


static func to_json_compatible_dict(maze_data: Dictionary) -> Dictionary:
	var copy := maze_data.duplicate(true)
	if copy.has("grid") and copy["grid"] is Array:
		copy["grid"] = serialize_grid(copy["grid"])
	return copy


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
		push_error("Invalid maze JSON: " + path)
		return {}

	if !(json.data is Dictionary):
		push_error("Maze JSON root is not a dictionary.")
		return {}

	var data: Dictionary = json.data
	if !data.has("grid") or !(data["grid"] is Array):
		push_error("Maze JSON missing grid array.")
		return {}

	data["grid"] = deserialize_grid(data["grid"])
	return data
