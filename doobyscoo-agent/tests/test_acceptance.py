import json
import re
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from doobyscoo.agent import ARCHITECTURE_ID, RecurrentPolicy
from doobyscoo.communication.server import createServer
from doobyscoo.environment import OBSERVATION_SIZE, loadMaze
from doobyscoo.evaluation import compareModels, evaluate
from doobyscoo.storage import getCheckpointMetadata, loadCheckpointFull
from doobyscoo.training import discoverMaps


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.agentRoot = Path(__file__).resolve().parent.parent
        self.godotRoot = self.agentRoot.parent / "dooby-scoo-godot"
        self.modelPath = self.agentRoot / "models" / "dog.pt"

    def testA_InitialTrainedCheckpointExistsAndValid(self):
        self.assertTrue(self.modelPath.exists(), "Trained model models/dog.pt must exist")
        meta = getCheckpointMetadata(self.modelPath)
        self.assertTrue(meta["exists"])
        self.assertEqual(meta["architecture"], ARCHITECTURE_ID)
        self.assertIsNotNone(meta["modelId"])
        self.assertTrue(meta["freshInit"]["startedFromScratch"])
        self.assertGreaterEqual(meta["updates"], 20)
        self.assertGreaterEqual(meta["version"], 1)
        trainMaps = discoverMaps(self.agentRoot / "maps" / "train")
        self.assertGreaterEqual(len(trainMaps), 30)

    def testB_UnseenMapsEvaluationAndBaselineComparison(self):
        testMaps = discoverMaps(self.agentRoot / "maps" / "test")
        self.assertEqual(len(testMaps), 8)
        comparison = compareModels(
            {"untrained": "untrained", "trained": self.modelPath},
            testMaps,
            episodesPerMap=1,
            maxSteps=300,
        )
        trainedMetrics = comparison["models"]["trained"]
        self.assertGreaterEqual(trainedMetrics["winRate"], 0.85)
        self.assertGreaterEqual(trainedMetrics["boneCollectionRate"], 0.35)
        self.assertLessEqual(trainedMetrics["revisitRate"], 0.20)
        self.assertEqual(len(trainedMetrics["resultsPerMap"]), 8)
        self.assertTrue(comparison["improvements"]["untrained_to_trained"]["improved"])

    def testC_D_E_F_GodotGameplayContinualLearningPersistenceAndRetention(self):
        with tempfile.TemporaryDirectory() as tmpDir:
            tmpRoot = Path(tmpDir)
            playedDir = tmpRoot / "played"
            playedDir.mkdir()
            tempModelPath = tmpRoot / "dog.pt"
            tempModelPath.write_bytes(self.modelPath.read_bytes())

            metaBefore = getCheckpointMetadata(tempModelPath)
            updatesBefore = metaBefore["updates"]
            versionBefore = metaBefore["version"]

            server1 = createServer(
                checkpoint=tempModelPath,
                mapsFolder=playedDir,
                port=0,
                learnUpdates=2,
                trainMapsFolder=self.agentRoot / "maps" / "train",
                validationFolder=self.agentRoot / "maps" / "validation",
            )
            port1 = server1.server_address[1]
            thread1 = threading.Thread(target=server1.serve_forever, daemon=True)
            thread1.start()
            baseUrl1 = f"http://127.0.0.1:{port1}"

            def postJson(url, endpoint, payload):
                req = urllib.request.Request(
                    url + endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            def getJson(url, endpoint):
                with urllib.request.urlopen(url + endpoint, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))

            try:
                godotStarterPath = self.godotRoot / "assets" / "starter_maps" / "Starter_Meadow_Run.json"
                godotMaze = loadMaze(godotStarterPath)
                startResp = postJson(
                    baseUrl1,
                    "/episode/start",
                    {"maze": godotMaze, "mode": "training", "deterministic": True, "collect_experience": True},
                )
                self.assertTrue(startResp["success"])
                self.assertEqual(len(startResp["observation"]), OBSERVATION_SIZE)
                sid = startResp["session_id"]

                done = False
                won = False
                steps = 0
                for _ in range(300):
                    stepResp = postJson(
                        baseUrl1,
                        "/episode/step",
                        {"session_id": sid, "deterministic": True, "auto_end": False},
                    )
                    self.assertTrue(stepResp["success"])
                    steps = stepResp["steps"]
                    done = stepResp["done"]
                    won = stepResp["won"]
                    if done:
                        break

                self.assertTrue(done, "Godot starter maze episode should finish within 300 steps")
                self.assertTrue(won, "Dog should solve the Godot starter maze")
                self.assertGreater(steps, 0)

                endResp = postJson(baseUrl1, "/episode/end", {"session_id": sid, "learn": False})
                self.assertTrue(endResp["episodeCompleted"])
                self.assertEqual(len(list(playedDir.glob("*.json"))), 1)

                learnResp = postJson(baseUrl1, "/learn", {"async": False})
                self.assertTrue(learnResp["completed"])
            finally:
                server1.shutdown()
                server1.server_close()

            server2 = createServer(
                checkpoint=tempModelPath,
                mapsFolder=playedDir,
                port=0,
                learnUpdates=2,
                trainMapsFolder=self.agentRoot / "maps" / "train",
                validationFolder=self.agentRoot / "maps" / "validation",
            )
            port2 = server2.server_address[1]
            thread2 = threading.Thread(target=server2.serve_forever, daemon=True)
            thread2.start()
            baseUrl2 = f"http://127.0.0.1:{port2}"

            try:
                statusAfterRestart = getJson(baseUrl2, "/agent/status")
                self.assertEqual(statusAfterRestart["updates"], updatesBefore + 2)
                self.assertEqual(statusAfterRestart["modelVersion"], versionBefore + 1)
                self.assertEqual(statusAfterRestart["playedMapsCount"], 1)
            finally:
                server2.shutdown()
                server2.server_close()

            updatedModel = RecurrentPolicy()
            loadCheckpointFull(tempModelPath, updatedModel)
            trainEval = evaluate(updatedModel, discoverMaps(self.agentRoot / "maps" / "train")[:10], maxSteps=300)
            testEval = evaluate(updatedModel, discoverMaps(self.agentRoot / "maps" / "test"), maxSteps=300)
            self.assertGreaterEqual(trainEval["winRate"], 0.80)
            self.assertGreaterEqual(testEval["winRate"], 0.85)

    def testGodotScenesAndScriptsIntegrity(self):
        requiredScenes = [
            "scenes/landing_page.tscn",
            "scenes/map_editor_page.tscn",
            "scenes/my_maps.tscn",
            "scenes/mazeRow.tscn",
            "scenes/gameplay_page.tscn",
            "scenes/multiplayer_page.tscn",
            "scenes/MazeSession.tscn",
        ]
        for relScene in requiredScenes:
            scenePath = self.godotRoot / relScene
            self.assertTrue(scenePath.exists(), f"Missing Godot scene: {relScene}")
            content = scenePath.read_text(encoding="utf-8")
            for match in re.finditer(r'path="res://([^"]+)"', content):
                resTarget = self.godotRoot / match.group(1)
                self.assertTrue(resTarget.exists(), f"Broken resource path res://{match.group(1)} in {relScene}")


if __name__ == "__main__":
    unittest.main()
