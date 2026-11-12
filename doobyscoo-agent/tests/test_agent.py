import unittest
import torch
from torch.distributions import Categorical
from doobyscoo.agent import RecurrentPolicy, RecurrentState, chooseAction
from doobyscoo.config import defaultConfig, entropyCoefficient
from doobyscoo.environment import MazeEnvironment, OBSERVATION_SIZE
from doobyscoo.training import collectEpisode, updatePolicy
from tests.test_environment import sampleMaze


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
        self.assertTrue(bool((probs > 0.0).all().item()))
        # Freshly initialized policy must have near-maximal entropy (~ln(4) = 1.386)
        self.assertGreater(float(dist.entropy().item()), 1.30)
        self.assertIsInstance(nextState, RecurrentState)

    def testStochasticTrainingVsDeterministicEvaluationActions(self):
        torch.manual_seed(7)
        model = RecurrentPolicy()
        env = MazeEnvironment(sampleMaze(), 20)
        obs = env.observe()
        state = model.initialState()

        # Stochastic sampling during training must produce multiple distinct actions
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
        self.assertIn(action, range(4))
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
        self.assertGreater(metrics.entropy, 0.5)
        self.assertAlmostEqual(metrics.entropyCoef, c0, places=5)


if __name__ == "__main__":
    unittest.main()
