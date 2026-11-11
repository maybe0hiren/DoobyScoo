import numpy as np


class TrainingMetricsTracker:
    def __init__(self):
        self.history = []

    def summarizeBatch(self, updateNumber, numMaps, totalEpisodes, episodes, updateMetrics, evalMetrics=None, checkpointSaved=False):
        wins = [1.0 if ep.get("won", False) else 0.0 for ep in episodes]
        scores = [ep.get("score", 0) for ep in episodes]
        lengths = [ep.get("length", 0) for ep in episodes]
        rewards = [ep.get("totalReward", 0.0) for ep in episodes]

        record = {
            "update": int(updateNumber),
            "numMaps": int(numMaps),
            "episodesCompleted": int(totalEpisodes),
            "winRate": float(np.mean(wins)) if wins else 0.0,
            "meanScore": float(np.mean(scores)) if scores else 0.0,
            "meanEpisodeLength": float(np.mean(lengths)) if lengths else 0.0,
            "meanReward": float(np.mean(rewards)) if rewards else 0.0,
            "policyLoss": float(getattr(updateMetrics, "policyLoss", 0.0)),
            "valueLoss": float(getattr(updateMetrics, "valueLoss", 0.0)),
            "entropy": float(getattr(updateMetrics, "entropy", 0.0)),
            "loss": float(updateMetrics),
            "checkpointSaved": bool(checkpointSaved),
        }
        if evalMetrics is not None:
            record["evalWinRate"] = float(evalMetrics.get("winRate", 0.0))
            record["evalMeanScore"] = float(evalMetrics.get("meanScore", 0.0))
        self.history.append(record)
        if len(self.history) > 200:
            self.history.pop(0)
        return record

    def formatProgress(self, record):
        ckptStr = "saved" if record.get("checkpointSaved") else "skip"
        evalPart = ""
        if "evalWinRate" in record:
            evalPart = f" | evalWin {record['evalWinRate']:.0%} (score {record['evalMeanScore']:.1f})"
        return (
            f"Update {record['update']:03d} | maps {record['numMaps']} | eps {record['episodesCompleted']} | "
            f"win {record['winRate']:.0%} | score {record['meanScore']:.1f} | len {record['meanEpisodeLength']:.1f} | "
            f"rew {record['meanReward']:.2f} | pLoss {record['policyLoss']:.3f} | vLoss {record['valueLoss']:.3f} | "
            f"ent {record['entropy']:.3f}{evalPart} | ckpt: {ckptStr}"
        )

