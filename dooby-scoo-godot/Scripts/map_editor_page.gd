extends Control
@onready var grid_map: Control = $HBoxContainer/GridMap


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


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
	pass # Replace with function body.


func _on_undo_pressed() -> void:
	pass # Replace with function body.
