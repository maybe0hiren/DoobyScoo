import json
import tempfile
import unittest
from pathlib import Path
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.communication.session_manager import GameService
from doobyscoo.evaluation import runKnowledgeTransferEvaluation
from doobyscoo.storage import ExperienceStore, saveCheckpoint
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
            testMaze["grid"][0][0]["element"] = 4
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

            # Test map must be rejected both by explicit flag/path AND by grid-hash match
            rejectedTest = store.addEpisode(ep, mazeData=testMaze, sourcePath=testPath, isTestMap=True)
            self.assertIsNone(rejectedTest)
            rejectedByHash = store.addEpisode(ep, mazeData=testMaze)
            self.assertIsNone(rejectedByHash)

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

    def testKnowledgeTransferAndRetentionEvaluation(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            root = Path(tmpDir)
            trainDir = root / "maps" / "train"
            testDir = root / "maps" / "test"
            trainDir.mkdir(parents=True)
            testDir.mkdir(parents=True)

            # Create 4 training maps (2 initial, 2 newly introduced) and 2 distinct unseen test maps
            for idx in range(4):
                m = sampleMaze()
                if idx == 1:
                    m["grid"][1][0]["element"] = 4
                elif idx == 2:
                    m["grid"][0][1]["element"] = 4
                elif idx == 3:
                    m["grid"][2][2]["element"] = 4
                m["metadata"]["maze_name"] = f"tr_{idx}"
                (trainDir / f"tr_{idx}.json").write_text(json.dumps(m), encoding="utf-8")

            for idx in range(2):
                m = sampleMaze()
                m["grid"][0][0]["element"] = 4
                if idx == 1:
                    m["grid"][1][2]["element"] = 4
                m["metadata"]["maze_name"] = f"te_{idx}"
                (testDir / f"te_{idx}.json").write_text(json.dumps(m), encoding="utf-8")

            reportPath = root / "report.json"
            report, _ = runKnowledgeTransferEvaluation(
                trainMapsFolder=trainDir,
                testMapsFolder=testDir,
                phase1Updates=4,
                phase2Updates=4,
                config={"training": {"episodesPerUpdate": 4, "maxSteps": 25}},
                seed=11,
                reportPath=reportPath,
            )
            self.assertTrue(reportPath.exists())
            self.assertTrue(report["mapGroups"]["testMapsIsolated"])
            self.assertFalse(report["verdict"]["catastrophicForgettingDetected"])
            self.assertGreaterEqual(report["verdict"]["retentionWinRate"], 0.5)
            self.assertGreaterEqual(report["verdict"]["unseenTestWinRate"], 0.5)


if __name__ == "__main__":
    unittest.main()
