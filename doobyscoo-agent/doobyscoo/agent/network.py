import torch
from torch import nn
from torch.distributions import Categorical
from .recurrent_state import RecurrentState
from ..environment.observation import OBSERVATION_SIZE

ARCHITECTURE_ID = "doobyscoo-recurrent-ppo-v2"
OPPOSITE_ACTION = (1, 0, 3, 2)
DIRECTION_CODES = 5
DIR_FEATURE_SIZE = 12


def _orthogonal(layer, gain):
    nn.init.orthogonal_(layer.weight, gain=gain)
    if layer.bias is not None:
        nn.init.zeros_(layer.bias)
    return layer


class RecurrentPolicy(nn.Module):
    """Recurrent actor-critic with direction-equivariant relational scoring + LSTM memory.

    - The four neighbour-type features are expanded to one-hot categories.
    - A shared per-direction relational scorer (`dirLinear` + `dirMlp` modulated by the
      LSTM hidden state) evaluates each candidate direction using the same learned weights,
      so knowledge about walls, bones, ends, pits, unexplored squares, revisits and doorway
      traversals transfers across all four orientations immediately.
    - Every parameter is randomly initialized and learned end-to-end from experience.
    """

    def __init__(self, observationSize=OBSERVATION_SIZE, hiddenSize=128):
        super().__init__()
        self.observationSize = int(observationSize)
        self.hiddenSize = int(hiddenSize)
        self.architecture = ARCHITECTURE_ID
        featureSize = 4 * DIRECTION_CODES + (self.observationSize - 4)
        self.encoder = nn.Sequential(
            _orthogonal(nn.Linear(featureSize, self.hiddenSize), 2 ** 0.5),
            nn.Tanh(),
            _orthogonal(nn.Linear(self.hiddenSize, self.hiddenSize), 2 ** 0.5),
            nn.Tanh(),
        )
        self.memory = nn.LSTM(self.hiddenSize, self.hiddenSize, batch_first=True)
        headIn = 2 * self.hiddenSize

        self.dirHidden = 32
        self.dirLinear = _orthogonal(nn.Linear(DIR_FEATURE_SIZE, 1, bias=False), 0.01)
        self.dirEncoder = nn.Sequential(
            _orthogonal(nn.Linear(DIR_FEATURE_SIZE, self.dirHidden), 2 ** 0.5),
            nn.Tanh(),
        )
        self.ctxToDir = _orthogonal(nn.Linear(self.hiddenSize, self.dirHidden), 0.2)
        self.dirActor = _orthogonal(nn.Linear(self.dirHidden, 1), 0.05)
        self.actor = _orthogonal(nn.Linear(headIn, 4), 0.01)
        self.critic = nn.Sequential(
            _orthogonal(nn.Linear(headIn, 64), 2 ** 0.5),
            nn.Tanh(),
            _orthogonal(nn.Linear(64, 1), 1.0),
        )

    def initialState(self, device="cpu", batchSize=1):
        return RecurrentState(hiddenSize=self.hiddenSize, batchSize=batchSize, device=device)

    def featurize(self, observation):
        if observation.shape[-1] != self.observationSize:
            raise ValueError(f"Expected {self.observationSize}-feature observation, got {observation.shape[-1]}")
        maxDir = observation[..., :4].detach().abs().max()
        scaledDir = observation[..., :4] * 4.0 if maxDir <= 1.05 else observation[..., :4]
        codes = torch.clamp(torch.round(scaledDir), 0, DIRECTION_CODES - 1).long()
        oneHot = torch.nn.functional.one_hot(codes, DIRECTION_CODES).float()  # [..., 4, 5]
        flat = torch.cat([oneHot.flatten(start_dim=-2), observation[..., 4:]], dim=-1)

        if self.observationSize < 23:
            return flat, None

        isBlocked = oneHot[..., 0:1]
        isEmpty = oneHot[..., 1:2]
        isBone = oneHot[..., 2:3]
        isEnd = oneHot[..., 3:4]
        isPit = oneHot[..., 4:5]
        isOpen = 1.0 - isBlocked

        nVisits = observation[..., 8:12].unsqueeze(-1) * isOpen
        eVisits = observation[..., 13:17].unsqueeze(-1) * isOpen
        unexplored = ((nVisits < 0.05) & (eVisits < 0.05)).float() * isOpen
        pitUnvisited = isPit * (nVisits < 0.05).float()
        pitVisited = isPit * (nVisits >= 0.05).float()

        lastAct = observation[..., 17:21]
        revIdx = torch.tensor(OPPOSITE_ACTION, device=observation.device, dtype=torch.long)
        movedLast = 1.0 - observation[..., 21:22]
        isRev = (lastAct.index_select(-1, revIdx) * movedLast).unsqueeze(-1) * isOpen
        bumpedThisDir = (lastAct * observation[..., 21:22]).unsqueeze(-1)
        endReady = isEnd * (1.0 - observation[..., 7:8].unsqueeze(-1))

        dirTensor = torch.cat(
            [
                isBlocked,
                isEmpty,
                isBone,
                isEnd,
                pitUnvisited,
                pitVisited,
                unexplored,
                nVisits,
                eVisits,
                isRev,
                bumpedThisDir,
                endReady,
            ],
            dim=-1,
        )
        return flat, dirTensor

    def _heads(self, lstmOut, encoded, dirTensor):
        joint = torch.cat([lstmOut, encoded], dim=-1)
        rawActor = self.actor(joint)
        if dirTensor is not None:
            linScore = 5.0 * self.dirLinear(dirTensor.detach()).squeeze(-1)
            dirEmb = self.dirEncoder(dirTensor)
            ctxEmb = self.ctxToDir(lstmOut).unsqueeze(-2)
            mlpScore = self.dirActor(torch.tanh(dirEmb + ctxEmb)).squeeze(-1)
            logits = linScore + 1.2 * torch.tanh(rawActor + mlpScore)
        else:
            logits = rawActor
        value = self.critic(joint).squeeze(-1)
        return logits, value

    def forwardStep(self, observation, state=None):
        obsTensor = torch.as_tensor(observation, dtype=torch.float32)
        if obsTensor.dim() == 1:
            obsTensor = obsTensor.unsqueeze(0)
        recState = self.initialState(device=obsTensor.device, batchSize=obsTensor.shape[0]) if state is None else RecurrentState.fromTuple(state)
        flat, dirTensor = self.featurize(obsTensor)
        encoded = self.encoder(flat)
        out, (h, c) = self.memory(encoded.unsqueeze(1), (recState.h.unsqueeze(0), recState.c.unsqueeze(0)))
        logits, value = self._heads(out.squeeze(1), encoded, dirTensor)
        nextState = recState._withTensors(h.squeeze(0), c.squeeze(0))
        return logits, value, nextState

    def sequence(self, observations, initialState=None, actions=None, returnDirFeats=False):
        """Run full sequences. observations: [T, F] or [B, T, F] (episodes start at t=0)."""
        obsTensor = torch.as_tensor(observations, dtype=torch.float32)
        single = obsTensor.dim() == 2
        if single:
            obsTensor = obsTensor.unsqueeze(0)
        batch = obsTensor.shape[0]
        if initialState is None:
            h0 = torch.zeros(1, batch, self.hiddenSize, device=obsTensor.device)
            c0 = torch.zeros(1, batch, self.hiddenSize, device=obsTensor.device)
        else:
            state = RecurrentState.fromTuple(initialState)
            h0, c0 = state.h.unsqueeze(0), state.c.unsqueeze(0)
        flat, dirTensor = self.featurize(obsTensor)
        encoded = self.encoder(flat)
        out, _ = self.memory(encoded, (h0, c0))
        logits, values = self._heads(out, encoded, dirTensor)
        if single:
            logits, values = logits.squeeze(0), values.squeeze(0)
            if dirTensor is not None:
                dirTensor = dirTensor.squeeze(0)
        if returnDirFeats and dirTensor is not None:
            return logits, values, dirTensor
        return logits, values


@torch.no_grad()
def chooseAction(model, observation, state=None, deterministic=False):
    """Select an action. deterministic=False samples from the policy (training);
    deterministic=True takes the argmax (evaluation / competitive inference)."""
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


@torch.no_grad()
def chooseActionsBatch(model, observations, state, deterministic=False):
    """Vectorised action selection for B independent episodes."""
    obsTensor = torch.as_tensor(observations, dtype=torch.float32)
    logits, values, nextState = model.forwardStep(obsTensor, state)
    distribution = Categorical(logits=logits)
    actions = logits.argmax(dim=-1) if deterministic else distribution.sample()
    return actions, distribution.log_prob(actions), values, distribution.entropy(), nextState
