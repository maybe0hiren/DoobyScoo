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
				"top": false,
				"bottom": false,
				"left": false,
				"right": false
			})

	queue_redraw()

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

	if selectedCell.x != -1:
		var x = PADDING.x + selectedCell.x * CELL_SIZE
		var y = PADDING.y + selectedCell.y * CELL_SIZE

		# Selected cell highlight
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

		# Wall Handles

		# Top
		draw_circle(
			Vector2(x + CELL_SIZE / 2, y),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Bottom
		draw_circle(
			Vector2(x + CELL_SIZE / 2, y + CELL_SIZE),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Left
		draw_circle(
			Vector2(x, y + CELL_SIZE / 2),
			HANDLE_SIZE,
			HANDLE_COLOR
		)

		# Right
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

# Mouse Input

func _gui_input(event):
	if event is InputEventMouseButton \
	and event.button_index == MOUSE_BUTTON_LEFT \
	and event.pressed:

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

		match currentTool:
			Tool.START:
				place_element(row, col, START)

			Tool.END:
				place_element(row, col, END)

			Tool.PIT:
				place_element(row, col, PIT)

			Tool.BONE:
				place_element(row, col, BONE)

		queue_redraw()
