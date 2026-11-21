extends Control

# ==============================================================================
# DOOBYSCOO ONLINE MULTIPLAYER ARENA — GAME-FIRST COMPETITIVE UI
# ==============================================================================

var mp_client: MultiplayerClient
var rl_adapter: RLAdapter
var board: GameplayBoard
var score_manager: ScoreManager

# --- Header (Strictly 3 Elements: Home | Title | Server Status) ---
var conn_dot: MultiplayerComponents.ConnectionDotControl
var top_status_label: Label

# --- Endpoints Acceptor Controls ---
var server_url_input: LineEdit
var rl_url_input: LineEdit
var auth_server_url_input: LineEdit

# --- Auth View ---
var auth_panel: PanelContainer
var login_user_input: LineEdit
var login_pass_input: LineEdit
var reg_user_input: LineEdit
var reg_display_input: LineEdit
var reg_email_input: LineEdit
var reg_pass_input: LineEdit
var auth_feedback_label: Label

# --- Hub Content Stack ---
var hub_tabs: Control
var main_pages: Array[Control] = []
var current_tab_index: int = 0

# --- Page 0: Battle Arena (Two-Column Lobby + Live Battle + Overlays) ---
var arena_page: Control
var lobby_view: Control
var battle_view: Control
var matchmaking_overlay: PanelContainer
var versus_overlay: PanelContainer
var results_overlay: PanelContainer
var inspect_modal: PanelContainer

# Battle Arena Left Half (Matchmaking + Endpoints)
var arena_hero_avatar: MultiplayerComponents.DogAvatarPortrait
var arena_hero_league: MultiplayerComponents.LeagueBadgeControl
var find_match_btn: Button
var match_state_label: Label
var rl_dot: MultiplayerComponents.ConnectionDotControl
var lobby_agent_ready_lbl: Label
var online_players_dot: MultiplayerComponents.ConnectionDotControl
var online_players_lbl: Label
var _online_status_http: HTTPRequest
var _online_status_fetching: bool = false

# Battle Arena Right Half (Navigation Menu Cards)
var nav_profile_avatar: MultiplayerComponents.DogAvatarPortrait
var nav_profile_sub_lbl: Label
var nav_lb_sub_lbl: Label
var nav_log_sub_lbl: Label

# Matchmaking Overlay
var mm_radar: MultiplayerComponents.MatchmakingRadarControl
var mm_headline_lbl: Label
var mm_substatus_lbl: Label
var mm_timer_lbl: Label
var mm_player_summary_lbl: Label
var cancel_match_btn: Button

# Opponent Found (VS) Overlay
var vs_left_slot: VBoxContainer
var vs_right_slot: VBoxContainer
var vs_status_banner_lbl: Label
var vs_map_badge_lbl: Label

# Active Battle HUD
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
var arena_step_log_label: Label
var arena_result_summary_label: RichTextLabel
var learn_after_match_btn: Button
var battle_return_lobby_btn: Button

# Battle Results Overlay
var res_banner_icon: MultiplayerComponents.ResultBannerControl
var res_title_lbl: Label
var res_subtitle_lbl: Label
var res_you_card_box: VBoxContainer
var res_opp_card_box: VBoxContainer
var res_trophy_delta_lbl: Label
var res_xp_awarded_lbl: Label
var res_play_again_btn: Button
var res_back_lobby_btn: Button
var res_train_dog_btn: Button
var res_train_feedback_lbl: Label

# --- Page 1: Trainer Profile ---
var prof_avatar_large: MultiplayerComponents.DogAvatarPortrait
var prof_league_shield_large: MultiplayerComponents.LeagueBadgeControl
var prof_title_name_lbl: Label
var prof_handle_lbl: Label
var prof_level_badge_lbl: Label
var prof_xp_bar: ProgressBar
var prof_trophy_big_lbl: Label
var prof_league_tier_lbl: Label
var prof_league_bar: ProgressBar
var prof_next_league_lbl: Label
var prof_stat_rank: PanelContainer
var prof_stat_wins: PanelContainer
var prof_stat_winrate: PanelContainer
var prof_stat_best: PanelContainer
var edit_display_input: LineEdit
var edit_avatar_select: OptionButton
var avatar_choice_buttons: Array[Button] = []
var prof_save_feedback_lbl: Label

# --- Page 2: Leaderboards ---
var leaderboard_league_select: OptionButton
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

# --- Page 3: Battle Log ---
var hist_matches_vbox: VBoxContainer
var hist_trophies_vbox: VBoxContainer
var hist_summary_stats_lbl: Label

# --- Detail Inspect Modal ---
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
var animating_step: bool = false
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
	_setup_online_players_request()
	_check_local_rl_agent()
	_fetch_online_players_count()

	if mp_client.is_authenticated():
		_show_authenticated_view()
		mp_client.connect_websocket()
		await _refresh_all_player_data()
	else:
		_show_auth_view()


func _build_ui() -> void:
	# Soft meadow scrim over mainBG.png so cartoon landscape shines through cleanly
	var scrim := ColorRect.new()
	scrim.set_anchors_preset(Control.PRESET_FULL_RECT)
	scrim.color = Color(0.08, 0.16, 0.11, 0.28)
	scrim.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(scrim)

	var outer_margin := MarginContainer.new()
	outer_margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	outer_margin.add_theme_constant_override("margin_left", 22)
	outer_margin.add_theme_constant_override("margin_right", 22)
	outer_margin.add_theme_constant_override("margin_top", 14)
	outer_margin.add_theme_constant_override("margin_bottom", 16)
	add_child(outer_margin)

	var root_vbox := VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 14)
	outer_margin.add_child(root_vbox)

	_build_top_header(root_vbox)

	# Auth View
	auth_panel = PanelContainer.new()
	auth_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	auth_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 22, 3, 8, 5)
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
# 1. MULTIPLAYER HEADER (STRICTLY 3 ELEMENTS: HOME | TITLE | SERVER STATUS)
# ==============================================================================

func _build_top_header(parent: VBoxContainer) -> void:
	var header_panel := PanelContainer.new()
	header_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.12, 0.20, 0.15, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 18, 2, 5, 3)
	)
	parent.add_child(header_panel)

	var top_bar := HBoxContainer.new()
	top_bar.add_theme_constant_override("separation", 12)
	header_panel.add_child(top_bar)

	# Left slot (balanced width)
	var left_slot := HBoxContainer.new()
	left_slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_slot.alignment = BoxContainer.ALIGNMENT_BEGIN
	top_bar.add_child(left_slot)

	var home_btn := Button.new()
	home_btn.text = "Home"
	home_btn.custom_minimum_size = Vector2(110, 40)
	MultiplayerTheme.style_lavender_button(home_btn, 16)
	home_btn.pressed.connect(_on_home_pressed)
	left_slot.add_child(home_btn)

	# Center slot: Title
	var title_lbl := Label.new()
	title_lbl.text = "DOOBYSCOO ARENA"
	title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	title_lbl.label_settings = MultiplayerTheme.make_title_settings(28, MultiplayerTheme.COL_TEXT_CREAM, 6)
	top_bar.add_child(title_lbl)

	# Right slot: Compact Server Status Indicator
	var right_slot := HBoxContainer.new()
	right_slot.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_slot.alignment = BoxContainer.ALIGNMENT_END
	top_bar.add_child(right_slot)

	var srv_pill := PanelContainer.new()
	srv_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.94), Color(0.45, 0.58, 0.48, 0.75), 18)
	)
	right_slot.add_child(srv_pill)

	var srv_hbox := HBoxContainer.new()
	srv_hbox.add_theme_constant_override("separation", 8)
	srv_pill.add_child(srv_hbox)

	conn_dot = MultiplayerComponents.ConnectionDotControl.new()
	srv_hbox.add_child(conn_dot)

	top_status_label = Label.new()
	top_status_label.text = "Offline"
	top_status_label.add_theme_font_size_override("font_size", 14)
	top_status_label.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	srv_hbox.add_child(top_status_label)


func _switch_main_tab(index: int) -> void:
	current_tab_index = clampi(index, 0, main_pages.size() - 1)
	for i in range(main_pages.size()):
		var is_target: bool = (i == current_tab_index)
		main_pages[i].visible = is_target
		if is_target:
			main_pages[i].modulate.a = 0.0
			var tw := create_tween()
			tw.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
			tw.tween_property(main_pages[i], "modulate:a", 1.0, 0.14)


# ==============================================================================
# 2. AUTHENTICATION SCREEN (SIGN IN & CREATE ACCOUNT)
# ==============================================================================

func _build_auth_panel() -> void:
	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_top", 14)
	margin.add_theme_constant_override("margin_bottom", 14)
	auth_panel.add_child(margin)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 14)
	margin.add_child(vbox)

	var hero_hbox := HBoxContainer.new()
	hero_hbox.alignment = BoxContainer.ALIGNMENT_CENTER
	hero_hbox.add_theme_constant_override("separation", 16)
	vbox.add_child(hero_hbox)

	hero_hbox.add_child(MultiplayerComponents.DogAvatarPortrait.new("dog_default", 64.0, true))

	var hero_text := VBoxContainer.new()
	hero_text.alignment = BoxContainer.ALIGNMENT_CENTER
	hero_text.add_theme_constant_override("separation", 2)
	hero_hbox.add_child(hero_text)

	var welcome_lbl := Label.new()
	welcome_lbl.text = "ENTER THE ARENA"
	welcome_lbl.label_settings = MultiplayerTheme.make_title_settings(26, MultiplayerTheme.COL_TEXT_CREAM, 6)
	hero_text.add_child(welcome_lbl)

	var sub_welcome := Label.new()
	sub_welcome.text = "Sign in or create a trainer account to battle online and climb the leagues."
	sub_welcome.add_theme_font_size_override("font_size", 15)
	sub_welcome.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	hero_text.add_child(sub_welcome)

	hero_hbox.add_child(MultiplayerComponents.LeagueBadgeControl.new("Gold", 58.0, true))

	var cols := HBoxContainer.new()
	cols.add_theme_constant_override("separation", 22)
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(cols)

	# Login Card
	var login_card := PanelContainer.new()
	login_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	login_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.10, 0.17, 0.13, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 18, 2)
	)
	cols.add_child(login_card)

	var login_box := VBoxContainer.new()
	login_box.add_theme_constant_override("separation", 12)
	login_card.add_child(login_box)

	var login_hdr := Label.new()
	login_hdr.text = "SIGN IN"
	login_hdr.label_settings = MultiplayerTheme.make_title_settings(21, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	login_box.add_child(login_hdr)

	login_user_input = LineEdit.new()
	login_user_input.placeholder_text = "Username or Email"
	login_user_input.custom_minimum_size = Vector2(0, 42)
	MultiplayerTheme.style_line_edit(login_user_input, 16)
	login_box.add_child(login_user_input)

	login_pass_input = LineEdit.new()
	login_pass_input.placeholder_text = "Password"
	login_pass_input.secret = true
	login_pass_input.custom_minimum_size = Vector2(0, 42)
	MultiplayerTheme.style_line_edit(login_pass_input, 16)
	login_pass_input.text_submitted.connect(func(_t: String): _on_login_pressed())
	login_box.add_child(login_pass_input)

	var login_spacer := Control.new()
	login_spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	login_box.add_child(login_spacer)

	var login_btn := Button.new()
	login_btn.text = "PLAY ONLINE"
	login_btn.custom_minimum_size = Vector2(0, 52)
	MultiplayerTheme.style_primary_battle_button(login_btn, 20)
	login_btn.pressed.connect(_on_login_pressed)
	login_box.add_child(login_btn)

	# Register Card
	var reg_card := PanelContainer.new()
	reg_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reg_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.10, 0.17, 0.13, 0.96), MultiplayerTheme.COL_LAVENDER, 18, 2)
	)
	cols.add_child(reg_card)

	var reg_box := VBoxContainer.new()
	reg_box.add_theme_constant_override("separation", 10)
	reg_card.add_child(reg_box)

	var reg_hdr := Label.new()
	reg_hdr.text = "NEW TRAINER"
	reg_hdr.label_settings = MultiplayerTheme.make_title_settings(21, Color(0.86, 0.86, 1.0), 4)
	reg_box.add_child(reg_hdr)

	reg_user_input = LineEdit.new()
	reg_user_input.placeholder_text = "Username"
	reg_user_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_user_input, 15)
	reg_box.add_child(reg_user_input)

	reg_display_input = LineEdit.new()
	reg_display_input.placeholder_text = "Display Name"
	reg_display_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_display_input, 15)
	reg_box.add_child(reg_display_input)

	reg_email_input = LineEdit.new()
	reg_email_input.placeholder_text = "Email"
	reg_email_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_email_input, 15)
	reg_box.add_child(reg_email_input)

	reg_pass_input = LineEdit.new()
	reg_pass_input.placeholder_text = "Password (min 6 chars)"
	reg_pass_input.secret = true
	reg_pass_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(reg_pass_input, 15)
	reg_pass_input.text_submitted.connect(func(_t: String): _on_register_pressed())
	reg_box.add_child(reg_pass_input)

	var reg_btn := Button.new()
	reg_btn.text = "CREATE ACCOUNT"
	reg_btn.custom_minimum_size = Vector2(0, 48)
	MultiplayerTheme.style_lavender_button(reg_btn, 18)
	reg_btn.pressed.connect(_on_register_pressed)
	reg_box.add_child(reg_btn)

	# Compact Server Endpoint Bar on Auth Screen (synced with Arena Endpoints)
	var srv_row := HBoxContainer.new()
	srv_row.add_theme_constant_override("separation", 10)
	vbox.add_child(srv_row)

	var srv_lbl := Label.new()
	srv_lbl.text = "Server URL:"
	srv_lbl.add_theme_font_size_override("font_size", 14)
	srv_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	srv_row.add_child(srv_lbl)

	auth_server_url_input = LineEdit.new()
	auth_server_url_input.text = mp_client.server_url
	auth_server_url_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	auth_server_url_input.custom_minimum_size = Vector2(0, 34)
	MultiplayerTheme.style_line_edit(auth_server_url_input, 14)
	srv_row.add_child(auth_server_url_input)

	auth_feedback_label = Label.new()
	auth_feedback_label.text = ""
	auth_feedback_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	auth_feedback_label.add_theme_font_size_override("font_size", 14)
	auth_feedback_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	vbox.add_child(auth_feedback_label)


# ==============================================================================
# 3. PAGE 0: BATTLE ARENA (TWO-COLUMN LAYOUT + LIVE BATTLE VIEW)
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
	lobby_view.add_theme_constant_override("separation", 20)
	arena_page.add_child(lobby_view)

	# --- LEFT HALF: BATTLE ARENA (MATCHMAKING + ENDPOINTS ACCEPTOR) ---
	var left_arena := PanelContainer.new()
	left_arena.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_arena.size_flags_stretch_ratio = 1.05
	left_arena.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD, 22, 3, 10, 6)
	)
	lobby_view.add_child(left_arena)

	var left_vbox := VBoxContainer.new()
	left_vbox.add_theme_constant_override("separation", 14)
	left_arena.add_child(left_vbox)

	var top_spacer := Control.new()
	top_spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	top_spacer.size_flags_stretch_ratio = 0.4
	left_vbox.add_child(top_spacer)

	# Arena Hero Showcase (Avatar + League Shield)
	var hero_icons := HBoxContainer.new()
	hero_icons.alignment = BoxContainer.ALIGNMENT_CENTER
	hero_icons.add_theme_constant_override("separation", 18)
	left_vbox.add_child(hero_icons)

	arena_hero_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 86.0, true)
	hero_icons.add_child(arena_hero_avatar)

	arena_hero_league = MultiplayerComponents.LeagueBadgeControl.new("Beginner", 74.0, true)
	hero_icons.add_child(arena_hero_league)

	var stage_title := Label.new()
	stage_title.text = "BATTLE ARENA"
	stage_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stage_title.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_TEXT_CREAM, 7)
	left_vbox.add_child(stage_title)

	var stage_sub := Label.new()
	stage_sub.text = "1v1 Ranked Maze Battle  •  Lowest Score Wins"
	stage_sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	stage_sub.add_theme_font_size_override("font_size", 15)
	stage_sub.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	left_vbox.add_child(stage_sub)

	# Primary Play Multiplayer Battle Button
	var play_margin := MarginContainer.new()
	play_margin.add_theme_constant_override("margin_left", 24)
	play_margin.add_theme_constant_override("margin_right", 24)
	play_margin.add_theme_constant_override("margin_top", 8)
	play_margin.add_theme_constant_override("margin_bottom", 4)
	left_vbox.add_child(play_margin)

	find_match_btn = Button.new()
	find_match_btn.text = "PLAY MULTIPLAYER BATTLE"
	find_match_btn.custom_minimum_size = Vector2(0, 74)
	MultiplayerTheme.style_primary_battle_button(find_match_btn, 24)
	find_match_btn.pressed.connect(_on_find_match_pressed)
	play_margin.add_child(find_match_btn)

	# Concise Matchmaking / Readiness Feedback
	match_state_label = Label.new()
	match_state_label.text = "Ready to battle!"
	match_state_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	match_state_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	match_state_label.add_theme_font_size_override("font_size", 15)
	match_state_label.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	left_vbox.add_child(match_state_label)

	var rl_pill_center := CenterContainer.new()
	left_vbox.add_child(rl_pill_center)

	var rl_pill := PanelContainer.new()
	rl_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.14, 0.10, 0.90), Color(0.45, 0.58, 0.48, 0.7), 16)
	)
	rl_pill_center.add_child(rl_pill)

	var rl_hbox := HBoxContainer.new()
	rl_hbox.add_theme_constant_override("separation", 8)
	rl_pill.add_child(rl_hbox)

	rl_dot = MultiplayerComponents.ConnectionDotControl.new()
	rl_hbox.add_child(rl_dot)

	lobby_agent_ready_lbl = Label.new()
	lobby_agent_ready_lbl.text = "Checking AI Dog..."
	lobby_agent_ready_lbl.add_theme_font_size_override("font_size", 13)
	lobby_agent_ready_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	rl_hbox.add_child(lobby_agent_ready_lbl)

	# Subtle Real Online Player Count directly underneath AI Dog Ready status
	var online_row_center := CenterContainer.new()
	left_vbox.add_child(online_row_center)

	var online_hbox := HBoxContainer.new()
	online_hbox.add_theme_constant_override("separation", 6)
	online_row_center.add_child(online_hbox)

	online_players_dot = MultiplayerComponents.ConnectionDotControl.new()
	online_players_dot.status_color = MultiplayerTheme.COL_GOLD
	online_hbox.add_child(online_players_dot)

	online_players_lbl = Label.new()
	online_players_lbl.text = "Players Online: ..."
	online_players_lbl.add_theme_font_size_override("font_size", 13)
	online_players_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	online_hbox.add_child(online_players_lbl)

	var mid_spacer := Control.new()
	mid_spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	left_vbox.add_child(mid_spacer)

	# Compact Endpoints Acceptor Card (Preserved on Battle Arena for testing)
	var ep_card := PanelContainer.new()
	ep_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.08, 0.14, 0.10, 0.92), Color(0.42, 0.54, 0.45, 0.72), 16, 2)
	)
	left_vbox.add_child(ep_card)

	var ep_vbox := VBoxContainer.new()
	ep_vbox.add_theme_constant_override("separation", 8)
	ep_card.add_child(ep_vbox)

	var ep_title := Label.new()
	ep_title.text = "SERVER ENDPOINTS"
	ep_title.add_theme_font_size_override("font_size", 12)
	ep_title.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	ep_vbox.add_child(ep_title)

	var ep_row := HBoxContainer.new()
	ep_row.add_theme_constant_override("separation", 8)
	ep_vbox.add_child(ep_row)

	server_url_input = LineEdit.new()
	server_url_input.text = mp_client.server_url
	server_url_input.placeholder_text = "Server URL"
	server_url_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	server_url_input.custom_minimum_size = Vector2(0, 34)
	MultiplayerTheme.style_line_edit(server_url_input, 13)
	ep_row.add_child(server_url_input)

	rl_url_input = LineEdit.new()
	rl_url_input.text = MazeSession.server_url
	rl_url_input.placeholder_text = "RL Agent URL"
	rl_url_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rl_url_input.custom_minimum_size = Vector2(0, 34)
	MultiplayerTheme.style_line_edit(rl_url_input, 13)
	ep_row.add_child(rl_url_input)

	var apply_urls_btn := Button.new()
	apply_urls_btn.text = "Apply"
	apply_urls_btn.custom_minimum_size = Vector2(88, 34)
	MultiplayerTheme.style_green_button(apply_urls_btn, 14)
	apply_urls_btn.pressed.connect(_on_apply_endpoints_pressed)
	ep_row.add_child(apply_urls_btn)

	# --- RIGHT HALF: MULTIPLAYER NAVIGATION CARDS ---
	var right_nav_vbox := VBoxContainer.new()
	right_nav_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_nav_vbox.size_flags_stretch_ratio = 0.95
	right_nav_vbox.add_theme_constant_override("separation", 18)
	lobby_view.add_child(right_nav_vbox)

	# 1. Trainer Profile Card
	nav_profile_avatar = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 62.0, true)
	var prof_card_res: Dictionary = MultiplayerComponents.create_nav_menu_card(
		"TRAINER PROFILE",
		"Customize avatar & view league rank",
		Color(0.24, 0.56, 0.36, 0.96),
		Color(0.62, 0.92, 0.70, 1.0),
		nav_profile_avatar,
		func(): _switch_main_tab(1)
	)
	nav_profile_sub_lbl = prof_card_res["subtitle_label"] as Label
	right_nav_vbox.add_child(prof_card_res["button"] as Button)

	# 2. Leaderboards Card
	var lb_card_res: Dictionary = MultiplayerComponents.create_nav_menu_card(
		"LEADERBOARDS",
		"Climb global & league rankings",
		Color(0.54, 0.52, 0.76, 0.96),
		Color(0.84, 0.82, 0.98, 1.0),
		MultiplayerComponents.TrophyIconControl.new(54.0, 1.75),
		func():
			_switch_main_tab(2)
			_on_load_global_leaderboard()
	)
	nav_lb_sub_lbl = lb_card_res["subtitle_label"] as Label
	right_nav_vbox.add_child(lb_card_res["button"] as Button)

	# 3. Battle Log Card
	var log_card_res: Dictionary = MultiplayerComponents.create_nav_menu_card(
		"BATTLE LOG",
		"Recent matches & trophy history",
		Color(0.18, 0.36, 0.28, 0.96),
		MultiplayerTheme.COL_GOLD_BORDER,
		MultiplayerComponents.BattleScrollIconControl.new(54.0, 1.5),
		func():
			_switch_main_tab(3)
			_on_load_history()
	)
	nav_log_sub_lbl = log_card_res["subtitle_label"] as Label
	right_nav_vbox.add_child(log_card_res["button"] as Button)


func _build_battle_view() -> void:
	battle_view = HBoxContainer.new()
	battle_view.set_anchors_preset(Control.PRESET_FULL_RECT)
	battle_view.add_theme_constant_override("separation", 18)
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
		MultiplayerTheme.make_panel_style(Color(0.10, 0.17, 0.13, 0.96), MultiplayerTheme.COL_GOLD, 20, 3, 8, 4)
	)
	battle_view.add_child(board_frame)

	board = GameplayBoard.new()
	board.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	board.size_flags_vertical = Control.SIZE_EXPAND_FILL
	board_frame.add_child(board)

	# Right: Clean Competitive Battle HUD
	var hud_panel := PanelContainer.new()
	hud_panel.custom_minimum_size = Vector2(390, 0)
	hud_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hud_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hud_panel.size_flags_stretch_ratio = 1.0
	hud_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 20, 3, 8, 5)
	)
	battle_view.add_child(hud_panel)

	var hud_vbox := VBoxContainer.new()
	hud_vbox.add_theme_constant_override("separation", 12)
	hud_panel.add_child(hud_vbox)

	var top_hud_row := HBoxContainer.new()
	top_hud_row.add_theme_constant_override("separation", 10)
	hud_vbox.add_child(top_hud_row)

	var live_tag := Label.new()
	live_tag.text = "LIVE BATTLE"
	live_tag.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	live_tag.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_hud_row.add_child(live_tag)

	var timer_pill := PanelContainer.new()
	timer_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 14)
	)
	top_hud_row.add_child(timer_pill)

	battle_timer_lbl = Label.new()
	battle_timer_lbl.text = "10:00"
	battle_timer_lbl.add_theme_font_size_override("font_size", 15)
	battle_timer_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	timer_pill.add_child(battle_timer_lbl)

	# Versus Duel Bar
	var duel_card := PanelContainer.new()
	duel_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.15, 0.11, 0.96), Color(0.55, 0.68, 0.56, 0.85), 16, 2)
	)
	hud_vbox.add_child(duel_card)

	var duel_hbox := HBoxContainer.new()
	duel_hbox.add_theme_constant_override("separation", 10)
	duel_card.add_child(duel_hbox)

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

	# Opponent Live Status Pill
	var opp_status_card := PanelContainer.new()
	opp_status_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.18, 0.14, 0.15, 0.94), Color(0.84, 0.44, 0.40, 0.8), 14)
	)
	hud_vbox.add_child(opp_status_card)

	battle_opp_status_pill = Label.new()
	battle_opp_status_pill.text = "Opponent solving maze..."
	battle_opp_status_pill.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	battle_opp_status_pill.add_theme_font_size_override("font_size", 14)
	battle_opp_status_pill.add_theme_color_override("font_color", Color(1.0, 0.86, 0.80))
	opp_status_card.add_child(battle_opp_status_pill)

	# Live Scoreboard Cards
	var live_score_row := HBoxContainer.new()
	live_score_row.add_theme_constant_override("separation", 8)
	hud_vbox.add_child(live_score_row)

	var sc_card := MultiplayerComponents.create_stat_badge("SCORE", "0", Color(0.45, 0.98, 0.62))
	battle_score_val_lbl = sc_card.get_child(0).get_child(1) as Label
	live_score_row.add_child(sc_card)

	var st_card := MultiplayerComponents.create_stat_badge("STEPS", "0 / 300", MultiplayerTheme.COL_TEXT_CREAM)
	battle_steps_val_lbl = st_card.get_child(0).get_child(1) as Label
	live_score_row.add_child(st_card)

	var bn_card := MultiplayerComponents.create_stat_badge("BONES", "0 / 5", MultiplayerTheme.COL_GOLD_BRIGHT)
	battle_bones_val_lbl = bn_card.get_child(0).get_child(1) as Label
	live_score_row.add_child(bn_card)

	# Progress Bars
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
	MultiplayerTheme.style_progress_bar(battle_steps_bar, Color(0.38, 0.84, 0.56))
	bars_vbox.add_child(battle_steps_bar)

	arena_step_log_label = Label.new()
	arena_step_log_label.text = "Steps: 0  •  Bones: 0/5  •  Score: 0"
	arena_step_log_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	arena_step_log_label.add_theme_font_size_override("font_size", 14)
	arena_step_log_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	hud_vbox.add_child(arena_step_log_label)

	var feed_panel := PanelContainer.new()
	feed_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	feed_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.08, 0.13, 0.10, 0.94), Color(0.38, 0.50, 0.42, 0.7), 14, 2)
	)
	hud_vbox.add_child(feed_panel)

	arena_result_summary_label = RichTextLabel.new()
	arena_result_summary_label.bbcode_enabled = true
	arena_result_summary_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	arena_result_summary_label.text = "Your dog is solving the arena maze!"
	feed_panel.add_child(arena_result_summary_label)

	var btm_row := HBoxContainer.new()
	btm_row.add_theme_constant_override("separation", 10)
	hud_vbox.add_child(btm_row)

	learn_after_match_btn = Button.new()
	learn_after_match_btn.text = "Train Dog on Maze"
	learn_after_match_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	learn_after_match_btn.custom_minimum_size = Vector2(0, 44)
	learn_after_match_btn.disabled = true
	MultiplayerTheme.style_lavender_button(learn_after_match_btn, 15)
	learn_after_match_btn.pressed.connect(_on_learn_after_match_pressed)
	btm_row.add_child(learn_after_match_btn)

	battle_return_lobby_btn = Button.new()
	battle_return_lobby_btn.text = "Back to Arena"
	battle_return_lobby_btn.custom_minimum_size = Vector2(142, 44)
	MultiplayerTheme.style_subtle_button(battle_return_lobby_btn, 15)
	battle_return_lobby_btn.pressed.connect(_on_back_to_lobby_pressed)
	btm_row.add_child(battle_return_lobby_btn)


# ==============================================================================
# 4. MATCHMAKING, VS SHOWDOWN & BATTLE RESULTS OVERLAYS
# ==============================================================================

func _build_matchmaking_overlay() -> void:
	matchmaking_overlay = PanelContainer.new()
	matchmaking_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	matchmaking_overlay.visible = false
	matchmaking_overlay.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.06, 0.11, 0.08, 0.92), MultiplayerTheme.COL_GOLD, 22, 3, 12, 6)
	)
	hub_tabs.add_child(matchmaking_overlay)

	var center := CenterContainer.new()
	matchmaking_overlay.add_child(center)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(520, 430)
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
	mm_substatus_lbl.text = "Searching for a challenger in your league..."
	mm_substatus_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_substatus_lbl.add_theme_font_size_override("font_size", 15)
	mm_substatus_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	vbox.add_child(mm_substatus_lbl)

	var radar_center := CenterContainer.new()
	vbox.add_child(radar_center)
	mm_radar = MultiplayerComponents.MatchmakingRadarControl.new()
	radar_center.add_child(mm_radar)

	var info_pill := PanelContainer.new()
	info_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.13, 0.10, 0.95), MultiplayerTheme.COL_GOLD_BORDER, 16)
	)
	vbox.add_child(info_pill)

	var info_vbox := VBoxContainer.new()
	info_vbox.add_theme_constant_override("separation", 4)
	info_pill.add_child(info_vbox)

	mm_player_summary_lbl = Label.new()
	mm_player_summary_lbl.text = "Trainer  •  0 Trophies"
	mm_player_summary_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_player_summary_lbl.add_theme_font_size_override("font_size", 15)
	mm_player_summary_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	info_vbox.add_child(mm_player_summary_lbl)

	mm_timer_lbl = Label.new()
	mm_timer_lbl.text = "00:00"
	mm_timer_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	mm_timer_lbl.add_theme_font_size_override("font_size", 16)
	mm_timer_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	info_vbox.add_child(mm_timer_lbl)

	cancel_match_btn = Button.new()
	cancel_match_btn.text = "CANCEL"
	cancel_match_btn.custom_minimum_size = Vector2(210, 48)
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
		MultiplayerTheme.make_panel_style(Color(0.06, 0.11, 0.08, 0.95), MultiplayerTheme.COL_GOLD, 22, 4, 14, 6)
	)
	hub_tabs.add_child(versus_overlay)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 18)
	versus_overlay.add_child(vbox)

	vs_status_banner_lbl = Label.new()
	vs_status_banner_lbl.text = "OPPONENT FOUND!"
	vs_status_banner_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_status_banner_lbl.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_GOLD_BRIGHT, 7)
	vbox.add_child(vs_status_banner_lbl)

	var cards_row := HBoxContainer.new()
	cards_row.alignment = BoxContainer.ALIGNMENT_CENTER
	cards_row.add_theme_constant_override("separation", 28)
	vbox.add_child(cards_row)

	vs_left_slot = VBoxContainer.new()
	vs_left_slot.custom_minimum_size = Vector2(290, 240)
	cards_row.add_child(vs_left_slot)

	var emblem_holder := CenterContainer.new()
	cards_row.add_child(emblem_holder)
	emblem_holder.add_child(MultiplayerComponents.VsEmblemControl.new())

	var vs_txt := Label.new()
	vs_txt.text = "VS"
	vs_txt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vs_txt.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_TEXT_CREAM, 8)
	emblem_holder.add_child(vs_txt)

	vs_right_slot = VBoxContainer.new()
	vs_right_slot.custom_minimum_size = Vector2(290, 240)
	cards_row.add_child(vs_right_slot)

	vs_map_badge_lbl = Label.new()
	vs_map_badge_lbl.text = "Entering Arena..."
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
		MultiplayerTheme.make_panel_style(Color(0.06, 0.11, 0.08, 0.93), MultiplayerTheme.COL_GOLD, 22, 3, 12, 6)
	)
	hub_tabs.add_child(results_overlay)

	var center := CenterContainer.new()
	results_overlay.add_child(center)

	var modal := PanelContainer.new()
	modal.custom_minimum_size = Vector2(720, 450)
	modal.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 24, 3, 12, 6)
	)
	center.add_child(modal)

	var vbox := VBoxContainer.new()
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_theme_constant_override("separation", 12)
	modal.add_child(vbox)

	var banner_center := CenterContainer.new()
	vbox.add_child(banner_center)
	res_banner_icon = MultiplayerComponents.ResultBannerControl.new()
	banner_center.add_child(res_banner_icon)

	res_title_lbl = Label.new()
	res_title_lbl.text = "VICTORY!"
	res_title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(36, MultiplayerTheme.COL_VICTORY, 7)
	vbox.add_child(res_title_lbl)

	res_subtitle_lbl = Label.new()
	res_subtitle_lbl.text = "Your dog finished with the winning score!"
	res_subtitle_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	res_subtitle_lbl.add_theme_font_size_override("font_size", 15)
	res_subtitle_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_LIGHT)
	vbox.add_child(res_subtitle_lbl)

	var rewards_row := HBoxContainer.new()
	rewards_row.alignment = BoxContainer.ALIGNMENT_CENTER
	rewards_row.add_theme_constant_override("separation", 14)
	vbox.add_child(rewards_row)

	var tr_pill := PanelContainer.new()
	tr_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.14, 0.10, 0.96), MultiplayerTheme.COL_GOLD, 16)
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
		MultiplayerTheme.make_pill_style(Color(0.08, 0.14, 0.10, 0.96), Color(0.45, 0.78, 0.96), 16)
	)
	rewards_row.add_child(xp_pill)

	res_xp_awarded_lbl = Label.new()
	res_xp_awarded_lbl.text = "+75 XP"
	res_xp_awarded_lbl.add_theme_font_size_override("font_size", 16)
	res_xp_awarded_lbl.add_theme_color_override("font_color", Color(0.65, 0.90, 1.0))
	xp_pill.add_child(res_xp_awarded_lbl)

	var compare_row := HBoxContainer.new()
	compare_row.add_theme_constant_override("separation", 16)
	vbox.add_child(compare_row)

	var you_panel := PanelContainer.new()
	you_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	you_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.11, 0.19, 0.14, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2)
	)
	compare_row.add_child(you_panel)
	res_you_card_box = VBoxContainer.new()
	res_you_card_box.add_theme_constant_override("separation", 4)
	you_panel.add_child(res_you_card_box)

	var opp_panel := PanelContainer.new()
	opp_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	opp_panel.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.19, 0.13, 0.14, 0.96), Color(0.86, 0.46, 0.42), 16, 2)
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

	var act_row := HBoxContainer.new()
	act_row.alignment = BoxContainer.ALIGNMENT_CENTER
	act_row.add_theme_constant_override("separation", 14)
	vbox.add_child(act_row)

	res_play_again_btn = Button.new()
	res_play_again_btn.text = "PLAY AGAIN"
	res_play_again_btn.custom_minimum_size = Vector2(190, 48)
	MultiplayerTheme.style_primary_battle_button(res_play_again_btn, 19)
	res_play_again_btn.pressed.connect(_on_play_again_from_results)
	act_row.add_child(res_play_again_btn)

	res_train_dog_btn = Button.new()
	res_train_dog_btn.text = "TRAIN DOG"
	res_train_dog_btn.custom_minimum_size = Vector2(180, 48)
	MultiplayerTheme.style_lavender_button(res_train_dog_btn, 16)
	res_train_dog_btn.pressed.connect(_on_learn_after_match_pressed)
	act_row.add_child(res_train_dog_btn)

	res_back_lobby_btn = Button.new()
	res_back_lobby_btn.text = "ARENA"
	res_back_lobby_btn.custom_minimum_size = Vector2(130, 48)
	MultiplayerTheme.style_subtle_button(res_back_lobby_btn, 16)
	res_back_lobby_btn.pressed.connect(_on_back_to_lobby_pressed)
	act_row.add_child(res_back_lobby_btn)


# ==============================================================================
# 5. PAGE 1: TRAINER PROFILE (COMPETITIVE PROFILE & CUSTOMIZATION)
# ==============================================================================

func _build_profile_tab() -> void:
	var prof_root := PanelContainer.new()
	prof_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	prof_root.visible = false
	prof_root.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 22, 3, 8, 5)
	)
	hub_tabs.add_child(prof_root)
	main_pages.append(prof_root)

	var outer_vbox := VBoxContainer.new()
	outer_vbox.add_theme_constant_override("separation", 14)
	prof_root.add_child(outer_vbox)

	# Sub-page top bar: Back to Arena | Title | Refresh & Log Out
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 12)
	outer_vbox.add_child(top_row)

	var back_btn := Button.new()
	back_btn.text = "<- Arena"
	back_btn.custom_minimum_size = Vector2(118, 38)
	MultiplayerTheme.style_subtle_button(back_btn, 15)
	back_btn.pressed.connect(func(): _switch_main_tab(0))
	top_row.add_child(back_btn)

	var page_title := Label.new()
	page_title.text = "TRAINER PROFILE"
	page_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	page_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	page_title.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_row.add_child(page_title)

	var ref_btn := Button.new()
	ref_btn.text = "Refresh"
	ref_btn.custom_minimum_size = Vector2(96, 38)
	MultiplayerTheme.style_subtle_button(ref_btn, 14)
	ref_btn.pressed.connect(_refresh_all_player_data)
	top_row.add_child(ref_btn)

	var logout_btn := Button.new()
	logout_btn.text = "Log Out"
	logout_btn.custom_minimum_size = Vector2(96, 38)
	MultiplayerTheme.style_danger_button(logout_btn, 14)
	logout_btn.pressed.connect(_on_logout_pressed)
	top_row.add_child(logout_btn)

	# Main Two-Column Profile Content
	var cols := HBoxContainer.new()
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols.add_theme_constant_override("separation", 18)
	outer_vbox.add_child(cols)

	# Left Column: Identity & Customization
	var left_col := VBoxContainer.new()
	left_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_col.size_flags_stretch_ratio = 0.92
	left_col.add_theme_constant_override("separation", 12)
	cols.add_child(left_col)

	var id_card := PanelContainer.new()
	id_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.16, 0.12, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 18, 2)
	)
	left_col.add_child(id_card)

	var id_vbox := VBoxContainer.new()
	id_vbox.add_theme_constant_override("separation", 10)
	id_card.add_child(id_vbox)

	var showcase_row := HBoxContainer.new()
	showcase_row.add_theme_constant_override("separation", 16)
	id_vbox.add_child(showcase_row)

	prof_avatar_large = MultiplayerComponents.DogAvatarPortrait.new("dog_default", 86.0, true)
	showcase_row.add_child(prof_avatar_large)

	var name_col := VBoxContainer.new()
	name_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_col.alignment = BoxContainer.ALIGNMENT_CENTER
	name_col.add_theme_constant_override("separation", 4)
	showcase_row.add_child(name_col)

	prof_title_name_lbl = Label.new()
	prof_title_name_lbl.text = "Trainer"
	prof_title_name_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_TEXT_CREAM, 5)
	name_col.add_child(prof_title_name_lbl)

	prof_handle_lbl = Label.new()
	prof_handle_lbl.text = "@trainer"
	prof_handle_lbl.add_theme_font_size_override("font_size", 14)
	prof_handle_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	name_col.add_child(prof_handle_lbl)

	prof_level_badge_lbl = Label.new()
	prof_level_badge_lbl.text = "Level 1"
	prof_level_badge_lbl.add_theme_font_size_override("font_size", 15)
	prof_level_badge_lbl.add_theme_color_override("font_color", Color(0.58, 0.88, 1.0))
	name_col.add_child(prof_level_badge_lbl)

	prof_xp_bar = ProgressBar.new()
	prof_xp_bar.custom_minimum_size = Vector2(0, 14)
	prof_xp_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(prof_xp_bar, Color(0.36, 0.78, 0.96))
	id_vbox.add_child(prof_xp_bar)

	# Customization Card
	var edit_card := PanelContainer.new()
	edit_card.size_flags_vertical = Control.SIZE_EXPAND_FILL
	edit_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.16, 0.12, 0.95), Color(0.45, 0.58, 0.48, 0.8), 18, 2)
	)
	left_col.add_child(edit_card)

	var ed_vbox := VBoxContainer.new()
	ed_vbox.add_theme_constant_override("separation", 10)
	edit_card.add_child(ed_vbox)

	var ed_hdr := Label.new()
	ed_hdr.text = "CUSTOMIZE TRAINER"
	ed_hdr.label_settings = MultiplayerTheme.make_title_settings(17, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	ed_vbox.add_child(ed_hdr)

	edit_display_input = LineEdit.new()
	edit_display_input.placeholder_text = "Display Name"
	edit_display_input.custom_minimum_size = Vector2(0, 38)
	MultiplayerTheme.style_line_edit(edit_display_input, 16)
	ed_vbox.add_child(edit_display_input)

	edit_avatar_select = OptionButton.new()
	edit_avatar_select.visible = false
	var avatar_ids: Array[String] = ["dog_default", "dog_golden", "dog_husky", "dog_cyber"]
	var avatar_labels: Array[String] = ["Classic", "Golden", "Husky", "Cyber"]
	for i in range(avatar_ids.size()):
		edit_avatar_select.add_item(avatar_ids[i], i)
	ed_vbox.add_child(edit_avatar_select)

	var av_grid := HBoxContainer.new()
	av_grid.add_theme_constant_override("separation", 8)
	ed_vbox.add_child(av_grid)

	avatar_choice_buttons.clear()
	for i in range(avatar_ids.size()):
		var av_btn := Button.new()
		av_btn.custom_minimum_size = Vector2(74, 78)
		av_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var idx: int = i
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

	var save_prof_btn := Button.new()
	save_prof_btn.text = "SAVE PROFILE"
	save_prof_btn.custom_minimum_size = Vector2(0, 44)
	MultiplayerTheme.style_green_button(save_prof_btn, 17)
	save_prof_btn.pressed.connect(_on_save_profile_pressed)
	ed_vbox.add_child(save_prof_btn)

	prof_save_feedback_lbl = Label.new()
	prof_save_feedback_lbl.text = ""
	prof_save_feedback_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prof_save_feedback_lbl.add_theme_font_size_override("font_size", 13)
	prof_save_feedback_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_VICTORY)
	ed_vbox.add_child(prof_save_feedback_lbl)

	# Right Column: League Progression & Competitive Performance Cards
	var right_col := VBoxContainer.new()
	right_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_col.size_flags_stretch_ratio = 1.08
	right_col.add_theme_constant_override("separation", 14)
	cols.add_child(right_col)

	var lg_banner := PanelContainer.new()
	lg_banner.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.16, 0.12, 0.96), MultiplayerTheme.COL_GOLD, 18, 2)
	)
	right_col.add_child(lg_banner)

	var lg_vbox := VBoxContainer.new()
	lg_vbox.add_theme_constant_override("separation", 10)
	lg_banner.add_child(lg_vbox)

	var lg_hbox := HBoxContainer.new()
	lg_hbox.add_theme_constant_override("separation", 16)
	lg_vbox.add_child(lg_hbox)

	prof_league_shield_large = MultiplayerComponents.LeagueBadgeControl.new("Beginner", 74.0, true)
	lg_hbox.add_child(prof_league_shield_large)

	var lg_info := VBoxContainer.new()
	lg_info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lg_info.alignment = BoxContainer.ALIGNMENT_CENTER
	lg_info.add_theme_constant_override("separation", 4)
	lg_hbox.add_child(lg_info)

	prof_league_tier_lbl = Label.new()
	prof_league_tier_lbl.text = "BEGINNER LEAGUE"
	prof_league_tier_lbl.label_settings = MultiplayerTheme.make_title_settings(22, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	lg_info.add_child(prof_league_tier_lbl)

	var tr_line := HBoxContainer.new()
	tr_line.add_theme_constant_override("separation", 6)
	lg_info.add_child(tr_line)
	tr_line.add_child(MultiplayerComponents.TrophyIconControl.new(22.0, 0.8))

	prof_trophy_big_lbl = Label.new()
	prof_trophy_big_lbl.text = "0 Trophies"
	prof_trophy_big_lbl.add_theme_font_size_override("font_size", 18)
	prof_trophy_big_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	tr_line.add_child(prof_trophy_big_lbl)

	prof_league_bar = ProgressBar.new()
	prof_league_bar.custom_minimum_size = Vector2(0, 16)
	prof_league_bar.show_percentage = false
	MultiplayerTheme.style_progress_bar(prof_league_bar, MultiplayerTheme.COL_GOLD)
	lg_vbox.add_child(prof_league_bar)

	prof_next_league_lbl = Label.new()
	prof_next_league_lbl.text = "Next: Bronze League"
	prof_next_league_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	prof_next_league_lbl.add_theme_font_size_override("font_size", 13)
	prof_next_league_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	lg_vbox.add_child(prof_next_league_lbl)

	# Visual 7-League Road Strip
	var road_card := PanelContainer.new()
	road_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.15, 0.11, 0.92), Color(0.42, 0.54, 0.45, 0.72), 16, 2)
	)
	right_col.add_child(road_card)

	var road_row := HBoxContainer.new()
	road_row.alignment = BoxContainer.ALIGNMENT_CENTER
	road_row.add_theme_constant_override("separation", 6)
	road_card.add_child(road_row)

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

	# 4 Clean Competitive Stat Cards
	var stats_grid := GridContainer.new()
	stats_grid.columns = 2
	stats_grid.size_flags_vertical = Control.SIZE_EXPAND_FILL
	stats_grid.add_theme_constant_override("h_separation", 12)
	stats_grid.add_theme_constant_override("v_separation", 12)
	right_col.add_child(stats_grid)

	prof_stat_rank = MultiplayerComponents.create_stat_badge("GLOBAL RANK", "#-", MultiplayerTheme.COL_GOLD_BRIGHT)
	prof_stat_wins = MultiplayerComponents.create_stat_badge("VICTORIES", "0", MultiplayerTheme.COL_VICTORY)
	prof_stat_winrate = MultiplayerComponents.create_stat_badge("WIN RATE", "0%", Color(0.55, 0.88, 1.0))
	prof_stat_best = MultiplayerComponents.create_stat_badge("BEST SCORE", "-", Color(0.55, 0.96, 0.68))

	stats_grid.add_child(prof_stat_rank)
	stats_grid.add_child(prof_stat_wins)
	stats_grid.add_child(prof_stat_winrate)
	stats_grid.add_child(prof_stat_best)


func _select_avatar_option(index: int) -> void:
	edit_avatar_select.selected = index
	var avatar_id: String = edit_avatar_select.get_item_text(index)
	prof_avatar_large.avatar_id = avatar_id
	for i in range(avatar_choice_buttons.size()):
		if i == index:
			MultiplayerTheme.style_primary_battle_button(avatar_choice_buttons[i], 11)
		else:
			MultiplayerTheme.style_subtle_button(avatar_choice_buttons[i], 11)


# ==============================================================================
# 6. PAGE 2: LEADERBOARDS (PODIUM + GAME CARDS + FILTERING & PAGINATION)
# ==============================================================================

func _build_leaderboards_tab() -> void:
	var lb_page := PanelContainer.new()
	lb_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	lb_page.visible = false
	lb_page.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 22, 3, 8, 5)
	)
	hub_tabs.add_child(lb_page)
	main_pages.append(lb_page)

	var lb_vbox := VBoxContainer.new()
	lb_vbox.add_theme_constant_override("separation", 12)
	lb_page.add_child(lb_vbox)

	# Sub-page top bar
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 12)
	lb_vbox.add_child(top_row)

	var back_btn := Button.new()
	back_btn.text = "<- Arena"
	back_btn.custom_minimum_size = Vector2(118, 38)
	MultiplayerTheme.style_subtle_button(back_btn, 15)
	back_btn.pressed.connect(func(): _switch_main_tab(0))
	top_row.add_child(back_btn)

	lb_header_title_lbl = Label.new()
	lb_header_title_lbl.text = "LEADERBOARDS"
	lb_header_title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lb_header_title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lb_header_title_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_row.add_child(lb_header_title_lbl)

	var rank_pill := PanelContainer.new()
	rank_pill.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_pill_style(Color(0.08, 0.14, 0.10, 0.94), MultiplayerTheme.COL_GOLD_BORDER, 16)
	)
	top_row.add_child(rank_pill)

	lb_your_rank_banner_lbl = Label.new()
	lb_your_rank_banner_lbl.text = "Your Rank: #-"
	lb_your_rank_banner_lbl.add_theme_font_size_override("font_size", 14)
	lb_your_rank_banner_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	rank_pill.add_child(lb_your_rank_banner_lbl)

	# Filter & Pagination Bar
	var filter_row := HBoxContainer.new()
	filter_row.add_theme_constant_override("separation", 10)
	lb_vbox.add_child(filter_row)

	var global_btn := Button.new()
	global_btn.text = "Global"
	global_btn.custom_minimum_size = Vector2(110, 38)
	MultiplayerTheme.style_primary_battle_button(global_btn, 15)
	global_btn.pressed.connect(func():
		lb_current_offset = 0
		_on_load_global_leaderboard()
	)
	filter_row.add_child(global_btn)

	leaderboard_league_select = OptionButton.new()
	leaderboard_league_select.custom_minimum_size = Vector2(130, 38)
	for lg in ["Beginner", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]:
		leaderboard_league_select.add_item(lg)
	filter_row.add_child(leaderboard_league_select)

	var league_btn := Button.new()
	league_btn.text = "League"
	league_btn.custom_minimum_size = Vector2(104, 38)
	MultiplayerTheme.style_lavender_button(league_btn, 15)
	league_btn.pressed.connect(func():
		lb_current_offset = 0
		_on_load_league_leaderboard()
	)
	filter_row.add_child(league_btn)

	var nearby_btn := Button.new()
	nearby_btn.text = "Nearby"
	nearby_btn.custom_minimum_size = Vector2(104, 38)
	MultiplayerTheme.style_green_button(nearby_btn, 15)
	nearby_btn.pressed.connect(_on_load_nearby_rankings)
	filter_row.add_child(nearby_btn)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	filter_row.add_child(spacer)

	lb_prev_btn = Button.new()
	lb_prev_btn.text = "<"
	lb_prev_btn.custom_minimum_size = Vector2(44, 36)
	MultiplayerTheme.style_subtle_button(lb_prev_btn, 15)
	lb_prev_btn.pressed.connect(_on_lb_prev_page)
	filter_row.add_child(lb_prev_btn)

	lb_page_lbl = Label.new()
	lb_page_lbl.text = "Page 1"
	lb_page_lbl.add_theme_font_size_override("font_size", 14)
	lb_page_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
	filter_row.add_child(lb_page_lbl)

	lb_next_btn = Button.new()
	lb_next_btn.text = ">"
	lb_next_btn.custom_minimum_size = Vector2(44, 36)
	MultiplayerTheme.style_subtle_button(lb_next_btn, 15)
	lb_next_btn.pressed.connect(_on_lb_next_page)
	filter_row.add_child(lb_next_btn)

	# Scrollable Podium & Rows
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	lb_vbox.add_child(scroll)

	var scroll_inner := VBoxContainer.new()
	scroll_inner.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll_inner.add_theme_constant_override("separation", 10)
	scroll.add_child(scroll_inner)

	lb_podium_container = HBoxContainer.new()
	lb_podium_container.add_theme_constant_override("separation", 12)
	scroll_inner.add_child(lb_podium_container)

	lb_rows_vbox = VBoxContainer.new()
	lb_rows_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lb_rows_vbox.add_theme_constant_override("separation", 8)
	scroll_inner.add_child(lb_rows_vbox)


# ==============================================================================
# 7. PAGE 3: BATTLE LOG & TROPHY PROGRESSION
# ==============================================================================

func _build_history_tab() -> void:
	var hist_page := PanelContainer.new()
	hist_page.set_anchors_preset(Control.PRESET_FULL_RECT)
	hist_page.visible = false
	hist_page.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD_BORDER, 22, 3, 8, 5)
	)
	hub_tabs.add_child(hist_page)
	main_pages.append(hist_page)

	var hist_vbox := VBoxContainer.new()
	hist_vbox.add_theme_constant_override("separation", 12)
	hist_page.add_child(hist_vbox)

	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 12)
	hist_vbox.add_child(top_row)

	var back_btn := Button.new()
	back_btn.text = "<- Arena"
	back_btn.custom_minimum_size = Vector2(118, 38)
	MultiplayerTheme.style_subtle_button(back_btn, 15)
	back_btn.pressed.connect(func(): _switch_main_tab(0))
	top_row.add_child(back_btn)

	var title_lbl := Label.new()
	title_lbl.text = "BATTLE LOG"
	title_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	title_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title_lbl.label_settings = MultiplayerTheme.make_title_settings(24, MultiplayerTheme.COL_GOLD_BRIGHT, 5)
	top_row.add_child(title_lbl)

	hist_summary_stats_lbl = Label.new()
	hist_summary_stats_lbl.text = "0 Battles"
	hist_summary_stats_lbl.add_theme_font_size_override("font_size", 14)
	hist_summary_stats_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
	top_row.add_child(hist_summary_stats_lbl)

	var refresh_hist_btn := Button.new()
	refresh_hist_btn.text = "Refresh"
	refresh_hist_btn.custom_minimum_size = Vector2(104, 38)
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

	# Right: Trophy Progression Card
	var tr_card := PanelContainer.new()
	tr_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	tr_card.size_flags_stretch_ratio = 0.85
	tr_card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_card_style(Color(0.09, 0.16, 0.12, 0.96), Color(0.45, 0.58, 0.48, 0.8), 18, 2)
	)
	split_hbox.add_child(tr_card)

	var tr_vbox := VBoxContainer.new()
	tr_vbox.add_theme_constant_override("separation", 10)
	tr_card.add_child(tr_vbox)

	var tr_hdr := Label.new()
	tr_hdr.text = "TROPHY LOG"
	tr_hdr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tr_hdr.label_settings = MultiplayerTheme.make_title_settings(18, MultiplayerTheme.COL_GOLD_BRIGHT, 4)
	tr_vbox.add_child(tr_hdr)

	var tr_scroll := ScrollContainer.new()
	tr_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tr_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tr_vbox.add_child(tr_scroll)

	hist_trophies_vbox = VBoxContainer.new()
	hist_trophies_vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hist_trophies_vbox.add_theme_constant_override("separation", 8)
	tr_scroll.add_child(hist_trophies_vbox)


# ==============================================================================
# 8. MATCH / PLAYER DETAIL INSPECT MODAL
# ==============================================================================

func _build_inspect_modal() -> void:
	inspect_modal = PanelContainer.new()
	inspect_modal.set_anchors_preset(Control.PRESET_FULL_RECT)
	inspect_modal.visible = false
	inspect_modal.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(Color(0.05, 0.10, 0.07, 0.88), MultiplayerTheme.COL_GOLD_BORDER, 20, 2, 10, 4)
	)
	hub_tabs.add_child(inspect_modal)

	var center := CenterContainer.new()
	inspect_modal.add_child(center)

	var card := PanelContainer.new()
	card.custom_minimum_size = Vector2(620, 370)
	card.add_theme_stylebox_override(
		"panel",
		MultiplayerTheme.make_panel_style(MultiplayerTheme.COL_PANEL_GREEN, MultiplayerTheme.COL_GOLD, 22, 3, 10, 5)
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
	close_btn.custom_minimum_size = Vector2(88, 34)
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
	# 1. Subtle breathing glow on PLAY MULTIPLAYER BATTLE button
	if find_match_btn != null and !find_match_btn.disabled and lobby_view.visible:
		play_btn_pulse_phase += delta * 3.0
		var glow: float = 1.0 + sin(play_btn_pulse_phase) * 0.04
		find_match_btn.modulate = Color(glow, glow, glow, 1.0)

	# 2. Matchmaking Search Timer & Status
	if is_searching_match and matchmaking_overlay.visible:
		search_elapsed_sec += delta
		var mins: int = int(search_elapsed_sec) / 60
		var secs: int = int(search_elapsed_sec) % 60
		mm_timer_lbl.text = "%02d:%02d" % [mins, secs]

		if search_elapsed_sec < 3.5:
			mm_headline_lbl.text = "FINDING OPPONENT..."
			mm_substatus_lbl.text = "Searching your league for an opponent..."
		elif search_elapsed_sec < 8.0:
			mm_headline_lbl.text = "EXPANDING SEARCH..."
			mm_substatus_lbl.text = "Looking for a balanced 1v1 match..."
		else:
			mm_headline_lbl.text = "PREPARING BATTLE..."
			mm_substatus_lbl.text = "Waiting for a challenger to join..."

		status_poll_timer += delta
		if status_poll_timer >= 2.0:
			status_poll_timer = 0.0
			_poll_matchmaking_while_searching()

	# 3. Active Competitive RL Step Loop
	if solving_active and !step_in_progress and !animating_step and (board == null or board.dog == null or !board.dog.is_moving):
		step_timer += delta
		if step_timer >= step_interval:
			step_timer = 0.0
			_run_next_competitive_step()

	# 4. Active Match Countdown Timer
	if battle_view.visible and match_expires_unix > 0.0:
		var now_unix: float = Time.get_unix_time_from_system()
		var rem: float = maxf(0.0, match_expires_unix - now_unix)
		var r_m: int = int(rem) / 60
		var r_s: int = int(rem) % 60
		battle_timer_lbl.text = "%02d:%02d" % [r_m, r_s]

	# 5. Poll active match status while waiting for opponent
	if mp_client.is_authenticated() and active_match_id != "" and !solving_active and !is_searching_match:
		status_poll_timer += delta
		if status_poll_timer >= 2.5:
			status_poll_timer = 0.0
			_poll_active_match_status()

	# 6. Periodic Local RL Agent & Online Players Health Check
	rl_health_poll_timer += delta
	if rl_health_poll_timer >= 8.0:
		rl_health_poll_timer = 0.0
		_check_local_rl_agent()
		_fetch_online_players_count()


func _setup_online_players_request() -> void:
	_online_status_http = HTTPRequest.new()
	_online_status_http.timeout = 4.0
	add_child(_online_status_http)
	_online_status_http.request_completed.connect(_on_online_players_response)


func _fetch_online_players_count() -> void:
	if _online_status_fetching or _online_status_http == null:
		return
	var base_url: String = mp_client.server_url.strip_edges().trim_suffix("/")
	if base_url == "":
		_set_online_players_unavailable()
		return
	_online_status_fetching = true
	var err: int = _online_status_http.request(base_url + "/api/v1/status")
	if err != OK:
		_online_status_fetching = false
		_set_online_players_unavailable()


func _on_online_players_response(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_online_status_fetching = false
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300:
		_set_online_players_unavailable()
		return
	var parsed = JSON.parse_string(body.get_string_from_utf8())
	if !(parsed is Dictionary):
		_set_online_players_unavailable()
		return
	var data: Dictionary = parsed
	if !data.has("online_ws_users"):
		_set_online_players_unavailable()
		return
	var count: int = int(data.get("online_ws_users", 0))
	online_players_dot.status_color = MultiplayerTheme.COL_VICTORY
	online_players_lbl.text = "1 Player Online" if count == 1 else ("%d Players Online" % count)
	online_players_lbl.add_theme_color_override("font_color", Color(0.80, 0.96, 0.85, 0.92))


func _set_online_players_unavailable() -> void:
	if online_players_dot != null:
		online_players_dot.status_color = Color(0.75, 0.50, 0.45, 0.9)
	if online_players_lbl != null:
		online_players_lbl.text = "Server Unavailable"
		online_players_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)


func _check_local_rl_agent() -> void:
	var st: Dictionary = await rl_adapter.fetch_status()
	if bool(st.get("success", true)) and !st.has("error"):
		local_rl_online = true
		local_rl_model_version = int(st.get("modelVersion", 1))
		rl_dot.status_color = MultiplayerTheme.COL_VICTORY
		lobby_agent_ready_lbl.text = "AI Dog Ready"
		lobby_agent_ready_lbl.add_theme_color_override("font_color", Color(0.58, 0.96, 0.70))
	else:
		local_rl_online = false
		rl_dot.status_color = Color(0.95, 0.55, 0.25)
		lobby_agent_ready_lbl.text = "AI Dog Offline"
		lobby_agent_ready_lbl.add_theme_color_override("font_color", Color(1.0, 0.78, 0.45))


# ==============================================================================
# 10. VIEW TRANSITIONS, PROFILE RENDERING & AUTH HANDLERS
# ==============================================================================

func _show_auth_view() -> void:
	auth_panel.visible = true
	hub_tabs.visible = false
	if auth_server_url_input != null:
		auth_server_url_input.text = mp_client.server_url
	_on_connection_state_changed(false, "Offline")


func _show_authenticated_view() -> void:
	auth_panel.visible = false
	hub_tabs.visible = true
	if server_url_input != null:
		server_url_input.text = mp_client.server_url
	_switch_main_tab(0)


func _on_connection_state_changed(connected: bool, status_text: String) -> void:
	if connected:
		conn_dot.status_color = MultiplayerTheme.COL_VICTORY
		top_status_label.text = "Online"
		top_status_label.add_theme_color_override("font_color", Color(0.65, 1.0, 0.74))
	elif status_text.to_lower().contains("connect") or status_text.to_lower().contains("reconnect"):
		conn_dot.status_color = MultiplayerTheme.COL_GOLD
		top_status_label.text = "Connecting..."
		top_status_label.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	else:
		conn_dot.status_color = MultiplayerTheme.COL_DEFEAT
		top_status_label.text = "Offline"
		top_status_label.add_theme_color_override("font_color", Color(1.0, 0.68, 0.64))


func _on_apply_endpoints_pressed() -> void:
	var target_srv: String = server_url_input.text.strip_edges()
	if auth_panel.visible and auth_server_url_input != null and auth_server_url_input.text.strip_edges() != "":
		target_srv = auth_server_url_input.text.strip_edges()
		server_url_input.text = target_srv
	elif auth_server_url_input != null:
		auth_server_url_input.text = target_srv

	mp_client.server_url = target_srv
	MazeSession.multiplayer_server_url = mp_client.server_url
	MazeSession.server_url = rl_url_input.text.strip_edges()
	rl_adapter.real_client.base_url = MazeSession.server_url
	mp_client.save_session()
	_check_local_rl_agent()
	_fetch_online_players_count()
	if mp_client.is_authenticated():
		mp_client.disconnect_websocket()
		mp_client.connect_websocket()
		await _refresh_all_player_data()
		match_state_label.text = "Endpoints updated!"


func _on_login_pressed() -> void:
	_on_apply_endpoints_pressed()
	auth_feedback_label.text = "Signing in..."
	var res: Dictionary = await mp_client.login_account(
		login_user_input.text.strip_edges(),
		login_pass_input.text
	)
	if bool(res.get("success", false)):
		auth_feedback_label.text = ""
		_show_authenticated_view()
		await _refresh_all_player_data()
	else:
		auth_feedback_label.text = str(res.get("error", "Sign in failed"))


func _on_register_pressed() -> void:
	_on_apply_endpoints_pressed()
	auth_feedback_label.text = "Creating account..."
	var res: Dictionary = await mp_client.register_account(
		reg_user_input.text.strip_edges(),
		reg_email_input.text.strip_edges(),
		reg_pass_input.text,
		reg_display_input.text.strip_edges()
	)
	if bool(res.get("success", false)):
		auth_feedback_label.text = ""
		_show_authenticated_view()
		await _refresh_all_player_data()
	else:
		auth_feedback_label.text = str(res.get("error", "Registration failed"))


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
		var player_dict: Dictionary = prof_res.get("player", {}) if (prof_res.get("player") is Dictionary) else {}
		_render_profile_details(player_dict)
	await _on_load_global_leaderboard()
	await _on_load_history()


func _render_profile_details(p: Dictionary) -> void:
	if p.is_empty():
		return

	var dname: String = str(p.get("display_name", p.get("username", "Trainer")))
	var uname: String = str(p.get("username", "player"))
	var av: String = str(p.get("avatar", "dog_default"))
	var lvl: int = int(p.get("level", 1))
	var xp: int = int(p.get("xp", 0))
	var trophies: int = int(p.get("trophies", 0))
	var league: String = str(p.get("league", "Beginner"))
	var g_rank: String = str(p.get("global_position", "-"))
	var wins: int = int(p.get("wins", 0))
	var losses: int = int(p.get("losses", 0))
	var win_pct: float = float(p.get("win_rate", 0.0)) * 100.0
	var best_str: String = str(p.get("best_score")) if p.get("best_score") != null else "-"

	var lg_info: Dictionary = MultiplayerTheme.get_league_info(league, trophies)
	var xp_in_level: int = xp % 100

	# 1. Update Battle Arena Hero & Right-Half Navigation Cards
	arena_hero_avatar.avatar_id = av
	arena_hero_league.league_name = league
	nav_profile_avatar.avatar_id = av
	nav_profile_sub_lbl.text = "%s  •  Lv.%d  •  %s" % [dname, lvl, league]
	nav_lb_sub_lbl.text = "Rank #%s  •  %d Trophies" % [g_rank, trophies]
	nav_log_sub_lbl.text = "%dW - %dL  •  View match history" % [wins, losses]

	# 2. Update Trainer Profile Page
	edit_display_input.text = dname
	prof_avatar_large.avatar_id = av
	prof_league_shield_large.league_name = league
	prof_title_name_lbl.text = dname
	prof_handle_lbl.text = "@" + uname
	prof_level_badge_lbl.text = "Level %d  •  %d / 100 XP" % [lvl, xp_in_level]
	prof_xp_bar.max_value = 100
	prof_xp_bar.value = xp_in_level

	prof_league_tier_lbl.text = "%s LEAGUE" % league.to_upper()
	prof_trophy_big_lbl.text = "%d Trophies" % trophies
	prof_league_bar.max_value = 100
	prof_league_bar.value = float(lg_info["progress"]) * 100.0
	if bool(lg_info["is_max"]):
		prof_next_league_lbl.text = "Highest League Reached!"
	else:
		var needed: int = max(0, int(lg_info["next_min"]) - trophies)
		prof_next_league_lbl.text = "%d more to %s" % [needed, str(lg_info["next_name"])]

	_set_stat_badge_value(prof_stat_rank, "#%s" % g_rank)
	_set_stat_badge_value(prof_stat_wins, str(wins))
	_set_stat_badge_value(prof_stat_winrate, "%.0f%%" % win_pct)
	_set_stat_badge_value(prof_stat_best, best_str)

	for i in range(edit_avatar_select.item_count):
		if edit_avatar_select.get_item_text(i) == av:
			_select_avatar_option(i)
			break

	if lb_your_rank_banner_lbl != null:
		lb_your_rank_banner_lbl.text = "Your Rank: #%s  (%d Trophies)" % [g_rank, trophies]


func _set_stat_badge_value(badge: PanelContainer, text_val: String) -> void:
	if badge == null or badge.get_child_count() == 0:
		return
	var vb: Node = badge.get_child(0)
	if vb.get_child_count() >= 2 and vb.get_child(1) is Label:
		(vb.get_child(1) as Label).text = text_val


func _on_save_profile_pressed() -> void:
	var avatar_name: String = edit_avatar_select.get_item_text(edit_avatar_select.selected)
	prof_save_feedback_lbl.text = "Saving..."
	var res: Dictionary = await mp_client.update_my_profile({
		"display_name": edit_display_input.text.strip_edges(),
		"avatar": avatar_name
	})
	if bool(res.get("success", false)):
		var player_dict: Dictionary = res.get("player", {}) if (res.get("player") is Dictionary) else {}
		_render_profile_details(player_dict)
		prof_save_feedback_lbl.text = "Profile saved!"
	else:
		prof_save_feedback_lbl.text = str(res.get("error", "Could not update profile"))


# ==============================================================================
# 11. MATCHMAKING, OPPONENT FOUND TRANSITION & LIVE BATTLE FLOW
# ==============================================================================

func _on_find_match_pressed() -> void:
	find_match_btn.disabled = true
	cancel_match_btn.disabled = false
	learn_after_match_btn.disabled = true
	results_overlay.visible = false

	var p: Dictionary = mp_client.current_player
	mm_radar.avatar_id = str(p.get("avatar", "dog_default"))
	mm_radar.league_name = str(p.get("league", "Beginner"))
	mm_player_summary_lbl.text = "%s  •  %d Trophies  •  %s" % [
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

	match_state_label.text = "Searching for an opponent..."
	arena_result_summary_label.text = "Searching for a challenger..."

	var res: Dictionary = await mp_client.join_matchmaking()
	if !bool(res.get("success", false)):
		is_searching_match = false
		matchmaking_overlay.visible = false
		find_match_btn.disabled = false
		cancel_match_btn.disabled = true
		match_state_label.text = "Matchmaking error: " + str(res.get("error", "Failed"))
		return

	if res.get("match_id") != null and str(res.get("match_id", "")) != "":
		if res.get("match") is Dictionary:
			_extract_opponent_from_match(res["match"])
		await _begin_assigned_match(str(res["match_id"]))


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
	await mp_client.cancel_matchmaking()
	matchmaking_overlay.visible = false
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	match_state_label.text = "Ready to battle!"


func _on_matchmaking_updated(state: String, payload: Dictionary) -> void:
	if state == "SEARCHING":
		match_state_label.text = "Searching for an opponent..."
	elif state == "OPPONENT_FOUND":
		var opp: Dictionary = payload.get("opponent", {}) if (payload.get("opponent") is Dictionary) else {}
		if !opp.is_empty():
			current_opponent_data = opp
		mm_headline_lbl.text = "OPPONENT FOUND!"
		mm_substatus_lbl.text = "Matched vs %s" % str(opp.get("display_name", opp.get("username", "Opponent")))
		match_state_label.text = "Matched vs %s!" % str(opp.get("display_name", opp.get("username", "Opponent")))


func _on_match_created(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", ""))
	if mid != "":
		active_match_id = mid
		match_state_label.text = "Match created! Loading arena..."


func _on_map_assigned(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", ""))
	if mid != "" and (active_match_id == "" or active_match_id == mid) and !solving_active:
		await _begin_assigned_match(mid)


func _extract_opponent_from_match(match_dict: Dictionary) -> void:
	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	var p1: Dictionary = match_dict.get("player_1", {}) if (match_dict.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_dict.get("player_2", {}) if (match_dict.get("player_2") is Dictionary) else {}
	if str(p1.get("player_id", "")) == my_id:
		current_opponent_data = p2
	elif str(p2.get("player_id", "")) == my_id:
		current_opponent_data = p1


func _show_opponent_found_ceremony(difficulty: String) -> void:
	if vs_transition_in_progress:
		return
	vs_transition_in_progress = true
	matchmaking_overlay.visible = false

	for c in vs_left_slot.get_children():
		c.queue_free()
	for c in vs_right_slot.get_children():
		c.queue_free()

	var my_card := MultiplayerComponents.create_versus_player_card(mp_client.current_player, true)
	var fallback_opp: Dictionary = {
		"display_name": "Challenger",
		"username": "opponent",
		"trophies": int(mp_client.current_player.get("trophies", 0)),
		"league": str(mp_client.current_player.get("league", "Beginner"))
	}
	var opp_card := MultiplayerComponents.create_versus_player_card(
		current_opponent_data if !current_opponent_data.is_empty() else fallback_opp,
		false
	)
	vs_left_slot.add_child(my_card)
	vs_right_slot.add_child(opp_card)

	vs_map_badge_lbl.text = "%s Arena  •  Lowest Score Wins" % difficulty.capitalize()
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
	match_state_label.text = "Loading arena maze..."

	if current_opponent_data.is_empty():
		var m_info: Dictionary = await mp_client.fetch_match(match_id)
		if bool(m_info.get("success", false)):
			_extract_opponent_from_match(m_info)

	var map_res: Dictionary = await mp_client.fetch_match_map(match_id)
	if !bool(map_res.get("success", false)):
		matchmaking_overlay.visible = false
		match_state_label.text = "Could not load arena map."
		find_match_btn.disabled = false
		return

	active_map_id = str(map_res.get("map_id", ""))
	active_map_hash = str(map_res.get("map_hash", ""))
	var difficulty: String = str(map_res.get("difficulty", "standard"))
	active_maze_data = map_res.get("maze", {}) if (map_res.get("maze") is Dictionary) else {}

	if !active_maze_data.has("grid"):
		matchmaking_overlay.visible = false
		match_state_label.text = "Invalid arena map received."
		find_match_btn.disabled = false
		return

	await _show_opponent_found_ceremony(difficulty)

	_switch_main_tab(0)
	lobby_view.visible = false
	results_overlay.visible = false
	battle_view.visible = true
	match_started_unix = Time.get_unix_time_from_system()
	match_expires_unix = match_started_unix + 600.0

	var me: Dictionary = mp_client.current_player
	battle_you_avatar.avatar_id = str(me.get("avatar", "dog_default"))
	battle_you_name_lbl.text = str(me.get("display_name", me.get("username", "You")))
	battle_you_trophies_lbl.text = "%d Trophies" % int(me.get("trophies", 0))

	var opp: Dictionary = current_opponent_data
	battle_opp_avatar.avatar_id = str(opp.get("avatar", "dog_husky"))
	battle_opp_name_lbl.text = str(opp.get("display_name", opp.get("username", "Challenger")))
	battle_opp_trophies_lbl.text = "%d Trophies" % int(opp.get("trophies", 0))
	battle_opp_status_pill.text = "Opponent solving maze..."
	battle_opp_status_pill.add_theme_color_override("font_color", Color(1.0, 0.86, 0.62))

	board.setup_board(active_maze_data["grid"])
	score_manager.reset()
	_update_battle_hud_metrics(0, 0, 0)

	match_state_label.text = "Battle in progress..."
	arena_result_summary_label.text = "[b][color=#ffe885]Battle Started![/color][/b]\nYour AI Dog is navigating the maze."

	var start_res: Dictionary = await rl_adapter.start_competitive_session(
		active_maze_data,
		active_match_id,
		active_map_id,
		active_map_hash,
		true
	)
	if !bool(start_res.get("success", false)):
		var err_msg: String = str(start_res.get("error", "Start your local RL agent"))
		match_state_label.text = "Local AI Dog offline."
		arena_result_summary_label.text = (
			"[color=#ff7878][b]Local AI Dog Unavailable[/b][/color]\n%s" % err_msg
		)
		find_match_btn.disabled = false
		return

	solving_active = true
	step_in_progress = false
	animating_step = false
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
	arena_step_log_label.text = "Steps: %d  •  Bones: %d/5  •  Score: %d" % [steps, bones, score]


func _run_next_competitive_step() -> void:
	if !solving_active or step_in_progress or animating_step or (board != null and board.dog != null and board.dog.is_moving):
		return
	step_in_progress = true
	var reported_pos: Array = [board.dog.grid_position.x, board.dog.grid_position.y]
	await rl_adapter.step_agent(true, reported_pos)
	step_in_progress = false


func _on_rl_step_completed(result: Dictionary) -> void:
	animating_step = true
	await board.animate_step_result(result)
	animating_step = false
	step_timer = 0.0
	var steps: int = int(result.get("steps", 0))
	var bones: int = int(result.get("bonesCollected", 0))
	var score: int = int(result.get("score", steps - 5 * bones))
	_update_battle_hud_metrics(steps, bones, score)


func _on_rl_episode_ended(result: Dictionary) -> void:
	solving_active = false
	match_state_label.text = "Submitting run..."

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
		match_state_label.text = "Submission error: " + str(sub_res.get("error", "Verification failed"))
		find_match_btn.disabled = false
		return

	var status_str: String = str(sub_res.get("status", "AWAITING_RESULTS"))
	if status_str == "COMPLETED":
		_display_completed_match_details(sub_res)
	else:
		match_state_label.text = "Waiting for opponent..."
		battle_opp_status_pill.text = "Run submitted! Waiting for opponent..."
		arena_result_summary_label.text = (
			"[b][color=#75f096]Run Verified![/color][/b]\n"
			+ "Score: [b]%d[/b] (Steps: %d, Bones: %d)\nWaiting for your opponent to finish..." % [
				int(sub_payload.get("claimed_score", 0)),
				int(sub_payload.get("claimed_steps", 0)),
				int(sub_payload.get("claimed_bones_collected", 0))
			]
		)


func _on_opponent_submitted(_payload: Dictionary) -> void:
	battle_opp_status_pill.text = "Opponent finished!"
	battle_opp_status_pill.add_theme_color_override("font_color", MultiplayerTheme.COL_VICTORY)


func _on_verification_started(_payload: Dictionary) -> void:
	battle_opp_status_pill.text = "Calculating results..."


func _on_match_completed(payload: Dictionary) -> void:
	var mid: String = str(payload.get("match_id", active_match_id))
	if mid != "":
		var full_match: Dictionary = await mp_client.fetch_match_result(mid)
		if bool(full_match.get("success", false)):
			_display_completed_match_details(full_match)
	await _refresh_all_player_data()


func _on_match_expired(_payload: Dictionary) -> void:
	match_state_label.text = "Match expired."
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
# 12. BATTLE RESULTS PRESENTATION
# ==============================================================================

func _display_completed_match_details(match_data: Dictionary) -> void:
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	matchmaking_overlay.visible = false
	versus_overlay.visible = false

	match_state_label.text = "Ready to battle!"

	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	var winner_id: String = str(match_data.get("winner_id", "")) if match_data.get("winner_id") != null else ""
	var is_draw: bool = bool(match_data.get("is_draw", false))

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}

	var me_p: Dictionary = p1 if str(p1.get("player_id", "")) == my_id else p2
	var opp_p: Dictionary = p2 if str(p1.get("player_id", "")) == my_id else p1
	var me_s: Dictionary = me_p.get("submission", {}) if (me_p.get("submission") is Dictionary) else {}
	var opp_s: Dictionary = opp_p.get("submission", {}) if (opp_p.get("submission") is Dictionary) else {}

	var outcome_mode: String = "draw"
	if !is_draw and winner_id != "":
		outcome_mode = "victory" if winner_id == my_id else "defeat"

	res_banner_icon.outcome = outcome_mode
	res_train_feedback_lbl.text = ""
	if outcome_mode == "victory":
		res_title_lbl.text = "VICTORY!"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(36, MultiplayerTheme.COL_VICTORY, 7)
		res_subtitle_lbl.text = "Your dog conquered the maze with the winning score!"
	elif outcome_mode == "defeat":
		res_title_lbl.text = "DEFEAT"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(34, Color(0.98, 0.56, 0.52), 7)
		res_subtitle_lbl.text = "Your opponent scored lower this round. Train up and rematch!"
	else:
		res_title_lbl.text = "DRAW!"
		res_title_lbl.label_settings = MultiplayerTheme.make_title_settings(34, MultiplayerTheme.COL_GOLD_BRIGHT, 7)
		res_subtitle_lbl.text = "Both dogs tied on the scorecard!"

	var my_tr_chg: int = int(me_s.get("trophy_change", 0)) if me_s.get("trophy_change") != null else 0
	var tr_sign: String = ("+%d" % my_tr_chg) if my_tr_chg >= 0 else str(my_tr_chg)
	res_trophy_delta_lbl.text = "%s Trophies" % tr_sign
	res_trophy_delta_lbl.add_theme_color_override(
		"font_color",
		MultiplayerTheme.COL_VICTORY if my_tr_chg > 0 else (MultiplayerTheme.COL_DEFEAT if my_tr_chg < 0 else MultiplayerTheme.COL_GOLD_BRIGHT)
	)

	var est_xp: int = 75 if outcome_mode == "victory" else 25
	res_xp_awarded_lbl.text = "+%d XP" % est_xp

	_populate_result_player_column(res_you_card_box, "YOUR RUN", me_p, me_s, true)
	_populate_result_player_column(res_opp_card_box, "OPPONENT", opp_p, opp_s, false)

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

	p_row.add_child(MultiplayerComponents.DogAvatarPortrait.new(str(p_info.get("avatar", "dog_default")), 44.0, false))

	var name_lbl := Label.new()
	name_lbl.text = str(p_info.get("display_name", p_info.get("username", "Player")))
	name_lbl.label_settings = MultiplayerTheme.make_title_settings(18, MultiplayerTheme.COL_TEXT_CREAM, 4)
	p_row.add_child(name_lbl)

	var sc_val: String = str(sub_info.get("verified_score", "-"))
	var sc_big := Label.new()
	sc_big.text = "Score: %s" % sc_val
	sc_big.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sc_big.add_theme_font_size_override("font_size", 20)
	sc_big.add_theme_color_override("font_color", Color(0.52, 0.98, 0.68))
	box.add_child(sc_big)

	var details_lbl := Label.new()
	var steps_str: String = str(sub_info.get("steps", "-"))
	var bones_str: String = str(sub_info.get("bones_collected", "-"))
	details_lbl.text = "Steps: %s  •  Bones: %s" % [steps_str, bones_str]
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
	res_train_feedback_lbl.text = "Training your AI Dog on this match..."
	var res: Dictionary = await rl_adapter.learn_from_competitive_match(true)
	if bool(res.get("success", false)):
		var st_res: Dictionary = await rl_adapter.fetch_status()
		var new_ver: int = int(st_res.get("modelVersion", 1))
		await mp_client.update_my_profile({"dog_model_version": new_ver})
		arena_step_log_label.text = "AI Dog trained! Model updated."
		res_train_feedback_lbl.text = "Your AI Dog learned from this battle!"
		_check_local_rl_agent()
	else:
		res_train_feedback_lbl.text = "Training failed: " + str(res.get("error", ""))


func _on_rl_error(message: String) -> void:
	solving_active = false
	step_in_progress = false
	animating_step = false
	find_match_btn.disabled = false
	match_state_label.text = "AI Dog error: " + message


# ==============================================================================
# 13. LIVE WEBSOCKET UPDATES, LEADERBOARDS & BATTLE LOG
# ==============================================================================

func _on_profile_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_render_profile_details(mp_client.current_player)


func _on_trophies_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_render_profile_details(mp_client.current_player)


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
		return
	var page_num: int = (lb_current_offset / LB_PAGE_LIMIT) + 1
	lb_page_lbl.text = "Page %d" % page_num
	lb_prev_btn.disabled = (lb_current_offset == 0)
	var entries: Array = res.get("entries", []) if (res.get("entries") is Array) else []
	lb_next_btn.disabled = (entries.size() < LB_PAGE_LIMIT)
	_render_leaderboard_entries("GLOBAL LEADERBOARD", entries)


func _on_load_league_leaderboard() -> void:
	lb_current_mode = "league"
	var lg: String = leaderboard_league_select.get_item_text(leaderboard_league_select.selected)
	var res: Dictionary = await mp_client.fetch_league_leaderboard(lg, LB_PAGE_LIMIT, lb_current_offset)
	if !bool(res.get("success", false)):
		return
	var page_num: int = (lb_current_offset / LB_PAGE_LIMIT) + 1
	lb_page_lbl.text = "Page %d" % page_num
	lb_prev_btn.disabled = (lb_current_offset == 0)
	var entries: Array = res.get("entries", []) if (res.get("entries") is Array) else []
	lb_next_btn.disabled = (entries.size() < LB_PAGE_LIMIT)
	_render_leaderboard_entries("%s LEAGUE" % lg.to_upper(), entries)


func _on_load_nearby_rankings() -> void:
	lb_current_mode = "nearby"
	var res: Dictionary = await mp_client.fetch_my_rank()
	if !bool(res.get("success", false)):
		return
	lb_prev_btn.disabled = true
	lb_next_btn.disabled = true
	lb_page_lbl.text = "Nearby"
	var nearby: Array = res.get("nearby_players", []) if (res.get("nearby_players") is Array) else []
	_render_leaderboard_entries("NEARBY CHALLENGERS", nearby)


func _render_leaderboard_entries(title: String, entries: Array) -> void:
	lb_header_title_lbl.text = title

	for c in lb_podium_container.get_children():
		c.queue_free()
	for c in lb_rows_vbox.get_children():
		c.queue_free()

	if entries.is_empty():
		lb_rows_vbox.add_child(
			MultiplayerComponents.create_empty_state_card(
				"No Challengers Ranked Yet",
				"Play a battle in the Arena to claim the #1 spot!",
				"trophy"
			)
		)
		return

	var my_id: String = str(mp_client.current_player.get("player_id", ""))

	if lb_current_offset == 0 and entries.size() >= 1 and lb_current_mode != "nearby":
		var top_count: int = mini(3, entries.size())
		for i in range(top_count):
			if entries[i] is Dictionary:
				lb_podium_container.add_child(_create_podium_card(entries[i], i + 1, my_id))

	for item in entries:
		if item is Dictionary:
			var row_card := MultiplayerComponents.create_leaderboard_row(item, my_id, _inspect_player_profile)
			lb_rows_vbox.add_child(row_card)


func _create_podium_card(entry: Dictionary, rank_pos: int, my_id: String) -> PanelContainer:
	var is_me: bool = (str(entry.get("player_id", "")) == my_id)
	var border_col: Color = Color(1.0, 0.86, 0.25) if rank_pos == 1 else (Color(0.84, 0.88, 0.95) if rank_pos == 2 else Color(0.88, 0.58, 0.32))
	var bg_col: Color = Color(0.26, 0.22, 0.10, 0.96) if rank_pos == 1 else (Color(0.16, 0.21, 0.24, 0.95) if rank_pos == 2 else Color(0.23, 0.16, 0.12, 0.95))

	var card := PanelContainer.new()
	card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	card.custom_minimum_size = Vector2(0, 110)
	card.add_theme_stylebox_override("panel", MultiplayerTheme.make_panel_style(bg_col, border_col, 16, 3, 6, 4))

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	card.add_child(hbox)

	var left_col := VBoxContainer.new()
	left_col.alignment = BoxContainer.ALIGNMENT_CENTER
	hbox.add_child(left_col)
	left_col.add_child(MultiplayerComponents.RankMedalControl.new(rank_pos))
	left_col.add_child(MultiplayerComponents.DogAvatarPortrait.new(str(entry.get("avatar", "dog_default")), 48.0, true))

	var info_col := VBoxContainer.new()
	info_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info_col.alignment = BoxContainer.ALIGNMENT_CENTER
	info_col.add_theme_constant_override("separation", 3)
	hbox.add_child(info_col)

	var tag_lbl := Label.new()
	tag_lbl.text = ("#1 CHAMPION" if rank_pos == 1 else ("#2 RUNNER-UP" if rank_pos == 2 else "#3 CONTENDER")) + (" (YOU)" if is_me else "")
	tag_lbl.add_theme_font_size_override("font_size", 12)
	tag_lbl.add_theme_color_override("font_color", border_col.lightened(0.25))
	info_col.add_child(tag_lbl)

	var dname := Label.new()
	dname.text = str(entry.get("display_name", entry.get("username", "Player")))
	dname.label_settings = MultiplayerTheme.make_title_settings(19, MultiplayerTheme.COL_TEXT_CREAM, 4)
	info_col.add_child(dname)

	var tr_row := HBoxContainer.new()
	tr_row.add_theme_constant_override("separation", 6)
	info_col.add_child(tr_row)
	tr_row.add_child(MultiplayerComponents.TrophyIconControl.new(18.0, 0.7))
	var tr_lbl := Label.new()
	tr_lbl.text = "%d  •  %s" % [int(entry.get("trophies", 0)), str(entry.get("league", "Beginner"))]
	tr_lbl.add_theme_font_size_override("font_size", 14)
	tr_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_GOLD_BRIGHT)
	tr_row.add_child(tr_lbl)

	return card


func _on_load_history() -> void:
	var res: Dictionary = await mp_client.fetch_my_history(25, 0)
	if !bool(res.get("success", false)):
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
	hist_summary_stats_lbl.text = "%d Battles" % matches_arr.size()
	var my_id: String = str(mp_client.current_player.get("player_id", ""))

	if matches_arr.is_empty():
		hist_matches_vbox.add_child(
			MultiplayerComponents.create_empty_state_card(
				"No Battles Yet",
				"Jump into the Battle Arena to play your first ranked match!",
				"dog"
			)
		)
	else:
		for m in matches_arr:
			if m is Dictionary:
				var card := MultiplayerComponents.create_battle_history_card(m, my_id, cached_trophy_deltas, _inspect_battle_details)
				hist_matches_vbox.add_child(card)

	if tr_arr.is_empty():
		var empty_tr := Label.new()
		empty_tr.text = "Play a ranked battle to track your trophy climb!"
		empty_tr.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		empty_tr.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		empty_tr.add_theme_font_size_override("font_size", 14)
		empty_tr.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_MUTED)
		hist_trophies_vbox.add_child(empty_tr)
	else:
		for t in tr_arr:
			if t is Dictionary:
				var td: Dictionary = t
				var chg: int = int(td.get("trophy_change", 0))
				var sign_str: String = ("+%d" % chg) if chg >= 0 else str(chg)
				var accent: Color = MultiplayerTheme.COL_VICTORY if chg > 0 else (MultiplayerTheme.COL_DEFEAT if chg < 0 else MultiplayerTheme.COL_GOLD)

				var row_p := PanelContainer.new()
				row_p.add_theme_stylebox_override(
					"panel",
					MultiplayerTheme.make_pill_style(Color(0.12, 0.20, 0.15, 0.94), accent.darkened(0.25), 14)
				)
				var r_hb := HBoxContainer.new()
				r_hb.add_theme_constant_override("separation", 10)
				row_p.add_child(r_hb)

				r_hb.add_child(MultiplayerComponents.TrophyIconControl.new(18.0, 0.68))

				var delta_lbl := Label.new()
				delta_lbl.text = sign_str
				delta_lbl.custom_minimum_size = Vector2(46, 0)
				delta_lbl.add_theme_font_size_override("font_size", 16)
				delta_lbl.add_theme_color_override("font_color", accent)
				r_hb.add_child(delta_lbl)

				var span_lbl := Label.new()
				span_lbl.text = "%d -> %d" % [int(td.get("previous_trophies", 0)), int(td.get("new_trophies", 0))]
				span_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				span_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
				span_lbl.add_theme_font_size_override("font_size", 14)
				span_lbl.add_theme_color_override("font_color", MultiplayerTheme.COL_TEXT_CREAM)
				r_hb.add_child(span_lbl)

				hist_trophies_vbox.add_child(row_p)


func _inspect_battle_details(match_data: Dictionary) -> void:
	for c in inspect_body_vbox.get_children():
		c.queue_free()

	inspect_title_lbl.text = "BATTLE SUMMARY"

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}
	var s1: Dictionary = p1.get("submission", {}) if (p1.get("submission") is Dictionary) else {}
	var s2: Dictionary = p2.get("submission", {}) if (p2.get("submission") is Dictionary) else {}

	var compare_hbox := HBoxContainer.new()
	compare_hbox.add_theme_constant_override("separation", 16)
	compare_hbox.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inspect_body_vbox.add_child(compare_hbox)

	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	for pair in [[p1, s1], [p2, s2]]:
		var p_info: Dictionary = pair[0]
		var s_info: Dictionary = pair[1]
		var is_you: bool = str(p_info.get("player_id", "")) == my_id
		var col_card := PanelContainer.new()
		col_card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col_card.add_theme_stylebox_override(
			"panel",
			MultiplayerTheme.make_card_style(Color(0.09, 0.16, 0.12, 0.96), MultiplayerTheme.COL_GOLD_BORDER, 16, 2)
		)
		compare_hbox.add_child(col_card)
		var vb := VBoxContainer.new()
		vb.alignment = BoxContainer.ALIGNMENT_CENTER
		vb.add_theme_constant_override("separation", 6)
		col_card.add_child(vb)
		_populate_result_player_column(vb, "YOU" if is_you else "OPPONENT", p_info, s_info, is_you)

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

	inspect_title_lbl.text = str(p.get("display_name", username))
	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	var card := MultiplayerComponents.create_versus_player_card(p, str(p.get("player_id", "")) == my_id)
	inspect_body_vbox.add_child(card)

	var stats_row := HBoxContainer.new()
	stats_row.add_theme_constant_override("separation", 10)
	inspect_body_vbox.add_child(stats_row)

	var best_val: String = str(p.get("best_score", "-")) if p.get("best_score") != null else "-"
	stats_row.add_child(MultiplayerComponents.create_stat_badge("WINS", str(int(p.get("wins", 0))), MultiplayerTheme.COL_VICTORY))
	stats_row.add_child(MultiplayerComponents.create_stat_badge("MATCHES", str(int(p.get("total_matches", 0))), MultiplayerTheme.COL_TEXT_CREAM))
	stats_row.add_child(MultiplayerComponents.create_stat_badge("BEST SCORE", best_val, Color(0.55, 0.96, 0.68)))

	inspect_modal.visible = true


func _on_home_pressed() -> void:
	solving_active = false
	is_searching_match = false
	mp_client.disconnect_websocket()
	MazeSession.transition_to("res://scenes/landing_page.tscn")
