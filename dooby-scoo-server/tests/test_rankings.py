import unittest
from app.config import settings
from app.database.session import getDb
from app.rl_verification.action_replay import replayActionTrace
from app.services.match_service import createMatchForPlayers
from tests.helpers import createIsolatedTestApp, findWinningActionSequence


class RankingsAndProgressionTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.tmpDir = createIsolatedTestApp()

    def tearDown(self):
        self.tmpDir.cleanup()

    def _register(self, username, trophies=0):
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
        if trophies > 0:
            db = getDb()
            league = settings.getLeagueForTrophies(trophies)
            db.execute(
                "UPDATE player_profiles SET trophies = ?, league = ? WHERE user_id = ?",
                (int(trophies), league, uid),
            )
        return uid, res["access_token"]

    def testLeagueThresholdsTrophyClampingAndXpProgression(self):
        self.assertEqual(settings.getLeagueForTrophies(0), "Beginner")
        self.assertEqual(settings.getLeagueForTrophies(499), "Beginner")
        self.assertEqual(settings.getLeagueForTrophies(500), "Bronze")
        self.assertEqual(settings.getLeagueForTrophies(1000), "Silver")
        self.assertEqual(settings.getLeagueForTrophies(1500), "Gold")
        self.assertEqual(settings.getLeagueForTrophies(2000), "Platinum")
        self.assertEqual(settings.getLeagueForTrophies(2500), "Diamond")
        self.assertEqual(settings.getLeagueForTrophies(3000), "Master")

        uid1, tok1 = self._register("promo_winner", trophies=490)
        uid2, tok2 = self._register("zero_loser", trophies=5)

        db = getDb()
        matchModel, mapModel = createMatchForPlayers(db, uid1, uid2, seed=101)
        winActions = findWinningActionSequence(mapModel.mazeJson)
        winRep = replayActionTrace(mapModel.mazeJson, winActions)
        loseRep = replayActionTrace(mapModel.mazeJson, [0])

        self.client.post(
            f"/api/v1/matches/{matchModel.id}/submit",
            {
                "map_id": mapModel.id,
                "map_hash": mapModel.mazeHash,
                "action_trace": winActions,
                "claimed_score": winRep["verified_score"],
                "claimed_steps": winRep["steps"],
                "claimed_bones_collected": winRep["bones_collected"],
                "claimed_completed": winRep["completed"],
                "final_position": winRep["final_position"],
                "submission_id": "sub_promo_1",
            },
            token=tok1,
        )
        self.client.post(
            f"/api/v1/matches/{matchModel.id}/submit",
            {
                "map_id": mapModel.id,
                "map_hash": mapModel.mazeHash,
                "action_trace": [0],
                "claimed_score": loseRep["verified_score"],
                "claimed_steps": loseRep["steps"],
                "claimed_bones_collected": loseRep["bones_collected"],
                "claimed_completed": loseRep["completed"],
                "final_position": loseRep["final_position"],
                "submission_id": "sub_promo_2",
            },
            token=tok2,
        )

        _, p1Prof = self.client.get("/api/v1/players/me", token=tok1)
        _, p2Prof = self.client.get("/api/v1/players/me", token=tok2)

        self.assertEqual(p1Prof["player"]["trophies"], 515)
        self.assertEqual(p1Prof["player"]["league"], "Bronze")
        expectedXp1 = (
            settings.xpMatchParticipation
            + settings.xpMatchWin
            + settings.xpPersonalBest
            + settings.xpLeagueAdvancement
        )
        self.assertEqual(p1Prof["player"]["xp"], expectedXp1)
        self.assertGreaterEqual(p1Prof["player"]["level"], 3)

        self.assertEqual(p2Prof["player"]["trophies"], 0)
        self.assertEqual(p2Prof["player"]["league"], "Beginner")

    def testLeaderboardSortingPaginationAndPositions(self):
        uA, tokA = self._register("rank_a", trophies=1200)
        uB, tokB = self._register("rank_b", trophies=1200)
        uC, tokC = self._register("rank_c", trophies=1800)
        uD, tokD = self._register("rank_d", trophies=600)

        db = getDb()
        db.execute("UPDATE player_profiles SET wins = 8, total_matches = 10 WHERE user_id = ?", (uB,))
        db.execute("UPDATE player_profiles SET wins = 5, total_matches = 10 WHERE user_id = ?", (uA,))

        status, globalLb = self.client.get("/api/v1/leaderboards/global?limit=10&offset=0")
        self.assertEqual(status, 200)
        usernamesOrder = [e["username"] for e in globalLb["entries"]]
        self.assertEqual(usernamesOrder, ["rank_c", "rank_b", "rank_a", "rank_d"])

        status, pageLb = self.client.get("/api/v1/leaderboards/global?limit=2&offset=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(pageLb["entries"]), 2)
        self.assertEqual(pageLb["entries"][0]["position"], 2)
        self.assertEqual(pageLb["entries"][0]["username"], "rank_b")

        status, silverLb = self.client.get("/api/v1/leaderboards/league/Silver")
        self.assertEqual(status, 200)
        self.assertEqual([e["username"] for e in silverLb["entries"]], ["rank_b", "rank_a"])

        status, rankResp = self.client.get("/api/v1/players/me/rank", token=tokA)
        self.assertEqual(status, 200)
        self.assertEqual(rankResp["global_position"], 3)
        self.assertEqual(rankResp["league_position"], 2)
        self.assertGreaterEqual(len(rankResp["nearby_players"]), 3)


if __name__ == "__main__":
    unittest.main()

