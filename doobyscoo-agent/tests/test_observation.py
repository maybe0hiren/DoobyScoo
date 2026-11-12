import unittest
import numpy as np
from doobyscoo.environment import (
    MazeEnvironment,
    OBSERVATION_SIZE,
    OBS_BLOCKED,
    OBS_EMPTY,
    OBS_BONE,
    OBS_END,
    OBS_PIT,
)
from tests.test_environment import sampleMaze


class ObservationTests(unittest.TestCase):
    def testObservationShapeAndRange(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        obs = env.observe()
        self.assertEqual(obs.shape, (OBSERVATION_SIZE,))
        self.assertEqual(obs.shape, (23,))
        self.assertEqual(obs.dtype, np.float32)
        self.assertTrue(np.all(obs >= 0.0))
        self.assertTrue(np.all(obs <= 1.0))

    def testDirectionalCellAndVisitationFeatures(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        raw = env.observeRaw()
        self.assertEqual(raw[0], OBS_EMPTY)
        self.assertEqual(raw[1], OBS_BLOCKED)
        self.assertEqual(raw[2], OBS_BLOCKED)
        self.assertEqual(raw[3], OBS_BONE)
        self.assertEqual(raw[4], 0.0)
        self.assertEqual(raw[5], 0.0)
        self.assertEqual(raw[6], 0.0)
        self.assertAlmostEqual(float(raw[7]), 1.0)
        # Neighbour UP (0, 1) and RIGHT (1, 2) are both unvisited at episode start
        self.assertEqual(raw[8], 0.0)
        self.assertEqual(raw[11], 0.0)
        # Current square (0, 2) has visit count 1
        self.assertEqual(raw[12], 1.0)

        # Step right onto Bone at (1, 2)
        env.step(3)
        rawAfterBone = env.observeRaw()
        self.assertEqual(rawAfterBone[0], OBS_PIT)
        self.assertEqual(rawAfterBone[5], 1.0)
        self.assertAlmostEqual(float(rawAfterBone[7]), 0.0)
        # From (1, 2), neighbour LEFT (0, 2) has been visited once (raw[10] == 1.0),
        # while neighbour RIGHT (2, 2) is unexplored (raw[11] == 0.0)
        self.assertEqual(rawAfterBone[10], 1.0)
        self.assertEqual(rawAfterBone[11], 0.0)

        # Revisit (0, 2) and return to (1, 2): neighbour LEFT (0, 2) now has 2 visits
        env.step(2)
        env.step(3)
        rawMulti = env.observeRaw()
        self.assertEqual(rawMulti[10], 2.0)

    def testPartialObservabilityNoGlobalLeakage(self):
        mazeA = sampleMaze()
        mazeB = sampleMaze()
        mazeB["grid"][0][0]["right"] = True
        mazeB["grid"][0][1]["left"] = True
        envA = MazeEnvironment(mazeA, maxSteps=20)
        envB = MazeEnvironment(mazeB, maxSteps=20)
        np.testing.assert_allclose(envA.observe(), envB.observe())


if __name__ == "__main__":
    unittest.main()
