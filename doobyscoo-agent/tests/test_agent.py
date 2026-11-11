import unittest
import torch
from torch.distributions import Categorical
from doobyscoo.agent import RecurrentPolicy, RecurrentState, chooseAction
from doobyscoo.environment import MazeEnvironment
from doobyscoo.training import collectEpisode, updatePolicy
from tests.test_environment import sampleMaze


class AgentTests(unittest.TestCase):
    def testObservationAndActionOutputShapes(self):
        model = RecurrentPolicy()
        env = MazeEnvironment(sampleMaze(), 20)
        obs = env.observe()
        self.assertEqual(obs.shape, (8,))
        state = model.initialState()
        logits, value, nextState = model.forwardStep(obs, state)
        self.assertEqual(logits.shape, (1, 4))
        self.assertEqual(value.shape, (1,))
        dist = Categorical(logits=logits)
        probs = dist.probs
        self.assertEqual(probs.shape, (1, 4))
        self.assertAlmostEqual(float(probs.sum().item()), 1.0, places=5)
        self.assertTrue(bool((probs > 0.0).all().item()))
        self.assertIsInstance(nextState, RecurrentState)

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
        self.assertEqual(env.observe().shape, (8,))
        _, _, _, info = env.step(3)
        self.assertTrue(info["bone"])
        self.assertEqual(info["score"], -4)
        _, _, _, info = env.step(0)
        self.assertTrue(info["teleported"])
        self.assertEqual(info["position"], [2, 1])
        _, _, done, info = env.step(0)
        self.assertTrue(done)
        self.assertTrue(info["won"])

    def testTraining(self):
        model = RecurrentPolicy()
        episodes = [collectEpisode(model, sampleMaze(), 12) for _ in range(2)]
        optimizer = torch.optim.Adam(model.parameters(), lr=0.0003)
        loss = updatePolicy(model, optimizer, episodes, epochs=1)
        self.assertTrue(float("-inf") < loss < float("inf"))


if __name__ == "__main__":
    unittest.main()
