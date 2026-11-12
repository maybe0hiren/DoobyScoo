import unittest
from app.database.session import getDb
from app.rl_verification.maze_environment import computeMazeHash, validateCompetitionMaze
from app.services.map_generator import generateCompetitionMaze
from app.services.match_service import createMatchForPlayers
from tests.helpers import createIsolatedTestApp


class MatchmakingAndMapTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.tmpDir = createIsolatedTestApp()

    def tearDown(self):
        self.tmpDir.cleanup()

    def _register(self, username, trophies=0, league="Beginner"):
        _, res = self.client.post(
            "/api/v1/auth/register",
            {
                "username": username,
                "email": f"{username}@example.com",
                "password": "Password123!",
                "display_name": username,
            },
        )
        uid = res["player"]["player_id"]
        if trophies > 0 or league != "Beginner":
            db = getDb()
            db.execute(
                "UPDATE player_profiles SET trophies = ?, league = ? WHERE user_id = ?",
                (int(trophies), str(league), uid),
            )
        return uid, res["access_token"]

    def testServerMapGenerationAndValidation(self):
        for diff in ("easy", "medium", "hard"):
            generated = generateCompetitionMaze(difficulty=diff, seed=42)
            self.assertEqual(generated["difficulty"], diff)
            validation = validateCompetitionMaze(
                generated["mazeJson"],
                requireStandardSize=True,
                requireExactBones=True,
                maxBones=5,
                requireOuterWalls=True,
                requireWallSync=True,
                requireSolvable=True,
            )
            self.assertTrue(validation["valid"], f"Generated {diff} maze failed validation: {validation['errors']}")
            self.assertTrue(validation["solvable"])
            self.assertEqual(generated["mazeHash"], computeMazeHash(generated["mazeJson"]))

    def testQueueJoinCancelDuplicateAndPairMatching(self):
        uid1, tok1 = self._register("p1_queue", trophies=100, league="Beginner")
        uid2, tok2 = self._register("p2_queue", trophies=140, league="Beginner")

        status, join1 = self.client.post("/api/v1/matchmaking/join", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(join1["state"], "SEARCHING")
        self.assertIsNone(join1["match_id"])

        status, dupJoin1 = self.client.post("/api/v1/matchmaking/join", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(dupJoin1["state"], "SEARCHING")

        status, cancel1 = self.client.post("/api/v1/matchmaking/cancel", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(cancel1["state"], "CANCELLED")
        self.assertTrue(cancel1["cancelled"])

        status, join1Again = self.client.post("/api/v1/matchmaking/join", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(join1Again["state"], "SEARCHING")

        status, join2 = self.client.post("/api/v1/matchmaking/join", token=tok2)
        self.assertEqual(status, 200)
        self.assertEqual(join2["state"], "MAP_ASSIGNED")
        matchId = join2["match_id"]
        self.assertIsNotNone(matchId)

        status, st1 = self.client.get("/api/v1/matchmaking/status", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(st1["match_id"], matchId)

    def testTrophyBasedMatchingAndSelfMatchPrevention(self):
        uid1, tok1 = self._register("bronze_a", trophies=600, league="Bronze")
        uid2, tok2 = self._register("master_x", trophies=3200, league="Master")
        uid3, tok3 = self._register("bronze_b", trophies=630, league="Bronze")

        db = getDb()
        with self.assertRaises(Exception):
            createMatchForPlayers(db, uid1, uid1)

        self.client.post("/api/v1/matchmaking/join", token=tok1)
        _, joinMaster = self.client.post("/api/v1/matchmaking/join", token=tok2)
        self.assertEqual(joinMaster["state"], "SEARCHING")

        _, joinBronzeB = self.client.post("/api/v1/matchmaking/join", token=tok3)
        self.assertEqual(joinBronzeB["state"], "MAP_ASSIGNED")
        matchedPlayers = {
            joinBronzeB["match"]["player_1"]["player_id"],
            joinBronzeB["match"]["player_2"]["player_id"],
        }
        self.assertEqual(matchedPlayers, {uid1, uid3})

    def testMatchExpiration(self):
        uid1, tok1 = self._register("exp_p1")
        uid2, tok2 = self._register("exp_p2")
        db = getDb()
        matchModel, _ = createMatchForPlayers(db, uid1, uid2, expirationSeconds=-5)

        status, matchResp = self.client.get(f"/api/v1/matches/{matchModel.id}", token=tok1)
        self.assertEqual(status, 200)
        self.assertEqual(matchResp["status"], "EXPIRED")

        status, subAfterExp = self.client.post(
            f"/api/v1/matches/{matchModel.id}/submit",
            {
                "action_trace": [0],
                "claimed_score": 1,
                "claimed_steps": 1,
                "claimed_bones_collected": 0,
                "claimed_completed": False,
                "final_position": [0, 0],
            },
            token=tok2,
        )
        self.assertEqual(status, 400)
        self.assertEqual(subAfterExp["code"], "match_expired")


if __name__ == "__main__":
    unittest.main()

