extends Node

class_name MockRLClient

# IMPORTANT: This is a Mock RL Client strictly for UI development and offline testing.
# It simulates the RL communication contract locally and does NOT perform real RL learning.

const IS_MOCK := true
const CLIENT_LABEL := "MOCK TESTING CLIENT (Simulated - Not Real Learning)"

const EMPTY := 0
const START := 1
const END := 2
const PIT := 3
const BONE := 4

const ACTION_NAMES := ["up", "down", "left", "right"]
const DELTAS := [Vector2i(0, -1), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(1, 0)]
const WALL_KEYS := ["top", "bottom", "left", "right"]
const OPP_WALL_KEYS := ["bottom", "top", "right", "left"]

var session_id: String = "mock_session_001"
var grid: Array = []
var dog_pos: Vector2i = Vector2i(0, 0)
var start_pos: Vector2i = Vector2i(0, 0)
var end_positions: Array[Vector2i] = []
var remaining_bones: Array[Vector2i] = []
var total_bones: int = 0
var steps: int = 0
var max_steps: int = 300
var done: bool = false
var won: bool = false
var visited_counts: Dictionary = {}
var mock_episodes: int = 0


func check_health() -> Dictionary:
	return {
		"success": true,
		"status": "ok",
		"service": "mock-rl-client",
		"is_mock": true,
		"learning": false
	}


func get_agent_status() -> Dictionary:
	return {
		"success": true,
		"status": "ok",
		"is_mock": true,
		"modelVersion": 0,
		"updates": 0,
		"totalEpisodes": mock_episodes,
		"totalSteps": steps,
		"bestWinRate": 0.0,
		"learning": false,
		"note": CLIENT_LABEL
	}


func get_training_status() -> Dictionary:
	return get_agent_status()


func start_episode(
	maze_data: Dictionary,
	mode: String = "mock",
	deterministic: bool = false,
	collect_experience: bool = false
) -> Dictionary:
	if !maze_data.has("grid"):
		return {"success": false, "error": "Maze data missing grid."}

	grid = MazeSerializer.deserialize_grid(maze_data["grid"])
	end_positions.clear()
	remaining_bones.clear()
	visited_counts.clear()

	for y in range(grid.size()):
		for x in range(grid[y].size()):
			var el := int(grid[y][x]["element"])
			var pos := Vector2i(x, y)
			if el == START:
				start_pos = pos
			elif el == END:
				end_positions.append(pos)
			elif el == BONE:
				remaining_bones.append(pos)

	total_bones = remaining_bones.size()
	dog_pos = start_pos
	steps = 0
	done = false
	won = false
	visited_counts[dog_pos] = 1

	var st := _build_state()
	return {
		"success": true,
		"is_mock": true,
		"session_id": session_id,
		"mode": "mock",
		"model_version": 0,
		"observation": _encode_observation(),
		"available_actions": _available_action_names(),
		"state": st,
		"position": st["position"],
		"steps": st["steps"],
		"score": st["score"],
		"done": st["done"]
	}


func reset_episode(_sid: String = "") -> Dictionary:
	return await start_episode({"grid": grid}, "mock", false, false)


func _can_move(action: int) -> bool:
	if grid.is_empty():
		return false
	var rows := grid.size()
	var cols: int = grid[0].size()
	var cell: Dictionary = grid[dog_pos.y][dog_pos.x]
	if bool(cell.get(WALL_KEYS[action], false)):
		return false
	var target: Vector2i = dog_pos + DELTAS[action]
	if target.x < 0 or target.x >= cols or target.y < 0 or target.y >= rows:
		return false
	if bool(grid[target.y][target.x].get(OPP_WALL_KEYS[action], false)):
		return false
	return true


func _available_action_indices() -> Array[int]:
	var valid: Array[int] = []
	for a in range(4):
		if _can_move(a):
			valid.append(a)
	return valid


func _available_action_names() -> Array[String]:
	var names: Array[String] = []
	for a in _available_action_indices():
		names.append(ACTION_NAMES[a])
	return names


func _encode_observation() -> Array:
	var obs := [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
	for a in range(4):
		if !_can_move(a):
			obs[a] = 0.0
		else:
			var target: Vector2i = dog_pos + DELTAS[a]
			if target in end_positions:
				obs[a] = 3.0 / 4.0
			elif target in remaining_bones:
				obs[a] = 2.0 / 4.0
			elif int(grid[target.y][target.x]["element"]) == PIT:
				obs[a] = 4.0 / 4.0
			else:
				obs[a] = 1.0 / 4.0
	obs[7] = float(remaining_bones.size()) / float(max(1, total_bones))
	return obs


func request_action(_sid: String, _observation: Array = [], _deterministic: bool = false) -> Dictionary:
	var valid := _available_action_indices()
	var chosen := 0
	if !valid.is_empty():
		# Exploratory heuristic for mock UI testing (prefers less-visited adjacent cells)
		var best_score := 999999.0
		for a in valid:
			var target: Vector2i = dog_pos + DELTAS[a]
			var visits: int = int(visited_counts.get(target, 0))
			var weight := float(visits) + randf() * 0.4
			if target in end_positions:
				weight = -10.0
			elif target in remaining_bones:
				weight = -5.0
			if weight < best_score:
				best_score = weight
				chosen = a
	return {
		"success": true,
		"is_mock": true,
		"session_id": session_id,
		"action": chosen,
		"action_name": ACTION_NAMES[chosen],
		"done": done
	}


func step_episode(
	_sid: String,
	action = null,
	deterministic: bool = false,
	_reported_position: Array = []
) -> Dictionary:
	if done:
		return {"success": false, "error": "Mock episode already finished. Reset first."}

	var chosen_action: int = 0
	if action == null:
		var act_res := await request_action(session_id, [], deterministic)
		chosen_action = int(act_res["action"])
	elif action is String:
		chosen_action = max(0, ACTION_NAMES.find(action.to_lower()))
	else:
		chosen_action = int(action)

	var prev_pos := dog_pos
	var moved := _can_move(chosen_action)
	if moved:
		dog_pos = dog_pos + DELTAS[chosen_action]

	var teleported := false
	var pit_entered = null
	if moved and int(grid[dog_pos.y][dog_pos.x]["element"]) == PIT:
		pit_entered = [dog_pos.x, dog_pos.y]
		var seen := {}
		while int(grid[dog_pos.y][dog_pos.x]["element"]) == PIT and !seen.has(dog_pos):
			seen[dog_pos] = true
			var dest = grid[dog_pos.y][dog_pos.x]["pit_destination"]
			if dest is Vector2i:
				dog_pos = dest
				teleported = true
			elif dest is Dictionary:
				dog_pos = Vector2i(int(dest["x"]), int(dest["y"]))
				teleported = true
			else:
				break

	var collected_bone := false
	if dog_pos in remaining_bones:
		remaining_bones.erase(dog_pos)
		collected_bone = true

	visited_counts[dog_pos] = int(visited_counts.get(dog_pos, 0)) + 1
	steps += 1
	won = dog_pos in end_positions
	var timeout := (!won) and (steps >= max_steps)
	done = won or timeout
	if done:
		mock_episodes += 1

	var bones_collected := total_bones - remaining_bones.size()
	var score := steps - 5 * bones_collected
	var st := _build_state()

	return {
		"success": true,
		"is_mock": true,
		"session_id": session_id,
		"action": chosen_action,
		"action_name": ACTION_NAMES[chosen_action],
		"previousPosition": [prev_pos.x, prev_pos.y],
		"position": [dog_pos.x, dog_pos.y],
		"pitEntered": pit_entered,
		"moved": moved,
		"teleported": teleported,
		"bone": collected_bone,
		"won": won,
		"timeout": timeout,
		"steps": steps,
		"bonesCollected": bones_collected,
		"score": score,
		"done": done,
		"reward": -1.0 + (5.0 if collected_bone else 0.0) + (50.0 if won else 0.0),
		"state": st
	}


func end_episode(_sid: String, _trigger_learn: bool = false) -> Dictionary:
	done = true
	return {
		"success": true,
		"is_mock": true,
		"episodeCompleted": true,
		"learningStarted": false,
		"note": CLIENT_LABEL
	}


func trigger_learning(_async_run: bool = true) -> Dictionary:
	return {
		"success": true,
		"is_mock": true,
		"learning": false,
		"note": "Mock client active — start Python RL server for real Recurrent PPO training."
	}


func _build_state() -> Dictionary:
	var bones_collected := total_bones - remaining_bones.size()
	var rem_list := []
	for b in remaining_bones:
		rem_list.append([b.x, b.y])
	return {
		"position": [dog_pos.x, dog_pos.y],
		"steps": steps,
		"done": done,
		"won": won,
		"timeout": (!won) and (steps >= max_steps),
		"bonesCollected": bones_collected,
		"remainingBones": rem_list,
		"score": steps - 5 * bones_collected,
		"availableActions": _available_action_names(),
		"observation": _encode_observation(),
		"grid": grid
	}

