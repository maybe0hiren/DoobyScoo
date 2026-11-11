extends Control

class_name GameplayBoard

const GRID_SIZE := 10
const CELL_SIZE := 56
const PADDING := Vector2(20, 20)

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

var grid: Array = []
var remaining_bones: Dictionary = {}
var visited_trail: Array[Vector2i] = []
var dog: DogController


func _ready() -> void:
	custom_minimum_size = Vector2(GRID_SIZE * CELL_SIZE + PADDING.x * 2, GRID_SIZE * CELL_SIZE + PADDING.y * 2)
	dog = DogController.new()
	add_child(dog)


func cell_center(cell: Vector2i) -> Vector2:
	return PADDING + Vector2(
		cell.x * CELL_SIZE + CELL_SIZE / 2.0,
		cell.y * CELL_SIZE + CELL_SIZE / 2.0
	)


func setup_board(maze_grid: Array) -> void:
	grid = MazeSerializer.deserialize_grid(maze_grid)
	remaining_bones.clear()
	visited_trail.clear()

	var start_cell := Vector2i(0, 0)
	for row in range(grid.size()):
		for col in range(grid[row].size()):
			var el := int(grid[row][col]["element"])
			var pos := Vector2i(col, row)
			if el == START:
				start_cell = pos
			elif el == BONE:
				remaining_bones[pos] = true

	visited_trail.append(start_cell)
	if dog != null:
		dog.place_at_cell(start_cell, cell_center(start_cell))
	queue_redraw()


func sync_remaining_bones(bones_array: Array) -> void:
	remaining_bones.clear()
	for item in bones_array:
		if item is Array and item.size() >= 2:
			remaining_bones[Vector2i(int(item[0]), int(item[1]))] = true
		elif item is Vector2i:
			remaining_bones[item] = true
	queue_redraw()


func animate_step_result(result: Dictionary) -> void:
	var action := int(result.get("action", 3))
	var pos_arr: Array = result.get("position", [dog.grid_position.x, dog.grid_position.y])
	var target_cell := Vector2i(int(pos_arr[0]), int(pos_arr[1]))
	var moved := bool(result.get("moved", true))
	var teleported := bool(result.get("teleported", false))
	var got_bone := bool(result.get("bone", false))
	var won := bool(result.get("won", false))

	if result.has("state") and result["state"] is Dictionary and result["state"].has("remainingBones"):
		sync_remaining_bones(result["state"]["remainingBones"])
	elif got_bone and remaining_bones.has(target_cell):
		remaining_bones.erase(target_cell)

	if !moved:
		await dog.animate_blocked(action)
	elif teleported and result.get("pitEntered", null) is Array:
		var pit_arr: Array = result["pitEntered"]
		var pit_cell := Vector2i(int(pit_arr[0]), int(pit_arr[1]))
		visited_trail.append(pit_cell)
		visited_trail.append(target_cell)
		queue_redraw()
		await dog.animate_teleport(cell_center(pit_cell), target_cell, cell_center(target_cell), action)
	else:
		visited_trail.append(target_cell)
		queue_redraw()
		await dog.animate_move(target_cell, cell_center(target_cell), action)

	if got_bone:
		dog.animate_bone_pickup()
	if won:
		dog.celebrate()
	queue_redraw()


func _draw_arrow(start: Vector2, end: Vector2, color: Color, width: float = 2.5) -> void:
	if start.distance_to(end) < 2.0:
		return
	draw_line(start, end, color, width)
	var direction := (end - start).normalized()
	var left := end - direction.rotated(deg_to_rad(28)) * 10.0
	var right := end - direction.rotated(deg_to_rad(-28)) * 10.0
	draw_line(end, left, color, width)
	draw_line(end, right, color, width)


func _draw_bone(center: Vector2) -> void:
	var bone_col := Color(0.99, 0.95, 0.78)
	var outline_col := Color(0.68, 0.48, 0.16)
	for offset in [Vector2(-8, -4.5), Vector2(-8, 4.5), Vector2(8, -4.5), Vector2(8, 4.5)]:
		draw_circle(center + offset, 5.0, outline_col)
	draw_line(center + Vector2(-8, 0), center + Vector2(8, 0), outline_col, 8.0)
	for offset in [Vector2(-8, -4.5), Vector2(-8, 4.5), Vector2(8, -4.5), Vector2(8, 4.5)]:
		draw_circle(center + offset, 3.6, bone_col)
	draw_line(center + Vector2(-8, 0), center + Vector2(8, 0), bone_col, 5.5)


func _draw() -> void:
	if grid.is_empty():
		return

	var rows := grid.size()
	var cols: int = grid[0].size()
	var board_rect := Rect2(
		PADDING - Vector2(8, 8),
		Vector2(cols * CELL_SIZE + 16, rows * CELL_SIZE + 16)
	)
	draw_rect(board_rect, Color(0.14, 0.20, 0.16, 0.92), true)
	draw_rect(board_rect, Color(0.95, 0.85, 0.55), false, 3.0)

	for row in range(rows):
		for col in range(cols):
			var x := PADDING.x + col * CELL_SIZE
			var y := PADDING.y + row * CELL_SIZE
			var rect := Rect2(x, y, CELL_SIZE, CELL_SIZE)
			var cell_pos := Vector2i(col, row)
			var checker := (row + col) % 2 == 0
			var bg := Color(0.96, 0.94, 0.86) if checker else Color(0.91, 0.88, 0.78)
			if cell_pos in visited_trail:
				bg = bg.lerp(Color(0.55, 0.88, 0.62), 0.25)
			draw_rect(rect, bg, true)
			draw_rect(rect, Color(0.75, 0.70, 0.60, 0.5), false, 1.0)

			var center := Vector2(x + CELL_SIZE / 2.0, y + CELL_SIZE / 2.0)
			var el := int(grid[row][col]["element"])
			if el == START:
				draw_circle(center, 15.0, Color(0.16, 0.74, 0.32, 0.45))
				draw_circle(center, 9.0, Color(0.18, 0.82, 0.36))
			elif el == END:
				draw_circle(center, 17.0, Color(0.96, 0.26, 0.26, 0.38))
				draw_circle(center, 12.5, Color(0.88, 0.18, 0.22))
				draw_circle(center, 8.0, Color(1.0, 0.84, 0.18))
				draw_circle(center, 3.8, Color(0.88, 0.18, 0.22))
			elif el == PIT:
				draw_circle(center, 14.0, Color(0.24, 0.10, 0.40))
				draw_circle(center, 9.5, Color(0.08, 0.03, 0.15))
				draw_arc(center, 11.0, 0.4, 4.9, 14, Color(0.58, 0.36, 0.92), 2.0)

			if remaining_bones.has(cell_pos):
				_draw_bone(center)

	# Draw pit arrows
	for row in range(rows):
		for col in range(cols):
			var cell: Dictionary = grid[row][col]
			if int(cell["element"]) == PIT and cell["pit_destination"] != null:
				var dest = cell["pit_destination"]
				if dest is Vector2i:
					_draw_arrow(cell_center(Vector2i(col, row)), cell_center(dest), Color(0.12, 0.68, 0.96, 0.75), 2.5)

	# Draw walls
	var wall_col := Color(0.24, 0.16, 0.10)
	for row in range(rows):
		for col in range(cols):
			var x := PADDING.x + col * CELL_SIZE
			var y := PADDING.y + row * CELL_SIZE
			if bool(grid[row][col]["top"]):
				draw_line(Vector2(x, y), Vector2(x + CELL_SIZE, y), wall_col, 5.0)
			if bool(grid[row][col]["bottom"]):
				draw_line(Vector2(x, y + CELL_SIZE), Vector2(x + CELL_SIZE, y + CELL_SIZE), wall_col, 5.0)
			if bool(grid[row][col]["left"]):
				draw_line(Vector2(x, y), Vector2(x, y + CELL_SIZE), wall_col, 5.0)
			if bool(grid[row][col]["right"]):
				draw_line(Vector2(x + CELL_SIZE, y), Vector2(x + CELL_SIZE, y + CELL_SIZE), wall_col, 5.0)

