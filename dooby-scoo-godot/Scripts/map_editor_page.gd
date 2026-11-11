extends Control

@onready var grid_map: Control = $HBoxContainer/GridMap
@onready var trainButton: Button = $HBoxContainer/Inventory/Train
@onready var startBtn: Button = $HBoxContainer/Inventory/Start
@onready var endBtn: Button = $HBoxContainer/Inventory/End
@onready var pitBtn: Button = $HBoxContainer/Inventory/Pit
@onready var boneBtn: Button = $HBoxContainer/Inventory/Bone
@onready var countsLabel: Label = get_node_or_null("HBoxContainer/Inventory/CountsLabel")

var isDirty := false
var pending_navigation: String = ""


func mark_dirty() -> void:
	if !isDirty:
		isDirty = true
		update_train_button()


func update_train_button() -> void:
	trainButton.disabled = MazeSession.editing_path.is_empty() or isDirty


func _update_tool_buttons() -> void:
	var active_col := Color(0.85, 1.0, 0.85)
	var normal_col := Color(1.0, 1.0, 1.0)
	startBtn.modulate = active_col if grid_map.currentTool == grid_map.Tool.START else normal_col
	endBtn.modulate = active_col if grid_map.currentTool == grid_map.Tool.END else normal_col
	pitBtn.modulate = active_col if grid_map.currentTool == grid_map.Tool.PIT else normal_col
	boneBtn.modulate = active_col if grid_map.currentTool == grid_map.Tool.BONE else normal_col


func _on_counts_changed(starts: int, ends: int, bones: int) -> void:
	if countsLabel != null:
		countsLabel.text = "Start: %d/1 | End: %d/2 | Bones: %d/5" % [starts, ends, bones]


func _ready() -> void:
	if grid_map.has_signal("counts_changed"):
		grid_map.counts_changed.connect(_on_counts_changed)
		_on_counts_changed(grid_map.startCount, grid_map.endCount, grid_map.boneCount)

	update_train_button()
	_update_tool_buttons()

	$UnsavedChangesDialog.get_ok_button().hide()
	$UnsavedChangesDialog.add_button("Save", true, "save")
	$UnsavedChangesDialog.add_button("Discard", false, "discard")
	$UnsavedChangesDialog.add_button("Cancel", false, "cancel")


func _on_start_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.START
	_update_tool_buttons()


func _on_end_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.END
	_update_tool_buttons()


func _on_pit_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.PIT
	_update_tool_buttons()


func _on_bone_pressed() -> void:
	grid_map.currentTool = grid_map.Tool.BONE
	_update_tool_buttons()


func save_existing_maze() -> bool:
	var success := MazeSerializer.save_to_path(
		grid_map.grid,
		MazeSession.editing_path
	)
	if success:
		MazeSession.loaded_maze = MazeSerializer.load_maze(MazeSession.editing_path)
		isDirty = false
		update_train_button()
		if !pending_navigation.is_empty():
			var dest := pending_navigation
			pending_navigation = ""
			get_tree().change_scene_to_file(dest)
		else:
			$SuccessDialog.dialog_text = "Maze updated successfully!"
			$SuccessDialog.popup_centered()
	else:
		pending_navigation = ""
		$ErrorDialog.dialog_text = "Failed to overwrite maze."
		$ErrorDialog.popup_centered()
	return success


func _validate_current_maze() -> bool:
	var result := MazeValidator.validate(grid_map.grid)
	if !result.success:
		$ErrorDialog.dialog_text = "\n".join(result.errors)
		$ErrorDialog.popup_centered()
		return false

	var solve_res := MazeSolver.is_solvable(grid_map.grid)
	if !solve_res.success:
		$ErrorDialog.dialog_text = "Maze is not solvable: " + str(solve_res.get("error", ""))
		$ErrorDialog.popup_centered()
		return false

	return true


func _on_save_pressed() -> void:
	if !_validate_current_maze():
		pending_navigation = ""
		return

	if !MazeSession.editing_path.is_empty() and !isDirty:
		if !pending_navigation.is_empty():
			var dest := pending_navigation
			pending_navigation = ""
			get_tree().change_scene_to_file(dest)
		return

	if !MazeSession.editing_path.is_empty() and isDirty:
		save_existing_maze()
		return

	$SaveDialog.popup_centered()


func _on_save_dialog_confirmed() -> void:
	var maze_name: String = $SaveDialog/VBoxContainer/MazeName.text
	var username: String = $SaveDialog/VBoxContainer/UserName.text

	var success := MazeSerializer.save(
		grid_map.grid,
		maze_name,
		username
	)

	if success:
		MazeSession.editing_path = MazeSerializer.last_saved_path
		MazeSession.loaded_maze = MazeSerializer.load_maze(MazeSession.editing_path)
		isDirty = false
		update_train_button()

		if !pending_navigation.is_empty():
			var dest := pending_navigation
			pending_navigation = ""
			get_tree().change_scene_to_file(dest)
		else:
			$SuccessDialog.dialog_text = "Maze saved successfully!"
			$SuccessDialog.popup_centered()
	else:
		pending_navigation = ""
		$ErrorDialog.dialog_text = "Failed to save maze."
		$ErrorDialog.popup_centered()


func _on_train_pressed() -> void:
	if MazeSession.editing_path.is_empty() or isDirty:
		$ErrorDialog.dialog_text = "Please save your maze before starting training or gameplay."
		$ErrorDialog.popup_centered()
		return

	if !_validate_current_maze():
		return

	MazeSession.loaded_maze = MazeSerializer.load_maze(MazeSession.editing_path)
	get_tree().change_scene_to_file("res://scenes/gameplay_page.tscn")


func _on_unsaved_changes_dialog_custom_action(action: String) -> void:
	$UnsavedChangesDialog.hide()
	match action:
		"save":
			pending_navigation = "res://scenes/landing_page.tscn"
			_on_save_pressed()
		"discard":
			pending_navigation = ""
			MazeSession.reset_session()
			get_tree().change_scene_to_file("res://scenes/landing_page.tscn")
		"cancel":
			pending_navigation = ""


func _on_home_pressed() -> void:
	if isDirty:
		$UnsavedChangesDialog.popup_centered()
	else:
		MazeSession.reset_session()
		get_tree().change_scene_to_file("res://scenes/landing_page.tscn")
