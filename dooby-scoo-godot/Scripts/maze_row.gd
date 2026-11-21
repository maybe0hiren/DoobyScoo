extends PanelContainer

signal play_requested(path: String)
signal edit_requested(path: String)
signal delete_requested(path: String)

var maze_path: String = ""
var _pending_name: String = ""
var _pending_author: String = ""
var _pending_size: String = ""
var _is_alt: bool = false

@onready var name_label: Label = $RowHBox/MazeName
@onready var author_label: Label = $RowHBox/AuthorLabel
@onready var grid_size_label: Label = $RowHBox/GridSizeLabel
@onready var play_button: Button = $RowHBox/HBoxContainer/Play
@onready var edit_button: Button = $RowHBox/HBoxContainer/Edit
@onready var delete_button: Button = $RowHBox/HBoxContainer/Delete


func configure(p_name: String, p_author: String, p_size: String, p_alt: bool = false) -> void:
	_pending_name = p_name
	_pending_author = p_author
	_pending_size = p_size
	_is_alt = p_alt
	if is_node_ready():
		_apply_values()


func _ready() -> void:
	var row_style := StyleBoxFlat.new()
	row_style.bg_color = Color(0.94, 0.91, 0.82, 0.96) if _is_alt else Color(0.99, 0.97, 0.91, 0.96)
	row_style.border_color = Color(0.78, 0.70, 0.54, 0.72)
	row_style.border_width_left = 1
	row_style.border_width_top = 1
	row_style.border_width_right = 1
	row_style.border_width_bottom = 2
	row_style.corner_radius_top_left = 12
	row_style.corner_radius_top_right = 12
	row_style.corner_radius_bottom_left = 12
	row_style.corner_radius_bottom_right = 12
	row_style.content_margin_left = 16
	row_style.content_margin_right = 12
	row_style.content_margin_top = 6
	row_style.content_margin_bottom = 6
	add_theme_stylebox_override("panel", row_style)

	# Clean, flat, single-surface My Maps row action buttons (Play: Green, Edit: Purple, Delete: Red)
	_style_subtle_row_button(play_button, Color(0.24, 0.64, 0.36, 1.0))
	_style_subtle_row_button(edit_button, Color(0.54, 0.52, 0.76, 1.0))
	_style_subtle_row_button(delete_button, Color(0.78, 0.30, 0.30, 1.0))

	play_button.pressed.connect(_on_play_pressed)
	edit_button.pressed.connect(_on_edit_pressed)
	delete_button.pressed.connect(_on_delete_pressed)
	_apply_values()


func _style_subtle_row_button(btn: Button, bg_col: Color) -> void:
	btn.add_theme_font_size_override("font_size", 14)
	btn.add_theme_color_override("font_color", Color.WHITE)
	btn.add_theme_color_override("font_hover_color", Color.WHITE)
	btn.add_theme_color_override("font_pressed_color", Color(0.95, 0.95, 0.95, 1.0))
	btn.add_theme_constant_override("outline_size", 0)
	btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

	var normal := StyleBoxFlat.new()
	normal.bg_color = bg_col
	normal.border_width_left = 0
	normal.border_width_top = 0
	normal.border_width_right = 0
	normal.border_width_bottom = 0
	normal.corner_radius_top_left = 10
	normal.corner_radius_top_right = 10
	normal.corner_radius_bottom_left = 10
	normal.corner_radius_bottom_right = 10
	normal.shadow_size = 0
	normal.anti_aliasing = true
	normal.content_margin_left = 12
	normal.content_margin_right = 12
	normal.content_margin_top = 5
	normal.content_margin_bottom = 5

	var hover: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	hover.bg_color = bg_col.lightened(0.07)

	var pressed: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	pressed.bg_color = bg_col.darkened(0.10)

	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("focus", StyleBoxEmpty.new())


func _apply_values() -> void:
	if !_pending_name.is_empty():
		name_label.text = _pending_name
	if !_pending_author.is_empty():
		author_label.text = _pending_author
	if !_pending_size.is_empty():
		grid_size_label.text = _pending_size


func _on_play_pressed() -> void:
	play_requested.emit(maze_path)


func _on_edit_pressed() -> void:
	edit_requested.emit(maze_path)


func _on_delete_pressed() -> void:
	delete_requested.emit(maze_path)
