import json
import tempfile
import unittest
from pathlib import Path
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.communication import GameService
from doobyscoo.storage import ExperienceStore, loadCheckpointFull, saveCheckpoint
from doobyscoo.training import RehearsalManager, collectEpisode, continualLearnStep
from tests.test_environment import sampleMaze


class ContinualLearningTests(unittest.TestCase):
    def testPlayedMapCollectionRehearsalExclusionAndResume(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            root = Path(tmpDir)
            trainDir = root / "maps" / "train"
            playedDir = root / "maps" / "played"
            testDir = root / "maps" / "test"
            valDir = root / "maps" / "validation"
            for d in (trainDir, playedDir, testDir, valDir):
                d.mkdir(parents=True)

            for i in range(2):
                m = sampleMaze()
                m["metadata"]["maze_name"] = f"train_{i}"
                (trainDir / f"train_{i}.json").write_text(json.dumps(m), encoding="utf-8")

            testMaze = sampleMaze()
            testMaze["metadata"]["maze_name"] = "secret_test"
            testPath = testDir / "secret_test.json"
            testPath.write_text(json.dumps(testMaze), encoding="utf-8")

            ckptPath = root / "models" / "dog.pt"
            initialModel = RecurrentPolicy()
            saveCheckpoint(ckptPath, initialModel, updates=5, bestRate=0.5, version=1)

            store = ExperienceStore(playedMapsFolder=playedDir, excludedFolders=[testDir, valDir])
            newMaze = sampleMaze()
            newMaze["grid"][0][1]["element"] = 4
            newMaze["metadata"]["maze_name"] = "user_created_1"
            ep = collectEpisode(initialModel, newMaze, maxSteps=15)
            savedPath = store.addEpisode(ep, mazeData=newMaze)
            self.assertIsNotNone(savedPath)
            self.assertTrue(savedPath.exists())
            self.assertEqual(len(store.listPlayedMaps()), 1)

            rejectedTest = store.addEpisode(ep, mazeData=testMaze, sourcePath=testPath, isTestMap=True)
            self.assertIsNone(rejectedTest)

            rehearsal = RehearsalManager(
                trainMapsFolder=trainDir,
                playedMapsFolder=playedDir,
                excludedFolders=[testDir, valDir],
            )
            sampledMaps = rehearsal.sampleRehearsalMaps(count=6)
            for p in sampledMaps:
                self.assertNotEqual(p.resolve(), testPath.resolve())

            result = continualLearnStep(
                checkpoint=ckptPath,
                recentEpisodes=store.popEpisodes(),
                trainMapsFolder=trainDir,
                playedMapsFolder=playedDir,
                validationFolder=valDir,
                updates=2,
                rehearsalCount=2,
                maxSteps=15,
            )
            self.assertEqual(result["updates"], 7)
            self.assertEqual(result["version"], 2)

            service = GameService(
                checkpoint=ckptPath,
                mapsFolder=playedDir,
                trainMapsFolder=trainDir,
                validationFolder=valDir,
            )
            status = service.agentStatus()
            self.assertEqual(status["updates"], 7)
            self.assertEqual(status["modelVersion"], 2)


if __name__ == "__main__":
    unittest.main()

