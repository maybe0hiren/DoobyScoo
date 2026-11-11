extends Node
class_name DoobyScooAgentClient

signal map_loaded(state: Dictionary)
signal step_completed(result: Dictionary)
signal action_selected(result: Dictionary)
signal episode_ended(result: Dictionary)
signal status_updated(status: Dictionary)
signal training_started()
signal request_failed(message: String)

const API_URL := "http://127.0.0.1:8765"
var session_id: String = ""

func _request(method: int, endpoint: String, payload: Dictionary = {}) -> Dictionary:
	var request := HTTPRequest.new()
	request.timeout = 8.0
	add_child(request)
	var headers := PackedStringArray(["Content-Type: application/json"])
	var body := "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var error := request.request(API_URL + endpoint, headers, method, body)
	if error != OK:
		request.queue_free()
		return {"error": "Unable to connect to Python server"}
	var response = await request.request_completed
	request.queue_free()
	if response[0] != HTTPRequest.RESULT_SUCCESS:
		return {"error": "Python server is offline or unreachable"}
	var raw_text: String = response[3].get_string_from_utf8()
	var parsed = JSON.parse_string(raw_text)
	if response[1] != 200:
		return parsed if parsed is Dictionary else {"error": "HTTP error " + str(response[1])}
	return parsed if parsed is Dictionary else {"error": "Invalid response"}

func _post(endpoint: String, payload: Dictionary) -> Dictionary:
	return await _request(HTTPClient.METHOD_POST, endpoint, payload)

func _get(endpoint: String) -> Dictionary:
	return await _request(HTTPClient.METHOD_GET, endpoint)

func check_health() -> Dictionary:
	return await _get("/health")

func fetch_agent_status() -> void:
	var result := await _get("/agent/status")
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		status_updated.emit(result)

func load_maze(maze_path: String, mode: String = "training", deterministic: bool = false) -> void:
	var file := FileAccess.open(maze_path, FileAccess.READ)
	if file == null:
		request_failed.emit("Cannot open maze: " + maze_path)
		return
	var maze_data = JSON.parse_string(file.get_as_text())
	if not maze_data is Dictionary:
		request_failed.emit("Invalid maze JSON")
		return
	await start_episode(maze_data, mode, deterministic)

func start_episode(maze_data: Dictionary, mode: String = "training", deterministic: bool = false, collect_experience: bool = true) -> void:
	var payload := {
		"maze": maze_data,
		"mode": mode,
		"deterministic": deterministic,
		"collect_experience": collect_experience
	}
	var result := await _post("/episode/start", payload)
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		session_id = str(result.get("session_id", "default"))
		map_loaded.emit(result)

func request_action(observation: Array = [], deterministic: bool = false) -> void:
	var payload := {"session_id": session_id, "deterministic": deterministic}
	if not observation.is_empty():
		payload["observation"] = observation
	var result := await _post("/agent/action", payload)
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		action_selected.emit(result)

func next_action(deterministic: bool = false) -> void:
	var result := await _post("/episode/step", {"session_id": session_id, "deterministic": deterministic})
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		step_completed.emit(result)
		if bool(result.get("done", false)):
			episode_ended.emit(result)

func end_episode(learn: bool = true) -> void:
	var result := await _post("/episode/end", {"session_id": session_id, "learn": learn})
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		episode_ended.emit(result)

func reset_agent() -> void:
	var result := await _post("/reset", {"session_id": session_id})
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		map_loaded.emit(result)

func learn_from_played_maps() -> void:
	var result := await _post("/learn", {"async": true})
	if result.has("error"):
		request_failed.emit(str(result["error"]))
	else:
		training_started.emit()

