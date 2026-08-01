extends Control

# Grid Configuration

const GRID_SIZE := 10
const CELL_SIZE := 60
const PADDING := Vector2(20, 20)

const HANDLE_SIZE := 8
const HANDLE_COLOR := Color.ORANGE

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4


# Grid Data

var grid = []

var selectedCell := Vector2i(-1, -1)

var startCount := 0
var endCount := 0
var boneCount := 0

var draggingPit := false          # True only after an actual drag begins
var draggedPit := Vector2i(-1, -1)
var hoveredCell := Vector2i(-1, -1)

var pendingPit := Vector2i(-1, -1)   # Cell where mouse was pressed
var pitExists := false               # Was there already a pit here?

# Tool Selection

enum Tool {
	NONE,
	START,
	END,
	PIT,
	BONE
}

var currentTool = Tool.NONE

# Initialization

func _ready():
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

	queue_redraw()
	if !MazeSession.loaded_maze.is_empty():
		load_maze(MazeSession.loaded_maze["grid"])

func cell_center(cell: Vector2i) -> Vector2:
	return PADDING + Vector2(
		cell.x * CELL_SIZE + CELL_SIZE / 2.0,
		cell.y * CELL_SIZE + CELL_SIZE / 2.0
	)
	
func draw_arrow(start: Vector2, end: Vector2, color: Color, width: float = 3.0):
	draw_line(start, end, color, width)

	var direction = (end - start).normalized()
	var arrow_length = 12.0
	var arrow_angle = deg_to_rad(30)

	var left = end - direction.rotated(arrow_angle) * arrow_length
	var right = end - direction.rotated(-arrow_angle) * arrow_length

	draw_line(end, left, color, width)
	draw_line(end, right, color, width)

# Drawing

func _draw():
	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):
			var x = PADDING.x + col * CELL_SIZE
			var y = PADDING.y + row * CELL_SIZE

			draw_rect(
				Rect2(x, y, CELL_SIZE, CELL_SIZE),
				Color.WHITE,
				false,
				2.0
			)

			# Walls
			if grid[row][col]["top"]:
				draw_line(
					Vector2(x, y),
					Vector2(x + CELL_SIZE, y),
					Color.BLACK,
					6.0
				)

			if grid[row][col]["bottom"]:
				draw_line(
					Vector2(x, y + CELL_SIZE),
					Vector2(x + CELL_SIZE, y + CELL_SIZE),
					Color.BLACK,
					6.0
				)

			if grid[row][col]["left"]:
				draw_line(
					Vector2(x, y),
					Vector2(x, y + CELL_SIZE),
					Color.BLACK,
					6.0
				)

			if grid[row][col]["right"]:
				draw_line(
					Vector2(x + CELL_SIZE, y),
					Vector2(x + CELL_SIZE, y + CELL_SIZE),
					Color.BLACK,
					6.0
				)

			match grid[row][col]["element"]:
				START:
					draw_circle(
 						Vector2(x + CELL_SIZE / 2, y + CELL_SIZE / 2),
						10,
						Color.GREEN
					)

				END:
					draw_circle(
						Vector2(x + CELL_SIZE / 2, y + CELL_SIZE / 2),
						10,
						Color.RED
					)

				PIT:
					draw_circle(
						Vector2(x + CELL_SIZE / 2, y + CELL_SIZE / 2),
						10,
						Color.BLACK
					)

				BONE:
					draw_circle(
						Vector2(x + CELL_SIZE / 2, y + CELL_SIZE / 2),
						10,
						Color.YELLOW
					)

	# Draw permanent pit connections
	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):
			var cell = grid[row][col]

			if cell["element"] == PIT and cell["pit_destination"] != null:

				var dest = cell["pit_destination"]

				print("TYPE:", typeof(dest))
				print("VALUE:", dest)

				if dest is Vector2i:
					draw_arrow(
						cell_center(Vector2i(col, row)),
						cell_center(dest),
						Color.DEEP_SKY_BLUE,
						3
				)
				else:
					print("INVALID DESTINATION")

	# Draw live drag preview
	if draggingPit:
		draw_arrow(
			cell_center(draggedPit),
			cell_center(hoveredCell),
			Color.YELLOW,
			3
		)

	# Selected cell highlight and wall handles
	if selectedCell.x != -1:
		var x = PADDING.x + selectedCell.x * CELL_SIZE
		var y = PADDING.y + selectedCell.y * CELL_SIZE

		draw_rect(
			Rect2(
				x,
				y,
				CELL_SIZE,
				CELL_SIZE
			),
			Color(0.2, 0.6, 1.0, 0.3),
			true
		)

		# Top Handle
		draw_circle(
			Vector2(x + CELL_SIZE / 2, y),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Bottom Handle
		draw_circle(
			Vector2(x + CELL_SIZE / 2, y + CELL_SIZE),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Left Handle
		draw_circle(
			Vector2(x, y + CELL_SIZE / 2),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Right Handle
		draw_circle(
			Vector2(x + CELL_SIZE, y + CELL_SIZE / 2),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

# Element Helpers

func remove_existing_element(row: int, col: int):
	match grid[row][col]["element"]:
		START:
			startCount -= 1
		END:
			endCount -= 1
		BONE:
			boneCount -= 1

	grid[row][col]["element"] = EMPTY
	get_tree().current_scene.mark_dirty()


func place_element(row: int, col: int, element: int):
	if grid[row][col]["element"] == element:
		return

	remove_existing_element(row, col)

	match element:
		START:
			if startCount >= 1:
				return
			startCount += 1

		END:
			if endCount >= 2:
				return
			endCount += 1

		BONE:
			if boneCount >= 5:
				return
			boneCount += 1

	grid[row][col]["element"] = element
	get_tree().current_scene.mark_dirty()
	
func get_cell_position(row: int, col: int) -> Vector2:
	return Vector2(
		PADDING.x + col * CELL_SIZE,
		PADDING.y + row * CELL_SIZE
	)


func point_in_circle(point: Vector2, center: Vector2, radius: float) -> bool:
	return point.distance_squared_to(center) <= radius * radius


func get_clicked_handle(mouse_pos: Vector2) -> String:
	if selectedCell.x == -1:
		return ""

	var pos = get_cell_position(selectedCell.y, selectedCell.x)

	var top = Vector2(pos.x + CELL_SIZE / 2, pos.y)
	var bottom = Vector2(pos.x + CELL_SIZE / 2, pos.y + CELL_SIZE)
	var left = Vector2(pos.x, pos.y + CELL_SIZE / 2)
	var right = Vector2(pos.x + CELL_SIZE, pos.y + CELL_SIZE / 2)

	if point_in_circle(mouse_pos, top, HANDLE_SIZE):
		return "top"

	if point_in_circle(mouse_pos, bottom, HANDLE_SIZE):
		return "bottom"

	if point_in_circle(mouse_pos, left, HANDLE_SIZE):
		return "left"

	if point_in_circle(mouse_pos, right, HANDLE_SIZE):
		return "right"

	return ""

# Mouse Input

func _gui_input(event):
	if event is InputEventMouseButton:

		var pos = event.position - PADDING

		if pos.x < 0 or pos.y < 0:
			return

		var col = int(pos.x / CELL_SIZE)
		var row = int(pos.y / CELL_SIZE)

		if row < 0 or row >= GRID_SIZE:
			return

		if col < 0 or col >= GRID_SIZE:
			return

		selectedCell = Vector2i(col, row)

		if event.pressed:

			var handle = get_clicked_handle(event.position)

			if event.button_index == MOUSE_BUTTON_LEFT and handle != "":
				toggle_wall(selectedCell.y, selectedCell.x, handle)
				return

			if event.button_index == MOUSE_BUTTON_RIGHT:
				remove_existing_element(row, col)
				queue_redraw()
				return

			if currentTool == Tool.PIT:
				pendingPit = Vector2i(col, row)
				pitExists = (grid[row][col]["element"] == PIT)

				if pitExists:
					draggedPit = pendingPit

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
			# Mouse released
			if draggingPit:
				var destination = Vector2i(col, row)

				if destination != draggedPit:
					grid[draggedPit.y][draggedPit.x]["pit_destination"] = destination
					get_tree().current_scene.mark_dirty()

			draggingPit = false
			draggedPit = Vector2i(-1, -1)
			hoveredCell = Vector2i(-1, -1)
			pendingPit = Vector2i(-1, -1)
			pitExists = false

			queue_redraw()

	elif event is InputEventMouseMotion:

		var pos = event.position - PADDING

		if pos.x < 0 or pos.y < 0:
			return

		var col = int(pos.x / CELL_SIZE)
		var row = int(pos.y / CELL_SIZE)

		if row < 0 or row >= GRID_SIZE:
			return

		if col < 0 or col >= GRID_SIZE:
			return

		if draggingPit:
			hoveredCell = Vector2i(col, row)
			queue_redraw()

		elif pendingPit != Vector2i(-1, -1) and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):

			if Vector2i(col, row) != pendingPit:

				if !pitExists:
					grid[pendingPit.y][pendingPit.x]["element"] = PIT
					get_tree().current_scene.mark_dirty()

				draggingPit = true
				draggedPit = pendingPit
				hoveredCell = Vector2i(col, row)
				queue_redraw()
		
func toggle_wall(row: int, col: int, wall: String):
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
			grid[row][col]["top"] = !grid[row][col]["top"]

			if row > 0:
				grid[row - 1][col]["bottom"] = grid[row][col]["top"]

		"bottom":
			grid[row][col]["bottom"] = !grid[row][col]["bottom"]

			if row < GRID_SIZE - 1:
				grid[row + 1][col]["top"] = grid[row][col]["bottom"]

		"left":
			grid[row][col]["left"] = !grid[row][col]["left"]

			if col > 0:
				grid[row][col - 1]["right"] = grid[row][col]["left"]

		"right":
			grid[row][col]["right"] = !grid[row][col]["right"]

			if col < GRID_SIZE - 1:
				grid[row][col + 1]["left"] = grid[row][col]["right"]

	queue_redraw()
	get_tree().current_scene.mark_dirty()

func load_maze(grid_data: Array) -> void:
	print("LOAD MAZE CALLED")

	grid = grid_data.duplicate(true)

	startCount = 0
	endCount = 0
	boneCount = 0

	for row in range(GRID_SIZE):
		for col in range(GRID_SIZE):

			# Restore element type
			grid[row][col]["element"] = int(grid[row][col]["element"])

			# Restore pit destination
			var pit = grid[row][col]["pit_destination"]

			if pit != null:
				if pit is Dictionary:
					grid[row][col]["pit_destination"] = Vector2i(
						int(pit["x"]),
						int(pit["y"])
					)
				elif pit is Array and pit.size() == 2:
					grid[row][col]["pit_destination"] = Vector2i(
						int(pit[0]),
						int(pit[1])
					)

			match grid[row][col]["element"]:
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

	queue_redraw()

	print("Loaded counts:", startCount, endCount, boneCount)
