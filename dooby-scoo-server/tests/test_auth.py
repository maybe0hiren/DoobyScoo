import unittest
from app.core.security import createJwtToken
from tests.helpers import createIsolatedTestApp


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client, self.tmpDir = createIsolatedTestApp()

    def tearDown(self):
        self.tmpDir.cleanup()

    def testRegistrationLoginProfileAndDuplicates(self):
        status, avail = self.client.get("/api/v1/auth/username-available?username=alpha_dog")
        self.assertEqual(status, 200)
        self.assertTrue(avail["available"])

        status, reg = self.client.post(
            "/api/v1/auth/register",
            {
                "username": "alpha_dog",
                "email": "alpha@example.com",
                "password": "StrongPassword123!",
                "display_name": "Alpha Trainer",
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue(reg["success"])
        self.assertIn("access_token", reg)
        self.assertIn("refresh_token", reg)
        self.assertEqual(reg["player"]["username"], "alpha_dog")
        self.assertEqual(reg["player"]["trophies"], 0)
        self.assertEqual(reg["player"]["league"], "Beginner")

        status, availAfter = self.client.get("/api/v1/auth/username-available?username=alpha_dog")
        self.assertEqual(status, 200)
        self.assertFalse(availAfter["available"])

        status, dupUser = self.client.post(
            "/api/v1/auth/register",
            {
                "username": "ALPHA_DOG",
                "email": "other@example.com",
                "password": "StrongPassword123!",
                "display_name": "Other",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(dupUser["code"], "username_taken")

        status, dupEmail = self.client.post(
            "/api/v1/auth/register",
            {
                "username": "beta_dog",
                "email": "ALPHA@example.com",
                "password": "StrongPassword123!",
                "display_name": "Beta",
            },
        )
        self.assertEqual(status, 409)
        self.assertEqual(dupEmail["code"], "email_taken")

        status, badLogin = self.client.post(
            "/api/v1/auth/login",
            {"username": "alpha_dog", "password": "WrongPassword"},
        )
        self.assertEqual(status, 401)

        status, goodLogin = self.client.post(
            "/api/v1/auth/login",
            {"username": "alpha_dog", "password": "StrongPassword123!"},
        )
        self.assertEqual(status, 200)
        token = goodLogin["access_token"]
        refreshToken = goodLogin["refresh_token"]

        status, meResp = self.client.get("/api/v1/players/me", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(meResp["player"]["email"], "alpha@example.com")

        status, pubResp = self.client.get("/api/v1/players/alpha_dog")
        self.assertEqual(status, 200)
        self.assertEqual(pubResp["player"]["display_name"], "Alpha Trainer")
        self.assertNotIn("email", pubResp["player"])

        status, patchResp = self.client.patch(
            "/api/v1/players/me",
            {"display_name": "Grandmaster Alpha", "avatar": "dog_golden"},
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertEqual(patchResp["player"]["display_name"], "Grandmaster Alpha")
        self.assertEqual(patchResp["player"]["avatar"], "dog_golden")

        status, refResp = self.client.post("/api/v1/auth/refresh", {"refresh_token": refreshToken})
        self.assertEqual(status, 200)
        self.assertIn("access_token", refResp)
        self.assertNotEqual(refResp["refresh_token"], refreshToken)

        status, reusedRefresh = self.client.post("/api/v1/auth/refresh", {"refresh_token": refreshToken})
        self.assertEqual(status, 401)

    def testExpiredTokenAndUnauthorizedAccess(self):
        status, unauth = self.client.get("/api/v1/players/me")
        self.assertEqual(status, 401)

        expiredToken = createJwtToken(
            {"sub": "usr_nonexistent", "username": "ghost", "type": "access"},
            expiresInSeconds=-10,
        )
        status, expResp = self.client.get("/api/v1/players/me", token=expiredToken)
        self.assertEqual(status, 401)
        self.assertEqual(expResp["code"], "token_expired")

    def testPasswordResetAndLogoutRevocation(self):
        _, reg = self.client.post(
            "/api/v1/auth/register",
            {
                "username": "reset_user",
                "email": "reset@example.com",
                "password": "OldPassword123",
                "display_name": "Reset User",
            },
        )
        token = reg["access_token"]
        refreshToken = reg["refresh_token"]

        status, logoutResp = self.client.post(
            "/api/v1/auth/logout",
            {"refresh_token": refreshToken},
            token=token,
        )
        self.assertEqual(status, 200)
        self.assertTrue(logoutResp["success"])

        status, afterLogoutRefresh = self.client.post("/api/v1/auth/refresh", {"refresh_token": refreshToken})
        self.assertEqual(status, 401)

        status, resetResp = self.client.post(
            "/api/v1/auth/password-reset",
            {
                "username": "reset_user",
                "email": "reset@example.com",
                "new_password": "NewPassword456!",
            },
        )
        self.assertEqual(status, 200)

        status, oldLogin = self.client.post(
            "/api/v1/auth/login",
            {"username": "reset_user", "password": "OldPassword123"},
        )
        self.assertEqual(status, 401)

        status, newLogin = self.client.post(
            "/api/v1/auth/login",
            {"username": "reset_user", "password": "NewPassword456!"},
        )
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()

