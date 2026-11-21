extends Control

class_name MazeCompletionPopup

# ==============================================================================
# DOOBYSCOO — MAZE COMPLETION REWARD POPUP
# Celebratory completion screen displaying Bones Collected, Score,
# Your Best Score (with New Personal Best highlight), and a data-driven
# RL Policy Update guidance reminder based on the agent's continual-learning
# batch threshold (continual.episodesPerUpdate = 8).
# ==============================================================================

const RECOMMENDED_EPISODES_FOR_UPDATE := 8

signal closed()

var _backdrop: ColorRect
var _center: CenterContainer
var _card: PanelContainer
var _burst: _CelebrationCrest
var _title_lbl: Label
var _new_best_pill: PanelContainer
var _new_best_lbl: Label

var _bones_icons_row: HBoxContainer
var _bones_count_lbl: Label
var _score_val_lbl: Label
var _steps_sub_lbl: Label
var _best_card: PanelContainer
var _best_val_lbl: Label
var _best_sub_lbl: Label

var _reminder_card: PanelContainer
var _reminder_title_lbl: Label
var _reminder_body_lbl: Label
var _reminder_bar: ProgressBar

var _continue_btn: Button
var _score_tween: Tween
var _display_score: float = 0.0


class _CelebrationCrest extends Control:
	var is_victory: bool = true
	var is_new_best: bool = false
	var _phase: float = 0.0

	func _init() -> void:
		custom_minimum_size = Vector2(180, 74)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _process(delta: float) -> void:
		if is_visible_in_tree():
			_phase += delta * 3.4
			queue_redraw()

	func _draw() -> void:
		var c := size * 0.5
		if is_victory:
			var star_count: int = 10 if is_new_best else 6
			for i in range(star_count):
				var ang := _phase * 0.55 + float(i) * (TAU / float(star_count))
				var rx := 58.0 + sin(_phase * 1.4 + float(i)) * 7.0
				var ry := 24.0 + cos(_phase * 1.2 + float(i)) * 4.0
				var sp := c + Vector2(cos(ang) * rx, sin(ang) * ry)
				var r := 3.6 if (i % 2 == 0) else 2.4
				var col := DoobyUI.COL_GOLD_BRIGHT if (i % 2 == 0) else Color(0.60, 0.96, 0.72, 0.92)
				draw_circle(sp, r, col)
			if is_new_best:
				var ring_r := 30.0 + sin(_phase * 2.2) * 2.5
				draw_arc(c, ring_r, 0.0, TAU, 36, Color(1.0, 0.90, 0.42, 0.45), 2.5)
			MultiplayerTheme.draw_trophy_icon(self, c, 1.85, DoobyUI.COL_GOLD)
		else:
			MultiplayerTheme.draw_dog_avatar(self, c, 28.0, "dog_default", _phase)


class _BoneSlotControl extends Control:
	var collected: bool = false:
		set(v):
			collected = v
			queue_redraw()

	func _init(p_collected: bool = false) -> void:
		collected = p_collected
		custom_minimum_size = Vector2(36, 32)
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		var c := size * 0.5
		if collected:
			draw_circle(c, 14.0, Color(1.0, 0.90, 0.42, 0.22))
			MultiplayerTheme.draw_bone_icon(self, c, 1.15)
		else:
			var dim := Color(0.32, 0.40, 0.34, 0.48)
			for off in [Vector2(-7, -4), Vector2(-7, 4), Vector2(7, -4), Vector2(7, 4)]:
				draw_circle(c + off * 1.05, 3.6, dim)
			draw_line(c + Vector2(-7, 0) * 1.05, c + Vector2(7, 0) * 1.05, dim, 5.2)


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	grow_horizontal = Control.GROW_DIRECTION_BOTH
	grow_vertical = Control.GROW_DIRECTION_BOTH
	visible = false
	z_index = 50
	_build_ui()


func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		_close_popup()
		get_viewport().set_input_as_handled()


func _build_ui() -> void:
	_backdrop = ColorRect.new()
	_backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_backdrop.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_backdrop.grow_vertical = Control.GROW_DIRECTION_BOTH
	_backdrop.color = Color(0.04, 0.09, 0.06, 0.72)
	add_child(_backdrop)

	_center = CenterContainer.new()
	_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_center.grow_horizontal = Control.GROW_DIRECTION_BOTH
	_center.grow_vertical = Control.GROW_DIRECTION_BOTH
	add_child(_center)

	_card = PanelContainer.new()
	_card.custom_minimum_size = Vector2(540, 0)
	_card.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DARK, DoobyUI.COL_GOLD, 24, 3, 28, 22)
	)
	_center.add_child(_card)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 14)
	_card.add_child(vbox)

	# --- TOP: Celebratory Crest, Heading, and Optional New Personal Best Pill ---
	var top_vbox := VBoxContainer.new()
	top_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	top_vbox.add_theme_constant_override("separation", 6)
	vbox.add_child(top_vbox)

	var crest_center := CenterContainer.new()
	top_vbox.add_child(crest_center)
	_burst = _CelebrationCrest.new()
	crest_center.add_child(_burst)

	_title_lbl = Label.new()
	_title_lbl.text = "MAZE COMPLETED!"
	_title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_title_lbl.label_settings = DoobyUI.make_heading_settings(34, DoobyUI.COL_GOLD_BRIGHT, 7)
	top_vbox.add_child(_title_lbl)

	var pill_center := CenterContainer.new()
	top_vbox.add_child(pill_center)
	_new_best_pill = PanelContainer.new()
	_new_best_pill.visible = false
	_new_best_pill.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_pill(Color(0.36, 0.27, 0.06, 0.96), DoobyUI.COL_GOLD_BRIGHT, 16)
	)
	pill_center.add_child(_new_best_pill)

	_new_best_lbl = Label.new()
	_new_best_lbl.text = "NEW PERSONAL BEST!"
	_new_best_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_new_best_lbl.add_theme_font_size_override("font_size", 13)
	_new_best_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
	_new_best_pill.add_child(_new_best_lbl)

	# --- MIDDLE: Performance Summary (Bones + Score + Your Best Score) ---
	var bones_card := PanelContainer.new()
	bones_card.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DEEP, Color(0.48, 0.60, 0.48, 0.72), 16, 2, 16, 12)
	)
	vbox.add_child(bones_card)

	var bones_vbox := VBoxContainer.new()
	bones_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	bones_vbox.add_theme_constant_override("separation", 6)
	bones_card.add_child(bones_vbox)

	var bones_cap := Label.new()
	bones_cap.text = "BONES COLLECTED"
	bones_cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	bones_cap.add_theme_font_size_override("font_size", 12)
	bones_cap.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	bones_vbox.add_child(bones_cap)

	_bones_icons_row = HBoxContainer.new()
	_bones_icons_row.alignment = BoxContainer.ALIGNMENT_CENTER
	_bones_icons_row.add_theme_constant_override("separation", 10)
	bones_vbox.add_child(_bones_icons_row)

	_bones_count_lbl = Label.new()
	_bones_count_lbl.text = "0 / 5 Bones"
	_bones_count_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bones_count_lbl.add_theme_font_size_override("font_size", 15)
	_bones_count_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
	bones_vbox.add_child(_bones_count_lbl)

	# Score & Your Best Score Side-by-Side Hero Cards
	var scores_row := HBoxContainer.new()
	scores_row.add_theme_constant_override("separation", 14)
	vbox.add_child(scores_row)

	var score_card := PanelContainer.new()
	score_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	score_card.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(Color(0.11, 0.21, 0.15, 0.96), Color(0.45, 0.90, 0.58, 0.92), 18, 2, 16, 14)
	)
	scores_row.add_child(score_card)

	var sc_vbox := VBoxContainer.new()
	sc_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	sc_vbox.add_theme_constant_override("separation", 4)
	score_card.add_child(sc_vbox)

	var sc_cap := Label.new()
	sc_cap.text = "SCORE"
	sc_cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sc_cap.add_theme_font_size_override("font_size", 13)
	sc_cap.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	sc_vbox.add_child(sc_cap)

	_score_val_lbl = Label.new()
	_score_val_lbl.text = "0"
	_score_val_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_score_val_lbl.label_settings = DoobyUI.make_heading_settings(40, Color(0.52, 0.98, 0.68, 1.0), 6)
	sc_vbox.add_child(_score_val_lbl)

	_steps_sub_lbl = Label.new()
	_steps_sub_lbl.text = "0 Steps  •  Lower is Better"
	_steps_sub_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_steps_sub_lbl.add_theme_font_size_override("font_size", 12)
	_steps_sub_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	sc_vbox.add_child(_steps_sub_lbl)

	_best_card = PanelContainer.new()
	_best_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_best_card.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DEEP, DoobyUI.COL_GOLD_BORDER, 18, 2, 16, 14)
	)
	scores_row.add_child(_best_card)

	var best_vbox := VBoxContainer.new()
	best_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	best_vbox.add_theme_constant_override("separation", 4)
	_best_card.add_child(best_vbox)

	var best_cap := Label.new()
	best_cap.text = "YOUR BEST SCORE"
	best_cap.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	best_cap.add_theme_font_size_override("font_size", 13)
	best_cap.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
	best_vbox.add_child(best_cap)

	_best_val_lbl = Label.new()
	_best_val_lbl.text = "--"
	_best_val_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_best_val_lbl.label_settings = DoobyUI.make_heading_settings(40, DoobyUI.COL_GOLD_BRIGHT, 6)
	best_vbox.add_child(_best_val_lbl)

	_best_sub_lbl = Label.new()
	_best_sub_lbl.text = "Personal Record"
	_best_sub_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_best_sub_lbl.add_theme_font_size_override("font_size", 12)
	_best_sub_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	best_vbox.add_child(_best_sub_lbl)

	# --- BOTTOM: RL Policy Update Reminder (Visually Secondary) ---
	_reminder_card = PanelContainer.new()
	_reminder_card.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(Color(0.08, 0.14, 0.11, 0.90), Color(0.42, 0.54, 0.45, 0.65), 14, 1, 14, 10)
	)
	vbox.add_child(_reminder_card)

	var rem_vbox := VBoxContainer.new()
	rem_vbox.add_theme_constant_override("separation", 5)
	_reminder_card.add_child(rem_vbox)

	_reminder_title_lbl = Label.new()
	_reminder_title_lbl.text = "Keep Training!"
	_reminder_title_lbl.add_theme_font_size_override("font_size", 14)
	_reminder_title_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
	rem_vbox.add_child(_reminder_title_lbl)

	_reminder_body_lbl = Label.new()
	_reminder_body_lbl.text = ""
	_reminder_body_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_reminder_body_lbl.add_theme_font_size_override("font_size", 13)
	_reminder_body_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	rem_vbox.add_child(_reminder_body_lbl)

	_reminder_bar = ProgressBar.new()
	_reminder_bar.custom_minimum_size = Vector2(0, 8)
	_reminder_bar.show_percentage = false
	_reminder_bar.max_value = RECOMMENDED_EPISODES_FOR_UPDATE
	_reminder_bar.value = 0
	MultiplayerTheme.style_progress_bar(_reminder_bar, DoobyUI.COL_GOLD)
	rem_vbox.add_child(_reminder_bar)

	# --- Footer Action ---
	var btn_center := CenterContainer.new()
	vbox.add_child(btn_center)

	_continue_btn = Button.new()
	_continue_btn.text = "Continue"
	_continue_btn.custom_minimum_size = Vector2(200, 48)
	DoobyUI.style_gold_button(_continue_btn, 19, 24)
	_continue_btn.pressed.connect(_close_popup)
	btn_center.add_child(_continue_btn)


func show_completion(summary: Dictionary) -> void:
	var won: bool = bool(summary.get("won", false))
	var score_limit: bool = bool(summary.get("score_limit", false))
	var final_score: int = int(summary.get("score", 0))
	var steps: int = int(summary.get("steps", 0))
	var bones: int = int(summary.get("bones", 0))
	var total_bones: int = maxi(0, int(summary.get("total_bones", 5)))
	var best_score_val = summary.get("best_score", null)
	var is_new_best: bool = bool(summary.get("is_new_best", false))
	var pending_episodes: int = int(summary.get("pending_episodes", 0))
	var is_learning: bool = bool(summary.get("learning", false))
	var is_mock: bool = bool(summary.get("is_mock", false))
	var collect_exp: bool = bool(summary.get("collect_experience", true))

	# 1. Header & Celebratory State
	_burst.is_victory = won
	_burst.is_new_best = won and is_new_best
	if won:
		_title_lbl.text = "MAZE COMPLETED!"
		_title_lbl.label_settings = DoobyUI.make_heading_settings(34, DoobyUI.COL_GOLD_BRIGHT, 7)
		DoobyUI.style_gold_button(_continue_btn, 19, 24)
	elif score_limit:
		_title_lbl.text = "SCORE LIMIT REACHED"
		_title_lbl.label_settings = DoobyUI.make_heading_settings(28, Color(1.0, 0.78, 0.45, 1.0), 6)
		DoobyUI.style_lavender_button(_continue_btn, 18, 22)
	else:
		_title_lbl.text = "ATTEMPT FINISHED"
		_title_lbl.label_settings = DoobyUI.make_heading_settings(30, DoobyUI.COL_TEXT_CREAM, 6)
		DoobyUI.style_lavender_button(_continue_btn, 18, 22)

	_new_best_pill.visible = won and is_new_best

	# 2. Bones Collected Icons & Count
	for child in _bones_icons_row.get_children():
		child.queue_free()
	var slot_count: int = maxi(total_bones, bones)
	var slots_to_anim: Array[_BoneSlotControl] = []
	for i in range(slot_count):
		var got_this: bool = i < bones
		var slot := _BoneSlotControl.new(got_this)
		_bones_icons_row.add_child(slot)
		if got_this:
			slot.scale = Vector2(0.2, 0.2)
			slots_to_anim.append(slot)
	_bones_count_lbl.text = "%d / %d Bones Collected" % [bones, total_bones]
	if bones == 0:
		_bones_count_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)
	else:
		_bones_count_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)

	# 3. Score & Your Best Score
	_steps_sub_lbl.text = "%d Steps  •  Lower is Better" % steps
	if best_score_val != null:
		_best_val_lbl.text = str(int(best_score_val))
	else:
		_best_val_lbl.text = "--"

	if won and is_new_best:
		_best_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.22, 0.20, 0.08, 0.96), DoobyUI.COL_GOLD_BRIGHT, 18, 3, 16, 14)
		)
		_best_sub_lbl.text = "New Personal Record!"
		_best_sub_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
	else:
		_best_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DEEP, DoobyUI.COL_GOLD_BORDER, 18, 2, 16, 14)
		)
		_best_sub_lbl.text = "Personal Record"
		_best_sub_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_MUTED)

	# 4. Data-Driven RL Policy Update Reminder
	_configure_policy_reminder(pending_episodes, is_learning, is_mock, collect_exp)

	# 5. Smooth Entrance & Reward Animations (non-blocking)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_backdrop.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	visible = true
	_backdrop.color.a = 0.0
	_card.modulate.a = 0.0
	_card.scale = Vector2(0.90, 0.90)
	_card.pivot_offset = _card.size * 0.5
	call_deferred("_sync_card_pivot")

	var enter_tw := create_tween()
	enter_tw.set_parallel(true)
	enter_tw.tween_property(_backdrop, "color:a", 0.72, 0.16)
	enter_tw.tween_property(_card, "modulate:a", 1.0, 0.18)
	enter_tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	enter_tw.tween_property(_card, "scale", Vector2.ONE, 0.24)

	# Animate Score Count-Up
	if _score_tween != null and _score_tween.is_valid():
		_score_tween.kill()
	_display_score = 0.0
	_score_val_lbl.text = "0"
	_score_tween = create_tween()
	_score_tween.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	_score_tween.tween_method(_set_animated_score, 0.0, float(final_score), 0.42)

	# Staggered Pop-In for Collected Bones
	for idx in range(slots_to_anim.size()):
		var bone_slot: _BoneSlotControl = slots_to_anim[idx]
		bone_slot.pivot_offset = Vector2(18, 16)
		var b_tw := create_tween()
		b_tw.tween_interval(0.10 + float(idx) * 0.07)
		b_tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		b_tw.tween_property(bone_slot, "scale", Vector2.ONE, 0.20)

	# Subtle Pop on New Personal Best Pill
	if _new_best_pill.visible:
		_new_best_pill.scale = Vector2(0.82, 0.82)
		_new_best_pill.pivot_offset = _new_best_pill.size * 0.5
		var nb_tw := create_tween()
		nb_tw.tween_interval(0.16)
		nb_tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		nb_tw.tween_property(_new_best_pill, "scale", Vector2.ONE, 0.24)


func _configure_policy_reminder(pending_episodes: int, is_learning: bool, is_mock: bool, collect_exp: bool) -> void:
	if is_mock:
		_reminder_card.visible = false
		return

	_reminder_card.visible = true
	if is_learning:
		_reminder_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.08, 0.16, 0.18, 0.90), Color(0.45, 0.78, 0.94, 0.75), 14, 1, 14, 10)
		)
		_reminder_title_lbl.text = "Policy Update in Progress"
		_reminder_title_lbl.add_theme_color_override("font_color", Color(0.62, 0.90, 1.0, 1.0))
		_reminder_body_lbl.text = "Your dog is currently learning from its recent training runs."
		_reminder_bar.visible = false
	elif !collect_exp:
		_reminder_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.08, 0.14, 0.11, 0.88), Color(0.42, 0.54, 0.45, 0.60), 14, 1, 14, 10)
		)
		_reminder_title_lbl.text = "Experience Recording Paused"
		_reminder_title_lbl.add_theme_color_override("font_color", DoobyUI.COL_TEXT_CREAM)
		_reminder_body_lbl.text = "Enable Record Learning when you want to gather training runs for a future policy update."
		_reminder_bar.visible = false
	elif pending_episodes == 0:
		_reminder_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.08, 0.15, 0.12, 0.90), Color(0.45, 0.68, 0.52, 0.65), 14, 1, 14, 10)
		)
		_reminder_title_lbl.text = "Policy Up to Date"
		_reminder_title_lbl.add_theme_color_override("font_color", Color(0.62, 0.94, 0.72, 1.0))
		_reminder_body_lbl.text = "No new training runs are waiting yet. Complete more runs to build up experience."
		_reminder_bar.visible = false
	elif pending_episodes >= RECOMMENDED_EPISODES_FOR_UPDATE:
		_reminder_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.10, 0.21, 0.14, 0.94), Color(0.42, 0.88, 0.56, 0.85), 14, 2, 14, 10)
		)
		_reminder_title_lbl.text = "Your dog has gained plenty of experience!"
		_reminder_title_lbl.add_theme_color_override("font_color", Color(0.55, 0.98, 0.68, 1.0))
		_reminder_body_lbl.text = "%d training runs are ready. Consider pressing Update Policy to help your dog learn from them." % pending_episodes
		_reminder_bar.visible = true
		_reminder_bar.max_value = RECOMMENDED_EPISODES_FOR_UPDATE
		_reminder_bar.value = RECOMMENDED_EPISODES_FOR_UPDATE
		MultiplayerTheme.style_progress_bar(_reminder_bar, Color(0.32, 0.84, 0.48, 1.0))
	else:
		_reminder_card.add_theme_stylebox_override(
			"panel",
			DoobyUI.make_meadow_panel(Color(0.15, 0.16, 0.10, 0.92), Color(0.82, 0.68, 0.34, 0.72), 14, 1, 14, 10)
		)
		_reminder_title_lbl.text = "Keep training!"
		_reminder_title_lbl.add_theme_color_override("font_color", DoobyUI.COL_GOLD_BRIGHT)
		var run_word: String = "run" if pending_episodes == 1 else "runs"
		_reminder_body_lbl.text = "%d of %d recommended %s collected. Updating after only a few runs can add noise — gather more experience before updating." % [
			pending_episodes,
			RECOMMENDED_EPISODES_FOR_UPDATE,
			run_word
		]
		_reminder_bar.visible = true
		_reminder_bar.max_value = RECOMMENDED_EPISODES_FOR_UPDATE
		_reminder_bar.value = pending_episodes
		MultiplayerTheme.style_progress_bar(_reminder_bar, DoobyUI.COL_GOLD)


func _set_animated_score(val: float) -> void:
	_display_score = val
	_score_val_lbl.text = str(int(round(val)))


func _sync_card_pivot() -> void:
	if _card != null:
		_card.pivot_offset = _card.size * 0.5


func _close_popup() -> void:
	if !visible:
		return
	var exit_tw := create_tween()
	exit_tw.set_parallel(true)
	exit_tw.tween_property(_backdrop, "color:a", 0.0, 0.12)
	exit_tw.tween_property(_card, "modulate:a", 0.0, 0.12)
	exit_tw.tween_property(_card, "scale", Vector2(0.95, 0.95), 0.12)
	await exit_tw.finished
	visible = false
	closed.emit()

