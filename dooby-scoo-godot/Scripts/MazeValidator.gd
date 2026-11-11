extends RefCounted

class_name MazeValidator

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

const MAX_BONES := 5


static func _extract_coords(destination) -> Vector2i:
	if destination is Vector2i:
		return destination
	if destination is Dictionary and destination.has("x") and destination.has("y"):
		return Vector2i(int(destination["x"]), int(destination["y"]))
	if destination is Array and destination.size() >= 2:
		return Vector2i(int(destination[0]), int(destination[1]))
	return Vector2i(-1, -1)


static func _has_pit_cycle(grid: Array, start_pos: Vector2i, rows: int, cols: int) -> bool:
	var visited_pits := {}
	var current := start_pos
	while current.x >= 0 and current.x < cols and current.y >= 0 and current.y < rows:
		var cell = grid[current.y][current.x]
		if int(cell.get("element", EMPTY)) != PIT:
			return false
		if visited_pits.has(current):
			return true
		visited_pits[current] = true
		var dest_raw = cell.get("pit_destination", null)
		if dest_raw == null:
			return true
		var next_pos := _extract_coords(dest_raw)
		if next_pos.x < 0 or next_pos.x >= cols or next_pos.y < 0 or next_pos.y >= rows:
			return true
		current = next_pos
	return true


static func validate(grid: Array, require_exact_bones: bool = false) -> Dictionary:
	var errors: Array[String] = []

	var rows: int = grid.size()
	if rows == 0:
		errors.append("Grid is empty.")
		return {
			"success": false,
			"errors": errors
		}

	if !(grid[0] is Array) or grid[0].is_empty():
		errors.append("Grid rows cannot be empty.")
		return {
			"success": false,
			"errors": errors
		}

	var cols: int = grid[0].size()
	for r in range(rows):
		if !(grid[r] is Array) or grid[r].size() != cols:
			errors.append("All grid rows must have equal length.")
			return {
				"success": false,
				"errors": errors
			}

	var start_count := 0
	var end_count := 0
	var bone_count := 0

	for row in range(rows):
		for col in range(cols):
			var cell = grid[row][col]
			if !(cell is Dictionary):
				errors.append("Invalid cell data at (%d, %d)." % [col, row])
				continue

			var element := int(cell.get("element", -1))
			match element:
				EMPTY:
					pass
				START:
					start_count += 1
				END:
					end_count += 1
				BONE:
					bone_count += 1
				PIT:
					var destination = cell.get("pit_destination", null)
					if destination == null:
						errors.append("Pit at (%d, %d) has no destination." % [col, row])
					else:
						var dest_vec := _extract_coords(destination)
						if dest_vec.x < 0 or dest_vec.x >= cols or dest_vec.y < 0 or dest_vec.y >= rows:
							errors.append("Pit at (%d, %d) has an invalid destination." % [col, row])
						elif dest_vec == Vector2i(col, row):
							errors.append("Pit at (%d, %d) cannot point to itself." % [col, row])
						elif _has_pit_cycle(grid, Vector2i(col, row), rows, cols):
							errors.append("Pit at (%d, %d) is part of a cyclic or invalid pit chain." % [col, row])
				_:
					errors.append("Invalid element type at (%d, %d)." % [col, row])

			if row == 0 and !bool(cell.get("top", false)):
				errors.append("Outer top boundary must be blocked at (%d, %d)." % [col, row])
			if row == rows - 1 and !bool(cell.get("bottom", false)):
				errors.append("Outer bottom boundary must be blocked at (%d, %d)." % [col, row])
			if col == 0 and !bool(cell.get("left", false)):
				errors.append("Outer left boundary must be blocked at (%d, %d)." % [col, row])
			if col == cols - 1 and !bool(cell.get("right", false)):
				errors.append("Outer right boundary must be blocked at (%d, %d)." % [col, row])

			if col < cols - 1:
				if bool(cell.get("right", false)) != bool(grid[row][col + 1].get("left", false)):
					errors.append(
						"Wall mismatch between (%d,%d) and (%d,%d)." % [col, row, col + 1, row]
					)

			if row < rows - 1:
				if bool(cell.get("bottom", false)) != bool(grid[row + 1][col].get("top", false)):
					errors.append(
						"Wall mismatch between (%d,%d) and (%d,%d)." % [col, row, col, row + 1]
					)

	if start_count != 1:
		errors.append("Maze must contain exactly one Start. Found %d." % start_count)

	if end_count < 1 or end_count > 2:
		errors.append("Maze must contain 1 or 2 Ends. Found %d." % end_count)

	if require_exact_bones and bone_count != MAX_BONES:
		errors.append("Maze must contain exactly %d Bones. Found %d." % [MAX_BONES, bone_count])
	elif bone_count > MAX_BONES:
		errors.append("Maze cannot contain more than %d Bones. Found %d." % [MAX_BONES, bone_count])

	return {
		"success": errors.is_empty(),
		"errors": errors
	}
