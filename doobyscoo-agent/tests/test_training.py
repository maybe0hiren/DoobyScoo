import json
import tempfile
import unittest
from pathlib import Path
import torch
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.storage import (
    IncompatibleCheckpointError,
    bestCheckpointPath,
    initializeFreshModel,
    loadCheckpointFull,
    metricsLogPath,
)
from doobyscoo.training import (
    BalancedMapSampler,
    LearningProgressReporter,
    MazeOptimizationTracker,
    SIMPLE_TITLES,
    collectEpisode,
    measureRouteDiversity,
    optimizeMaze,
    train,
    trajectorySimilarity,
    updatePolicy,
)
from tests.test_environment import makeGrid, sampleMaze


class TrainingTests(unittest.TestCase):
    def testOnePpoUpdateChangesParameters(self):
        model = RecurrentPolicy()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        beforeParams = [p.detach().clone() for p in model.parameters()]
        episodes = [collectEpisode(model, sampleMaze(), maxSteps=15) for _ in range(3)]
        metrics = updatePolicy(model, optimizer, episodes, epochs=2)
        self.assertTrue(float("-inf") < float(metrics) < float("inf"))
        self.assertFalse(torch.isnan(torch.tensor(float(metrics))))
        afterParams = list(model.parameters())
        changed = any(not torch.allclose(b, a) for b, a in zip(beforeParams, afterParams))
        self.assertTrue(changed)

    def testFreshModelInitializationAndOldCheckpointRejection(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            ckptPath = Path(tmpDir) / "models" / "dog.pt"
            ckptPath.parent.mkdir(parents=True, exist_ok=True)
            # Save a fake legacy checkpoint with wrong architecture / shapes
            torch.save(
                {
                    "model": {"actor.weight": torch.zeros(4, 128)},
                    "updates": 99,
                    "version": 9,
                    "config": {"architecture": "legacy-v1", "observationSize": 8},
                },
                ckptPath,
            )
            with self.assertRaises(IncompatibleCheckpointError):
                loadCheckpointFull(ckptPath, RecurrentPolicy())

            # Fresh initialization must overwrite legacy checkpoint and create a clean modelId
            freshModel = RecurrentPolicy()
            modelId, freshMeta = initializeFreshModel(ckptPath, freshModel, seed=123, reason="unit_test_fresh")
            loadedMeta = loadCheckpointFull(ckptPath, RecurrentPolicy())
            self.assertTrue(loadedMeta["loaded"])
            self.assertEqual(loadedMeta["updates"], 0)
            self.assertEqual(loadedMeta["modelId"], modelId)
            self.assertEqual(loadedMeta["freshInit"]["seed"], 123)

    def testCheckpointSaveLoadAndResume(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            mapDir = Path(tmpDir) / "maps"
            mapDir.mkdir()
            for idx in range(3):
                maze = sampleMaze()
                maze["metadata"]["maze_name"] = f"map_{idx}"
                (mapDir / f"map_{idx}.json").write_text(json.dumps(maze), encoding="utf-8")

            ckptPath = Path(tmpDir) / "models" / "dog.pt"
            train(
                mapsFolder=mapDir,
                checkpoint=ckptPath,
                updates=2,
                episodesPerUpdate=2,
                maxSteps=15,
                resume=False,
            )
            self.assertTrue(ckptPath.exists())
            self.assertTrue(bestCheckpointPath(ckptPath).exists())
            self.assertTrue(metricsLogPath(ckptPath).exists())
            meta1 = loadCheckpointFull(ckptPath, RecurrentPolicy())
            self.assertEqual(meta1["updates"], 2)
            self.assertEqual(meta1["totalEpisodes"], 4)
            self.assertTrue(meta1["freshInit"]["startedFromScratch"])

            train(
                mapsFolder=mapDir,
                checkpoint=ckptPath,
                updates=2,
                episodesPerUpdate=2,
                maxSteps=15,
                resume=True,
            )
            meta2 = loadCheckpointFull(ckptPath, RecurrentPolicy())
            self.assertEqual(meta2["updates"], 4)
            self.assertEqual(meta2["totalEpisodes"], 8)
            self.assertEqual(meta2["modelId"], meta1["modelId"])
            self.assertGreaterEqual(len(meta2["mapHistory"]), 1)

    def testBalancedMapSamplerSamplesMultipleMaps(self):
        paths = [Path(f"map_{i}.json") for i in range(6)]
        sampler = BalancedMapSampler(paths)
        sampled = sampler.sample(count=24)
        self.assertEqual(len(sampled), 24)
        self.assertEqual(len(set(sampled)), 6)
        sampler.recordOutcome(paths[0], won=False, score=100)
        sampler.recordOutcome(paths[1], won=True, score=-10)
        self.assertLess(sampler.winRates[paths[0]], sampler.winRates[paths[1]])

    def testFailedScoreLimitTrajectoryIncludedInPpoUpdate(self):
        maze = sampleMaze()
        # Seal Start (0, 2) on all sides so the agent cannot reach End and exceeds score limit 10
        maze["grid"][2][0]["top"] = True
        maze["grid"][1][0]["bottom"] = True
        maze["grid"][2][0]["right"] = True
        maze["grid"][2][1]["left"] = True
        model = RecurrentPolicy()
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        beforeParams = [p.detach().clone() for p in model.parameters()]

        epFailed = collectEpisode(
            model,
            maze,
            maxSteps=50,
            rewardConfig={"maxScoreLimit": 10.0},
            enforceScoreLimit=True,
        )
        self.assertFalse(epFailed["won"])
        self.assertTrue(epFailed["failed"])
        self.assertTrue(epFailed["scoreLimitExceeded"])
        self.assertGreater(epFailed["trainingScore"], 10.0)
        self.assertEqual(len(epFailed["observations"]), epFailed["steps"])
        self.assertEqual(len(epFailed["actions"]), epFailed["steps"])
        self.assertEqual(len(epFailed["positionHistory"]), epFailed["steps"] + 1)
        self.assertGreaterEqual(len(epFailed["visitedCells"]), 1)

        metrics = updatePolicy(model, optimizer, [epFailed], epochs=2)
        self.assertFalse(torch.isnan(torch.tensor(float(metrics))))
        afterParams = list(model.parameters())
        self.assertTrue(any(not torch.allclose(b, a) for b, a in zip(beforeParams, afterParams)))

    def testMazeOptimizationTrackerAndRepeatedAttempts(self):
        tracker = MazeOptimizationTracker()
        # Attempt 1: solves maze with score 15, steps 25, 1 bone
        out1 = tracker.recordAttempt(
            "maze_alpha",
            {
                "won": True,
                "trainingScore": 15,
                "officialScore": 20,
                "length": 25,
                "bonesCollected": 1,
                "revisits": 6,
                "actions": [0, 0, 3, 3, 0],
                "positionHistory": [[0, 2], [0, 1], [1, 1], [2, 1], [2, 0]],
            },
        )
        self.assertTrue(out1["improvedScore"])
        self.assertTrue(out1["firstSolve"])
        self.assertEqual(tracker.getMazeSummary("maze_alpha")["bestScore"], 15)
        self.assertEqual(tracker.getMazeSummary("maze_alpha")["bestSteps"], 25)

        # Attempt 2: worse score (22) and more steps (32) must NOT overwrite bestScore or bestTrajectory
        out2 = tracker.recordAttempt(
            "maze_alpha",
            {
                "won": True,
                "trainingScore": 22,
                "officialScore": 27,
                "length": 32,
                "bonesCollected": 1,
                "revisits": 8,
                "actions": [3, 3, 0, 0, 1, 0],
                "positionHistory": [[0, 2], [1, 2], [2, 2], [2, 1], [2, 0]],
            },
        )
        self.assertFalse(out2["improvedScore"])
        self.assertFalse(out2["isBetterRoute"])
        self.assertEqual(tracker.getMazeSummary("maze_alpha")["bestScore"], 15)
        self.assertEqual(tracker.getMazeSummary("maze_alpha")["bestSteps"], 25)
        self.assertEqual(tracker.getMazeSummary("maze_alpha")["bestTrajectory"], [0, 0, 3, 3, 0])

        # Attempt 3: better score (-5) with 2 bones and fewer steps (15) updates bestScore and bestTrajectory
        out3 = tracker.recordAttempt(
            "maze_alpha",
            {
                "won": True,
                "trainingScore": -5,
                "officialScore": 5,
                "length": 15,
                "bonesCollected": 2,
                "revisits": 1,
                "actions": [3, 0, 0, 3],
                "positionHistory": [[0, 2], [1, 2], [1, 1], [2, 0]],
            },
        )
        self.assertTrue(out3["improvedScore"])
        self.assertTrue(out3["isBetterRoute"])
        self.assertTrue(out3["improvedBones"])
        self.assertTrue(out3["reducedRevisits"])
        rec = tracker.getMazeSummary("maze_alpha")
        self.assertEqual(rec["bestScore"], -5)
        self.assertEqual(rec["bestSteps"], 15)
        self.assertEqual(rec["bonesCollected"], 2)
        self.assertEqual(rec["distinctSuccessfulTrajectories"], 3)
        self.assertEqual(rec["scoreImprovement"], 20)

        # Route diversity and trajectory similarity checks
        div = measureRouteDiversity([[0, 0, 3, 3], [3, 3, 0, 0], [0, 0, 3, 3]])
        self.assertEqual(div["distinctTrajectories"], 2)
        self.assertEqual(div["duplicateTrajectories"], 1)
        self.assertLess(trajectorySimilarity([0, 0, 3, 3], [3, 3, 0, 0]), 1.0)

        # Verify optimizeMaze runs repeated attempts and stops at configured limits
        grid = makeGrid(3, 3)
        grid[2][0]["element"] = 1
        grid[0][2]["element"] = 2
        grid[1][0]["element"] = 4
        grid[2][1]["element"] = 4
        openMaze = {"metadata": {"maze_name": "open_3x3"}, "grid": grid}
        torch.manual_seed(7)
        optModel = RecurrentPolicy()
        optRes = optimizeMaze(
            model=optModel,
            mazeData=openMaze,
            updates=2,
            attemptsPerUpdate=3,
            maxSteps=20,
        )
        self.assertEqual(optRes["totalAttempts"], 6)
        self.assertGreaterEqual(optRes["distinctSuccessfulTrajectories"], 1)
        self.assertGreaterEqual(optRes["routeDiversity"]["distinctTrajectories"], 2)

    def testLearningProgressReporterTitlesAndDeduplication(self):
        reporter = LearningProgressReporter()
        mStart = reporter.recordTrainingStarted(numMaps=30, maxScoreLimit=100)
        self.assertEqual(mStart["title"], "Training Started")
        self.assertIn(mStart["title"], SIMPLE_TITLES)

        # Failed score-limit attempt -> "Learning from Failure"
        failOutcome = {
            "mapName": "Starter_Meadow_Run",
            "attemptNumber": 1,
            "failed": True,
            "scoreLimitExceeded": True,
            "trainingScore": 102,
            "steps": 102,
            "bonesCollected": 0,
        }
        msgsFail = reporter.recordAttemptOutcome(failOutcome)
        self.assertEqual([m["title"] for m in msgsFail], ["Learning from Failure"])

        # Repeated identical failure message is suppressed
        msgsFailDup = reporter.recordAttemptOutcome(failOutcome)
        self.assertEqual(msgsFailDup, [])

        # Ordinary non-improving successful attempt produces NO false learning claims
        msgsOrdinary = reporter.recordAttemptOutcome(
            {
                "mapName": "Starter_Meadow_Run",
                "attemptNumber": 2,
                "won": True,
                "failed": False,
                "trainingScore": 15,
                "steps": 15,
                "bonesCollected": 0,
                "improvedScore": False,
                "firstSolve": False,
                "isBetterRoute": False,
                "improvedBones": False,
                "reducedRevisits": False,
            }
        )
        self.assertEqual(msgsOrdinary, [])

        # Genuine improvements emit exact simple titles
        msgsImproved = reporter.recordAttemptOutcome(
            {
                "mapName": "Starter_Meadow_Run",
                "attemptNumber": 3,
                "won": True,
                "failed": False,
                "trainingScore": -12,
                "steps": 18,
                "bonesCollected": 3,
                "improvedScore": True,
                "previousBestScore": 10,
                "newBestScore": -12,
                "isBetterRoute": True,
                "improvedBones": True,
                "previousMaxBones": 1,
                "newMaxBones": 3,
                "reducedRevisits": True,
                "previousBestRevisits": 5,
                "newBestRevisits": 1,
            }
        )
        titles = [m["title"] for m in msgsImproved]
        self.assertIn("New Best Score", titles)
        self.assertIn("Better Route Found", titles)
        self.assertIn("Bone Collection Improved", titles)
        self.assertIn("Reduced Revisits", titles)

        # Navigation & mistake-avoidance titles
        msgsExplore = reporter.recordAttemptOutcome(
            {
                "mapName": "Starter_Meadow_Run",
                "attemptNumber": 4,
                "won": False,
                "failed": False,
                "trainingScore": 35,
                "steps": 25,
                "bonesCollected": 1,
                "newAreasExplored": 12,
                "exploredNewArea": True,
                "deadEndsEncountered": 2,
                "avoidedPreviousMistakes": 1,
            }
        )
        navTitles = [m["title"] for m in msgsExplore]
        self.assertIn("Exploring New Area", navTitles)
        self.assertIn("Dead End Found", navTitles)
        self.assertIn("Avoided Previous Mistake", navTitles)

        # Policy update message emitted only when measurable improvement occurs over baseline
        reporter.recordPolicyUpdate(
            1,
            [{"won": True, "failed": False}],
            evalMetrics={"winRate": 0.5, "meanTrainingScore": 10.0, "meanScore": 10.0, "bonesCollected": 1.0, "revisitRate": 0.25},
        )
        msgsNoChange = reporter.recordPolicyUpdate(
            2,
            [{"won": True, "failed": False}],
            evalMetrics={"winRate": 0.5, "meanTrainingScore": 10.0, "meanScore": 10.0, "bonesCollected": 1.0, "revisitRate": 0.25},
        )
        self.assertEqual(msgsNoChange, [])

        msgsPolImproved = reporter.recordPolicyUpdate(
            3,
            [{"won": True, "failed": False}],
            evalMetrics={"winRate": 0.75, "meanTrainingScore": -5.0, "meanScore": -5.0, "bonesCollected": 2.5, "revisitRate": 0.08},
        )
        self.assertEqual([m["title"] for m in msgsPolImproved], ["Update RL Policy"])


if __name__ == "__main__":
    unittest.main()
