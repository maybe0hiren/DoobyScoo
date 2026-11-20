import unittest
import torch
from torch.distributions import Categorical
from doobyscoo.agent import RecurrentPolicy, RecurrentState, chooseAction
from doobyscoo.config import defaultConfig, entropyCoefficient
from doobyscoo.environment import MazeEnvironment, OBSERVATION_SIZE
from doobyscoo.training import collectEpisode, updatePolicy
from tests.test_environment import makeGrid, sampleMaze


class AgentTests(unittest.TestCase):
    def testObservationAndActionOutputShapes(self):
        model = RecurrentPolicy()
        env = MazeEnvironment(sampleMaze(), 20)
        obs = env.observe()
        self.assertEqual(obs.shape, (OBSERVATION_SIZE,))
        state = model.initialState()
        logits, value, nextState = model.forwardStep(obs, state)
        self.assertEqual(logits.shape, (1, 4))
        self.assertEqual(value.shape, (1,))
        dist = Categorical(logits=logits)
        probs = dist.probs
        self.assertEqual(probs.shape, (1, 4))
        self.assertAlmostEqual(float(probs.sum().item()), 1.0, places=5)
        # At Start (0, 2) of sampleMaze, UP (0) and RIGHT (3) are legal; DOWN (1) and LEFT (2) are blocked
        self.assertGreater(float(probs[0, 0].item()), 0.0)
        self.assertEqual(float(probs[0, 1].item()), 0.0)
        self.assertEqual(float(probs[0, 2].item()), 0.0)
        self.assertGreater(float(probs[0, 3].item()), 0.0)
        # Entropy over 2 legal actions is near ln(2) = 0.693
        self.assertGreater(float(dist.entropy().item()), 0.65)
        self.assertIsInstance(nextState, RecurrentState)

    def testLegalActionMaskingAndAllBlockedFallback(self):
        torch.manual_seed(11)
        model = RecurrentPolicy()
        env = MazeEnvironment(sampleMaze(), 20)
        obs = env.observe()
        state = model.initialState()

        # Verify blocked actions (1=DOWN, 2=LEFT) are NEVER selected across 64 samples
        sampled = [chooseAction(model, obs, state, deterministic=False)[0] for _ in range(64)]
        self.assertTrue(all(a in (0, 3) for a in sampled))
        self.assertEqual(set(sampled), {0, 3})

        # Verify deterministic action is also strictly legal
        detAction, detLogProb, _, _ = chooseAction(model, obs, state, deterministic=True)
        self.assertIn(detAction, (0, 3))
        self.assertTrue(float("-inf") < detLogProb <= 0.0)

        # In a cell where all 4 directions are open (centre (1, 1) of an open 3x3 grid), all 4 actions have > 0 probability
        grid = makeGrid(3, 3)
        grid[1][1]["element"] = 1  # Start at (1, 1)
        grid[0][2]["element"] = 2
        openEnv = MazeEnvironment({"metadata": {"maze_name": "open_center"}, "grid": grid}, 20)
        openObs = openEnv.observe()
        openLogits, _, _ = model.forwardStep(openObs, state)
        openDist = Categorical(logits=openLogits)
        self.assertTrue(bool((openDist.probs > 0.0).all().item()))
        self.assertGreater(float(openDist.entropy().item()), 1.30)

        # If all 4 directions are blocked (sealed cell), fallback must keep probabilities valid and finite (no NaNs)
        sealedGrid = makeGrid(3, 3)
        sealedGrid[2][0]["element"] = 1
        sealedGrid[0][2]["element"] = 2
        sealedGrid[2][0]["top"] = True
        sealedGrid[1][0]["bottom"] = True
        sealedGrid[2][0]["right"] = True
        sealedGrid[2][1]["left"] = True
        sealedEnv = MazeEnvironment({"metadata": {"maze_name": "sealed"}, "grid": sealedGrid}, 20)
        sealedObs = sealedEnv.observe()
        sealedLogits, _, _ = model.forwardStep(sealedObs, state)
        sealedDist = Categorical(logits=sealedLogits)
        self.assertFalse(bool(torch.isnan(sealedDist.probs).any().item()))
        self.assertAlmostEqual(float(sealedDist.probs.sum().item()), 1.0, places=5)
        act, lp, val, _ = chooseAction(model, sealedObs, state, deterministic=False)
        self.assertIn(act, range(4))
        self.assertFalse(torch.isnan(torch.tensor([lp, val])).any().item())

    def testStochasticTrainingVsDeterministicEvaluationActions(self):
        torch.manual_seed(7)
        model = RecurrentPolicy()
        grid = makeGrid(3, 3)
        grid[1][1]["element"] = 1  # Start at (1, 1) with all 4 directions legal
        grid[0][2]["element"] = 2
        env = MazeEnvironment({"metadata": {"maze_name": "center_start"}, "grid": grid}, 20)
        obs = env.observe()
        state = model.initialState()

        # Stochastic sampling during training must produce multiple distinct legal actions
        sampledActions = {chooseAction(model, obs, state, deterministic=False)[0] for _ in range(32)}
        self.assertGreaterEqual(len(sampledActions), 3)

        # Deterministic selection during evaluation must always return the same argmax action
        detActions = {chooseAction(model, obs, state, deterministic=True)[0] for _ in range(10)}
        self.assertEqual(len(detActions), 1)

    def testRecurrentStatePersistenceAndReset(self):
        model = RecurrentPolicy()
        env = MazeEnvironment(sampleMaze(), 20)
        obs = env.observe()
        state = model.initialState()
        self.assertEqual(state.stepCount, 0)
        self.assertTrue(torch.allclose(state.h, torch.zeros_like(state.h)))

        action, _, _, nextState = chooseAction(model, obs, state, deterministic=False)
        self.assertIn(action, (0, 3))
        self.assertEqual(nextState.stepCount, 1)
        self.assertFalse(torch.allclose(nextState.h, torch.zeros_like(nextState.h)))

        nextState.reset()
        self.assertEqual(nextState.stepCount, 0)
        self.assertTrue(torch.allclose(nextState.h, torch.zeros_like(nextState.h)))

    def testMovement(self):
        env = MazeEnvironment(sampleMaze(), 20)
        self.assertEqual(env.observe().shape, (OBSERVATION_SIZE,))
        _, _, _, info = env.step(3)
        self.assertTrue(info["bone"])
        self.assertEqual(info["score"], -4)
        _, _, _, info = env.step(0)
        self.assertTrue(info["teleported"])
        self.assertEqual(info["position"], [2, 1])
        _, _, done, info = env.step(0)
        self.assertTrue(done)
        self.assertTrue(info["won"])

    def testTrainingAndEntropySchedule(self):
        cfg = defaultConfig()
        c0 = entropyCoefficient(cfg, 0)
        cMid = entropyCoefficient(cfg, 100)
        cBoost = entropyCoefficient(cfg, 100, measuredEntropy=0.10)
        self.assertGreater(c0, cMid)
        self.assertGreater(cBoost, cMid)

        model = RecurrentPolicy()
        episodes = [collectEpisode(model, sampleMaze(), 12) for _ in range(2)]
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0005)
        metrics = updatePolicy(model, optimizer, episodes, epochs=1, entropyCoef=c0)
        self.assertTrue(float("-inf") < float(metrics) < float("inf"))
        self.assertGreater(metrics.entropy, 0.3)
        self.assertAlmostEqual(metrics.entropyCoef, c0, places=5)


if __name__ == "__main__":
    unittest.main()
