extends Control

# ==============================================================================
# DOOBYSCOO ONLINE MULTIPLAYER ARENA — COMPLETE COMPETITIVE GAME UI
# ==============================================================================

var mp_client: MultiplayerClient
var rl_adapter: RLAdapter
var board: GameplayBoard
var score_manager: ScoreManager

# --- Backward-Compatible Legacy Nodes & References ---
var top_status_label: Label
var top_player_badge: Label
var server_url_input: LineEdit
var rl_url_input: LineEdit

var auth_panel: PanelContainer
var hub_tabs: Control # Kept for compatibility; navigation uses polished pill tabs

var login_user_input: LineEdit
var login_pass_input: LineEdit
var reg_user_input: LineEdit
var reg_display_input: LineEdit
var reg_email_input: LineEdit
var reg_pass_input: LineEdit
var auth_feedback_label: Label

var match_state_label: Label
var match_info_label: Label
var find_match_btn: Button
var cancel_match_btn: Button
var learn_after_match_btn: Button
var arena_step_log_label: Label
var arena_result_summary_label: RichTextLabel

var profile_details_text: RichTextLabel
var edit_display_input: LineEdit
var edit_avatar_select: OptionButton

var leaderboard_league_select: OptionButton
var leaderboard_text: RichTextLabel
var history_text: RichTextLabel

# --- New Game-Style UI Controls & Containers ---
var conn_dot: MultiplayerComponents.ConnectionDotControl
var rl_status_pill_label: Label
var rl_dot: MultiplayerComponents.ConnectionDotControl
var settings_drawer: PanelContainer
var header_trophy_label: Label
var header_league_badge: MultiplayerComponents.LeagueBadgeControl
var header_avatar: MultiplayerComponents.DogAvatarPortrait
var logout_btn: Button

var nav_bar: PanelContainer
var nav_buttons: Array[Button] = []
var main_pages: Array[Control] = []
var current_tab_index: int = 0

# --- Tab 0: Arena Lobby, Matchmaking, Opponent Found, Live Battle, Battle Results ---
var arena_page: Control
var lobby_view: Control
var matchmaking_overlay: PanelContainer
var versus_overlay: PanelContainer
var battle_view: Control
var results_overlay: PanelContainer
var inspect_modal: PanelContainer

# Lobby Player Profile Card & Progression
var lobby_avatar: MultiplayerComponents.DogAvatarPortrait
var lobby_display_name_lbl: Label
var lobby_username_lbl: Label
var lobby_level_lbl: Label
var lobby_xp_bar: ProgressBar
var lobby_league_badge: MultiplayerComponents.LeagueBadgeControl
var lobby_league_name_lbl: Label
var lobby_trophy_count_lbl: Label
var lobby_next_league_lbl: Label
var lobby_league_progress_bar: ProgressBar
var lobby_stat_rank: PanelContainer
var lobby_stat_wins: PanelContainer
var lobby_stat_losses: PanelContainer
var lobby_stat_winrate: PanelContainer
var lobby_stat_best: PanelContainer
var lobby_stat_model: PanelContainer
var lobby_agent_ready_lbl: Label
var lobby_quick_status_lbl: Label

# Matchmaking Overlay Controls
var mm_radar: MultiplayerComponents.MatchmakingRadarControl
var mm_headline_lbl: Label
var mm_substatus_lbl: Label
var mm_timer_lbl: Label
var mm_trophy_range_lbl: Label
var mm_player_summary_lbl: Label

# Opponent Found (VS) Overlay Controls
var vs_left_slot: VBoxContainer
var vs_right_slot: VBoxContainer
var vs_status_banner_lbl: Label
var vs_map_badge_lbl: Label

# Active Battle HUD Controls
var battle_you_avatar: MultiplayerComponents.DogAvatarPortrait
var battle_you_name_lbl: Label
var battle_you_trophies_lbl: Label
var battle_opp_avatar: MultiplayerComponents.DogAvatarPortrait
var battle_opp_name_lbl: Label
var battle_opp_trophies_lbl: Label
var battle_opp_status_pill: Label
var battle_timer_lbl: Label
var battle_score_val_lbl: Label
var battle_steps_val_lbl: Label
var battle_bones_val_lbl: Label
var battle_bones_bar: ProgressBar
var battle_steps_bar: ProgressBar
var battle_map_info_lbl: Label
var battle_return_lobby_btn: Button

# Battle Results Overlay Controls
var res_banner_icon: MultiplayerComponents.ResultBannerControl
var res_title_lbl: Label
var res_subtitle_lbl: Label
var res_you_card_box: VBoxContainer
var res_opp_card_box: VBoxContainer
var res_trophy_delta_lbl: Label
var res_xp_awarded_lbl: Label
var res_duration_lbl: Label
var res_play_again_btn: Button
var res_back_lobby_btn: Button
var res_train_dog_btn: Button
var res_train_feedback_lbl: Label

# Profile Tab Controls
var prof_avatar_large: MultiplayerComponents.DogAvatarPortrait
var prof_league_shield_large: MultiplayerComponents.LeagueBadgeControl
var prof_title_name_lbl: Label
var prof_handle_lbl: Label
var prof_trophy_big_lbl: Label
var prof_league_tier_lbl: Label
var prof_league_bar: ProgressBar
var prof_xp_bar: ProgressBar
var prof_level_badge_lbl: Label
var prof_stats_grid: GridContainer
var prof_save_feedback_lbl: Label
var avatar_choice_buttons: Array[Button] = []

# Leaderboard Tab Controls
var lb_podium_container: HBoxContainer
var lb_rows_vbox: VBoxContainer
var lb_header_title_lbl: Label
var lb_your_rank_banner_lbl: Label
var lb_page_lbl: Label
var lb_prev_btn: Button
var lb_next_btn: Button
var lb_current_mode: String = "global"
var lb_current_offset: int = 0
const LB_PAGE_LIMIT: int = 25

# Battle History Tab Controls
var hist_matches_vbox: VBoxContainer
var hist_trophies_vbox: VBoxContainer
var hist_summary_stats_lbl: Label

# Match / Player Inspect Modal Controls
var inspect_title_lbl: Label
var inspect_body_vbox: VBoxContainer

# --- Runtime State ---
var active_match_id: String = ""
var active_map_id: String = ""
var active_map_hash: String = ""
var active_maze_data: Dictionary = {}
var current_opponent_data: Dictionary = {}
var match_expires_unix: float = 0.0
var match_started_unix: float = 0.0
var solving_active: bool = false
var step_in_progress: bool = false
var step_timer: float = 0.0
var step_interval: float = 0.12
var status_poll_timer: float = 0.0
var rl_health_poll_timer: float = 0.0
var is_searching_match: bool = false
var search_elapsed_sec: float = 0.0
var play_btn_pulse_phase: float = 0.0
var local_rl_online: bool = false
var local_rl_model_version: int = 1
var vs_transition_in_progress: bool = false
var cached_trophy_deltas: Dictionary = {}


func _ready() -> void:
	score_manager = ScoreManager.new(5)
	mp_client = MultiplayerClient.new()
	add_child(mp_client)

	rl_adapter = RLAdapter.new()
	add_child(rl_adapter)

	_build_ui()
	_connect_signals()
	_check_local_rl_agent()

	if mp_client.is_authenticated():
		_show_authenticated_view()
		mp_client.connect_websocket()
		await _refresh_all_player_data()
	else:
		_show_auth_view()


func _build_ui() -> void:
	# Ambient Dark Arena Vignette Overlay over mainBG.png
	var vignette := ColorRect.new()
	vignette.set_anchors_preset(Control.PRESET_FULL_RECT)
	vignette.color = Color(0.05, 0.09, 0.07, 0.55)
	vignette.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(vignette)

	var root_vbox := VBoxContainer.new()
	root_vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	root_vbox.offset_left = 16.0
	root_vbox.offset_top = 10.0
	root_vbox.offset_right = -16.0
	root_vbox.offset_bottom = -10.0
	root_vbox.add_theme_constant_override("separation", 8)
	add_child(root_vbox)

	_build_top_header(root_vbox)
	_build_endpoints_drawer(root_vbox)
	_build_navigation_ribbon(root_vbox)

	# Auth View
	auth_panel = PanelContainer.new()
	auth_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	auth_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 10, 6)
	)
	root_vbox.add_child(auth_panel)
	_build_auth_panel()

	# Main Hub Content Stack
	hub_tabs = Control.new()
	hub_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hub_tabs.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hub_tabs.visible = false
	root_vbox.add_child(hub_tabs)

	_build_arena_tab()
	_build_profile_tab()
	_build_leaderboards_tab()
	_build_history_tab()

	# Overlays layered inside hub_tabs
	_build_matchmaking_overlay()
	_build_versus_overlay()
	_build_results_overlay()
	_build_inspect_modal()

	_switch_main_tab(0)


# ==============================================================================
# 1. TOP COMMAND BAR & ENDPOINTS DRAWER
# ==============================================================================

func _build_top_header(parent: VBoxContainer) -> void:
	var header_panel := PanelContainer.new()
	header_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.11, 0.17, 0.13, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2, 5, 3)
	)
	parent.add_child(header_panel)

	var top_bar := HBoxContainer.new()
	top_bar.add_theme_constant_override("separation", 12)
	header_panel.add_child(top_bar)

	var home_btn := Button.new()
	home_btn.text = "<- Home"
	home_btn.custom_minimum_size = Vector2(104, 38)
	MultiplayerTheme.style_lavender_button(home_btn, 16)
	home_btn.pressed.connect(_on_home_pressed)
	top_bar.add_child(home_btn)

	# Arena Crest + Title
	var title_box := HBoxContainer.new()
	title_box.add_theme_constant_override("separation", 8)
	top_bar.add_child(title_box)

	title_box.add_child(MultiplayerComponents.TrophyIconControl.new(30.0, 1.0))

	var title_lbl := Label.new()
	title_lbl.text = "DOOBYSCOO ARENA"
	title_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_TEXT_CREAM, 6)
	title_box.add_child(title_lbl)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top_bar.add_child(spacer)

	# Live Server Connection Status Pill
	var srv_pill := PanelContainer.new()
	srv_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.07, 0.11, 0.08, 0.94), Color(0.45, 0.58, 0.48, 0.75), 16)
	)
	top_bar.add_child(srv_pill)

	var srv_hbox := HBoxContainer.new()
	srv_hbox.add_theme_constant_override("separation", 6)
	srv_pill.add_child(srv_hbox)

	conn_dot = MultiplayerComponents.ConnectionDotControl.new()
	srv_hbox.add_child(conn_dot)

	top_status_label = Label.new()
	top_status_label.text = "Server: Connecting..."
	top_status_label.add_theme_font_size_override("font_size", 13)
	top_status_label.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	srv_hbox.add_child(top_status_label)

	# Local RL Agent Status Pill
	var rl_pill := PanelContainer.new()
	rl_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.07, 0.11, 0.08, 0.94), Color(0.45, 0.58, 0.48, 0.75), 16)
	)
	top_bar.add_child(rl_pill)

	var rl_hbox := HBoxContainer.new()
	rl_hbox.add_theme_constant_override("separation", 6)
	rl_pill.add_child(rl_hbox)

	rl_dot = MultiplayerComponents.ConnectionDotControl.new()
	rl_hbox.add_child(rl_dot)

	rl_status_pill_label = Label.new()
	rl_status_pill_label.text = "AI Dog: Checking..."
	rl_status_pill_label.add_theme_font_size_override("font_size", 13)
	rl_status_pill_label.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	rl_hbox.add_child(rl_status_pill_label)

	# Player Identity & Trophy Pill in Header
	var player_pill := PanelContainer.new()
	player_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.16, 0.24, 0.18, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 18)
	)
	top_bar.add_child(player_pill)

	var p_hbox := HBoxContainer.new()
	p_hbox.add_theme_constant_override("separation", 8)
	player_pill.add_child(p_hbox)

	header_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 28.0, false)
	p_hbox.add_child(header_avatar)

	top_player_badge = Label.new()
	top_player_badge.text = "Not Signed In"
	top_player_badge.add_theme_font_size_override("font_size", 14)
	top_player_badge.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	p_hbox.add_child(top_player_badge)

	header_league_badge = MultiplayerComponents.LeagueBadgeControl.new("Beginner", 26.0, false)
	p_hbox.add_child(header_league_badge)

	header_trophy_label = Label.new()
	header_trophy_label.text = "0"
	header_trophy_label.add_theme_font_size_override("font_size", 15)
	header_trophy_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	p_hbox.add_child(header_trophy_label)

	# Network Endpoints Drawer Toggle Button
	var net_btn := Button.new()
	net_btn.text = "Endpoints"
	net_btn.custom_minimum_size = Vector2(96, 36)
	MultiplayerTheme.style_subtle_button(net_btn, 14)
	net_btn.pressed.connect(func(): settings_drawer.visible = !settings_drawer.visible)
	top_bar.add_child(net_btn)

	logout_btn = Button.new()
	logout_btn.text = "Logout"
	logout_btn.custom_minimum_size = Vector2(84, 36)
	MultiplayerTheme.style_danger_button(logout_btn, 14)
	logout_btn.pressed.connect(_on_logout_pressed)
	top_bar.add_child(logout_btn)


func _build_endpoints_drawer(parent: VBoxContainer) -> void:
	settings_drawer = PanelContainer.new()
	settings_drawer.visible = false
	settings_drawer.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.09, 0.14, 0.11, 0.96), Color(0.52, 0.66, 0.54, 0.85), 14, 2, 4, 2)
	)
	parent.add_child(settings_drawer)

	var url_bar := HBoxContainer.new()
	url_bar.add_theme_constant_override("separation", 10)
	settings_drawer.add_child(url_bar)

	var srv_lbl := Label.new()
	srv_lbl.text = "Multiplayer Server URL:"
	srv_lbl.add_theme_font_size_override("font_size", 14)
	srv_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	url_bar.add_child(srv_lbl)

	server_url_input = LineEdit.new()
	server_url_input.text = mp_client.server_url
	server_url_input.custom_minimum_size = Vector2(230, 34)
	server_url_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	MultiplayerTheme.style_line_edit(server_url_input, 14)
	url_bar.add_child(server_url_input)

	var rl_lbl := Label.new()
	rl_lbl.text = "Local RL Agent URL:"
	rl_lbl.add_theme_font_size_override("font_size", 14)
	rl_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	url_bar.add_child(rl_lbl)

	rl_url_input = LineEdit.new()
	rl_url_input.text = MazeSession.server_url
	rl_url_input.custom_minimum_size = Vector2(210, 34)
	rl_url_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	MultiplayerTheme.style_line_edit(rl_url_input, 14)
	url_bar.add_child(rl_url_input)

	var apply_urls_btn := Button.new()
	apply_urls_btn.text = "Apply & Reconnect"
	apply_urls_btn.custom_minimum_size = Vector2(150, 34)
	MultiplayerTheme.style_green_button(apply_urls_btn, 14)
	apply_urls_btn.pressed.connect(_on_apply_endpoints_pressed)
	url_bar.add_child(apply_urls_btn)


func _build_navigation_ribbon(parent: VBoxContainer) -> void:
	nav_bar = PanelContainer.new()
	nav_bar.visible = false
	nav_bar.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.10, 0.16, 0.12, 0.94), Color(0.45, 0.58, 0.48, 0.7), 16, 2, 3, 2)
	)
	parent.add_child(nav_bar)

	var hbox := HBoxContainer.new()
	hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_theme_constant_override("separation", 14)
	nav_bar.add_child(hbox)

	var tab_titles := [
		"BATTLE ARENA",
		"TRAINER PROFILE",
		"LEADERBOARDS",
		"BATTLE LOG"
	]
	nav_buttons.clear()
	for i in range(tab_titles.size()):
		var b := Button.new()
		b.text = tab_titles[i]
		b.custom_minimum_size = Vector2(210, 40)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var idx := i
		b.pressed.connect(func(): _switch_main_tab(idx))
		hbox.add_child(b)
		nav_buttons.append(b)


func _switch_main_tab(index: int) -> void:
	current_tab_index = clampi(index, 0, main_pages.size() - 1)
	for i in range(main_pages.size()):
		main_pages[i].visible = (i == current_tab_index)
	for i in range(nav_buttons.size()):
		if i == current_tab_index:
			MultiplayerTheme.style_primary_battle_button(nav_buttons[i], 16)
		else:
			MultiplayerTheme.style_subtle_button(nav_buttons[i], 15)


# ==============================================================================
# 2. AUTHENTICATION SCREEN (LOGIN & REGISTRATION)
# ==============================================================================

func _build_auth_panel() -> void:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 28)
	margin.add_theme_constant_override("margin_right", 28)
	margin.add_theme_constant_override("margin_top", 18)
	margin.add_theme_constant_override("margin_bottom", 18)
	auth_panel.add_child(margin)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 16)
	margin.add_child(vbox)

	# Hero Banner inside Auth Screen
	var hero_hbox := HBoxContainer.new()
	hero_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hero_hbox.add_theme_constant_override("separation", 18)
	vbox.add_child(hero_hbox)

	hero_hbox.add_child(MultiplayerComponents.DogAvatarPortrait.new("dog_default", 72.0, true))

	var hero_text_vbox := VBoxContainer.new()
	hero_text_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hero_text_vbox.add_theme_constant_override("separation", 4)
	hero_hbox.add_child(hero_text_vbox)

	var welcome_lbl := Label.new()
	welcome_lbl.text = "WELCOME TO THE DOOBYSCOO COMPETITIVE ARENA"
	welcome_lbl.label_settings = MultiplayerTheme.make_title_settings(26, MultiplayerTheme.COL_TEXT_CREAM, 6)
	hero_text_vbox.add_child(welcome_lbl)

	var sub_welcome := Label.new()
	sub_welcome.text = "Enter ranked AI-vs-AI maze battles! Your local trained RL Dog competes on server-assigned mazes for Trophies & Leagues."
	sub_welcome.add_theme_font_size_override("font_size", 15)
	sub_welcome.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	hero_text_vbox.add_child(sub_welcome)

	hero_hbox.add_child(MultiplayerComponents.LeagueBadgeControl.new("Master", 64.0, true))

	# Two Game-Style Cards: Sign In vs Create Challenger Account
	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 24)
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(cols)

	# Left Card: Login
	var login_card := PanelContainer.new()
	login_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	login_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.11, 0.17, 0.13, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2)
	)
	cols.add_child(login_card)

	var login_box := VBoxContainer.new()
	login_box.add_theme_constant_override("separation", 12)
	login_card.add_child(login_box)

	var login_hdr := Label.new()
	login_hdr.text = "RETURNING TRAINER SIGN IN"
	login_hdr.label_settings = MultiplayerTheme.make_title_settings(20, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	login_box.add_child(login_hdr)

	var login_desc := Label.new()
	login_desc.text = "Sign in to load your Trophy rating, League rank, and match history."
	login_desc.add_theme_font_size_override("font_size", 14)
	login_desc.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	login_box.add_child(login_desc)

	login_user_input = LineEdit.new()
	login_user_input.placeholder_text = "Username or Email"
	login_user_input.custom_minimum_size = Vector2(0, 40)
	MultiplayerTheme.style_line_edit(login_user_input, 16)
	login_box.add_child(login_user_input)

	login_pass_input = LineEdit.new()
	login_pass_input.placeholder_text = "Password"
	login_pass_input.secret = true
	login_pass_input.custom_minimum_size = Vector2(0, 40)
	MultiplayerTheme.style_line_edit(login_pass_input, 16)
	login_pass_input.text_submitted.connect(func(_t): _on_login_pressed())
	login_box.add_child(login_pass_input)

	var login_spacer := Control.new()
	login_spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	login_box.add_child(login_spacer)

	var login_btn := Button.new()
	login_btn.text = "LOGIN & ENTER ARENA"
	login_btn.custom_minimum_size = Vector2(0, 50)
	MultiplayerTheme.style_primary_battle_button(login_btn, 20)
	login_btn.pressed.connect(_on_login_pressed)
	login_box.add_child(login_btn)

	# Right Card: Register
	var reg_card := PanelContainer.new()
	reg_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reg_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.11, 0.17, 0.13, 0.96), Color(0.58, 0.58, 0.80, 1.0), 16, 2)
	)
	cols.add_child(reg_card)

	var reg_box := VBoxContainer.new()
	reg_box.add_theme_constant_override("separation", 10)
	reg_card.add_child(reg_box)

	var reg_hdr := Label.new()
	reg_hdr.text = "NEW CHALLENGER REGISTRATION"
	reg_hdr.label_settings = MultiplayerTheme.make_title_settings(20, Color(0.84, 0.84, 1.0), 4)
	reg_box.add_child(reg_hdr)

	reg_user_input = LineEdit.new()
	reg_user_input.placeholder_text = "Username (3-24 chars, letters/numbers/_)"
	reg_user_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_user_input, 15)
	reg_box.add_child(reg_user_input)

	reg_display_input = LineEdit.new()
	reg_display_input.placeholder_text = "Trainer Display Name (e.g. AlphaDooby)"
	reg_display_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_display_input, 15)
	reg_box.add_child(reg_display_input)

	reg_email_input = LineEdit.new()
	reg_email_input.placeholder_text = "Email Address"
	reg_email_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_email_input, 15)
	reg_box.add_child(reg_email_input)

	reg_pass_input = LineEdit.new()
	reg_pass_input.placeholder_text = "Password (min 6 characters)"
	reg_pass_input.secret = true
	reg_pass_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_pass_input, 15)
	reg_pass_input.text_submitted.connect(func(_t): _on_register_pressed())
	reg_box.add_child(reg_pass_input)

	var reg_btn := Button.new()
	reg_btn.text = "CREATE CHALLENGER ACCOUNT"
	reg_btn.custom_minimum_size = Vector2(0, 50)
	MultiplayerTheme.style_lavender_button(reg_btn, 19)
	reg_btn.pressed.connect(_on_register_pressed)
	reg_box.add_child(reg_btn)

	# Auth Feedback Status Banner
	var fb_panel := PanelContainer.new()
	fb_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.12, 0.09, 0.94), Color(0.45, 0.56, 0.48, 0.7), 12)
	)
	vbox.add_child(fb_panel)

	auth_feedback_label = Label.new()
	auth_feedback_label.text = "Ready to connect. Sign in or register to enter the competitive arena."
	auth_feedback_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	auth_feedback_label.add_theme_font_size_override("font_size", 15)
	auth_feedback_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	fb_panel.add_child(auth_feedback_label)


# ==============================================================================
# 3. TAB 1: ARENA LOBBY & LIVE MULTIPLAYER BATTLE HUD
# ==============================================================================

func _build_arena_tab() -> void:
	arena_page = Control.new()
	arena_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	hub_tabs.add_child(arena_page)
	main_pages.append(arena_page)

	_build_lobby_view()
	_build_battle_view()


func _build_lobby_view() -> void:
	lobby_view = HBoxContainer.new()
	lobby_view.set_anchors_preset(Control.PRESET_FULL_RECT)
	lobby_view.add_theme_constant_override("separation", 18)
	arena_page.add_child(lobby_view)

	# --- LEFT COLUMN: PLAYER PROFILE & COMPETITIVE PROGRESSION CARD ---
	var left_card := PanelContainer.new()
	left_card.custom_minimum_size = Vector2(440, 0)
	left_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_card.size_flags_stretch_ratio = 0.92
	left_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	lobby_view.add_child(left_card)

	var left_vbox := VBoxContainer.new()
	left_vbox.add_theme_constant_override("separation", 12)
	left_card.add_child(left_vbox)

	# Card Header: Avatar + Name + Level Bar
	var id_row := HBoxContainer.new()
	id_row.add_theme_constant_override("separation", 14)
	left_vbox.add_child(id_row)

	lobby_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 78.0, true)
	id_row.add_child(lobby_avatar)

	var id_vbox := VBoxContainer.new()
	id_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	id_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	id_vbox.add_theme_constant_override("separation", 4)
	id_row.add_child(id_vbox)

	lobby_display_name_lbl = Label.new()
	lobby_display_name_lbl.text = "Trainer Dooby"
	lobby_display_name_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_TEXT_CREAM, 5)
	id_vbox.add_child(lobby_display_name_lbl)

	lobby_username_lbl = Label.new()
	lobby_username_lbl.text = "@trainer • Global Rank #-"
	lobby_username_lbl.add_theme_font_size_override("font_size", 14)
	lobby_username_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	id_vbox.add_child(lobby_username_lbl)

	var xp_row := HBoxContainer.new()
	xp_row.add_theme_constant_override("separation", 8)
	id_vbox.add_child(xp_row)

	lobby_level_lbl = Label.new()
	lobby_level_lbl.text = "Lv.1"
	lobby_level_lbl.add_theme_font_size_override("font_size", 14)
	lobby_level_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	xp_row.add_child(lobby_level_lbl)

	lobby_xp_bar = ProgressBar.new()
	lobby_xp_bar.custom_minimum_size = Vector2(0, 14)
	lobby_xp_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lobby_xp_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	lobby_xp_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(lobby_xp_bar, Color(0.36, 0.78, 0.96))
	xp_row.add_child(lobby_xp_bar)

	# Competitive League & Trophy Progression Panel
	var league_panel := PanelContainer.new()
	league_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.14, 0.11, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2)
	)
	left_vbox.add_child(league_panel)

	var lg_vbox := VBoxContainer.new()
	lg_vbox.add_theme_constant_override("separation", 8)
	league_panel.add_child(lg_vbox)

	var lg_top := HBoxContainer.new()
	lg_top.add_theme_constant_override("separation", 14)
	lg_vbox.add_child(lg_top)

	lobby_league_badge = MultiplayerComponents.LeagueBadgeControl.new("Beginner", 62.0, true)
	lg_top.add_child(lobby_league_badge)

	var lg_info_vbox := VBoxContainer.new()
	lg_info_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lg_info_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	lg_info_vbox.add_theme_constant_override("separation", 2)
	lg_top.add_child(lg_info_vbox)

	lobby_league_name_lbl = Label.new()
	lobby_league_name_lbl.text = "BEGINNER LEAGUE"
	lobby_league_name_lbl.label_settings = MultiplayerTheme.make_title_settings(20, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	lg_info_vbox.add_child(lobby_league_name_lbl)

	var tr_line := HBoxContainer.new()
	tr_line.add_theme_constant_override("separation", 6)
	lg_info_vbox.add_child(tr_line)

	tr_line.add_child(MultiplayerComponents.TrophyIconControl.new(24.0, 0.85))
	lobby_trophy_count_lbl = Label.new()
	lobby_trophy_count_lbl.text = "0 Trophies"
	lobby_trophy_count_lbl.add_theme_font_size_override("font_size", 19)
	lobby_trophy_count_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	tr_line.add_child(lobby_trophy_count_lbl)

	lobby_league_progress_bar = ProgressBar.new()
	lobby_league_progress_bar.custom_minimum_size = Vector2(0, 16)
	lobby_league_progress_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(lobby_league_progress_bar, MultiplayerTheme.COL_GOLD)
	lg_vbox.add_child(lobby_league_progress_bar)

	lobby_next_league_lbl = Label.new()
	lobby_next_league_lbl.text = "Next Rank: Bronze League (0 / 500 Trophies)"
	lobby_next_league_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	lobby_next_league_lbl.add_theme_font_size_override("font_size", 12)
	lobby_next_league_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	lg_vbox.add_child(lobby_next_league_lbl)

	# 6 Battle Stat Badges Grid
	var stats_grid := GridContainer.new()
	stats_grid.columns = 3
	stats_grid.add_theme_constant_override("h_separation", 8)
	stats_grid.add_theme_constant_override("v_separation", 8)
	stats_grid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left_vbox.add_child(stats_grid)

	lobby_stat_rank = MultiplayerComponents.create_stat_badge("GLOBAL RANK", "#-", MultiplayerTheme.COL_GOLD_BRIGHT)
	lobby_stat_wins = MultiplayerComponents.create_stat_badge("VICTORIES", "0", MultiplayerTheme.COL_VICTORY)
	lobby_stat_losses = MultiplayerComponents.create_stat_badge("DEFEATS", "0", Color(0.95, 0.55, 0.52))
	lobby_stat_winrate = MultiplayerComponents.create_stat_badge("WIN RATE", "0.0%", Color(0.55, 0.88, 1.0))
	lobby_stat_best = MultiplayerComponents.create_stat_badge("BEST SCORE", "N/A", Color(0.55, 0.96, 0.68))
	lobby_stat_model = MultiplayerComponents.create_stat_badge("DOG POLICY", "v1", Color(0.84, 0.78, 1.0))

	stats_grid.add_child(lobby_stat_rank)
	stats_grid.add_child(lobby_stat_wins)
	stats_grid.add_child(lobby_stat_losses)
	stats_grid.add_child(lobby_stat_winrate)
	stats_grid.add_child(lobby_stat_best)
	stats_grid.add_child(lobby_stat_model)

	# --- RIGHT COLUMN: MAIN BATTLE ARENA STAGE ---
	var right_stage := PanelContainer.new()
	right_stage.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_stage.size_flags_stretch_ratio = 1.15
	right_stage.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.11, 0.18, 0.14, 0.96), MultiplayerTheme.COL_GOLD, 22, 3, 10, 6)
	)
	lobby_view.add_child(right_stage)

	var stage_vbox := VBoxContainer.new()
	stage_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	stage_vbox.add_theme_constant_override("separation", 12)
	right_stage.add_child(stage_vbox)

	var arena_badge_row := HBoxContainer.new()
	arena_badge_row.alignment = BoxContainer.ALIGNMENT_CENTER
	arena_badge_row.add_theme_constant_override("separation", 18)
	stage_vbox.add_child(arena_badge_row)

	arena_badge_row.add_child(MultiplayerComponents.TrophyIconControl.new(44.0, 1.45))

	var stage_title_vbox := VBoxContainer.new()
	stage_title_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	arena_badge_row.add_child(stage_title_vbox)

	var stage_title := Label.new()
	stage_title.text = "RANKED AI MAZE BATTLE"
	stage_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stage_title.label_settings = MultiplayerTheme.make_title_settings(30, MultiplayerTheme.COL_TEXT_CREAM, 7)
	stage_title_vbox.add_child(stage_title)

	var stage_sub := Label.new()
	stage_sub.text = "1v1 Authoritative Server Match • Identical Maze Seed • Lowest Official Score Wins"
	stage_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stage_sub.add_theme_font_size_override("font_size", 14)
	stage_sub.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	stage_title_vbox.add_child(stage_sub)

	arena_badge_row.add_child(MultiplayerComponents.TrophyIconControl.new(44.0, 1.45))

	# Rules & Rewards Pill Cards
	var rules_row := HBoxContainer.new()
	rules_row.alignment = BoxContainer.ALIGNMENT_CENTER
	rules_row.add_theme_constant_override("separation", 10)
	stage_vbox.add_child(rules_row)

	var r1 := MultiplayerComponents.create_stat_badge("VICTORY REWARD", "+25 Trophies", MultiplayerTheme.COL_VICTORY)
	var r2 := MultiplayerComponents.create_stat_badge("BONE BONUS", "-5 Score / Bone", MultiplayerTheme.COL_GOLD_BRIGHT)
	var r3 := MultiplayerComponents.create_stat_badge("EXECUTION", "100% Local RL Dog", Color(0.65, 0.88, 1.0))
	rules_row.add_child(r1)
	rules_row.add_child(r2)
	rules_row.add_child(r3)

	# Local RL Readiness Banner
	var rl_ready_card := PanelContainer.new()
	rl_ready_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.94), Color(0.45, 0.62, 0.48, 0.8), 14)
	)
	stage_vbox.add_child(rl_ready_card)

	match_info_label = Label.new()
	match_info_label.text = "Your trained AI Dog solves the server's competition maze locally on your machine, then submits its action trace for anti-cheat verification."
	match_info_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	match_info_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	match_info_label.add_theme_font_size_override("font_size", 14)
	match_info_label.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	rl_ready_card.add_child(match_info_label)

	# Primary Exciting PLAY MULTIPLAYER Button
	var play_btn_holder := MarginContainer.new()
	play_btn_holder.add_theme_constant_override("margin_left", 36)
	play_btn_holder.add_theme_constant_override("margin_right", 36)
	play_btn_holder.add_theme_constant_override("margin_top", 4)
	play_btn_holder.add_theme_constant_override("margin_bottom", 4)
	stage_vbox.add_child(play_btn_holder)

	find_match_btn = Button.new()
	find_match_btn.text = "PLAY MULTIPLAYER BATTLE"
	find_match_btn.custom_minimum_size = Vector2(0, 74)
	MultiplayerTheme.style_primary_battle_button(find_match_btn, 28)
	find_match_btn.pressed.connect(_on_find_match_pressed)
	play_btn_holder.add_child(find_match_btn)

	# Matchmaking Status Banner
	var status_box := PanelContainer.new()
	status_box.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.07, 0.11, 0.08, 0.92), MultiplayerTheme.COL_GOLD_BORDER, 14)
	)
	stage_vbox.add_child(status_box)

	var st_vbox := VBoxContainer.new()
	st_vbox.add_theme_constant_override("separation", 4)
	status_box.add_child(st_vbox)

	match_state_label = Label.new()
	match_state_label.text = "ARENA READY — Press Play Multiplayer Battle to find a challenger!"
	match_state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	match_state_label.add_theme_font_size_override("font_size", 16)
	match_state_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	st_vbox.add_child(match_state_label)

	lobby_agent_ready_lbl = Label.new()
	lobby_agent_ready_lbl.text = "Checking Local Python RL Dog Agent..."
	lobby_agent_ready_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lobby_agent_ready_lbl.add_theme_font_size_override("font_size", 13)
	lobby_agent_ready_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	st_vbox.add_child(lobby_agent_ready_lbl)


func _build_battle_view() -> void:
	battle_view = HBoxContainer.new()
	battle_view.set_anchors_preset(Control.PRESET_FULL_RECT)
	battle_view.add_theme_constant_override("separation", 16)
	battle_view.visible = false
	arena_page.add_child(battle_view)

	# Left: The 10x10 Competition Maze Board
	var board_frame := PanelContainer.new()
	board_frame.custom_minimum_size = Vector2(360, 360)
	board_frame.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board_frame.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board_frame.size_flags_stretch_ratio = 1.25
	board_frame.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.10, 0.16, 0.12, 0.96), MultiplayerTheme.COL_GOLD, 18, 3, 8, 4)
	)
	battle_view.add_child(board_frame)

	board = GameplayBoard.new()
	board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board_frame.add_child(board)

	# Right: Competitive Battle HUD Side Panel
	var hud_panel := PanelContainer.new()
	hud_panel.custom_minimum_size = Vector2(400, 0)
	hud_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hud_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hud_panel.size_flags_stretch_ratio = 1.0
	hud_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 18, 3, 8, 5)
	)
	battle_view.add_child(hud_panel)

	var hud_vbox := VBoxContainer.new()
	hud_vbox.add_theme_constant_override("separation", 10)
	hud_panel.add_child(hud_vbox)

	# Battle Header: Live Match Banner + Timer
	var top_hud_row := HBoxContainer.new()
	top_hud_row.add_theme_constant_override("separation", 10)
	hud_vbox.add_child(top_hud_row)

	var live_tag := Label.new()
	live_tag.text = "LIVE RANKED BATTLE"
	live_tag.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	live_tag.label_settings = MultiplayerTheme.make_title_settings(20, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_hud_row.add_child(live_tag)

	var timer_pill := PanelContainer.new()
	timer_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.12, 0.09, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 14)
	)
	top_hud_row.add_child(timer_pill)

	battle_timer_lbl = Label.new()
	battle_timer_lbl.text = "TIME: 10:00"
	battle_timer_lbl.add_theme_font_size_override("font_size", 15)
	battle_timer_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	timer_pill.add_child(battle_timer_lbl)

	# Versus Duel Bar (You vs Opponent)
	var duel_card := PanelContainer.new()
	duel_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.14, 0.11, 0.96), Color(0.55, 0.68, 0.56, 0.85), 14, 2)
	)
	hud_vbox.add_child(duel_card)

	var duel_hbox := HBoxContainer.new()
	duel_hbox.add_theme_constant_override("separation", 10)
	duel_card.add_child(duel_hbox)

	# Your mini-box
	var you_box := HBoxContainer.new()
	you_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	you_box.add_theme_constant_override("separation", 8)
	duel_hbox.add_child(you_box)

	battle_you_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 44.0, true)
	you_box.add_child(battle_you_avatar)

	var you_txt := VBoxContainer.new()
	you_txt.alignment = BoxContainer.ALIGNMENT_CENTER
	you_box.add_child(you_txt)

	battle_you_name_lbl = Label.new()
	battle_you_name_lbl.text = "You"
	battle_you_name_lbl.add_theme_font_size_override("font_size", 15)
	battle_you_name_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	you_txt.add_child(battle_you_name_lbl)

	battle_you_trophies_lbl = Label.new()
	battle_you_trophies_lbl.text = "0 Trophies"
	battle_you_trophies_lbl.add_theme_font_size_override("font_size", 12)
	battle_you_trophies_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	you_txt.add_child(battle_you_trophies_lbl)

	var vs_mid := Label.new()
	vs_mid.text = "VS"
	vs_mid.label_settings = MultiplayerTheme.make_title_settings(20, Color(0.96, 0.36, 0.30), 5)
	duel_hbox.add_child(vs_mid)

	# Opponent mini-box
	var opp_box := HBoxContainer.new()
	opp_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	opp_box.alignment = BoxContainer.ALIGNMENT_END
	opp_box.add_theme_constant_override("separation", 8)
	duel_hbox.add_child(opp_box)

	var opp_txt := VBoxContainer.new()
	opp_txt.alignment = BoxContainer.ALIGNMENT_CENTER
	opp_box.add_child(opp_txt)

	battle_opp_name_lbl = Label.new()
	battle_opp_name_lbl.text = "Challenger"
	battle_opp_name_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	battle_opp_name_lbl.add_theme_font_size_override("font_size", 15)
	battle_opp_name_lbl.add_theme_color_override("font_color", Color(1.0, 0.72, 0.68))
	opp_txt.add_child(battle_opp_name_lbl)

	battle_opp_trophies_lbl = Label.new()
	battle_opp_trophies_lbl.text = "0 Trophies"
	battle_opp_trophies_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	battle_opp_trophies_lbl.add_theme_font_size_override("font_size", 12)
	battle_opp_trophies_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	opp_txt.add_child(battle_opp_trophies_lbl)

	battle_opp_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_husky", 44.0, true)
	opp_box.add_child(battle_opp_avatar)

	# Opponent Live Telemetry Pill
	var opp_status_card := PanelContainer.new()
	opp_status_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.17, 0.13, 0.14, 0.94), Color(0.84, 0.44, 0.40, 0.8), 12)
	)
	hud_vbox.add_child(opp_status_card)

	battle_opp_status_pill = Label.new()
	battle_opp_status_pill.text = "Opponent Status: Solving Maze Live..."
	battle_opp_status_pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	battle_opp_status_pill.add_theme_font_size_override("font_size", 14)
	battle_opp_status_pill.add_theme_color_override("font_color", Color(1.0, 0.84, 0.80))
	opp_status_card.add_child(battle_opp_status_pill)

	# Your Live Scoreboard Grid (Official Score, Steps, Bones)
	var live_score_row := HBoxContainer.new()
	live_score_row.add_theme_constant_override("separation", 8)
	hud_vbox.add_child(live_score_row)

	var sc_card := MultiplayerComponents.create_stat_badge("OFFICIAL SCORE (LOWER WINS)", "0", Color(0.45, 0.98, 0.62))
	battle_score_val_lbl = sc_card.get_node("VBoxContainer/ValueLabel") if sc_card.has_node("VBoxContainer/ValueLabel") else sc_card.get_child(0).get_child(1)
	live_score_row.add_child(sc_card)

	var st_card := MultiplayerComponents.create_stat_badge("STEPS TAKEN", "0 / 300", MultiplayerTheme.COL_TEXT_CREAM)
	battle_steps_val_lbl = st_card.get_child(0).get_child(1)
	live_score_row.add_child(st_card)

	var bn_card := MultiplayerComponents.create_stat_badge("BONES (-5 EACH)", "0 / 5", MultiplayerTheme.COL_GOLD_BRIGHT)
	battle_bones_val_lbl = bn_card.get_child(0).get_child(1)
	live_score_row.add_child(bn_card)

	# Progress Bars for Bones & Step Budget
	var bars_vbox := VBoxContainer.new()
	bars_vbox.add_theme_constant_override("separation", 6)
	hud_vbox.add_child(bars_vbox)

	var bone_bar_row := HBoxContainer.new()
	bone_bar_row.add_theme_constant_override("separation", 8)
	bars_vbox.add_child(bone_bar_row)
	bone_bar_row.add_child(MultiplayerComponents.BoneIconControl.new(22.0, 0.85))
	battle_bones_bar = ProgressBar.new()
	battle_bones_bar.max_value = 5
	battle_bones_bar.value = 0
	battle_bones_bar.custom_minimum_size = Vector2(0, 14)
	battle_bones_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	battle_bones_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	battle_bones_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(battle_bones_bar, MultiplayerTheme.COL_GOLD)
	bone_bar_row.add_child(battle_bones_bar)

	battle_steps_bar = ProgressBar.new()
	battle_steps_bar.max_value = 300
	battle_steps_bar.value = 0
	battle_steps_bar.custom_minimum_size = Vector2(0, 10)
	battle_steps_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(battle_steps_bar, Color(0.38, 0.82, 0.56))
	bars_vbox.add_child(battle_steps_bar)

	# Live Step Log & Battle Commentary Feed
	arena_step_log_label = Label.new()
	arena_step_log_label.text = "Steps: 0 | Bones: 0/5 | Official Score: 0"
	arena_step_log_label.add_theme_font_size_override("font_size", 14)
	arena_step_log_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	hud_vbox.add_child(arena_step_log_label)

	var feed_panel := PanelContainer.new()
	feed_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	feed_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.07, 0.11, 0.08, 0.94), Color(0.38, 0.48, 0.40, 0.7), 12, 2)
	)
	hud_vbox.add_child(feed_panel)

	arena_result_summary_label = RichTextLabel.new()
	arena_result_summary_label.bbcode_enabled = true
	arena_result_summary_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	arena_result_summary_label.text = "Waiting for match start..."
	feed_panel.add_child(arena_result_summary_label)

	# Bottom Actions in Battle HUD
	var btm_row := HBoxContainer.new()
	btm_row.add_theme_constant_override("separation", 10)
	hud_vbox.add_child(btm_row)

	learn_after_match_btn = Button.new()
	learn_after_match_btn.text = "Train Dog on This Maze"
	learn_after_match_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	learn_after_match_btn.custom_minimum_size = Vector2(0, 42)
	learn_after_match_btn.disabled = true
	MultiplayerTheme.style_lavender_button(learn_after_match_btn, 15)
	learn_after_match_btn.pressed.connect(_on_learn_after_match_pressed)
	btm_row.add_child(learn_after_match_btn)

	battle_return_lobby_btn = Button.new()
	battle_return_lobby_btn.text = "Back to Lobby"
	battle_return_lobby_btn.custom_minimum_size = Vector2(140, 42)
	MultiplayerTheme.style_subtle_button(battle_return_lobby_btn, 15)
	battle_return_lobby_btn.pressed.connect(_on_back_to_lobby_pressed)
	btm_row.add_child(battle_return_lobby_btn)


# ==============================================================================
# 4. MATCHMAKING OVERLAY, OPPONENT FOUND (VS) SCREEN, AND BATTLE RESULTS OVERLAY
# ==============================================================================

func _build_matchmaking_overlay() -> void:
	matchmaking_overlay = PanelContainer.new()
	matchmaking_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	matchmaking_overlay.visible = false
	matchmaking_overlay.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.05, 0.09, 0.07, 0.94), MultiplayerTheme.COL_GOLD, 22, 3, 12, 6)
	)
	hub_tabs.add_child(matchmaking_overlay)

	var center := CenterContainer.new()
	matchmaking_overlay.add_child(center)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(560, 460)
	card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 24, 3, 10, 6)
	)
	center.add_child(card)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 12)
	card.add_child(vbox)

	mm_headline_lbl = Label.new()
	mm_headline_lbl.text = "FINDING OPPONENT..."
	mm_headline_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_headline_lbl.label_settings = MultiplayerTheme.make_title_settings(28, MultiplayerTheme.COL_GOLD_BRIGHT, 6)
	vbox.add_child(mm_headline_lbl)

	mm_substatus_lbl = Label.new()
	mm_substatus_lbl.text = "Scanning the DoobyScoo Arena for worthy challengers..."
	mm_substatus_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_substatus_lbl.add_theme_font_size_override("font_size", 15)
	mm_substatus_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	vbox.add_child(mm_substatus_lbl)

	var radar_center := CenterContainer.new()
	vbox.add_child(radar_center)
	mm_radar = MultiplayerComponents.MatchmakingRadarControl.new()
	radar_center.add_child(mm_radar)

	# Player Info + Search Elapsed Pill
	var info_pill := PanelContainer.new()
	info_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.12, 0.09, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 16)
	)
	vbox.add_child(info_pill)

	var info_vbox := VBoxContainer.new()
	info_vbox.add_theme_constant_override("separation", 4)
	info_pill.add_child(info_vbox)

	mm_player_summary_lbl = Label.new()
	mm_player_summary_lbl.text = "Trainer • 0 Trophies • Beginner League"
	mm_player_summary_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_player_summary_lbl.add_theme_font_size_override("font_size", 16)
	mm_player_summary_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	info_vbox.add_child(mm_player_summary_lbl)

	var timer_row := HBoxContainer.new()
	timer_row.alignment = BoxContainer.ALIGNMENT_CENTER
	timer_row.add_theme_constant_override("separation", 18)
	info_vbox.add_child(timer_row)

	mm_timer_lbl = Label.new()
	mm_timer_lbl.text = "Search Time: 00:00"
	mm_timer_lbl.add_theme_font_size_override("font_size", 14)
	mm_timer_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	timer_row.add_child(mm_timer_lbl)

	mm_trophy_range_lbl = Label.new()
	mm_trophy_range_lbl.text = "Trophy Window: ±200"
	mm_trophy_range_lbl.add_theme_font_size_override("font_size", 14)
	mm_trophy_range_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	timer_row.add_child(mm_trophy_range_lbl)

	cancel_match_btn = Button.new()
	cancel_match_btn.text = "CANCEL MATCHMAKING"
	cancel_match_btn.custom_minimum_size = Vector2(240, 48)
	cancel_match_btn.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	cancel_match_btn.disabled = true
	MultiplayerTheme.style_danger_button(cancel_match_btn, 18)
	cancel_match_btn.pressed.connect(_on_cancel_match_pressed)
	vbox.add_child(cancel_match_btn)


func _build_versus_overlay() -> void:
	versus_overlay = PanelContainer.new()
	versus_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	versus_overlay.visible = false
	versus_overlay.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.05, 0.08, 0.06, 0.96), MultiplayerTheme.COL_GOLD, 22, 4, 14, 6)
	)
	hub_tabs.add_child(versus_overlay)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 18)
	versus_overlay.add_child(vbox)

	vs_status_banner_lbl = Label.new()
	vs_status_banner_lbl.text = "OPPONENT FOUND! PREPARING ARENA..."
	vs_status_banner_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_status_banner_lbl.label_settings = MultiplayerTheme.make_title_settings(32, MultiplayerTheme.COL_GOLD_BRIGHT, 7)
	vbox.add_child(vs_status_banner_lbl)

	var cards_row := HBoxContainer.new()
	cards_row.alignment = BoxContainer.ALIGNMENT_CENTER
	cards_row.add_theme_constant_override("separation", 28)
	vbox.add_child(cards_row)

	vs_left_slot = VBoxContainer.new()
	vs_left_slot.custom_minimum_size = Vector2(310, 260)
	cards_row.add_child(vs_left_slot)

	var vs_center_col := VBoxContainer.new()
	vs_center_col.alignment = BoxContainer.ALIGNMENT_CENTER
	cards_row.add_child(vs_center_col)

	var emblem_holder := CenterContainer.new()
	vs_center_col.add_child(emblem_holder)
	emblem_holder.add_child(MultiplayerComponents.VsEmblemControl.new())

	var vs_txt := Label.new()
	vs_txt.text = "VS"
	vs_txt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_txt.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_TEXT_CREAM, 8)
	emblem_holder.add_child(vs_txt)

	vs_right_slot = VBoxContainer.new()
	vs_right_slot.custom_minimum_size = Vector2(310, 260)
	cards_row.add_child(vs_right_slot)

	vs_map_badge_lbl = Label.new()
	vs_map_badge_lbl.text = "Syncing Server Maze Seed & Launching Local RL Agent..."
	vs_map_badge_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_map_badge_lbl.add_theme_font_size_override("font_size", 16)
	vs_map_badge_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	vbox.add_child(vs_map_badge_lbl)


func _build_results_overlay() -> void:
	results_overlay = PanelContainer.new()
	results_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	results_overlay.visible = false
	results_overlay.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.05, 0.09, 0.07, 0.94), MultiplayerTheme.COL_GOLD, 22, 3, 12, 6)
	)
	hub_tabs.add_child(results_overlay)

	var center := CenterContainer.new()
	results_overlay.add_child(center)

	var modal := PanelContainer.new()
	modal.custom_minimum_size = Vector2(760, 470)
	modal.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 24, 3, 12, 6)
	)
	center.add_child(modal)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 10)
	modal.add_child(vbox)

	var banner_center := CenterContainer.new()
	vbox.add_child(banner_center)
	res_banner_icon = MultiplayerComponents.ResultBannerControl.new()
	banner_center.add_child(res_banner_icon)

	res_title_lbl = Label.new()
	res_title_lbl.text = "VICTORY!"
	res_title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_VICTORY, 7)
	vbox.add_child(res_title_lbl)

	res_subtitle_lbl = Label.new()
	res_subtitle_lbl.text = "Your Dog Solved the Maze with a Superior Official Score!"
	res_subtitle_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	res_subtitle_lbl.add_theme_font_size_override("font_size", 15)
	res_subtitle_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	vbox.add_child(res_subtitle_lbl)

	# Progression & Rewards Bar (Trophy Delta, XP, Duration)
	var rewards_row := HBoxContainer.new()
	rewards_row.alignment = BoxContainer.ALIGNMENT_CENTER
	rewards_row.add_theme_constant_override("separation", 14)
	vbox.add_child(rewards_row)

	var tr_pill := PanelContainer.new()
	tr_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.96), MultiplayerTheme.COL_GOLD, 16)
	)
	rewards_row.add_child(tr_pill)

	var tr_p_hbox := HBoxContainer.new()
	tr_p_hbox.add_theme_constant_override("separation", 6)
	tr_pill.add_child(tr_p_hbox)
	tr_p_hbox.add_child(MultiplayerComponents.TrophyIconControl.new(22.0, 0.8))
	res_trophy_delta_lbl = Label.new()
	res_trophy_delta_lbl.text = "+25 Trophies"
	res_trophy_delta_lbl.add_theme_font_size_override("font_size", 17)
	res_trophy_delta_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	tr_p_hbox.add_child(res_trophy_delta_lbl)

	var xp_pill := PanelContainer.new()
	xp_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.96), Color(0.45, 0.78, 0.96), 16)
	)
	rewards_row.add_child(xp_pill)

	res_xp_awarded_lbl = Label.new()
	res_xp_awarded_lbl.text = "+75 XP Earned"
	res_xp_awarded_lbl.add_theme_font_size_override("font_size", 16)
	res_xp_awarded_lbl.add_theme_color_override("font_color", Color(0.65, 0.90, 1.0))
	xp_pill.add_child(res_xp_awarded_lbl)

	var dur_pill := PanelContainer.new()
	dur_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.96), Color(0.48, 0.58, 0.50), 16)
	)
	rewards_row.add_child(dur_pill)

	res_duration_lbl = Label.new()
	res_duration_lbl.text = "Map: Verified"
	res_duration_lbl.add_theme_font_size_override("font_size", 14)
	res_duration_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	dur_pill.add_child(res_duration_lbl)

	# Side-by-Side Score Comparison Cards
	var compare_row := HBoxContainer.new()
	compare_row.add_theme_constant_override("separation", 18)
	vbox.add_child(compare_row)

	var you_panel := PanelContainer.new()
	you_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	you_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.11, 0.18, 0.14, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2)
	)
	compare_row.add_child(you_panel)
	res_you_card_box = VBoxContainer.new()
	res_you_card_box.add_theme_constant_override("separation", 4)
	you_panel.add_child(res_you_card_box)

	var opp_panel := PanelContainer.new()
	opp_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	opp_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.18, 0.13, 0.14, 0.96), Color(0.86, 0.46, 0.42), 16, 2)
	)
	compare_row.add_child(opp_panel)
	res_opp_card_box = VBoxContainer.new()
	res_opp_card_box.add_theme_constant_override("separation", 4)
	opp_panel.add_child(res_opp_card_box)

	res_train_feedback_lbl = Label.new()
	res_train_feedback_lbl.text = ""
	res_train_feedback_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	res_train_feedback_lbl.add_theme_font_size_override("font_size", 13)
	res_train_feedback_lbl.add_theme_color_override("font_color", Color(0.65, 0.96, 0.74))
	vbox.add_child(res_train_feedback_lbl)

	# Action Buttons Row
	var act_row := HBoxContainer.new()
	act_row.alignment = BoxContainer.ALIGNMENT_CENTER
	act_row.add_theme_constant_override("separation", 14)
	vbox.add_child(act_row)

	res_play_again_btn = Button.new()
	res_play_again_btn.text = "PLAY AGAIN"
	res_play_again_btn.custom_minimum_size = Vector2(200, 48)
	MultiplayerTheme.style_primary_battle_button(res_play_again_btn, 20)
	res_play_again_btn.pressed.connect(_on_play_again_from_results)
	act_row.add_child(res_play_again_btn)

	res_train_dog_btn = Button.new()
	res_train_dog_btn.text = "UPDATE RL POLICY ON MATCH"
	res_train_dog_btn.custom_minimum_size = Vector2(240, 48)
	MultiplayerTheme.style_lavender_button(res_train_dog_btn, 16)
	res_train_dog_btn.pressed.connect(_on_learn_after_match_pressed)
	act_row.add_child(res_train_dog_btn)

	res_back_lobby_btn = Button.new()
	res_back_lobby_btn.text = "ARENA LOBBY"
	res_back_lobby_btn.custom_minimum_size = Vector2(150, 48)
	MultiplayerTheme.style_subtle_button(res_back_lobby_btn, 16)
	res_back_lobby_btn.pressed.connect(_on_back_to_lobby_pressed)
	act_row.add_child(res_back_lobby_btn)


# ==============================================================================
# 5. TAB 2: TRAINER PROFILE & COMPETITIVE PROGRESSION
# ==============================================================================

func _build_profile_tab() -> void:
	var prof_page := HBoxContainer.new()
	prof_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	prof_page.add_theme_constant_override("separation", 18)
	prof_page.visible = false
	hub_tabs.add_child(prof_page)
	main_pages.append(prof_page)

	# Left Column: Showcase Card & Customization
	var left_panel := PanelContainer.new()
	left_panel.custom_minimum_size = Vector2(420, 0)
	left_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_panel.size_flags_stretch_ratio = 0.85
	left_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	prof_page.add_child(left_panel)

	var l_vbox := VBoxContainer.new()
	l_vbox.add_theme_constant_override("separation", 12)
	left_panel.add_child(l_vbox)

	var showcase_row := HBoxContainer.new()
	showcase_row.alignment = BoxContainer.ALIGNMENT_CENTER
	showcase_row.add_theme_constant_override("separation", 16)
	l_vbox.add_child(showcase_row)

	prof_avatar_large = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 92.0, true)
	showcase_row.add_child(prof_avatar_large)

	var name_col := VBoxContainer.new()
	name_col.alignment = BoxContainer.ALIGNMENT_CENTER
	name_col.add_theme_constant_override("separation", 4)
	showcase_row.add_child(name_col)

	prof_title_name_lbl = Label.new()
	prof_title_name_lbl.text = "Trainer"
	prof_title_name_lbl.label_settings = MultiplayerTheme.make_title_settings(26, MultiplayerTheme.COL_TEXT_CREAM, 6)
	name_col.add_child(prof_title_name_lbl)

	prof_handle_lbl = Label.new()
	prof_handle_lbl.text = "@username"
	prof_handle_lbl.add_theme_font_size_override("font_size", 14)
	prof_handle_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	name_col.add_child(prof_handle_lbl)

	prof_level_badge_lbl = Label.new()
	prof_level_badge_lbl.text = "Level 1 • 0 XP"
	prof_level_badge_lbl.add_theme_font_size_override("font_size", 15)
	prof_level_badge_lbl.add_theme_color_override("font_color", Color(0.58, 0.88, 1.0))
	name_col.add_child(prof_level_badge_lbl)

	prof_xp_bar = ProgressBar.new()
	prof_xp_bar.custom_minimum_size = Vector2(0, 14)
	prof_xp_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(prof_xp_bar, Color(0.36, 0.78, 0.96))
	l_vbox.add_child(prof_xp_bar)

	# Edit Profile Card
	var edit_card := PanelContainer.new()
	edit_card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	edit_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.14, 0.11, 0.95), Color(0.45, 0.58, 0.48, 0.8), 16, 2)
	)
	l_vbox.add_child(edit_card)

	var ed_vbox := VBoxContainer.new()
	ed_vbox.add_theme_constant_override("separation", 10)
	edit_card.add_child(ed_vbox)

	var ed_hdr := Label.new()
	ed_hdr.text = "CUSTOMIZE TRAINER IDENTITY"
	ed_hdr.label_settings = MultiplayerTheme.make_title_settings(18, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	ed_vbox.add_child(ed_hdr)

	var dn_lbl := Label.new()
	dn_lbl.text = "Display Name:"
	dn_lbl.add_theme_font_size_override("font_size", 14)
	dn_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	ed_vbox.add_child(dn_lbl)

	edit_display_input = LineEdit.new()
	edit_display_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(edit_display_input, 16)
	ed_vbox.add_child(edit_display_input)

	var av_lbl := Label.new()
	av_lbl.text = "Select Dog Avatar Portrait:"
	av_lbl.add_theme_font_size_override("font_size", 14)
	av_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	ed_vbox.add_child(av_lbl)

	# Hidden OptionButton preserved for signal/state compatibility + Visual Avatar Selector Grid
	edit_avatar_select = OptionButton.new()
	edit_avatar_select.visible = false
	var avatar_ids := ["dog_default", "dog_golden", "dog_husky", "dog_cyber"]
	var avatar_labels := ["Classic Dooby", "Golden Champ", "Arctic Husky", "Cyber Hound"]
	for i in range(avatar_ids.size()):
		edit_avatar_select.add_item(avatar_ids[i], i)
	ed_vbox.add_child(edit_avatar_select)

	var av_grid := HBoxContainer.new()
	av_grid.add_theme_constant_override("separation", 8)
	ed_vbox.add_child(av_grid)

	avatar_choice_buttons.clear()
	for i in range(avatar_ids.size()):
		var av_btn := Button.new()
		av_btn.custom_minimum_size = Vector2(80, 76)
		av_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var idx := i
		var av_id: String = avatar_ids[i]
		MultiplayerTheme.style_subtle_button(av_btn, 11)
		av_btn.pressed.connect(func(): _select_avatar_option(idx))

		var av_vbox := VBoxContainer.new()
		av_vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
		av_vbox.alignment = BoxContainer.ALIGNMENT_CENTER
		av_vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
		av_btn.add_child(av_vbox)

		var p_center := CenterContainer.new()
		p_center.mouse_filter = Control.MOUSE_FILTER_IGNORE
		av_vbox.add_child(p_center)
		p_center.add_child(MultiplayerComponents.DogAvatarPortrait.new(av_id, 42.0, false))

		var c_lbl := Label.new()
		c_lbl.text = avatar_labels[i]
		c_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		c_lbl.add_theme_font_size_override("font_size", 11)
		c_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
		c_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
		av_vbox.add_child(c_lbl)

		av_grid.add_child(av_btn)
		avatar_choice_buttons.append(av_btn)

	var btn_row := HBoxContainer.new()
	btn_row.add_theme_constant_override("separation", 10)
	ed_vbox.add_child(btn_row)

	var save_prof_btn := Button.new()
	save_prof_btn.text = "SAVE PROFILE"
	save_prof_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	save_prof_btn.custom_minimum_size = Vector2(0, 42)
	MultiplayerTheme.style_green_button(save_prof_btn, 16)
	save_prof_btn.pressed.connect(_on_save_profile_pressed)
	btn_row.add_child(save_prof_btn)

	var ref_prof_btn := Button.new()
	ref_prof_btn.text = "Refresh"
	ref_prof_btn.custom_minimum_size = Vector2(100, 42)
	MultiplayerTheme.style_subtle_button(ref_prof_btn, 15)
	ref_prof_btn.pressed.connect(_refresh_all_player_data)
	btn_row.add_child(ref_prof_btn)

	prof_save_feedback_lbl = Label.new()
	prof_save_feedback_lbl.text = ""
	prof_save_feedback_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prof_save_feedback_lbl.add_theme_font_size_override("font_size", 13)
	prof_save_feedback_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_VICTORY)
	ed_vbox.add_child(prof_save_feedback_lbl)

	# Right Column: Competitive Career & League Road
	var right_panel := PanelContainer.new()
	right_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_panel.size_flags_stretch_ratio = 1.15
	right_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	prof_page.add_child(right_panel)

	var r_vbox := VBoxContainer.new()
	r_vbox.add_theme_constant_override("separation", 12)
	right_panel.add_child(r_vbox)

	# League Banner Card
	var lg_banner := PanelContainer.new()
	lg_banner.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.14, 0.11, 0.96), MultiplayerTheme.COL_GOLD, 16, 2)
	)
	r_vbox.add_child(lg_banner)

	var lg_hbox := HBoxContainer.new()
	lg_hbox.add_theme_constant_override("separation", 16)
	lg_banner.add_child(lg_hbox)

	prof_league_shield_large = MultiplayerComponents.LeagueBadgeControl.new("Beginner", 74.0, true)
	lg_hbox.add_child(prof_league_shield_large)

	var lg_col := VBoxContainer.new()
	lg_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lg_col.alignment = BoxContainer.ALIGNMENT_CENTER
	lg_col.add_theme_constant_override("separation", 6)
	lg_hbox.add_child(lg_col)

	prof_league_tier_lbl = Label.new()
	prof_league_tier_lbl.text = "BEGINNER LEAGUE"
	prof_league_tier_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	lg_col.add_child(prof_league_tier_lbl)

	prof_trophy_big_lbl = Label.new()
	prof_trophy_big_lbl.text = "0 Trophies • Next Tier at 500"
	prof_trophy_big_lbl.add_theme_font_size_override("font_size", 15)
	prof_trophy_big_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	lg_col.add_child(prof_trophy_big_lbl)

	prof_league_bar = ProgressBar.new()
	prof_league_bar.custom_minimum_size = Vector2(0, 16)
	prof_league_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(prof_league_bar, MultiplayerTheme.COL_GOLD)
	lg_col.add_child(prof_league_bar)

	# Visual League Road Strip (All 7 Leagues)
	var road_row := HBoxContainer.new()
	road_row.alignment = BoxContainer.ALIGNMENT_CENTER
	road_row.add_theme_constant_override("separation", 6)
	r_vbox.add_child(road_row)

	for tier in MultiplayerTheme.LEAGUE_TIERS:
		var t_box := VBoxContainer.new()
		t_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		t_box.alignment = BoxContainer.ALIGNMENT_CENTER
		t_box.add_theme_constant_override("separation", 2)
		road_row.add_child(t_box)

		var b_center := CenterContainer.new()
		t_box.add_child(b_center)
		b_center.add_child(MultiplayerComponents.LeagueBadgeControl.new(str(tier["name"]), 32.0, false))

		var t_name := Label.new()
		t_name.text = str(tier["name"])
		t_name.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		t_name.add_theme_font_size_override("font_size", 11)
		t_name.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
		t_box.add_child(t_name)

		var t_min := Label.new()
		t_min.text = "%d+" % int(tier["min"])
		t_min.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		t_min.add_theme_font_size_override("font_size", 10)
		t_min.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD)
		t_box.add_child(t_min)

	# Career Stats Summary Rich Panel (Also preserves `profile_details_text`)
	var career_card := PanelContainer.new()
	career_card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	career_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.08, 0.13, 0.10, 0.94), Color(0.42, 0.54, 0.44, 0.75), 14, 2)
	)
	r_vbox.add_child(career_card)

	profile_details_text = RichTextLabel.new()
	profile_details_text.bbcode_enabled = true
	profile_details_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	career_card.add_child(profile_details_text)


func _select_avatar_option(index: int) -> void:
	edit_avatar_select.selected = index
	var avatar_id := edit_avatar_select.get_item_text(index)
	prof_avatar_large.avatar_id = avatar_id
	for i in range(avatar_choice_buttons.size()):
		if i == index:
			MultiplayerTheme.style_primary_battle_button(avatar_choice_buttons[i], 11)
		else:
			MultiplayerTheme.style_subtle_button(avatar_choice_buttons[i], 11)


# ==============================================================================
# 6. TAB 3: LEADERBOARDS & LEAGUES (WITH TOP-3 PODIUM & PLAYER CARDS)
# ==============================================================================

func _build_leaderboards_tab() -> void:
	var lb_page := PanelContainer.new()
	lb_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	lb_page.visible = false
	lb_page.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	hub_tabs.add_child(lb_page)
	main_pages.append(lb_page)

	var lb_vbox := VBoxContainer.new()
	lb_vbox.add_theme_constant_override("separation", 10)
	lb_page.add_child(lb_vbox)

	# Filter & League Controls Bar
	var filter_row := HBoxContainer.new()
	filter_row.add_theme_constant_override("separation", 10)
	lb_vbox.add_child(filter_row)

	var global_btn := Button.new()
	global_btn.text = "Global Top Rankings"
	global_btn.custom_minimum_size = Vector2(180, 38)
	MultiplayerTheme.style_primary_battle_button(global_btn, 15)
	global_btn.pressed.connect(func():
		lb_current_offset = 0
		_on_load_global_leaderboard()
	)
	filter_row.add_child(global_btn)

	leaderboard_league_select = OptionButton.new()
	leaderboard_league_select.custom_minimum_size = Vector2(140, 38)
	for lg in ["Beginner", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]:
		leaderboard_league_select.add_item(lg)
	filter_row.add_child(leaderboard_league_select)

	var league_btn := Button.new()
	league_btn.text = "View League Standings"
	league_btn.custom_minimum_size = Vector2(180, 38)
	MultiplayerTheme.style_lavender_button(league_btn, 15)
	league_btn.pressed.connect(func():
		lb_current_offset = 0
		_on_load_league_leaderboard()
	)
	filter_row.add_child(league_btn)

	var nearby_btn := Button.new()
	nearby_btn.text = "My Nearby Challengers"
	nearby_btn.custom_minimum_size = Vector2(185, 38)
	MultiplayerTheme.style_green_button(nearby_btn, 15)
	nearby_btn.pressed.connect(_on_load_nearby_rankings)
	filter_row.add_child(nearby_btn)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter_row.add_child(spacer)

	# Pagination Controls
	lb_prev_btn = Button.new()
	lb_prev_btn.text = "< Prev"
	lb_prev_btn.custom_minimum_size = Vector2(80, 36)
	MultiplayerTheme.style_subtle_button(lb_prev_btn, 14)
	lb_prev_btn.pressed.connect(_on_lb_prev_page)
	filter_row.add_child(lb_prev_btn)

	lb_page_lbl = Label.new()
	lb_page_lbl.text = "Page 1"
	lb_page_lbl.add_theme_font_size_override("font_size", 14)
	lb_page_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	filter_row.add_child(lb_page_lbl)

	lb_next_btn = Button.new()
	lb_next_btn.text = "Next >"
	lb_next_btn.custom_minimum_size = Vector2(80, 36)
	MultiplayerTheme.style_subtle_button(lb_next_btn, 14)
	lb_next_btn.pressed.connect(_on_lb_next_page)
	filter_row.add_child(lb_next_btn)

	# Leaderboard Header Banner + Your Position Summary
	var banner_row := HBoxContainer.new()
	banner_row.add_theme_constant_override("separation", 12)
	lb_vbox.add_child(banner_row)

	lb_header_title_lbl = Label.new()
	lb_header_title_lbl.text = "GLOBAL ARENA LEADERBOARD"
	lb_header_title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lb_header_title_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	banner_row.add_child(lb_header_title_lbl)

	lb_your_rank_banner_lbl = Label.new()
	lb_your_rank_banner_lbl.text = "Your Standing: Global #- • League #-"
	lb_your_rank_banner_lbl.add_theme_font_size_override("font_size", 15)
	lb_your_rank_banner_lbl.add_theme_color_override("font_color", Color(0.62, 0.96, 0.72))
	banner_row.add_child(lb_your_rank_banner_lbl)

	# Scrollable Leaderboard Container
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	lb_vbox.add_child(scroll)

	var scroll_inner := VBoxContainer.new()
	scroll_inner.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll_inner.add_theme_constant_override("separation", 8)
	scroll.add_child(scroll_inner)

	lb_podium_container = HBoxContainer.new()
	lb_podium_container.add_theme_constant_override("separation", 12)
	scroll_inner.add_child(lb_podium_container)

	lb_rows_vbox = VBoxContainer.new()
	lb_rows_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lb_rows_vbox.add_theme_constant_override("separation", 6)
	scroll_inner.add_child(lb_rows_vbox)

	# Hidden RichTextLabel preserved for backward compatibility
	leaderboard_text = RichTextLabel.new()
	leaderboard_text.bbcode_enabled = true
	leaderboard_text.visible = false
	lb_vbox.add_child(leaderboard_text)


# ==============================================================================
# 7. TAB 4: BATTLE LOG & TROPHY TIMELINE
# ==============================================================================

func _build_history_tab() -> void:
	var hist_page := PanelContainer.new()
	hist_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	hist_page.visible = false
	hist_page.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	hub_tabs.add_child(hist_page)
	main_pages.append(hist_page)

	var hist_vbox := VBoxContainer.new()
	hist_vbox.add_theme_constant_override("separation", 10)
	hist_page.add_child(hist_vbox)

	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 14)
	hist_vbox.add_child(top_row)

	var title_lbl := Label.new()
	title_lbl.text = "RECENT COMPETITIVE BATTLES & TROPHY LOG"
	title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_row.add_child(title_lbl)

	hist_summary_stats_lbl = Label.new()
	hist_summary_stats_lbl.text = "0 Matches Recorded"
	hist_summary_stats_lbl.add_theme_font_size_override("font_size", 15)
	hist_summary_stats_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	top_row.add_child(hist_summary_stats_lbl)

	var refresh_hist_btn := Button.new()
	refresh_hist_btn.text = "Refresh Battle Log"
	refresh_hist_btn.custom_minimum_size = Vector2(165, 38)
	MultiplayerTheme.style_green_button(refresh_hist_btn, 15)
	refresh_hist_btn.pressed.connect(_on_load_history)
	top_row.add_child(refresh_hist_btn)

	var split_hbox := HBoxContainer.new()
	split_hbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	split_hbox.add_theme_constant_override("separation", 16)
	hist_vbox.add_child(split_hbox)

	# Left: Match Cards Scroll List
	var matches_scroll := ScrollContainer.new()
	matches_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	matches_scroll.size_flags_stretch_ratio = 1.75
	matches_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	split_hbox.add_child(matches_scroll)

	hist_matches_vbox = VBoxContainer.new()
	hist_matches_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hist_matches_vbox.add_theme_constant_override("separation", 8)
	matches_scroll.add_child(hist_matches_vbox)

	# Right: Trophy Progression Timeline
	var tr_card := PanelContainer.new()
	tr_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tr_card.size_flags_stretch_ratio = 0.85
	tr_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.14, 0.11, 0.96), Color(0.45, 0.58, 0.48, 0.8), 16, 2)
	)
	split_hbox.add_child(tr_card)

	var tr_vbox := VBoxContainer.new()
	tr_vbox.add_theme_constant_override("separation", 8)
	tr_card.add_child(tr_vbox)

	var tr_hdr := Label.new()
	tr_hdr.text = "TROPHY PROGRESSION LOG"
	tr_hdr.label_settings = MultiplayerTheme.make_title_settings(17, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	tr_vbox.add_child(tr_hdr)

	var tr_scroll := ScrollContainer.new()
	tr_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tr_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tr_vbox.add_child(tr_scroll)

	hist_trophies_vbox = VBoxContainer.new()
	hist_trophies_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hist_trophies_vbox.add_theme_constant_override("separation", 6)
	tr_scroll.add_child(hist_trophies_vbox)

	# Hidden RichTextLabel preserved for backward compatibility
	history_text = RichTextLabel.new()
	history_text.bbcode_enabled = true
	history_text.visible = false
	hist_vbox.add_child(history_text)


# ==============================================================================
# 8. MATCH / PLAYER DETAIL INSPECT MODAL
# ==============================================================================

func _build_inspect_modal() -> void:
	inspect_modal = PanelContainer.new()
	inspect_modal.set_anchors_preset(Control.PRESET_FULL_RECT)
	inspect_modal.visible = false
	inspect_modal.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.04, 0.08, 0.06, 0.88), MultiplayerTheme.COL_GOLD_BORDER, 18, 2, 10, 4)
	)
	hub_tabs.add_child(inspect_modal)

	var center := CenterContainer.new()
	inspect_modal.add_child(center)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(640, 390)
	card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD, 20, 3, 10, 5)
	)
	center.add_child(card)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 12)
	card.add_child(vbox)

	var top_bar := HBoxContainer.new()
	vbox.add_child(top_bar)

	inspect_title_lbl = Label.new()
	inspect_title_lbl.text = "BATTLE DETAILS"
	inspect_title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inspect_title_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_bar.add_child(inspect_title_lbl)

	var close_btn := Button.new()
	close_btn.text = "Close"
	close_btn.custom_minimum_size = Vector2(90, 34)
	MultiplayerTheme.style_danger_button(close_btn, 14)
	close_btn.pressed.connect(func(): inspect_modal.visible = false)
	top_bar.add_child(close_btn)

	inspect_body_vbox = VBoxContainer.new()
	inspect_body_vbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspect_body_vbox.add_theme_constant_override("separation", 10)
	vbox.add_child(inspect_body_vbox)


# ==============================================================================
# 9. SIGNAL CONNECTIONS & REAL-TIME FRAME LOOP
# ==============================================================================

func _connect_signals() -> void:
	mp_client.connection_state_changed.connect(_on_connection_state_changed)
	mp_client.matchmaking_updated.connect(_on_matchmaking_updated)
	mp_client.match_created.connect(_on_match_created)
	mp_client.map_assigned.connect(_on_map_assigned)
	mp_client.opponent_submitted.connect(_on_opponent_submitted)
	mp_client.verification_started.connect(_on_verification_started)
	mp_client.match_completed.connect(_on_match_completed)
	mp_client.match_expired.connect(_on_match_expired)
	mp_client.profile_updated.connect(_on_profile_updated_ws)
	mp_client.trophies_updated.connect(_on_trophies_updated_ws)
	mp_client.leaderboard_updated.connect(_on_leaderboard_updated_ws)

	rl_adapter.step_completed.connect(_on_rl_step_completed)
	rl_adapter.episode_ended.connect(_on_rl_episode_ended)
	rl_adapter.integration_error.connect(_on_rl_error)


func _process(delta: float) -> void:
	# 1. Subtle breathing glow on the main PLAY MULTIPLAYER button when idle in lobby
	if find_match_btn != null and !find_match_btn.disabled and lobby_view.visible:
		play_btn_pulse_phase += delta * 3.0
		var glow := 1.0 + sin(play_btn_pulse_phase) * 0.04
		find_match_btn.modulate = Color(glow, glow, glow, 1.0)

	# 2. Matchmaking Search Timer & Contextual Status Messages
	if is_searching_match and matchmaking_overlay.visible:
		search_elapsed_sec += delta
		var mins := int(search_elapsed_sec) / 60
		var secs := int(search_elapsed_sec) % 60
		mm_timer_lbl.text = "Search Time: %02d:%02d" % [mins, secs]
		var expanded_range := 200 + int(search_elapsed_sec) * 25
		mm_trophy_range_lbl.text = "Trophy Window: ±%d" % expanded_range

		if search_elapsed_sec < 3.5:
			mm_headline_lbl.text = "FINDING OPPONENT..."
			mm_substatus_lbl.text = "Scanning your League for online AI Dog trainers..."
		elif search_elapsed_sec < 8.0:
			mm_headline_lbl.text = "SEARCHING FOR WORTHY CHALLENGERS..."
			mm_substatus_lbl.text = "Expanding trophy range to find a balanced 1v1 match..."
		else:
			mm_headline_lbl.text = "PREPARING THE BATTLEFIELD..."
			mm_substatus_lbl.text = "Awaiting challenger queue pairing from the matchmaking server..."

		# Poll matchmaking status periodically so two queuing players pair promptly
		status_poll_timer += delta
		if status_poll_timer >= 2.0:
			status_poll_timer = 0.0
			_poll_matchmaking_while_searching()

	# 3. Active Competitive RL Step Loop
	if solving_active and !step_in_progress:
		step_timer += delta
		if step_timer >= step_interval:
			step_timer = 0.0
			_run_next_competitive_step()

	# 4. Active Match Countdown Timer in Battle HUD
	if battle_view.visible and match_expires_unix > 0.0:
		var now_unix := Time.get_unix_time_from_system()
		var rem := maxf(0.0, match_expires_unix - now_unix)
		var r_m := int(rem) / 60
		var r_s := int(rem) % 60
		battle_timer_lbl.text = "TIME: %02d:%02d" % [r_m, r_s]

	# 5. Poll active match status while waiting for opponent submission
	if mp_client.is_authenticated() and active_match_id != "" and !solving_active and !is_searching_match:
		status_poll_timer += delta
		if status_poll_timer >= 2.5:
			status_poll_timer = 0.0
			_poll_active_match_status()

	# 6. Periodic Local RL Agent Health Check
	rl_health_poll_timer += delta
	if rl_health_poll_timer >= 8.0:
		rl_health_poll_timer = 0.0
		_check_local_rl_agent()


func _check_local_rl_agent() -> void:
	var st: Dictionary = await rl_adapter.fetch_status()
	if bool(st.get("success", true)) and !st.has("error"):
		local_rl_online = true
		local_rl_model_version = int(st.get("modelVersion", 1))
		var ups := int(st.get("updates", 0))
		rl_dot.status_color = MultiplayerTheme.COL_VICTORY
		rl_status_pill_label.text = "AI Dog: Online (v%d)" % local_rl_model_version
		if lobby_agent_ready_lbl != null:
			lobby_agent_ready_lbl.text = "Local RL Dog Online: Policy Model v%d (%d PPO Updates) Ready for Battle" % [local_rl_model_version, ups]
			lobby_agent_ready_lbl.add_theme_color_override("font_color", Color(0.55, 0.96, 0.68))
	else:
		local_rl_online = false
		rl_dot.status_color = Color(0.95, 0.55, 0.25)
		rl_status_pill_label.text = "AI Dog: Offline"
		if lobby_agent_ready_lbl != null:
			lobby_agent_ready_lbl.text = "Local Python RL Agent not detected at %s (start doobyscoo-agent before battle)" % MazeSession.server_url
			lobby_agent_ready_lbl.add_theme_color_override("font_color", Color(1.0, 0.76, 0.42))


# ==============================================================================
# 10. VIEW TRANSITIONS, PROFILE RENDERING & AUTH HANDLERS
# ==============================================================================

func _show_auth_view() -> void:
	auth_panel.visible = true
	hub_tabs.visible = false
	nav_bar.visible = false
	logout_btn.visible = false
	top_player_badge.text = "Not Signed In"
	header_trophy_label.text = "0"


func _show_authenticated_view() -> void:
	auth_panel.visible = false
	hub_tabs.visible = true
	nav_bar.visible = true
	logout_btn.visible = true
	_update_header_badge()


func _update_header_badge() -> void:
	var p: Dictionary = mp_client.current_player
	if p.is_empty():
		top_player_badge.text = "Signed In"
		return
	var dname := str(p.get("display_name", p.get("username", "Player")))
	var lvl := int(p.get("level", 1))
	var tr := int(p.get("trophies", 0))
	var lg := str(p.get("league", "Beginner"))
	var av := str(p.get("avatar", "dog_default"))

	top_player_badge.text = "%s (Lv.%d)" % [dname, lvl]
	header_trophy_label.text = "%d (%s)" % [tr, lg]
	header_league_badge.league_name = lg
	header_avatar.avatar_id = av


func _on_connection_state_changed(connected: bool, status_text: String) -> void:
	top_status_label.text = "Server: " + status_text
	if connected:
		conn_dot.status_color = MultiplayerTheme.COL_VICTORY
		top_status_label.add_theme_color_override("font_color", Color(0.65, 1.0, 0.74))
	elif status_text.to_lower().contains("connect") or status_text.to_lower().contains("reconnect"):
		conn_dot.status_color = MultiplayerTheme.COL_GOLD
		top_status_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	else:
		conn_dot.status_color = MultiplayerTheme.COL_DEFEAT
		top_status_label.add_theme_color_override("font_color", Color(1.0, 0.68, 0.64))


func _on_apply_endpoints_pressed() -> void:
	mp_client.server_url = server_url_input.text.strip_edges()
	MazeSession.multiplayer_server_url = mp_client.server_url
	MazeSession.server_url = rl_url_input.text.strip_edges()
	rl_adapter.real_client.base_url = MazeSession.server_url
	mp_client.save_session()
	_check_local_rl_agent()
	if mp_client.is_authenticated():
		mp_client.disconnect_websocket()
		mp_client.connect_websocket()
		await _refresh_all_player_data()


func _on_login_pressed() -> void:
	_on_apply_endpoints_pressed()
	auth_feedback_label.text = "Authenticating with DoobyScoo Arena Server..."
	var res: Dictionary = await mp_client.login_account(
		login_user_input.text.strip_edges(),
		login_pass_input.text
	)
	if bool(res.get("success", false)):
		_show_authenticated_view()
		await _refresh_all_player_data()
	else:
		auth_feedback_label.text = "Login Error: " + str(res.get("error", "Failed"))


func _on_register_pressed() -> void:
	_on_apply_endpoints_pressed()
	auth_feedback_label.text = "Creating your Challenger Account..."
	var res: Dictionary = await mp_client.register_account(
		reg_user_input.text.strip_edges(),
		reg_email_input.text.strip_edges(),
		reg_pass_input.text,
		reg_display_input.text.strip_edges()
	)
	if bool(res.get("success", false)):
		_show_authenticated_view()
		await _refresh_all_player_data()
	else:
		auth_feedback_label.text = "Registration Error: " + str(res.get("error", "Failed"))


func _on_logout_pressed() -> void:
	solving_active = false
	is_searching_match = false
	active_match_id = ""
	matchmaking_overlay.visible = false
	versus_overlay.visible = false
	results_overlay.visible = false
	battle_view.visible = false
	lobby_view.visible = true
	await mp_client.logout_account()
	_show_auth_view()


func _refresh_all_player_data() -> void:
	var prof_res: Dictionary = await mp_client.fetch_my_profile()
	if bool(prof_res.get("success", false)):
		_update_header_badge()
		_render_profile_details(prof_res.get("player", {}))
	await _on_load_global_leaderboard()
	await _on_load_history()


func _render_profile_details(p: Dictionary) -> void:
	if p.is_empty():
		return

	var dname := str(p.get("display_name", p.get("username", "Trainer")))
	var uname := str(p.get("username", "player"))
	var av := str(p.get("avatar", "dog_default"))
	var lvl := int(p.get("level", 1))
	var xp := int(p.get("xp", 0))
	var trophies := int(p.get("trophies", 0))
	var league := str(p.get("league", "Beginner"))
	var g_rank := str(p.get("global_position", "-"))
	var l_rank := str(p.get("league_position", "-"))
	var wins := int(p.get("wins", 0))
	var losses := int(p.get("losses", 0))
	var draws := int(p.get("draws", 0))
	var total_m := int(p.get("total_matches", 0))
	var win_pct := float(p.get("win_rate", 0.0)) * 100.0
	var best_str := str(p.get("best_score")) if p.get("best_score") != null else "N/A"
	var avg_str := str(p.get("average_score")) if p.get("average_score") != null else "N/A"
	var bones_total := int(p.get("total_bones_collected", 0))
	var dog_ver := int(p.get("dog_model_version", 1))

	var lg_info := MultiplayerTheme.get_league_info(league, trophies)
	var xp_in_level := xp % 100

	# 1. Update Lobby Player Card
	lobby_avatar.avatar_id = av
	lobby_display_name_lbl.text = dname
	lobby_username_lbl.text = "@%s • Global Rank #%s • League #%s" % [uname, g_rank, l_rank]
	lobby_level_lbl.text = "Lv.%d (%d/100 XP)" % [lvl, xp_in_level]
	lobby_xp_bar.max_value = 100
	lobby_xp_bar.value = xp_in_level

	lobby_league_badge.league_name = league
	lobby_league_name_lbl.text = "%s LEAGUE" % league.to_upper()
	lobby_trophy_count_lbl.text = "%d Trophies" % trophies
	lobby_league_progress_bar.max_value = 100
	lobby_league_progress_bar.value = float(lg_info["progress"]) * 100.0
	if bool(lg_info["is_max"]):
		lobby_next_league_lbl.text = "Master Tier Reached — Top Competitive Division!"
	else:
		var needed: int = max(0, int(lg_info["next_min"]) - trophies)
		lobby_next_league_lbl.text = "%d Trophies to %s League (%d / %d)" % [needed, str(lg_info["next_name"]), trophies, int(lg_info["next_min"])]

	_set_stat_badge_value(lobby_stat_rank, "#%s" % g_rank)
	_set_stat_badge_value(lobby_stat_wins, str(wins))
	_set_stat_badge_value(lobby_stat_losses, str(losses))
	_set_stat_badge_value(lobby_stat_winrate, "%.1f%%" % win_pct)
	_set_stat_badge_value(lobby_stat_best, best_str)
	_set_stat_badge_value(lobby_stat_model, "v%d" % dog_ver)

	# 2. Update Profile Tab
	edit_display_input.text = dname
	prof_avatar_large.avatar_id = av
	prof_league_shield_large.league_name = league
	prof_title_name_lbl.text = dname
	prof_handle_lbl.text = "@%s • Joined %s" % [uname, str(p.get("created_at", "")).substr(0, 10)]
	prof_level_badge_lbl.text = "Level %d • %d Total XP (%d / 100 to Lv.%d)" % [lvl, xp, xp_in_level, lvl + 1]
	prof_xp_bar.max_value = 100
	prof_xp_bar.value = xp_in_level

	prof_league_tier_lbl.text = "%s LEAGUE — RANK #%s" % [league.to_upper(), l_rank]
	prof_trophy_big_lbl.text = "%d Trophies • Global Standing #%s" % [trophies, g_rank]
	prof_league_bar.max_value = 100
	prof_league_bar.value = float(lg_info["progress"]) * 100.0

	for i in range(edit_avatar_select.item_count):
		if edit_avatar_select.get_item_text(i) == av:
			_select_avatar_option(i)
			break

	if lb_your_rank_banner_lbl != null:
		lb_your_rank_banner_lbl.text = "Your Standing: Global #%s • %s League #%s (%d Trophies)" % [g_rank, league, l_rank, trophies]

	profile_details_text.text = (
		"[b][color=#ffe885]COMPETITIVE CAREER RECORD[/color][/b]\n"
		+ "Trainer: [b]%s[/b] (@%s)  |  Account Level: [b]Lv.%d[/b] (%d XP)\n" % [dname, uname, lvl, xp]
		+ "Trophies: [b][color=#ffd952]%d[/color][/b]  |  Division: [b]%s League[/b]  |  Global Rank: [b]#%s[/b] (League #%s)\n\n" % [trophies, league, g_rank, l_rank]
		+ "[b][color=#8cf5a8]BATTLE PERFORMANCE[/color][/b]\n"
		+ "Total Ranked Battles: [b]%d[/b]  |  Victories: [b][color=#52e075]%d[/color][/b]  |  Defeats: [b][color=#f26d68]%d[/color][/b]  |  Draws: [b]%d[/b]\n" % [total_m, wins, losses, draws]
		+ "Career Win Rate: [b]%.1f%%[/b]  |  Total Bones Collected: [b]%d[/b]\n" % [win_pct, bones_total]
		+ "Best Verified Official Score: [b]%s[/b] (Lower = Better)  |  Average Official Score: [b]%s[/b]\n" % [best_str, avg_str]
		+ "Local RL Dog Policy Version: [b]Model v%d[/b]" % dog_ver
	)


func _set_stat_badge_value(badge: PanelContainer, text_val: String) -> void:
	if badge == null or badge.get_child_count() == 0:
		return
	var vb := badge.get_child(0)
	if vb.get_child_count() >= 2 and vb.get_child(1) is Label:
		(vb.get_child(1) as Label).text = text_val


func _on_save_profile_pressed() -> void:
	var avatar_name: String = edit_avatar_select.get_item_text(edit_avatar_select.selected)
	prof_save_feedback_lbl.text = "Saving trainer profile..."
	var res: Dictionary = await mp_client.update_my_profile({
		"display_name": edit_display_input.text.strip_edges(),
		"avatar": avatar_name
	})
	if bool(res.get("success", false)):
		_update_header_badge()
		_render_profile_details(res.get("player", {}))
		prof_save_feedback_lbl.text = "Profile saved!"
	else:
		prof_save_feedback_lbl.text = "Error: " + str(res.get("error", "Could not update profile"))


# ==============================================================================
# 11. MATCHMAKING, OPPONENT FOUND TRANSITION & LIVE BATTLE FLOW
# ==============================================================================

func _on_find_match_pressed() -> void:
	find_match_btn.disabled = true
	cancel_match_btn.disabled = false
	learn_after_match_btn.disabled = true
	results_overlay.visible = false

	# Open Animated Matchmaking Radar Overlay
	var p := mp_client.current_player
	mm_radar.avatar_id = str(p.get("avatar", "dog_default"))
	mm_radar.league_name = str(p.get("league", "Beginner"))
	mm_player_summary_lbl.text = "%s • %d Trophies • %s League" % [
		str(p.get("display_name", p.get("username", "Trainer"))),
		int(p.get("trophies", 0)),
		str(p.get("league", "Beginner"))
	]
	search_elapsed_sec = 0.0
	is_searching_match = true
	matchmaking_overlay.visible = true
	matchmaking_overlay.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(matchmaking_overlay, "modulate:a", 1.0, 0.18)

	match_state_label.text = "State: SEARCHING — Finding opponent..."
	arena_result_summary_label.text = "Searching for a challenger with a similar trophy count..."

	var res: Dictionary = await mp_client.join_matchmaking()
	if !bool(res.get("success", false)):
		is_searching_match = false
		matchmaking_overlay.visible = false
		find_match_btn.disabled = false
		cancel_match_btn.disabled = true
		match_state_label.text = "Matchmaking Error: " + str(res.get("error", "Failed"))
		return

	var state: String = str(res.get("state", "SEARCHING"))
	if res.get("match_id") != null and str(res.get("match_id", "")) != "":
		if res.get("match") is Dictionary:
			_extract_opponent_from_match(res["match"])
		await _begin_assigned_match(str(res["match_id"]))
	else:
		match_state_label.text = "State: %s — Finding opponent..." % state


func _poll_matchmaking_while_searching() -> void:
	if !is_searching_match:
		return
	var res: Dictionary = await mp_client.fetch_matchmaking_status()
	if !bool(res.get("success", false)):
		return
	if res.get("match_id") != null and str(res.get("match_id", "")) != "":
		if res.get("match") is Dictionary:
			_extract_opponent_from_match(res["match"])
		await _begin_assigned_match(str(res["match_id"]))


func _on_cancel_match_pressed() -> void:
	is_searching_match = false
	var res: Dictionary = await mp_client.cancel_matchmaking()
	matchmaking_overlay.visible = false
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	match_state_label.text = "Matchmaking Cancelled — Ready in Arena Lobby (" + str(res.get("state", "CANCELLED")) + ")"


func _on_matchmaking_updated(state: String, payload: Dictionary) -> void:
	if state == "SEARCHING":
		match_state_label.text = "State: SEARCHING — Finding opponent..."
	elif state == "OPPONENT_FOUND":
		var opp: Dictionary = payload.get("opponent", {}) if (payload.get("opponent") is Dictionary) else {}
		if !opp.is_empty():
			current_opponent_data = opp
		mm_headline_lbl.text = "OPPONENT FOUND!"
		mm_substatus_lbl.text = "Matched vs %s (%d Trophies)" % [
			str(opp.get("display_name", opp.get("username", "Opponent"))),
			int(opp.get("trophies", 0))
		]
		match_state_label.text = "State: OPPONENT_FOUND — Matched vs %s (%d Trophies)" % [
			str(opp.get("display_name", opp.get("username", "Opponent"))),
			int(opp.get("trophies", 0))
		]


func _on_match_created(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", ""))
	if mid != "":
		active_match_id = mid
		match_state_label.text = "State: MATCH_CREATED (%s)" % mid


func _on_map_assigned(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", ""))
	if mid != "" and (active_match_id == "" or active_match_id == mid) and !solving_active:
		await _begin_assigned_match(mid)


func _extract_opponent_from_match(match_dict: Dictionary) -> void:
	var my_id := str(mp_client.current_player.get("player_id", ""))
	var p1: Dictionary = match_dict.get("player_1", {}) if (match_dict.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_dict.get("player_2", {}) if (match_dict.get("player_2") is Dictionary) else {}
	if str(p1.get("player_id", "")) == my_id:
		current_opponent_data = p2
	elif str(p2.get("player_id", "")) == my_id:
		current_opponent_data = p1


func _show_opponent_found_ceremony(map_id: String, difficulty: String) -> void:
	if vs_transition_in_progress:
		return
	vs_transition_in_progress = true
	matchmaking_overlay.visible = false

	for c in vs_left_slot.get_children():
		c.queue_free()
	for c in vs_right_slot.get_children():
		c.queue_free()

	var my_card := MultiplayerComponents.create_versus_player_card(mp_client.current_player, true)
	var opp_card := MultiplayerComponents.create_versus_player_card(
		current_opponent_data if !current_opponent_data.is_empty() else {"display_name": "Challenger", "username": "opponent", "trophies": int(mp_client.current_player.get("trophies", 0)), "league": str(mp_client.current_player.get("league", "Beginner"))},
		false
	)
	vs_left_slot.add_child(my_card)
	vs_right_slot.add_child(opp_card)

	vs_map_badge_lbl.text = "Assigned Arena Map: %s • Tier: %s • Official Scoring: Steps - 5 × Bones" % [map_id, difficulty.capitalize()]
	versus_overlay.visible = true
	versus_overlay.modulate.a = 0.0

	var tw := create_tween()
	tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(versus_overlay, "modulate:a", 1.0, 0.22)
	await get_tree().create_timer(1.45).timeout

	var fade_out := create_tween()
	fade_out.tween_property(versus_overlay, "modulate:a", 0.0, 0.18)
	await fade_out.finished
	versus_overlay.visible = false
	vs_transition_in_progress = false


func _begin_assigned_match(match_id: String) -> void:
	if (solving_active or vs_transition_in_progress) and active_match_id == match_id:
		return
	is_searching_match = false
	active_match_id = match_id
	cancel_match_btn.disabled = true
	find_match_btn.disabled = true
	match_state_label.text = "State: MAP_ASSIGNED — Downloading competition map..."

	# Fetch match details if opponent info isn't populated yet
	if current_opponent_data.is_empty():
		var m_info: Dictionary = await mp_client.fetch_match(match_id)
		if bool(m_info.get("success", false)):
			_extract_opponent_from_match(m_info)

	var map_res: Dictionary = await mp_client.fetch_match_map(match_id)
	if !bool(map_res.get("success", false)):
		matchmaking_overlay.visible = false
		match_state_label.text = "Error fetching match map: " + str(map_res.get("error", ""))
		find_match_btn.disabled = false
		return

	active_map_id = str(map_res.get("map_id", ""))
	active_map_hash = str(map_res.get("map_hash", ""))
	var difficulty := str(map_res.get("difficulty", "standard"))
	active_maze_data = map_res.get("maze", {}) if (map_res.get("maze") is Dictionary) else {}

	if !active_maze_data.has("grid"):
		matchmaking_overlay.visible = false
		match_state_label.text = "Invalid competition map received."
		find_match_btn.disabled = false
		return

	# Show exciting Opponent Found VS ceremony before entering the battle board
	await _show_opponent_found_ceremony(active_map_id, difficulty)

	# Switch Arena tab from Lobby View to Live Battle View
	_switch_main_tab(0)
	lobby_view.visible = false
	results_overlay.visible = false
	battle_view.visible = true
	match_started_unix = Time.get_unix_time_from_system()
	match_expires_unix = match_started_unix + 600.0

	# Populate Battle HUD Player vs Opponent headers
	var me := mp_client.current_player
	battle_you_avatar.avatar_id = str(me.get("avatar", "dog_default"))
	battle_you_name_lbl.text = str(me.get("display_name", me.get("username", "You")))
	battle_you_trophies_lbl.text = "%d Trophies (%s)" % [int(me.get("trophies", 0)), str(me.get("league", "Beginner"))]

	var opp := current_opponent_data
	battle_opp_avatar.avatar_id = str(opp.get("avatar", "dog_husky"))
	battle_opp_name_lbl.text = str(opp.get("display_name", opp.get("username", "Challenger")))
	battle_opp_trophies_lbl.text = "%d Trophies (%s)" % [int(opp.get("trophies", 0)), str(opp.get("league", "Beginner"))]
	battle_opp_status_pill.text = "Opponent Status: Solving Maze Live..."
	battle_opp_status_pill.add_theme_color_override("font_color", Color(1.0, 0.86, 0.62))

	board.setup_board(active_maze_data["grid"])
	score_manager.reset()
	_update_battle_hud_metrics(0, 0, 0)

	match_state_label.text = "State: DOG SOLVING LOCALLY (Map %s)" % active_map_id
	arena_result_summary_label.text = (
		"[b][color=#ffe885]Competition Map Ready![/color][/b]\n"
		+ "Map ID: [b]%s[/b]  |  SHA-256: [code]%s...[/code]\n" % [active_map_id, active_map_hash.substr(0, 12)]
		+ "Your local Python RL Dog is now navigating the maze on your device."
	)

	var start_res: Dictionary = await rl_adapter.start_competitive_session(
		active_maze_data,
		active_match_id,
		active_map_id,
		active_map_hash,
		true
	)
	if !bool(start_res.get("success", false)):
		var err_msg := str(start_res.get("error", "Ensure local Python agent is running"))
		match_state_label.text = "Local RL Agent Error: " + err_msg
		arena_result_summary_label.text = (
			"[color=#ff7878][b]Local RL Agent Unavailable[/b][/color]\n"
			+ "%s\n\nStart your local agent with:\n[code]python -m doobyscoo serve --port 8765[/code]" % err_msg
		)
		find_match_btn.disabled = false
		return

	solving_active = true
	step_in_progress = false
	step_timer = 0.0


func _update_battle_hud_metrics(steps: int, bones: int, score: int) -> void:
	if battle_score_val_lbl != null:
		battle_score_val_lbl.text = str(score)
	if battle_steps_val_lbl != null:
		battle_steps_val_lbl.text = "%d / 300" % steps
	if battle_bones_val_lbl != null:
		battle_bones_val_lbl.text = "%d / 5" % bones
	if battle_bones_bar != null:
		battle_bones_bar.value = bones
	if battle_steps_bar != null:
		battle_steps_bar.value = steps
	arena_step_log_label.text = "Steps: %d | Bones: %d/5 | Official Score: %d" % [steps, bones, score]


func _run_next_competitive_step() -> void:
	if !solving_active or step_in_progress:
		return
	step_in_progress = true
	var reported_pos: Array = [board.dog.grid_position.x, board.dog.grid_position.y]
	await rl_adapter.step_agent(true, reported_pos)
	step_in_progress = false


func _on_rl_step_completed(result: Dictionary) -> void:
	await board.animate_step_result(result)
	var steps: int = int(result.get("steps", 0))
	var bones: int = int(result.get("bonesCollected", 0))
	var score: int = int(result.get("score", steps - 5 * bones))
	_update_battle_hud_metrics(steps, bones, score)


func _on_rl_episode_ended(result: Dictionary) -> void:
	solving_active = false
	match_state_label.text = "State: SUBMITTING RESULT TO SERVER..."

	var sub_payload: Dictionary = result.get("submission_payload", {}) if (result.get("submission_payload") is Dictionary) else {
		"match_id": active_match_id,
		"map_id": active_map_id,
		"map_hash": active_map_hash,
		"action_trace": result.get("action_trace", []),
		"claimed_score": int(result.get("claimed_score", result.get("score", 0))),
		"claimed_steps": int(result.get("claimed_steps", result.get("steps", 0))),
		"claimed_bones_collected": int(result.get("claimed_bones_collected", result.get("bonesCollected", 0))),
		"claimed_completed": bool(result.get("claimed_completed", result.get("won", false))),
		"final_position": result.get("final_position", result.get("position", [0, 0])),
		"submission_id": str(result.get("submission_id", "sub_" + active_match_id)),
		"model_version": int(result.get("model_version", 1)),
	}
	sub_payload["player_id"] = str(mp_client.current_player.get("player_id", ""))

	var sub_res: Dictionary = await mp_client.submit_match_result(active_match_id, sub_payload)
	learn_after_match_btn.disabled = false
	res_train_dog_btn.disabled = false

	if !bool(sub_res.get("success", false)):
		match_state_label.text = "Submission Rejected: " + str(sub_res.get("error", "Verification failed"))
		find_match_btn.disabled = false
		return

	var status_str: String = str(sub_res.get("status", "AWAITING_RESULTS"))
	if status_str == "COMPLETED":
		_display_completed_match_details(sub_res)
	else:
		match_state_label.text = "State: WAITING FOR OPPONENT SUBMISSION..."
		battle_opp_status_pill.text = "Your Run Verified! Waiting for Opponent to Finish..."
		arena_result_summary_label.text = (
			"[b][color=#75f096]Your Action Trace Was Verified by the Server![/color][/b]\n"
			+ "Verified Official Score: [b]%d[/b] (Steps: %d, Bones: %d)\n" % [
				int(sub_payload.get("claimed_score", 0)),
				int(sub_payload.get("claimed_steps", 0)),
				int(sub_payload.get("claimed_bones_collected", 0))
			]
			+ "Waiting asynchronously for challenger to complete their maze run..."
		)


func _on_opponent_submitted(_payload: Dictionary) -> void:
	battle_opp_status_pill.text = "Opponent Finished & Submitted Trace!"
	battle_opp_status_pill.add_theme_color_override("font_color", MultiplayerTheme.COL_VICTORY)
	if active_match_id != "" and !solving_active:
		match_state_label.text = "Opponent submitted! Verifying results..."


func _on_verification_started(_payload: Dictionary) -> void:
	battle_opp_status_pill.text = "Server Verifying Both Action Traces..."
	match_state_label.text = "State: VERIFYING RESULTS..."


func _on_match_completed(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", active_match_id))
	if mid != "":
		var full_match: Dictionary = await mp_client.fetch_match_result(mid)
		if bool(full_match.get("success", false)):
			_display_completed_match_details(full_match)
	await _refresh_all_player_data()


func _on_match_expired(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", active_match_id))
	match_state_label.text = "State: MATCH EXPIRED (%s)" % mid
	find_match_btn.disabled = false
	matchmaking_overlay.visible = false


func _poll_active_match_status() -> void:
	if active_match_id == "":
		return
	var res: Dictionary = await mp_client.fetch_match(active_match_id)
	if bool(res.get("success", false)):
		var st: String = str(res.get("status", ""))
		if st == "COMPLETED" or st == "EXPIRED":
			_display_completed_match_details(res)
			await _refresh_all_player_data()


# ==============================================================================
# 12. BATTLE RESULTS SCREEN PRESENTATION
# ==============================================================================

func _display_completed_match_details(match_data: Dictionary) -> void:
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	matchmaking_overlay.visible = false
	versus_overlay.visible = false

	var st: String = str(match_data.get("status", "COMPLETED"))
	match_state_label.text = "State: " + st

	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	var winner_id: String = str(match_data.get("winner_id", "")) if match_data.get("winner_id") != null else ""
	var is_draw: bool = bool(match_data.get("is_draw", false))

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}
	var s1: Dictionary = p1.get("submission", {}) if (p1.get("submission") is Dictionary) else {}
	var s2: Dictionary = p2.get("submission", {}) if (p2.get("submission") is Dictionary) else {}

	var me_p: Dictionary = p1 if str(p1.get("player_id", "")) == my_id else p2
	var opp_p: Dictionary = p2 if str(p1.get("player_id", "")) == my_id else p1
	var me_s: Dictionary = me_p.get("submission", {}) if (me_p.get("submission") is Dictionary) else {}
	var opp_s: Dictionary = opp_p.get("submission", {}) if (opp_p.get("submission") is Dictionary) else {}

	var headline: String = "[color=yellow][b]MATCH DRAW![/b][/color]"
	var outcome_mode := "draw"
	if !is_draw and winner_id != "":
		if winner_id == my_id:
			headline = "[color=lime][b]VICTORY! YOUR DOG WON THE MATCH![/b][/color]"
			outcome_mode = "victory"
		else:
			headline = "[color=salmon][b]DEFEAT — OPPONENT'S DOG SCORED BETTER[/b][/color]"
			outcome_mode = "defeat"

	arena_result_summary_label.text = (
		"%s\n\n" % headline
		+ "[b]%s[/b]: Score %s | Steps %s | Bones %s | Completed: %s | Trophies: %s\n" % [
			str(p1.get("display_name", p1.get("username", "Player 1"))),
			str(s1.get("verified_score", "N/A")),
			str(s1.get("steps", "-")),
			str(s1.get("bones_collected", "-")),
			str(s1.get("completed", false)),
			str(s1.get("trophy_change", 0))
		]
		+ "[b]%s[/b]: Score %s | Steps %s | Bones %s | Completed: %s | Trophies: %s\n" % [
			str(p2.get("display_name", p2.get("username", "Player 2"))),
			str(s2.get("verified_score", "N/A")),
			str(s2.get("steps", "-")),
			str(s2.get("bones_collected", "-")),
			str(s2.get("completed", false)),
			str(s2.get("trophy_change", 0))
		]
	)

	# Populate Celebratory / Polished Results Overlay
	res_banner_icon.outcome = outcome_mode
	res_train_feedback_lbl.text = ""
	if outcome_mode == "victory":
		res_title_lbl.text = "VICTORY!"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(36, MultiplayerTheme.COL_VICTORY, 7)
		res_subtitle_lbl.text = "Your trained AI Dog conquered the maze with the winning Official Score!"
	elif outcome_mode == "defeat":
		res_title_lbl.text = "VALIANT EFFORT!"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(34, Color(0.98, 0.56, 0.52), 7)
		res_subtitle_lbl.text = "Your challenger achieved a lower score this round. Train your Dog policy & strike back!"
	else:
		res_title_lbl.text = "COMPETITIVE DRAW!"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_GOLD_BRIGHT, 7)
		res_subtitle_lbl.text = "Neck and neck! Both AI Dogs tied on the official arena scorecard."

	var my_tr_chg := int(me_s.get("trophy_change", 0)) if me_s.get("trophy_change") != null else 0
	var tr_sign := ("+%d" % my_tr_chg) if my_tr_chg >= 0 else str(my_tr_chg)
	res_trophy_delta_lbl.text = "%s Trophies" % tr_sign
	res_trophy_delta_lbl.add_theme_color_override(
		"font_color",
		MultiplayerTheme.COL_VICTORY if my_tr_chg > 0 else (MultiplayerTheme.COL_DEFEAT if my_tr_chg < 0 else MultiplayerTheme.COL_GOLD_BRIGHT)
	)

	# Calculate real duration if timestamps exist
	var elapsed_sec := int(maxf(1.0, Time.get_unix_time_from_system() - match_started_unix)) if match_started_unix > 0.0 else 0
	var map_label := str(match_data.get("map_id", active_map_id))
	res_duration_lbl.text = ("Map: %s • %ds" % [map_label, elapsed_sec]) if elapsed_sec > 0 else ("Map: %s" % map_label)

	var est_xp := 75 if outcome_mode == "victory" else 25
	res_xp_awarded_lbl.text = "+%d Arena XP" % est_xp

	_populate_result_player_column(res_you_card_box, "YOUR DOG RUN", me_p, me_s, true)
	_populate_result_player_column(res_opp_card_box, "OPPONENT RUN", opp_p, opp_s, false)

	results_overlay.visible = true
	results_overlay.scale = Vector2(0.92, 0.92)
	results_overlay.pivot_offset = results_overlay.size * 0.5
	var tw := create_tween()
	tw.set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(results_overlay, "scale", Vector2.ONE, 0.24)

	active_match_id = ""


func _populate_result_player_column(box: VBoxContainer, tag: String, p_info: Dictionary, sub_info: Dictionary, is_you: bool) -> void:
	for c in box.get_children():
		c.queue_free()

	var hdr := Label.new()
	hdr.text = tag
	hdr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hdr.add_theme_font_size_override("font_size", 12)
	hdr.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT if is_you else Color(1.0, 0.72, 0.68))
	box.add_child(hdr)

	var p_row := HBoxContainer.new()
	p_row.alignment = BoxContainer.ALIGNMENT_CENTER
	p_row.add_theme_constant_override("separation", 10)
	box.add_child(p_row)

	p_row.add_child(MultiplayerComponents.DogAvatarPortrait.new(str(p_info.get("avatar", "dog_default")), 46.0, false))

	var name_lbl := Label.new()
	name_lbl.text = str(p_info.get("display_name", p_info.get("username", "Player")))
	name_lbl.label_settings = MultiplayerTheme.make_title_settings(19, MultiplayerTheme.COL_TEXT_CREAM, 4)
	p_row.add_child(name_lbl)

	var sc_val := str(sub_info.get("verified_score", "N/A"))
	var sc_big := Label.new()
	sc_big.text = "Official Score: %s" % sc_val
	sc_big.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sc_big.add_theme_font_size_override("font_size", 20)
	sc_big.add_theme_color_override("font_color", Color(0.52, 0.98, 0.68))
	box.add_child(sc_big)

	var details_lbl := Label.new()
	var steps_str := str(sub_info.get("steps", "-"))
	var bones_str := str(sub_info.get("bones_collected", "-"))
	var comp_str := "Goal Reached" if bool(sub_info.get("completed", false)) else "Incomplete"
	details_lbl.text = "Steps: %s  •  Bones: %s  •  %s" % [steps_str, bones_str, comp_str]
	details_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	details_lbl.add_theme_font_size_override("font_size", 13)
	details_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	box.add_child(details_lbl)


func _on_play_again_from_results() -> void:
	results_overlay.visible = false
	battle_view.visible = false
	lobby_view.visible = true
	await _on_find_match_pressed()


func _on_back_to_lobby_pressed() -> void:
	solving_active = false
	results_overlay.visible = false
	matchmaking_overlay.visible = false
	versus_overlay.visible = false
	battle_view.visible = false
	lobby_view.visible = true
	find_match_btn.disabled = false


func _on_learn_after_match_pressed() -> void:
	learn_after_match_btn.disabled = true
	res_train_dog_btn.disabled = true
	res_train_feedback_lbl.text = "Running PPO Continual Learning Update on Local Python RL Agent..."
	var res: Dictionary = await rl_adapter.learn_from_competitive_match(true)
	if bool(res.get("success", false)):
		var st_res: Dictionary = await rl_adapter.fetch_status()
		var new_ver: int = int(st_res.get("modelVersion", 1))
		await mp_client.update_my_profile({"dog_model_version": new_ver})
		arena_step_log_label.text = "Post-match continual learning triggered! Dog updated to Model v%d." % new_ver
		res_train_feedback_lbl.text = "Success! Local AI Dog updated to Policy Model v%d!" % new_ver
		_check_local_rl_agent()
	else:
		res_train_feedback_lbl.text = "Could not trigger continual learning: " + str(res.get("error", ""))


func _on_rl_error(message: String) -> void:
	solving_active = false
	step_in_progress = false
	find_match_btn.disabled = false
	match_state_label.text = "RL Error: " + message


# ==============================================================================
# 13. LIVE WEBSOCKET UPDATES, LEADERBOARDS & BATTLE HISTORY
# ==============================================================================

func _on_profile_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_update_header_badge()
	_render_profile_details(mp_client.current_player)


func _on_trophies_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_update_header_badge()


func _on_leaderboard_updated_ws(_payload: Dictionary) -> void:
	await _on_load_global_leaderboard()


func _on_lb_prev_page() -> void:
	if lb_current_offset >= LB_PAGE_LIMIT:
		lb_current_offset -= LB_PAGE_LIMIT
		if lb_current_mode == "league":
			await _on_load_league_leaderboard()
		else:
			await _on_load_global_leaderboard()


func _on_lb_next_page() -> void:
	lb_current_offset += LB_PAGE_LIMIT
	if lb_current_mode == "league":
		await _on_load_league_leaderboard()
	else:
		await _on_load_global_leaderboard()


func _on_load_global_leaderboard() -> void:
	lb_current_mode = "global"
	var res: Dictionary = await mp_client.fetch_global_leaderboard(LB_PAGE_LIMIT, lb_current_offset)
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load global leaderboard."
		return
	var page_num := (lb_current_offset / LB_PAGE_LIMIT) + 1
	lb_page_lbl.text = "Page %d" % page_num
	lb_prev_btn.disabled = (lb_current_offset == 0)
	var entries: Array = res.get("entries", [])
	lb_next_btn.disabled = (entries.size() < LB_PAGE_LIMIT)
	_render_leaderboard_entries("GLOBAL LEADERBOARD (TOP CHALLENGERS)", entries)


func _on_load_league_leaderboard() -> void:
	lb_current_mode = "league"
	var lg: String = leaderboard_league_select.get_item_text(leaderboard_league_select.selected)
	var res: Dictionary = await mp_client.fetch_league_leaderboard(lg, LB_PAGE_LIMIT, lb_current_offset)
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load league leaderboard."
		return
	var page_num := (lb_current_offset / LB_PAGE_LIMIT) + 1
	lb_page_lbl.text = "Page %d" % page_num
	lb_prev_btn.disabled = (lb_current_offset == 0)
	var entries: Array = res.get("entries", [])
	lb_next_btn.disabled = (entries.size() < LB_PAGE_LIMIT)
	_render_leaderboard_entries("%s LEAGUE STANDINGS" % lg.to_upper(), entries)


func _on_load_nearby_rankings() -> void:
	lb_current_mode = "nearby"
	var res: Dictionary = await mp_client.fetch_my_rank()
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load nearby rankings."
		return
	lb_prev_btn.disabled = true
	lb_next_btn.disabled = true
	lb_page_lbl.text = "Nearby"
	var title: String = "NEARBY CHALLENGERS (GLOBAL #%s | LEAGUE #%s)" % [
		str(res.get("global_position", "-")),
		str(res.get("league_position", "-"))
	]
	_render_leaderboard_entries(title, res.get("nearby_players", []))


func _render_leaderboard_entries(title: String, entries: Array) -> void:
	lb_header_title_lbl.text = title

	for c in lb_podium_container.get_children():
		c.queue_free()
	for c in lb_rows_vbox.get_children():
		c.queue_free()

	# Also populate legacy `leaderboard_text` for any external script inspection
	var lines: Array[String] = ["[b]%s[/b]\n" % title]
	if entries.is_empty():
		lines.append("No players ranked yet.")
		lb_rows_vbox.add_child(
			MultiplayerComponents.create_empty_state_card(
				"No Challengers Ranked in This Division Yet",
				"Play a ranked match in the Battle Arena to claim the #1 spot on the podium!",
				"trophy"
			)
		)
		leaderboard_text.text = "\n".join(lines)
		return

	var my_id := str(mp_client.current_player.get("player_id", ""))

	# Render Top 3 Podium Cards when viewing from rank #1
	if lb_current_offset == 0 and entries.size() >= 1 and lb_current_mode != "nearby":
		var top_count := mini(3, entries.size())
		for i in range(top_count):
			if entries[i] is Dictionary:
				lb_podium_container.add_child(_create_podium_card(entries[i], i + 1, my_id))

	for item in entries:
		if item is Dictionary:
			var d: Dictionary = item
			lines.append(
				"#%d  [b]%s[/b] (@%s) — [b]%d[/b] Trophies [%s] | W/L/D: %d/%d/%d (%.0f%%) | Best: %s" % [
					int(d.get("position", 0)),
					str(d.get("display_name", "")),
					str(d.get("username", "")),
					int(d.get("trophies", 0)),
					str(d.get("league", "Beginner")),
					int(d.get("wins", 0)),
					int(d.get("losses", 0)),
					int(d.get("draws", 0)),
					float(d.get("win_rate", 0.0)) * 100.0,
					str(d.get("best_score", "-"))
				]
			)
			var row_card := MultiplayerComponents.create_leaderboard_row(d, my_id, _inspect_player_profile)
			lb_rows_vbox.add_child(row_card)

	leaderboard_text.text = "\n".join(lines)


func _create_podium_card(entry: Dictionary, rank_pos: int, my_id: String) -> PanelContainer:
	var is_me := (str(entry.get("player_id", "")) == my_id)
	var border_col := Color(1.0, 0.86, 0.25) if rank_pos == 1 else (Color(0.84, 0.88, 0.95) if rank_pos == 2 else Color(0.88, 0.58, 0.32))
	var bg_col := Color(0.24, 0.20, 0.10, 0.96) if rank_pos == 1 else (Color(0.16, 0.20, 0.23, 0.95) if rank_pos == 2 else Color(0.22, 0.16, 0.12, 0.95))

	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.custom_minimum_size = Vector2(0, 118)
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 16, 3, 6, 4))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	card.add_child(hbox)

	var left_col := VBoxContainer.new()
	left_col.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_child(left_col)

	left_col.add_child(MultiplayerComponents.RankMedalControl.new(rank_pos))
	left_col.add_child(MultiplayerComponents.DogAvatarPortrait.new(str(entry.get("avatar", "dog_default")), 52.0, true))

	var info_col := VBoxContainer.new()
	info_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info_col.alignment = BoxContainer.ALIGNMENT_CENTER
	info_col.add_theme_constant_override("separation", 3)
	hbox.add_child(info_col)

	var champ_tag := Label.new()
	champ_tag.text = ("#1 ARENA CHAMPION" if rank_pos == 1 else ("#2 CHALLENGER" if rank_pos == 2 else "#3 CONTENDER")) + (" (YOU)" if is_me else "")
	champ_tag.add_theme_font_size_override("font_size", 12)
	champ_tag.add_theme_color_override("font_color", border_col.lightened(0.25))
	info_col.add_child(champ_tag)

	var dname := Label.new()
	dname.text = str(entry.get("display_name", entry.get("username", "Player")))
	dname.label_settings = MultiplayerTheme.make_title_settings(19, MultiplayerTheme.COL_TEXT_CREAM, 4)
	info_col.add_child(dname)

	var tr_row := HBoxContainer.new()
	tr_row.add_theme_constant_override("separation", 6)
	info_col.add_child(tr_row)
	tr_row.add_child(MultiplayerComponents.TrophyIconControl.new(20.0, 0.72))
	var tr_lbl := Label.new()
	tr_lbl.text = "%d Trophies • %s" % [int(entry.get("trophies", 0)), str(entry.get("league", "Beginner"))]
	tr_lbl.add_theme_font_size_override("font_size", 14)
	tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	tr_row.add_child(tr_lbl)

	var rec_lbl := Label.new()
	rec_lbl.text = "%d Wins (%.0f%%) • Best Score: %s" % [
		int(entry.get("wins", 0)),
		float(entry.get("win_rate", 0.0)) * 100.0,
		str(entry.get("best_score", "-")) if entry.get("best_score") != null else "-"
	]
	rec_lbl.add_theme_font_size_override("font_size", 12)
	rec_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	info_col.add_child(rec_lbl)

	return card


func _on_load_history() -> void:
	var res: Dictionary = await mp_client.fetch_my_history(25, 0)
	if !bool(res.get("success", false)):
		history_text.text = "Failed to load match history."
		return

	for c in hist_matches_vbox.get_children():
		c.queue_free()
	for c in hist_trophies_vbox.get_children():
		c.queue_free()

	var tr_arr: Array = res.get("trophy_history", []) if (res.get("trophy_history") is Array) else []
	cached_trophy_deltas.clear()
	for t in tr_arr:
		if t is Dictionary:
			var td: Dictionary = t
			cached_trophy_deltas[str(td.get("match_id", ""))] = int(td.get("trophy_change", 0))

	var matches_arr: Array = res.get("matches", []) if (res.get("matches") is Array) else []
	hist_summary_stats_lbl.text = "%d Recent Battles • %d Trophy Events" % [matches_arr.size(), tr_arr.size()]

	var lines: Array[String] = ["[b]Recent Competitive Matches[/b]"]
	var my_id := str(mp_client.current_player.get("player_id", ""))

	if matches_arr.is_empty():
		lines.append("No matches played yet.")
		hist_matches_vbox.add_child(
			MultiplayerComponents.create_empty_state_card(
				"No Battles Fought Yet",
				"Press Play Multiplayer Battle in the Arena tab to test your trained AI Dog against online challengers!",
				"dog"
			)
		)
	else:
		for m in matches_arr:
			if m is Dictionary:
				var md: Dictionary = m
				var p1: Dictionary = md.get("player_1", {})
				var p2: Dictionary = md.get("player_2", {})
				lines.append(
					"• Match %s [%s] — %s vs %s | Winner: %s | Map: %s" % [
						str(md.get("match_id", "")),
						str(md.get("status", "")),
						str(p1.get("username", "P1")),
						str(p2.get("username", "P2")),
						str(md.get("winner_id", "Draw/Pending")),
						str(md.get("map_id", ""))
					]
				)
				var card := MultiplayerComponents.create_battle_history_card(md, my_id, cached_trophy_deltas, _inspect_battle_details)
				hist_matches_vbox.add_child(card)

	lines.append("\n[b]Trophy History[/b]")
	if tr_arr.is_empty():
		lines.append("No trophy changes recorded yet.")
		var empty_tr := Label.new()
		empty_tr.text = "Complete your first ranked battle to track trophy progression here."
		empty_tr.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		empty_tr.add_theme_font_size_override("font_size", 14)
		empty_tr.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
		hist_trophies_vbox.add_child(empty_tr)
	else:
		for t in tr_arr:
			if t is Dictionary:
				var td: Dictionary = t
				var chg: int = int(td.get("trophy_change", 0))
				var sign_str: String = ("+" + str(chg)) if chg >= 0 else str(chg)
				lines.append(
					"• Match %s: %d -> %d (%s) at %s" % [
						str(td.get("match_id", "")),
						int(td.get("previous_trophies", 0)),
						int(td.get("new_trophies", 0)),
						sign_str,
						str(td.get("created_at", ""))
					]
				)
				var row_p := PanelContainer.new()
				row_p.add_theme_stylebox_override(
					"panel",
					MultiplayerTheme.make_pill_style(Color(0.12, 0.18, 0.14, 0.94), Color(0.38, 0.48, 0.40, 0.7), 10)
				)
				var r_hb := HBoxContainer.new()
				r_hb.add_theme_constant_override("separation", 8)
				row_p.add_child(r_hb)

				r_hb.add_child(MultiplayerComponents.TrophyIconControl.new(18.0, 0.65))

				var delta_lbl := Label.new()
				delta_lbl.text = sign_str
				delta_lbl.custom_minimum_size = Vector2(44, 0)
				delta_lbl.add_theme_font_size_override("font_size", 15)
				delta_lbl.add_theme_color_override(
					"font_color",
					MultiplayerTheme.COL_VICTORY if chg > 0 else (MultiplayerTheme.COL_DEFEAT if chg < 0 else MultiplayerTheme.COL_GOLD)
				)
				r_hb.add_child(delta_lbl)

				var span_lbl := Label.new()
				span_lbl.text = "%d -> %d Trophies" % [int(td.get("previous_trophies", 0)), int(td.get("new_trophies", 0))]
				span_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				span_lbl.add_theme_font_size_override("font_size", 13)
				span_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
				r_hb.add_child(span_lbl)

				var ts_lbl := Label.new()
				var raw_ts := str(td.get("created_at", ""))
				ts_lbl.text = raw_ts.substr(5, 11).replace("T", " ") if raw_ts.length() >= 16 else raw_ts
				ts_lbl.add_theme_font_size_override("font_size", 11)
				ts_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
				r_hb.add_child(ts_lbl)

				hist_trophies_vbox.add_child(row_p)

	history_text.text = "\n".join(lines)


func _inspect_battle_details(match_data: Dictionary) -> void:
	for c in inspect_body_vbox.get_children():
		c.queue_free()

	var mid := str(match_data.get("match_id", ""))
	inspect_title_lbl.text = "OFFICIAL BATTLE REPORT — %s" % mid

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}
	var s1: Dictionary = p1.get("submission", {}) if (p1.get("submission") is Dictionary) else {}
	var s2: Dictionary = p2.get("submission", {}) if (p2.get("submission") is Dictionary) else {}

	var meta_lbl := Label.new()
	meta_lbl.text = "Status: %s  •  Verification: %s  •  Map ID: %s" % [
		str(match_data.get("status", "COMPLETED")),
		str(match_data.get("verification_status", "VERIFIED")),
		str(match_data.get("map_id", ""))
	]
	meta_lbl.add_theme_font_size_override("font_size", 14)
	meta_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	inspect_body_vbox.add_child(meta_lbl)

	var compare_hbox := HBoxContainer.new()
	compare_hbox.add_theme_constant_override("separation", 16)
	compare_hbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspect_body_vbox.add_child(compare_hbox)

	for pair in [[p1, s1], [p2, s2]]:
		var p_info: Dictionary = pair[0]
		var s_info: Dictionary = pair[1]
		var col_card := PanelContainer.new()
		col_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col_card.add_theme_stylebox_override(
			"panel",
			MultiplayerTheme.make_card_style(Color(0.09, 0.15, 0.11, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 14, 2)
		)
		compare_hbox.add_child(col_card)
		var vb := VBoxContainer.new()
		vb.alignment = BoxContainer.ALIGNMENT_CENTER
		vb.add_theme_constant_override("separation", 6)
		col_card.add_child(vb)
		_populate_result_player_column(vb, "CHALLENGER REPORT", p_info, s_info, str(p_info.get("player_id", "")) == str(mp_client.current_player.get("player_id", "")))

	inspect_modal.visible = true


func _inspect_player_profile(username: String) -> void:
	var res: Dictionary = await mp_client.fetch_user_stats(username)
	if !bool(res.get("success", false)):
		return
	var p: Dictionary = res.get("player", {}) if (res.get("player") is Dictionary) else {}
	if p.is_empty():
		return

	for c in inspect_body_vbox.get_children():
		c.queue_free()

	inspect_title_lbl.text = "CHALLENGER SCOUTING REPORT — @%s" % str(p.get("username", username))
	var card := MultiplayerComponents.create_versus_player_card(p, str(p.get("player_id", "")) == str(mp_client.current_player.get("player_id", "")))
	inspect_body_vbox.add_child(card)

	var stats_lbl := Label.new()
	stats_lbl.text = "Matches: %d  |  Wins: %d  |  Losses: %d  |  Draws: %d  |  Best Score: %s  |  Total Bones: %d" % [
		int(p.get("total_matches", 0)),
		int(p.get("wins", 0)),
		int(p.get("losses", 0)),
		int(p.get("draws", 0)),
		str(p.get("best_score", "N/A")) if p.get("best_score") != null else "N/A",
		int(p.get("total_bones_collected", 0))
	]
	stats_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stats_lbl.add_theme_font_size_override("font_size", 15)
	stats_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	inspect_body_vbox.add_child(stats_lbl)

	inspect_modal.visible = true


func _on_home_pressed() -> void:
	solving_active = false
	is_searching_match = false
	get_tree().change_scene_to_file("res://scenes/landing_page.tscn")
