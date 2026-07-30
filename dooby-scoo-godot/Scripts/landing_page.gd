extends Node2D

@onready var newMapButton: Button = $NewMapButton;
@onready var myMapsButton: Button = $MyMapsButton;

var ogPosition: Vector2;
var ogPosition2: Vector2;


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	ogPosition = newMapButton.position;
	ogPosition2 = myMapsButton.position;


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	pass


func _on_new_map_button_button_down() -> void:
	var tween = create_tween();
	tween.set_trans(Tween.TRANS_QUAD);
	tween.set_ease(Tween.EASE_OUT);
	tween.tween_property(newMapButton, "position", ogPosition + Vector2(5, 5), 0.08);


func _on_new_map_button_button_up() -> void:
	var tween = create_tween();
	tween.set_trans(Tween.TRANS_QUAD);
	tween.set_ease(Tween.EASE_OUT);
	tween.tween_property(newMapButton, "position", ogPosition, 0.08);
	await tween.finished;
	get_tree().change_scene_to_file("res://scenes/map_editor_page.tscn");


func _on_my_maps_button_button_down() -> void:
	var tween = create_tween();
	tween.set_trans(Tween.TRANS_QUAD);
	tween.set_ease(Tween.EASE_OUT);
	tween.tween_property(myMapsButton, "position", ogPosition2 + Vector2(5, 5), 0.08);


func _on_my_maps_button_button_up() -> void:
	var tween = create_tween();
	tween.set_trans(Tween.TRANS_QUAD);
	tween.set_ease(Tween.EASE_OUT);
	tween.tween_property(myMapsButton, "position", ogPosition2, 0.08);
	await tween.finished;
	get_tree().change_scene_to_file("res://scenes/my_maps.tscn");
