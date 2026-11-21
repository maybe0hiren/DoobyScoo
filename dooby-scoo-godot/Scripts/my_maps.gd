extends Control

const ROW_SCENE = preload("res://scenes/mazeRow.tscn")
const SAVE_DIR = "user://Mazes/"

var pending_delete_path: String = ""

@onready var card_panel: PanelContainer = $OuterMargin/CardPanel
@onready var back_btn: Button = $OuterMargin/CardPanel/VBoxContainer/Header/BackButton
@onready var new_maze_btn: Button = $OuterMargin/CardPanel/VBoxContainer/Header/NewMazeButton
@onready var title_label: Label = $OuterMargin/CardPanel/VBoxContainer/Header/Title


func _ready() -> void:
	_apply_theme()
	MazeSession.ensure_default_maps()
	load_saved_mazes()


func _apply_theme() -> void:
	card_panel.add_theme_stylebox_override("panel", DoobyUI.make_parchment_panel(22, 3, 24, 20))
	DoobyUI.style_lavender_button(back_btn, 17, 20)
	DoobyUI.style_green_button(new_maze_btn, 17, 20)
	title_label.label_settings = DoobyUI.make_heading_settings(34, DoobyUI.COL_TEXT_CREAM, 7)


func load_saved_mazes() -> void:
	var container: Control = $OuterMargin/CardPanel/VBoxContainer/ScrollContainer/VBoxContainer2
	for child in container.get_children():
		child.queue_free()

	var dir := DirAccess.open(SAVE_DIR)
	if dir == null:
		return

	var files: Array[String] = []
	dir.list_dir_begin()
	while true:
		var file_name := dir.get_next()
		if file_name == "":
			break
		if !dir.current_is_dir() and file_name.ends_with(".json"):
			files.append(file_name)
	dir.list_dir_end()
	files.sort()

	var idx: int = 0
	for file_name in files:
		var path := SAVE_DIR + file_name
		var data := MazeSerializer.load_maze(path)
		if data.is_empty():
			continue

		var row: PanelContainer = ROW_SCENE.instantiate()
		row.maze_path = path
		if row.has_signal("play_requested"):
			row.play_requested.connect(_on_play_requested)
		row.delete_requested.connect(_on_delete_requested)
		row.edit_requested.connect(_on_edit_requested)

		var meta: Dictionary = data.get("metadata", {})
		var maze_name_str: String = str(meta.get("maze_name", file_name.get_basename()))
		var author_str: String = str(meta.get("author", "Player"))
		var gsize: int = int(meta.get("grid_size", 10))
		if row.has_method("configure"):
			row.configure(maze_name_str, author_str, "%dx%d" % [gsize, gsize], (idx % 2 == 1))

		container.add_child(row)
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		idx += 1


func _on_back_button_pressed() -> void:
	MazeSession.transition_to("res://scenes/landing_page.tscn")


func _on_new_maze_button_pressed() -> void:
	MazeSession.reset_session()
	MazeSession.transition_to("res://scenes/map_editor_page.tscn")


func _on_play_requested(path: String) -> void:
	var data := MazeSerializer.load_maze(path)
	if data.is_empty():
		push_error("Failed to load maze for gameplay.")
		return
	MazeSession.loaded_maze = data
	MazeSession.editing_path = path
	MazeSession.transition_to("res://scenes/gameplay_page.tscn")


func _on_delete_requested(path: String) -> void:
	pending_delete_path = path
	$DeleteDialog.dialog_text = "Are you sure you want to delete this maze?\n\nThis action cannot be undone."
	$DeleteDialog.popup_centered()


func _on_edit_requested(path: String) -> void:
	var data := MazeSerializer.load_maze(path)
	if data.is_empty():
		push_error("Failed to load maze.")
		return
	MazeSession.loaded_maze = data
	MazeSession.editing_path = path
	MazeSession.transition_to("res://scenes/map_editor_page.tscn")


func _on_delete_dialog_confirmed() -> void:
	if pending_delete_path.is_empty():
		return
	var error := DirAccess.remove_absolute(
		ProjectSettings.globalize_path(pending_delete_path)
	)
	if error != OK:
		push_error("Failed to delete maze.")
	pending_delete_path = ""
	load_saved_mazes()
