import tempfile
import unittest
from pathlib import Path
import torch
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.training import (
    BalancedMapSampler,
    collectEpisode,
    loadCheckpointFull,
    saveCheckpoint,
    train,
    updatePolicy,
)
from tests.test_environment import sampleMaze
import json


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
            meta1 = loadCheckpointFull(ckptPath, RecurrentPolicy())
            self.assertEqual(meta1["updates"], 2)
            self.assertEqual(meta1["totalEpisodes"], 4)

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
            self.assertTrue(ckptPath.with_suffix(".pt.bak").exists())

    def testBalancedMapSamplerSamplesMultipleMaps(self):
        paths = [Path(f"map_{i}.json") for i in range(5)]
        sampler = BalancedMapSampler(paths)
        sampled = sampler.sample(count=25)
        self.assertGreaterEqual(len(set(sampled)), 3)


if __name__ == "__main__":
    unittest.main()

