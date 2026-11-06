import json
import random
from pathlib import Path
import numpy as np
import torch
from torch.distributions import Categorical
from .agent import RecurrentPolicy, chooseAction
from .environment import MazeEnvironment, loadMaze


def discoverMaps(folder):
    paths = sorted(Path(folder).rglob("*.json"))
    valid = []
    for path in paths:
        try:
            MazeEnvironment(loadMaze(path))
            valid.append(path)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print(f"Skipping {path.name}: {error}")
    if not valid:
        raise ValueError(f"No valid maze JSON files in {folder}")
    return valid


def saveCheckpoint(path, model, optimizer, updates, bestRate=0.0):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tempPath = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(), "updates": updates, "bestRate": bestRate}, tempPath)
    tempPath.replace(path)


def loadCheckpoint(path, model, optimizer=None):
    path = Path(path)
    if not path.exists():
        return 0, 0.0
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    model.load_state_dict(payload["model"])
    if optimizer is not None and "optimizer" in payload:
        optimizer.load_state_dict(payload["optimizer"])
    return int(payload.get("updates", 0)), float(payload.get("bestRate", 0))


def collectEpisode(model, mazeData, maxSteps):
    env = MazeEnvironment(mazeData, maxSteps)
    observation = env.reset()
    state = model.initialState()
    episode = {"observations": [], "actions": [], "logProbs": [], "values": [], "rewards": []}
    info = None
    for _ in range(maxSteps):
        action, logProb, value, state = chooseAction(model, observation, state)
        nextObservation, reward, done, info = env.step(action)
        episode["observations"].append(observation)
        episode["actions"].append(action)
        episode["logProbs"].append(logProb)
        episode["values"].append(value)
        episode["rewards"].append(reward)
        observation = nextObservation
        if done:
            break
    episode["won"] = bool(info["won"])
    episode["score"] = info["score"]
    episode["length"] = len(episode["actions"])
    return episode


def computeAdvantages(episode, gamma=0.99, gaeLambda=0.95):
    rewards, values = episode["rewards"], episode["values"]
    advantages = np.zeros(len(rewards), dtype=np.float32)
    running = 0.0
    for index in reversed(range(len(rewards))):
        nextValue = values[index + 1] if index + 1 < len(values) else 0.0
        delta = rewards[index] + gamma * nextValue - values[index]
        running = delta + gamma * gaeLambda * running
        advantages[index] = running
    return advantages, advantages + np.asarray(values, dtype=np.float32)


def updatePolicy(model, optimizer, episodes, epochs=4, clipRange=0.2):
    advantageList = [computeAdvantages(episode)[0] for episode in episodes]
    allAdvantages = np.concatenate(advantageList)
    advantageMean = float(allAdvantages.mean())
    advantageStd = float(allAdvantages.std() + 1e-8)
    losses = []
    for _ in range(epochs):
        randomOrder = list(range(len(episodes)))
        random.shuffle(randomOrder)
        for index in randomOrder:
            episode = episodes[index]
            observations = torch.as_tensor(np.asarray(episode["observations"]), dtype=torch.float32)
            actions = torch.tensor(episode["actions"], dtype=torch.long)
            oldLogProbs = torch.tensor(episode["logProbs"], dtype=torch.float32)
            advantages, returns = computeAdvantages(episode)
            advantages = torch.as_tensor((advantages - advantageMean) / advantageStd)
            returns = torch.as_tensor(returns)
            logits, values = model.sequence(observations)
            distribution = Categorical(logits=logits)
            ratio = (distribution.log_prob(actions) - oldLogProbs).exp()
            actorLoss = -torch.minimum(ratio * advantages, torch.clamp(ratio, 1 - clipRange, 1 + clipRange) * advantages).mean()
            valueLoss = 0.5 * (values - returns).square().mean()
            entropy = distribution.entropy().mean()
            loss = actorLoss + 0.5 * valueLoss - 0.01 * entropy
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()
            losses.append(float(loss.detach()))
    return float(np.mean(losses))


def evaluate(model, paths, episodesPerMap=3, maxSteps=300):
    wins, scores, total = 0, [], 0
    model.eval()
    with torch.no_grad():
        for path in paths:
            mazeData = loadMaze(path)
            for _ in range(episodesPerMap):
                env = MazeEnvironment(mazeData, maxSteps)
                observation = env.reset()
                state = model.initialState()
                for _ in range(maxSteps):
                    action, _, _, state = chooseAction(model, observation, state, deterministic=True)
                    observation, _, done, info = env.step(action)
                    if done:
                        break
                wins += int(info["won"])
                scores.append(info["score"])
                total += 1
    return {"winRate": wins / max(1, total), "meanScore": float(np.mean(scores)), "episodes": total}


def train(mapsFolder, checkpoint, updates=100, episodesPerUpdate=8, maxSteps=300, learningRate=3e-4, rehearsalFolder=None):
    torch.set_num_threads(min(4, torch.get_num_threads()))
    paths = discoverMaps(mapsFolder)
    if rehearsalFolder:
        paths = list(dict.fromkeys(paths + discoverMaps(rehearsalFolder)))
    model = RecurrentPolicy()
    optimizer = torch.optim.Adam(model.parameters(), lr=learningRate)
    startUpdate, bestRate = loadCheckpoint(checkpoint, model, optimizer)
    print(f"Maps: {len(paths)} | Resuming from update: {startUpdate} | Device: CPU", flush=True)
    for updateIndex in range(1, updates + 1):
        model.eval()
        episodes = [collectEpisode(model, loadMaze(random.choice(paths)), maxSteps) for _ in range(episodesPerUpdate)]
        model.train()
        loss = updatePolicy(model, optimizer, episodes)
        updateNumber = startUpdate + updateIndex
        winRate = sum(episode["won"] for episode in episodes) / len(episodes)
        if updateIndex % 5 == 0 or updateIndex == updates:
            metrics = evaluate(model, paths, episodesPerMap=1, maxSteps=maxSteps)
            bestRate = max(bestRate, metrics["winRate"])
            saveCheckpoint(checkpoint, model, optimizer, updateNumber, bestRate)
            print(f"Update {updateNumber} | rollout wins {winRate:.0%} | eval wins {metrics['winRate']:.0%} | score {metrics['meanScore']:.1f} | loss {loss:.3f}", flush=True)
        elif updateIndex % 1 == 0:
            print(f"Update {updateNumber} | rollout wins {winRate:.0%} | loss {loss:.3f}", flush=True)
    return model
