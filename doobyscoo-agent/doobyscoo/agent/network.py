import torch
from torch import nn
from torch.distributions import Categorical
from .recurrent_state import RecurrentState
from ..environment.observation import OBSERVATION_SIZE

OPPOSITE_ACTION = (1, 0, 3, 2)


class RecurrentPolicy(nn.Module):
    def __init__(self, observationSize=OBSERVATION_SIZE, hiddenSize=128):
        super().__init__()
        self.observationSize = int(observationSize)
        self.hiddenSize = int(hiddenSize)
        stemSize = 29 if self.observationSize == 8 else self.observationSize
        self.encoder = nn.Sequential(
            nn.Linear(stemSize, self.hiddenSize),
            nn.Tanh(),
        )
        self.memory = nn.LSTMCell(self.hiddenSize, self.hiddenSize)
        self.actor = nn.Linear(self.hiddenSize, 4)
        self.critic = nn.Linear(self.hiddenSize, 1)
        self.dirScorer = nn.Linear(9, 1, bias=False)
        nn.init.zeros_(self.dirScorer.weight)
        nn.init.orthogonal_(self.actor.weight, gain=0.05)
        nn.init.zeros_(self.actor.bias)

    def initialState(self, device="cpu", batchSize=1):
        return RecurrentState(hiddenSize=self.hiddenSize, batchSize=batchSize, device=device)

    def _featurize(self, observation, recState=None):
        if observation.dim() == 1:
            observation = observation.unsqueeze(0)
        if self.observationSize != 8 or observation.shape[-1] != 8:
            return observation, None
        directional = observation[:, :4]
        maxDir = directional.detach().abs().max()
        scaledDir = directional * 4.0 if maxDir <= 1.05 else directional
        oneHotParts = []
        dirRows = []
        for idx in range(4):
            col = scaledDir[:, idx : idx + 1]
            codes = []
            for code in range(5):
                cVal = torch.clamp(1.0 - (col - float(code)).abs(), min=0.0)
                oneHotParts.append(cVal)
                codes.append(cVal)
            dirRows.append(torch.cat(codes, dim=-1))
        categoricalDir = torch.cat(oneHotParts, dim=-1)
        dirCodeTensor = torch.stack(dirRows, dim=1)
        extra = observation[:, 4:8]
        if recState is not None and observation.shape[0] == 1:
            visitFeats = recState.neighborVisitFeatures()
            stepFeat = min(1.0, float(recState.stepCount) / 300.0)
            memTensor = torch.tensor([visitFeats + [stepFeat]], dtype=torch.float32, device=observation.device)
            dirMem = torch.tensor([recState.directionalMemoryMatrix(OPPOSITE_ACTION)], dtype=torch.float32, device=observation.device)
        else:
            memTensor = torch.zeros(observation.shape[0], 5, dtype=torch.float32, device=observation.device)
            dirMem = torch.zeros(observation.shape[0], 4, 5, dtype=torch.float32, device=observation.device)
            dirMem[:, :, 0] = 1.0

        isBlocked = dirCodeTensor[:, :, 0:1]
        isEmpty = dirCodeTensor[:, :, 1:2]
        isBone = dirCodeTensor[:, :, 2:3]
        isEnd = dirCodeTensor[:, :, 3:4]
        isPit = dirCodeTensor[:, :, 4:5]
        pitFirst = isPit * dirMem[:, :, 0:1]
        pitRepeat = isPit * dirMem[:, :, 1:2]
        visits = dirMem[:, :, 2:3]
        edges = dirMem[:, :, 3:4]
        isRev = dirMem[:, :, 4:5]
        dirFeats = torch.cat([isBlocked, isEmpty, isBone, isEnd, pitFirst, pitRepeat, visits, edges, isRev], dim=-1)
        return torch.cat([categoricalDir, extra, memTensor], dim=-1), dirFeats

    def forwardStep(self, observation, state=None):
        obsTensor = torch.as_tensor(observation, dtype=torch.float32)
        if obsTensor.dim() == 1:
            obsTensor = obsTensor.unsqueeze(0)
        if state is None:
            recState = self.initialState(device=obsTensor.device, batchSize=obsTensor.shape[0])
        else:
            recState = RecurrentState.fromTuple(state)
        features, dirFeats = self._featurize(obsTensor, recState=recState)
        encoded = self.encoder(features)
        nextH, nextC = self.memory(encoded, (recState.h, recState.c))
        logits = self.actor(nextH)
        if dirFeats is not None:
            logits = logits + 10.0 * self.dirScorer(dirFeats).squeeze(-1)
        value = self.critic(nextH).squeeze(-1)
        nextState = recState.clone()
        nextState.h = nextH
        nextState.c = nextC
        return logits, value, nextState

    def sequence(self, observations, initialState=None, actions=None, returnDirFeats=False):
        obsTensor = torch.as_tensor(observations, dtype=torch.float32)
        if obsTensor.dim() == 1:
            obsTensor = obsTensor.unsqueeze(0)
        state = self.initialState(obsTensor.device) if initialState is None else RecurrentState.fromTuple(initialState)
        logits, values, allDirFeats = [], [], []
        for idx, observation in enumerate(obsTensor):
            obsStep = observation.unsqueeze(0)
            _, dirFeats = self._featurize(obsStep, recState=state)
            logit, value, state = self.forwardStep(obsStep, state)
            logits.append(logit.squeeze(0))
            values.append(value.squeeze(0))
            if dirFeats is not None:
                allDirFeats.append(dirFeats.squeeze(0))
            if actions is not None and idx < len(actions):
                state.recordAction(obsStep, int(actions[idx]))
            else:
                state.recordAction(obsStep, int(logit.argmax(dim=-1).item()))
        if returnDirFeats and allDirFeats:
            return torch.stack(logits), torch.stack(values), torch.stack(allDirFeats)
        return torch.stack(logits), torch.stack(values)


@torch.no_grad()
def chooseAction(model, observation, state=None, deterministic=False):
    obsTensor = torch.as_tensor(observation, dtype=torch.float32)
    if obsTensor.dim() == 1:
        obsTensor = obsTensor.unsqueeze(0)
    recState = model.initialState(device=obsTensor.device) if state is None else RecurrentState.fromTuple(state)
    logits, value, nextState = model.forwardStep(obsTensor, recState)
    distribution = Categorical(logits=logits)
    action = logits.argmax(dim=-1) if deterministic else distribution.sample()
    actionInt = int(action.item())
    logProb = float(distribution.log_prob(action).item())
    nextState.recordAction(obsTensor, actionInt)
    return actionInt, logProb, float(value.item()), nextState
