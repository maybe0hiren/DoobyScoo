extends RefCounted

class_name MultiplayerTheme

# ==============================================================================
# DOOBYSCOO MULTIPLAYER THEME & PROCEDURAL ART LIBRARY
# Cohesive with DoobyScoo's bright meadow green, warm parchment cream,
# golden amber, and signature lavender rounded game UI identity.
# ==============================================================================

const COL_BG_DARK := Color(0.10, 0.17, 0.13, 0.94)
const COL_PANEL_GREEN := Color(0.13, 0.22, 0.16, 0.94)
const COL_PANEL_DEEP := Color(0.09, 0.16, 0.12, 0.95)
const COL_CARD_DARK := Color(0.16, 0.26, 0.19, 0.96)
const COL_CARD_LIGHT := Color(0.97, 0.95, 0.87, 0.97)
const COL_CARD_CREAM_ALT := Color(0.93, 0.90, 0.80, 0.96)

const COL_GOLD := Color(0.96, 0.74, 0.18, 1.0)
const COL_GOLD_BRIGHT := Color(1.0, 0.93, 0.56, 1.0)
const COL_GOLD_BORDER := Color(0.96, 0.84, 0.46, 1.0)
const COL_GOLD_DARK := Color(0.68, 0.48, 0.14, 1.0)
const COL_BROWN_DARK := Color(0.24, 0.14, 0.06, 1.0)

const COL_LAVENDER := Color(0.56, 0.55, 0.78, 1.0)
const COL_LAVENDER_HOVER := Color(0.65, 0.64, 0.86, 1.0)
const COL_LAVENDER_DARK := Color(0.38, 0.37, 0.54, 1.0)

const COL_VICTORY := Color(0.24, 0.84, 0.40, 1.0)
const COL_VICTORY_BG := Color(0.13, 0.31, 0.19, 0.96)
const COL_DEFEAT := Color(0.92, 0.32, 0.30, 1.0)
const COL_DEFEAT_BG := Color(0.31, 0.14, 0.15, 0.96)
const COL_DRAW := Color(0.96, 0.76, 0.22, 1.0)
const COL_DRAW_BG := Color(0.29, 0.24, 0.12, 0.96)

const COL_TEXT_CREAM := Color(1.0, 0.96, 0.84, 1.0)
const COL_TEXT_LIGHT := Color(0.94, 0.97, 0.94, 1.0)
const COL_TEXT_MUTED := Color(0.75, 0.84, 0.77, 1.0)
const COL_TEXT_DARK := Color(0.14, 0.20, 0.13, 1.0)

const LEAGUE_TIERS := [
	{"name": "Beginner", "min": 0, "max": 499, "primary": Color(0.55, 0.78, 0.45), "secondary": Color(0.32, 0.52, 0.24), "rim": Color(0.78, 0.94, 0.68)},
	{"name": "Bronze", "min": 500, "max": 999, "primary": Color(0.82, 0.52, 0.28), "secondary": Color(0.52, 0.30, 0.14), "rim": Color(0.96, 0.74, 0.52)},
	{"name": "Silver", "min": 1000, "max": 1499, "primary": Color(0.78, 0.83, 0.88), "secondary": Color(0.48, 0.54, 0.60), "rim": Color(0.95, 0.98, 1.0)},
	{"name": "Gold", "min": 1500, "max": 1999, "primary": Color(0.98, 0.80, 0.22), "secondary": Color(0.68, 0.48, 0.08), "rim": Color(1.0, 0.94, 0.60)},
	{"name": "Platinum", "min": 2000, "max": 2499, "primary": Color(0.28, 0.84, 0.86), "secondary": Color(0.14, 0.50, 0.56), "rim": Color(0.72, 0.98, 1.0)},
	{"name": "Diamond", "min": 2500, "max": 2999, "primary": Color(0.48, 0.68, 0.98), "secondary": Color(0.24, 0.36, 0.74), "rim": Color(0.82, 0.90, 1.0)},
	{"name": "Master", "min": 3000, "max": 999999, "primary": Color(0.76, 0.34, 0.94), "secondary": Color(0.42, 0.14, 0.62), "rim": Color(0.98, 0.84, 0.35)},
]


static func get_league_info(league_name: String, trophies: int = 0) -> Dictionary:
	for idx in range(LEAGUE_TIERS.size()):
		var tier: Dictionary = LEAGUE_TIERS[idx]
		if str(tier["name"]).to_lower() == league_name.to_lower():
			var next_tier: Dictionary = LEAGUE_TIERS[min(idx + 1, LEAGUE_TIERS.size() - 1)]
			var is_max: bool = (idx == LEAGUE_TIERS.size() - 1)
			var span: float = max(1.0, float(int(tier["max"]) - int(tier["min"]) + 1))
			var progress: float = 1.0 if is_max else clampf(float(trophies - int(tier["min"])) / span, 0.0, 1.0)
			return {
				"index": idx,
				"name": tier["name"],
				"min": tier["min"],
				"max": tier["max"],
				"primary": tier["primary"],
				"secondary": tier["secondary"],
				"rim": tier["rim"],
				"next_name": "Max Tier" if is_max else str(next_tier["name"]),
				"next_min": int(tier["min"]) if is_max else int(next_tier["min"]),
				"progress": progress,
				"is_max": is_max
			}
	return get_league_info("Beginner", trophies)


static func make_panel_style(
	bg: Color = COL_PANEL_GREEN,
	border: Color = COL_GOLD_BORDER,
	radius: int = 18,
	border_width: int = 3,
	shadow: int = 6,
	bottom_bevel: int = 4
) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.border_color = border
	s.border_width_left = border_width
	s.border_width_top = border_width
	s.border_width_right = border_width
	s.border_width_bottom = border_width + bottom_bevel
	s.corner_radius_top_left = radius
	s.corner_radius_top_right = radius
	s.corner_radius_bottom_left = radius
	s.corner_radius_bottom_right = radius
	s.shadow_size = shadow
	s.shadow_color = Color(0, 0, 0, 0.30)
	s.shadow_offset = Vector2(0, 4)
	s.content_margin_left = 16
	s.content_margin_right = 16
	s.content_margin_top = 14
	s.content_margin_bottom = 14
	return s


static func make_card_style(
	bg: Color = COL_CARD_DARK,
	border: Color = COL_GOLD_BORDER,
	radius: int = 16,
	border_width: int = 2
) -> StyleBoxFlat:
	return make_panel_style(bg, border, radius, border_width, 4, 3)


static func make_pill_style(bg: Color, border: Color = Color(1, 1, 1, 0.24), radius: int = 20) -> StyleBoxFlat:
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
	radius: int = 22,
	bevel: int = 5
) -> void:
	DoobyUI.style_button(btn, base_color, border_color, font_color, font_size, radius, bevel)


static func style_primary_battle_button(btn: Button, font_size: int = 26) -> void:
	DoobyUI.style_gold_button(btn, font_size, 32)


static func style_lavender_button(btn: Button, font_size: int = 18) -> void:
	DoobyUI.style_lavender_button(btn, font_size, 22)


static func style_green_button(btn: Button, font_size: int = 18) -> void:
	DoobyUI.style_green_button(btn, font_size, 22)


static func style_danger_button(btn: Button, font_size: int = 18) -> void:
	DoobyUI.style_danger_button(btn, font_size, 20)


static func style_subtle_button(btn: Button, font_size: int = 16) -> void:
	DoobyUI.style_subtle_button(btn, font_size, 18)


static func style_line_edit(input: LineEdit, font_size: int = 16) -> void:
	input.add_theme_font_size_override("font_size", font_size)
	input.add_theme_color_override("font_color", COL_TEXT_CREAM)
	input.add_theme_color_override("font_placeholder_color", Color(0.64, 0.72, 0.66, 0.78))
	var normal := StyleBoxFlat.new()
	normal.bg_color = Color(0.08, 0.13, 0.10, 0.94)
	normal.border_color = Color(0.45, 0.58, 0.48, 0.85)
	normal.border_width_left = 2
	normal.border_width_top = 2
	normal.border_width_right = 2
	normal.border_width_bottom = 2
	normal.corner_radius_top_left = 12
	normal.corner_radius_top_right = 12
	normal.corner_radius_bottom_left = 12
	normal.corner_radius_bottom_right = 12
	normal.content_margin_left = 12
	normal.content_margin_right = 12
	normal.content_margin_top = 7
	normal.content_margin_bottom = 7

	var focus: StyleBoxFlat = normal.duplicate() as StyleBoxFlat
	focus.border_color = COL_GOLD
	focus.bg_color = Color(0.11, 0.17, 0.13, 0.98)

	input.add_theme_stylebox_override("normal", normal)
	input.add_theme_stylebox_override("focus", focus)


static func style_progress_bar(bar: ProgressBar, fill_color: Color = COL_GOLD, bg_color: Color = Color(0.07, 0.12, 0.09, 0.95)) -> void:
	var bg := StyleBoxFlat.new()
	bg.bg_color = bg_color
	bg.border_color = Color(0.42, 0.54, 0.45, 0.75)
	bg.border_width_left = 2
	bg.border_width_top = 2
	bg.border_width_right = 2
	bg.border_width_bottom = 2
	bg.corner_radius_top_left = 10
	bg.corner_radius_top_right = 10
	bg.corner_radius_bottom_left = 10
	bg.corner_radius_bottom_right = 10

	var fill := StyleBoxFlat.new()
	fill.bg_color = fill_color
	fill.border_color = fill_color.lightened(0.28)
	fill.border_width_top = 2
	fill.corner_radius_top_left = 8
	fill.corner_radius_top_right = 8
	fill.corner_radius_bottom_left = 8
	fill.corner_radius_bottom_right = 8

	bar.add_theme_stylebox_override("background", bg)
	bar.add_theme_stylebox_override("fill", fill)


static func make_title_settings(size: int = 28, color: Color = COL_TEXT_CREAM, outline: int = 6) -> LabelSettings:
	return DoobyUI.make_heading_settings(size, color, outline)


# ==============================================================================
# PROCEDURAL VECTOR DRAWING HELPERS (Badges, Trophies, Avatars, Medals, Scroll)
# ==============================================================================

static func draw_trophy_icon(canvas: CanvasItem, center: Vector2, scale_f: float = 1.0, gold_col: Color = COL_GOLD) -> void:
	var rim_col := gold_col.lightened(0.25)
	var dark_col := gold_col.darkened(0.35)
	canvas.draw_arc(center + Vector2(-9, -4) * scale_f, 5.5 * scale_f, deg_to_rad(90), deg_to_rad(270), 12, dark_col, 2.6 * scale_f)
	canvas.draw_arc(center + Vector2(9, -4) * scale_f, 5.5 * scale_f, deg_to_rad(-90), deg_to_rad(90), 12, dark_col, 2.6 * scale_f)
	var cup_pts := PackedVector2Array([
		center + Vector2(-10, -11) * scale_f,
		center + Vector2(10, -11) * scale_f,
		center + Vector2(7, 1) * scale_f,
		center + Vector2(-7, 1) * scale_f,
	])
	canvas.draw_colored_polygon(cup_pts, gold_col)
	canvas.draw_circle(center + Vector2(0, 0) * scale_f, 7.0 * scale_f, gold_col)
	canvas.draw_line(center + Vector2(-10, -10) * scale_f, center + Vector2(10, -10) * scale_f, rim_col, 2.5 * scale_f)
	canvas.draw_rect(Rect2(center + Vector2(-2.5, 5) * scale_f, Vector2(5, 6) * scale_f), dark_col, true)
	canvas.draw_rect(Rect2(center + Vector2(-7.5, 10) * scale_f, Vector2(15, 4) * scale_f), gold_col, true)
	canvas.draw_rect(Rect2(center + Vector2(-9.5, 13) * scale_f, Vector2(19, 3) * scale_f), COL_BROWN_DARK, true)
	canvas.draw_circle(center + Vector2(-4, -5) * scale_f, 2.0 * scale_f, rim_col)


static func draw_bone_icon(canvas: CanvasItem, center: Vector2, scale_f: float = 1.0) -> void:
	var bone_col := Color(0.99, 0.95, 0.78)
	var outline_col := Color(0.68, 0.48, 0.16)
	for offset in [Vector2(-7, -4), Vector2(-7, 4), Vector2(7, -4), Vector2(7, 4)]:
		canvas.draw_circle(center + offset * scale_f, 4.4 * scale_f, outline_col)
	canvas.draw_line(center + Vector2(-7, 0) * scale_f, center + Vector2(7, 0) * scale_f, outline_col, 7.0 * scale_f)
	for offset in [Vector2(-7, -4), Vector2(-7, 4), Vector2(7, -4), Vector2(7, 4)]:
		canvas.draw_circle(center + offset * scale_f, 3.1 * scale_f, bone_col)
	canvas.draw_line(center + Vector2(-7, 0) * scale_f, center + Vector2(7, 0) * scale_f, bone_col, 4.8 * scale_f)


static func draw_battle_scroll_icon(canvas: CanvasItem, center: Vector2, scale_f: float = 1.0) -> void:
	var parchment := Color(0.97, 0.93, 0.80)
	var trim := Color(0.70, 0.48, 0.20)
	var ink := Color(0.32, 0.22, 0.12)
	var w := 22.0 * scale_f
	var h := 26.0 * scale_f
	canvas.draw_rect(Rect2(center - Vector2(w * 0.5, h * 0.5), Vector2(w, h)), parchment, true)
	canvas.draw_rect(Rect2(center - Vector2(w * 0.5, h * 0.5), Vector2(w, h)), trim, false, 2.2 * scale_f)
	canvas.draw_rect(Rect2(center + Vector2(-w * 0.62, -h * 0.55), Vector2(w * 1.24, 5.0 * scale_f)), trim, true)
	canvas.draw_rect(Rect2(center + Vector2(-w * 0.62, h * 0.36), Vector2(w * 1.24, 5.0 * scale_f)), trim, true)
	for row_y in [-5.5, 0.0, 5.5]:
		canvas.draw_line(
			center + Vector2(-w * 0.28, row_y * scale_f),
			center + Vector2(w * 0.28, row_y * scale_f),
			ink,
			2.0 * scale_f
		)


static func draw_league_shield(canvas: CanvasItem, center: Vector2, radius: float, league_name: String, pulse: float = 0.0) -> void:
	var info := get_league_info(league_name)
	var primary: Color = info["primary"]
	var secondary: Color = info["secondary"]
	var rim: Color = info["rim"]
	var r := radius * (1.0 + sin(pulse) * 0.025)

	var shadow_pts := PackedVector2Array([
		center + Vector2(0, -r) + Vector2(0, 3),
		center + Vector2(r * 0.88, -r * 0.45) + Vector2(0, 3),
		center + Vector2(r * 0.72, r * 0.42) + Vector2(0, 3),
		center + Vector2(0, r * 1.05) + Vector2(0, 3),
		center + Vector2(-r * 0.72, r * 0.42) + Vector2(0, 3),
		center + Vector2(-r * 0.88, -r * 0.45) + Vector2(0, 3),
	])
	canvas.draw_colored_polygon(shadow_pts, Color(0, 0, 0, 0.30))

	var outer_pts := PackedVector2Array([
		center + Vector2(0, -r),
		center + Vector2(r * 0.88, -r * 0.45),
		center + Vector2(r * 0.72, r * 0.42),
		center + Vector2(0, r * 1.05),
		center + Vector2(-r * 0.72, r * 0.42),
		center + Vector2(-r * 0.88, -r * 0.45),
	])
	canvas.draw_colored_polygon(outer_pts, rim)

	var ir := r * 0.82
	var inner_pts := PackedVector2Array([
		center + Vector2(0, -ir),
		center + Vector2(ir * 0.88, -ir * 0.45),
		center + Vector2(ir * 0.72, ir * 0.42),
		center + Vector2(0, ir * 1.05),
		center + Vector2(-ir * 0.72, ir * 0.42),
		center + Vector2(-ir * 0.88, -ir * 0.45),
	])
	canvas.draw_colored_polygon(inner_pts, secondary)

	var left_pts := PackedVector2Array([
		center + Vector2(0, -ir),
		center + Vector2(0, ir * 1.05),
		center + Vector2(-ir * 0.72, ir * 0.42),
		center + Vector2(-ir * 0.88, -ir * 0.45),
	])
	canvas.draw_colored_polygon(left_pts, primary)

	var tier_idx: int = int(info["index"])
	if tier_idx >= 4:
		var gem_pts := PackedVector2Array([
			center + Vector2(0, -r * 0.42),
			center + Vector2(r * 0.32, 0),
			center + Vector2(0, r * 0.42),
			center + Vector2(-r * 0.32, 0),
		])
		canvas.draw_colored_polygon(gem_pts, rim)
		canvas.draw_circle(center, r * 0.14, Color.WHITE)
	else:
		var paw_col := rim.lightened(0.18)
		canvas.draw_circle(center + Vector2(0, r * 0.12), r * 0.22, paw_col)
		canvas.draw_circle(center + Vector2(-r * 0.22, -r * 0.14), r * 0.10, paw_col)
		canvas.draw_circle(center + Vector2(-r * 0.07, -r * 0.24), r * 0.10, paw_col)
		canvas.draw_circle(center + Vector2(r * 0.07, -r * 0.24), r * 0.10, paw_col)
		canvas.draw_circle(center + Vector2(r * 0.22, -r * 0.14), r * 0.10, paw_col)


static func draw_dog_avatar(canvas: CanvasItem, center: Vector2, radius: float, avatar_id: String = "dog_default", bob_phase: float = 0.0) -> void:
	var coat_col := Color(0.82, 0.52, 0.24)
	var ear_col := Color(0.45, 0.25, 0.09)
	var snout_col := Color(0.93, 0.74, 0.52)
	var collar_col := Color(0.12, 0.72, 0.86)
	var bg_col := Color(0.18, 0.32, 0.22)
	var rim_col := COL_GOLD_BORDER

	match avatar_id:
		"dog_golden":
			coat_col = Color(0.95, 0.76, 0.32)
			ear_col = Color(0.72, 0.50, 0.14)
			snout_col = Color(0.99, 0.90, 0.68)
			collar_col = Color(0.88, 0.20, 0.24)
			bg_col = Color(0.26, 0.22, 0.12)
		"dog_husky":
			coat_col = Color(0.74, 0.80, 0.88)
			ear_col = Color(0.28, 0.34, 0.42)
			snout_col = Color(0.95, 0.97, 1.0)
			collar_col = Color(0.92, 0.52, 0.16)
			bg_col = Color(0.14, 0.24, 0.34)
		"dog_cyber":
			coat_col = Color(0.44, 0.36, 0.74)
			ear_col = Color(0.22, 0.16, 0.44)
			snout_col = Color(0.72, 0.86, 0.98)
			collar_col = Color(0.20, 0.98, 0.72)
			bg_col = Color(0.14, 0.12, 0.26)
			rim_col = Color(0.32, 0.95, 0.88)

	canvas.draw_circle(center + Vector2(0, 2), radius, Color(0, 0, 0, 0.32))
	canvas.draw_circle(center, radius, rim_col)
	canvas.draw_circle(center, radius * 0.90, bg_col)

	var s := radius / 26.0
	var bob_y := sin(bob_phase) * 1.4 * s
	var c := center + Vector2(0, bob_y + 2.0 * s)

	canvas.draw_circle(c + Vector2(0, 11 * s), 11 * s, coat_col.darkened(0.08))
	canvas.draw_line(c + Vector2(-9 * s, 6 * s), c + Vector2(9 * s, 6 * s), collar_col, 3.8 * s)
	canvas.draw_circle(c + Vector2(0, 8.5 * s), 3.2 * s, COL_GOLD)

	canvas.draw_circle(c + Vector2(-12 * s, -4 * s), 6.8 * s, ear_col)
	canvas.draw_circle(c + Vector2(12 * s, -4 * s), 6.8 * s, ear_col)
	canvas.draw_circle(c + Vector2(0, -4 * s), 12.0 * s, coat_col)
	canvas.draw_circle(c + Vector2(0, -1 * s), 6.2 * s, snout_col)
	canvas.draw_circle(c + Vector2(0, -3.2 * s), 2.8 * s, Color(0.15, 0.12, 0.10))

	if avatar_id == "dog_cyber":
		canvas.draw_rect(Rect2(c + Vector2(-8 * s, -9.5 * s), Vector2(16 * s, 4.2 * s)), Color(0.18, 0.96, 0.88), true)
		canvas.draw_line(c + Vector2(-6 * s, -7.5 * s), c + Vector2(6 * s, -7.5 * s), Color.WHITE, 1.5 * s)
	else:
		canvas.draw_circle(c + Vector2(-4.2 * s, -7.2 * s), 2.9 * s, Color.WHITE)
		canvas.draw_circle(c + Vector2(4.2 * s, -7.2 * s), 2.9 * s, Color.WHITE)
		canvas.draw_circle(c + Vector2(-4.0 * s, -7.2 * s), 1.6 * s, Color.BLACK)
		canvas.draw_circle(c + Vector2(4.0 * s, -7.2 * s), 1.6 * s, Color.BLACK)
		canvas.draw_circle(c + Vector2(-4.5 * s, -7.8 * s), 0.7 * s, Color.WHITE)
		canvas.draw_circle(c + Vector2(3.5 * s, -7.8 * s), 0.7 * s, Color.WHITE)
