import torch
from torch import nn
from torch.distributions import Categorical


class RecurrentPolicy(nn.Module):
    def __init__(self, observationSize=22, hiddenSize=128):
        super().__init__()
        self.hiddenSize = hiddenSize
        self.encoder = nn.Sequential(nn.Linear(observationSize, 128), nn.Tanh())
        self.memory = nn.LSTMCell(128, hiddenSize)
        self.actor = nn.Linear(hiddenSize, 4)
        self.critic = nn.Linear(hiddenSize, 1)

    def initialState(self, device="cpu"):
        return (torch.zeros(1, self.hiddenSize, device=device), torch.zeros(1, self.hiddenSize, device=device))

    def forwardStep(self, observation, state):
        encoded = self.encoder(observation)
        nextState = self.memory(encoded, state)
        hidden = nextState[0]
        return self.actor(hidden), self.critic(hidden).squeeze(-1), nextState

    def sequence(self, observations):
        state = self.initialState(observations.device)
        logits, values = [], []
        for observation in observations:
            logit, value, state = self.forwardStep(observation.unsqueeze(0), state)
            logits.append(logit.squeeze(0))
            values.append(value.squeeze(0))
        return torch.stack(logits), torch.stack(values)


@torch.no_grad()
def chooseAction(model, observation, state, deterministic=False):
    logits, value, nextState = model.forwardStep(torch.as_tensor(observation, dtype=torch.float32).unsqueeze(0), state)
    distribution = Categorical(logits=logits)
    action = logits.argmax(dim=-1) if deterministic else distribution.sample()
    return int(action.item()), float(distribution.log_prob(action).item()), float(value.item()), nextState
