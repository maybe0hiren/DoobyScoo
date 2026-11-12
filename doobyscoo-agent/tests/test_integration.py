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
        (self.trainDir / "train_0.json").write_text(json.dumps(maze), encoding="utf-8")
        (self.valDir / "val_0.json").write_text(json.dumps(maze), encoding="utf-8")

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


if __name__ == "__main__":
    unittest.main()

