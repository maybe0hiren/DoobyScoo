extends Control

@onready var board: GameplayBoard = $MainHBox/BoardContainer/GameplayBoard
@onready var mazeTitleLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/MazeTitleLabel
@onready var serverStatusLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/ServerStatusLabel
@onready var modeSelect: OptionButton = $MainHBox/SidePanel/PanelMargin/VBox/ModeRow/ModeSelect
@onready var deterministicCheck: CheckBox = $MainHBox/SidePanel/PanelMargin/VBox/OptionsRow/DeterministicCheck
@onready var collectExpCheck: CheckBox = $MainHBox/SidePanel/PanelMargin/VBox/OptionsRow/CollectExpCheck
@onready var stepsValueLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/StatsGrid/StepsValue
@onready var bonesValueLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/StatsGrid/BonesValue
@onready var scoreValueLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/StatsGrid/ScoreValue
@onready var statusValueLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/StatsGrid/StatusValue
@onready var actionLogLabel: Label = $MainHBox/SidePanel/PanelMargin/VBox/ActionLogLabel
@onready var autoPlayBtn: Button = $MainHBox/SidePanel/PanelMargin/VBox/ControlsRow1/AutoPlayButton
@onready var stepBtn: Button = $MainHBox/SidePanel/PanelMargin/VBox/ControlsRow1/StepButton
@onready var resetBtn: Button = $MainHBox/SidePanel/PanelMargin/VBox/ControlsRow2/ResetButton
@onready var learnBtn: Button = $MainHBox/SidePanel/PanelMargin/VBox/ControlsRow2/LearnButton
@onready var speedSlider: HSlider = $MainHBox/SidePanel/PanelMargin/VBox/SpeedRow/SpeedSlider
@onready var resultDialog: AcceptDialog = $ResultDialog
@onready var connectionDialog: ConfirmationDialog = $ConnectionDialog

var adapter: RLAdapter
var score_manager: ScoreManager
var auto_play: bool = false
var step_in_progress: bool = false
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
	modeSelect.add_item("Mode A: Training (RL Active)", 0)
	modeSelect.add_item("Mode B: Evaluation / Gameplay", 1)
	modeSelect.add_item("Mock Client (Offline UI Test)", 2)

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


func _initialize_gameplay() -> void:
	if MazeSession.loaded_maze.is_empty() or !MazeSession.loaded_maze.has("grid"):
		actionLogLabel.text = "No maze loaded. Returning to My Maps..."
		return

	var meta: Dictionary = MazeSession.loaded_maze.get("metadata", {})
	var mname := str(meta.get("maze_name", "Custom Maze"))
	mazeTitleLabel.text = "Maze: " + mname

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
	if !auto_play or step_in_progress or score_manager.completed or score_manager.timed_out:
		return
	step_timer += delta
	if step_timer >= step_interval:
		step_timer = 0.0
		_trigger_single_step()


func _trigger_single_step() -> void:
	if step_in_progress or score_manager.completed or score_manager.timed_out:
		return
	step_in_progress = true
	stepBtn.disabled = true
	var det := deterministicCheck.button_pressed
	var reported_pos := [board.dog.grid_position.x, board.dog.grid_position.y]
	await adapter.step_agent(det, reported_pos)
	step_in_progress = false
	if !score_manager.completed and !score_manager.timed_out:
		stepBtn.disabled = false


func _on_session_started(data: Dictionary) -> void:
	score_manager.reset()
	board.setup_board(MazeSession.loaded_maze["grid"])
	stepBtn.disabled = false
	autoPlayBtn.disabled = false
	current_attempt_number = int(data.get("attempt_number", current_attempt_number))
	if data.get("best_score", null) != null:
		current_best_score = int(data.get("best_score"))
	pending_episodes_count = int(data.get("pending_episodes", pending_episodes_count))
	pending_samples_count = int(data.get("pending_samples", pending_samples_count))
	var st: Dictionary = data.get("state", {})
	current_revisits = int(st.get("revisits", 0))
	current_new_areas = int(st.get("discoveredCellsCount", 1))
	_update_learn_button()
	var mode_badge := "[MOCK CLIENT]" if adapter.use_mock else ("[EVAL MODE]" if modeSelect.selected == 1 else "[TRAINING MODE]")
	var ver := int(data.get("model_version", 0))
	actionLogLabel.text = "Training Started — %s Attempt #%d (Model v%d | Pending: %d eps)" % [mode_badge, current_attempt_number, ver, pending_episodes_count]
	_refresh_scoreboard("Ready")


func _on_step_completed(result: Dictionary) -> void:
	await board.animate_step_result(result)

	var steps := int(result.get("steps", score_manager.actual_steps + 1))
	var bones := int(result.get("bonesCollected", score_manager.bones_collected))
	var won := bool(result.get("won", false))
	var score_limit := bool(result.get("scoreLimitExceeded", false))
	var timeout := bool(result.get("timeout", false)) or score_limit
	var reward := float(result.get("reward", 0.0))
	score_manager.sync_from_state(steps, bones, won, timeout, score_manager.cumulative_rl_reward + reward)

	current_revisits = int(result.get("revisits", current_revisits))
	var prev_areas := current_new_areas
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
	var notes: Array[String] = []
	if !bool(result.get("moved", true)):
		notes.append("Blocked by wall")
	if bool(result.get("teleported", false)):
		notes.append("Pit teleport!")
	if bool(result.get("bone", false)):
		notes.append("Bone Collected")
	elif current_new_areas > prev_areas:
		notes.append("Exploring New Area (%d cells)" % current_new_areas)
	if bool(result.get("enteredDeadEnd", false)):
		notes.append("Dead End Found")
	if won:
		notes.append("Reached Goal!")
	elif score_limit:
		notes.append("Score > 100 (Learning from Failure)")
	elif timeout:
		notes.append("Max steps reached")

	var extra := (" | " + ", ".join(notes)) if !notes.is_empty() else ""
	actionLogLabel.text = "Attempt #%d | %s -> (%d, %d) | Revisits: %d | Explored: %d%s" % [
		current_attempt_number,
		act_name,
		board.dog.grid_position.x,
		board.dog.grid_position.y,
		current_revisits,
		current_new_areas,
		extra
	]

	var status_txt := "Victory!" if won else ("Score > 100" if score_limit else ("Timeout" if timeout else "Attempt #%d" % current_attempt_number))
	_refresh_scoreboard(status_txt)


func _on_episode_ended(result: Dictionary) -> void:
	auto_play = false
	_update_autoplay_button()
	stepBtn.disabled = true

	var won := bool(result.get("won", score_manager.completed))
	var score_limit := bool(result.get("scoreLimitExceeded", false))
	var final_score := score_manager.get_score()
	var training_score := int(result.get("trainingScore", final_score))
	var steps := score_manager.actual_steps
	var bones := score_manager.bones_collected
	var learning_started := bool(result.get("learningStarted", false))
	var prog_msgs: Array = result.get("progress_messages", [])
	current_revisits = int(result.get("revisits", current_revisits))
	current_new_areas = int(result.get("discoveredCellsCount", result.get("newAreasExplored", current_new_areas)))
	if result.has("attemptNumber"):
		current_attempt_number = int(result.get("attemptNumber"))
	if result.get("bestScore", null) != null:
		current_best_score = int(result.get("bestScore"))
	elif won and (current_best_score == null or training_score < int(current_best_score)):
		current_best_score = training_score
	if result.has("pendingEpisodes"):
		pending_episodes_count = int(result.get("pendingEpisodes"))
	if result.has("pendingSamples"):
		pending_samples_count = int(result.get("pendingSamples"))
	_update_learn_button()

	var headline := "Dooby Solved the Maze!" if won else ("Learning from Failure (Training Score > 100)" if score_limit else "Episode Ended (Step Limit Reached)")
	var best_txt := str(current_best_score) if current_best_score != null else "N/A"
	var learn_note := ""
	if !prog_msgs.is_empty():
		var joined_prog := ""
		for m in prog_msgs:
			joined_prog += "\n• " + str(m)
		learn_note += "\n\nLearning Progress:" + joined_prog
		actionLogLabel.text = str(prog_msgs[0])
	if adapter.use_mock:
		learn_note += "\n\n[Mock Testing Client: No neural network weights were modified.]"
	elif learning_started:
		learn_note += "\n\nUpdate RL Policy: PPO policy update started!"
	elif collectExpCheck.button_pressed:
		learn_note += "\n\nTrajectory recorded (%d episodes, %d samples waiting). Policy stays frozen until you press Update RL Policy." % [pending_episodes_count, pending_samples_count]

	resultDialog.title = "New Best Score" if (won and !prog_msgs.is_empty()) else ("Victory!" if won else ("Learning from Failure" if score_limit else "Attempt Finished"))
	resultDialog.dialog_text = (
		"%s (Attempt #%d)\n\n"
		+ "Current Score: %d | Training Score: %d (Best: %s, limit 100)\n"
		+ "Steps Taken: %d | Revisited Cells: %d | New Areas Explored: %d\n"
		+ "Bones Collected: %d / %d (-%d official score)\n"
		+ "Episodes Waiting for Policy Update: %d (%d samples)%s"
	) % [
		headline,
		current_attempt_number,
		final_score,
		training_score,
		best_txt,
		steps,
		current_revisits,
		current_new_areas,
		bones,
		total_bones_in_maze,
		bones * score_manager.bone_reward_value,
		pending_episodes_count,
		pending_samples_count,
		learn_note
	]
	resultDialog.popup_centered()
	_refresh_scoreboard("Victory!" if won else ("Score > 100" if score_limit else "Finished"))
	await adapter.fetch_status()


func _on_status_received(status: Dictionary) -> void:
	if bool(status.get("is_mock", false)):
		serverStatusLabel.text = "Client: MOCK TESTING MODE (Offline Simulation)"
		serverStatusLabel.modulate = Color(1.0, 0.85, 0.35)
	else:
		var ver := int(status.get("modelVersion", 1))
		var ups := int(status.get("updates", 0))
		var eps := int(status.get("totalEpisodes", 0))
		pending_episodes_count = int(status.get("pendingEpisodes", pending_episodes_count))
		pending_samples_count = int(status.get("pendingSamples", pending_samples_count))
		_update_learn_button()
		var is_learning := bool(status.get("learning", false))
		var state_tag := " [Updating Policy...]" if is_learning else " [Policy Frozen]"
		serverStatusLabel.text = "Python RL%s | Model v%d | Updates: %d | Pending: %d eps (%d steps) | Total: %d" % [
			state_tag, ver, ups, pending_episodes_count, pending_samples_count, eps
		]
		serverStatusLabel.modulate = Color(0.55, 1.0, 0.65)
		if ups > last_known_updates and last_known_updates > 0:
			actionLogLabel.text = "Update RL Policy — Policy updated to Model v%d (Update #%d)!" % [ver, ups]
		var latest_prog = status.get("latestProgress", null)
		if latest_prog != null and str(latest_prog) != "" and actionLogLabel.text.begins_with("Update RL Policy — Continual"):
			actionLogLabel.text = str(latest_prog)
		last_known_updates = ups
		last_known_model_version = ver


func _on_learning_started(data: Dictionary) -> void:
	if adapter.use_mock:
		actionLogLabel.text = "Mock Client active: switch to Mode A/B with Python server for real PPO training."
	else:
		var ver := int(data.get("modelVersion", last_known_model_version))
		var ups := int(data.get("updates", last_known_updates))
		actionLogLabel.text = "Update RL Policy — Running PPO update on %d pending episodes (%d samples)..." % [pending_episodes_count, pending_samples_count]
		await get_tree().create_timer(0.6).timeout
		var st := await adapter.fetch_status()
		var new_ver := int(st.get("modelVersion", ver))
		var new_ups := int(st.get("updates", ups))
		actionLogLabel.text = "Update RL Policy — Policy updated! Now using Model v%d (Updates: %d)." % [new_ver, new_ups]


func _on_integration_error(message: String) -> void:
	auto_play = false
	_update_autoplay_button()
	step_in_progress = false
	stepBtn.disabled = false
	actionLogLabel.text = "RL Error: " + message
	serverStatusLabel.text = "Python RL Server: Disconnected / Error"
	serverStatusLabel.modulate = Color(1.0, 0.45, 0.45)


func _refresh_scoreboard(status_text: String) -> void:
	stepsValueLabel.text = str(score_manager.actual_steps)
	bonesValueLabel.text = "%d / %d" % [score_manager.bones_collected, total_bones_in_maze]
	scoreValueLabel.text = str(score_manager.get_score())
	statusValueLabel.text = status_text


func _update_learn_button() -> void:
	if learnBtn == null:
		return
	learnBtn.text = "Update RL Policy"


func _update_autoplay_button() -> void:
	autoPlayBtn.text = "Pause Auto-Play" if auto_play else "Start Auto-Play"


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
	get_tree().change_scene_to_file("res://scenes/map_editor_page.tscn")


func _on_my_maps_button_pressed() -> void:
	auto_play = false
	await adapter.stop_session(false)
	get_tree().change_scene_to_file("res://scenes/my_maps.tscn")


func _on_home_button_pressed() -> void:
	auto_play = false
	await adapter.stop_session(false)
	get_tree().change_scene_to_file("res://scenes/landing_page.tscn")

