extends Node

class_name RLAdapter

signal session_started(data: Dictionary)
signal step_completed(data: Dictionary)
signal episode_ended(data: Dictionary)
signal status_received(data: Dictionary)
signal learning_started(data: Dictionary)
signal integration_error(message: String)

var real_client: RLClient
var mock_client: MockRLClient
var use_mock: bool = false
var current_session_id: String = ""
var session_active: bool = false


func _ready() -> void:
	var url := "http://127.0.0.1:8765"
	if Engine.has_singleton("MazeSession") or get_node_or_null("/root/MazeSession") != null:
		url = get_node("/root/MazeSession").server_url
	real_client = RLClient.new(url)
	mock_client = MockRLClient.new()
	add_child(real_client)
	add_child(mock_client)


func _active_client():
	return mock_client if use_mock else real_client


func get_client_label() -> String:
	return MockRLClient.CLIENT_LABEL if use_mock else RLClient.CLIENT_LABEL


func check_service_available() -> Dictionary:
	var res: Dictionary = await _active_client().check_health()
	return res


func fetch_status() -> Dictionary:
	var res: Dictionary = await _active_client().get_agent_status()
	if res.get("success", true) and !res.has("error"):
		status_received.emit(res)
	return res


func start_maze_session(
	maze_data: Dictionary,
	mode: String = "training",
	deterministic: bool = false,
	collect_experience: bool = true
) -> Dictionary:
	var res: Dictionary = await _active_client().start_episode(
		maze_data,
		mode,
		deterministic,
		collect_experience
	)
	if !res.get("success", false) or res.has("error"):
		var msg := str(res.get("error", "Failed to start RL session."))
		integration_error.emit(msg)
		return res

	current_session_id = str(res.get("session_id", "default"))
	session_active = true
	session_started.emit(res)
	return res


func step_agent(deterministic: bool = false, reported_position: Array = []) -> Dictionary:
	if !session_active:
		var err := {"success": false, "error": "No active maze session. Start or reset first."}
		integration_error.emit(err["error"])
		return err

	var res: Dictionary = await _active_client().step_episode(
		current_session_id,
		null,
		deterministic,
		reported_position
	)
	if !res.get("success", false) or res.has("error"):
		var msg := str(res.get("error", "Failed to execute RL agent step."))
		integration_error.emit(msg)
		return res

	step_completed.emit(res)
	if bool(res.get("done", false)):
		episode_ended.emit(res)
	return res


func reset_session() -> Dictionary:
	var res: Dictionary = await _active_client().reset_episode(current_session_id)
	if !res.get("success", false) or res.has("error"):
		var msg := str(res.get("error", "Failed to reset session."))
		integration_error.emit(msg)
		return res
	session_active = true
	session_started.emit(res)
	return res


func stop_session(trigger_learn: bool = false) -> Dictionary:
	if !session_active:
		return {"success": true}
	var res: Dictionary = await _active_client().end_episode(current_session_id, trigger_learn)
	session_active = false
	return res


func request_continual_learning(async_run: bool = true) -> Dictionary:
	var res: Dictionary = await _active_client().trigger_learning(async_run)
	if !res.get("success", true) or res.has("error"):
		integration_error.emit(str(res.get("error", "Failed to start learning.")))
		return res
	learning_started.emit(res)
	return res


func start_competitive_session(
	maze_data: Dictionary,
	match_id: String,
	map_id: String,
	map_hash: String,
	deterministic: bool = true
) -> Dictionary:
	use_mock = false
	var res: Dictionary = await real_client.start_competitive_episode(
		maze_data,
		match_id,
		map_id,
		map_hash,
		deterministic
	)
	if !res.get("success", false) or res.has("error"):
		var msg := str(res.get("error", "Failed to start competitive RL session."))
		integration_error.emit(msg)
		return res
	current_session_id = str(res.get("session_id", "default"))
	session_active = true
	session_started.emit(res)
	return res


func learn_from_competitive_match(async_run: bool = true) -> Dictionary:
	if current_session_id == "":
		return {"success": false, "error": "No competitive session available to learn from."}
	var res: Dictionary = await real_client.learn_from_competitive_session(current_session_id, async_run)
	if !res.get("success", false) or res.has("error"):
		integration_error.emit(str(res.get("error", "Failed to learn from competitive session.")))
		return res
	learning_started.emit(res)
	return res

