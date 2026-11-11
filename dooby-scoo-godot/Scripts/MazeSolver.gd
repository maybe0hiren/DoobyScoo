extends RefCounted

class_name MazeSolver

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4


static func _extract_coords(destination) -> Vector2i:
	if destination is Vector2i:
		return destination
	if destination is Dictionary and destination.has("x") and destination.has("y"):
		return Vector2i(int(destination["x"]), int(destination["y"]))
	if destination is Array and destination.size() >= 2:
		return Vector2i(int(destination[0]), int(destination[1]))
	return Vector2i(-1, -1)


static func is_solvable(grid: Array) -> Dictionary:
	var rows: int = grid.size()
	if rows == 0:
		return {
			"success": false,
			"path_length": -1,
			"error": "Grid is empty."
		}

	var cols: int = grid[0].size()
	var start := Vector2i(-1, -1)
	var end_positions: Array[Vector2i] = []
	var bone_positions: Array[Vector2i] = []

	for y in range(rows):
		for x in range(cols):
			match int(grid[y][x]["element"]):
				START:
					start = Vector2i(x, y)
				END:
					end_positions.append(Vector2i(x, y))
				BONE:
					bone_positions.append(Vector2i(x, y))

	if start.x == -1:
		return {
			"success": false,
			"path_length": -1,
			"error": "No Start found."
		}

	if end_positions.is_empty():
		return {
			"success": false,
			"path_length": -1,
			"error": "No End found."
		}

	var queue: Array = []
	var visited := {}
	var distances := {}

	queue.append({
		"position": start,
		"distance": 0
	})
	visited[start] = true
	distances[start] = 0

	var reachable := {}

	while !queue.is_empty():
		var current = queue.pop_front()
		var pos: Vector2i = current["position"]
		var distance: int = current["distance"]

		reachable[pos] = true
		var row := pos.y
		var col := pos.x
		var cell = grid[row][col]

		if !bool(cell["top"]) and row > 0 and !bool(grid[row - 1][col]["bottom"]):
			_add_neighbor(Vector2i(col, row - 1), distance + 1, grid, queue, visited, distances)

		if !bool(cell["bottom"]) and row < rows - 1 and !bool(grid[row + 1][col]["top"]):
			_add_neighbor(Vector2i(col, row + 1), distance + 1, grid, queue, visited, distances)

		if !bool(cell["left"]) and col > 0 and !bool(grid[row][col - 1]["right"]):
			_add_neighbor(Vector2i(col - 1, row), distance + 1, grid, queue, visited, distances)

		if !bool(cell["right"]) and col < cols - 1 and !bool(grid[row][col + 1]["left"]):
			_add_neighbor(Vector2i(col + 1, row), distance + 1, grid, queue, visited, distances)

	for bone in bone_positions:
		if !reachable.has(bone):
			return {
				"success": false,
				"path_length": -1,
				"error": "A Bone is unreachable."
			}

	var end_found := false
	var shortest_end_dist := 999999

	for e in end_positions:
		if reachable.has(e):
			end_found = true
			if distances.has(e) and distances[e] < shortest_end_dist:
				shortest_end_dist = distances[e]

	if !end_found:
		return {
			"success": false,
			"path_length": -1,
			"error": "No End is reachable."
		}

	return {
		"success": true,
		"path_length": shortest_end_dist,
		"reachable_cells": reachable.size(),
		"error": ""
	}


static func _add_neighbor(
	position: Vector2i,
	distance: int,
	grid: Array,
	queue: Array,
	visited: Dictionary,
	distances: Dictionary
) -> void:
	var rows: int = grid.size()
	var cols: int = grid[0].size()

	if position.x < 0 or position.x >= cols:
		return
	if position.y < 0 or position.y >= rows:
		return

	var destination := position
	var pit_chain := {}

	while int(grid[destination.y][destination.x]["element"]) == PIT:
		if pit_chain.has(destination):
			return
		pit_chain[destination] = true

		var next_raw = grid[destination.y][destination.x]["pit_destination"]
		if next_raw == null:
			return
		var next_vec := _extract_coords(next_raw)
		if next_vec.x < 0 or next_vec.x >= cols:
			return
		if next_vec.y < 0 or next_vec.y >= rows:
			return
		destination = next_vec

	if visited.has(destination):
		return

	visited[destination] = true
	distances[destination] = distance
	queue.append({
		"position": destination,
		"distance": distance
	})
