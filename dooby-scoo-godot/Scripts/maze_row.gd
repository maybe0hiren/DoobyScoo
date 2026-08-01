extends HBoxContainer


signal edit_requested(path: String)
signal delete_requested(path: String)

var maze_path: String = "";
@onready var edit_button: Button = $HBoxContainer/Edit
@onready var delete_button: Button = $HBoxContainer/Delete


func _ready() -> void:
	edit_button.pressed.connect(_on_edit_pressed)
	delete_button.pressed.connect(_on_delete_pressed)


func _on_edit_pressed() -> void:
	edit_requested.emit(maze_path)


func _on_delete_pressed() -> void:
	delete_requested.emit(maze_path)
