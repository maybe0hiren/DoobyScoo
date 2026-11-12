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
    collectEpisode,
    train,
    updatePolicy,
)
from tests.test_environment import sampleMaze


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


if __name__ == "__main__":
    unittest.main()
