extends Control

@onready var board_frame: PanelContainer = $OuterMargin/MainHBox/BoardContainer
@onready var side_panel: PanelContainer = $OuterMargin/MainHBox/SidePanel
@onready var status_pill: PanelContainer = $OuterMargin/MainHBox/SidePanel/VBox/StatusPill
@onready var board: GameplayBoard = $OuterMargin/MainHBox/BoardContainer/GameplayBoard
@onready var mazeTitleLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/MazeTitleLabel
@onready var serverStatusLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/StatusPill/ServerStatusLabel
@onready var modeSelect: OptionButton = $OuterMargin/MainHBox/SidePanel/VBox/ModeRow/ModeSelect
@onready var deterministicCheck: CheckBox = $OuterMargin/MainHBox/SidePanel/VBox/OptionsRow/DeterministicCheck
@onready var collectExpCheck: CheckBox = $OuterMargin/MainHBox/SidePanel/VBox/OptionsRow/CollectExpCheck
@onready var stepsValueLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/StatsGrid/StepsCard/VBox/StepsValue
@onready var bonesValueLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/StatsGrid/BonesCard/VBox/BonesValue
@onready var scoreValueLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/StatsGrid/ScoreCard/VBox/ScoreValue
@onready var statusValueLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/StatsGrid/StatusCard/VBox/StatusValue
@onready var actionLogLabel: Label = $OuterMargin/MainHBox/SidePanel/VBox/ActionLogLabel
@onready var autoPlayBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/ControlsRow1/AutoPlayButton
@onready var stepBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/ControlsRow1/StepButton
@onready var resetBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/ControlsRow2/ResetButton
@onready var learnBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/ControlsRow2/LearnButton
@onready var editMazeBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/NavRow/EditMazeButton
@onready var myMapsBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/NavRow/MyMapsButton
@onready var homeBtn: Button = $OuterMargin/MainHBox/SidePanel/VBox/NavRow/HomeButton
@onready var speedSlider: HSlider = $OuterMargin/MainHBox/SidePanel/VBox/SpeedRow/SpeedSlider
@onready var resultDialog: AcceptDialog = $ResultDialog
@onready var connectionDialog: ConfirmationDialog = $ConnectionDialog

var adapter: RLAdapter
var score_manager: ScoreManager
var completion_popup: MazeCompletionPopup
var auto_play: bool = false
var step_in_progress: bool = false
var animating_step: bool = false
var step_timer: float = 0.0
var step_interval: float = 0.18
var total_bones_in_maze: int = 5
var current_attempt_number: int = 1
var current_best_score = null
var current_revisits: int = 0
var current_new_areas: int = 1
var pending_episodes_count: int = 0
var pending_samples_count: int = 0
var last_known_updates: int = 0
var last_known_model_version: int = 1


func _ready() -> void:
	_apply_theme()
	completion_popup = MazeCompletionPopup.new()
	add_child(completion_popup)
	score_manager = ScoreManager.new(5)
	adapter = RLAdapter.new()
	add_child(adapter)

	adapter.session_started.connect(_on_session_started)
	adapter.step_completed.connect(_on_step_completed)
	adapter.episode_ended.connect(_on_episode_ended)
	adapter.status_received.connect(_on_status_received)
	adapter.learning_started.connect(_on_learning_started)
	adapter.integration_error.connect(_on_integration_error)

	modeSelect.clear()
	modeSelect.add_item("Training (RL Active)", 0)
	modeSelect.add_item("Evaluation / Gameplay", 1)
	modeSelect.add_item("Offline Mock Mode", 2)

	if MazeSession.selected_mode == "evaluation":
		modeSelect.selected = 1
		deterministicCheck.button_pressed = true
	elif MazeSession.selected_mode == "mock":
		modeSelect.selected = 2
		adapter.use_mock = true
	else:
		modeSelect.selected = 0
		deterministicCheck.button_pressed = false

	collectExpCheck.button_pressed = MazeSession.collect_experience
	_apply_speed(speedSlider.value)

	if MazeSession.loaded_maze.is_empty():
		MazeSession.ensure_default_maps()
		var fallback := MazeSession.SAVE_DIRECTORY + "Starter_Meadow_Run.json"
		if FileAccess.file_exists(fallback):
			MazeSession.loaded_maze = MazeSerializer.load_maze(fallback)
			MazeSession.editing_path = fallback

	_initialize_gameplay()


func _apply_theme() -> void:
	board_frame.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DARK, DoobyUI.COL_GOLD_BORDER, 20, 3, 10, 10)
	)
	side_panel.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DARK, DoobyUI.COL_GOLD_BORDER, 20, 3, 20, 18)
	)
	status_pill.add_theme_stylebox_override(
		"panel",
		DoobyUI.make_pill(DoobyUI.COL_MEADOW_DEEP, Color(0.45, 0.58, 0.48, 0.7), 14)
	)
	mazeTitleLabel.label_settings = DoobyUI.make_heading_settings(24, DoobyUI.COL_TEXT_CREAM, 5)

	var stats_grid: GridContainer = $OuterMargin/MainHBox/SidePanel/VBox/StatsGrid
	for card in stats_grid.get_children():
		if card is PanelContainer:
			(card as PanelContainer).add_theme_stylebox_override(
				"panel",
				DoobyUI.make_meadow_panel(DoobyUI.COL_MEADOW_DEEP, Color(0.44, 0.56, 0.46, 0.72), 14, 2, 10, 8)
			)

	DoobyUI.style_gold_button(autoPlayBtn, 18, 20)
	DoobyUI.style_lavender_button(stepBtn, 18, 20)
	DoobyUI.style_subtle_button(resetBtn, 16, 18)
	DoobyUI.style_green_button(learnBtn, 16, 18)
	DoobyUI.style_subtle_button(editMazeBtn, 15, 16)
	DoobyUI.style_subtle_button(myMapsBtn, 15, 16)
	DoobyUI.style_lavender_button(homeBtn, 15, 16)


func _initialize_gameplay() -> void:
	if MazeSession.loaded_maze.is_empty() or !MazeSession.loaded_maze.has("grid"):
		actionLogLabel.text = "No maze loaded."
		return

	var meta: Dictionary = MazeSession.loaded_maze.get("metadata", {})
	var mname: String = str(meta.get("maze_name", "Custom Maze"))
	mazeTitleLabel.text = mname

	var grid: Array = MazeSession.loaded_maze["grid"]
	board.setup_board(grid)
	total_bones_in_maze = board.remaining_bones.size()
	score_manager.reset()
	_refresh_scoreboard("Connecting...")

	await _start_rl_episode()
	await adapter.fetch_status()


func _start_rl_episode() -> void:
	auto_play = false
	_update_autoplay_button()
	var mode_str := "training"
	if modeSelect.selected == 1:
		mode_str = "evaluation"
	elif modeSelect.selected == 2:
		mode_str = "mock"

	adapter.use_mock = (modeSelect.selected == 2)
	var det := deterministicCheck.button_pressed
	var collect := collectExpCheck.button_pressed and (modeSelect.selected != 2)

	var res := await adapter.start_maze_session(
		MazeSession.loaded_maze,
		mode_str,
		det,
		collect
	)
	if !res.get("success", false) and !adapter.use_mock:
		connectionDialog.dialog_text = (
			"Could not connect to the Python RL server at 127.0.0.1:8765.\n\n"
			+ "Start it with:\npython -m doobyscoo serve --model models/dog.pt --port 8765\n\n"
			+ "Press OK to switch to the Mock Testing Client for offline UI preview, or Cancel to retry."
		)
		connectionDialog.popup_centered()


func _process(delta: float) -> void:
	if !auto_play or step_in_progress or animating_step or (board != null and board.dog != null and board.dog.is_moving) or score_manager.completed or score_manager.timed_out:
		return
	step_timer += delta
	if step_timer >= step_interval:
		step_timer = 0.0
		_trigger_single_step()


func _trigger_single_step() -> void:
	if step_in_progress or animating_step or (board != null and board.dog != null and board.dog.is_moving) or score_manager.completed or score_manager.timed_out:
		return
	step_in_progress = true
	stepBtn.disabled = true
	var det := deterministicCheck.button_pressed
	var reported_pos: Array = [board.dog.grid_position.x, board.dog.grid_position.y]
	await adapter.step_agent(det, reported_pos)
	step_in_progress = false
	if !animating_step and !score_manager.completed and !score_manager.timed_out:
		stepBtn.disabled = false


func _on_session_started(data: Dictionary) -> void:
	animating_step = false
	score_manager.reset()
	board.setup_board(MazeSession.loaded_maze["grid"])
	stepBtn.disabled = false
	autoPlayBtn.disabled = false
	current_attempt_number = int(data.get("attempt_number", current_attempt_number))
	if data.get("bestOfficialScore", null) != null:
		current_best_score = int(data.get("bestOfficialScore"))
	elif data.get("best_score", null) != null:
		current_best_score = int(data.get("best_score"))
	pending_episodes_count = int(data.get("pending_episodes", pending_episodes_count))
	pending_samples_count = int(data.get("pending_samples", pending_samples_count))
	var st: Dictionary = data.get("state", {})
	current_revisits = int(st.get("revisits", 0))
	current_new_areas = int(st.get("discoveredCellsCount", 1))
	_update_learn_button()
	actionLogLabel.text = "Attempt #%d ready — press Start Auto-Play or Single Step." % current_attempt_number
	_refresh_scoreboard("Ready")


func _on_step_completed(result: Dictionary) -> void:
	animating_step = true
	stepBtn.disabled = true
	await board.animate_step_result(result)
	animating_step = false
	step_timer = 0.0

	var steps := int(result.get("steps", score_manager.actual_steps + 1))
	var bones := int(result.get("bonesCollected", score_manager.bones_collected))
	var won := bool(result.get("won", false))
	var score_limit := bool(result.get("scoreLimitExceeded", false))
	var timeout := bool(result.get("timeout", false)) or score_limit
	var reward := float(result.get("reward", 0.0))
	score_manager.sync_from_state(steps, bones, won, timeout, score_manager.cumulative_rl_reward + reward)
	if !step_in_progress and !score_manager.completed and !score_manager.timed_out:
		stepBtn.disabled = false

	current_revisits = int(result.get("revisits", current_revisits))
	current_new_areas = int(result.get("discoveredCellsCount", current_new_areas))
	if result.has("attemptNumber"):
		current_attempt_number = int(result.get("attemptNumber"))
	if result.get("bestScore", null) != null:
		current_best_score = int(result.get("bestScore"))
	if result.has("pendingEpisodes"):
		pending_episodes_count = int(result.get("pendingEpisodes"))
	if result.has("pendingSamples"):
		pending_samples_count = int(result.get("pendingSamples"))
	_update_learn_button()

	var act_name := str(result.get("action_name", result.get("action", "?"))).to_upper()
	var note := ""
	if won:
		note = "Reached the goal!"
	elif bool(result.get("bone", false)):
		note = "Collected a bone!"
	elif bool(result.get("teleported", false)):
		note = "Fell into a pit teleport!"
	elif !bool(result.get("moved", true)):
		note = "Bumped a wall"
	elif score_limit:
		note = "Score limit reached"
	elif timeout:
		note = "Step limit reached"
	else:
		note = "Moved %s" % act_name
	actionLogLabel.text = note

	var status_txt := "Victory!" if won else ("Score > 100" if score_limit else ("Timeout" if timeout else "Running"))
	_refresh_scoreboard(status_txt)


func _on_episode_ended(result: Dictionary) -> void:
	auto_play = false
	_update_autoplay_button()
	stepBtn.disabled = true

	var prev_best = current_best_score
	var won: bool = bool(result.get("won", score_manager.completed))
	var score_limit: bool = bool(result.get("scoreLimitExceeded", false))
	var final_score: int = score_manager.get_score()
	var steps: int = score_manager.actual_steps
	var bones: int = score_manager.bones_collected
	var learning_started: bool = bool(result.get("learningStarted", false))
	var prog_msgs: Array = result.get("progress_messages", [])
	current_revisits = int(result.get("revisits", current_revisits))
	current_new_areas = int(result.get("discoveredCellsCount", result.get("newAreasExplored", current_new_areas)))
	if result.has("attemptNumber"):
		current_attempt_number = int(result.get("attemptNumber"))
	if result.get("bestOfficialScore", null) != null:
		current_best_score = int(result.get("bestOfficialScore"))
	elif result.get("bestScore", null) != null:
		current_best_score = int(result.get("bestScore"))
	elif won and (current_best_score == null or final_score < int(current_best_score)):
		current_best_score = final_score
	if result.has("pendingEpisodes"):
		pending_episodes_count = int(result.get("pendingEpisodes"))
	if result.has("pendingSamples"):
		pending_samples_count = int(result.get("pendingSamples"))
	_update_learn_button()

	var is_new_best: bool = won and (prev_best == null or final_score < int(prev_best))
	if !prog_msgs.is_empty():
		actionLogLabel.text = str(prog_msgs[0])

	_refresh_scoreboard("Victory!" if won else ("Score > 100" if score_limit else "Finished"))
	var latest_status: Dictionary = await adapter.fetch_status()
	var is_learning_now: bool = learning_started or bool(latest_status.get("learning", false))
	if latest_status.has("pendingEpisodes"):
		pending_episodes_count = int(latest_status.get("pendingEpisodes"))

	completion_popup.show_completion({
		"won": won,
		"score_limit": score_limit,
		"score": final_score,
		"steps": steps,
		"bones": bones,
		"total_bones": total_bones_in_maze,
		"best_score": current_best_score,
		"is_new_best": is_new_best,
		"pending_episodes": pending_episodes_count,
		"learning": is_learning_now,
		"is_mock": adapter.use_mock,
		"collect_experience": collectExpCheck.button_pressed,
	})


func _on_status_received(status: Dictionary) -> void:
	if bool(status.get("is_mock", false)):
		serverStatusLabel.text = "Offline Mock Mode"
		serverStatusLabel.modulate = Color(1.0, 0.85, 0.35)
	else:
		var ver := int(status.get("modelVersion", 1))
		var ups := int(status.get("updates", 0))
		pending_episodes_count = int(status.get("pendingEpisodes", pending_episodes_count))
		pending_samples_count = int(status.get("pendingSamples", pending_samples_count))
		_update_learn_button()
		var is_learning := bool(status.get("learning", false))
		if is_learning:
			serverStatusLabel.text = "RL Online  •  Updating Policy..."
		else:
			serverStatusLabel.text = "RL Online  •  Model v%d  •  %d Pending" % [ver, pending_episodes_count]
		serverStatusLabel.modulate = Color(0.55, 1.0, 0.65)
		if ups > last_known_updates and last_known_updates > 0:
			actionLogLabel.text = "Policy updated to Model v%d!" % ver
		last_known_updates = ups
		last_known_model_version = ver


func _on_learning_started(data: Dictionary) -> void:
	if adapter.use_mock:
		actionLogLabel.text = "Switch to Training mode with Python RL running to update policy."
	else:
		var ver := int(data.get("modelVersion", last_known_model_version))
		actionLogLabel.text = "Updating RL policy..."
		await get_tree().create_timer(0.6).timeout
		var st := await adapter.fetch_status()
		var new_ver := int(st.get("modelVersion", ver))
		actionLogLabel.text = "Policy updated to Model v%d!" % new_ver


func _on_integration_error(message: String) -> void:
	auto_play = false
	_update_autoplay_button()
	step_in_progress = false
	animating_step = false
	stepBtn.disabled = false
	actionLogLabel.text = "RL Error: " + message
	serverStatusLabel.text = "RL Agent Offline"
	serverStatusLabel.modulate = Color(1.0, 0.45, 0.45)


func _refresh_scoreboard(status_text: String) -> void:
	stepsValueLabel.text = str(score_manager.actual_steps)
	bonesValueLabel.text = "%d / %d" % [score_manager.bones_collected, total_bones_in_maze]
	scoreValueLabel.text = str(score_manager.get_score())
	statusValueLabel.text = status_text


func _update_learn_button() -> void:
	if learnBtn == null:
		return
	learnBtn.text = "Update Policy"


func _update_autoplay_button() -> void:
	autoPlayBtn.text = "Pause" if auto_play else "Start Auto-Play"


func _apply_speed(slider_val: float) -> void:
	step_interval = clampf(0.52 - slider_val * 0.45, 0.05, 0.50)
	if board != null and board.dog != null:
		board.dog.step_duration = clampf(step_interval * 0.8, 0.04, 0.25)


func _on_auto_play_button_pressed() -> void:
	if score_manager.completed or score_manager.timed_out:
		await _on_reset_button_pressed()
	auto_play = !auto_play
	_update_autoplay_button()


func _on_step_button_pressed() -> void:
	auto_play = false
	_update_autoplay_button()
	await _trigger_single_step()


func _on_reset_button_pressed() -> void:
	auto_play = false
	_update_autoplay_button()
	await _start_rl_episode()
	await adapter.fetch_status()


func _on_learn_button_pressed() -> void:
	await adapter.request_continual_learning(true)


func _on_mode_select_item_selected(index: int) -> void:
	if index == 0:
		MazeSession.selected_mode = "training"
		deterministicCheck.button_pressed = false
		collectExpCheck.button_pressed = true
	elif index == 1:
		MazeSession.selected_mode = "evaluation"
		deterministicCheck.button_pressed = true
	else:
		MazeSession.selected_mode = "mock"
	await _start_rl_episode()
	await adapter.fetch_status()


func _on_speed_slider_value_changed(value: float) -> void:
	_apply_speed(value)


func _on_connection_dialog_confirmed() -> void:
	modeSelect.selected = 2
	MazeSession.selected_mode = "mock"
	await _start_rl_episode()
	await adapter.fetch_status()


func _on_edit_maze_button_pressed() -> void:
	auto_play = false
	await adapter.stop_session(false)
	MazeSession.transition_to("res://scenes/map_editor_page.tscn")


func _on_my_maps_button_pressed() -> void:
	auto_play = false
	await adapter.stop_session(false)
	MazeSession.transition_to("res://scenes/my_maps.tscn")


func _on_home_button_pressed() -> void:
	auto_play = false
	await adapter.stop_session(false)
	MazeSession.transition_to("res://scenes/landing_page.tscn")
