import unittest
from doobyscoo.environment import MazeEnvironment
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.training import collectEpisode, updatePolicy
import torch


def sampleMaze():
    grid = [[{"element": 0, "top": y == 0, "bottom": y == 2, "left": x == 0, "right": x == 2, "pit_destination": None} for x in range(3)] for y in range(3)]
    grid[2][0]["element"] = 1
    grid[0][2]["element"] = 2
    grid[2][1]["element"] = 4
    grid[1][1]["element"] = 3
    grid[1][1]["pit_destination"] = {"x": 2, "y": 1}
    return {"grid": grid}


class AgentTests(unittest.TestCase):
    def testMovement(self):
        env = MazeEnvironment(sampleMaze(), 20)
        self.assertEqual(env.observe().shape, (22,))
        _, _, _, info = env.step(3)
        self.assertTrue(info["bone"])
        self.assertEqual(info["score"], -4)
        _, _, _, info = env.step(0)
        self.assertTrue(info["teleported"])
        self.assertEqual(info["position"], [2, 1])
        _, _, done, info = env.step(0)
        self.assertTrue(done)
        self.assertTrue(info["won"])

    def testTraining(self):
        model = RecurrentPolicy()
        episodes = [collectEpisode(model, sampleMaze(), 12) for _ in range(2)]
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0003)
        loss = updatePolicy(model, optimizer, episodes, epochs=1)
        self.assertTrue(float("-inf") < loss < float("inf"))


if __name__ == "__main__":
    unittest.main()
