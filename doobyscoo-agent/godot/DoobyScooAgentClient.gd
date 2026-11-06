extends Node
class_name DoobyScooAgentClient

signal map_loaded(state: Dictionary)
signal step_completed(result: Dictionary)
signal training_started()
signal request_failed(message: String)

const API_URL := "http://127.0.0.1:8765"

func _post(endpoint: String, payload: Dictionary) -> Dictionary:
    var request := HTTPRequest.new()
    add_child(request)
    var headers := PackedStringArray(["Content-Type: application/json"])
    var error := request.request(API_URL + endpoint, headers, HTTPClient.METHOD_POST, JSON.stringify(payload))
    if error != OK:
        request.queue_free()
        return {"error": "Unable to connect to Python server"}
    var response = await request.request_completed
    request.queue_free()
    if response[1] != 200:
        var errorData = JSON.parse_string(response[3].get_string_from_utf8())
        return errorData if errorData is Dictionary else {"error": "HTTP error"}
    var data = JSON.parse_string(response[3].get_string_from_utf8())
    return data if data is Dictionary else {"error": "Invalid response"}

func load_maze(maze_path: String) -> void:
    var file := FileAccess.open(maze_path, FileAccess.READ)
    if file == null:
        request_failed.emit("Cannot open maze: " + maze_path)
        return
    var maze_data = JSON.parse_string(file.get_as_text())
    if not maze_data is Dictionary:
        request_failed.emit("Invalid maze JSON")
        return
    var result := await _post("/map", maze_data)
    if result.has("error"):
        request_failed.emit(str(result["error"]))
    else:
        map_loaded.emit(result)

func next_action() -> void:
    var result := await _post("/step", {})
    if result.has("error"):
        request_failed.emit(str(result["error"]))
    else:
        step_completed.emit(result)

func reset_agent() -> void:
    var result := await _post("/reset", {})
    if result.has("error"):
        request_failed.emit(str(result["error"]))
    else:
        map_loaded.emit(result)

func learn_from_played_maps() -> void:
    var result := await _post("/learn", {})
    if result.has("error"):
        request_failed.emit(str(result["error"]))
    else:
        training_started.emit()
