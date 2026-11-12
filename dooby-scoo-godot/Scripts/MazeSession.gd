extends Node

const SAVE_DIRECTORY := "user://Mazes/"
const STARTER_MAPS := [
	"res://assets/starter_maps/Starter_Meadow_Run.json",
	"res://assets/starter_maps/Bone_Canyon_Challenge.json",
	"res://assets/starter_maps/Portal_Labyrinth.json"
]

var loaded_maze: Dictionary = {}
var editing_path: String = ""
var selected_mode: String = "training"
var deterministic_eval: bool = true
var collect_experience: bool = true
var server_url: String = "http://127.0.0.1:8765"
var multiplayer_server_url: String = "http://127.0.0.1:8000"
var active_match_id: String = ""
var profile_slot: String = "default"


func _ready() -> void:
	var env_rl := OS.get_environment("DOOBYSCOO_RL_URL")
	if env_rl != "":
		server_url = env_rl
	var env_mp := OS.get_environment("DOOBYSCOO_SERVER_URL")
	if env_mp != "":
		multiplayer_server_url = env_mp
	var env_slot := OS.get_environment("DOOBYSCOO_PROFILE_SLOT")
	if env_slot != "":
		profile_slot = env_slot
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--rl-url="):
			server_url = arg.substr(9)
		elif arg.begins_with("--server-url="):
			multiplayer_server_url = arg.substr(13)
		elif arg.begins_with("--profile-slot="):
			profile_slot = arg.substr(15)
	ensure_default_maps()


func reset_session() -> void:
	loaded_maze = {}
	editing_path = ""


func ensure_default_maps() -> void:
	var absolute_dir := ProjectSettings.globalize_path(SAVE_DIRECTORY)
	if !DirAccess.dir_exists_absolute(absolute_dir):
		DirAccess.make_dir_recursive_absolute(absolute_dir)

	var dir := DirAccess.open(SAVE_DIRECTORY)
	if dir == null:
		return

	var has_json := false
	dir.list_dir_begin()
	while true:
		var file_name := dir.get_next()
		if file_name == "":
			break
		if !dir.current_is_dir() and file_name.ends_with(".json"):
			has_json = true
			break
	dir.list_dir_end()

	if !has_json:
		for res_path in STARTER_MAPS:
			if FileAccess.file_exists(res_path):
				var src := FileAccess.open(res_path, FileAccess.READ)
				if src != null:
					var content := src.get_as_text()
					src.close()
					var dst_path: String = SAVE_DIRECTORY + res_path.get_file()
					var dst := FileAccess.open(dst_path, FileAccess.WRITE)
					if dst != null:
						dst.store_string(content)
						dst.close()
