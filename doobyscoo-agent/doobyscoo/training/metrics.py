import numpy as np

SIMPLE_TITLES = (
    "Training Started",
    "Exploring New Area",
    "Dead End Found",
    "Better Route Found",
    "Bone Collected",
    "Bone Collection Improved",
    "Collecting Bones",
    "Avoided Previous Mistake",
    "Reduced Revisits",
    "Learning from Failure",
    "New Best Score",
    "Update RL Policy",
    "Training Complete",
)


def trajectorySimilarity(actionsA, actionsB):
    """Compute similarity in [0.0, 1.0] between two action sequences."""
    seqA = [int(a) for a in (actionsA or [])]
    seqB = [int(b) for b in (actionsB or [])]
    if not seqA and not seqB:
        return 1.0
    if not seqA or not seqB:
        return 0.0
    if seqA == seqB:
        return 1.0
    maxLen = max(len(seqA), len(seqB))
    minLen = min(len(seqA), len(seqB))
    alignedMatches = sum(1 for i in range(minLen) if seqA[i] == seqB[i])
    alignedScore = float(alignedMatches) / float(maxLen)

    bigramsA = {(seqA[i], seqA[i + 1]) for i in range(len(seqA) - 1)} or {("single", seqA[0])}
    bigramsB = {(seqB[i], seqB[i + 1]) for i in range(len(seqB) - 1)} or {("single", seqB[0])}
    union = len(bigramsA | bigramsB)
    jaccard = float(len(bigramsA & bigramsB)) / float(max(1, union))
    return round(0.6 * alignedScore + 0.4 * jaccard, 4)


def measureRouteDiversity(trajectories):
    """Measure route diversity, duplicate trajectories, and pairwise similarity."""
    seqs = [tuple(int(a) for a in (t.get("actions", t) if isinstance(t, dict) else t)) for t in (trajectories or [])]
    seqs = [s for s in seqs if len(s) > 0]
    total = len(seqs)
    if total == 0:
        return {
            "totalTrajectories": 0,
            "distinctTrajectories": 0,
            "duplicateTrajectories": 0,
            "meanSimilarity": 0.0,
            "diversityScore": 0.0,
        }
    distinct = len(set(seqs))
    duplicates = total - distinct
    if total == 1:
        return {
            "totalTrajectories": 1,
            "distinctTrajectories": 1,
            "duplicateTrajectories": 0,
            "meanSimilarity": 1.0,
            "diversityScore": 0.0,
        }
    sims = []
    for i in range(total):
        for j in range(i + 1, total):
            sims.append(trajectorySimilarity(seqs[i], seqs[j]))
    meanSim = float(np.mean(sims)) if sims else 0.0
    return {
        "totalTrajectories": total,
        "distinctTrajectories": distinct,
        "duplicateTrajectories": duplicates,
        "meanSimilarity": round(meanSim, 4),
        "diversityScore": round(1.0 - meanSim, 4),
    }


class MazeOptimizationTracker:
    """Tracks per-maze best solutions, route diversity, dead-end discovery,
    oscillation/mistake reduction, and official score improvements across attempts.
    """

    def __init__(self, initialState=None):
        self.mazes = {}
        if isinstance(initialState, dict):
            for mapName, data in initialState.items():
                if isinstance(data, dict):
                    self.mazes[str(mapName)] = self._normalizeEntry(data)

    def _normalizeEntry(self, data=None):
        data = data or {}
        return {
            "bestScore": data.get("bestScore", None),
            "bestTrainingScore": data.get("bestTrainingScore", data.get("bestScore", None)),
            "bestOfficialScore": data.get("bestOfficialScore", None),
            "firstSolvedScore": data.get("firstSolvedScore", None),
            "bestTrajectory": list(data.get("bestTrajectory") or []),
            "bestPositions": list(data.get("bestPositions") or []),
            "bestSteps": data.get("bestSteps", None),
            "bonesCollected": int(data.get("bonesCollected", 0)),
            "maxBonesCollected": int(data.get("maxBonesCollected", 0)),
            "bestRevisits": data.get("bestRevisits", None),
            "bestMistakes": data.get("bestMistakes", None),
            "maxUniqueCells": int(data.get("maxUniqueCells", 0)),
            "totalAttempts": int(data.get("totalAttempts", 0)),
            "successfulAttempts": int(data.get("successfulAttempts", 0)),
            "failedAttempts": int(data.get("failedAttempts", 0)),
            "scoreLimitFailures": int(data.get("scoreLimitFailures", 0)),
            "fiveBoneCompletions": int(data.get("fiveBoneCompletions", 0)),
            "distinctSuccessfulTrajectories": int(data.get("distinctSuccessfulTrajectories", 0)),
            "duplicateSuccessfulTrajectories": int(data.get("duplicateSuccessfulTrajectories", 0)),
            "successfulTrajectorySet": [list(t) for t in (data.get("successfulTrajectorySet") or [])],
            "recentTrajectories": [list(t) for t in (data.get("recentTrajectories") or [])][-20:],
            "attemptScores": list(data.get("attemptScores") or [])[-50:],
            "attemptSteps": list(data.get("attemptSteps") or [])[-50:],
            "attemptRevisits": list(data.get("attemptRevisits") or [])[-50:],
            "scoreImprovements": list(data.get("scoreImprovements") or []),
            "attemptsBeforeImprovement": list(data.get("attemptsBeforeImprovement") or []),
            "attemptsSinceLastBest": int(data.get("attemptsSinceLastBest", 0)),
            "edgesSeen": [list(e) for e in (data.get("edgesSeen") or [])][-200:],
            "deadEndEdges": [list(e) for e in (data.get("deadEndEdges") or [])][-200:],
            "loopEdges": [list(e) for e in (data.get("loopEdges") or [])][-200:],
            "visitedCellsUnion": [list(c) for c in (data.get("visitedCellsUnion") or [])][-200:],
            "knownDeadEndsUnion": [list(c) for c in (data.get("knownDeadEndsUnion") or [])][-200:],
            "totalDeadEndsEncountered": int(data.get("totalDeadEndsEncountered", 0)),
            "totalRepeatedMistakes": int(data.get("totalRepeatedMistakes", 0)),
            "totalOscillationsDetected": int(data.get("totalOscillationsDetected", 0)),
            "totalAvoidedMistakes": int(data.get("totalAvoidedMistakes", 0)),
            "totalNewAreasExplored": int(data.get("totalNewAreasExplored", 0)),
        }

    def recordAttempt(self, mapName, episode):
        key = str(mapName or episode.get("sourceMap", "maze"))
        entry = self.mazes.setdefault(key, self._normalizeEntry())

        won = bool(episode.get("won", False))
        scoreLimitExceeded = bool(episode.get("scoreLimitExceeded", False))
        failed = bool(episode.get("failed", not won))
        trainingScore = int(episode.get("trainingScore", episode.get("score", 0)))
        officialScore = int(episode.get("officialScore", episode.get("score", 0)))
        actions = [int(a) for a in episode.get("actions", [])]
        positions = list(episode.get("positionHistory") or [])
        steps = int(episode.get("length", len(actions)))
        bones = int(episode.get("bonesCollected", 0))
        revisits = int(episode.get("revisits", 0))
        uniqueCells = int(episode.get("uniqueCells", len(episode.get("visitedCells") or [])))
        deadEndsEncountered = int(episode.get("deadEndsEncountered", 0))
        repeatedMistakes = int(episode.get("repeatedMistakes", 0))
        oscillationsDetected = int(episode.get("oscillationsDetected", 0))
        avoidedMistakes = int(episode.get("avoidedPreviousMistakes", 0))

        entry["totalAttempts"] += 1
        entry["attemptsSinceLastBest"] += 1
        entry["attemptScores"].append(trainingScore)
        entry["attemptSteps"].append(steps)
        entry["attemptRevisits"].append(revisits)
        if len(entry["attemptScores"]) > 50:
            entry["attemptScores"] = entry["attemptScores"][-50:]
            entry["attemptSteps"] = entry["attemptSteps"][-50:]
            entry["attemptRevisits"] = entry["attemptRevisits"][-50:]

        if actions:
            entry["recentTrajectories"].append(actions)
            if len(entry["recentTrajectories"]) > 20:
                entry["recentTrajectories"] = entry["recentTrajectories"][-20:]

        edges = episode.get("edgesTraversed") or []
        seenSet = {tuple(e) for e in entry["edgesSeen"]}
        for e in edges:
            seenSet.add(tuple(e))
        entry["edgesSeen"] = [list(e) for e in sorted(seenSet)][-200:]

        deadEdgeSet = {tuple(e) for e in entry["deadEndEdges"]}
        for e in episode.get("deadEndEdges") or []:
            deadEdgeSet.add(tuple(e))
        entry["deadEndEdges"] = [list(e) for e in sorted(deadEdgeSet)][-200:]

        loopEdgeSet = {tuple(e) for e in entry["loopEdges"]}
        for e in episode.get("loopEdges") or []:
            loopEdgeSet.add(tuple(e))
        entry["loopEdges"] = [list(e) for e in sorted(loopEdgeSet)][-200:]

        priorVisitedUnion = {tuple(c) for c in entry["visitedCellsUnion"]}
        epVisited = {tuple(c) for c in (episode.get("visitedCells") or [])}
        newlyDiscoveredCells = len(epVisited - priorVisitedUnion) if epVisited else int(episode.get("newAreasExplored", 0))
        priorVisitedUnion.update(epVisited)
        entry["visitedCellsUnion"] = [list(c) for c in sorted(priorVisitedUnion)][-200:]

        priorDeadUnion = {tuple(c) for c in entry["knownDeadEndsUnion"]}
        epDeadEnds = {tuple(c) for c in (episode.get("knownDeadEnds") or [])}
        newlyDiscoveredDeadEnds = len(epDeadEnds - priorDeadUnion)
        priorDeadUnion.update(epDeadEnds)
        entry["knownDeadEndsUnion"] = [list(c) for c in sorted(priorDeadUnion)][-200:]

        entry["totalDeadEndsEncountered"] += deadEndsEncountered
        entry["totalRepeatedMistakes"] += repeatedMistakes
        entry["totalOscillationsDetected"] += oscillationsDetected
        entry["totalAvoidedMistakes"] += avoidedMistakes
        entry["totalNewAreasExplored"] += newlyDiscoveredCells

        prevMaxUnique = entry["maxUniqueCells"]
        exploredMoreCells = uniqueCells > prevMaxUnique and entry["totalAttempts"] > 1
        if uniqueCells > prevMaxUnique:
            entry["maxUniqueCells"] = uniqueCells

        prevBestMistakes = entry["bestMistakes"]
        reducedMistakes = prevBestMistakes is not None and repeatedMistakes < prevBestMistakes
        if prevBestMistakes is None or repeatedMistakes < prevBestMistakes:
            entry["bestMistakes"] = repeatedMistakes

        prevMaxBones = entry["maxBonesCollected"]
        improvedBones = bones > prevMaxBones
        if improvedBones:
            entry["maxBonesCollected"] = bones
        if bones >= 5:
            entry["fiveBoneCompletions"] += 1

        prevBestScore = entry["bestScore"]
        prevBestRevisits = entry["bestRevisits"]
        prevBestTrajectory = list(entry["bestTrajectory"])
        improvedScore = False
        isNewDistinctRoute = False
        isBetterRoute = False
        scoreDelta = 0
        reducedRevisits = False

        if won:
            entry["successfulAttempts"] += 1
            knownSet = {tuple(t) for t in entry["successfulTrajectorySet"]}
            if tuple(actions) not in knownSet:
                isNewDistinctRoute = True
                entry["successfulTrajectorySet"].append(actions)
                entry["distinctSuccessfulTrajectories"] = len(entry["successfulTrajectorySet"])
            else:
                entry["duplicateSuccessfulTrajectories"] += 1

            if entry["firstSolvedScore"] is None:
                entry["firstSolvedScore"] = trainingScore

            if prevBestRevisits is None or revisits < prevBestRevisits:
                if prevBestRevisits is not None and revisits < prevBestRevisits:
                    reducedRevisits = True
                entry["bestRevisits"] = revisits

            if prevBestScore is None or trainingScore < prevBestScore:
                improvedScore = True
                if prevBestScore is not None:
                    scoreDelta = int(prevBestScore - trainingScore)
                    entry["scoreImprovements"].append(scoreDelta)
                    entry["attemptsBeforeImprovement"].append(entry["attemptsSinceLastBest"])
                    if prevBestTrajectory and actions != prevBestTrajectory:
                        isBetterRoute = True
                entry["attemptsSinceLastBest"] = 0
                entry["bestScore"] = trainingScore
                entry["bestTrainingScore"] = trainingScore
                entry["bestOfficialScore"] = officialScore
                entry["bestTrajectory"] = list(actions)
                entry["bestPositions"] = list(positions)
                entry["bestSteps"] = steps
                entry["bonesCollected"] = bones
            elif entry["bestOfficialScore"] is None or officialScore < entry["bestOfficialScore"]:
                entry["bestOfficialScore"] = officialScore
        else:
            entry["failedAttempts"] += 1
            if scoreLimitExceeded:
                entry["scoreLimitFailures"] += 1

        return {
            "mapName": key,
            "attemptNumber": entry["totalAttempts"],
            "won": won,
            "failed": failed,
            "scoreLimitExceeded": scoreLimitExceeded,
            "trainingScore": trainingScore,
            "officialScore": officialScore,
            "steps": steps,
            "bonesCollected": bones,
            "revisits": revisits,
            "uniqueCells": uniqueCells,
            "newAreasExplored": newlyDiscoveredCells,
            "exploredMoreCells": exploredMoreCells,
            "deadEndsEncountered": deadEndsEncountered,
            "newlyDiscoveredDeadEnds": newlyDiscoveredDeadEnds,
            "repeatedMistakes": repeatedMistakes,
            "oscillationsDetected": oscillationsDetected,
            "avoidedPreviousMistakes": avoidedMistakes,
            "reducedMistakes": reducedMistakes,
            "improvedScore": improvedScore,
            "firstSolve": bool(won and prevBestScore is None),
            "previousBestScore": prevBestScore,
            "newBestScore": entry["bestScore"],
            "scoreImprovement": scoreDelta,
            "isNewDistinctRoute": isNewDistinctRoute,
            "isBetterRoute": isBetterRoute,
            "improvedBones": improvedBones,
            "previousMaxBones": prevMaxBones,
            "newMaxBones": entry["maxBonesCollected"],
            "reducedRevisits": reducedRevisits,
            "previousBestRevisits": prevBestRevisits,
            "newBestRevisits": entry["bestRevisits"],
            "distinctSuccessfulTrajectories": entry["distinctSuccessfulTrajectories"],
        }

    def priorEdgesByMap(self):
        return {
            mapName: {tuple(e) for e in entry.get("edgesSeen", [])}
            for mapName, entry in self.mazes.items()
        }

    def deadEndEdgesByMap(self):
        return {
            mapName: {tuple(e) for e in entry.get("deadEndEdges", [])}
            for mapName, entry in self.mazes.items()
        }

    def loopEdgesByMap(self):
        return {
            mapName: {tuple(e) for e in entry.get("loopEdges", [])}
            for mapName, entry in self.mazes.items()
        }

    def bestEdgesByMap(self):
        out = {}
        for mapName, entry in self.mazes.items():
            positions = entry.get("bestPositions") or []
            actions = entry.get("bestTrajectory") or []
            edges = set()
            for idx, act in enumerate(actions):
                if idx < len(positions):
                    pos = positions[idx]
                    edges.add((int(pos[0]), int(pos[1]), int(act)))
            if edges:
                out[mapName] = edges
        return out

    def getMazeSummary(self, mapName):
        entry = self.mazes.get(str(mapName))
        if entry is None:
            return None
        div = measureRouteDiversity(entry["recentTrajectories"])
        totalImp = 0
        if entry["firstSolvedScore"] is not None and entry["bestScore"] is not None:
            totalImp = int(entry["firstSolvedScore"] - entry["bestScore"])
        avgAttempts = (
            float(np.mean(entry["attemptsBeforeImprovement"]))
            if entry["attemptsBeforeImprovement"]
            else 0.0
        )
        attempts = max(1, entry["totalAttempts"])
        avgSteps = float(np.mean(entry["attemptSteps"])) if entry["attemptSteps"] else float(entry["bestSteps"] or 0)
        avgRevisits = float(np.mean(entry["attemptRevisits"])) if entry["attemptRevisits"] else 0.0
        revisitRate = avgRevisits / max(1.0, avgSteps)
        return {
            "bestScore": entry["bestScore"],
            "bestTrainingScore": entry["bestTrainingScore"],
            "bestOfficialScore": entry["bestOfficialScore"],
            "firstSolvedScore": entry["firstSolvedScore"],
            "bestTrajectory": list(entry["bestTrajectory"]),
            "bestSteps": entry["bestSteps"],
            "averageSteps": round(avgSteps, 2),
            "bonesCollected": entry["bonesCollected"],
            "maxBonesCollected": entry["maxBonesCollected"],
            "totalAttempts": entry["totalAttempts"],
            "successfulAttempts": entry["successfulAttempts"],
            "failedAttempts": entry["failedAttempts"],
            "mazeCompletionRate": round(float(entry["successfulAttempts"]) / float(attempts), 4),
            "scoreLimitFailures": entry["scoreLimitFailures"],
            "fiveBoneCompletions": entry["fiveBoneCompletions"],
            "distinctSuccessfulTrajectories": entry["distinctSuccessfulTrajectories"],
            "duplicateSuccessfulTrajectories": entry["duplicateSuccessfulTrajectories"],
            "distinctRoutes": div["distinctTrajectories"],
            "totalDeadEndsEncountered": entry["totalDeadEndsEncountered"],
            "totalRepeatedMistakes": entry["totalRepeatedMistakes"],
            "repeatedMoves": entry["totalRepeatedMistakes"],
            "loopsDetected": entry["totalOscillationsDetected"],
            "revisitRate": round(revisitRate, 4),
            "totalAvoidedMistakes": entry["totalAvoidedMistakes"],
            "totalNewAreasExplored": entry["totalNewAreasExplored"],
            "scoreImprovement": totalImp,
            "scoreImprovements": list(entry["scoreImprovements"]),
            "attemptsBeforeImprovement": list(entry["attemptsBeforeImprovement"]),
            "averageAttemptsBeforeImprovement": round(avgAttempts, 2),
            "routeDiversity": div,
            "attemptScores": list(entry["attemptScores"]),
        }

    def globalSummary(self):
        if not self.mazes:
            return {
                "trackedMazes": 0,
                "totalAttempts": 0,
                "attempts": 0,
                "averageSteps": 0.0,
                "bestScore": None,
                "bonesCollected": 0,
                "mazeCompletionRate": 0.0,
                "repeatedMoves": 0,
                "revisitRate": 0.0,
                "loopsDetected": 0,
                "distinctSuccessfulTrajectories": 0,
                "distinctRoutes": 0,
                "totalDeadEndsEncountered": 0,
                "totalRepeatedMistakes": 0,
                "totalAvoidedMistakes": 0,
                "totalNewAreasExplored": 0,
                "averageAttemptsBeforeImprovement": 0.0,
                "meanScoreImprovement": 0.0,
            }
        summaries = [self.getMazeSummary(k) for k in self.mazes]
        allWait = [x for s in summaries for x in s["attemptsBeforeImprovement"]]
        allImp = [s["scoreImprovement"] for s in summaries if s["firstSolvedScore"] is not None]
        totalAttempts = sum(s["totalAttempts"] for s in summaries)
        succAttempts = sum(s["successfulAttempts"] for s in summaries)
        bestScores = [s["bestOfficialScore"] for s in summaries if s["bestOfficialScore"] is not None]
        return {
            "trackedMazes": len(summaries),
            "totalAttempts": totalAttempts,
            "attempts": totalAttempts,
            "successfulAttempts": succAttempts,
            "failedAttempts": sum(s["failedAttempts"] for s in summaries),
            "mazeCompletionRate": round(float(succAttempts) / float(max(1, totalAttempts)), 4),
            "averageSteps": round(float(np.mean([s["averageSteps"] for s in summaries])), 2),
            "bestScore": min(bestScores) if bestScores else None,
            "bonesCollected": sum(s["maxBonesCollected"] for s in summaries),
            "repeatedMoves": sum(s["totalRepeatedMistakes"] for s in summaries),
            "revisitRate": round(float(np.mean([s["revisitRate"] for s in summaries])), 4),
            "loopsDetected": sum(s["loopsDetected"] for s in summaries),
            "scoreLimitFailures": sum(s["scoreLimitFailures"] for s in summaries),
            "distinctSuccessfulTrajectories": sum(s["distinctSuccessfulTrajectories"] for s in summaries),
            "distinctRoutes": sum(s["distinctRoutes"] for s in summaries),
            "totalDeadEndsEncountered": sum(s["totalDeadEndsEncountered"] for s in summaries),
            "totalRepeatedMistakes": sum(s["totalRepeatedMistakes"] for s in summaries),
            "totalAvoidedMistakes": sum(s["totalAvoidedMistakes"] for s in summaries),
            "totalNewAreasExplored": sum(s["totalNewAreasExplored"] for s in summaries),
            "averageAttemptsBeforeImprovement": round(float(np.mean(allWait)), 2) if allWait else 0.0,
            "meanScoreImprovement": round(float(np.mean(allImp)), 2) if allImp else 0.0,
        }

    def toDict(self):
        return {k: self._normalizeEntry(v) for k, v in self.mazes.items()}


class LearningProgressReporter:
    """Generates short, simple, evidence-backed learning progress updates."""

    def __init__(self):
        self.events = []
        self._lastSignatureByTitle = {}
        self._baselineMetrics = None

    def _emit(self, title, message, category="progress", details=None):
        if title not in SIMPLE_TITLES:
            raise ValueError(f"Unsupported progress title: {title}")
        sig = f"{title}|{message}"
        if self._lastSignatureByTitle.get(title) == sig:
            return None
        self._lastSignatureByTitle[title] = sig
        event = {
            "title": title,
            "message": message,
            "formatted": f"{title} — {message}",
            "category": category,
            "details": details or {},
        }
        self.events.append(event)
        if len(self.events) > 200:
            self.events.pop(0)
        return event

    def recordTrainingStarted(self, numMaps, maxScoreLimit=100):
        return self._emit(
            "Training Started",
            f"Training across {int(numMaps)} mazes (max score limit: {int(maxScoreLimit)}).",
            category="lifecycle",
            details={"numMaps": int(numMaps), "maxScoreLimit": int(maxScoreLimit)},
        )

    def recordTrainingComplete(self, totalUpdates, totalEpisodes, bestWinRate, bestScore):
        scoreTxt = f"{bestScore:.1f}" if isinstance(bestScore, (int, float)) else "N/A"
        return self._emit(
            "Training Complete",
            f"Completed {int(totalUpdates)} updates ({int(totalEpisodes)} episodes, best win rate {bestWinRate:.0%}, best score {scoreTxt}).",
            category="lifecycle",
            details={
                "updates": int(totalUpdates),
                "episodes": int(totalEpisodes),
                "bestWinRate": float(bestWinRate),
                "bestScore": bestScore,
            },
        )

    def recordAttemptOutcome(self, attemptOutcome, totalBones=5):
        emitted = []
        mapName = attemptOutcome["mapName"]
        attemptNum = attemptOutcome["attemptNumber"]
        bones = attemptOutcome["bonesCollected"]
        steps = attemptOutcome["steps"]
        tScore = attemptOutcome["trainingScore"]

        if attemptOutcome.get("failed"):
            if attemptOutcome.get("scoreLimitExceeded"):
                ev = self._emit(
                    "Learning from Failure",
                    f"Attempt #{attemptNum} on {mapName} exceeded score limit (score {tScore} > 100, {bones}/{totalBones} Bones); trajectory recorded for next policy update.",
                    category="failure",
                    details=attemptOutcome,
                )
                if ev:
                    emitted.append(ev)
                return emitted

        if (attemptOutcome.get("exploredMoreCells") or attemptOutcome.get("exploredNewArea")) and attemptOutcome.get("newAreasExplored", 0) > 0:
            evExp = self._emit(
                "Exploring New Area",
                f"Explored {attemptOutcome['newAreasExplored']} new cell(s) on {mapName} (attempt #{attemptNum}).",
                category="exploration",
                details=attemptOutcome,
            )
            if evExp:
                emitted.append(evExp)

        deadCount = int(attemptOutcome.get("newlyDiscoveredDeadEnds", attemptOutcome.get("deadEndsEncountered", 0)))
        if deadCount > 0 and (attemptOutcome.get("newlyDiscoveredDeadEnds", 0) > 0 or not attemptOutcome.get("won", False)):
            evDead = self._emit(
                "Dead End Found",
                f"Identified {deadCount} dead-end cell(s) on {mapName} (attempt #{attemptNum}).",
                category="navigation",
                details=attemptOutcome,
            )
            if evDead:
                emitted.append(evDead)

        if attemptOutcome.get("avoidedPreviousMistakes", 0) > 0 and attemptOutcome.get("reducedMistakes", True):
            evMistake = self._emit(
                "Avoided Previous Mistake",
                f"Bypassed {attemptOutcome['avoidedPreviousMistakes']} known dead-end/loop branch(es) on {mapName} (attempt #{attemptNum}).",
                category="mistakes",
                details=attemptOutcome,
            )
            if evMistake:
                emitted.append(evMistake)

        if attemptOutcome.get("failed"):
            return emitted

        if attemptOutcome.get("improvedScore") and attemptOutcome.get("previousBestScore") is not None:
            prevScore = attemptOutcome["previousBestScore"]
            newScore = attemptOutcome["newBestScore"]
            ev = self._emit(
                "New Best Score",
                f"{mapName}: score improved from {prevScore} to {newScore} ({bones}/{totalBones} Bones, {steps} steps, attempt #{attemptNum}).",
                category="best_score",
                details=attemptOutcome,
            )
            if ev:
                emitted.append(ev)
            if attemptOutcome.get("isBetterRoute"):
                evRoute = self._emit(
                    "Better Route Found",
                    f"Alternative route on {mapName} lowered score from {prevScore} to {newScore} ({steps} steps, {bones}/{totalBones} Bones).",
                    category="route",
                    details=attemptOutcome,
                )
                if evRoute:
                    emitted.append(evRoute)
        elif attemptOutcome.get("firstSolve"):
            ev = self._emit(
                "New Best Score",
                f"First solution on {mapName}: score {tScore} ({bones}/{totalBones} Bones, {steps} steps, attempt #{attemptNum}).",
                category="best_score",
                details=attemptOutcome,
            )
            if ev:
                emitted.append(ev)

        if attemptOutcome.get("improvedBones") and bones > 0:
            prevBones = attemptOutcome.get("previousMaxBones", 0)
            title = "Collecting Bones" if bones >= 5 else "Bone Collection Improved"
            evBone = self._emit(
                title,
                f"Collected {bones}/{totalBones} Bones on {mapName} (up from {prevBones}/{totalBones}, attempt #{attemptNum}).",
                category="bones",
                details=attemptOutcome,
            )
            if evBone:
                emitted.append(evBone)

        if attemptOutcome.get("reducedRevisits"):
            prevRev = attemptOutcome.get("previousBestRevisits")
            newRev = attemptOutcome.get("newBestRevisits")
            evRev = self._emit(
                "Reduced Revisits",
                f"Revisits on {mapName} dropped from {prevRev} to {newRev} (attempt #{attemptNum}).",
                category="revisits",
                details=attemptOutcome,
            )
            if evRev:
                emitted.append(evRev)

        return emitted

    def recordPolicyUpdate(self, updateNumber, episodes, evalMetrics=None):
        emitted = []
        failedEps = [ep for ep in episodes if ep.get("failed", False) or ep.get("scoreLimitExceeded", False)]
        scoreLimitEps = [ep for ep in episodes if ep.get("scoreLimitExceeded", False)]
        if failedEps:
            reason = (
                f"{len(scoreLimitEps)} score-limit (>100)"
                if scoreLimitEps
                else f"{len(failedEps)} failed"
            )
            evFail = self._emit(
                "Learning from Failure",
                f"Update #{int(updateNumber)} trained on {reason} attempt(s) to avoid high-score loops.",
                category="failure",
                details={"update": int(updateNumber), "failedCount": len(failedEps), "scoreLimitCount": len(scoreLimitEps)},
            )
            if evFail:
                emitted.append(evFail)

        winRate = float(evalMetrics["winRate"]) if evalMetrics else float(np.mean([1.0 if e.get("won") else 0.0 for e in episodes]))
        meanScore = float(evalMetrics.get("meanTrainingScore", evalMetrics["meanScore"])) if evalMetrics else float(np.mean([e.get("trainingScore", e.get("score", 0)) for e in episodes]))
        meanBones = float(evalMetrics["bonesCollected"]) if evalMetrics else float(np.mean([e.get("bonesCollected", 0) for e in episodes]))
        revisitRate = float(evalMetrics["revisitRate"]) if evalMetrics else float(np.mean([e.get("revisitRate", 0.0) for e in episodes]))

        currentSnap = {
            "winRate": winRate,
            "meanScore": meanScore,
            "meanBones": meanBones,
            "revisitRate": revisitRate,
        }

        if self._baselineMetrics is None:
            self._baselineMetrics = currentSnap
            return emitted

        prev = self._baselineMetrics
        improvedWin = winRate > prev["winRate"] + 1e-4
        improvedScore = (winRate >= prev["winRate"] - 0.02) and (meanScore < prev["meanScore"] - 0.5)
        improvedBones = meanBones > prev["meanBones"] + 0.1
        improvedRev = (winRate >= prev["winRate"] - 0.02) and (revisitRate < prev["revisitRate"] - 0.015)

        if improvedWin or improvedScore or improvedBones or improvedRev:
            parts = []
            if improvedWin:
                parts.append(f"win rate {prev['winRate']:.0%} -> {winRate:.0%}")
            if improvedScore:
                parts.append(f"score {prev['meanScore']:.1f} -> {meanScore:.1f}")
            if improvedBones:
                parts.append(f"Bones {prev['meanBones']:.2f} -> {meanBones:.2f}")
            if improvedRev:
                parts.append(f"revisits {prev['revisitRate']:.1%} -> {revisitRate:.1%}")
            evPol = self._emit(
                "Update RL Policy",
                f"Update #{int(updateNumber)} improved navigation ({', '.join(parts)}).",
                category="policy_update",
                details={"update": int(updateNumber), "previous": dict(prev), "current": dict(currentSnap)},
            )
            if evPol:
                emitted.append(evPol)
            self._baselineMetrics = {
                "winRate": max(prev["winRate"], winRate),
                "meanScore": min(prev["meanScore"], meanScore) if winRate >= prev["winRate"] else prev["meanScore"],
                "meanBones": max(prev["meanBones"], meanBones),
                "revisitRate": min(prev["revisitRate"], revisitRate) if winRate >= prev["winRate"] else prev["revisitRate"],
            }

        return emitted

    def recentMessages(self, limit=10):
        return list(self.events[-int(limit) :])


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
        progressEvents=None,
        optimizationSummary=None,
    ):
        wins = [1.0 if ep.get("won", False) else 0.0 for ep in episodes]
        scores = [ep.get("score", 0) for ep in episodes]
        trainingScores = [ep.get("trainingScore", ep.get("score", 0)) for ep in episodes]
        lengths = [ep.get("length", len(ep.get("actions", []))) for ep in episodes]
        rewards = [ep.get("totalReward", 0.0) for ep in episodes]
        bones = [ep.get("bonesCollected", 0) for ep in episodes]
        fiveBones = [1.0 if ep.get("bonesCollected", 0) >= 5 else 0.0 for ep in episodes]
        totalBones = [ep.get("totalBones", 5) for ep in episodes]
        revisits = [ep.get("revisits", 0) for ep in episodes]
        uniqueCells = [ep.get("uniqueCells", 1) for ep in episodes]
        newAreas = [ep.get("newAreasExplored", 0) for ep in episodes]
        deadEnds = [ep.get("deadEndsEncountered", 0) for ep in episodes]
        mistakes = [ep.get("repeatedMistakes", 0) for ep in episodes]
        oscillations = [ep.get("oscillationsDetected", 0) for ep in episodes]
        maxVisits = [ep.get("maxVisitCount", 1) for ep in episodes]
        scoreLimitFails = sum(1 for ep in episodes if ep.get("scoreLimitExceeded", False))
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
            "scoreLimitFailures": int(scoreLimitFails),
            "winRate": float(np.mean(wins)) if wins else 0.0,
            "mazeCompletionRate": float(np.mean(wins)) if wins else 0.0,
            "meanScore": float(np.mean(scores)) if scores else 0.0,
            "bestScore": float(np.min(scores)) if scores else 0.0,
            "meanTrainingScore": float(np.mean(trainingScores)) if trainingScores else 0.0,
            "meanSteps": float(np.mean(lengths)) if lengths else 0.0,
            "averageSteps": float(np.mean(lengths)) if lengths else 0.0,
            "meanEpisodeLength": float(np.mean(lengths)) if lengths else 0.0,
            "meanReward": float(np.mean(rewards)) if rewards else 0.0,
            "meanBonesCollected": float(np.mean(bones)) if bones else 0.0,
            "boneCollectionRate": float(boneRate),
            "fiveBoneCompletionRate": float(np.mean(fiveBones)) if fiveBones else 0.0,
            "meanRevisits": float(np.mean(revisits)) if revisits else 0.0,
            "revisitRate": float(np.mean(revisitRates)) if revisitRates else 0.0,
            "revisitPercentage": float(100.0 * np.mean(revisitRates)) if revisitRates else 0.0,
            "meanUniqueSquares": float(np.mean(uniqueCells)) if uniqueCells else 0.0,
            "meanNewAreasExplored": float(np.mean(newAreas)) if newAreas else 0.0,
            "meanDeadEndsEncountered": float(np.mean(deadEnds)) if deadEnds else 0.0,
            "meanRepeatedMistakes": float(np.mean(mistakes)) if mistakes else 0.0,
            "repeatedMoves": int(sum(mistakes)),
            "loopsDetected": int(sum(oscillations)),
            "maxVisitCount": int(max(maxVisits)) if maxVisits else 0,
            "policyLoss": float(getattr(updateMetrics, "policyLoss", 0.0)),
            "valueLoss": float(getattr(updateMetrics, "valueLoss", 0.0)),
            "entropy": float(getattr(updateMetrics, "entropy", 0.0)),
            "entropyCoef": float(entCoef),
            "approxKl": float(getattr(updateMetrics, "approxKl", 0.0)),
            "loss": float(updateMetrics),
            "checkpointSaved": bool(checkpointSaved),
            "bestCheckpointSaved": bool(bestCheckpointSaved),
            "progressMessages": [e["formatted"] for e in (progressEvents or [])],
        }
        if optimizationSummary is not None:
            record["optimization"] = optimizationSummary
        if evalMetrics is not None:
            record["evalWinRate"] = float(evalMetrics.get("winRate", 0.0))
            record["evalMeanScore"] = float(evalMetrics.get("meanScore", 0.0))
            record["evalMeanTrainingScore"] = float(evalMetrics.get("meanTrainingScore", evalMetrics.get("meanScore", 0.0)))
            record["evalBonesCollected"] = float(evalMetrics.get("bonesCollected", 0.0))
            record["evalBoneRate"] = float(evalMetrics.get("boneCollectionRate", 0.0))
            record["evalFiveBoneRate"] = float(evalMetrics.get("fiveBoneCompletionRate", 0.0))
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
                f"(score {record['evalMeanScore']:.1f}, tScore {record.get('evalMeanTrainingScore', record['evalMeanScore']):.1f}, "
                f"bones {record.get('evalBonesCollected', 0.0):.1f})"
            )
        if "retentionWinRate" in record:
            evalPart += f" | retWin {record['retentionWinRate']:.0%}"
        return (
            f"Update {record['update']:03d} | maps {record['mapsSampled']}/{record['numMaps']} | "
            f"eps {record['episodesCompleted']} (reh {record['rehearsalEpisodes']}, fail>100: {record.get('scoreLimitFailures', 0)}) | "
            f"win {record['winRate']:.0%} | tScore {record['meanTrainingScore']:.1f} (off {record['meanScore']:.1f}) | "
            f"steps {record['meanSteps']:.1f} | bones {record['meanBonesCollected']:.2f} ({record['boneCollectionRate']:.0%}) | "
            f"rev {record['meanRevisits']:.1f} ({record['revisitRate']:.0%}) | uniq {record['meanUniqueSquares']:.1f} | "
            f"rew {record['meanReward']:.2f} | ent {record['entropy']:.3f}{evalPart} | ckpt: {ckptStr}"
        )

