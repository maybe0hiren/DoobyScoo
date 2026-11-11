extends Node2D

class_name DogController

signal animation_finished()

var grid_position: Vector2i = Vector2i(0, 0)
var facing_direction: int = 3 # 0=UP, 1=DOWN, 2=LEFT, 3=RIGHT
var bob_phase: float = 0.0
var is_moving: bool = false
var is_celebrating: bool = false
var step_duration: float = 0.16


func _ready() -> void:
	z_index = 10


func _process(delta: float) -> void:
	bob_phase += delta * (14.0 if is_moving else 5.0)
	queue_redraw()


func place_at_cell(cell: Vector2i, world_pos: Vector2) -> void:
	grid_position = cell
	position = world_pos
	is_moving = false
	is_celebrating = false
	queue_redraw()


func animate_move(target_cell: Vector2i, target_world_pos: Vector2, action: int = -1) -> void:
	if action in [0, 1, 2, 3]:
		facing_direction = action
	grid_position = target_cell
	is_moving = true
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_QUAD)
	tween.set_ease(Tween.EASE_OUT)
	tween.tween_property(self, "position", target_world_pos, step_duration)
	await tween.finished
	is_moving = false
	animation_finished.emit()


func animate_teleport(pit_world_pos: Vector2, dest_cell: Vector2i, dest_world_pos: Vector2, action: int = -1) -> void:
	if action in [0, 1, 2, 3]:
		facing_direction = action
	grid_position = dest_cell
	is_moving = true
	var tween := create_tween()
	tween.set_trans(Tween.TRANS_BACK)
	tween.set_ease(Tween.EASE_IN_OUT)
	tween.tween_property(self, "position", pit_world_pos, step_duration * 0.45)
	tween.tween_property(self, "scale", Vector2(0.15, 0.15), step_duration * 0.25)
	tween.tween_callback(func(): position = dest_world_pos)
	tween.tween_property(self, "scale", Vector2(1.0, 1.0), step_duration * 0.3)
	await tween.finished
	is_moving = false
	animation_finished.emit()


func animate_blocked(action: int) -> void:
	if action in [0, 1, 2, 3]:
		facing_direction = action
	var offsets := [Vector2(0, -8), Vector2(0, 8), Vector2(-8, 0), Vector2(8, 0)]
	var bump: Vector2 = offsets[action] if action in [0, 1, 2, 3] else Vector2.ZERO
	var start_pos := position
	is_moving = true
	var tween := create_tween()
	tween.tween_property(self, "position", start_pos + bump, step_duration * 0.4)
	tween.tween_property(self, "position", start_pos, step_duration * 0.4)
	await tween.finished
	is_moving = false
	animation_finished.emit()


func animate_bone_pickup() -> void:
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector2(1.28, 1.28), 0.08)
	tween.tween_property(self, "scale", Vector2(1.0, 1.0), 0.08)


func celebrate() -> void:
	is_celebrating = true
	var tween := create_tween()
	tween.tween_property(self, "scale", Vector2(1.3, 1.3), 0.15)
	tween.tween_property(self, "scale", Vector2(1.0, 1.0), 0.15)


func _draw() -> void:
	var bob_y := sin(bob_phase) * (2.5 if is_moving else 1.2)
	if is_celebrating:
		bob_y = -abs(sin(bob_phase * 2.0)) * 6.0

	var center := Vector2(0, bob_y)
	var flip_x := -1.0 if facing_direction == 2 else 1.0

	# Drop shadow
	draw_circle(Vector2(0, 16), 14.0, Color(0, 0, 0, 0.25))

	# Wagging tail
	var tail_wag := sin(bob_phase * 2.2) * 5.0
	draw_line(
		center + Vector2(-12.0 * flip_x, 4.0),
		center + Vector2(-21.0 * flip_x, -5.0 + tail_wag),
		Color(0.58, 0.34, 0.14),
		5.0
	)

	# Body & Collar
	draw_circle(center + Vector2(0, 5), 14.0, Color(0.76, 0.46, 0.20))
	draw_line(
		center + Vector2(-9, 1),
		center + Vector2(9, 1),
		Color(0.12, 0.72, 0.86),
		4.0
	)
	# Golden Scooby/Dooby collar tag
	draw_circle(center + Vector2(3.0 * flip_x, 4.0), 3.5, Color(0.98, 0.82, 0.18))

	# Paws
	var paw_shift := sin(bob_phase * 2.0) * (3.0 if is_moving else 0.5)
	draw_circle(center + Vector2(-7, 15 + paw_shift), 4.5, Color(0.55, 0.32, 0.12))
	draw_circle(center + Vector2(7, 15 - paw_shift), 4.5, Color(0.55, 0.32, 0.12))

	# Floppy Ears
	draw_circle(center + Vector2(-13, -7), 7.0, Color(0.45, 0.25, 0.09))
	draw_circle(center + Vector2(13, -7), 7.0, Color(0.45, 0.25, 0.09))

	# Head
	draw_circle(center + Vector2(0, -7), 12.5, Color(0.82, 0.52, 0.24))

	# Snout & Nose
	draw_circle(center + Vector2(4.0 * flip_x, -4.0), 6.5, Color(0.93, 0.74, 0.52))
	draw_circle(center + Vector2(6.5 * flip_x, -5.5), 3.0, Color(0.15, 0.12, 0.10))

	# Eyes
	draw_circle(center + Vector2(-3.5, -10.0), 3.0, Color.WHITE)
	draw_circle(center + Vector2(3.5, -10.0), 3.0, Color.WHITE)
	draw_circle(center + Vector2(-3.5 + 1.0 * flip_x, -10.0), 1.6, Color.BLACK)
	draw_circle(center + Vector2(3.5 + 1.0 * flip_x, -10.0), 1.6, Color.BLACK)

