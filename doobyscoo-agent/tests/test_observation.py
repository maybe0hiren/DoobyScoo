import unittest
import numpy as np
from doobyscoo.environment import (
    ACTION_MASK_OFFSET,
    BONE_FEATURES_PER_SLOT,
    BONE_OBSERVATION_OFFSET,
    EXPLORATION_MEMORY_OFFSET,
    LOCAL_VIEW_CENTER_INDEX,
    LOCAL_VIEW_OFFSET,
    LOCAL_VIEW_SIDE,
    LOCAL_VIEW_SIZE,
    MAX_BONES,
    MazeEnvironment,
    NAVIGATION_OFFSET,
    OBJECTIVE_OFFSET,
    OBSERVATION_SIZE,
    OBS_BLOCKED,
    OBS_EMPTY,
    OBS_BONE,
    OBS_END,
    OBS_PIT,
    OBS_UNKNOWN,
)
from tests.test_environment import makeGrid, sampleMaze


class ObservationTests(unittest.TestCase):
    def testObservationShapeAndRange(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        obs = env.observe()
        self.assertEqual(obs.shape, (OBSERVATION_SIZE,))
        self.assertEqual(obs.shape, (95,))
        self.assertEqual(obs.dtype, np.float32)
        self.assertTrue(np.all(obs[:BONE_OBSERVATION_OFFSET] >= 0.0))
        self.assertTrue(np.all(obs[:BONE_OBSERVATION_OFFSET] <= 1.0))
        self.assertTrue(np.all(obs >= -1.0))
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
        self.assertEqual(raw[8], 0.0)
        self.assertEqual(raw[11], 0.0)
        self.assertEqual(raw[12], 1.0)

        env.step(3)
        rawAfterBone = env.observeRaw()
        self.assertEqual(rawAfterBone[0], OBS_PIT)
        self.assertEqual(rawAfterBone[5], 1.0)
        self.assertAlmostEqual(float(rawAfterBone[7]), 0.0)
        self.assertEqual(rawAfterBone[10], 1.0)
        self.assertEqual(rawAfterBone[11], 0.0)

        env.step(2)
        env.step(3)
        rawMulti = env.observeRaw()
        self.assertEqual(rawMulti[10], 2.0)

    def testFiveByFiveLocalVisionShapeCentreBoundsAndUnknowns(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        # Start is at (0, 2) in a 3x3 maze
        view = env.localView()
        self.assertEqual(view.shape, (LOCAL_VIEW_SIDE, LOCAL_VIEW_SIDE))
        self.assertEqual(view.size, LOCAL_VIEW_SIZE)
        self.assertEqual(view.shape, (5, 5))

        # Centre cell (row=2, col=2) is always the Dog's current position (0, 2) -> empty
        self.assertEqual(int(view[2, 2]), int(OBS_EMPTY))
        raw = env.observeRaw()
        self.assertEqual(float(raw[LOCAL_VIEW_OFFSET + LOCAL_VIEW_CENTER_INDEX]), OBS_EMPTY)

        # Out-of-bounds cells (col < 2 implies x < 0; row > 2 implies y > 2) must be OBS_BLOCKED
        self.assertTrue(np.all(view[:, 0] == int(OBS_BLOCKED)))
        self.assertTrue(np.all(view[:, 1] == int(OBS_BLOCKED)))
        self.assertTrue(np.all(view[3, :] == int(OBS_BLOCKED)))
        self.assertTrue(np.all(view[4, :] == int(OBS_BLOCKED)))

        # Immediate reachable neighbours from (0, 2): UP (0, 1) is OBS_EMPTY, RIGHT (1, 2) is OBS_BONE
        self.assertEqual(int(view[1, 2]), int(OBS_EMPTY))
        self.assertEqual(int(view[2, 3]), int(OBS_BONE))

        # Unexplored non-adjacent in-bounds cells like (0, 0) at view[0, 2], (1, 1) at view[1, 3], (2, 0) at view[0, 4]
        # must be marked OBS_UNKNOWN (not exposing hidden walls, pits, or End)
        self.assertEqual(int(view[0, 2]), int(OBS_UNKNOWN))
        self.assertEqual(int(view[1, 3]), int(OBS_UNKNOWN))
        self.assertEqual(int(view[0, 4]), int(OBS_UNKNOWN))
        self.assertEqual(int(view[2, 4]), int(OBS_UNKNOWN))

        # After stepping RIGHT to (1, 2), the 5x5 local view shifts so (1, 2) is now at centre (2, 2)
        env.step(3)
        viewAfter = env.localView()
        self.assertEqual(int(viewAfter[2, 2]), int(OBS_BONE))   # Bone at (1, 2) was collected on this step
        self.assertEqual(int(viewAfter[2, 1]), int(OBS_EMPTY))  # Previous cell (0, 2) is now to the LEFT
        self.assertEqual(int(viewAfter[1, 2]), int(OBS_PIT))    # Reachable UP neighbour (1, 1) is now visible as PIT
        self.assertEqual(int(viewAfter[2, 3]), int(OBS_EMPTY))  # Reachable RIGHT neighbour (2, 2) is now visible
        # Stepping RIGHT again to (2, 2) leaves (1, 2) as OBS_EMPTY (Bone already collected)
        env.step(3)
        viewAfter2 = env.localView()
        self.assertEqual(int(viewAfter2[2, 1]), int(OBS_EMPTY))

    def testNavigationAwarenessDeadEndCorridorAndJunction(self):
        # Construct a 3x3 maze where:
        # (0, 2) Start has only 1 exit UP to (0, 1) -> Start is 1-exit leaf, (0, 1) is a junction with 3 exits:
        # UP to (0, 0) [dead-end room], DOWN to (0, 2) [Start], RIGHT to (1, 1) [corridor to (2, 1) End]
        grid = makeGrid(3, 3)
        grid[2][0]["element"] = 1  # Start at (0, 2)
        grid[1][2]["element"] = 2  # End at (2, 1)
        # Wall off (0, 2) -> (1, 2) so (0, 2) only opens UP
        grid[2][0]["right"] = True
        grid[2][1]["left"] = True
        # Seal (0, 0) on the right so (0, 0) only connects DOWN to (0, 1) -> dead end!
        grid[0][0]["right"] = True
        grid[0][1]["left"] = True
        # Make (1, 1) a 2-exit horizontal corridor connecting (0, 1) and (2, 1) by sealing top & bottom of (1, 1)
        grid[1][1]["top"] = True
        grid[0][1]["bottom"] = True
        grid[1][1]["bottom"] = True
        grid[2][1]["top"] = True

        env = MazeEnvironment({"metadata": {"maze_name": "nav_test"}, "grid": grid}, maxSteps=30)

        # At (0, 2), only UP is legal (1 exit)
        navStart = env.navigationInfo()
        self.assertEqual(navStart["openExitsCount"], 1)
        self.assertFalse(navStart["isCorridor"])
        self.assertFalse(navStart["isJunction"])
        self.assertFalse(navStart["hasMultipleExits"])
        self.assertEqual(navStart["unexploredExits"], [True, False, False, False])

        # Step UP to (0, 1): 3 legal exits (UP to (0,0), DOWN to (0,2), RIGHT to (1,1)) -> Junction!
        env.step(0)
        navJunc = env.navigationInfo()
        self.assertTrue(navJunc["isJunction"])
        self.assertTrue(navJunc["hasMultipleExits"])
        self.assertEqual(navJunc["openExitsCount"], 3)
        # DOWN (dir 1) was already visited; UP (dir 0) and RIGHT (dir 3) are unexplored
        self.assertEqual(navJunc["exploredExits"], [False, True, False, False])
        self.assertEqual(navJunc["unexploredExits"], [True, False, False, True])

        # Step UP into (0, 0): only 1 exit (DOWN back to (0, 1)) -> Dead End!
        env.step(0)
        navDead = env.navigationInfo()
        self.assertTrue(navDead["isDeadEnd"])
        self.assertEqual(navDead["openExitsCount"], 1)

        # Return DOWN to junction (0, 1): now UP (dir 0 -> (0,0)) and DOWN (dir 1 -> degree-1 Start (0,2))
        # are both recognized as 1-exit dead-end pockets, leaving RIGHT (dir 3) as the only non-dead-end exit!
        env.step(1)
        navJuncAfter = env.navigationInfo()
        self.assertEqual(navJuncAfter["deadEndExits"], [True, True, False, False])
        self.assertEqual(navJuncAfter["nonDeadEndExitsCount"], 1)
        self.assertEqual(navJuncAfter["unexploredExits"], [False, False, False, True])

        # Step RIGHT into (1, 1): 2 exits (LEFT and RIGHT) -> Corridor!
        env.step(3)
        navCorr = env.navigationInfo()
        self.assertTrue(navCorr["isCorridor"])
        self.assertFalse(navCorr["isJunction"])
        self.assertEqual(navCorr["openExitsCount"], 2)

    def testExplorationMemoryPersistenceAndEpisodeReset(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=25)
        mem0 = env.explorationMemory()
        self.assertEqual(mem0["episodic"]["visitedCells"], [[0, 2]])
        self.assertEqual(mem0["episodic"]["discoveredPits"], [])
        self.assertEqual(mem0["episodic"]["collectedBones"], [])

        # Step RIGHT to Bone (1, 2) -> discovers PIT at (1, 1) via local adjacency and collects Bone at (1, 2)
        env.step(3)
        mem1 = env.explorationMemory()
        self.assertIn([1, 2], mem1["episodic"]["visitedCells"])
        self.assertEqual(mem1["episodic"]["collectedBones"], [[1, 2]])
        self.assertIn([1, 1], mem1["episodic"]["discoveredPits"])
        self.assertEqual(len(mem1["episodic"]["traversedConnections"]), 1)
        # Hidden Pit or walls outside explored area must NOT be in discoveredPits
        self.assertEqual(len(mem1["episodic"]["discoveredPits"]), 1)

        # Resetting the environment clears episode-specific memory for the policy while retaining trainingDiagnostics
        env.reset()
        memReset = env.explorationMemory()
        self.assertEqual(memReset["episodic"]["visitedCells"], [[0, 2]])
        self.assertEqual(memReset["episodic"]["collectedBones"], [])
        self.assertEqual(memReset["episodic"]["discoveredPits"], [])
        self.assertEqual(memReset["episodic"]["traversedConnections"], [])
        self.assertEqual(memReset["trainingDiagnostics"]["attemptsCompleted"], 1)
        self.assertEqual(memReset["trainingDiagnostics"]["cumulativeVisitedCellsCount"], 2)

    def testFiveBoneLocationObservationsAndObjectiveAwareness(self):
        grid = makeGrid(3, 3)
        grid[2][0]["element"] = 1  # Start at (0, 2)
        grid[2][2]["element"] = 2  # End at (2, 2)
        boneCoords = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 2)]
        for bx, by in boneCoords:
            grid[by][bx]["element"] = 4
        maze = {"metadata": {"maze_name": "obs_bones"}, "grid": grid}
        env = MazeEnvironment(maze, maxSteps=25)

        boneObs0 = env.boneObservations()
        self.assertEqual(len(boneObs0), MAX_BONES)
        expectedOrder = sorted(boneCoords, key=lambda p: (p[1], p[0]))
        for slotIdx, (bx, by) in enumerate(expectedOrder):
            slot = boneObs0[slotIdx]
            self.assertTrue(slot["present"])
            self.assertFalse(slot["collected"])
            self.assertEqual(slot["dx"], bx - 0)
            self.assertEqual(slot["dy"], by - 2)

        obj0 = env.objectiveInfo()
        # Nearest End is at (2, 2), so from (0, 2) endDxNorm = +1.0, endDyNorm = 0.0
        self.assertAlmostEqual(obj0["endDxNorm"], 1.0, places=5)
        self.assertAlmostEqual(obj0["endDyNorm"], 0.0, places=5)
        self.assertEqual(obj0["activeObjective"]["type"], "bone")

        # Step RIGHT toward Bone at (1, 2) -> positive objective progress and Bone collected
        env.step(3)
        obj1 = env.objectiveInfo()
        self.assertGreater(obj1["objectiveProgress"], 0.0)
        self.assertTrue(obj1["madeProgress"])
        obs1 = env.observe()
        slot4Base = BONE_OBSERVATION_OFFSET + 4 * BONE_FEATURES_PER_SLOT
        self.assertAlmostEqual(float(obs1[slot4Base + 2]), 1.0, places=5)
        # Objective vector at OBJECTIVE_OFFSET..OBJECTIVE_OFFSET+6 is finite and normalized in [-1, 1]
        objVec = obs1[OBJECTIVE_OFFSET : OBJECTIVE_OFFSET + 6]
        self.assertEqual(objVec.shape, (6,))
        self.assertTrue(np.all(objVec >= -1.0) and np.all(objVec <= 1.0))

    def testPartialObservabilityNoGlobalLeakage(self):
        mazeA = sampleMaze()
        mazeB = sampleMaze()
        # Modify distant walls and distant pits outside the 4 immediate neighbors while keeping Bone locations identical
        mazeB["grid"][0][0]["right"] = True
        mazeB["grid"][0][1]["left"] = True
        mazeB["grid"][0][1]["element"] = 3
        mazeB["grid"][0][1]["pit_destination"] = {"x": 2, "y": 1}
        envA = MazeEnvironment(mazeA, maxSteps=20)
        envB = MazeEnvironment(mazeB, maxSteps=20)
        np.testing.assert_allclose(envA.observe(), envB.observe())
        np.testing.assert_array_equal(envA.localView(), envB.localView())


if __name__ == "__main__":
    unittest.main()
