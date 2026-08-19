import json
from pathlib import Path


class MazeEnvironment:
    EMPTY = 0
    START = 1
    END = 2
    PIT = 3
    BONE = 4

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    ACTIONS = [UP, DOWN, LEFT, RIGHT]

    def __init__(self, maze_path):
        self.maze_path = Path(maze_path)

        self.maze_data = None
        self.grid = None

        self.width = 0
        self.height = 0

        self.start_position = None
        self.end_positions = []
        self.bone_positions = []
        self.pit_positions = {}

        self.remaining_bones = set()

        self.dog_position = None
        self.step_count = 0

        self.load_maze()

    def load_maze(self):
        if not self.maze_path.exists():
            raise FileNotFoundError(
                f"Maze file not found: {self.maze_path}"
            )

        with open(self.maze_path, "r", encoding="utf-8") as file:
            self.maze_data = json.load(file)

        self.grid = self.maze_data["grid"]

        self.height = len(self.grid)
        self.width = len(self.grid[0])

        self._parse_grid()
        self.reset()

    def _parse_grid(self):
        self.start_position = None
        self.end_positions = []
        self.bone_positions = []
        self.pit_positions = {}

        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                position = (x, y)
                element = cell["element"]

                if element == self.START:
                    self.start_position = position

                elif element == self.END:
                    self.end_positions.append(position)

                elif element == self.BONE:
                    self.bone_positions.append(position)

                elif element == self.PIT:
                    destination = cell["pit_destination"]

                    if destination is not None:
                        self.pit_positions[position] = (
                            destination["x"],
                            destination["y"],
                        )

        if self.start_position is None:
            raise ValueError("Maze does not contain a Start position.")

    def reset(self):
        self.dog_position = self.start_position
        self.step_count = 0
        self.remaining_bones = set(self.bone_positions)

    def can_move(self, action):
        x, y = self.dog_position
        cell = self.grid[y][x]

        if action == self.UP:
            return not cell["top"]

        if action == self.DOWN:
            return not cell["bottom"]

        if action == self.LEFT:
            return not cell["left"]

        if action == self.RIGHT:
            return not cell["right"]

        raise ValueError(f"Unknown action: {action}")

    def step(self, action):
        if action not in self.ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        if not self.can_move(action):
            self.step_count += 1

            return {
                "position": self.dog_position,
                "moved": False,
                "teleported": False,
                "collected_bone": False,
                "reached_end": self.dog_position in self.end_positions,
                "action": action,
                "step": self.step_count,
            }

        x, y = self.dog_position

        if action == self.UP:
            self.dog_position = (x, y - 1)

        elif action == self.DOWN:
            self.dog_position = (x, y + 1)

        elif action == self.LEFT:
            self.dog_position = (x - 1, y)

        elif action == self.RIGHT:
            self.dog_position = (x + 1, y)

        self.step_count += 1

        teleported = False

        if self.dog_position in self.pit_positions:
            self.dog_position = self.pit_positions[self.dog_position]
            teleported = True

        collected_bone = False

        if self.dog_position in self.remaining_bones:
            self.remaining_bones.remove(self.dog_position)
            collected_bone = True

        reached_end = self.dog_position in self.end_positions

        return {
            "position": self.dog_position,
            "moved": True,
            "teleported": teleported,
            "collected_bone": collected_bone,
            "reached_end": reached_end,
            "action": action,
            "step": self.step_count,
        }

    def print_summary(self):
        print("\nMaze Summary")
        print("------------")
        print(f"Size: {self.width} x {self.height}")
        print(f"Start: {self.start_position}")
        print(f"Ends: {self.end_positions}")
        print(f"Bones: {self.bone_positions}")
        print(f"Pits: {self.pit_positions}")
        print(f"Dog position: {self.dog_position}")
        print(f"Remaining bones: {self.remaining_bones}")


if __name__ == "__main__":
    maze_path = input("Enter path to maze JSON: ").strip()

    environment = MazeEnvironment(maze_path)

    environment.print_summary()

    print("\nEnvironment initialized successfully.")