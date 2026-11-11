extends Control

signal counts_changed(starts: int, ends: int, bones: int)

const GRID_SIZE := 10
const CELL_SIZE := 58
const PADDING := Vector2(24, 24)

const HANDLE_SIZE := 8.0
const HANDLE_COLOR := Color(1.0, 0.58, 0.12)

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

var grid: Array = []
var selectedCell := Vector2i(-1, -1)

var startCount := 0
var endCount := 0
var boneCount := 0

var draggingPit := false
var draggedPit := Vector2i(-1, -1)
var hoveredCell := Vector2i(-1, -1)
var pendingPit := Vector2i(-1, -1)
var pitExists := false

enum Tool {
	NONE,
	START,
	END,
	PIT,
	BONE
}

var currentTool = Tool.NONE


func _ready() -> void:
	custom_minimum_size = Vector2(GRID_SIZE * CELL_SIZE + PADDING.x * 2, GRID_SIZE * CELL_SIZE + PADDING.y * 2)
	_init_empty_grid()
	if !MazeSession.loaded_maze.is_empty() and MazeSession.loaded_maze.has("grid"):
		load_maze(MazeSession.loaded_maze["grid"])
	else:
		counts_changed.emit(startCount, endCount, boneCount)
	queue_redraw()


func _init_empty_grid() -> void:
	grid.clear()
	for row in range(GRID_SIZE):
		grid.append([])
		for col in range(GRID_SIZE):
			grid[row].append({
				"element": EMPTY,
				"top": row == 0,
				"bottom": row == GRID_SIZE - 1,
				"left": col == 0,
				"right": col == GRID_SIZE - 1,
				"pit_destination": null,
				"visited": false
			})


func cell_center(cell: Vector2i) -> Vector2:
	return PADDING + Vector2(
		cell.x * CELL_SIZE + CELL_SIZE / 2.0,
		cell.y * CELL_SIZE + CELL_SIZE / 2.0
	)


func draw_arrow(start: Vector2, end: Vector2, color: Color, width: float = 3.0) -> void:
	if start.distance_to(end) < 2.0:
		return
	draw_line(start, end, color, width)
	var direction := (end - start).normalized()
	var arrow_length := 12.0
	var arrow_angle := deg_to_rad(28)
	var left := end - direction.rotated(arrow_angle) * arrow_length
	var right := end - direction.rotated(-arrow_angle) * arrow_length
	draw_line(end, left, color, width)
	draw_line(end, right, color, width)


func _draw_bone_icon(center: Vector2) -> void:
	var bone_col := Color(0.99, 0.95, 0.78)
	var outline_col := Color(0.68, 0.48, 0.16)
	draw_circle(center + Vector2(-9, -5), 5.5, outline_col)
	draw_circle(center + Vector2(-9, 5), 5.5, outline_col)
	draw_circle(center + Vector2(9, -5), 5.5, outline_col)
	draw_circle(center + Vector2(9, 5), 5.5, outline_col)
	draw_line(center + Vector2(-9, 0), center + Vector2(9, 0), outline_col, 9.0)

	draw_circle(center + Vector2(-9, -5), 4.0, bone_col)
	draw_circle(center + Vector2(-9, 5), 4.0, bone_col)
	draw_circle(center + Vector2(9, -5), 4.0, bone_col)
	draw_circle(center + Vector2(9, 5), 4.0, bone_col)
	draw_line(center + Vector2(-9, 0), center + Vector2(9, 0), bone_col, 6.0)


func _draw_start_icon(center: Vector2) -> void:
	draw_circle(center, 18.0, Color(0.18, 0.78, 0.34, 0.35))
	draw_circle(center, 13.0, Color(0.16, 0.72, 0.30))
	draw_circle(center, 9.0, Color(0.32, 0.92, 0.46))
	draw_circle(center + Vector2(0, 2), 4.5, Color.WHITE)
	draw_circle(center + Vector2(-4, -3), 2.2, Color.WHITE)
	draw_circle(center + Vector2(0, -5), 2.2, Color.WHITE)
	draw_circle(center + Vector2(4, -3), 2.2, Color.WHITE)


func _draw_end_icon(center: Vector2) -> void:
	draw_circle(center, 18.0, Color(0.98, 0.28, 0.28, 0.35))
	draw_circle(center, 13.0, Color(0.88, 0.18, 0.22))
	draw_circle(center, 8.5, Color(1.0, 0.84, 0.18))
	draw_circle(center, 4.0, Color(0.88, 0.18, 0.22))


func _draw_pit_icon(center: Vector2) -> void:
	draw_circle(center, 15.0, Color(0.26, 0.12, 0.42))
	draw_circle(center, 11.0, Color(0.12, 0.05, 0.22))
	draw_circle(center, 6.0, Color(0.04, 0.02, 0.08))
	draw_arc(center, 12.0, 0.3, 4.8, 16, Color(0.55, 0.32, 0.88), 2.0)


func _draw() -> void:
	var board_rect := Rect2(
		PADDING - Vector2(8, 8),
		Vector2(GRID_SIZE * CELL_SIZE + 16, GRID_SIZE * CELL_SIZE + 16)
	)
	draw_rect(board_rect, Color(0.16, 0.22, 0.18, 0.88), true)
	draw_rect(board_rect, Color(0.95, 0.85, 0.55), false, 3.0)

	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):
			var x := PADDING.x + col * CELL_SIZE
			var y := PADDING.y + row * CELL_SIZE
			var cell_rect := Rect2(x, y, CELL_SIZE, CELL_SIZE)
			var checker := (row + col) % 2 == 0
			var bg_col := Color(0.96, 0.94, 0.86) if checker else Color(0.91, 0.88, 0.78)
			draw_rect(cell_rect, bg_col, true)
			draw_rect(cell_rect, Color(0.76, 0.72, 0.62, 0.55), false, 1.0)

			var center := Vector2(x + CELL_SIZE / 2.0, y + CELL_SIZE / 2.0)
			match int(grid[row][col]["element"]):
				START:
					_draw_start_icon(center)
				END:
					_draw_end_icon(center)
				PIT:
					_draw_pit_icon(center)
				BONE:
					_draw_bone_icon(center)

	# Draw walls on top of cells
	var wall_color := Color(0.24, 0.16, 0.10)
	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):
			var x := PADDING.x + col * CELL_SIZE
			var y := PADDING.y + row * CELL_SIZE
			if bool(grid[row][col]["top"]):
				draw_line(Vector2(x, y), Vector2(x + CELL_SIZE, y), wall_color, 5.0)
			if bool(grid[row][col]["bottom"]):
				draw_line(Vector2(x, y + CELL_SIZE), Vector2(x + CELL_SIZE, y + CELL_SIZE), wall_color, 5.0)
			if bool(grid[row][col]["left"]):
				draw_line(Vector2(x, y), Vector2(x, y + CELL_SIZE), wall_color, 5.0)
			if bool(grid[row][col]["right"]):
				draw_line(Vector2(x + CELL_SIZE, y), Vector2(x + CELL_SIZE, y + CELL_SIZE), wall_color, 5.0)

	# Draw permanent pit destination arrows
	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):
			var cell: Dictionary = grid[row][col]
			if int(cell["element"]) == PIT and cell["pit_destination"] != null:
				var dest = cell["pit_destination"]
				if dest is Vector2i:
					draw_arrow(cell_center(Vector2i(col, row)), cell_center(dest), Color(0.08, 0.68, 0.96), 3.0)
				elif dest is Dictionary and dest.has("x") and dest.has("y"):
					var dvec := Vector2i(int(dest["x"]), int(dest["y"]))
					draw_arrow(cell_center(Vector2i(col, row)), cell_center(dvec), Color(0.08, 0.68, 0.96), 3.0)

	# Draw live pit drag preview
	if draggingPit and hoveredCell.x != -1:
		draw_arrow(cell_center(draggedPit), cell_center(hoveredCell), Color(1.0, 0.82, 0.12), 3.5)

	# Selected cell highlight and wall handles
	if selectedCell.x != -1:
		var x := PADDING.x + selectedCell.x * CELL_SIZE
		var y := PADDING.y + selectedCell.y * CELL_SIZE
		draw_rect(Rect2(x, y, CELL_SIZE, CELL_SIZE), Color(0.2, 0.6, 1.0, 0.25), true)
		draw_circle(Vector2(x + CELL_SIZE / 2.0, y), HANDLE_SIZE, HANDLE_COLOR)
		draw_circle(Vector2(x + CELL_SIZE / 2.0, y + CELL_SIZE), HANDLE_SIZE, HANDLE_COLOR)
		draw_circle(Vector2(x, y + CELL_SIZE / 2.0), HANDLE_SIZE, HANDLE_COLOR)
		draw_circle(Vector2(x + CELL_SIZE, y + CELL_SIZE / 2.0), HANDLE_SIZE, HANDLE_COLOR)


func _notify_dirty() -> void:
	counts_changed.emit(startCount, endCount, boneCount)
	if get_tree() and get_tree().current_scene and get_tree().current_scene.has_method("mark_dirty"):
		get_tree().current_scene.mark_dirty()


func remove_existing_element(row: int, col: int) -> void:
	var existing := int(grid[row][col]["element"])
	if existing == EMPTY and grid[row][col]["pit_destination"] == null:
		return
	match existing:
		START:
			startCount = max(0, startCount - 1)
		END:
			endCount = max(0, endCount - 1)
		BONE:
			boneCount = max(0, boneCount - 1)
	grid[row][col]["element"] = EMPTY
	grid[row][col]["pit_destination"] = null
	_notify_dirty()


func place_element(row: int, col: int, element: int) -> void:
	if int(grid[row][col]["element"]) == element:
		return

	match element:
		START:
			if startCount >= 1:
				return
		END:
			if endCount >= 2:
				return
		BONE:
			if boneCount >= 5:
				return

	remove_existing_element(row, col)

	match element:
		START:
			startCount += 1
		END:
			endCount += 1
		BONE:
			boneCount += 1

	grid[row][col]["element"] = element
	_notify_dirty()


func get_cell_position(row: int, col: int) -> Vector2:
	return Vector2(PADDING.x + col * CELL_SIZE, PADDING.y + row * CELL_SIZE)


func point_in_circle(point: Vector2, center: Vector2, radius: float) -> bool:
	return point.distance_squared_to(center) <= radius * radius


func get_clicked_handle(mouse_pos: Vector2) -> String:
	if selectedCell.x == -1:
		return ""
	var pos := get_cell_position(selectedCell.y, selectedCell.x)
	var top := Vector2(pos.x + CELL_SIZE / 2.0, pos.y)
	var bottom := Vector2(pos.x + CELL_SIZE / 2.0, pos.y + CELL_SIZE)
	var left := Vector2(pos.x, pos.y + CELL_SIZE / 2.0)
	var right := Vector2(pos.x + CELL_SIZE, pos.y + CELL_SIZE / 2.0)

	if point_in_circle(mouse_pos, top, HANDLE_SIZE + 2.0):
		return "top"
	if point_in_circle(mouse_pos, bottom, HANDLE_SIZE + 2.0):
		return "bottom"
	if point_in_circle(mouse_pos, left, HANDLE_SIZE + 2.0):
		return "left"
	if point_in_circle(mouse_pos, right, HANDLE_SIZE + 2.0):
		return "right"
	return ""


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var pos: Vector2 = event.position - PADDING
		if pos.x < 0 or pos.y < 0:
			return
		var col := int(pos.x / CELL_SIZE)
		var row := int(pos.y / CELL_SIZE)
		if row < 0 or row >= GRID_SIZE or col < 0 or col >= GRID_SIZE:
			return

		selectedCell = Vector2i(col, row)

		if event.pressed:
			var handle := get_clicked_handle(event.position)
			if event.button_index == MOUSE_BUTTON_LEFT and handle != "":
				toggle_wall(selectedCell.y, selectedCell.x, handle)
				return

			if event.button_index == MOUSE_BUTTON_RIGHT:
				remove_existing_element(row, col)
				queue_redraw()
				return

			if currentTool == Tool.PIT:
				pendingPit = Vector2i(col, row)
				pitExists = (int(grid[row][col]["element"]) == PIT)
				if pitExists:
					draggedPit = pendingPit
				queue_redraw()
				return

			match currentTool:
				Tool.START:
					place_element(row, col, START)
				Tool.END:
					place_element(row, col, END)
				Tool.BONE:
					place_element(row, col, BONE)

			queue_redraw()
		else:
			if draggingPit:
				var destination := Vector2i(col, row)
				if destination != draggedPit:
					grid[draggedPit.y][draggedPit.x]["pit_destination"] = destination
					_notify_dirty()
				elif !pitExists and grid[draggedPit.y][draggedPit.x]["pit_destination"] == null:
					grid[draggedPit.y][draggedPit.x]["element"] = EMPTY
					_notify_dirty()

			draggingPit = false
			draggedPit = Vector2i(-1, -1)
			hoveredCell = Vector2i(-1, -1)
			pendingPit = Vector2i(-1, -1)
			pitExists = false
			queue_redraw()

	elif event is InputEventMouseMotion:
		var pos: Vector2 = event.position - PADDING
		if pos.x < 0 or pos.y < 0:
			return
		var col := int(pos.x / CELL_SIZE)
		var row := int(pos.y / CELL_SIZE)
		if row < 0 or row >= GRID_SIZE or col < 0 or col >= GRID_SIZE:
			return

		if draggingPit:
			hoveredCell = Vector2i(col, row)
			queue_redraw()
		elif pendingPit != Vector2i(-1, -1) and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
			if Vector2i(col, row) != pendingPit:
				if !pitExists:
					remove_existing_element(pendingPit.y, pendingPit.x)
					grid[pendingPit.y][pendingPit.x]["element"] = PIT
					_notify_dirty()
				draggingPit = true
				draggedPit = pendingPit
				hoveredCell = Vector2i(col, row)
				queue_redraw()


func toggle_wall(row: int, col: int, wall: String) -> void:
	if wall == "top" and row == 0:
		return
	if wall == "bottom" and row == GRID_SIZE - 1:
		return
	if wall == "left" and col == 0:
		return
	if wall == "right" and col == GRID_SIZE - 1:
		return

	match wall:
		"top":
			grid[row][col]["top"] = !bool(grid[row][col]["top"])
			if row > 0:
				grid[row - 1][col]["bottom"] = grid[row][col]["top"]
		"bottom":
			grid[row][col]["bottom"] = !bool(grid[row][col]["bottom"])
			if row < GRID_SIZE - 1:
				grid[row + 1][col]["top"] = grid[row][col]["bottom"]
		"left":
			grid[row][col]["left"] = !bool(grid[row][col]["left"])
			if col > 0:
				grid[row][col - 1]["right"] = grid[row][col]["left"]
		"right":
			grid[row][col]["right"] = !bool(grid[row][col]["right"])
			if col < GRID_SIZE - 1:
				grid[row][col + 1]["left"] = grid[row][col]["right"]

	queue_redraw()
	_notify_dirty()


func load_maze(grid_data: Array) -> void:
	grid = MazeSerializer.deserialize_grid(grid_data)
	startCount = 0
	endCount = 0
	boneCount = 0

	for row in range(grid.size()):
		for col in range(grid[row].size()):
			match int(grid[row][col]["element"]):
				START:
					startCount += 1
				END:
					endCount += 1
				BONE:
					boneCount += 1

	selectedCell = Vector2i(-1, -1)
	draggingPit = false
	draggedPit = Vector2i(-1, -1)
	hoveredCell = Vector2i(-1, -1)
	pendingPit = Vector2i(-1, -1)
	pitExists = false
	counts_changed.emit(startCount, endCount, boneCount)
	queue_redraw()
