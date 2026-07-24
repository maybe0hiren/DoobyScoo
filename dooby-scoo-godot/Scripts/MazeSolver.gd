extends RefCounted

class_name MazeSolver

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4


static func is_solvable(grid:Array) -> Dictionary:

	var rows :int = grid.size()

	if rows == 0:
		return {
			"success": false,
			"path_length": -1,
			"error":"Grid is empty."
		}

	var cols : int = grid[0].size()

	var start := Vector2i(-1,-1)

	var end_positions:Array[Vector2i] = []
	var bone_positions:Array[Vector2i] = []

	for y in range(rows):
		for x in range(cols):

			match grid[y][x]["element"]:

				START:
					start = Vector2i(x,y)

				END:
					end_positions.append(Vector2i(x,y))

				BONE:
					bone_positions.append(Vector2i(x,y))

	if start.x == -1:
		return {
			"success":false,
			"path_length":-1,
			"error":"No Start found."
		}

	var queue:Array = []
	var visited := {}

	queue.append({
		"position":start,
		"distance":0
	})

	visited[start]=true

	var reachable := {}

	while !queue.is_empty():

		var current = queue.pop_front()

		var pos:Vector2i = current["position"]
		var distance:int = current["distance"]

		reachable[pos]=true

		var row := pos.y
		var col := pos.x

		var cell = grid[row][col]

		if !cell["top"]:
			_add_neighbor(Vector2i(col,row-1),distance+1,grid,queue,visited)

		if !cell["bottom"]:
			_add_neighbor(Vector2i(col,row+1),distance+1,grid,queue,visited)

		if !cell["left"]:
			_add_neighbor(Vector2i(col-1,row),distance+1,grid,queue,visited)

		if !cell["right"]:
			_add_neighbor(Vector2i(col+1,row),distance+1,grid,queue,visited)

	# -----------------------
	# Every bone reachable?
	# -----------------------

	for bone in bone_positions:

		if !reachable.has(bone):

			return {
				"success":false,
				"path_length":-1,
				"error":"A Bone is unreachable."
			}

	# -----------------------
	# At least one End reachable?
	# -----------------------

	var end_found := false

	for e in end_positions:

		if reachable.has(e):
			end_found = true
			break

	if !end_found:

		return {
			"success":false,
			"path_length":-1,
			"error":"No End is reachable."
		}

	return {
		"success":true,
		"path_length":reachable.size(),
		"error":""
	}


static func _add_neighbor(
	position:Vector2i,
	distance:int,
	grid:Array,
	queue:Array,
	visited:Dictionary
)->void:

	var rows : int = grid.size()
	var cols : int = grid[0].size()

	if position.x<0 or position.x>=cols:
		return

	if position.y<0 or position.y>=rows:
		return

	var destination := position

	var pit_chain := {}

	while grid[destination.y][destination.x]["element"] == PIT:

		if pit_chain.has(destination):
			return

		pit_chain[destination]=true

		var next = grid[destination.y][destination.x]["pit_destination"]

		if next==null:
			return

		if next.x<0 or next.x>=cols:
			return

		if next.y<0 or next.y>=rows:
			return

		destination = next

	if visited.has(destination):
		return

	visited[destination]=true

	queue.append({
		"position":destination,
		"distance":distance
	})
