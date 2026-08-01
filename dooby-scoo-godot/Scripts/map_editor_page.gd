extends Control
@onready var grid_map: Control = $HBoxContainer/GridMap
@onready var trainButton: Button = $HBoxContainer/Inventory/Train

var isDirty := false

func mark_dirty() -> void:
	if !isDirty:
		isDirty = true
		update_train_button()

func update_train_button() -> void:
	trainButton.disabled = MazeSession.editing_path.is_empty() or isDirty

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	print("MapEditorPage Ready")
	update_train_button()
	$UnsavedChangesDialog.get_ok_button().hide()
	$UnsavedChangesDialog.add_button("Save", true, "save")
	$UnsavedChangesDialog.add_button("Discard", false, "discard")


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

func save_existing_maze() -> void:
	print("Saving existing maze...")

	var success = MazeSerializer.save_to_path(
		$HBoxContainer/GridMap.grid,
		MazeSession.editing_path
	)

	if success:
		isDirty = false
		update_train_button()

func _on_save_pressed() -> void:
	print("Save button pressed")

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

	# Existing maze and no changes -> nothing to do
	if !MazeSession.editing_path.is_empty() and !isDirty:
		print("No changes to save.")
		return

	# Existing maze with changes -> overwrite directly
	if !MazeSession.editing_path.is_empty() and isDirty:
		save_existing_maze()
		return

	# New maze -> ask for name and username
	$SaveDialog.popup_centered()


func _on_save_dialog_confirmed() -> void:
	print("Confirmed")

	var maze_name = $SaveDialog/VBoxContainer/MazeName.text
	var username = $SaveDialog/VBoxContainer/UserName.text

	var success = MazeSerializer.save(
		$HBoxContainer/GridMap.grid,
		maze_name,
		username
	)

	if success:

		# This maze is now an existing maze
		MazeSession.editing_path = "user://Mazes/" + maze_name.strip_edges().replace(" ", "_") + ".json"

		isDirty = false
		update_train_button()

		$SuccessDialog.dialog_text = "Maze saved successfully!"
		$SuccessDialog.popup_centered()

	else:
		$ErrorDialog.dialog_text = "Failed to save maze."
		$ErrorDialog.popup_centered()


func _on_unsaved_changes_dialog_custom_action(action: String) -> void:

	match action:

		"save":
			_on_save_pressed()

			# If saving succeeded, leave the editor
			if !isDirty:
				get_tree().change_scene_to_file("res://scenes/landing_page.tscn")

		"discard":
			get_tree().change_scene_to_file("res://scenes/landing_page.tscn")


func _on_home_pressed() -> void:
	if isDirty:
		$UnsavedChangesDialog.popup_centered()
	else:
		get_tree().change_scene_to_file("res://scenes/landing_page.tscn")
