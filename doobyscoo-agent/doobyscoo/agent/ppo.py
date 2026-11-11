import random
import numpy as np
import torch
from torch.distributions import Categorical


class UpdateMetrics(float):
    def __new__(cls, totalLoss, policyLoss=0.0, valueLoss=0.0, entropy=0.0, approxKl=0.0):
        instance = super().__new__(cls, float(totalLoss))
        instance.totalLoss = float(totalLoss)
        instance.policyLoss = float(policyLoss)
        instance.valueLoss = float(valueLoss)
        instance.entropy = float(entropy)
        instance.approxKl = float(approxKl)
        return instance

    def toDict(self):
        return {
            "loss": self.totalLoss,
            "policyLoss": self.policyLoss,
            "valueLoss": self.valueLoss,
            "entropy": self.entropy,
            "approxKl": self.approxKl,
        }

    def __getitem__(self, key):
        return self.toDict()[key]


def computeAdvantages(episode, gamma=0.99, gaeLambda=0.95):
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


def updatePolicy(
    model,
    optimizer,
    episodes,
    epochs=4,
    clipRange=0.2,
    valueCoef=0.5,
    entropyCoef=0.01,
    maxGradNorm=0.5,
    gamma=0.99,
    gaeLambda=0.95,
):
    validEpisodes = [ep for ep in episodes if len(ep.get("actions", [])) > 0]
    if not validEpisodes:
        return UpdateMetrics(0.0)

    computed = [computeAdvantages(ep, gamma=gamma, gaeLambda=gaeLambda) for ep in validEpisodes]
    shortComputed = [computeAdvantages(ep, gamma=0.4, gaeLambda=0.4) for ep in validEpisodes]
    allAdvantages = np.concatenate([adv for adv, _ in computed])
    advantageMean = float(allAdvantages.mean())
    advantageStd = float(allAdvantages.std() + 1e-8)
    allShort = np.concatenate([adv for adv, _ in shortComputed])
    shortMean = float(allShort.mean())
    shortStd = float(allShort.std() + 1e-8)

    totalLosses, policyLosses, valueLosses, entropies, kls = [], [], [], [], []

    for _ in range(epochs):
        order = list(range(len(validEpisodes)))
        random.shuffle(order)
        for index in order:
            episode = validEpisodes[index]
            rawAdvantages, rawReturns = computed[index]
            rawShortAdv, _ = shortComputed[index]
            observations = torch.as_tensor(np.asarray(episode["observations"]), dtype=torch.float32)
            actions = torch.as_tensor(episode["actions"], dtype=torch.long)
            rewardsTensor = torch.as_tensor(episode["rewards"], dtype=torch.float32)
            oldLogProbs = torch.as_tensor(episode["logProbs"], dtype=torch.float32)
            normLong = (rawAdvantages - advantageMean) / advantageStd
            normShort = (rawShortAdv - shortMean) / shortStd
            advantages = torch.as_tensor(0.45 * normLong + 0.55 * normShort, dtype=torch.float32)
            returns = torch.as_tensor(rawReturns, dtype=torch.float32)

            initialState = episode.get("initialState", None)
            seqOut = model.sequence(
                observations,
                initialState=initialState,
                actions=episode["actions"],
                returnDirFeats=True,
            )
            if len(seqOut) == 3:
                logits, values, dirFeats = seqOut
            else:
                logits, values = seqOut
                dirFeats = None

            distribution = Categorical(logits=logits)
            newLogProbs = distribution.log_prob(actions)
            logRatio = newLogProbs - oldLogProbs
            ratio = logRatio.exp()

            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1.0 - clipRange, 1.0 + clipRange) * advantages
            actorLoss = -torch.minimum(surr1, surr2).mean()
            valueLoss = 0.5 * (values - returns).square().mean()
            entropy = distribution.entropy().mean()
            loss = actorLoss + valueCoef * valueLoss - entropyCoef * entropy

            if dirFeats is not None and hasattr(model, "dirScorer"):
                chosenFeats = dirFeats[torch.arange(len(actions)), actions]
                predDirUtility = model.dirScorer(chosenFeats).squeeze(-1)
                targetUtility = torch.clamp(rewardsTensor, min=-1.0, max=2.0)
                dirAuxLoss = 0.5 * (predDirUtility - targetUtility).square().mean()
                loss = loss + 0.5 * dirAuxLoss

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), maxGradNorm)
            optimizer.step()
            if dirFeats is not None and hasattr(model, "dirScorer"):
                with torch.no_grad():
                    chosenFeats = dirFeats[torch.arange(len(actions)), actions]
                    err = torch.clamp(rewardsTensor, min=-1.0, max=2.0) - model.dirScorer(chosenFeats).squeeze(-1)
                    gradStep = (err.unsqueeze(-1) * chosenFeats).mean(dim=0, keepdim=True)
                    model.dirScorer.weight.add_(0.08 * gradStep)

            approxKl = float(((ratio - 1.0) - logRatio).mean().detach().item())
            totalLosses.append(float(loss.detach().item()))
            policyLosses.append(float(actorLoss.detach().item()))
            valueLosses.append(float(valueLoss.detach().item()))
            entropies.append(float(entropy.detach().item()))
            kls.append(approxKl)

    return UpdateMetrics(
        np.mean(totalLosses),
        policyLoss=np.mean(policyLosses),
        valueLoss=np.mean(valueLosses),
        entropy=np.mean(entropies),
        approxKl=np.mean(kls),
    )
