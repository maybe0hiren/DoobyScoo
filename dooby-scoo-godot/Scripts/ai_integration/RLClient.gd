extends Node

class_name RLClient

const IS_MOCK := false
const CLIENT_LABEL := "Python RL Server (Recurrent PPO)"

var base_url: String = "http://127.0.0.1:8765"
var timeout_sec: float = 8.0


func _init(url: String = "http://127.0.0.1:8765") -> void:
	base_url = url


func _request_json(method: int, endpoint: String, payload: Dictionary = {}) -> Dictionary:
	var http := HTTPRequest.new()
	http.timeout = timeout_sec
	add_child(http)

	var headers := PackedStringArray(["Content-Type: application/json"])
	var body := "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var err := http.request(base_url + endpoint, headers, method, body)
	if err != OK:
		http.queue_free()
		return {"success": false, "error": "Unable to initiate HTTP request to " + base_url + endpoint}

	var response = await http.request_completed
	http.queue_free()

	var result_code: int = response[0]
	var status_code: int = response[1]
	var raw_bytes: PackedByteArray = response[3]

	if result_code != HTTPRequest.RESULT_SUCCESS:
		return {
			"success": false,
			"error": "Python RL service is unreachable at %s (code %d). Make sure `python -m doobyscoo serve` is running." % [base_url, result_code]
		}

	var text := raw_bytes.get_string_from_utf8()
	var parsed = JSON.parse_string(text)
	if !(parsed is Dictionary):
		return {"success": false, "error": "Invalid JSON response from Python RL service."}

	if status_code != 200:
		var msg := str(parsed.get("error", "HTTP status %d" % status_code))
		return {"success": false, "error": msg}

	if !parsed.has("success"):
		parsed["success"] = !parsed.has("error")
	return parsed


func check_health() -> Dictionary:
	return await _request_json(HTTPClient.METHOD_GET, "/health")


func get_agent_status() -> Dictionary:
	return await _request_json(HTTPClient.METHOD_GET, "/agent/status")


func get_training_status() -> Dictionary:
	return await _request_json(HTTPClient.METHOD_GET, "/training/status")


func start_episode(
	maze_data: Dictionary,
	mode: String = "training",
	deterministic: bool = false,
	collect_experience: bool = true
) -> Dictionary:
	var clean_maze := MazeSerializer.to_json_compatible_dict(maze_data)
	var payload := {
		"maze": clean_maze,
		"session": {
			"mode": mode,
			"deterministic": deterministic,
			"collect_experience": collect_experience,
			"maze_id": str(clean_maze.get("metadata", {}).get("maze_name", "custom_maze"))
		},
		"mode": mode,
		"deterministic": deterministic,
		"collect_experience": collect_experience
	}
	return await _request_json(HTTPClient.METHOD_POST, "/episode/start", payload)


func request_action(session_id: String, observation: Array = [], deterministic: bool = false) -> Dictionary:
	var payload := {
		"session_id": session_id,
		"deterministic": deterministic,
		"defer_state_update": true
	}
	if !observation.is_empty():
		payload["observation"] = observation
	return await _request_json(HTTPClient.METHOD_POST, "/agent/action", payload)


func step_episode(
	session_id: String,
	action = null,
	deterministic: bool = false,
	reported_position: Array = []
) -> Dictionary:
	var payload := {
		"session_id": session_id,
		"deterministic": deterministic,
		"auto_end": true
	}
	if action != null:
		payload["action"] = action
	if !reported_position.is_empty():
		payload["reported_position"] = reported_position
	return await _request_json(HTTPClient.METHOD_POST, "/episode/step", payload)


func end_episode(session_id: String, trigger_learn: bool = true) -> Dictionary:
	var payload := {
		"session_id": session_id,
		"learn": trigger_learn
	}
	return await _request_json(HTTPClient.METHOD_POST, "/episode/end", payload)


func reset_episode(session_id: String = "") -> Dictionary:
	return await _request_json(HTTPClient.METHOD_POST, "/reset", {"session_id": session_id})


func trigger_learning(async_run: bool = true) -> Dictionary:
	return await _request_json(HTTPClient.METHOD_POST, "/learn", {"async": async_run})

