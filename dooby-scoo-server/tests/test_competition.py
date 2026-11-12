import unittest
from app.database.session import getDb
from app.rl_verification.action_replay import replayActionTrace
from app.services.match_service import createMatchForPlayers
from tests.helpers import createIsolatedTestApp, findWinningActionSequence


class CompetitionAndVerificationTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.tmpDir = createIsolatedTestApp()

    def tearDown(self):
        self.tmpDir.cleanup()

    def _register(self, username):
        _, res = self.client.post(
            "/api/v1/auth/register",
            {
                "username": username,
                "email": f"{username}@example.com",
                "password": "Password123!",
                "display_name": username,
            },
        )
        return res["player"]["player_id"], res["access_token"]

    def testIdenticalMapAssignmentReplayAndVerification(self):
        uid1, tok1 = self._register("comp_p1")
        uid2, tok2 = self._register("comp_p2")
        uid3, tok3 = self._register("outsider_p3")

        self.client.post("/api/v1/matchmaking/join", token=tok1)
        _, join2 = self.client.post("/api/v1/matchmaking/join", token=tok2)
        matchId = join2["match_id"]

        status1, map1 = self.client.get(f"/api/v1/matches/{matchId}/map", token=tok1)
        status2, map2 = self.client.get(f"/api/v1/matches/{matchId}/map", token=tok2)
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        self.assertEqual(map1["map_id"], map2["map_id"])
        self.assertEqual(map1["map_hash"], map2["map_hash"])
        self.assertEqual(map1["maze"], map2["maze"])

        statusOut, _ = self.client.get(f"/api/v1/matches/{matchId}/map", token=tok3)
        self.assertEqual(statusOut, 403)

        winActions = findWinningActionSequence(map1["maze"])
        replay1 = replayActionTrace(map1["maze"], winActions)
        self.assertTrue(replay1["valid"])
        self.assertTrue(replay1["completed"])

        statusBadScore, badScoreResp = self.client.post(
            f"/api/v1/matches/{matchId}/submit",
            {
                "map_id": map1["map_id"],
                "map_hash": map1["map_hash"],
                "action_trace": winActions,
                "claimed_score": replay1["verified_score"] - 50,
                "claimed_steps": replay1["steps"],
                "claimed_bones_collected": replay1["bones_collected"],
                "claimed_completed": replay1["completed"],
                "final_position": replay1["final_position"],
                "submission_id": "sub_bad_score",
            },
            token=tok1,
        )
        self.assertEqual(statusBadScore, 400)
        self.assertEqual(badScoreResp["code"], "score_mismatch")

        statusBadTrace, badTraceResp = self.client.post(
            f"/api/v1/matches/{matchId}/submit",
            {
                "map_id": map1["map_id"],
                "map_hash": map1["map_hash"],
                "action_trace": [99],
                "claimed_score": 1,
                "claimed_steps": 1,
                "claimed_bones_collected": 0,
                "claimed_completed": False,
                "final_position": [0, 0],
                "submission_id": "sub_bad_trace",
            },
            token=tok1,
        )
        self.assertEqual(statusBadTrace, 400)
        self.assertEqual(badTraceResp["code"], "invalid_action_trace")

        subPayload1 = {
            "map_id": map1["map_id"],
            "map_hash": map1["map_hash"],
            "action_trace": winActions,
            "claimed_score": replay1["verified_score"],
            "claimed_steps": replay1["steps"],
            "claimed_bones_collected": replay1["bones_collected"],
            "claimed_completed": replay1["completed"],
            "final_position": replay1["final_position"],
            "submission_id": "sub_valid_p1",
        }
        statusSub1, subResp1 = self.client.post(f"/api/v1/matches/{matchId}/submit", subPayload1, token=tok1)
        self.assertEqual(statusSub1, 200)
        self.assertEqual(subResp1["status"], "AWAITING_RESULTS")

        statusIdemp, idempResp = self.client.post(f"/api/v1/matches/{matchId}/submit", subPayload1, token=tok1)
        self.assertEqual(statusIdemp, 200)
        self.assertTrue(idempResp.get("idempotent"))

        subPayload1Dup = dict(subPayload1)
        subPayload1Dup["submission_id"] = "sub_different_id_p1"
        statusDup, dupResp = self.client.post(f"/api/v1/matches/{matchId}/submit", subPayload1Dup, token=tok1)
        self.assertEqual(statusDup, 409)
        self.assertEqual(dupResp["code"], "duplicate_submission")

        failActions = [0, 0, 0]
        replay2 = replayActionTrace(map2["maze"], failActions)
        subPayload2 = {
            "map_id": map2["map_id"],
            "map_hash": map2["map_hash"],
            "action_trace": failActions,
            "claimed_score": replay2["verified_score"],
            "claimed_steps": replay2["steps"],
            "claimed_bones_collected": replay2["bones_collected"],
            "claimed_completed": replay2["completed"],
            "final_position": replay2["final_position"],
            "submission_id": "sub_valid_p2",
        }
        statusSub2, subResp2 = self.client.post(f"/api/v1/matches/{matchId}/submit", subPayload2, token=tok2)
        self.assertEqual(statusSub2, 200)
        self.assertEqual(subResp2["status"], "COMPLETED")
        self.assertEqual(subResp2["winner_id"], uid1)
        self.assertFalse(subResp2["is_draw"])

    def testWallCollisionPitTeleportBoneCollectionTimeoutAndDraw(self):
        customGrid = []
        for y in range(10):
            row = []
            for x in range(10):
                row.append({
                    "element": 0,
                    "top": y == 0,
                    "bottom": y == 9,
                    "left": x == 0,
                    "right": x == 9,
                    "pit_destination": None,
                    "visited": False,
                })
            customGrid.append(row)
        customGrid[0][0]["element"] = 1
        customGrid[0][1]["element"] = 3
        customGrid[0][1]["pit_destination"] = {"x": 5, "y": 5}
        customGrid[5][5]["element"] = 4
        customGrid[5][6]["element"] = 2
        customGrid[0][2]["element"] = 4
        customGrid[0][3]["element"] = 4
        customGrid[0][4]["element"] = 4
        customGrid[0][5]["element"] = 4

        customMaze = {"metadata": {"maze_name": "unit_replay_maze"}, "grid": customGrid}
        replay = replayActionTrace(customMaze, [0, 3, 3], maxSteps=10)
        self.assertTrue(replay["valid"])
        self.assertTrue(replay["completed"])
        self.assertEqual(replay["steps"], 3)
        self.assertEqual(replay["bones_collected"], 1)
        self.assertEqual(replay["verified_score"], 3 - 5 * 1)
        self.assertEqual(replay["final_position"], [6, 5])

        timeoutReplay = replayActionTrace(customMaze, [0] * 10, maxSteps=10)
        self.assertTrue(timeoutReplay["valid"])
        self.assertFalse(timeoutReplay["completed"])
        self.assertTrue(timeoutReplay["timeout"])
        self.assertEqual(timeoutReplay["steps"], 10)

        uid1, tok1 = self._register("draw_p1")
        uid2, tok2 = self._register("draw_p2")
        db = getDb()
        matchModel, mapModel = createMatchForPlayers(db, uid1, uid2, seed=99)
        winActions = findWinningActionSequence(mapModel.mazeJson)
        rep = replayActionTrace(mapModel.mazeJson, winActions)

        for idx, tok in enumerate((tok1, tok2)):
            status, res = self.client.post(
                f"/api/v1/matches/{matchModel.id}/submit",
                {
                    "map_id": mapModel.id,
                    "map_hash": mapModel.mazeHash,
                    "action_trace": winActions,
                    "claimed_score": rep["verified_score"],
                    "claimed_steps": rep["steps"],
                    "claimed_bones_collected": rep["bones_collected"],
                    "claimed_completed": rep["completed"],
                    "final_position": rep["final_position"],
                    "submission_id": f"draw_sub_{idx}",
                },
                token=tok,
            )
            self.assertEqual(status, 200)

        _, finalMatch = self.client.get(f"/api/v1/matches/{matchModel.id}/result", token=tok1)
        self.assertEqual(finalMatch["status"], "COMPLETED")
        self.assertIsNone(finalMatch["winner_id"])
        self.assertTrue(finalMatch["is_draw"])
        self.assertEqual(finalMatch["player_1"]["submission"]["trophy_change"], 5)
        self.assertEqual(finalMatch["player_2"]["submission"]["trophy_change"], 5)


if __name__ == "__main__":
    unittest.main()

