extends RefCounted

class_name MultiplayerComponents

# ==============================================================================
# DOOBYSCOO REUSABLE MULTIPLAYER UI COMPONENTS
# ==============================================================================


# 1. Procedural Dog Avatar Portrait Control
class DogAvatarPortrait extends Control:
	var avatar_id: String = "dog_default":
		set(val):
			avatar_id = val
			queue_redraw()
	var animate_bob: bool = true
	var _phase: float = 0.0

	func _init(p_avatar: String = "dog_default", p_size: float = 56.0, p_animate: bool = true) -> void:
		avatar_id = p_avatar
		animate_bob = p_animate
		custom_minimum_size = Vector2(p_size, p_size)
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		_phase = randf() * TAU

	func _process(delta: float) -> void:
		if animate_bob and is_visible_in_tree():
			_phase += delta * 3.8
			queue_redraw()

	func _draw() -> void:
		var r := minf(size.x, size.y) * 0.46
		MultiplayerTheme.draw_dog_avatar(self, size * 0.5, r, avatar_id, _phase if animate_bob else 0.0)


# 2. Procedural League Shield Badge Control
class LeagueBadgeControl extends Control:
	var league_name: String = "Beginner":
		set(val):
			league_name = val
			queue_redraw()
	var animate_pulse: bool = true
	var _phase: float = 0.0

	func _init(p_league: String = "Beginner", p_size: float = 52.0, p_animate: bool = true) -> void:
		league_name = p_league
		animate_pulse = p_animate
		custom_minimum_size = Vector2(p_size, p_size)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if animate_pulse and is_visible_in_tree():
			_phase += delta * 3.2
			queue_redraw()

	func _draw() -> void:
		var r := minf(size.x, size.y) * 0.43
		MultiplayerTheme.draw_league_shield(self, size * 0.5, r, league_name, _phase if animate_pulse else 0.0)


# 3. Procedural Trophy Icon Control
class TrophyIconControl extends Control:
	var trophy_color: Color = MultiplayerTheme.COL_GOLD:
		set(val):
			trophy_color = val
			queue_redraw()
	var icon_scale: float = 1.0

	func _init(p_size: float = 28.0, p_scale: float = 1.0, p_color: Color = MultiplayerTheme.COL_GOLD) -> void:
		custom_minimum_size = Vector2(p_size, p_size)
		icon_scale = p_scale
		trophy_color = p_color
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		MultiplayerTheme.draw_trophy_icon(self, size * 0.5, icon_scale, trophy_color)


# 4. Procedural Bone Icon Control
class BoneIconControl extends Control:
	var icon_scale: float = 1.0

	func _init(p_size: float = 26.0, p_scale: float = 1.0) -> void:
		custom_minimum_size = Vector2(p_size, p_size)
		icon_scale = p_scale
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		MultiplayerTheme.draw_bone_icon(self, size * 0.5, icon_scale)


# 4b. Procedural Battle Log Scroll Icon Control
class BattleScrollIconControl extends Control:
	var icon_scale: float = 1.0

	func _init(p_size: float = 48.0, p_scale: float = 1.35) -> void:
		custom_minimum_size = Vector2(p_size, p_size)
		icon_scale = p_scale
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		MultiplayerTheme.draw_battle_scroll_icon(self, size * 0.5, icon_scale)


# 5. Connection Status Dot Indicator
class ConnectionDotControl extends Control:
	var status_color: Color = Color(0.95, 0.72, 0.22):
		set(val):
			status_color = val
			queue_redraw()
	var pulse_active: bool = true
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(16, 16)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if pulse_active and is_visible_in_tree():
			_phase += delta * 4.5
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		if pulse_active:
			var glow_r := 5.0 + (sin(_phase) * 0.5 + 0.5) * 3.0
			draw_circle(c, glow_r, Color(status_color.r, status_color.g, status_color.b, 0.28))
		draw_circle(c, 4.8, status_color)
		draw_circle(c + Vector2(-1.2, -1.2), 1.4, Color(1, 1, 1, 0.75))


# 6. Animated Radar & Orbiting Particle Scanner for Matchmaking
class MatchmakingRadarControl extends Control:
	var _angle: float = 0.0
	var _pulse: float = 0.0
	var avatar_id: String = "dog_default"
	var league_name: String = "Beginner"

	func _init() -> void:
		custom_minimum_size = Vector2(200, 200)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_angle += delta * 2.4
			_pulse += delta * 3.5
			queue_redraw()

	func _draw() -> void:
		var center := size * 0.5
		var max_r := minf(size.x, size.y) * 0.46

		for i in range(3):
			var phase_frac := fmod(_pulse * 0.28 + float(i) * 0.33, 1.0)
			var r := lerpf(28.0, max_r, phase_frac)
			var alpha := (1.0 - phase_frac) * 0.55
			draw_arc(center, r, 0.0, TAU, 48, Color(0.98, 0.84, 0.32, alpha), 2.5)

		draw_arc(center, max_r, 0.0, TAU, 64, Color(0.95, 0.85, 0.55, 0.45), 2.0)
		draw_arc(center, max_r * 0.72, 0.0, TAU, 48, Color(0.55, 0.88, 0.62, 0.30), 1.5)
		draw_arc(center, max_r * 0.88, _angle, _angle + 1.15, 24, MultiplayerTheme.COL_GOLD, 4.0)
		draw_arc(center, max_r * 0.88, _angle + PI, _angle + PI + 1.15, 24, MultiplayerTheme.COL_GOLD, 4.0)

		var orbit_r := max_r * 0.78
		for idx in range(4):
			var a := _angle * 0.85 + float(idx) * (PI * 0.5)
			var p := center + Vector2(cos(a), sin(a)) * orbit_r
			draw_circle(p, 4.8, Color(1.0, 0.92, 0.52, 0.85))
			draw_circle(p, 2.3, Color.WHITE)

		MultiplayerTheme.draw_dog_avatar(self, center, 38.0, avatar_id, _pulse)


# 7. Competitive VS Badge Emblem for Opponent Found Screen
class VsEmblemControl extends Control:
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(106, 106)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_phase += delta * 5.0
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.42
		var pulse_r := r * (1.0 + sin(_phase) * 0.06)

		var spikes := 12
		var pts := PackedVector2Array()
		for i in range(spikes * 2):
			var ang := _phase * 0.25 + float(i) * PI / float(spikes)
			var rad := pulse_r * (1.18 if i % 2 == 0 else 0.86)
			pts.append(c + Vector2(cos(ang), sin(ang)) * rad)
		draw_colored_polygon(pts, MultiplayerTheme.COL_GOLD)

		draw_circle(c, r * 0.78, MultiplayerTheme.COL_BROWN_DARK)
		draw_circle(c, r * 0.70, Color(0.84, 0.22, 0.18))
		draw_arc(c, r * 0.70, 0, TAU, 32, MultiplayerTheme.COL_GOLD_BRIGHT, 3.0)


# 8. Celebratory Particle Banner for Victory / Defeat / Draw Results
class ResultBannerControl extends Control:
	var outcome: String = "victory":
		set(val):
			outcome = val
			queue_redraw()
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(120, 72)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_phase += delta * 3.6
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		if outcome == "victory":
			for i in range(8):
				var ang := _phase * 0.6 + float(i) * (TAU / 8.0)
				var dist := 34.0 + sin(_phase * 1.5 + float(i)) * 8.0
				var sp := c + Vector2(cos(ang) * dist * 1.4, sin(ang) * dist * 0.65)
				draw_circle(sp, 3.5, MultiplayerTheme.COL_GOLD_BRIGHT)
			MultiplayerTheme.draw_trophy_icon(self, c, 1.85, MultiplayerTheme.COL_GOLD)
		elif outcome == "defeat":
			MultiplayerTheme.draw_league_shield(self, c, 28.0, "Bronze", 0.0)
		else:
			MultiplayerTheme.draw_trophy_icon(self, c + Vector2(-22, 0), 1.35, Color(0.82, 0.86, 0.92))
			MultiplayerTheme.draw_trophy_icon(self, c + Vector2(22, 0), 1.35, Color(0.82, 0.86, 0.92))


# 9. Top 3 Leaderboard Medal Emblem
class RankMedalControl extends Control:
	var rank: int = 1:
		set(val):
			rank = val
			queue_redraw()

	func _init(p_rank: int = 1) -> void:
		rank = p_rank
		custom_minimum_size = Vector2(44, 40)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var c := size * 0.5
		if rank == 1:
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.86, 0.18, 0.20), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.86, 0.18, 0.20), 4.5)
			draw_circle(c + Vector2(0, -2), 13.5, Color(0.68, 0.46, 0.08))
			draw_circle(c + Vector2(0, -2), 11.5, Color(1.0, 0.86, 0.24))
			draw_circle(c + Vector2(-3, -5), 2.5, Color(1.0, 0.96, 0.72))
		elif rank == 2:
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.20, 0.48, 0.84), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.20, 0.48, 0.84), 4.5)
			draw_circle(c + Vector2(0, -2), 12.5, Color(0.45, 0.50, 0.56))
			draw_circle(c + Vector2(0, -2), 10.5, Color(0.86, 0.90, 0.95))
			draw_circle(c + Vector2(-3, -5), 2.2, Color.WHITE)
		elif rank == 3:
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.22, 0.62, 0.34), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.22, 0.62, 0.34), 4.5)
			draw_circle(c + Vector2(0, -2), 12.0, Color(0.50, 0.28, 0.12))
			draw_circle(c + Vector2(0, -2), 10.0, Color(0.86, 0.56, 0.30))
			draw_circle(c + Vector2(-3, -5), 2.0, Color(0.98, 0.78, 0.58))
		else:
			draw_circle(c, 12.0, Color(0.10, 0.16, 0.12, 0.85))
			draw_arc(c, 12.0, 0, TAU, 24, Color(0.45, 0.56, 0.48, 0.65), 1.5)


# ==============================================================================
# FACTORY METHODS FOR REUSABLE GAME CARDS & MENU BUTTONS
# ==============================================================================

static func create_nav_menu_card(
	title_text: String,
	subtitle_text: String,
	bg_color: Color,
	border_color: Color,
	icon_node: Control,
	on_pressed: Callable
) -> Dictionary:
	var btn := Button.new()
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.size_flags_vertical = Control.SIZE_EXPAND_FILL
	btn.custom_minimum_size = Vector2(0, 118)
	MultiplayerTheme.style_button(btn, bg_color, border_color, Color.WHITE, 18, 22, 6)
	btn.text = ""
	btn.pressed.connect(on_pressed)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.mouse_filter = Control.MOUSE_FILTER_IGNORE
	margin.add_theme_constant_override("margin_left", 22)
	margin.add_theme_constant_override("margin_right", 22)
	margin.add_theme_constant_override("margin_top", 14)
	margin.add_theme_constant_override("margin_bottom", 18)
	btn.add_child(margin)

	var hbox := HBoxContainer.new()
	hbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_theme_constant_override("separation", 18)
	margin.add_child(hbox)

	var icon_wrap := CenterContainer.new()
	icon_wrap.custom_minimum_size = Vector2(68, 68)
	icon_wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hbox.add_child(icon_wrap)
	if icon_node != null:
		icon_wrap.add_child(icon_node)

	var text_col := VBoxContainer.new()
	text_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	text_col.alignment = BoxContainer.ALIGNMENT_CENTER
	text_col.mouse_filter = Control.MOUSE_FILTER_IGNORE
	text_col.add_theme_constant_override("separation", 4)
	hbox.add_child(text_col)

	var title_lbl := Label.new()
	title_lbl.text = title_text
	title_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_TEXT_CREAM, 5)
	text_col.add_child(title_lbl)

	var sub_lbl := Label.new()
	sub_lbl.text = subtitle_text
	sub_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sub_lbl.add_theme_font_size_override("font_size", 15)
	sub_lbl.add_theme_color_override("font_color", Color(0.92, 0.96, 0.90, 0.92))
	text_col.add_child(sub_lbl)

	var arrow_lbl := Label.new()
	arrow_lbl.text = ">"
	arrow_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	arrow_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	arrow_lbl.label_settings = MultiplayerTheme.make_title_settings(26, border_color.lightened(0.2), 4)
	hbox.add_child(arrow_lbl)

	return {
		"button": btn,
		"title_label": title_lbl,
		"subtitle_label": sub_lbl,
		"icon_holder": icon_wrap
	}


static func create_stat_badge(title_text: String, value_text: String, accent_col: Color = MultiplayerTheme.COL_GOLD) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.09, 0.15, 0.11, 0.92), accent_col.darkened(0.22), 14, 2, 2, 2)
	)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 2)
	panel.add_child(vbox)

	var cap := Label.new()
	cap.text = title_text
	cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cap.add_theme_font_size_override("font_size", 12)
	cap.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	vbox.add_child(cap)

	var val := Label.new()
	val.name = "ValueLabel"
	val.text = value_text
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	val.add_theme_font_size_override("font_size", 20)
	val.add_theme_color_override("font_color", accent_col)
	vbox.add_child(val)

	return panel


static func create_versus_player_card(
	p_data: Dictionary,
	is_local_player: bool
) -> PanelContainer:
	var border_col := MultiplayerTheme.COL_GOLD if is_local_player else Color(0.92, 0.42, 0.36)
	var bg_col := Color(0.14, 0.24, 0.18, 0.98) if is_local_player else Color(0.23, 0.15, 0.16, 0.98)
	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(260, 240)
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 18, 3, 8, 5))

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 8)
	card.add_child(vbox)

	var tag_lbl := Label.new()
	tag_lbl.text = "YOU" if is_local_player else "CHALLENGER"
	tag_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tag_lbl.add_theme_font_size_override("font_size", 13)
	tag_lbl.add_theme_color_override("font_color", border_col.lightened(0.2))
	vbox.add_child(tag_lbl)

	var icon_row := HBoxContainer.new()
	icon_row.alignment = BoxContainer.ALIGNMENT_CENTER
	icon_row.add_theme_constant_override("separation", 12)
	vbox.add_child(icon_row)

	var avatar_id := str(p_data.get("avatar", "dog_default"))
	var league_name := str(p_data.get("league", "Beginner"))
	var trophies := int(p_data.get("trophies", 0))

	icon_row.add_child(DogAvatarPortrait.new(avatar_id, 66.0, true))
	icon_row.add_child(LeagueBadgeControl.new(league_name, 52.0, true))

	var dname := str(p_data.get("display_name", p_data.get("username", "Challenger")))
	var name_lbl := Label.new()
	name_lbl.text = dname
	name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_TEXT_CREAM, 5)
	vbox.add_child(name_lbl)

	var trophy_row := HBoxContainer.new()
	trophy_row.alignment = BoxContainer.ALIGNMENT_CENTER
	trophy_row.add_theme_constant_override("separation", 6)
	vbox.add_child(trophy_row)

	trophy_row.add_child(TrophyIconControl.new(22.0, 0.8))
	var tr_lbl := Label.new()
	tr_lbl.text = "%d  •  %s" % [trophies, league_name]
	tr_lbl.add_theme_font_size_override("font_size", 15)
	tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	trophy_row.add_child(tr_lbl)

	return card


static func create_leaderboard_row(entry: Dictionary, my_player_id: String, on_inspect: Callable = Callable()) -> PanelContainer:
	var pos := int(entry.get("position", 0))
	var pid := str(entry.get("player_id", ""))
	var is_me := (pid != "" and pid == my_player_id)

	var bg_col := Color(0.14, 0.22, 0.17, 0.94)
	var border_col := Color(0.40, 0.52, 0.42, 0.72)
	var border_w := 2

	if is_me:
		bg_col = Color(0.20, 0.36, 0.24, 0.98)
		border_col = MultiplayerTheme.COL_GOLD
		border_w = 3
	elif pos == 1:
		bg_col = Color(0.29, 0.24, 0.11, 0.96)
		border_col = Color(1.0, 0.86, 0.28, 1.0)
	elif pos == 2:
		bg_col = Color(0.20, 0.24, 0.27, 0.96)
		border_col = Color(0.82, 0.88, 0.95, 1.0)
	elif pos == 3:
		bg_col = Color(0.26, 0.18, 0.13, 0.96)
		border_col = Color(0.88, 0.58, 0.32, 1.0)

	var row_panel := PanelContainer.new()
	row_panel.custom_minimum_size = Vector2(0, 62)
	row_panel.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 14, border_w, 3, 2))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	row_panel.add_child(hbox)

	var rank_box := CenterContainer.new()
	rank_box.custom_minimum_size = Vector2(52, 42)
	hbox.add_child(rank_box)
	rank_box.add_child(RankMedalControl.new(pos))

	var rank_lbl := Label.new()
	rank_lbl.text = "#%d" % pos
	rank_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_lbl.add_theme_font_size_override("font_size", 15 if pos <= 3 else 14)
	rank_lbl.add_theme_color_override("font_color", Color(0.12, 0.10, 0.06) if pos <= 3 else MultiplayerTheme.COL_TEXT_CREAM)
	rank_box.add_child(rank_lbl)

	var avatar_id := str(entry.get("avatar", "dog_default"))
	hbox.add_child(DogAvatarPortrait.new(avatar_id, 44.0, false))

	var id_vbox := VBoxContainer.new()
	id_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	id_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	id_vbox.add_theme_constant_override("separation", 1)
	hbox.add_child(id_vbox)

	var dname := str(entry.get("display_name", entry.get("username", "Player")))
	var uname := str(entry.get("username", "player"))
	var league_name := str(entry.get("league", "Beginner"))

	var name_lbl := Label.new()
	name_lbl.text = dname + ("  (YOU)" if is_me else "")
	name_lbl.add_theme_font_size_override("font_size", 17)
	name_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT if is_me else MultiplayerTheme.COL_TEXT_CREAM)
	id_vbox.add_child(name_lbl)

	var wins := int(entry.get("wins", 0))
	var losses := int(entry.get("losses", 0))
	var win_pct := float(entry.get("win_rate", 0.0)) * 100.0
	var sub_lbl := Label.new()
	sub_lbl.text = "%s League  •  %dW - %dL (%.0f%%)" % [league_name, wins, losses, win_pct]
	sub_lbl.add_theme_font_size_override("font_size", 13)
	sub_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	id_vbox.add_child(sub_lbl)

	hbox.add_child(LeagueBadgeControl.new(league_name, 36.0, false))

	var trophy_pill := PanelContainer.new()
	trophy_pill.custom_minimum_size = Vector2(108, 36)
	trophy_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.14, 0.10, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 18)
	)
	hbox.add_child(trophy_pill)

	var tr_hbox := HBoxContainer.new()
	tr_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	tr_hbox.add_theme_constant_override("separation", 6)
	trophy_pill.add_child(tr_hbox)

	tr_hbox.add_child(TrophyIconControl.new(18.0, 0.68))
	var tr_val := Label.new()
	tr_val.text = str(int(entry.get("trophies", 0)))
	tr_val.add_theme_font_size_override("font_size", 17)
	tr_val.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	tr_hbox.add_child(tr_val)

	if on_inspect.is_valid() and uname != "":
		var view_btn := Button.new()
		view_btn.text = "Profile"
		view_btn.custom_minimum_size = Vector2(76, 34)
		MultiplayerTheme.style_subtle_button(view_btn, 13)
		view_btn.pressed.connect(func(): on_inspect.call(uname))
		hbox.add_child(view_btn)

	return row_panel


static func create_battle_history_card(
	match_data: Dictionary,
	my_player_id: String,
	trophy_delta_map: Dictionary,
	on_details_pressed: Callable
) -> PanelContainer:
	var mid := str(match_data.get("match_id", ""))
	var st := str(match_data.get("status", "COMPLETED"))
	var winner_id := str(match_data.get("winner_id", "")) if match_data.get("winner_id") != null else ""
	var is_draw := bool(match_data.get("is_draw", false))

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}
	var me: Dictionary = p1 if str(p1.get("player_id", "")) == my_player_id else p2
	var opp: Dictionary = p2 if str(p1.get("player_id", "")) == my_player_id else p1

	var my_sub: Dictionary = me.get("submission", {}) if (me.get("submission") is Dictionary) else {}
	var opp_sub: Dictionary = opp.get("submission", {}) if (opp.get("submission") is Dictionary) else {}

	var outcome_title := "ACTIVE"
	var accent_col := Color(0.55, 0.80, 0.96)
	var bg_col := Color(0.13, 0.20, 0.23, 0.95)

	if st == "COMPLETED":
		if is_draw or winner_id == "":
			outcome_title = "DRAW"
			accent_col = MultiplayerTheme.COL_DRAW
			bg_col = MultiplayerTheme.COL_DRAW_BG
		elif winner_id == my_player_id:
			outcome_title = "VICTORY"
			accent_col = MultiplayerTheme.COL_VICTORY
			bg_col = MultiplayerTheme.COL_VICTORY_BG
		else:
			outcome_title = "DEFEAT"
			accent_col = MultiplayerTheme.COL_DEFEAT
			bg_col = MultiplayerTheme.COL_DEFEAT_BG
	elif st == "EXPIRED":
		outcome_title = "EXPIRED"
		accent_col = Color(0.62, 0.65, 0.62)
		bg_col = Color(0.18, 0.20, 0.18, 0.94)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(0, 72)
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, accent_col, 16, 2, 4, 3))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 14)
	card.add_child(hbox)

	var badge_panel := PanelContainer.new()
	badge_panel.custom_minimum_size = Vector2(102, 42)
	badge_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(accent_col.darkened(0.45), accent_col, 14)
	)
	hbox.add_child(badge_panel)

	var badge_lbl := Label.new()
	badge_lbl.text = outcome_title
	badge_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	badge_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	badge_lbl.add_theme_font_size_override("font_size", 15)
	badge_lbl.add_theme_color_override("font_color", accent_col.lightened(0.35))
	badge_panel.add_child(badge_lbl)

	var opp_avatar := str(opp.get("avatar", "dog_default"))
	hbox.add_child(DogAvatarPortrait.new(opp_avatar, 44.0, false))

	var info_vbox := VBoxContainer.new()
	info_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	info_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(info_vbox)

	var opp_name := str(opp.get("display_name", opp.get("username", "Opponent")))
	var vs_lbl := Label.new()
	vs_lbl.text = "vs %s" % opp_name
	vs_lbl.add_theme_font_size_override("font_size", 18)
	vs_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	info_vbox.add_child(vs_lbl)

	var my_sc := str(my_sub.get("verified_score", "-")) if !my_sub.is_empty() else "-"
	var opp_sc := str(opp_sub.get("verified_score", "-")) if !opp_sub.is_empty() else "-"
	var sc_lbl := Label.new()
	sc_lbl.text = "Score: %s  vs  %s" % [my_sc, opp_sc]
	sc_lbl.add_theme_font_size_override("font_size", 14)
	sc_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	info_vbox.add_child(sc_lbl)

	var tr_change = my_sub.get("trophy_change", null)
	if tr_change == null and trophy_delta_map.has(mid):
		tr_change = trophy_delta_map[mid]

	var tr_panel := PanelContainer.new()
	tr_panel.custom_minimum_size = Vector2(88, 36)
	tr_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.92), MultiplayerTheme.COL_GOLD_BORDER, 16)
	)
	hbox.add_child(tr_panel)

	var tr_hbox := HBoxContainer.new()
	tr_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	tr_hbox.add_theme_constant_override("separation", 4)
	tr_panel.add_child(tr_hbox)

	tr_hbox.add_child(TrophyIconControl.new(18.0, 0.65))
	var tr_lbl := Label.new()
	if tr_change != null:
		var chg := int(tr_change)
		tr_lbl.text = ("+%d" % chg) if chg >= 0 else str(chg)
		tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_VICTORY if chg > 0 else (MultiplayerTheme.COL_DEFEAT if chg < 0 else MultiplayerTheme.COL_GOLD))
	else:
		tr_lbl.text = "--"
		tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	tr_lbl.add_theme_font_size_override("font_size", 16)
	tr_hbox.add_child(tr_lbl)

	var inspect_btn := Button.new()
	inspect_btn.text = "Details"
	inspect_btn.custom_minimum_size = Vector2(80, 36)
	MultiplayerTheme.style_subtle_button(inspect_btn, 14)
	inspect_btn.pressed.connect(func(): on_details_pressed.call(match_data))
	hbox.add_child(inspect_btn)

	return card


static func create_empty_state_card(title_text: String, subtitle_text: String, icon_type: String = "trophy") -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	panel.custom_minimum_size = Vector2(0, 180)
	panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.10, 0.17, 0.13, 0.88), Color(0.45, 0.58, 0.48, 0.65), 16, 2, 2, 2)
	)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 10)
	panel.add_child(vbox)

	var icon_holder := CenterContainer.new()
	vbox.add_child(icon_holder)
	if icon_type == "dog":
		icon_holder.add_child(DogAvatarPortrait.new("dog_default", 62.0, true))
	elif icon_type == "shield":
		icon_holder.add_child(LeagueBadgeControl.new("Gold", 56.0, true))
	else:
		icon_holder.add_child(TrophyIconControl.new(52.0, 1.65))

	var t_lbl := Label.new()
	t_lbl.text = title_text
	t_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_TEXT_CREAM, 4)
	vbox.add_child(t_lbl)

	var s_lbl := Label.new()
	s_lbl.text = subtitle_text
	s_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	s_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	s_lbl.add_theme_font_size_override("font_size", 15)
	s_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	vbox.add_child(s_lbl)

	return panel
