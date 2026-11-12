extends Control

var mp_client: MultiplayerClient
var rl_adapter: RLAdapter
var board: GameplayBoard
var score_manager: ScoreManager

var top_status_label: Label
var top_player_badge: Label
var server_url_input: LineEdit
var rl_url_input: LineEdit

var auth_panel: PanelContainer
var hub_tabs: TabContainer

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

var active_match_id: String = ""
var active_map_id: String = ""
var active_map_hash: String = ""
var active_maze_data: Dictionary = {}
var solving_active: bool = false
var step_in_progress: bool = false
var step_timer: float = 0.0
var step_interval: float = 0.12
var status_poll_timer: float = 0.0


func _ready() -> void:
	score_manager = ScoreManager.new(5)
	mp_client = MultiplayerClient.new()
	add_child(mp_client)

	rl_adapter = RLAdapter.new()
	add_child(rl_adapter)

	_build_ui()
	_connect_signals()

	if mp_client.is_authenticated():
		_show_authenticated_view()
		mp_client.connect_websocket()
		await _refresh_all_player_data()
	else:
		_show_auth_view()


func _build_ui() -> void:
	var root_vbox: VBoxContainer = VBoxContainer.new()
	root_vbox.set_anchors_preset(Control.PRESET_FULL_RECT)
	root_vbox.offset_left = 18.0
	root_vbox.offset_top = 14.0
	root_vbox.offset_right = -18.0
	root_vbox.offset_bottom = -14.0
	root_vbox.add_theme_constant_override("separation", 10)
	add_child(root_vbox)

	var top_bar: HBoxContainer = HBoxContainer.new()
	top_bar.add_theme_constant_override("separation", 12)
	root_vbox.add_child(top_bar)

	var home_btn: Button = Button.new()
	home_btn.text = "< Home"
	home_btn.custom_minimum_size = Vector2(100, 38)
	home_btn.pressed.connect(_on_home_pressed)
	top_bar.add_child(home_btn)

	var title_lbl: Label = Label.new()
	title_lbl.text = "DOOBYSCOO ONLINE ARENA"
	title_lbl.add_theme_font_size_override("font_size", 24)
	top_bar.add_child(title_lbl)

	top_status_label = Label.new()
	top_status_label.text = "Server: Disconnected"
	top_status_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top_bar.add_child(top_status_label)

	top_player_badge = Label.new()
	top_player_badge.text = "Not Signed In"
	top_bar.add_child(top_player_badge)

	var url_bar: HBoxContainer = HBoxContainer.new()
	url_bar.add_theme_constant_override("separation", 8)
	root_vbox.add_child(url_bar)

	var srv_lbl: Label = Label.new()
	srv_lbl.text = "Multiplayer Server:"
	url_bar.add_child(srv_lbl)

	server_url_input = LineEdit.new()
	server_url_input.text = mp_client.server_url
	server_url_input.custom_minimum_size = Vector2(230, 32)
	url_bar.add_child(server_url_input)

	var rl_lbl: Label = Label.new()
	rl_lbl.text = "Local RL Agent:"
	url_bar.add_child(rl_lbl)

	rl_url_input = LineEdit.new()
	rl_url_input.text = MazeSession.server_url
	rl_url_input.custom_minimum_size = Vector2(210, 32)
	url_bar.add_child(rl_url_input)

	var apply_urls_btn: Button = Button.new()
	apply_urls_btn.text = "Apply Endpoints"
	apply_urls_btn.pressed.connect(_on_apply_endpoints_pressed)
	url_bar.add_child(apply_urls_btn)

	var logout_btn: Button = Button.new()
	logout_btn.text = "Logout"
	logout_btn.pressed.connect(_on_logout_pressed)
	url_bar.add_child(logout_btn)

	auth_panel = PanelContainer.new()
	auth_panel.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root_vbox.add_child(auth_panel)
	_build_auth_panel()

	hub_tabs = TabContainer.new()
	hub_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hub_tabs.visible = false
	root_vbox.add_child(hub_tabs)
	_build_arena_tab()
	_build_profile_tab()
	_build_leaderboards_tab()
	_build_history_tab()


func _build_auth_panel() -> void:
	var margin: MarginContainer = MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 24)
	margin.add_theme_constant_override("margin_right", 24)
	margin.add_theme_constant_override("margin_top", 20)
	margin.add_theme_constant_override("margin_bottom", 20)
	auth_panel.add_child(margin)

	var vbox: VBoxContainer = VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 14)
	margin.add_child(vbox)

	var cols: HBoxContainer = HBoxContainer.new()
	cols.add_theme_constant_override("separation", 32)
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	vbox.add_child(cols)

	var login_box: VBoxContainer = VBoxContainer.new()
	login_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	login_box.add_theme_constant_override("separation", 10)
	cols.add_child(login_box)

	var login_hdr: Label = Label.new()
	login_hdr.text = "Sign In to Existing Account"
	login_hdr.add_theme_font_size_override("font_size", 20)
	login_box.add_child(login_hdr)

	login_user_input = LineEdit.new()
	login_user_input.placeholder_text = "Username or Email"
	login_box.add_child(login_user_input)

	login_pass_input = LineEdit.new()
	login_pass_input.placeholder_text = "Password"
	login_pass_input.secret = true
	login_box.add_child(login_pass_input)

	var login_btn: Button = Button.new()
	login_btn.text = "Login & Connect"
	login_btn.custom_minimum_size = Vector2(0, 42)
	login_btn.pressed.connect(_on_login_pressed)
	login_box.add_child(login_btn)

	var reg_box: VBoxContainer = VBoxContainer.new()
	reg_box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reg_box.add_theme_constant_override("separation", 10)
	cols.add_child(reg_box)

	var reg_hdr: Label = Label.new()
	reg_hdr.text = "Create New Player Account"
	reg_hdr.add_theme_font_size_override("font_size", 20)
	reg_box.add_child(reg_hdr)

	reg_user_input = LineEdit.new()
	reg_user_input.placeholder_text = "Username (3-24 chars, letters/numbers/_)"
	reg_box.add_child(reg_user_input)

	reg_display_input = LineEdit.new()
	reg_display_input.placeholder_text = "Display Name (e.g. Trainer Alex)"
	reg_box.add_child(reg_display_input)

	reg_email_input = LineEdit.new()
	reg_email_input.placeholder_text = "Email Address"
	reg_box.add_child(reg_email_input)

	reg_pass_input = LineEdit.new()
	reg_pass_input.placeholder_text = "Password (min 6 characters)"
	reg_pass_input.secret = true
	reg_box.add_child(reg_pass_input)

	var reg_btn: Button = Button.new()
	reg_btn.text = "Register New Account"
	reg_btn.custom_minimum_size = Vector2(0, 42)
	reg_btn.pressed.connect(_on_register_pressed)
	reg_box.add_child(reg_btn)

	auth_feedback_label = Label.new()
	auth_feedback_label.text = "Sign in or create an account to enter competitive AI-vs-AI matchmaking."
	vbox.add_child(auth_feedback_label)


func _build_arena_tab() -> void:
	var arena_split: HBoxContainer = HBoxContainer.new()
	arena_split.name = "1. Competitive Arena"
	arena_split.add_theme_constant_override("separation", 16)
	hub_tabs.add_child(arena_split)

	var board_panel: PanelContainer = PanelContainer.new()
	board_panel.custom_minimum_size = Vector2(560, 500)
	arena_split.add_child(board_panel)

	board = GameplayBoard.new()
	board_panel.add_child(board)

	var right_col: VBoxContainer = VBoxContainer.new()
	right_col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	right_col.add_theme_constant_override("separation", 10)
	arena_split.add_child(right_col)

	match_state_label = Label.new()
	match_state_label.text = "Matchmaking State: IDLE"
	match_state_label.add_theme_font_size_override("font_size", 20)
	right_col.add_child(match_state_label)

	match_info_label = Label.new()
	match_info_label.text = "Local AI Execution: Your trained Dog solves assigned competition mazes locally on your device."
	match_info_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	right_col.add_child(match_info_label)

	var btn_row: HBoxContainer = HBoxContainer.new()
	btn_row.add_theme_constant_override("separation", 10)
	right_col.add_child(btn_row)

	find_match_btn = Button.new()
	find_match_btn.text = "Find Competitive Match"
	find_match_btn.custom_minimum_size = Vector2(200, 42)
	find_match_btn.pressed.connect(_on_find_match_pressed)
	btn_row.add_child(find_match_btn)

	cancel_match_btn = Button.new()
	cancel_match_btn.text = "Cancel Search"
	cancel_match_btn.custom_minimum_size = Vector2(130, 42)
	cancel_match_btn.disabled = true
	cancel_match_btn.pressed.connect(_on_cancel_match_pressed)
	btn_row.add_child(cancel_match_btn)

	learn_after_match_btn = Button.new()
	learn_after_match_btn.text = "Train Dog on Match (Local Continual Learning)"
	learn_after_match_btn.disabled = true
	learn_after_match_btn.pressed.connect(_on_learn_after_match_pressed)
	right_col.add_child(learn_after_match_btn)

	arena_step_log_label = Label.new()
	arena_step_log_label.text = "Steps: 0 | Bones: 0/5 | Score: 0"
	right_col.add_child(arena_step_log_label)

	arena_result_summary_label = RichTextLabel.new()
	arena_result_summary_label.bbcode_enabled = true
	arena_result_summary_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	arena_result_summary_label.text = "Click [b]Find Competitive Match[/b] to enter the queue."
	right_col.add_child(arena_result_summary_label)


func _build_profile_tab() -> void:
	var prof_vbox: VBoxContainer = VBoxContainer.new()
	prof_vbox.name = "2. Player Profile & Stats"
	prof_vbox.add_theme_constant_override("separation", 12)
	hub_tabs.add_child(prof_vbox)

	var edit_row: HBoxContainer = HBoxContainer.new()
	edit_row.add_theme_constant_override("separation", 10)
	prof_vbox.add_child(edit_row)

	var dn_lbl: Label = Label.new()
	dn_lbl.text = "Display Name:"
	edit_row.add_child(dn_lbl)

	edit_display_input = LineEdit.new()
	edit_display_input.custom_minimum_size = Vector2(220, 34)
	edit_row.add_child(edit_display_input)

	var av_lbl: Label = Label.new()
	av_lbl.text = "Avatar:"
	edit_row.add_child(av_lbl)

	edit_avatar_select = OptionButton.new()
	edit_avatar_select.add_item("dog_default", 0)
	edit_avatar_select.add_item("dog_golden", 1)
	edit_avatar_select.add_item("dog_husky", 2)
	edit_avatar_select.add_item("dog_cyber", 3)
	edit_row.add_child(edit_avatar_select)

	var save_prof_btn: Button = Button.new()
	save_prof_btn.text = "Save Profile"
	save_prof_btn.pressed.connect(_on_save_profile_pressed)
	edit_row.add_child(save_prof_btn)

	var ref_prof_btn: Button = Button.new()
	ref_prof_btn.text = "Refresh Profile"
	ref_prof_btn.pressed.connect(_refresh_all_player_data)
	edit_row.add_child(ref_prof_btn)

	profile_details_text = RichTextLabel.new()
	profile_details_text.bbcode_enabled = true
	profile_details_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	prof_vbox.add_child(profile_details_text)


func _build_leaderboards_tab() -> void:
	var lb_vbox: VBoxContainer = VBoxContainer.new()
	lb_vbox.name = "3. Leaderboards & Leagues"
	lb_vbox.add_theme_constant_override("separation", 10)
	hub_tabs.add_child(lb_vbox)

	var filter_row: HBoxContainer = HBoxContainer.new()
	filter_row.add_theme_constant_override("separation", 10)
	lb_vbox.add_child(filter_row)

	var global_btn: Button = Button.new()
	global_btn.text = "Global Top 50"
	global_btn.pressed.connect(_on_load_global_leaderboard)
	filter_row.add_child(global_btn)

	leaderboard_league_select = OptionButton.new()
	for lg in ["Beginner", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Master"]:
		leaderboard_league_select.add_item(lg)
	filter_row.add_child(leaderboard_league_select)

	var league_btn: Button = Button.new()
	league_btn.text = "Load League Leaderboard"
	league_btn.pressed.connect(_on_load_league_leaderboard)
	filter_row.add_child(league_btn)

	var nearby_btn: Button = Button.new()
	nearby_btn.text = "Show Nearby Ranked Players"
	nearby_btn.pressed.connect(_on_load_nearby_rankings)
	filter_row.add_child(nearby_btn)

	leaderboard_text = RichTextLabel.new()
	leaderboard_text.bbcode_enabled = true
	leaderboard_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	lb_vbox.add_child(leaderboard_text)


func _build_history_tab() -> void:
	var hist_vbox: VBoxContainer = VBoxContainer.new()
	hist_vbox.name = "4. Match & Trophy History"
	hist_vbox.add_theme_constant_override("separation", 10)
	hub_tabs.add_child(hist_vbox)

	var refresh_hist_btn: Button = Button.new()
	refresh_hist_btn.text = "Refresh Match & Trophy History"
	refresh_hist_btn.pressed.connect(_on_load_history)
	hist_vbox.add_child(refresh_hist_btn)

	history_text = RichTextLabel.new()
	history_text.bbcode_enabled = true
	history_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	hist_vbox.add_child(history_text)


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
	if solving_active and !step_in_progress:
		step_timer += delta
		if step_timer >= step_interval:
			step_timer = 0.0
			_run_next_competitive_step()

	if mp_client.is_authenticated() and active_match_id != "" and !solving_active:
		status_poll_timer += delta
		if status_poll_timer >= 3.0:
			status_poll_timer = 0.0
			_poll_active_match_status()


func _show_auth_view() -> void:
	auth_panel.visible = true
	hub_tabs.visible = false
	top_player_badge.text = "Not Signed In"


func _show_authenticated_view() -> void:
	auth_panel.visible = false
	hub_tabs.visible = true
	_update_header_badge()


func _update_header_badge() -> void:
	var p: Dictionary = mp_client.current_player
	if p.is_empty():
		top_player_badge.text = "Signed In"
		return
	top_player_badge.text = "%s | Lv.%d | %d Trophies (%s)" % [
		str(p.get("display_name", p.get("username", "Player"))),
		int(p.get("level", 1)),
		int(p.get("trophies", 0)),
		str(p.get("league", "Beginner"))
	]


func _on_connection_state_changed(connected: bool, status_text: String) -> void:
	top_status_label.text = "Server: " + status_text
	top_status_label.modulate = Color(0.55, 1.0, 0.65) if connected else Color(1.0, 0.8, 0.4)


func _on_apply_endpoints_pressed() -> void:
	mp_client.server_url = server_url_input.text.strip_edges()
	MazeSession.multiplayer_server_url = mp_client.server_url
	MazeSession.server_url = rl_url_input.text.strip_edges()
	rl_adapter.real_client.base_url = MazeSession.server_url
	mp_client.save_session()
	if mp_client.is_authenticated():
		mp_client.disconnect_websocket()
		mp_client.connect_websocket()


func _on_login_pressed() -> void:
	_on_apply_endpoints_pressed()
	auth_feedback_label.text = "Signing in..."
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
	auth_feedback_label.text = "Creating account..."
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
	active_match_id = ""
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
	edit_display_input.text = str(p.get("display_name", ""))
	var win_pct: float = float(p.get("win_rate", 0.0)) * 100.0
	var best_str: String = str(p.get("best_score")) if p.get("best_score") != null else "N/A"
	var avg_str: String = str(p.get("average_score")) if p.get("average_score") != null else "N/A"
	profile_details_text.text = (
		"[b]Account & Competitive Profile[/b]\n"
		+ "Username: [b]%s[/b] (%s)\n" % [str(p.get("username", "")), str(p.get("display_name", ""))]
		+ "Level: [b]%d[/b] (XP: %d)\n" % [int(p.get("level", 1)), int(p.get("xp", 0))]
		+ "Trophies: [b]%d[/b] | League: [b]%s[/b]\n" % [int(p.get("trophies", 0)), str(p.get("league", "Beginner"))]
		+ "Global Rank: [b]#%s[/b] | League Rank: [b]#%s[/b]\n\n" % [str(p.get("global_position", "-")), str(p.get("league_position", "-"))]
		+ "[b]Match Statistics[/b]\n"
		+ "Total Matches: %d | Wins: %d | Losses: %d | Draws: %d (Win Rate: %.1f%%)\n" % [
			int(p.get("total_matches", 0)),
			int(p.get("wins", 0)),
			int(p.get("losses", 0)),
			int(p.get("draws", 0)),
			win_pct
		]
		+ "Best Official Score: [b]%s[/b] | Average Score: [b]%s[/b]\n" % [best_str, avg_str]
		+ "Total Bones Collected: [b]%d[/b]\n" % int(p.get("total_bones_collected", 0))
		+ "Local Dog Model Version: [b]v%d[/b]" % int(p.get("dog_model_version", 1))
	)


func _on_save_profile_pressed() -> void:
	var avatar_name: String = edit_avatar_select.get_item_text(edit_avatar_select.selected)
	var res: Dictionary = await mp_client.update_my_profile({
		"display_name": edit_display_input.text.strip_edges(),
		"avatar": avatar_name
	})
	if bool(res.get("success", false)):
		_update_header_badge()
		_render_profile_details(res.get("player", {}))


func _on_find_match_pressed() -> void:
	find_match_btn.disabled = true
	cancel_match_btn.disabled = false
	learn_after_match_btn.disabled = true
	match_state_label.text = "State: SEARCHING — Finding opponent..."
	arena_result_summary_label.text = "Searching for an opponent with a similar trophy count..."

	var res: Dictionary = await mp_client.join_matchmaking()
	if !bool(res.get("success", false)):
		find_match_btn.disabled = false
		cancel_match_btn.disabled = true
		match_state_label.text = "Matchmaking Error: " + str(res.get("error", "Failed"))
		return

	var state: String = str(res.get("state", "SEARCHING"))
	if res.get("match_id") != null and str(res.get("match_id", "")) != "":
		await _begin_assigned_match(str(res["match_id"]))
	else:
		match_state_label.text = "State: %s — Finding opponent..." % state


func _on_cancel_match_pressed() -> void:
	var res: Dictionary = await mp_client.cancel_matchmaking()
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	match_state_label.text = "State: " + str(res.get("state", "CANCELLED"))


func _on_matchmaking_updated(state: String, payload: Dictionary) -> void:
	if state == "SEARCHING":
		match_state_label.text = "State: SEARCHING — Finding opponent..."
	elif state == "OPPONENT_FOUND":
		var opp: Dictionary = payload.get("opponent", {}) if (payload.get("opponent") is Dictionary) else {}
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


func _begin_assigned_match(match_id: String) -> void:
	if solving_active and active_match_id == match_id:
		return
	active_match_id = match_id
	cancel_match_btn.disabled = true
	find_match_btn.disabled = true
	match_state_label.text = "State: MAP_ASSIGNED — Downloading competition map..."

	var map_res: Dictionary = await mp_client.fetch_match_map(match_id)
	if !bool(map_res.get("success", false)):
		match_state_label.text = "Error fetching match map: " + str(map_res.get("error", ""))
		find_match_btn.disabled = false
		return

	active_map_id = str(map_res.get("map_id", ""))
	active_map_hash = str(map_res.get("map_hash", ""))
	active_maze_data = map_res.get("maze", {}) if (map_res.get("maze") is Dictionary) else {}

	if !active_maze_data.has("grid"):
		match_state_label.text = "Invalid competition map received."
		find_match_btn.disabled = false
		return

	board.setup_board(active_maze_data["grid"])
	score_manager.reset()
	match_state_label.text = "State: DOG SOLVING LOCALLY (Map %s)" % active_map_id
	arena_result_summary_label.text = (
		"[b]Competition Map Ready![/b]\n"
		+ "Map ID: %s | SHA-256: %s...\n" % [active_map_id, active_map_hash.substr(0, 12)]
		+ "Your local Python RL Dog is now solving the maze on your device."
	)

	var start_res: Dictionary = await rl_adapter.start_competitive_session(
		active_maze_data,
		active_match_id,
		active_map_id,
		active_map_hash,
		true
	)
	if !bool(start_res.get("success", false)):
		match_state_label.text = "Local RL Agent Error: " + str(start_res.get("error", "Ensure local Python agent is running"))
		find_match_btn.disabled = false
		return

	solving_active = true
	step_in_progress = false
	step_timer = 0.0


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
	arena_step_log_label.text = "Steps: %d | Bones: %d/5 | Official Score: %d" % [steps, bones, score]


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

	if !bool(sub_res.get("success", false)):
		match_state_label.text = "Submission Rejected: " + str(sub_res.get("error", "Verification failed"))
		find_match_btn.disabled = false
		return

	var status_str: String = str(sub_res.get("status", "AWAITING_RESULTS"))
	if status_str == "COMPLETED":
		_display_completed_match_details(sub_res)
	else:
		match_state_label.text = "State: WAITING FOR OPPONENT SUBMISSION..."
		arena_result_summary_label.text = (
			"[b]Your Result Was Verified by the Server![/b]\n"
			+ "Verified Score: [b]%d[/b] (Steps: %d, Bones: %d)\n" % [
				int(sub_payload.get("claimed_score", 0)),
				int(sub_payload.get("claimed_steps", 0)),
				int(sub_payload.get("claimed_bones_collected", 0))
			]
			+ "Waiting asynchronously for opponent to finish..."
		)


func _on_opponent_submitted(_payload: Dictionary) -> void:
	if active_match_id != "" and !solving_active:
		match_state_label.text = "Opponent submitted! Verifying results..."


func _on_verification_started(_payload: Dictionary) -> void:
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


func _poll_active_match_status() -> void:
	if active_match_id == "":
		return
	var res: Dictionary = await mp_client.fetch_match(active_match_id)
	if bool(res.get("success", false)):
		var st: String = str(res.get("status", ""))
		if st == "COMPLETED" or st == "EXPIRED":
			_display_completed_match_details(res)
			await _refresh_all_player_data()


func _display_completed_match_details(match_data: Dictionary) -> void:
	find_match_btn.disabled = false
	cancel_match_btn.disabled = true
	var st: String = str(match_data.get("status", "COMPLETED"))
	match_state_label.text = "State: " + st

	var my_id: String = str(mp_client.current_player.get("player_id", ""))
	var winner_id: String = str(match_data.get("winner_id", "")) if match_data.get("winner_id") != null else ""
	var is_draw: bool = bool(match_data.get("is_draw", false))

	var headline: String = "[color=yellow][b]MATCH DRAW![/b][/color]"
	if !is_draw and winner_id != "":
		if winner_id == my_id:
			headline = "[color=lime][b]VICTORY! YOUR DOG WON THE MATCH![/b][/color]"
		else:
			headline = "[color=salmon][b]DEFEAT — OPPONENT'S DOG SCORED BETTER[/b][/color]"

	var p1: Dictionary = match_data.get("player_1", {}) if (match_data.get("player_1") is Dictionary) else {}
	var p2: Dictionary = match_data.get("player_2", {}) if (match_data.get("player_2") is Dictionary) else {}
	var s1: Dictionary = p1.get("submission", {}) if (p1.get("submission") is Dictionary) else {}
	var s2: Dictionary = p2.get("submission", {}) if (p2.get("submission") is Dictionary) else {}

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
	active_match_id = ""


func _on_learn_after_match_pressed() -> void:
	learn_after_match_btn.disabled = true
	var res: Dictionary = await rl_adapter.learn_from_competitive_match(true)
	if bool(res.get("success", false)):
		var st_res: Dictionary = await rl_adapter.fetch_status()
		var new_ver: int = int(st_res.get("modelVersion", 1))
		await mp_client.update_my_profile({"dog_model_version": new_ver})
		arena_step_log_label.text = "Post-match continual learning triggered on local Python RL agent!"


func _on_rl_error(message: String) -> void:
	solving_active = false
	step_in_progress = false
	find_match_btn.disabled = false
	match_state_label.text = "RL Error: " + message


func _on_profile_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_update_header_badge()
	_render_profile_details(mp_client.current_player)


func _on_trophies_updated_ws(_payload: Dictionary) -> void:
	await mp_client.fetch_my_profile()
	_update_header_badge()


func _on_leaderboard_updated_ws(_payload: Dictionary) -> void:
	await _on_load_global_leaderboard()


func _on_load_global_leaderboard() -> void:
	var res: Dictionary = await mp_client.fetch_global_leaderboard(50, 0)
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load global leaderboard."
		return
	_render_leaderboard_entries("Global Leaderboard (Top 50)", res.get("entries", []))


func _on_load_league_leaderboard() -> void:
	var lg: String = leaderboard_league_select.get_item_text(leaderboard_league_select.selected)
	var res: Dictionary = await mp_client.fetch_league_leaderboard(lg, 50, 0)
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load league leaderboard."
		return
	_render_leaderboard_entries("%s League Leaderboard" % lg, res.get("entries", []))


func _on_load_nearby_rankings() -> void:
	var res: Dictionary = await mp_client.fetch_my_rank()
	if !bool(res.get("success", false)):
		leaderboard_text.text = "Failed to load nearby rankings."
		return
	var title: String = "Nearby Rankings (Your Global Rank: #%s | League Rank: #%s)" % [
		str(res.get("global_position", "-")),
		str(res.get("league_position", "-"))
	]
	_render_leaderboard_entries(title, res.get("nearby_players", []))


func _render_leaderboard_entries(title: String, entries: Array) -> void:
	var lines: Array[String] = ["[b]%s[/b]\n" % title]
	if entries.is_empty():
		lines.append("No players ranked yet.")
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
	leaderboard_text.text = "\n".join(lines)


func _on_load_history() -> void:
	var res: Dictionary = await mp_client.fetch_my_history(25, 0)
	if !bool(res.get("success", false)):
		history_text.text = "Failed to load match history."
		return
	var lines: Array[String] = ["[b]Recent Competitive Matches[/b]"]
	var matches_arr: Array = res.get("matches", []) if (res.get("matches") is Array) else []
	if matches_arr.is_empty():
		lines.append("No matches played yet.")
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
	lines.append("\n[b]Trophy History[/b]")
	var tr_arr: Array = res.get("trophy_history", []) if (res.get("trophy_history") is Array) else []
	if tr_arr.is_empty():
		lines.append("No trophy changes recorded yet.")
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
	history_text.text = "\n".join(lines)


func _on_home_pressed() -> void:
	solving_active = false
	get_tree().change_scene_to_file("res://scenes/landing_page.tscn")
