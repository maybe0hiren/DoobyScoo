import random
import numpy as np
import torch
from torch.distributions import Categorical


class UpdateMetrics(float):
    def __new__(cls, totalLoss, policyLoss=0.0, valueLoss=0.0, entropy=0.0, approxKl=0.0, clipFraction=0.0,
                epochsRun=0, entropyCoef=0.0):
        instance = super().__new__(cls, float(totalLoss))
        instance.totalLoss = float(totalLoss)
        instance.policyLoss = float(policyLoss)
        instance.valueLoss = float(valueLoss)
        instance.entropy = float(entropy)
        instance.approxKl = float(approxKl)
        instance.clipFraction = float(clipFraction)
        instance.epochsRun = int(epochsRun)
        instance.entropyCoef = float(entropyCoef)
        return instance

    def toDict(self):
        return {
            "loss": self.totalLoss,
            "policyLoss": self.policyLoss,
            "valueLoss": self.valueLoss,
            "entropy": self.entropy,
            "approxKl": self.approxKl,
            "clipFraction": self.clipFraction,
            "epochsRun": self.epochsRun,
            "entropyCoef": self.entropyCoef,
        }

    def __getitem__(self, key):
        return self.toDict()[key]


def computeAdvantages(episode, gamma=0.99, gaeLambda=0.95):
    """Generalised Advantage Estimation over one complete episode."""
    rewards = episode["rewards"]
    values = episode["values"]
    bootstrapValue = float(episode.get("bootstrapValue", 0.0))
    advantages = np.zeros(len(rewards), dtype=np.float32)
    running = 0.0
    for index in reversed(range(len(rewards))):
        nextValue = values[index + 1] if index + 1 < len(values) else bootstrapValue
        delta = rewards[index] + gamma * nextValue - values[index]
        running = delta + gamma * gaeLambda * running
        advantages[index] = running
    returns = advantages + np.asarray(values, dtype=np.float32)
    return advantages, returns


def _pad(sequences, length, dtype, featureSize=None):
    shape = (len(sequences), length) if featureSize is None else (len(sequences), length, featureSize)
    out = np.zeros(shape, dtype=dtype)
    for i, seq in enumerate(sequences):
        arr = np.asarray(seq, dtype=dtype)
        out[i, : len(arr)] = arr
    return torch.as_tensor(out)


def updatePolicy(
    model,
    optimizer,
    episodes,
    epochs=4,
    clipRange=0.2,
    valueCoef=0.5,
    entropyCoef=0.015,
    maxGradNorm=0.5,
    gamma=0.99,
    gaeLambda=0.95,
    shortGamma=0.50,
    shortLambda=0.50,
    shortAdvantageWeight=0.55,
    minibatchEpisodes=8,
    targetKl=0.04,
):
    """Recurrent PPO update over complete episodes.

    Every episode is replayed from its own zero initial LSTM state, so sequence
    boundaries are respected; padding is masked out of every loss term. Blends
    short-horizon GAE (for low-variance credit on immediate wall collisions,
    revisits, and bone pickups) with long-horizon GAE (for multi-step routes),
    and updates `dirLinear` on the experienced directional step rewards.
    """
    validEpisodes = [ep for ep in episodes if len(ep.get("actions", [])) > 0]
    if not validEpisodes:
        return UpdateMetrics(0.0, entropyCoef=entropyCoef)

    computed = [computeAdvantages(ep, gamma=gamma, gaeLambda=gaeLambda) for ep in validEpisodes]
    shortComputed = [computeAdvantages(ep, gamma=shortGamma, gaeLambda=shortLambda) for ep in validEpisodes]
    allAdv = np.concatenate([adv for adv, _ in computed])
    advMean = float(allAdv.mean())
    advStd = float(allAdv.std() + 1e-8)
    allShort = np.concatenate([adv for adv, _ in shortComputed])
    shortMean = float(allShort.mean())
    shortStd = float(allShort.std() + 1e-8)
    shortW = float(shortAdvantageWeight)

    featureSize = len(validEpisodes[0]["observations"][0])
    lengths = [len(ep["actions"]) for ep in validEpisodes]

    totalLosses, policyLosses, valueLosses, entropies, kls, clipFracs = [], [], [], [], [], []
    epochsRun = 0
    model.train()
    for _ in range(int(epochs)):
        order = list(range(len(validEpisodes)))
        random.shuffle(order)
        epochKls = []
        for start in range(0, len(order), max(1, int(minibatchEpisodes))):
            idx = order[start : start + max(1, int(minibatchEpisodes))]
            maxLen = max(lengths[i] for i in idx)
            obs = _pad([validEpisodes[i]["observations"] for i in idx], maxLen, np.float32, featureSize)
            actions = _pad([validEpisodes[i]["actions"] for i in idx], maxLen, np.int64)
            rewards = _pad([validEpisodes[i]["rewards"] for i in idx], maxLen, np.float32)
            oldLogProbs = _pad([validEpisodes[i]["logProbs"] for i in idx], maxLen, np.float32)
            blendedAdv = [
                (1.0 - shortW) * ((computed[i][0] - advMean) / advStd)
                + shortW * ((shortComputed[i][0] - shortMean) / shortStd)
                for i in idx
            ]
            adv = _pad(blendedAdv, maxLen, np.float32)
            returns = _pad([computed[i][1] for i in idx], maxLen, np.float32)
            mask = _pad([np.ones(lengths[i]) for i in idx], maxLen, np.float32)
            maskSum = mask.sum().clamp(min=1.0)

            seqOut = model.sequence(obs, returnDirFeats=True)
            if len(seqOut) == 3:
                logits, values, dirTensor = seqOut
            else:
                logits, values = seqOut
                dirTensor = None

            distribution = Categorical(logits=logits)
            newLogProbs = distribution.log_prob(actions)
            logRatio = newLogProbs - oldLogProbs
            ratio = logRatio.exp()
            surr1 = ratio * adv
            surr2 = torch.clamp(ratio, 1.0 - clipRange, 1.0 + clipRange) * adv
            actorLoss = -(torch.minimum(surr1, surr2) * mask).sum() / maskSum
            valueLoss = 0.5 * (((values - returns) ** 2) * mask).sum() / maskSum
            entropy = (distribution.entropy() * mask).sum() / maskSum
            loss = actorLoss + valueCoef * valueLoss - entropyCoef * entropy

            chosenDir = None
            targetUtility = None
            if dirTensor is not None and hasattr(model, "dirLinear"):
                chosenDir = dirTensor.detach().gather(
                    2, actions.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, 1, dirTensor.shape[-1])
                ).squeeze(2)
                targetUtility = torch.clamp(rewards, min=-1.0, max=2.2)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), maxGradNorm)
            optimizer.step()

            if chosenDir is not None and targetUtility is not None:
                with torch.no_grad():
                    err = (targetUtility - model.dirLinear(chosenDir).squeeze(-1)) * mask
                    activeMass = (chosenDir.abs() * mask.unsqueeze(-1)).sum(dim=(0, 1)).clamp(min=1.0)
                    gradStep = ((err.unsqueeze(-1) * chosenDir).sum(dim=(0, 1)) / activeMass).unsqueeze(0)
                    model.dirLinear.weight.add_(0.12 * gradStep)

            with torch.no_grad():
                approxKl = float((((ratio - 1.0) - logRatio) * mask).sum() / maskSum)
                clipFrac = float((((ratio - 1.0).abs() > clipRange).float() * mask).sum() / maskSum)
            epochKls.append(approxKl)
            totalLosses.append(float(loss.detach()))
            policyLosses.append(float(actorLoss.detach()))
            valueLosses.append(float(valueLoss.detach()))
            entropies.append(float(entropy.detach()))
            kls.append(approxKl)
            clipFracs.append(clipFrac)
        epochsRun += 1
        if targetKl and np.mean(epochKls) > 1.5 * float(targetKl):
            break

    return UpdateMetrics(
        np.mean(totalLosses),
        policyLoss=np.mean(policyLosses),
        valueLoss=np.mean(valueLosses),
        entropy=np.mean(entropies),
        approxKl=np.mean(kls),
        clipFraction=np.mean(clipFracs),
        epochsRun=epochsRun,
        entropyCoef=entropyCoef,
    )
