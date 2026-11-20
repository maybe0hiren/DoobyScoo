from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import tempfile
import threading
import unittest
import uuid
from pathlib import Path
import httpx
import websocket

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_ROOT = PROJECT_ROOT / "doobyscoo-agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from app.core.dependencies import rateLimiter
from app.core.framework import startBackgroundServer
from app.core.websocket_manager import wsManager
from app.main import createApp
from app.rl_verification.action_replay import replayActionTrace
from tests.helpers import findWinningActionSequence

try:
    from doobyscoo.communication.server import createServer as createRlAgentServer
    HAS_LOCAL_RL_AGENT = True
except ImportError:
    createRlAgentServer = None
    HAS_LOCAL_RL_AGENT = False


def _createStandaloneSimulatedAgentServer(deterministicSolve=True):
    sessions = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, formatStr, *args):
            return

        def sendJson(self, status, data):
            encoded = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            rawBody = self.rfile.read(size) if size else b""
            data = json.loads(rawBody.decode("utf-8")) if rawBody else {}
            for forbidden in ("password", "password_hash", "refresh_token"):
                if forbidden in data:
                    return self.sendJson(400, {"error": f"Security violation: {forbidden}"})
            if self.path == "/competitive/solve":
                maze = data["maze"]
                actions = findWinningActionSequence(maze) if deterministicSolve else [0, 1, 0]
                rep = replayActionTrace(maze, actions)
                sid = f"sim_{uuid.uuid4().hex[:10]}"
                sessions[sid] = True
                subPayload = {
                    "match_id": data.get("match_id", ""),
                    "map_id": data.get("map_id", ""),
                    "map_hash": data.get("map_hash", ""),
                    "action_trace": actions,
                    "claimed_score": rep["verified_score"],
                    "claimed_steps": rep["steps"],
                    "claimed_bones_collected": rep["bones_collected"],
                    "claimed_completed": rep["completed"],
                    "final_position": rep["final_position"],
                    "submission_id": f"sub_{uuid.uuid4().hex[:12]}",
                    "model_version": 1,
                }
                return self.sendJson(200, {
                    "success": True,
                    "session_id": sid,
                    "action_trace": actions,
                    "submission_payload": subPayload,
                })
            if self.path == "/competitive/learn":
                return self.sendJson(200, {"success": True, "post_match_learning": True})
            return self.sendJson(404, {"error": "Not found"})

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


def _recvWsEvents(wsConn, timeout=1.5, maxMessages=25):
    wsConn.settimeout(timeout)
    received = []
    for _ in range(maxMessages):
        try:
            raw = wsConn.recv()
            if not raw:
                break
            received.append(json.loads(raw))
        except Exception:
            break
    return received


class EndToEndMultiplayerAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmpDir = tempfile.TemporaryDirectory()
        tmpPath = Path(self.tmpDir.name)
        dbPath = tmpPath / "e2e_multiplayer.db"

        rateLimiter.reset()
        wsManager.reset()
        self.serverApp = createApp(
            databaseUrl=f"sqlite:///{dbPath}",
            fallbackSqlitePath=str(dbPath),
            resetDb=True,
        )
        self.mpServer = startBackgroundServer(self.serverApp, host="127.0.0.1", port=0)

        baseModelPath = AGENT_ROOT / "models" / "dog.pt"
        if HAS_LOCAL_RL_AGENT and baseModelPath.exists():
            p1ModelPath = tmpPath / "p1_dog.pt"
            p2ModelPath = tmpPath / "p2_dog.pt"
            p1ModelPath.write_bytes(baseModelPath.read_bytes())
            p2ModelPath.write_bytes(baseModelPath.read_bytes())

            p1PlayedDir = tmpPath / "p1_played"
            p2PlayedDir = tmpPath / "p2_played"
            p1PlayedDir.mkdir()
            p2PlayedDir.mkdir()

            self.rlServer1 = createRlAgentServer(
                checkpoint=p1ModelPath,
                mapsFolder=p1PlayedDir,
                port=0,
                learnUpdates=1,
                trainMapsFolder=AGENT_ROOT / "maps" / "train",
                validationFolder=AGENT_ROOT / "maps" / "validation",
            )
            self.rlServer2 = createRlAgentServer(
                checkpoint=p2ModelPath,
                mapsFolder=p2PlayedDir,
                port=0,
                learnUpdates=1,
                trainMapsFolder=AGENT_ROOT / "maps" / "train",
                validationFolder=AGENT_ROOT / "maps" / "validation",
            )
        else:
            self.rlServer1 = _createStandaloneSimulatedAgentServer(deterministicSolve=True)
            self.rlServer2 = _createStandaloneSimulatedAgentServer(deterministicSolve=False)

        self.rlPort1 = self.rlServer1.server_address[1]
        self.rlThread1 = threading.Thread(target=self.rlServer1.serve_forever, daemon=True)
        self.rlThread1.start()

        self.rlPort2 = self.rlServer2.server_address[1]
        self.rlThread2 = threading.Thread(target=self.rlServer2.serve_forever, daemon=True)
        self.rlThread2.start()

    def tearDown(self):
        self.rlServer1.shutdown()
        self.rlServer1.server_close()
        self.rlServer2.shutdown()
        self.rlServer2.server_close()
        self.mpServer.stop()
        self.tmpDir.cleanup()

    def testCompleteTwoPlayerOnlineCompetitionAndReconnectionScenario(self):
        baseUrl = self.mpServer.baseUrl
        wsBase = self.mpServer.wsUrl
        rlUrl1 = f"http://127.0.0.1:{self.rlPort1}"
        rlUrl2 = f"http://127.0.0.1:{self.rlPort2}"

        with httpx.Client(timeout=15.0) as http:
            reg1 = http.post(
                f"{baseUrl}/api/v1/auth/register",
                json={
                    "username": "player_one",
                    "email": "p1@doobyscoo.local",
                    "password": "PlayerOnePass123!",
                    "display_name": "Dooby Trainer 1",
                },
            ).json()
            reg2 = http.post(
                f"{baseUrl}/api/v1/auth/register",
                json={
                    "username": "player_two",
                    "email": "p2@doobyscoo.local",
                    "password": "PlayerTwoPass123!",
                    "display_name": "Scoo Trainer 2",
                },
            ).json()
            self.assertTrue(reg1["success"])
            self.assertTrue(reg2["success"])

            login1 = http.post(
                f"{baseUrl}/api/v1/auth/login",
                json={"username": "player_one", "password": "PlayerOnePass123!"},
            ).json()
            login2 = http.post(
                f"{baseUrl}/api/v1/auth/login",
                json={"username": "player_two", "password": "PlayerTwoPass123!"},
            ).json()
            tok1 = login1["access_token"]
            tok2 = login2["access_token"]
            hdr1 = {"Authorization": f"Bearer {tok1}"}
            hdr2 = {"Authorization": f"Bearer {tok2}"}
            p1Id = login1["player"]["player_id"]
            p2Id = login2["player"]["player_id"]

            prof1 = http.get(f"{baseUrl}/api/v1/players/me", headers=hdr1).json()
            prof2 = http.get(f"{baseUrl}/api/v1/players/me", headers=hdr2).json()
            self.assertEqual(prof1["player"]["username"], "player_one")
            self.assertEqual(prof2["player"]["username"], "player_two")

            ws1 = websocket.create_connection(f"{wsBase}?token={tok1}", timeout=5.0)
            ws2 = websocket.create_connection(f"{wsBase}?token={tok2}", timeout=5.0)
            try:
                ack1 = _recvWsEvents(ws1, timeout=0.5, maxMessages=1)
                ack2 = _recvWsEvents(ws2, timeout=0.5, maxMessages=1)
                self.assertEqual(ack1[0]["event_type"], "connection.authenticated")
                self.assertEqual(ack2[0]["event_type"], "connection.authenticated")

                ws1.send(json.dumps({"type": "ping", "client_event_id": "cli_ping_1"}))
                pong1 = _recvWsEvents(ws1, timeout=0.5, maxMessages=1)
                self.assertEqual(pong1[0]["event_type"], "pong")

                ws1.send(json.dumps({"type": "ping", "client_event_id": "cli_ping_1"}))
                dupAck = _recvWsEvents(ws1, timeout=0.5, maxMessages=1)
                self.assertEqual(dupAck[0]["event_type"], "event.duplicate_ignored")

                join1 = http.post(f"{baseUrl}/api/v1/matchmaking/join", headers=hdr1).json()
                self.assertEqual(join1["state"], "SEARCHING")

                join2 = http.post(f"{baseUrl}/api/v1/matchmaking/join", headers=hdr2).json()
                self.assertEqual(join2["state"], "MAP_ASSIGNED")
                matchId = join2["match_id"]
                self.assertIsNotNone(matchId)

                events1 = _recvWsEvents(ws1, timeout=0.6, maxMessages=10)
                events2 = _recvWsEvents(ws2, timeout=0.6, maxMessages=10)
                evTypes1 = {e["event_type"] for e in events1}
                evTypes2 = {e["event_type"] for e in events2}
                self.assertIn("matchmaking.started", evTypes1)
                self.assertIn("matchmaking.opponent_found", evTypes1)
                self.assertIn("match.created", evTypes1)
                self.assertIn("match.map_assigned", evTypes1)
                self.assertIn("match.map_assigned", evTypes2)

                mapResp1 = http.get(f"{baseUrl}/api/v1/matches/{matchId}/map", headers=hdr1).json()
                mapResp2 = http.get(f"{baseUrl}/api/v1/matches/{matchId}/map", headers=hdr2).json()
                self.assertEqual(mapResp1["map_id"], mapResp2["map_id"])
                self.assertEqual(mapResp1["map_hash"], mapResp2["map_hash"])
                self.assertEqual(mapResp1["maze"], mapResp2["maze"])

                battleWs1 = websocket.create_connection(f"{baseUrl.replace('http://', 'ws://')}/api/v1/battles/{matchId}/ws?token={tok1}", timeout=5.0)
                try:
                    battleAck = _recvWsEvents(battleWs1, timeout=0.5, maxMessages=1)
                    self.assertEqual(battleAck[0]["event_type"], "connection.authenticated")
                finally:
                    battleWs1.close()

                reg3 = http.post(
                    f"{baseUrl}/api/v1/auth/register",
                    json={
                        "username": "outsider_three",
                        "email": "p3@doobyscoo.local",
                        "password": "PlayerThreePass123!",
                        "display_name": "Outsider 3",
                    },
                ).json()
                tok3 = reg3["access_token"]
                battleWsOutsider = websocket.create_connection(f"{baseUrl.replace('http://', 'ws://')}/api/v1/battles/{matchId}/ws?token={tok3}", timeout=5.0)
                try:
                    outsiderEvents = _recvWsEvents(battleWsOutsider, timeout=0.5, maxMessages=1)
                    self.assertEqual(outsiderEvents[0]["event_type"], "connection.error")
                    self.assertEqual(outsiderEvents[0]["code"], "forbidden")
                finally:
                    battleWsOutsider.close()

                secCheck = http.post(
                    f"{rlUrl1}/competitive/solve",
                    json={"maze": mapResp1["maze"], "password": "leaked"},
                )
                self.assertEqual(secCheck.status_code, 400)

                solve1 = http.post(
                    f"{rlUrl1}/competitive/solve",
                    json={
                        "maze": mapResp1["maze"],
                        "match_id": matchId,
                        "map_id": mapResp1["map_id"],
                        "map_hash": mapResp1["map_hash"],
                        "deterministic": True,
                    },
                ).json()
                self.assertTrue(solve1["success"])
                self.assertGreater(len(solve1["action_trace"]), 0)

                solve2 = http.post(
                    f"{rlUrl2}/competitive/solve",
                    json={
                        "maze": mapResp2["maze"],
                        "match_id": matchId,
                        "map_id": mapResp2["map_id"],
                        "map_hash": mapResp2["map_hash"],
                        "deterministic": False,
                    },
                ).json()
                self.assertTrue(solve2["success"])
                self.assertGreater(len(solve2["action_trace"]), 0)

                sub1 = http.post(
                    f"{baseUrl}/api/v1/matches/{matchId}/submit",
                    headers=hdr1,
                    json=solve1["submission_payload"],
                ).json()
                self.assertTrue(sub1["success"])
                self.assertEqual(sub1["status"], "AWAITING_RESULTS")

                oppSubEvents2 = _recvWsEvents(ws2, timeout=0.5, maxMessages=5)
                self.assertIn("match.opponent_submitted", {e["event_type"] for e in oppSubEvents2})

                sub2 = http.post(
                    f"{baseUrl}/api/v1/matches/{matchId}/submit",
                    headers=hdr2,
                    json=solve2["submission_payload"],
                ).json()
                self.assertTrue(sub2["success"])
                self.assertEqual(sub2["status"], "COMPLETED")

                postEvents1 = _recvWsEvents(ws1, timeout=0.6, maxMessages=10)
                postEvents2 = _recvWsEvents(ws2, timeout=0.6, maxMessages=10)
                postTypes1 = {e["event_type"] for e in postEvents1}
                postTypes2 = {e["event_type"] for e in postEvents2}
                self.assertIn("match.verification_started", postTypes1)
                self.assertIn("match.completed", postTypes1)
                self.assertIn("player.trophies_updated", postTypes1)
                self.assertIn("player.profile_updated", postTypes1)
                self.assertIn("leaderboard.updated", postTypes1)
                self.assertIn("match.completed", postTypes2)

                updatedProf1 = http.get(f"{baseUrl}/api/v1/players/me", headers=hdr1).json()["player"]
                updatedProf2 = http.get(f"{baseUrl}/api/v1/players/me", headers=hdr2).json()["player"]
                self.assertEqual(updatedProf1["total_matches"], 1)
                self.assertEqual(updatedProf2["total_matches"], 1)
                self.assertGreater(updatedProf1["xp"], 0)
                self.assertGreater(updatedProf2["xp"], 0)

                lbResp = http.get(f"{baseUrl}/api/v1/leaderboards/global").json()
                self.assertGreaterEqual(lbResp["total"], 2)

                hist1 = http.get(f"{baseUrl}/api/v1/players/me/history", headers=hdr1).json()
                self.assertEqual(len(hist1["matches"]), 1)
                self.assertEqual(len(hist1["trophy_history"]), 1)

                learnPost = http.post(
                    f"{rlUrl1}/competitive/learn",
                    json={"session_id": solve1["session_id"], "async": False},
                ).json()
                self.assertTrue(learnPost["success"])
                self.assertTrue(learnPost["post_match_learning"])

                lastSeqBeforeDisconnect = max(
                    (e.get("seq_id", 0) for e in (events2 + oppSubEvents2 + postEvents2) if e.get("seq_id")),
                    default=0,
                )

                http.post(f"{baseUrl}/api/v1/matchmaking/join", headers=hdr1)
                join2Match2 = http.post(f"{baseUrl}/api/v1/matchmaking/join", headers=hdr2).json()
                match2Id = join2Match2["match_id"]
                _recvWsEvents(ws1, timeout=0.4, maxMessages=10)
                preDiscEvents2 = _recvWsEvents(ws2, timeout=0.4, maxMessages=10)
                for ev in preDiscEvents2:
                    if ev.get("seq_id"):
                        lastSeqBeforeDisconnect = max(lastSeqBeforeDisconnect, int(ev["seq_id"]))

                ws2.close()
                ws2 = None

                mapM2 = http.get(f"{baseUrl}/api/v1/matches/{match2Id}/map", headers=hdr1).json()
                s1M2 = http.post(
                    f"{rlUrl1}/competitive/solve",
                    json={
                        "maze": mapM2["maze"],
                        "match_id": match2Id,
                        "map_id": mapM2["map_id"],
                        "map_hash": mapM2["map_hash"],
                        "deterministic": True,
                    },
                ).json()
                s2M2 = http.post(
                    f"{rlUrl2}/competitive/solve",
                    json={
                        "maze": mapM2["maze"],
                        "match_id": match2Id,
                        "map_id": mapM2["map_id"],
                        "map_hash": mapM2["map_hash"],
                        "deterministic": True,
                    },
                ).json()

                http.post(f"{baseUrl}/api/v1/matches/{match2Id}/submit", headers=hdr1, json=s1M2["submission_payload"])
                http.post(f"{baseUrl}/api/v1/matches/{match2Id}/submit", headers=hdr2, json=s2M2["submission_payload"])

                ws2Reconnected = websocket.create_connection(
                    f"{wsBase}?token={tok2}&since_seq={lastSeqBeforeDisconnect}",
                    timeout=5.0,
                )
                try:
                    recoveredEvents = _recvWsEvents(ws2Reconnected, timeout=0.8, maxMessages=15)
                    recoveredTypes = {e["event_type"] for e in recoveredEvents}
                    self.assertIn("connection.authenticated", recoveredTypes)
                    self.assertIn("match.completed", recoveredTypes)
                    self.assertIn("player.trophies_updated", recoveredTypes)
                finally:
                    ws2Reconnected.close()

                resAfterRestart1 = http.get(f"{baseUrl}/api/v1/matches/{match2Id}/result", headers=hdr1).json()
                resAfterRestart2 = http.get(f"{baseUrl}/api/v1/matches/{match2Id}/result", headers=hdr2).json()
                self.assertEqual(resAfterRestart1["status"], "COMPLETED")
                self.assertEqual(resAfterRestart2["status"], "COMPLETED")
                self.assertEqual(resAfterRestart1["match_id"], match2Id)

                finalProf2 = http.get(f"{baseUrl}/api/v1/players/me", headers=hdr2).json()["player"]
                self.assertEqual(finalProf2["total_matches"], 2)
            finally:
                if ws1:
                    ws1.close()
                if ws2:
                    ws2.close()


if __name__ == "__main__":
    unittest.main()

