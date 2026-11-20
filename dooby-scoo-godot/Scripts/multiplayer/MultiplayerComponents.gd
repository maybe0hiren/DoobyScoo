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


# 5. Connection Status Dot Indicator
class ConnectionDotControl extends Control:
	var status_color: Color = Color(0.95, 0.72, 0.22):
		set(val):
			status_color = val
			queue_redraw()
	var pulse_active: bool = true
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(18, 18)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if pulse_active and is_visible_in_tree():
			_phase += delta * 4.5
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		if pulse_active:
			var glow_r := 5.5 + (sin(_phase) * 0.5 + 0.5) * 3.5
			draw_circle(c, glow_r, Color(status_color.r, status_color.g, status_color.b, 0.28))
		draw_circle(c, 5.2, status_color)
		draw_circle(c + Vector2(-1.4, -1.4), 1.6, Color(1, 1, 1, 0.75))


# 6. Animated Radar & Orbiting Particle Scanner for Matchmaking Screen
class MatchmakingRadarControl extends Control:
	var _angle: float = 0.0
	var _pulse: float = 0.0
	var avatar_id: String = "dog_default"
	var league_name: String = "Beginner"

	func _init() -> void:
		custom_minimum_size = Vector2(210, 210)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_angle += delta * 2.4
			_pulse += delta * 3.5
			queue_redraw()

	func _draw() -> void:
		var center := size * 0.5
		var max_r := minf(size.x, size.y) * 0.46

		# Pulsating concentric sonar rings
		for i in range(3):
			var phase_frac := fmod(_pulse * 0.28 + float(i) * 0.33, 1.0)
			var r := lerpf(28.0, max_r, phase_frac)
			var alpha := (1.0 - phase_frac) * 0.55
			draw_arc(center, r, 0.0, TAU, 48, Color(0.98, 0.84, 0.32, alpha), 2.5)

		# Fixed outer tactical ring
		draw_arc(center, max_r, 0.0, TAU, 64, Color(0.95, 0.85, 0.55, 0.45), 2.0)
		draw_arc(center, max_r * 0.72, 0.0, TAU, 48, Color(0.55, 0.88, 0.62, 0.30), 1.5)

		# Rotating radar sweep arcs
		draw_arc(center, max_r * 0.88, _angle, _angle + 1.15, 24, MultiplayerTheme.COL_GOLD, 4.0)
		draw_arc(center, max_r * 0.88, _angle + PI, _angle + PI + 1.15, 24, MultiplayerTheme.COL_GOLD, 4.0)

		# Orbiting bone & trophy particles
		var orbit_r := max_r * 0.78
		for idx in range(4):
			var a := _angle * 0.85 + float(idx) * (PI * 0.5)
			var p := center + Vector2(cos(a), sin(a)) * orbit_r
			draw_circle(p, 5.0, Color(1.0, 0.92, 0.52, 0.85))
			draw_circle(p, 2.5, Color.WHITE)

		# Center Dog Avatar Portrait
		MultiplayerTheme.draw_dog_avatar(self, center, 40.0, avatar_id, _pulse)


# 7. Competitive VS Badge Emblem for Opponent Found Screen
class VsEmblemControl extends Control:
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(110, 110)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_phase += delta * 5.0
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		var r := minf(size.x, size.y) * 0.42
		var pulse_r := r * (1.0 + sin(_phase) * 0.06)

		# Outer sunburst spikes
		var spikes := 12
		var pts := PackedVector2Array()
		for i in range(spikes * 2):
			var ang := _phase * 0.25 + float(i) * PI / float(spikes)
			var rad := pulse_r * (1.18 if i % 2 == 0 else 0.86)
			pts.append(c + Vector2(cos(ang), sin(ang)) * rad)
		draw_colored_polygon(pts, MultiplayerTheme.COL_GOLD)

		# Inner crimson/brown competitive shield circle
		draw_circle(c, r * 0.78, MultiplayerTheme.COL_BROWN_DARK)
		draw_circle(c, r * 0.70, Color(0.84, 0.22, 0.18))
		draw_arc(c, r * 0.70, 0, TAU, 32, MultiplayerTheme.COL_GOLD_BRIGHT, 3.0)


# 8. Celebratory Particle Banner for Victory / Defeat / Draw Results
class ResultBannerControl extends Control:
	var outcome: String = "victory": # "victory", "defeat", "draw"
		set(val):
			outcome = val
			queue_redraw()
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(120, 74)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_phase += delta * 3.6
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		if outcome == "victory":
			# Floating golden stars & central trophy
			for i in range(8):
				var ang := _phase * 0.6 + float(i) * (TAU / 8.0)
				var dist := 34.0 + sin(_phase * 1.5 + float(i)) * 8.0
				var sp := c + Vector2(cos(ang) * dist * 1.4, sin(ang) * dist * 0.65)
				draw_circle(sp, 3.5, MultiplayerTheme.COL_GOLD_BRIGHT)
			MultiplayerTheme.draw_trophy_icon(self, c, 1.85, MultiplayerTheme.COL_GOLD)
		elif outcome == "defeat":
			# Crossed bones & shield
			MultiplayerTheme.draw_league_shield(self, c, 28.0, "Bronze", 0.0)
		else:
			# Draw: balanced twin trophies
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
			# Gold Medal with ribbons
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.86, 0.18, 0.20), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.86, 0.18, 0.20), 4.5)
			draw_circle(c + Vector2(0, -2), 13.5, Color(0.68, 0.46, 0.08))
			draw_circle(c + Vector2(0, -2), 11.5, Color(1.0, 0.86, 0.24))
			draw_circle(c + Vector2(-3, -5), 2.5, Color(1.0, 0.96, 0.72))
		elif rank == 2:
			# Silver Medal
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.20, 0.48, 0.84), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.20, 0.48, 0.84), 4.5)
			draw_circle(c + Vector2(0, -2), 12.5, Color(0.45, 0.50, 0.56))
			draw_circle(c + Vector2(0, -2), 10.5, Color(0.86, 0.90, 0.95))
			draw_circle(c + Vector2(-3, -5), 2.2, Color.WHITE)
		elif rank == 3:
			# Bronze Medal
			draw_line(c + Vector2(-5, 4), c + Vector2(-9, 16), Color(0.22, 0.62, 0.34), 4.5)
			draw_line(c + Vector2(5, 4), c + Vector2(9, 16), Color(0.22, 0.62, 0.34), 4.5)
			draw_circle(c + Vector2(0, -2), 12.0, Color(0.50, 0.28, 0.12))
			draw_circle(c + Vector2(0, -2), 10.0, Color(0.86, 0.56, 0.30))
			draw_circle(c + Vector2(-3, -5), 2.0, Color(0.98, 0.78, 0.58))
		else:
			draw_circle(c, 12.0, Color(0.10, 0.16, 0.12, 0.85))
			draw_arc(c, 12.0, 0, TAU, 24, Color(0.45, 0.56, 0.48, 0.65), 1.5)


# ==============================================================================
# FACTORY METHODS FOR REUSABLE GAME CARDS & ROWS
# ==============================================================================

static func create_stat_badge(title_text: String, value_text: String, accent_col: Color = MultiplayerTheme.COL_GOLD) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.09, 0.14, 0.11, 0.92), accent_col.darkened(0.25), 12, 2, 2, 2)
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
	val.add_theme_font_size_override("font_size", 19)
	val.add_theme_color_override("font_color", accent_col)
	vbox.add_child(val)

	return panel


static func create_versus_player_card(
	p_data: Dictionary,
	is_local_player: bool
) -> PanelContainer:
	var border_col := MultiplayerTheme.COL_GOLD if is_local_player else Color(0.92, 0.42, 0.36)
	var bg_col := Color(0.14, 0.23, 0.17, 0.98) if is_local_player else Color(0.22, 0.15, 0.16, 0.98)
	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(260, 250)
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 18, 3, 8, 5))

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 8)
	card.add_child(vbox)

	var tag_lbl := Label.new()
	tag_lbl.text = "YOUR TRAINED DOG" if is_local_player else "WORTHY CHALLENGER"
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

	var portrait := DogAvatarPortrait.new(avatar_id, 68.0, true)
	icon_row.add_child(portrait)

	var badge := LeagueBadgeControl.new(league_name, 54.0, true)
	icon_row.add_child(badge)

	var dname := str(p_data.get("display_name", p_data.get("username", "Challenger")))
	var uname := str(p_data.get("username", "player"))

	var name_lbl := Label.new()
	name_lbl.text = dname
	name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_TEXT_CREAM, 5)
	vbox.add_child(name_lbl)

	var user_lbl := Label.new()
	user_lbl.text = "@" + uname
	user_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	user_lbl.add_theme_font_size_override("font_size", 13)
	user_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	vbox.add_child(user_lbl)

	var trophy_row := HBoxContainer.new()
	trophy_row.alignment = BoxContainer.ALIGNMENT_CENTER
	trophy_row.add_theme_constant_override("separation", 6)
	vbox.add_child(trophy_row)

	trophy_row.add_child(TrophyIconControl.new(24.0, 0.85))
	var tr_lbl := Label.new()
	tr_lbl.text = "%d Trophies • %s League" % [trophies, league_name]
	tr_lbl.add_theme_font_size_override("font_size", 15)
	tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	trophy_row.add_child(tr_lbl)

	if p_data.has("wins") or p_data.has("level"):
		var extra_lbl := Label.new()
		var lvl := int(p_data.get("level", 1))
		var wins := int(p_data.get("wins", 0))
		var ver := int(p_data.get("dog_model_version", 1))
		extra_lbl.text = "Lv.%d • %d Wins • Dog Model v%d" % [lvl, wins, ver]
		extra_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		extra_lbl.add_theme_font_size_override("font_size", 13)
		extra_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
		vbox.add_child(extra_lbl)

	return card


static func create_leaderboard_row(entry: Dictionary, my_player_id: String, on_inspect: Callable = Callable()) -> PanelContainer:
	var pos := int(entry.get("position", 0))
	var pid := str(entry.get("player_id", ""))
	var is_me := (pid != "" and pid == my_player_id)

	var bg_col := Color(0.14, 0.21, 0.16, 0.94)
	var border_col := Color(0.38, 0.48, 0.40, 0.75)
	var border_w := 2

	if is_me:
		bg_col = Color(0.20, 0.34, 0.23, 0.98)
		border_col = MultiplayerTheme.COL_GOLD
		border_w = 3
	elif pos == 1:
		bg_col = Color(0.28, 0.23, 0.11, 0.96)
		border_col = Color(1.0, 0.86, 0.28, 1.0)
	elif pos == 2:
		bg_col = Color(0.20, 0.23, 0.26, 0.96)
		border_col = Color(0.82, 0.88, 0.95, 1.0)
	elif pos == 3:
		bg_col = Color(0.25, 0.18, 0.13, 0.96)
		border_col = Color(0.88, 0.58, 0.32, 1.0)

	var row_panel := PanelContainer.new()
	row_panel.custom_minimum_size = Vector2(0, 62)
	row_panel.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 14, border_w, 3, 2))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	row_panel.add_child(hbox)

	# Rank column with medal
	var rank_box := CenterContainer.new()
	rank_box.custom_minimum_size = Vector2(54, 42)
	hbox.add_child(rank_box)

	var medal := RankMedalControl.new(pos)
	rank_box.add_child(medal)

	var rank_lbl := Label.new()
	rank_lbl.text = "#%d" % pos
	rank_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	rank_lbl.add_theme_font_size_override("font_size", 15 if pos <= 3 else 14)
	rank_lbl.add_theme_color_override("font_color", Color(0.12, 0.10, 0.06) if pos <= 3 else MultiplayerTheme.COL_TEXT_CREAM)
	rank_box.add_child(rank_lbl)

	# Avatar portrait
	var avatar_id := str(entry.get("avatar", "dog_default"))
	hbox.add_child(DogAvatarPortrait.new(avatar_id, 44.0, false))

	# Player Identity
	var id_vbox := VBoxContainer.new()
	id_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	id_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	id_vbox.add_theme_constant_override("separation", 1)
	hbox.add_child(id_vbox)

	var dname := str(entry.get("display_name", entry.get("username", "Player")))
	var uname := str(entry.get("username", "player"))
	var lvl := int(entry.get("level", 1))
	var ver := int(entry.get("dog_model_version", 1))

	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	id_vbox.add_child(name_row)

	var name_lbl := Label.new()
	name_lbl.text = dname + (" (YOU)" if is_me else "")
	name_lbl.add_theme_font_size_override("font_size", 17)
	name_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT if is_me else MultiplayerTheme.COL_TEXT_CREAM)
	name_row.add_child(name_lbl)

	var sub_lbl := Label.new()
	sub_lbl.text = "@%s • Lv.%d • AI Dog v%d" % [uname, lvl, ver]
	sub_lbl.add_theme_font_size_override("font_size", 12)
	sub_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	id_vbox.add_child(sub_lbl)

	# W/L/D & Best Score column
	var stats_vbox := VBoxContainer.new()
	stats_vbox.custom_minimum_size = Vector2(180, 0)
	stats_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	stats_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(stats_vbox)

	var wins := int(entry.get("wins", 0))
	var losses := int(entry.get("losses", 0))
	var draws := int(entry.get("draws", 0))
	var win_pct := float(entry.get("win_rate", 0.0)) * 100.0
	var best_val = entry.get("best_score", null)
	var best_str := str(best_val) if best_val != null else "-"

	var wld_lbl := Label.new()
	wld_lbl.text = "%dW / %dL / %dD (%.0f%%)" % [wins, losses, draws, win_pct]
	wld_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	wld_lbl.add_theme_font_size_override("font_size", 14)
	wld_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	stats_vbox.add_child(wld_lbl)

	var best_lbl := Label.new()
	best_lbl.text = "Best Official Score: %s" % best_str
	best_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	best_lbl.add_theme_font_size_override("font_size", 12)
	best_lbl.add_theme_color_override("font_color", Color(0.55, 0.94, 0.66))
	stats_vbox.add_child(best_lbl)

	# League Shield & Trophy Count Pill
	var league_name := str(entry.get("league", "Beginner"))
	hbox.add_child(LeagueBadgeControl.new(league_name, 38.0, false))

	var trophy_pill := PanelContainer.new()
	trophy_pill.custom_minimum_size = Vector2(118, 38)
	trophy_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 18)
	)
	hbox.add_child(trophy_pill)

	var tr_hbox := HBoxContainer.new()
	tr_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	tr_hbox.add_theme_constant_override("separation", 6)
	trophy_pill.add_child(tr_hbox)

	tr_hbox.add_child(TrophyIconControl.new(20.0, 0.72))
	var tr_val := Label.new()
	tr_val.text = str(int(entry.get("trophies", 0)))
	tr_val.add_theme_font_size_override("font_size", 17)
	tr_val.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	tr_hbox.add_child(tr_val)

	if on_inspect.is_valid() and uname != "":
		var view_btn := Button.new()
		view_btn.text = "Profile"
		view_btn.custom_minimum_size = Vector2(74, 34)
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

	var outcome_title := "IN PROGRESS"
	var accent_col := Color(0.55, 0.78, 0.95)
	var bg_col := Color(0.13, 0.19, 0.22, 0.95)

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
		accent_col = Color(0.62, 0.64, 0.62)
		bg_col = Color(0.18, 0.20, 0.18, 0.94)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(0, 74)
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, accent_col, 14, 2, 4, 3))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 14)
	card.add_child(hbox)

	# Outcome Badge Pill
	var badge_panel := PanelContainer.new()
	badge_panel.custom_minimum_size = Vector2(106, 46)
	badge_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(accent_col.darkened(0.45), accent_col, 12)
	)
	hbox.add_child(badge_panel)

	var badge_lbl := Label.new()
	badge_lbl.text = outcome_title
	badge_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	badge_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	badge_lbl.add_theme_font_size_override("font_size", 16)
	badge_lbl.add_theme_color_override("font_color", accent_col.lightened(0.35))
	badge_panel.add_child(badge_lbl)

	# Opponent Avatar & Match Info
	var opp_avatar := str(opp.get("avatar", "dog_default"))
	hbox.add_child(DogAvatarPortrait.new(opp_avatar, 46.0, false))

	var info_vbox := VBoxContainer.new()
	info_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	info_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(info_vbox)

	var opp_name := str(opp.get("display_name", opp.get("username", "Opponent")))
	var vs_lbl := Label.new()
	vs_lbl.text = "vs. %s (@%s)" % [opp_name, str(opp.get("username", "opponent"))]
	vs_lbl.add_theme_font_size_override("font_size", 17)
	vs_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	info_vbox.add_child(vs_lbl)

	var created_raw := str(match_data.get("created_at", ""))
	var date_clean := created_raw.substr(0, 19).replace("T", " ") if created_raw.length() >= 19 else created_raw
	var map_id := str(match_data.get("map_id", "Arena Map"))
	var meta_lbl := Label.new()
	meta_lbl.text = "Map: %s • %s" % [map_id, date_clean]
	meta_lbl.add_theme_font_size_override("font_size", 12)
	meta_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	info_vbox.add_child(meta_lbl)

	# Score Comparison Box
	var score_vbox := VBoxContainer.new()
	score_vbox.custom_minimum_size = Vector2(190, 0)
	score_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	score_vbox.add_theme_constant_override("separation", 2)
	hbox.add_child(score_vbox)

	var my_sc := str(my_sub.get("verified_score", "-")) if !my_sub.is_empty() else "-"
	var opp_sc := str(opp_sub.get("verified_score", "-")) if !opp_sub.is_empty() else "-"
	var sc_lbl := Label.new()
	sc_lbl.text = "Score: %s  vs  %s" % [my_sc, opp_sc]
	sc_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	sc_lbl.add_theme_font_size_override("font_size", 16)
	sc_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	score_vbox.add_child(sc_lbl)

	var my_steps := str(my_sub.get("steps", "-")) if !my_sub.is_empty() else "-"
	var my_bones := str(my_sub.get("bones_collected", "-")) if !my_sub.is_empty() else "-"
	var detail_sc := Label.new()
	detail_sc.text = "Your Dog: %s steps, %s bones" % [my_steps, my_bones]
	detail_sc.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	detail_sc.add_theme_font_size_override("font_size", 12)
	detail_sc.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	score_vbox.add_child(detail_sc)

	# Trophy Delta Badge
	var tr_change = my_sub.get("trophy_change", null)
	if tr_change == null and trophy_delta_map.has(mid):
		tr_change = trophy_delta_map[mid]

	var tr_panel := PanelContainer.new()
	tr_panel.custom_minimum_size = Vector2(92, 38)
	tr_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.12, 0.09, 0.92), MultiplayerTheme.COL_GOLD_BORDER, 16)
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

	# Inspect Details Button
	var inspect_btn := Button.new()
	inspect_btn.text = "Details"
	inspect_btn.custom_minimum_size = Vector2(82, 36)
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
		MultiplayerTheme.make_panel_style(Color(0.10, 0.15, 0.12, 0.88), Color(0.42, 0.54, 0.44, 0.65), 16, 2, 2, 2)
	)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 10)
	panel.add_child(vbox)

	var icon_holder := CenterContainer.new()
	vbox.add_child(icon_holder)
	if icon_type == "dog":
		icon_holder.add_child(DogAvatarPortrait.new("dog_default", 64.0, true))
	elif icon_type == "shield":
		icon_holder.add_child(LeagueBadgeControl.new("Gold", 58.0, true))
	else:
		icon_holder.add_child(TrophyIconControl.new(54.0, 1.7))

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

