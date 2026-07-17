extends Control

const GRID_SIZE = 10;
const PADDING = Vector2(20, 20);
const CELL_SIZE = 60;
var selectedCell := Vector2i(-1, -1);

func _ready():
	queue_redraw()
	print("GridMap ready")

func _draw():
	for row in range(10):
		for col in range(10):
			draw_rect(
				Rect2(
					PADDING.x + col * CELL_SIZE,
					PADDING.y + row * CELL_SIZE,
					CELL_SIZE,
					CELL_SIZE
				),
				Color.WHITE,
				false,
				2.0
			)
	if selectedCell.x != -1:
		draw_rect(
			Rect2(
				PADDING.x + selectedCell.x * CELL_SIZE,
				PADDING.y + selectedCell.y * CELL_SIZE,
				CELL_SIZE,
				CELL_SIZE
			),
			Color(0.2, 0.6, 1.0, 0.3),
			true
		)
			
func _gui_input(event):
	if event is InputEventMouseButton and event.pressed:
		var pos = event.position - PADDING

		if pos.x < 0 or pos.y < 0:
			return

		var col = int(pos.x / CELL_SIZE)
		var row = int(pos.y / CELL_SIZE)

		if row >= 0 and row < GRID_SIZE and col >= 0 and col < GRID_SIZE:
			selectedCell = Vector2i(col, row)
			queue_redraw()
