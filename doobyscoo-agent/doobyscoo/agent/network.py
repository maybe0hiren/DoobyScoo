import torch
from torch import nn
from torch.distributions import Categorical
from .recurrent_state import RecurrentState
from ..environment.observation import (
    ACTION_MASK_OFFSET,
    BONE_FEATURES_PER_SLOT,
    BONE_OBSERVATION_OFFSET,
    EXPLORATION_MEMORY_OFFSET,
    LOCAL_VIEW_OFFSET,
    LOCAL_VIEW_SIZE,
    MAX_BONES,
    NAVIGATION_OFFSET,
    OBJECTIVE_OFFSET,
    OBSERVATION_SIZE,
)

ARCHITECTURE_ID = "doobyscoo-recurrent-ppo-v4"
OPPOSITE_ACTION = (1, 0, 3, 2)
DIRECTION_CODES = 5
DIR_FEATURE_SIZE = 17
MASKED_LOGIT_VALUE = -1e9


def _orthogonal(layer, gain):
    nn.init.orthogonal_(layer.weight, gain=gain)
    if layer.bias is not None:
        nn.init.zeros_(layer.bias)
    return layer


def extractActionMask(observation, actionMask=None):
    """Extract a boolean legal-action mask of shape [..., 4].

    If all four directions are blocked (e.g. a sealed test cell), falls back to
    all-True so probability distributions remain valid and finite.
    """
    obsTensor = torch.as_tensor(observation, dtype=torch.float32)
    if actionMask is not None:
        rawMask = torch.as_tensor(actionMask, dtype=torch.float32, device=obsTensor.device)
        if rawMask.shape != obsTensor.shape[:-1] + (4,):
            rawMask = rawMask.view(*obsTensor.shape[:-1], 4)
        mask = rawMask > 0.5
    elif obsTensor.shape[-1] >= ACTION_MASK_OFFSET + 4:
        mask = obsTensor[..., ACTION_MASK_OFFSET : ACTION_MASK_OFFSET + 4] > 0.5
    else:
        mask = obsTensor[..., :4].abs() > 1e-5

    anyLegal = mask.any(dim=-1, keepdim=True)
    safeMask = torch.where(anyLegal, mask, torch.ones_like(mask))
    return safeMask


def maskActionLogits(logits, actionMask):
    """Mask illegal action logits to MASKED_LOGIT_VALUE (-1e9) so Categorical assigns
    exact 0.0 probability to blocked actions while keeping gradients finite."""
    if actionMask is None:
        return logits
    mask = actionMask.to(device=logits.device, dtype=torch.bool)
    if mask.shape != logits.shape:
        mask = mask.view_as(logits)
    anyLegal = mask.any(dim=-1, keepdim=True)
    safeMask = torch.where(anyLegal, mask, torch.ones_like(mask))
    return logits.masked_fill(~safeMask, MASKED_LOGIT_VALUE)


class RecurrentPolicy(nn.Module):
    """Recurrent actor-critic with 5x5 local view, legal action masking,
    dead-end/junction topology awareness, 5-Bone + End compass features,
    and LSTM episodic memory.
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

    def _directionalPull(self, dx, dy):
        stepX = torch.where(dx.abs() > 0.02, dx.sign(), torch.zeros_like(dx))
        stepY = torch.where(dy.abs() > 0.02, dy.sign(), torch.zeros_like(dy))
        magX = dx.abs().clamp(max=1.0)
        magY = dy.abs().clamp(max=1.0)
        totalMag = (magX + magY).clamp(min=1e-5)
        pullX = stepX * (0.5 + 0.5 * (magX / totalMag))
        pullY = stepY * (0.5 + 0.5 * (magY / totalMag))
        return torch.stack(
            [
                (-pullY).clamp(min=0.0),
                pullY.clamp(min=0.0),
                (-pullX).clamp(min=0.0),
                pullX.clamp(min=0.0),
            ],
            dim=-1,
        )

    def featurize(self, observation):
        if observation.shape[-1] != self.observationSize:
            raise ValueError(f"Expected {self.observationSize}-feature observation, got {observation.shape[-1]}")
        maxDir = observation[..., :4].detach().abs().max()
        scaledDir = observation[..., :4] * 4.0 if maxDir <= 1.05 else observation[..., :4]
        codes = torch.clamp(torch.round(scaledDir), 0, DIRECTION_CODES - 1).long()
        oneHot = torch.nn.functional.one_hot(codes, DIRECTION_CODES).float()  # [..., 4, 5]

        rest = observation[..., 4:]
        if self.observationSize >= BONE_OBSERVATION_OFFSET + MAX_BONES * BONE_FEATURES_PER_SLOT:
            boneSlice = observation[..., BONE_OBSERVATION_OFFSET : BONE_OBSERVATION_OFFSET + MAX_BONES * BONE_FEATURES_PER_SLOT]
            maxDisp = boneSlice.detach().abs().max()
            if maxDisp > 1.05:
                boneScaled = boneSlice.clone()
                boneScaled[..., 0::3] = boneScaled[..., 0::3] / 9.0
                boneScaled[..., 1::3] = boneScaled[..., 1::3] / 9.0
                rest = torch.cat(
                    [
                        observation[..., 4:BONE_OBSERVATION_OFFSET],
                        boneScaled,
                        observation[..., BONE_OBSERVATION_OFFSET + MAX_BONES * BONE_FEATURES_PER_SLOT :],
                    ],
                    dim=-1,
                )

        flat = torch.cat([oneHot.flatten(start_dim=-2), rest], dim=-1)

        if self.observationSize < 23:
            return flat, None

        isBlocked = oneHot[..., 0:1]
        isEmpty = oneHot[..., 1:2]
        isBone = oneHot[..., 2:3]
        isEnd = oneHot[..., 3:4]
        isPit = oneHot[..., 4:5]
        isOpen = 1.0 - isBlocked

        if self.observationSize >= NAVIGATION_OFFSET + 16:
            deadEndExit = observation[..., NAVIGATION_OFFSET + 12 : NAVIGATION_OFFSET + 16].unsqueeze(-1) * isOpen
            unexplored = observation[..., NAVIGATION_OFFSET + 8 : NAVIGATION_OFFSET + 12].unsqueeze(-1) * isOpen * (1.0 - deadEndExit)
        else:
            deadEndExit = torch.zeros_like(isOpen)
            nVisitsTmp = observation[..., 8:12].unsqueeze(-1) * isOpen
            eVisitsTmp = observation[..., 13:17].unsqueeze(-1) * isOpen
            unexplored = ((nVisitsTmp < 0.05) & (eVisitsTmp < 0.05)).float() * isOpen

        nVisits = observation[..., 8:12].unsqueeze(-1) * isOpen
        eVisits = observation[..., 13:17].unsqueeze(-1) * isOpen
        pitUnvisited = isPit * (nVisits < 0.05).float()
        pitVisited = isPit * (nVisits >= 0.05).float()

        lastAct = observation[..., 17:21]
        revIdx = torch.tensor(OPPOSITE_ACTION, device=observation.device, dtype=torch.long)
        movedLast = 1.0 - observation[..., 21:22]
        rawRev = (lastAct.index_select(-1, revIdx) * movedLast).unsqueeze(-1) * isOpen
        nonDeadOpenCount = (isOpen * (1.0 - deadEndExit)).sum(dim=-2, keepdim=True)
        # Only treat reverse as undesirable when there is at least one other non-dead-end open exit
        isRev = rawRev * (nonDeadOpenCount > 1.5).float()
        bumpedThisDir = (lastAct * observation[..., 21:22]).unsqueeze(-1)
        endReady = isEnd * (1.0 - 0.5 * observation[..., 7:8].unsqueeze(-1))

        nonDeadOpen = isOpen * (1.0 - deadEndExit)
        if self.observationSize >= BONE_OBSERVATION_OFFSET + MAX_BONES * BONE_FEATURES_PER_SLOT:
            boneFlat = rest[..., (BONE_OBSERVATION_OFFSET - 4) : (BONE_OBSERVATION_OFFSET - 4) + MAX_BONES * BONE_FEATURES_PER_SLOT]
            boneReshaped = boneFlat.reshape(*boneFlat.shape[:-1], MAX_BONES, BONE_FEATURES_PER_SLOT)
            dx = boneReshaped[..., 0]
            dy = boneReshaped[..., 1]
            collected = boneReshaped[..., 2]
            activeBone = (collected < 0.5).float()
            dist = (dx.abs() + dy.abs()).clamp(min=0.08)
            weights = activeBone / (dist * dist)
            wSum = weights.sum(dim=-1, keepdim=True).clamp(min=1e-5)
            stepX = torch.where(dx.abs() > 0.02, dx.sign(), torch.zeros_like(dx))
            stepY = torch.where(dy.abs() > 0.02, dy.sign(), torch.zeros_like(dy))
            pullX = (weights * stepX).sum(dim=-1, keepdim=True) / wSum
            pullY = (weights * stepY).sum(dim=-1, keepdim=True) / wSum
            dirPull = torch.cat(
                [
                    (-pullY).clamp(min=0.0),
                    pullY.clamp(min=0.0),
                    (-pullX).clamp(min=0.0),
                    pullX.clamp(min=0.0),
                ],
                dim=-1,
            )
            boneCompass = dirPull.unsqueeze(-1) * nonDeadOpen
        else:
            boneCompass = torch.zeros_like(unexplored)

        if self.observationSize >= OBJECTIVE_OFFSET + 6:
            endDx = observation[..., OBJECTIVE_OFFSET]
            endDy = observation[..., OBJECTIVE_OFFSET + 1]
            targetDx = observation[..., OBJECTIVE_OFFSET + 3]
            targetDy = observation[..., OBJECTIVE_OFFSET + 4]
            remBonesRatio = observation[..., 7:8]
            endWeight = (1.0 - 0.65 * remBonesRatio).unsqueeze(-1)
            endCompass = self._directionalPull(endDx, endDy).unsqueeze(-1) * nonDeadOpen * endWeight
            targetCompass = self._directionalPull(targetDx, targetDy).unsqueeze(-1) * nonDeadOpen
        else:
            endCompass = torch.zeros_like(unexplored)
            targetCompass = boneCompass

        corridorContinue = nonDeadOpen * (1.0 - isRev)

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
                boneCompass,
                deadEndExit,
                targetCompass,
                endCompass,
                corridorContinue,
            ],
            dim=-1,
        )
        return flat, dirTensor

    def _heads(self, lstmOut, encoded, dirTensor, actionMask=None):
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
        if actionMask is not None:
            logits = maskActionLogits(logits, actionMask)
        value = self.critic(joint).squeeze(-1)
        return logits, value

    def forwardStep(self, observation, state=None, actionMask=None):
        obsTensor = torch.as_tensor(observation, dtype=torch.float32)
        if obsTensor.dim() == 1:
            obsTensor = obsTensor.unsqueeze(0)
        recState = self.initialState(device=obsTensor.device, batchSize=obsTensor.shape[0]) if state is None else RecurrentState.fromTuple(state)
        mask = extractActionMask(obsTensor, actionMask=actionMask)
        flat, dirTensor = self.featurize(obsTensor)
        encoded = self.encoder(flat)
        out, (h, c) = self.memory(encoded.unsqueeze(1), (recState.h.unsqueeze(0), recState.c.unsqueeze(0)))
        logits, value = self._heads(out.squeeze(1), encoded, dirTensor, actionMask=mask)
        nextState = recState._withTensors(h.squeeze(0), c.squeeze(0))
        return logits, value, nextState

    def sequence(self, observations, initialState=None, actions=None, returnDirFeats=False, actionMask=None):
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
        mask = extractActionMask(obsTensor, actionMask=actionMask)
        if actions is not None:
            actTensor = torch.as_tensor(actions, dtype=torch.long, device=obsTensor.device)
            if single and actTensor.dim() == 1:
                actTensor = actTensor.unsqueeze(0)
            if actTensor.shape == mask.shape[:-1]:
                takenMask = torch.nn.functional.one_hot(actTensor.clamp(0, 3), 4).bool()
                mask = mask | takenMask
        flat, dirTensor = self.featurize(obsTensor)
        encoded = self.encoder(flat)
        out, _ = self.memory(encoded, (h0, c0))
        logits, values = self._heads(out, encoded, dirTensor, actionMask=mask)
        if single:
            logits, values = logits.squeeze(0), values.squeeze(0)
            if dirTensor is not None:
                dirTensor = dirTensor.squeeze(0)
        if returnDirFeats and dirTensor is not None:
            return logits, values, dirTensor
        return logits, values


@torch.no_grad()
def chooseAction(model, observation, state=None, deterministic=False, logitBias=None, actionMask=None):
    """Select a legal action using masked policy probabilities.
    deterministic=False samples from the masked policy (training);
    deterministic=True takes the masked argmax (evaluation / competitive inference)."""
    obsTensor = torch.as_tensor(observation, dtype=torch.float32)
    if obsTensor.dim() == 1:
        obsTensor = obsTensor.unsqueeze(0)
    mask = extractActionMask(obsTensor, actionMask=actionMask)
    recState = model.initialState(device=obsTensor.device) if state is None else RecurrentState.fromTuple(state)
    logits, value, nextState = model.forwardStep(obsTensor, recState, actionMask=mask)
    samplingLogits = logits
    if not deterministic and logitBias is not None:
        biasTensor = torch.as_tensor(logitBias, dtype=torch.float32, device=logits.device).view_as(logits)
        samplingLogits = maskActionLogits(logits + biasTensor, mask)
    distribution = Categorical(logits=samplingLogits)
    baseDist = Categorical(logits=logits)
    action = logits.argmax(dim=-1) if deterministic else distribution.sample()
    actionInt = int(action.item())
    logProb = float(baseDist.log_prob(action).item())
    nextState.recordAction(obsTensor, actionInt)
    return actionInt, logProb, float(value.item()), nextState


@torch.no_grad()
def chooseActionsBatch(model, observations, state, deterministic=False, logitBias=None, actionMask=None):
    """Vectorised masked action selection for B independent episodes."""
    obsTensor = torch.as_tensor(observations, dtype=torch.float32)
    mask = extractActionMask(obsTensor, actionMask=actionMask)
    logits, values, nextState = model.forwardStep(obsTensor, state, actionMask=mask)
    samplingLogits = logits
    if not deterministic and logitBias is not None:
        biasTensor = torch.as_tensor(logitBias, dtype=torch.float32, device=logits.device).view_as(logits)
        samplingLogits = maskActionLogits(logits + biasTensor, mask)
    samplingDist = Categorical(logits=samplingLogits)
    baseDist = Categorical(logits=logits)
    actions = logits.argmax(dim=-1) if deterministic else samplingDist.sample()
    return actions, baseDist.log_prob(actions), values, baseDist.entropy(), nextState
