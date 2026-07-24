extends Control
@onready var grid_map: Control = $HBoxContainer/GridMap


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	print("MapEditorPage Ready")


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass


func _on_start_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.START;
	print(grid_map.currentTool);


func _on_end_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.END;
	print(grid_map.currentTool);
	
func _on_pit_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.PIT;
	print(grid_map.currentTool);


func _on_bone_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.BONE;
	print(grid_map.currentTool)


func _on_save_pressed() -> void:
	print("Save button pressed");
	var result = MazeValidator.validate($HBoxContainer/GridMap.grid)

	if !result.success:
		$ErrorDialog.dialog_text = "\n".join(result.errors)
		$ErrorDialog.popup_centered()
		return

	result = MazeSolver.is_solvable($HBoxContainer/GridMap.grid)

	if !result.success:
		$ErrorDialog.dialog_text = "Maze is not solvable."
		$ErrorDialog.popup_centered()
		return

	$SaveDialog.popup_centered()


func _on_save_dialog_confirmed() -> void:
	print("Confirmed");
	var maze_name = $SaveDialog/VBoxContainer/MazeName.text
	var username = $SaveDialog/VBoxContainer/UserName.text

	var success = MazeSerializer.save(
		$HBoxContainer/GridMap.grid,
		maze_name,
		username
	)

	if success:
		$SuccessDialog.dialog_text = "Maze saved successfully!"
		$SuccessDialog.popup_centered()
	else:
		$ErrorDialog.dialog_text = "Failed to save maze."
		$ErrorDialog.popup_centered()
