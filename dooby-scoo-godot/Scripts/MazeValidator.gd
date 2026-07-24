extends RefCounted

class_name MazeValidator

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4


static func validate(grid: Array) -> Dictionary:
	var errors: Array[String] = []

	var rows : int = grid.size()

	if rows == 0:
		errors.append("Grid is empty.")
		return {
			"success": false,
			"errors": errors
		}

	var cols : int = grid[0].size()

	var start_count := 0
	var end_count := 0
	var bone_count := 0

	for row in range(rows):
		for col in range(cols):
			var cell = grid[row][col]

			match cell["element"]:
				START:
					start_count += 1

				END:
					end_count += 1

				BONE:
					bone_count += 1

				PIT:
					var destination = cell["pit_destination"]

					if destination == null:
						errors.append(
							"Pit at (%d, %d) has no destination." % [col, row]
						)
					else:
						if destination.x < 0 or destination.x >= cols \
						or destination.y < 0 or destination.y >= rows:
							errors.append(
								"Pit at (%d, %d) has an invalid destination." % [col, row]
							)

			if col < cols - 1:
				if cell["right"] != grid[row][col + 1]["left"]:
					errors.append(
						"Wall mismatch between (%d,%d) and (%d,%d)." %
						[col, row, col + 1, row]
					)

			if row < rows - 1:
				if cell["bottom"] != grid[row + 1][col]["top"]:
					errors.append(
						"Wall mismatch between (%d,%d) and (%d,%d)." %
						[col, row, col, row + 1]
					)
					
	if start_count != 1:
		errors.append(
			"Maze must contain exactly one Start. Found %d." % start_count
		)

	if end_count < 1 or end_count > 2:
		errors.append(
			"Maze must contain 1 or 2 Ends. Found %d." % end_count
		)

	if bone_count != 5:
		errors.append(
			"Maze must contain exactly 5 Bones. Found %d." % bone_count
		)

	return {
		"success": errors.is_empty(),
		"errors": errors
	}
