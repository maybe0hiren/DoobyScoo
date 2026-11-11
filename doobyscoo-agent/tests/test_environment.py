import unittest
from doobyscoo.environment import MazeEnvironment, validateMaze, checkSolvability


def makeGrid(width=3, height=3):
    return [
        [
            {
                "element": 0,
                "top": y == 0,
                "bottom": y == height - 1,
                "left": x == 0,
                "right": x == width - 1,
                "pit_destination": None,
                "visited": False,
            }
            for x in range(width)
        ]
        for y in range(height)
    ]


def sampleMaze():
    grid = makeGrid(3, 3)
    grid[2][0]["element"] = 1
    grid[0][2]["element"] = 2
    grid[2][1]["element"] = 4
    grid[1][1]["element"] = 3
    grid[1][1]["pit_destination"] = {"x": 2, "y": 1}
    return {"metadata": {"maze_name": "sample"}, "grid": grid}


class EnvironmentTests(unittest.TestCase):
    def testValidMazeLoading(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=25)
        self.assertEqual(env.position, (0, 2))
        self.assertEqual(env.steps, 0)
        self.assertFalse(env.done)
        self.assertEqual(len(env.bones), 1)

    def testInvalidMazeRejection(self):
        with self.assertRaises(ValueError):
            MazeEnvironment({"grid": []})

        noStart = sampleMaze()
        noStart["grid"][2][0]["element"] = 0
        with self.assertRaises(ValueError):
            MazeEnvironment(noStart)

        twoStarts = sampleMaze()
        twoStarts["grid"][0][0]["element"] = 1
        with self.assertRaises(ValueError):
            MazeEnvironment(twoStarts)

        noEnd = sampleMaze()
        noEnd["grid"][0][2]["element"] = 0
        with self.assertRaises(ValueError):
            MazeEnvironment(noEnd)

        tooManyBones = sampleMaze()
        for x in range(3):
            for y in range(2):
                if tooManyBones["grid"][y][x]["element"] == 0:
                    tooManyBones["grid"][y][x]["element"] = 4
        tooManyBones["grid"][2][2]["element"] = 4
        with self.assertRaises(ValueError):
            MazeEnvironment(tooManyBones)

        badPit = sampleMaze()
        badPit["grid"][1][1]["pit_destination"] = {"x": 99, "y": 99}
        with self.assertRaises(ValueError):
            MazeEnvironment(badPit)

        cyclicPit = sampleMaze()
        cyclicPit["grid"][1][1]["pit_destination"] = {"x": 1, "y": 0}
        cyclicPit["grid"][0][1]["element"] = 3
        cyclicPit["grid"][0][1]["pit_destination"] = {"x": 1, "y": 1}
        with self.assertRaises(ValueError):
            MazeEnvironment(cyclicPit)

        wallMismatch = sampleMaze()
        wallMismatch["grid"][0][0]["right"] = True
        wallMismatch["grid"][0][1]["left"] = False
        with self.assertRaises(ValueError):
            MazeEnvironment(wallMismatch)

    def testBoundaryAndWallBlocking(self):
        maze = sampleMaze()
        maze["grid"][2][0]["top"] = True
        maze["grid"][1][0]["bottom"] = True
        env = MazeEnvironment(maze, maxSteps=20)
        _, _, done, info = env.step(2)
        self.assertFalse(info["moved"])
        self.assertEqual(info["position"], [0, 2])
        self.assertEqual(info["steps"], 1)
        self.assertFalse(done)

        _, _, done, info = env.step(0)
        self.assertFalse(info["moved"])
        self.assertEqual(info["position"], [0, 2])
        self.assertEqual(info["steps"], 2)

    def testNormalMovementBoneCollectionPitAndEnd(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        obs, _, done, info = env.step(3)
        self.assertEqual(obs.shape, (8,))
        self.assertTrue(info["moved"])
        self.assertTrue(info["bone"])
        self.assertEqual(info["bonesCollected"], 1)
        self.assertEqual(info["score"], 1 - 5 * 1)
        self.assertFalse(done)

        _, _, done, info = env.step(0)
        self.assertTrue(info["teleported"])
        self.assertEqual(info["position"], [2, 1])
        self.assertFalse(done)

        _, _, done, info = env.step(0)
        self.assertTrue(done)
        self.assertTrue(info["won"])
        self.assertEqual(info["position"], [2, 0])
        self.assertEqual(info["score"], 3 - 5 * 1)

        with self.assertRaises(RuntimeError):
            env.step(0)

    def testPitTeleportationOntoBoneAndEnd(self):
        maze = sampleMaze()
        maze["grid"][1][2]["element"] = 4
        env = MazeEnvironment(maze, maxSteps=20)
        env.step(3)
        _, _, done, info = env.step(0)
        self.assertTrue(info["teleported"])
        self.assertTrue(info["bone"])
        self.assertEqual(info["bonesCollected"], 2)
        self.assertFalse(done)

        mazeToEnd = sampleMaze()
        mazeToEnd["grid"][1][1]["pit_destination"] = {"x": 2, "y": 0}
        env2 = MazeEnvironment(mazeToEnd, maxSteps=20)
        env2.step(3)
        _, _, done2, info2 = env2.step(0)
        self.assertTrue(info2["teleported"])
        self.assertTrue(info2["won"])
        self.assertTrue(done2)

    def testSolvabilityChecker(self):
        solvableRes = checkSolvability(sampleMaze()["grid"], requireAllBones=True)
        self.assertTrue(solvableRes["solvable"])

        unsolvable = sampleMaze()
        unsolvable["grid"][0][2]["left"] = True
        unsolvable["grid"][0][1]["right"] = True
        unsolvable["grid"][0][2]["bottom"] = True
        unsolvable["grid"][1][2]["top"] = True
        unsolvableRes = validateMaze(unsolvable, requireSolvable=True)
        self.assertFalse(unsolvableRes["valid"])


if __name__ == "__main__":
    unittest.main()

