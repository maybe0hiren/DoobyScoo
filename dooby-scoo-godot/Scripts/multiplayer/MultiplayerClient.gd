extends Node

class_name MultiplayerClient

signal connection_state_changed(connected: bool, status_text: String)
signal ws_event_received(event_type: String, envelope: Dictionary)
signal auth_succeeded(player: Dictionary)
signal auth_failed(error_message: String)
signal matchmaking_updated(state: String, payload: Dictionary)
signal match_created(payload: Dictionary)
signal map_assigned(payload: Dictionary)
signal opponent_submitted(payload: Dictionary)
signal verification_started(payload: Dictionary)
signal match_completed(payload: Dictionary)
signal match_expired(payload: Dictionary)
signal profile_updated(payload: Dictionary)
signal trophies_updated(payload: Dictionary)
signal leaderboard_updated(payload: Dictionary)

var server_url: String = "http://127.0.0.1:8000"
var access_token: String = ""
var refresh_token: String = ""
var current_player: Dictionary = {}
var last_event_id: String = ""
var last_seq_id: int = 0
var seen_event_ids: Dictionary = {}

var _ws: WebSocketPeer = WebSocketPeer.new()
var _ws_connected: bool = false
var _ws_connecting: bool = false
var _heartbeat_timer: float = 0.0
var _reconnect_timer: float = 0.0
var _reconnect_delay: float = 2.5


func _ready() -> void:
	if get_node_or_null("/root/MazeSession") != null:
		server_url = str(get_node("/root/MazeSession").multiplayer_server_url)
	load_saved_session()


func _get_session_file_path() -> String:
	var slot: String = "default"
	if get_node_or_null("/root/MazeSession") != null:
		slot = str(get_node("/root/MazeSession").profile_slot)
	return "user://multiplayer_session_%s.json" % slot


func save_session() -> void:
	var path: String = _get_session_file_path()
	var f: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if f != null:
		var data: Dictionary = {
			"server_url": server_url,
			"access_token": access_token,
			"refresh_token": refresh_token,
			"current_player": current_player,
			"last_event_id": last_event_id,
			"last_seq_id": last_seq_id,
		}
		f.store_string(JSON.stringify(data))
		f.close()


func load_saved_session() -> void:
	var path: String = _get_session_file_path()
	if !FileAccess.file_exists(path):
		return
	var f: FileAccess = FileAccess.open(path, FileAccess.READ)
	if f == null:
		return
	var raw: String = f.get_as_text()
	f.close()
	var parsed = JSON.parse_string(raw)
	if parsed is Dictionary:
		var dict_data: Dictionary = parsed
		if dict_data.has("server_url") and str(dict_data["server_url"]) != "":
			server_url = str(dict_data["server_url"])
		access_token = str(dict_data.get("access_token", ""))
		refresh_token = str(dict_data.get("refresh_token", ""))
		if dict_data.get("current_player") is Dictionary:
			current_player = dict_data["current_player"]
		last_event_id = str(dict_data.get("last_event_id", ""))
		last_seq_id = int(dict_data.get("last_seq_id", 0))


func clear_session() -> void:
	access_token = ""
	refresh_token = ""
	current_player = {}
	last_event_id = ""
	last_seq_id = 0
	disconnect_websocket()
	save_session()


func is_authenticated() -> bool:
	return access_token != ""


func _ws_url() -> String:
	var base: String = server_url.strip_edges().trim_suffix("/")
	if base.begins_with("https://"):
		base = "wss://" + base.substr(8)
	elif base.begins_with("http://"):
		base = "ws://" + base.substr(7)
	else:
		base = "ws://" + base
	return "%s/ws?token=%s&last_event_id=%s&since_seq=%d" % [
		base,
		access_token.uri_encode(),
		last_event_id.uri_encode(),
		last_seq_id
	]


func connect_websocket() -> void:
	if access_token == "":
		return
	_ws = WebSocketPeer.new()
	var err: int = _ws.connect_to_url(_ws_url())
	if err == OK:
		_ws_connecting = true
		_ws_connected = false
		connection_state_changed.emit(false, "Connecting WebSocket...")
	else:
		_ws_connecting = false
		_ws_connected = false
		connection_state_changed.emit(false, "WebSocket connection failed")


func disconnect_websocket() -> void:
	if _ws_connected or _ws_connecting:
		_ws.close()
	_ws_connected = false
	_ws_connecting = false
	connection_state_changed.emit(false, "Disconnected")


func _process(delta: float) -> void:
	if access_token == "":
		return

	if _ws_connected or _ws_connecting:
		_ws.poll()
		var state: int = _ws.get_ready_state()
		if state == WebSocketPeer.STATE_OPEN:
			if !_ws_connected:
				_ws_connected = true
				_ws_connecting = false
				_heartbeat_timer = 0.0
				connection_state_changed.emit(true, "Online (Live WS Connected)")
			while _ws.get_available_packet_count() > 0:
				var pkt: PackedByteArray = _ws.get_packet()
				var msg_text: String = pkt.get_string_from_utf8()
				_handle_ws_message(msg_text)
			_heartbeat_timer += delta
			if _heartbeat_timer >= 15.0:
				_heartbeat_timer = 0.0
				send_ws_json({"type": "ping"})
		elif state == WebSocketPeer.STATE_CLOSED:
			var was_open: bool = _ws_connected
			_ws_connected = false
			_ws_connecting = false
			if was_open:
				connection_state_changed.emit(false, "Connection lost. Reconnecting...")
			_reconnect_timer = 0.0
	else:
		_reconnect_timer += delta
		if _reconnect_timer >= _reconnect_delay:
			_reconnect_timer = 0.0
			connect_websocket()


func send_ws_json(payload: Dictionary) -> void:
	if _ws_connected and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		_ws.send_text(JSON.stringify(payload))


func _handle_ws_message(raw_text: String) -> void:
	var parsed = JSON.parse_string(raw_text)
	if !(parsed is Dictionary):
		return
	var env: Dictionary = parsed
	var ev_id: String = str(env.get("event_id", ""))
	if ev_id != "":
		if seen_event_ids.has(ev_id):
			return
		seen_event_ids[ev_id] = true
		if !ev_id.begins_with("auth_"):
			last_event_id = ev_id

	if env.has("seq_id") and env["seq_id"] != null:
		var seq_val: int = int(env["seq_id"])
		if seq_val > last_seq_id:
			last_seq_id = seq_val
			save_session()

	var ev_type: String = str(env.get("event_type", ""))
	var payload: Dictionary = env.get("payload", {}) if (env.get("payload") is Dictionary) else env
	ws_event_received.emit(ev_type, env)

	match ev_type:
		"matchmaking.started":
			matchmaking_updated.emit("SEARCHING", payload)
		"matchmaking.opponent_found":
			matchmaking_updated.emit("OPPONENT_FOUND", payload)
		"match.created":
			match_created.emit(payload)
		"match.map_assigned":
			map_assigned.emit(payload)
		"match.opponent_submitted":
			opponent_submitted.emit(payload)
		"match.verification_started":
			verification_started.emit(payload)
		"match.completed":
			match_completed.emit(payload)
		"match.expired":
			match_expired.emit(payload)
		"player.profile_updated":
			profile_updated.emit(payload)
		"player.trophies_updated":
			trophies_updated.emit(payload)
		"leaderboard.updated":
			leaderboard_updated.emit(payload)


func _request_api(
	method: int,
	endpoint: String,
	payload: Dictionary = {},
	require_auth: bool = true,
	allow_refresh_retry: bool = true
) -> Dictionary:
	var http: HTTPRequest = HTTPRequest.new()
	http.timeout = 10.0
	add_child(http)

	var headers: PackedStringArray = PackedStringArray(["Content-Type: application/json"])
	if require_auth and access_token != "":
		headers.append("Authorization: Bearer " + access_token)

	var url: String = server_url.strip_edges().trim_suffix("/") + endpoint
	var body: String = "" if method == HTTPClient.METHOD_GET else JSON.stringify(payload)
	var err: int = http.request(url, headers, method, body)
	if err != OK:
		http.queue_free()
		return {"success": false, "error": "Failed to send HTTP request to " + url}

	var response = await http.request_completed
	http.queue_free()

	var result_code: int = response[0]
	var status_code: int = response[1]
	var raw_bytes: PackedByteArray = response[3]

	if result_code != HTTPRequest.RESULT_SUCCESS:
		return {
			"success": false,
			"error": "Multiplayer server unreachable at %s (code %d)." % [server_url, result_code]
		}

	var text: String = raw_bytes.get_string_from_utf8()
	var parsed = JSON.parse_string(text)
	var data: Dictionary = parsed if (parsed is Dictionary) else {"error": "Invalid JSON response"}

	if status_code == 401 and require_auth and allow_refresh_retry and refresh_token != "":
		var refreshed: bool = await refresh_access_token()
		if refreshed:
			return await _request_api(method, endpoint, payload, require_auth, false)

	if status_code < 200 or status_code >= 300:
		var msg: String = str(data.get("error", data.get("detail", "HTTP error %d" % status_code)))
		return {"success": false, "status_code": status_code, "error": msg, "code": str(data.get("code", ""))}

	if !data.has("success"):
		data["success"] = true
	return data


func register_account(username: String, email: String, password: String, display_name: String) -> Dictionary:
	var res: Dictionary = await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/auth/register",
		{
			"username": username,
			"email": email,
			"password": password,
			"display_name": display_name
		},
		false
	)
	if bool(res.get("success", false)):
		access_token = str(res.get("access_token", ""))
		refresh_token = str(res.get("refresh_token", ""))
		current_player = res.get("player", {})
		save_session()
		connect_websocket()
		auth_succeeded.emit(current_player)
	else:
		auth_failed.emit(str(res.get("error", "Registration failed")))
	return res


func login_account(identifier: String, password: String) -> Dictionary:
	var res: Dictionary = await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/auth/login",
		{"username": identifier, "password": password},
		false
	)
	if bool(res.get("success", false)):
		access_token = str(res.get("access_token", ""))
		refresh_token = str(res.get("refresh_token", ""))
		current_player = res.get("player", {})
		save_session()
		connect_websocket()
		auth_succeeded.emit(current_player)
	else:
		auth_failed.emit(str(res.get("error", "Login failed")))
	return res


func logout_account() -> Dictionary:
	var res: Dictionary = await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/auth/logout",
		{"refresh_token": refresh_token},
		true,
		false
	)
	clear_session()
	return res


func refresh_access_token() -> bool:
	if refresh_token == "":
		return false
	var res: Dictionary = await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/auth/refresh",
		{"refresh_token": refresh_token},
		false,
		false
	)
	if bool(res.get("success", false)):
		access_token = str(res.get("access_token", ""))
		refresh_token = str(res.get("refresh_token", ""))
		save_session()
		return true
	return false


func reset_password(username: String, email: String, new_password: String) -> Dictionary:
	return await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/auth/password-reset",
		{"username": username, "email": email, "new_password": new_password},
		false
	)


func fetch_my_profile() -> Dictionary:
	var res: Dictionary = await _request_api(HTTPClient.METHOD_GET, "/api/v1/players/me")
	if bool(res.get("success", false)) and res.get("player") is Dictionary:
		current_player = res["player"]
		save_session()
	return res


func update_my_profile(updates: Dictionary) -> Dictionary:
	var res: Dictionary = await _request_api(HTTPClient.METHOD_PATCH, "/api/v1/players/me", updates)
	if bool(res.get("success", false)) and res.get("player") is Dictionary:
		current_player = res["player"]
		save_session()
	return res


func fetch_my_rank() -> Dictionary:
	return await _request_api(HTTPClient.METHOD_GET, "/api/v1/players/me/rank")


func fetch_my_history(limit: int = 25, offset: int = 0) -> Dictionary:
	return await _request_api(
		HTTPClient.METHOD_GET,
		"/api/v1/players/me/history?limit=%d&offset=%d" % [limit, offset]
	)


func join_matchmaking() -> Dictionary:
	return await _request_api(HTTPClient.METHOD_POST, "/api/v1/matchmaking/join", {})


func cancel_matchmaking() -> Dictionary:
	return await _request_api(HTTPClient.METHOD_POST, "/api/v1/matchmaking/cancel", {})


func fetch_matchmaking_status() -> Dictionary:
	return await _request_api(HTTPClient.METHOD_GET, "/api/v1/matchmaking/status")


func fetch_match(match_id: String) -> Dictionary:
	return await _request_api(HTTPClient.METHOD_GET, "/api/v1/matches/" + match_id)


func fetch_match_map(match_id: String) -> Dictionary:
	return await _request_api(HTTPClient.METHOD_GET, "/api/v1/matches/%s/map" % match_id)


func submit_match_result(match_id: String, submission_payload: Dictionary) -> Dictionary:
	return await _request_api(
		HTTPClient.METHOD_POST,
		"/api/v1/matches/%s/submit" % match_id,
		submission_payload
	)


func fetch_match_result(match_id: String) -> Dictionary:
	return await _request_api(HTTPClient.METHOD_GET, "/api/v1/matches/%s/result" % match_id)


func fetch_global_leaderboard(limit: int = 50, offset: int = 0) -> Dictionary:
	return await _request_api(
		HTTPClient.METHOD_GET,
		"/api/v1/leaderboards/global?limit=%d&offset=%d" % [limit, offset],
		{},
		false
	)


func fetch_league_leaderboard(league: String, limit: int = 50, offset: int = 0) -> Dictionary:
	return await _request_api(
		HTTPClient.METHOD_GET,
		"/api/v1/leaderboards/league/%s?limit=%d&offset=%d" % [league.uri_encode(), limit, offset],
		{},
		false
	)


func sync_missed_events() -> Dictionary:
	var res: Dictionary = await _request_api(
		HTTPClient.METHOD_GET,
		"/api/v1/players/me/events?last_event_id=%s&since_seq=%d" % [last_event_id.uri_encode(), last_seq_id]
	)
	if bool(res.get("success", false)) and res.get("events") is Array:
		var ev_list: Array = res["events"]
		for ev in ev_list:
			if ev is Dictionary:
				_handle_ws_message(JSON.stringify(ev))
	return res

