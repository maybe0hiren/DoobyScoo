import numpy as np


class TrainingMetricsTracker:
    def __init__(self):
        self.history = []

    def summarizeBatch(
        self,
        updateNumber,
        numMaps,
        totalEpisodes,
        episodes,
        updateMetrics,
        evalMetrics=None,
        retentionMetrics=None,
        checkpointSaved=False,
        bestCheckpointSaved=False,
        entropyCoef=None,
        rehearsalEpisodes=None,
    ):
        wins = [1.0 if ep.get("won", False) else 0.0 for ep in episodes]
        scores = [ep.get("score", 0) for ep in episodes]
        lengths = [ep.get("length", len(ep.get("actions", []))) for ep in episodes]
        rewards = [ep.get("totalReward", 0.0) for ep in episodes]
        bones = [ep.get("bonesCollected", 0) for ep in episodes]
        totalBones = [ep.get("totalBones", 5) for ep in episodes]
        revisits = [ep.get("revisits", 0) for ep in episodes]
        uniqueCells = [ep.get("uniqueCells", 1) for ep in episodes]
        rehearsalCount = (
            int(rehearsalEpisodes)
            if rehearsalEpisodes is not None
            else sum(1 for ep in episodes if ep.get("rehearsal", False))
        )
        sampledMapNames = sorted({str(ep.get("sourceMap", "")) for ep in episodes if ep.get("sourceMap")})
        boneRate = float(sum(bones)) / float(max(1, sum(totalBones))) if episodes else 0.0
        revisitRates = [rev / float(max(1, length)) for rev, length in zip(revisits, lengths)]

        entCoef = (
            float(entropyCoef)
            if entropyCoef is not None
            else float(getattr(updateMetrics, "entropyCoef", 0.0))
        )

        record = {
            "update": int(updateNumber),
            "numMaps": int(numMaps),
            "mapsSampled": len(sampledMapNames) if sampledMapNames else len(episodes),
            "episodesCompleted": int(totalEpisodes),
            "batchEpisodes": len(episodes),
            "rehearsalEpisodes": int(rehearsalCount),
            "winRate": float(np.mean(wins)) if wins else 0.0,
            "meanScore": float(np.mean(scores)) if scores else 0.0,
            "meanSteps": float(np.mean(lengths)) if lengths else 0.0,
            "meanEpisodeLength": float(np.mean(lengths)) if lengths else 0.0,
            "meanReward": float(np.mean(rewards)) if rewards else 0.0,
            "meanBonesCollected": float(np.mean(bones)) if bones else 0.0,
            "boneCollectionRate": float(boneRate),
            "meanRevisits": float(np.mean(revisits)) if revisits else 0.0,
            "revisitRate": float(np.mean(revisitRates)) if revisitRates else 0.0,
            "meanUniqueSquares": float(np.mean(uniqueCells)) if uniqueCells else 0.0,
            "policyLoss": float(getattr(updateMetrics, "policyLoss", 0.0)),
            "valueLoss": float(getattr(updateMetrics, "valueLoss", 0.0)),
            "entropy": float(getattr(updateMetrics, "entropy", 0.0)),
            "entropyCoef": float(entCoef),
            "approxKl": float(getattr(updateMetrics, "approxKl", 0.0)),
            "loss": float(updateMetrics),
            "checkpointSaved": bool(checkpointSaved),
            "bestCheckpointSaved": bool(bestCheckpointSaved),
        }
        if evalMetrics is not None:
            record["evalWinRate"] = float(evalMetrics.get("winRate", 0.0))
            record["evalMeanScore"] = float(evalMetrics.get("meanScore", 0.0))
            record["evalBonesCollected"] = float(evalMetrics.get("bonesCollected", 0.0))
            record["evalBoneRate"] = float(evalMetrics.get("boneCollectionRate", 0.0))
            record["evalRevisitRate"] = float(evalMetrics.get("revisitRate", 0.0))
        if retentionMetrics is not None:
            record["retentionWinRate"] = float(retentionMetrics.get("winRate", 0.0))
            record["retentionMeanScore"] = float(retentionMetrics.get("meanScore", 0.0))

        self.history.append(record)
        if len(self.history) > 500:
            self.history.pop(0)
        return record

    def formatProgress(self, record):
        ckptStr = "best+saved" if record.get("bestCheckpointSaved") else ("saved" if record.get("checkpointSaved") else "skip")
        evalPart = ""
        if "evalWinRate" in record:
            evalPart = (
                f" | evalWin {record['evalWinRate']:.0%} "
                f"(score {record['evalMeanScore']:.1f}, bones {record.get('evalBonesCollected', 0.0):.1f})"
            )
        if "retentionWinRate" in record:
            evalPart += f" | retWin {record['retentionWinRate']:.0%}"
        return (
            f"Update {record['update']:03d} | maps {record['mapsSampled']}/{record['numMaps']} | "
            f"eps {record['episodesCompleted']} (reh {record['rehearsalEpisodes']}) | "
            f"win {record['winRate']:.0%} | score {record['meanScore']:.1f} | "
            f"steps {record['meanSteps']:.1f} | bones {record['meanBonesCollected']:.2f} ({record['boneCollectionRate']:.0%}) | "
            f"rev {record['meanRevisits']:.1f} ({record['revisitRate']:.0%}) | uniq {record['meanUniqueSquares']:.1f} | "
            f"rew {record['meanReward']:.2f} | pLoss {record['policyLoss']:.3f} | vLoss {record['valueLoss']:.3f} | "
            f"ent {record['entropy']:.3f} (c={record['entropyCoef']:.4f}){evalPart} | ckpt: {ckptStr}"
        )
