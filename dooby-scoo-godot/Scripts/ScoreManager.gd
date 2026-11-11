extends RefCounted

class_name ScoreManager

# Official DoobyScoo Scoring Formula:
# Effective Steps / Score = actual_steps - (bone_reward_value * bones_collected)
# Lower scores indicate more efficient maze solutions.

var bone_reward_value: int = 5
var actual_steps: int = 0
var bones_collected: int = 0
var completed: bool = false
var timed_out: bool = false
var cumulative_rl_reward: float = 0.0


func _init(bone_reward: int = 5) -> void:
	bone_reward_value = bone_reward
	reset()


func reset() -> void:
	actual_steps = 0
	bones_collected = 0
	completed = false
	timed_out = false
	cumulative_rl_reward = 0.0


func record_step(collected_bone: bool = false, reached_end: bool = false, is_timeout: bool = false, rl_reward: float = 0.0) -> void:
	actual_steps += 1
	if collected_bone:
		bones_collected += 1
	if reached_end:
		completed = true
	if is_timeout and !reached_end:
		timed_out = true
	cumulative_rl_reward += rl_reward


func sync_from_state(steps: int, bones: int, won: bool = false, timeout: bool = false, rl_reward: float = 0.0) -> void:
	actual_steps = steps
	bones_collected = bones
	completed = won
	timed_out = timeout
	cumulative_rl_reward = rl_reward


func get_effective_steps() -> int:
	return actual_steps - (bone_reward_value * bones_collected)


func get_score() -> int:
	return get_effective_steps()


func get_summary() -> Dictionary:
	return {
		"actual_steps": actual_steps,
		"bones_collected": bones_collected,
		"bone_reward_value": bone_reward_value,
		"effective_steps": get_effective_steps(),
		"score": get_score(),
		"completed": completed,
		"timed_out": timed_out,
		"cumulative_rl_reward": cumulative_rl_reward
	}

