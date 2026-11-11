from pathlib import Path
import numpy as np
import torch
from ..agent.network import chooseAction
from ..environment.maze_environment import MazeEnvironment, loadMaze


def evaluate(model, paths, episodesPerMap=1, maxSteps=300, deterministic=True, modelVersion=1):
    wins = 0
    timeouts = 0
    scores = []
    lengths = []
    bonesList = []
    rewards = []
    resultsPerMap = {}
    total = 0

    wasTraining = model.training
    model.eval()
    with torch.no_grad():
        for pathItem in paths:
            if isinstance(pathItem, dict):
                mazeData = pathItem
                mapName = mazeData.get("metadata", {}).get("maze_name", f"map_{total}")
            else:
                pathObj = Path(pathItem)
                mazeData = loadMaze(pathObj)
                mapName = pathObj.name

            mapWins = 0
            mapScores = []
            mapLengths = []
            mapBones = []
            for _ in range(episodesPerMap):
                env = MazeEnvironment(mazeData, maxSteps=maxSteps)
                observation = env.reset()
                state = model.initialState()
                info = None
                for _ in range(maxSteps):
                    action, _, _, state = chooseAction(model, observation, state, deterministic=deterministic)
                    observation, _, done, info = env.step(action)
                    if done:
                        break
                won = bool(info["won"])
                timedOut = bool(info["timeout"])
                score = int(info["score"])
                steps = int(info["steps"])
                bones = int(info["bonesCollected"])
                cumReward = float(info["cumulativeReward"])

                wins += int(won)
                timeouts += int(timedOut)
                scores.append(score)
                lengths.append(steps)
                bonesList.append(bones)
                rewards.append(cumReward)
                total += 1

                mapWins += int(won)
                mapScores.append(score)
                mapLengths.append(steps)
                mapBones.append(bones)

            resultsPerMap[mapName] = {
                "winRate": mapWins / max(1, episodesPerMap),
                "meanScore": float(np.mean(mapScores)),
                "meanSteps": float(np.mean(mapLengths)),
                "meanBones": float(np.mean(mapBones)),
                "won": mapWins == episodesPerMap,
            }

    if wasTraining:
        model.train()

    winRate = wins / max(1, total)
    timeoutRate = timeouts / max(1, total)
    failureRate = 1.0 - winRate
    return {
        "winRate": float(winRate),
        "failureRate": float(failureRate),
        "timeoutRate": float(timeoutRate),
        "meanScore": float(np.mean(scores)) if scores else 0.0,
        "medianScore": float(np.median(scores)) if scores else 0.0,
        "meanEpisodeLength": float(np.mean(lengths)) if lengths else 0.0,
        "bonesCollected": float(np.mean(bonesList)) if bonesList else 0.0,
        "meanReward": float(np.mean(rewards)) if rewards else 0.0,
        "episodes": int(total),
        "modelVersion": int(modelVersion),
        "resultsPerMap": resultsPerMap,
    }

