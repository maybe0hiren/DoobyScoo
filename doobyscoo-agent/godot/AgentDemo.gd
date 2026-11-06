extends Control

var client: DoobyScooAgentClient
var statusLabel: Label
var mapLabel: Label
var stepButton: Button
var autoPlay := false
var elapsed := 0.0
var currentState: Dictionary = {}

func _ready() -> void:
    client = DoobyScooAgentClient.new()
    add_child(client)
    client.map_loaded.connect(_on_map_loaded)
    client.step_completed.connect(_on_step)
    client.request_failed.connect(_on_error)
    client.training_started.connect(func(): statusLabel.text = "Training started on Python server")
    var layout := VBoxContainer.new()
    layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
    add_child(layout)
    statusLabel = Label.new()
    statusLabel.text = "Start the Python server, then load a maze"
    layout.add_child(statusLabel)
    var loadButton := Button.new()
    loadButton.text = "Load selected editor maze"
    loadButton.pressed.connect(func(): client.load_maze(MazeSession.editing_path))
    layout.add_child(loadButton)
    stepButton = Button.new()
    stepButton.text = "Dog: next action"
    stepButton.pressed.connect(func(): client.next_action())
    layout.add_child(stepButton)
    var autoButton := Button.new()
    autoButton.text = "Toggle autoplay"
    autoButton.pressed.connect(func(): autoPlay = not autoPlay)
    layout.add_child(autoButton)
    var resetButton := Button.new()
    resetButton.text = "Reset episode"
    resetButton.pressed.connect(func(): client.reset_agent())
    layout.add_child(resetButton)
    var learnButton := Button.new()
    learnButton.text = "Learn from played maps"
    learnButton.pressed.connect(func(): client.learn_from_played_maps())
    layout.add_child(learnButton)
    mapLabel = Label.new()
    mapLabel.add_theme_font_size_override("font_size", 17)
    layout.add_child(mapLabel)

func _process(delta: float) -> void:
    if not autoPlay or currentState.is_empty() or currentState.get("done", false):
        return
    elapsed += delta
    if elapsed > 0.25 and not stepButton.disabled:
        elapsed = 0.0
        stepButton.disabled = true
        client.next_action()

func _on_map_loaded(state: Dictionary) -> void:
    currentState = state
    stepButton.disabled = false
    _draw_state()

func _on_step(result: Dictionary) -> void:
    currentState = result["state"]
    stepButton.disabled = false
    statusLabel.text = "Action: %s | Reward: %.2f | Win: %s" % [str(result["action"]), float(result["reward"]), str(result["won"])]
    _draw_state()
    if currentState.get("done", false):
        autoPlay = false

func _on_error(message: String) -> void:
    autoPlay = false
    stepButton.disabled = false
    statusLabel.text = "Error: " + message

func _draw_state() -> void:
    var lines: Array[String] = []
    var dog: Array = currentState["position"]
    for y in range(currentState["grid"].size()):
        var line := ""
        for x in range(currentState["grid"][y].size()):
            var cell: Dictionary = currentState["grid"][y][x]
            var symbol := "."
            var element := int(cell["element"])
            if element == 2: symbol = "E"
            elif element == 3: symbol = "P"
            elif element == 4: symbol = "B"
            elif element == 1: symbol = "S"
            if element == 4 and not ([x, y] in currentState["remainingBones"]): symbol = "."
            if dog[0] == x and dog[1] == y: symbol = "D"
            line += symbol + "  "
        lines.append(line)
    mapLabel.text = "Steps: %d | Score: %d\n%s" % [int(currentState["steps"]), int(currentState["score"]), "\n".join(lines)]
