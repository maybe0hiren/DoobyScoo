import unittest
from doobyscoo.environment import MazeEnvironment, RewardConfig, OBSERVATION_SIZE, validateMaze, checkSolvability


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
        _, rew, done, info = env.step(2)
        self.assertFalse(info["moved"])
        self.assertTrue(info["wallBump"])
        self.assertIn("wall", info["rewardBreakdown"])
        self.assertLess(rew, env.rewardConfig.movePenalty)
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
        self.assertEqual(obs.shape, (OBSERVATION_SIZE,))
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

    def testBoneRewardSubstantialAndOnlyOnce(self):
        maze = sampleMaze()
        # Add a second bone at (0, 1) so collecting (1, 2) does not also trigger allBonesBonus
        maze["grid"][1][0]["element"] = 4
        rc = RewardConfig()
        env = MazeEnvironment(maze, maxSteps=20, rewardConfig=rc)

        # First step right onto Bone at (1, 2)
        _, rewardBone, _, info1 = env.step(3)
        self.assertTrue(info1["bone"])
        self.assertIn("bone", info1["rewardBreakdown"])
        self.assertAlmostEqual(info1["rewardBreakdown"]["bone"], rc.boneReward)
        self.assertGreater(rewardBone, 2.0)

        # Step left back to start (0, 2), then right onto (1, 2) again: bone must NOT be awarded a second time
        env.step(2)
        _, rewardRepeat, _, info3 = env.step(3)
        self.assertFalse(info3["bone"])
        self.assertNotIn("bone", info3["rewardBreakdown"])
        self.assertEqual(info3["bonesCollected"], 1)
        self.assertLess(rewardRepeat, 0.0)

    def testFirstVisitRevisitAndRepeatedRevisitPenaltiesAndReset(self):
        rc = RewardConfig()
        env = MazeEnvironment(sampleMaze(), maxSteps=30, rewardConfig=rc)
        # Step UP to (0, 1): first visit to (0, 1) -> penalty is 0
        _, rFirst, _, infoFirst = env.step(0)
        self.assertTrue(infoFirst["newCell"])
        self.assertFalse(infoFirst["revisit"])
        self.assertEqual(infoFirst["visitCount"], 1)
        self.assertEqual(rc.revisitPenaltyForVisit(1), 0.0)
        self.assertIn("novelty", infoFirst["rewardBreakdown"])
        self.assertNotIn("revisit", infoFirst["rewardBreakdown"])
        self.assertAlmostEqual(rFirst, rc.movePenalty + rc.noveltyReward, places=5)

        # Step DOWN back to Start (0, 2): 2nd visit -> penalty is -2
        _, rRev2, _, infoRev2 = env.step(1)
        self.assertFalse(infoRev2["newCell"])
        self.assertTrue(infoRev2["revisit"])
        self.assertEqual(infoRev2["visitCount"], 2)
        self.assertAlmostEqual(infoRev2["rewardBreakdown"]["revisit"], -2.0, places=5)

        # Step UP to (0, 1) (2nd visit -> -2), then DOWN to (0, 2) (3rd visit -> -4)
        env.step(0)
        _, rRev3, _, infoRev3 = env.step(1)
        self.assertTrue(infoRev3["revisit"])
        self.assertEqual(infoRev3["visitCount"], 3)
        self.assertAlmostEqual(infoRev3["rewardBreakdown"]["revisit"], -4.0, places=5)
        self.assertLess(rRev3, rRev2)

        # Step UP to (0, 1) (3rd visit -> -4), then DOWN to (0, 2) (4th visit -> -6)
        env.step(0)
        _, rRev4, _, infoRev4 = env.step(1)
        self.assertEqual(infoRev4["visitCount"], 4)
        self.assertAlmostEqual(infoRev4["rewardBreakdown"]["revisit"], -6.0, places=5)

        # Step UP to (0, 1) (4th visit -> -6), then DOWN to (0, 2) (5th visit -> -8)
        env.step(0)
        _, _, _, infoRev5 = env.step(1)
        self.assertEqual(infoRev5["visitCount"], 5)
        self.assertAlmostEqual(infoRev5["rewardBreakdown"]["revisit"], -8.0, places=5)

        # Step UP to (0, 1) (5th visit -> -8), then DOWN to (0, 2) (6th visit -> capped at -8)
        env.step(0)
        _, _, _, infoRev6 = env.step(1)
        self.assertEqual(infoRev6["visitCount"], 6)
        self.assertAlmostEqual(infoRev6["rewardBreakdown"]["revisit"], -8.0, places=5)

        # Verify revisit tracking metrics
        self.assertEqual(env.revisits, 9)
        self.assertEqual(len(env.visited), 2)
        self.assertEqual(env.maxVisitCount(), 6)
        self.assertEqual(env.mostFrequentlyRevisitedCell(), [0, 2])
        self.assertAlmostEqual(env.revisitPercentage(), 90.0, places=5)

        # Reset must clear visitation history
        env.reset()
        self.assertEqual(env.revisits, 0)
        self.assertEqual(env.visitCounts, {(0, 2): 1})
        self.assertEqual(env.pitVisitCounts, {})
        self.assertEqual(env.edgeCounts, {})

    def testScoreLimit100EnforcementAndEpisodeRestart(self):
        maze = sampleMaze()
        # Add top wall on Start (0, 2) so action UP (0) bumps the wall in place without winning
        maze["grid"][2][0]["top"] = True
        maze["grid"][1][0]["bottom"] = True
        env = MazeEnvironment(maze, maxSteps=500, enforceScoreLimit=True)

        # Take 98 steps -> trainingScore == 98
        for _ in range(98):
            _, _, done, info = env.step(0)
            self.assertFalse(done)

        # Step 99 -> trainingScore == 99 (continues episode)
        _, _, done99, info99 = env.step(0)
        self.assertEqual(info99["trainingScore"], 99.0)
        self.assertFalse(done99)
        self.assertFalse(info99["failed"])
        self.assertFalse(info99["scoreLimitExceeded"])

        # Step 100 -> trainingScore == 100 (allowed; continues episode)
        _, _, done100, info100 = env.step(0)
        self.assertEqual(info100["trainingScore"], 100.0)
        self.assertFalse(done100)
        self.assertFalse(info100["failed"])
        self.assertFalse(info100["scoreLimitExceeded"])

        # Step 101 -> trainingScore == 101 (> 100 -> terminates immediately as failed)
        _, reward101, done101, info101 = env.step(0)
        self.assertEqual(info101["trainingScore"], 101.0)
        self.assertTrue(done101)
        self.assertFalse(info101["won"])
        self.assertTrue(info101["failed"])
        self.assertTrue(info101["scoreLimitExceeded"])
        self.assertIn("scoreLimit", info101["rewardBreakdown"])
        self.assertIn("failure", info101["rewardBreakdown"])
        self.assertLess(reward101, -20.0)
        self.assertEqual(len(env.actionHistory), 101)
        self.assertEqual(len(env.positionHistory), 102)

        # Restarting the episode resets episode state cleanly
        env.reset()
        self.assertFalse(env.done)
        self.assertFalse(env.failed)
        self.assertFalse(env.scoreLimitExceeded)
        self.assertEqual(env.currentTrainingScore(), 0.0)
        self.assertEqual(env.steps, 0)

    def testFiveBoneCollectionRewardSchedule(self):
        # Create a 3x3 maze with 5 Bones at (0,1), (0,0), (1,0), (2,0), (2,1) and End at (2,2)
        grid = makeGrid(3, 3)
        grid[2][0]["element"] = 1  # Start at (0, 2)
        grid[2][2]["element"] = 2  # End at (2, 2)
        boneCoords = [(0, 1), (0, 0), (1, 0), (2, 0), (2, 1)]
        for bx, by in boneCoords:
            grid[by][bx]["element"] = 4
        maze = {"metadata": {"maze_name": "five_bone_test"}, "grid": grid}
        env = MazeEnvironment(maze, maxSteps=50)

        # Path to collect all 5 Bones in order: UP, UP, RIGHT, RIGHT, DOWN
        actions = [0, 0, 3, 3, 1]
        expectedReductions = [-10.0, -10.0, -10.0, -10.0, -20.0]
        expectedBoneRewards = [10.0, 10.0, 10.0, 10.0, 20.0]
        cumulativeReduction = 0.0

        for idx, (act, expRed, expRew) in enumerate(zip(actions, expectedReductions, expectedBoneRewards), start=1):
            _, _, done, info = env.step(act)
            self.assertFalse(done)
            self.assertTrue(info["bone"])
            self.assertEqual(info["bonesCollected"], idx)
            self.assertAlmostEqual(info["boneScoreReduction"], expRed, places=5)
            self.assertAlmostEqual(info["boneReward"], expRew, places=5)
            self.assertAlmostEqual(
                info["rewardBreakdown"]["bone"] + info["rewardBreakdown"].get("allBones", 0.0),
                expRew,
                places=5,
            )
            cumulativeReduction += expRed
            self.assertAlmostEqual(info["totalBoneScoreReduction"], cumulativeReduction, places=5)
            self.assertAlmostEqual(info["trainingScore"], idx + cumulativeReduction, places=5)

        # Total score reduction for collecting all 5 Bones must be -60.0
        self.assertAlmostEqual(env.totalBoneScoreReduction, -60.0, places=5)
        self.assertAlmostEqual(env.currentTrainingScore(), 5.0 - 60.0, places=5)
        # Official score formula remains unchanged: Steps - 5 * Bones = 5 - 25 = -20
        self.assertEqual(env.currentScore(), 5 - 5 * 5)

        # Re-entering a collected Bone cell (UP to (2, 0)) gives no additional Bone reward
        _, _, _, infoRepeat = env.step(0)
        self.assertFalse(infoRepeat["bone"])
        self.assertEqual(infoRepeat["boneScoreReduction"], 0.0)
        self.assertNotIn("bone", infoRepeat["rewardBreakdown"])
        self.assertAlmostEqual(env.totalBoneScoreReduction, -60.0, places=5)

    def testPitTeleportationVisitationTracking(self):
        env = MazeEnvironment(sampleMaze(), maxSteps=20)
        env.step(3)  # move to (1, 2)
        _, _, _, info = env.step(0)  # step into pit at (1, 1) -> teleports to (2, 1)
        self.assertTrue(info["teleported"])
        self.assertEqual(info["pitEntered"], [1, 1])
        self.assertEqual(info["position"], [2, 1])
        # Both the pit square (1, 1) and destination (2, 1) must be tracked as visited
        self.assertEqual(env.pitVisitCounts.get((1, 1), 0), 1)
        self.assertEqual(env.visitCounts.get((2, 1), 0), 1)
        self.assertGreaterEqual(env.visitCountAt((1, 1)), 1)
        self.assertGreaterEqual(env.visitCountAt((2, 1)), 1)

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
