import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from doobyscoo.agent import RecurrentPolicy
from doobyscoo.communication.server import createServer
from doobyscoo.environment import OBSERVATION_SIZE
from doobyscoo.storage import saveCheckpoint
from tests.test_environment import sampleMaze


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmpDir = tempfile.TemporaryDirectory()
        root = Path(self.tmpDir.name)
        self.trainDir = root / "maps" / "train"
        self.playedDir = root / "maps" / "played"
        self.valDir = root / "maps" / "validation"
        for d in (self.trainDir, self.playedDir, self.valDir):
            d.mkdir(parents=True)

        maze = sampleMaze()
        valMaze = sampleMaze()
        valMaze["grid"][0][0]["element"] = 4
        (self.trainDir / "train_0.json").write_text(json.dumps(maze), encoding="utf-8")
        (self.valDir / "val_0.json").write_text(json.dumps(valMaze), encoding="utf-8")

        self.ckptPath = root / "models" / "dog.pt"
        saveCheckpoint(self.ckptPath, RecurrentPolicy(), updates=1, bestRate=0.5, version=1)

        self.server = createServer(
            checkpoint=self.ckptPath,
            mapsFolder=self.playedDir,
            port=0,
            learnUpdates=1,
            trainMapsFolder=self.trainDir,
            validationFolder=self.valDir,
        )
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.baseUrl = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmpDir.cleanup()

    def _get(self, path):
        with urllib.request.urlopen(self.baseUrl + path, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post(self, path, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.baseUrl + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def testServerConnectionAndEpisodeLifecycle(self):
        health = self._get("/health")
        self.assertEqual(health["status"], "ok")

        startResp = self._post("/episode/start", {"maze": sampleMaze(), "mode": "training"})
        self.assertTrue(startResp["success"])
        sessionId = startResp["session_id"]
        self.assertEqual(len(startResp["observation"]), OBSERVATION_SIZE)

        actionResp = self._post("/agent/action", {"session_id": sessionId, "observation": startResp["observation"]})
        self.assertTrue(actionResp["success"])
        self.assertIn(actionResp["action"], range(4))
        self.assertIn(actionResp["action_name"], ("up", "down", "left", "right"))

        stepResp = self._post("/episode/step", {"session_id": sessionId, "action": 3})
        self.assertTrue(stepResp["success"])
        self.assertTrue(stepResp["bone"])
        self.assertEqual(stepResp["steps"], 1)

        endResp = self._post("/episode/end", {"session_id": sessionId, "learn": False})
        self.assertTrue(endResp["success"])
        self.assertTrue(endResp["episodeCompleted"])

    def testActiveInferenceNotCorruptedDuringLearning(self):
        startResp = self._post("/map", sampleMaze())
        sessionId = startResp["session_id"]
        learnResp = self._post("/learn", {"async": False})
        self.assertTrue(learnResp["completed"])

        stepResp = self._post("/step", {"session_id": sessionId, "deterministic": True})
        self.assertIn(stepResp["action"], range(4))
        status = self._get("/agent/status")
        self.assertGreaterEqual(status["updates"], 2)

    def testUserControlledPolicyUpdatesNeverAutoTriggerAfterOneOrFiveAttempts(self):
        status0 = self._get("/agent/status")
        initialUpdates = status0["updates"]
        initialVersion = status0["modelVersion"]
        self.assertEqual(status0["pendingEpisodes"], 0)
        self.assertEqual(status0["pendingSamples"], 0)

        # Complete 1 full attempt (Right -> Up -> Up solves sampleMaze)
        start1 = self._post("/episode/start", {"maze": sampleMaze(), "mode": "training", "collect_experience": True})
        sid1 = start1["session_id"]
        self.assertEqual(start1["attempt_number"], 1)
        self._post("/episode/step", {"session_id": sid1, "action": 3})
        self._post("/episode/step", {"session_id": sid1, "action": 0})
        done1 = self._post("/episode/step", {"session_id": sid1, "action": 0})
        self.assertTrue(done1["done"])
        self.assertTrue(done1["won"])
        self.assertFalse(done1["learningStarted"])

        statusAfter1 = self._get("/agent/status")
        # Completing 1 episode must NOT update the policy automatically
        self.assertEqual(statusAfter1["updates"], initialUpdates)
        self.assertEqual(statusAfter1["modelVersion"], initialVersion)
        self.assertEqual(statusAfter1["pendingEpisodes"], 1)
        self.assertEqual(statusAfter1["pendingSamples"], 3)

        # Complete 4 more attempts (total 5 attempts on the same maze)
        for expectedAttempt in range(2, 6):
            st = self._post("/episode/start", {"maze": sampleMaze(), "mode": "training", "collect_experience": True})
            self.assertEqual(st["attempt_number"], expectedAttempt)
            self.assertEqual(st["model_version"], initialVersion)
            sid = st["session_id"]
            self._post("/episode/step", {"session_id": sid, "action": 3})
            self._post("/episode/step", {"session_id": sid, "action": 0})
            fin = self._post("/episode/step", {"session_id": sid, "action": 0})
            self.assertTrue(fin["done"])
            self.assertFalse(fin["learningStarted"])

        statusAfter5 = self._get("/agent/status")
        # Completing 5 attempts must NOT automatically call the PPO optimizer or change policy weights
        self.assertEqual(statusAfter5["updates"], initialUpdates)
        self.assertEqual(statusAfter5["modelVersion"], initialVersion)
        self.assertEqual(statusAfter5["pendingEpisodes"], 5)
        self.assertEqual(statusAfter5["pendingSamples"], 15)

        # Now user explicitly presses "Update RL Policy" (/learn)
        learnResp = self._post("/learn", {"async": False})
        self.assertTrue(learnResp["completed"])
        self.assertGreater(learnResp["updates"], initialUpdates)
        self.assertGreater(learnResp["modelVersion"], initialVersion)
        self.assertEqual(learnResp["pendingEpisodes"], 0)
        self.assertEqual(learnResp["pendingSamples"], 0)

        # Subsequent attempt uses the newly updated policy version
        start6 = self._post("/episode/start", {"maze": sampleMaze(), "mode": "training", "collect_experience": True})
        self.assertEqual(start6["attempt_number"], 6)
        self.assertEqual(start6["model_version"], learnResp["modelVersion"])
        self.assertGreater(start6["model_version"], initialVersion)


if __name__ == "__main__":
    unittest.main()

