extends RefCounted

class_name DoobyUI

# ==============================================================================
# DOOBYSCOO SHARED GAME UI THEME & STYLING HELPERS
# Cohesive cartoon/game visual identity shared across Home, My Maps, Editor,
# Gameplay, and Multiplayer Arena.
# ==============================================================================

const COL_PARCHMENT := Color(0.97, 0.95, 0.87, 0.95)
const COL_PARCHMENT_ALT := Color(0.93, 0.90, 0.80, 0.96)
const COL_PARCHMENT_BORDER := Color(0.55, 0.38, 0.18, 0.95)

const COL_MEADOW_DARK := Color(0.13, 0.22, 0.16, 0.94)
const COL_MEADOW_DEEP := Color(0.09, 0.16, 0.12, 0.95)
const COL_MEADOW_CARD := Color(0.16, 0.27, 0.19, 0.95)

const COL_GOLD := Color(0.96, 0.74, 0.18, 1.0)
const COL_GOLD_BRIGHT := Color(1.0, 0.93, 0.56, 1.0)
const COL_GOLD_BORDER := Color(0.96, 0.84, 0.46, 1.0)
const COL_BROWN_INK := Color(0.24, 0.14, 0.06, 1.0)
const COL_FOREST_INK := Color(0.14, 0.20, 0.13, 1.0)
const COL_FOREST_MUTED := Color(0.32, 0.40, 0.30, 1.0)

const COL_LAVENDER := Color(0.56, 0.55, 0.78, 1.0)
const COL_LAVENDER_BORDER := Color(0.82, 0.81, 0.96, 1.0)
const COL_GREEN_BTN := Color(0.22, 0.66, 0.35, 1.0)
const COL_GREEN_BORDER := Color(0.58, 0.92, 0.66, 1.0)
const COL_DANGER_BTN := Color(0.78, 0.26, 0.26, 1.0)
const COL_DANGER_BORDER := Color(0.98, 0.60, 0.58, 1.0)

const COL_TEXT_CREAM := Color(1.0, 0.96, 0.84, 1.0)
const COL_TEXT_LIGHT := Color(0.94, 0.97, 0.94, 1.0)
const COL_TEXT_MUTED := Color(0.74, 0.82, 0.76, 1.0)


static func make_parchment_panel(radius: int = 22, border_width: int = 3, pad_x: int = 20, pad_y: int = 16) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = COL_PARCHMENT
	s.border_color = COL_PARCHMENT_BORDER
	s.border_width_left = border_width
	s.border_width_top = border_width
	s.border_width_right = border_width
	s.border_width_bottom = border_width + 4
	s.corner_radius_top_left = radius
	s.corner_radius_top_right = radius
	s.corner_radius_bottom_left = radius
	s.corner_radius_bottom_right = radius
	s.shadow_size = 8
	s.shadow_color = Color(0.10, 0.08, 0.04, 0.28)
	s.shadow_offset = Vector2(0, 5)
	s.content_margin_left = pad_x
	s.content_margin_right = pad_x
	s.content_margin_top = pad_y
	s.content_margin_bottom = pad_y
	return s


static func make_meadow_panel(
	bg: Color = COL_MEADOW_DARK,
	border: Color = COL_GOLD_BORDER,
	radius: int = 18,
	border_width: int = 3,
	pad_x: int = 16,
	pad_y: int = 14
) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.border_width_left = border_width
	s.border_width_top = border_width
	s.border_width_right = border_width
	s.border_width_bottom = border_width + 3
	s.corner_radius_top_left = radius
	s.corner_radius_top_right = radius
	s.corner_radius_bottom_left = radius
	s.corner_radius_bottom_right = radius
	s.shadow_size = 7
	s.shadow_color = Color(0, 0, 0, 0.32)
	s.shadow_offset = Vector2(0, 4)
	s.content_margin_left = pad_x
	s.content_margin_right = pad_x
	s.content_margin_top = pad_y
	s.content_margin_bottom = pad_y
	return s


static func make_row_card(is_alt: bool = false) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = COL_PARCHMENT_ALT if is_alt else Color(1.0, 0.98, 0.92, 0.96)
	s.border_color = Color(0.76, 0.66, 0.48, 0.85)
	s.border_width_left = 2
	s.border_width_top = 2
	s.border_width_right = 2
	s.border_width_bottom = 4
	s.corner_radius_top_left = 14
	s.corner_radius_top_right = 14
	s.corner_radius_bottom_left = 14
	s.corner_radius_bottom_right = 14
	s.content_margin_left = 16
	s.content_margin_right = 14
	s.content_margin_top = 8
	s.content_margin_bottom = 8
	return s


static func make_pill(bg: Color, border: Color = Color(1, 1, 1, 0.25), radius: int = 16) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.border_width_left = 2
	s.border_width_top = 2
	s.border_width_right = 2
	s.border_width_bottom = 2
	s.corner_radius_top_left = radius
	s.corner_radius_top_right = radius
	s.corner_radius_bottom_left = radius
	s.corner_radius_bottom_right = radius
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 5
	s.content_margin_bottom = 5
	return s


static func style_button(
	btn: Button,
	base_color: Color,
	border_color: Color,
	font_color: Color = Color.WHITE,
	font_size: int = 18,
	radius: int = 24,
	bevel: int = 5
) -> void:
	btn.add_theme_font_size_override("font_size", font_size)
	btn.add_theme_color_override("font_color", font_color)
	btn.add_theme_color_override("font_hover_color", font_color.lightened(0.12))
	btn.add_theme_color_override("font_pressed_color", font_color.darkened(0.06))
	btn.add_theme_color_override("font_disabled_color", Color(0.75, 0.77, 0.74, 0.72))
	btn.add_theme_color_override("font_outline_color", COL_BROWN_INK)
	btn.add_theme_constant_override("outline_size", 4)
	btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND

	var normal := StyleBoxFlat.new()
	normal.bg_color = base_color
	normal.border_color = border_color
	normal.border_width_left = 2
	normal.border_width_top = 2
	normal.border_width_right = 2
	normal.border_width_bottom = 2 + bevel
	normal.corner_radius_top_left = radius
	normal.corner_radius_top_right = radius
	normal.corner_radius_bottom_left = radius
	normal.corner_radius_bottom_right = radius
	normal.shadow_size = 4
	normal.shadow_color = Color(0, 0, 0, 0.28)
	normal.shadow_offset = Vector2(0, 3)
	normal.content_margin_left = 16
	normal.content_margin_right = 16
	normal.content_margin_top = 8
	normal.content_margin_bottom = 8 + int(bevel * 0.4)

	var hover: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	hover.bg_color = base_color.lightened(0.09)
	hover.border_color = border_color.lightened(0.14)
	hover.shadow_size = 6

	var pressed: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	pressed.bg_color = base_color.darkened(0.09)
	pressed.border_width_bottom = 2
	pressed.shadow_size = 1
	pressed.shadow_offset = Vector2(0, 1)
	pressed.content_margin_top = 10
	pressed.content_margin_bottom = 6

	var disabled: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	disabled.bg_color = Color(0.42, 0.46, 0.43, 0.65)
	disabled.border_color = Color(0.55, 0.58, 0.55, 0.55)
	disabled.border_width_bottom = 3
	disabled.shadow_size = 0

	btn.add_theme_stylebox_override("normal", normal)
	btn.add_theme_stylebox_override("hover", hover)
	btn.add_theme_stylebox_override("pressed", pressed)
	btn.add_theme_stylebox_override("focus", hover)
	btn.add_theme_stylebox_override("disabled", disabled)

	if !btn.has_meta("dooby_anim_bound"):
		btn.set_meta("dooby_anim_bound", true)
		btn.resized.connect(func(): btn.pivot_offset = btn.size * 0.5)
		btn.mouse_entered.connect(func():
			if btn.disabled:
				return
			btn.pivot_offset = btn.size * 0.5
			var tw := btn.create_tween()
			tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(btn, "scale", Vector2(1.03, 1.03), 0.10)
		)
		btn.mouse_exited.connect(func():
			btn.pivot_offset = btn.size * 0.5
			var tw := btn.create_tween()
			tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_property(btn, "scale", Vector2.ONE, 0.09)
		)
		btn.button_down.connect(func():
			if btn.disabled:
				return
			btn.pivot_offset = btn.size * 0.5
			var tw := btn.create_tween()
			tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_property(btn, "scale", Vector2(0.96, 0.96), 0.06)
		)
		btn.button_up.connect(func():
			btn.pivot_offset = btn.size * 0.5
			var tw := btn.create_tween()
			tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_property(btn, "scale", Vector2.ONE, 0.08)
		)


static func style_gold_button(btn: Button, font_size: int = 22, radius: int = 28) -> void:
	style_button(btn, COL_GOLD, COL_GOLD_BRIGHT, Color(1.0, 0.99, 0.92, 1.0), font_size, radius, 6)


static func style_green_button(btn: Button, font_size: int = 18, radius: int = 22) -> void:
	style_button(btn, COL_GREEN_BTN, COL_GREEN_BORDER, Color.WHITE, font_size, radius, 5)


static func style_lavender_button(btn: Button, font_size: int = 18, radius: int = 24) -> void:
	style_button(btn, COL_LAVENDER, COL_LAVENDER_BORDER, Color.WHITE, font_size, radius, 5)


static func style_danger_button(btn: Button, font_size: int = 16, radius: int = 20) -> void:
	style_button(btn, COL_DANGER_BTN, COL_DANGER_BORDER, Color.WHITE, font_size, radius, 4)


static func style_subtle_button(btn: Button, font_size: int = 16, radius: int = 18) -> void:
	style_button(
		btn,
		Color(0.22, 0.31, 0.24, 0.95),
		Color(0.56, 0.68, 0.58, 0.85),
		COL_TEXT_CREAM,
		font_size,
		radius,
		3
	)


static func style_tool_button(btn: Button, is_selected: bool, font_size: int = 18) -> void:
	if is_selected:
		style_button(
			btn,
			Color(0.25, 0.62, 0.36, 1.0),
			COL_GOLD_BRIGHT,
			Color(1.0, 0.99, 0.92, 1.0),
			font_size,
			16,
			5
		)
	else:
		style_button(
			btn,
			Color(0.95, 0.92, 0.82, 1.0),
			Color(0.68, 0.56, 0.38, 0.95),
			COL_FOREST_INK,
			font_size,
			16,
			4
		)
		btn.add_theme_constant_override("outline_size", 0)
		btn.add_theme_color_override("font_color", COL_FOREST_INK)
		btn.add_theme_color_override("font_hover_color", COL_BROWN_INK)
		btn.add_theme_color_override("font_pressed_color", COL_BROWN_INK)


static func make_heading_settings(size: int = 34, color: Color = COL_TEXT_CREAM, outline: int = 7) -> LabelSettings:
	var ls := LabelSettings.new()
	ls.font_size = size
	ls.font_color = color
	ls.outline_size = outline
	ls.outline_color = COL_BROWN_INK
	ls.shadow_size = 4
	ls.shadow_color = Color(0, 0, 0, 0.36)
	ls.shadow_offset = Vector2(2, 3)
	return ls

