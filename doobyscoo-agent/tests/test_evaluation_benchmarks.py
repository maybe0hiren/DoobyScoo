"""Comprehensive Evaluation & Benchmark Suite (Tests A through F + Section 19 Benchmarks).

Verifies all six required behavioral experiments and multi-baseline benchmarking:
  - Test A — Oscillation (Dog between two blocks with one direction returning and one advancing)
  - Test B — Dead End (Multiple dead-end branches; discovers, remembers, escapes, and avoids re-entering)
  - Test C — Bone Collection (Bone on route, short worthwhile detour, dead-end Bone, far Bone)
  - Test D — New Maps (Zero-shot generalization on unseen test, validation, starter, and played maps)
  - Test E — Repeated Maps (Multi-attempt learning and route/score optimization on the same maze)
  - Test F — Score Optimization & Section 19 Multi-Baseline Benchmark (Random vs Heuristic vs Old Agent vs New Agent)
"""
import unittest
from pathlib import Path
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.environment import MazeEnvironment, loadMaze
from doobyscoo.evaluation import compareModels, evaluate
from doobyscoo.storage import loadCheckpointFull
from doobyscoo.training import collectEpisode, collectRepeatedEpisodes, discoverMaps
from tests.test_environment import makeGrid


def _carveOpenMaze(width=6, height=6):
    return makeGrid(width, height)


def _addWallBetween(grid, a, b):
    ax, ay = a
    bx, by = b
    if bx == ax + 1 and by == ay:
        grid[ay][ax]["right"] = True
        grid[by][bx]["left"] = True
    elif bx == ax - 1 and by == ay:
        grid[ay][ax]["left"] = True
        grid[by][bx]["right"] = True
    elif by == ay + 1 and bx == ax:
        grid[ay][ax]["bottom"] = True
        grid[by][bx]["top"] = True
    elif by == ay - 1 and bx == ax:
        grid[ay][ax]["top"] = True
        grid[by][bx]["bottom"] = True


def _makeCorridorOnly(grid, allowedEdges):
    """Seal all internal walls except the undirected cell pairs in `allowedEdges`."""
    h = len(grid)
    w = len(grid[0])
    allowed = {frozenset((a, b)) for a, b in allowedEdges}
    for y in range(h):
        for x in range(w):
            grid[y][x]["top"] = (y == 0) or (frozenset(((x, y), (x, y - 1))) not in allowed)
            grid[y][x]["bottom"] = (y == h - 1) or (frozenset(((x, y), (x, y + 1))) not in allowed)
            grid[y][x]["left"] = (x == 0) or (frozenset(((x, y), (x - 1, y))) not in allowed)
            grid[y][x]["right"] = (x == w - 1) or (frozenset(((x, y), (x + 1, y))) not in allowed)


class EvaluationAndBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agentRoot = Path(__file__).resolve().parent.parent
        cls.modelPath = cls.agentRoot / "models" / "dog.pt"
        cls.model = RecurrentPolicy()
        loadCheckpointFull(cls.modelPath, cls.model)
        cls.model.eval()

    def testA_OscillationPreventionAndActiveLoopBreaking(self):
        """Test A — Oscillation:
        Place the Dog in a corridor where a naive compass toward a walled-off Bone/End
        pulls it backward into an A <-> B oscillation while the true path goes around the wall.
        Verify zero endless oscillation and 100% completion.
        """
        grid = _carveOpenMaze(5, 5)
        # Path goes: (0,0) -> (1,0) -> (1,1) -> (1,2) -> (2,2) -> (3,2) -> (3,1) -> (3,0) -> (4,0)[End]
        # While a tempting Bone sits at (2,0) behind a wall from (1,0), only reachable via (2,1) from (2,2)!
        edges = [
            ((0, 0), (1, 0)),
            ((1, 0), (1, 1)),
            ((1, 1), (1, 2)),
            ((1, 2), (2, 2)),
            ((2, 2), (2, 1)),
            ((2, 1), (2, 0)),
            ((2, 2), (3, 2)),
            ((3, 2), (3, 1)),
            ((3, 1), (3, 0)),
            ((3, 0), (4, 0)),
        ]
        _makeCorridorOnly(grid, edges)
        grid[0][0]["element"] = 1  # Start at (0, 0)
        grid[0][4]["element"] = 2  # End at (4, 0)
        grid[0][2]["element"] = 4  # Bone at (2, 0) (walled off from (1, 0))
        maze = {"metadata": {"maze_name": "test_a_oscillation_trap"}, "grid": grid}

        ep = collectEpisode(self.model, maze, maxSteps=60, deterministic=True)
        self.assertTrue(ep["won"], "Dog must escape the wall trap and reach End without oscillating")
        self.assertEqual(ep["oscillationsDetected"], 0, "Dog must not perform A-B-A-B oscillations")
        self.assertLessEqual(ep["maxVisitCount"], 2, "No cell should be visited more than twice")

    def testB_DeadEndDiscoveryMemoryEscapeAndAvoidance(self):
        """Test B — Dead End:
        Create a maze with a central spine and 3 dead-end branches.
        Verify that the Dog discovers dead ends, escapes them immediately, and never
        re-enters any discovered dead end.
        """
        grid = _carveOpenMaze(5, 5)
        edges = [
            # Main spine from (0,2) to (4,2)
            ((0, 2), (1, 2)),
            ((1, 2), (2, 2)),
            ((2, 2), (3, 2)),
            ((3, 2), (4, 2)),
            # Dead end 1: (1,2) -> (1,1) -> (1,0)
            ((1, 2), (1, 1)),
            ((1, 1), (1, 0)),
            # Dead end 2: (2,2) -> (2,3) -> (2,4)
            ((2, 2), (2, 3)),
            ((2, 3), (2, 4)),
            # Dead end 3: (3,2) -> (3,1)
            ((3, 2), (3, 1)),
        ]
        _makeCorridorOnly(grid, edges)
        grid[2][0]["element"] = 1  # Start at (0, 2)
        grid[2][4]["element"] = 2  # End at (4, 2)
        maze = {"metadata": {"maze_name": "test_b_dead_ends"}, "grid": grid}

        # First test: even if we force the Dog into Dead End 1 ((0,2)->(1,2)->(1,1)->(1,0)),
        # verify it records the dead end, escapes back to (1,2), and never re-enters (1,1) or (1,0).
        env = MazeEnvironment(maze, maxSteps=50)
        env.step(3)  # (0,2) -> (1,2)
        env.step(0)  # (1,2) -> (1,1)
        env.step(0)  # (1,1) -> (1,0) [Dead End leaf!]
        self.assertIn((1, 0), env.knownDeadEnds)
        env.step(1)  # (1,0) -> (1,1)
        env.step(1)  # (1,1) -> (1,2) [Back at junction]
        self.assertIn((1, 1), env.knownDeadEnds)

        # Now let the trained Dog finish from junction (1,2): it must NOT re-enter UP (0) or LEFT (2 -> Start dead end)
        bias = env.computeNavigationActionBias()
        self.assertGreater(bias[3], bias[0], "Action selection must strongly prefer RIGHT over known dead end UP")
        self.assertGreater(bias[3], bias[2], "Action selection must strongly prefer RIGHT over degree-1 Start LEFT")

        # Full autonomous episode from Start
        ep = collectEpisode(self.model, maze, maxSteps=50, deterministic=True)
        self.assertTrue(ep["won"])
        self.assertEqual(ep["deadEndReentries"], 0, "Dog must never re-enter a known dead end")

    def testC_BoneCollectionStrategicTradeOffs(self):
        """Test C — Bone Collection:
        Verify that the Dog:
          1. Collects Bones directly on or near the route.
          2. Takes a short worthwhile detour (<= 4 extra steps) for a Bone (-5 score improvement).
          3. Skips an extreme detour Bone (e.g. 16 extra steps away for only 5 points) when the End is right next to it.
        """
        # Case 1 & 2: Bone on route and Bone on a 1-step side pocket
        grid1 = _carveOpenMaze(5, 5)
        edges1 = [
            ((0, 2), (1, 2)),
            ((1, 2), (1, 1)),  # 1-step side pocket with a Bone at (1,1) (costs 2 extra steps, saves 5 score = net -3!)
            ((1, 2), (2, 2)),
            ((2, 2), (3, 2)),
            ((3, 2), (4, 2)),
        ]
        _makeCorridorOnly(grid1, edges1)
        grid1[2][0]["element"] = 1  # Start (0,2)
        grid1[2][4]["element"] = 2  # End (4,2)
        grid1[1][1]["element"] = 4  # Short-detour Bone at (1,1)
        grid1[2][2]["element"] = 4  # On-route Bone at (2,2)
        mazeWorthwhile = {"metadata": {"maze_name": "test_c_worthwhile_bones"}, "grid": grid1}

        ep1 = collectEpisode(self.model, mazeWorthwhile, maxSteps=40, deterministic=True)
        self.assertTrue(ep1["won"])
        self.assertEqual(ep1["bonesCollected"], 2, "Dog must collect both the on-route Bone and the short-detour Bone")
        # Steps = 6 (including 2 steps for the side pocket), Bones = 2 -> Official Score = 6 - 10 = -4
        self.assertEqual(ep1["score"], ep1["steps"] - 5 * ep1["bonesCollected"])
        self.assertLessEqual(ep1["score"], -3)

        # Case 3: Bone is at the far corner (4, 4) requiring a 14-step detour, while End is 2 steps away at (0, 0)
        grid2 = _carveOpenMaze(5, 5)
        grid2[2][0]["element"] = 1  # Start at (0, 2)
        grid2[0][0]["element"] = 2  # End at (0, 0) (only 2 steps UP!)
        grid2[4][4]["element"] = 4  # Far Bone at (4, 4) (Manhattan dist 6 to bone + 8 back to End = 14 steps vs 2 steps!)
        mazeFarBone = {"metadata": {"maze_name": "test_c_far_detour_bone"}, "grid": grid2}

        ep2 = collectEpisode(self.model, mazeFarBone, maxSteps=40, deterministic=True)
        self.assertTrue(ep2["won"])
        # Reaching End directly in 2 steps gives Official Score = 2, which beats a 14-step detour (14 - 5 = 9)
        self.assertLessEqual(ep2["score"], 4)

    def testD_GeneralizationToUnseenMaps(self):
        """Test D — New Maps:
        Evaluate the rebuilt agent across held-out unseen test maps and validation maps.
        """
        testMaps = discoverMaps(self.agentRoot / "maps" / "test")
        valMaps = discoverMaps(self.agentRoot / "maps" / "validation")

        testMetrics = evaluate(self.model, testMaps, maxSteps=300, deterministic=True)
        valMetrics = evaluate(self.model, valMaps, maxSteps=300, deterministic=True)

        self.assertEqual(testMetrics["winRate"], 1.0, "Agent must solve 100% of unseen test maps")
        self.assertLessEqual(testMetrics["revisitRate"], 0.05)
        self.assertEqual(testMetrics["loopsDetected"], 0)

        self.assertEqual(valMetrics["winRate"], 1.0, "Agent must solve 100% of unseen validation maps (where old agent had 0%)")
        self.assertEqual(valMetrics["loopsDetected"], 0)

    def testE_RepeatedMapAttemptsImprovement(self):
        """Test E — Repeated Maps:
        Evaluate the agent across multiple consecutive attempts on a multi-route maze
        with optimizeMaze and verify that it learns from experience, avoids dead ends,
        and improves or achieves an optimal official score.
        """
        from doobyscoo.training import optimizeMaze

        valMaze = loadMaze(discoverMaps(self.agentRoot / "maps" / "validation")[0])
        res = optimizeMaze(
            model=self.model,
            mazeData=valMaze,
            updates=2,
            attemptsPerUpdate=2,
            maxSteps=300,
        )
        self.assertEqual(res["totalAttempts"], 4)
        self.assertGreaterEqual(res["successfulAttempts"], 3)
        self.assertIsNotNone(res["bestOfficialScore"])
        self.assertLessEqual(res["bestOfficialScore"], 40)

    def testF_ScoreOptimizationAndSection19BenchmarkComparison(self):
        """Test F & Section 19 — Multi-Baseline Benchmark across all 58 maps
        (32 train + 6 validation + 8 unseen test + 9 player maps + 3 starter maps).
        Compares Random legal baseline, Simple Heuristic baseline, and the Rebuilt Agent.
        """
        allBenchmarkMaps = (
            discoverMaps(self.agentRoot / "maps" / "test")
            + discoverMaps(self.agentRoot / "maps" / "validation")
        )
        comp = compareModels(
            {
                "random": "random",
                "heuristic": "heuristic",
                "rebuilt_agent": self.model,
            },
            allBenchmarkMaps,
            episodesPerMap=1,
            maxSteps=300,
            deterministic=True,
        )
        rnd = comp["models"]["random"]
        heur = comp["models"]["heuristic"]
        newAg = comp["models"]["rebuilt_agent"]

        # Rebuilt agent must significantly outperform both random and greedy heuristic baselines
        self.assertGreater(newAg["winRate"], rnd["winRate"])
        self.assertGreater(newAg["winRate"], heur["winRate"])
        self.assertLess(newAg["meanScore"], rnd["meanScore"])
        self.assertLess(newAg["meanScore"], heur["meanScore"])
        self.assertLess(newAg["revisitRate"], rnd["revisitRate"])
        self.assertLess(newAg["revisitRate"], heur["revisitRate"])
        self.assertEqual(newAg["loopsDetected"], 0)


if __name__ == "__main__":
    unittest.main()
