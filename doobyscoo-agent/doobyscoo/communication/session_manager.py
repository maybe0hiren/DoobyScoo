import threading
import uuid
from pathlib import Path
from ..agent.network import RecurrentPolicy, chooseAction
from ..environment.maze_environment import MazeEnvironment, ACTION_NAMES
from ..storage.checkpoint import getCheckpointMetadata, loadCheckpointFull, saveCheckpoint
from ..storage.experience_store import ExperienceStore
from ..training.trainer import continualLearnStep
from .protocol import actionToName, parseActionValue, validateObservationInput


class EpisodeSession:
    def __init__(self, sessionId, mazeData, model, maxSteps=300, mode="training", deterministic=False, collectExperience=True, isTestMap=False):
        self.sessionId = str(sessionId)
        self.mazeData = mazeData
        self.environment = MazeEnvironment(mazeData, maxSteps=maxSteps)
        self.memory = model.initialState()
        self.initialState = self.memory.detach()
        self.mode = str(mode)
        self.deterministic = bool(deterministic)
        self.collectExperience = bool(collectExperience)
        self.isTestMap = bool(isTestMap)
        self.pendingAction = None
        self.completed = False
        self.trajectory = {
            "observations": [],
            "actions": [],
            "logProbs": [],
            "values": [],
            "rewards": [],
            "rawRewards": [],
            "initialState": self.initialState,
        }

    def reset(self, model):
        self.environment.reset()
        self.memory = model.initialState()
        self.initialState = self.memory.detach()
        self.pendingAction = None
        self.completed = False
        self.trajectory = {
            "observations": [],
            "actions": [],
            "logProbs": [],
            "values": [],
            "rewards": [],
            "rawRewards": [],
            "initialState": self.initialState,
        }


class GameService:
    def __init__(
        self,
        checkpoint="models/dog.pt",
        mapsFolder="maps/played",
        trainMapsFolder="maps/train",
        validationFolder="maps/validation",
        maxSteps=300,
        learnUpdates=3,
    ):
        self.checkpoint = Path(checkpoint)
        self.mapsFolder = Path(mapsFolder)
        self.mapsFolder.mkdir(parents=True, exist_ok=True)
        self.trainMapsFolder = Path(trainMapsFolder) if trainMapsFolder else None
        self.validationFolder = Path(validationFolder) if validationFolder else None
        self.maxSteps = int(maxSteps)
        self.learnUpdates = int(learnUpdates)

        self.model = RecurrentPolicy()
        self.meta = loadCheckpointFull(self.checkpoint, self.model)
        if not self.checkpoint.exists():
            saveCheckpoint(self.checkpoint, self.model, updates=0, bestRate=0.0, version=1)
            self.meta = loadCheckpointFull(self.checkpoint, self.model)
        self.model.eval()

        self.experienceStore = ExperienceStore(
            playedMapsFolder=self.mapsFolder,
            excludedFolders=["maps/test", self.validationFolder] if self.validationFolder else ["maps/test"],
        )

        self.lock = threading.RLock()
        self.learning = False
        self.lastTrainingMetrics = {}
        self.sessions = {}
        self.defaultSessionId = "default"
        self.environment = None
        self.memory = None
        self.mazeData = None
        self.episodeIndex = 0

    def _syncLegacyAttributes(self, session):
        self.environment = session.environment
        self.memory = session.memory
        self.mazeData = session.mazeData

    def startEpisode(self, payload):
        with self.lock:
            mazeData = payload.get("maze", payload) if isinstance(payload, dict) else payload
            sessionCfg = payload.get("session", {}) if isinstance(payload, dict) else {}
            sessionId = str(payload.get("session_id") or sessionCfg.get("session_id") or uuid.uuid4().hex[:12])
            mode = str(payload.get("mode") or sessionCfg.get("mode") or "training").lower()
            deterministic = bool(payload.get("deterministic", sessionCfg.get("deterministic", mode in ("evaluation", "inference", "eval"))))
            collectExperience = bool(payload.get("collect_experience", sessionCfg.get("collect_experience", mode != "evaluation_no_learn")))
            isTestMap = bool(payload.get("is_test_map", sessionCfg.get("is_test_map", False)))

            session = EpisodeSession(
                sessionId=sessionId,
                mazeData=mazeData,
                model=self.model,
                maxSteps=self.maxSteps,
                mode=mode,
                deterministic=deterministic,
                collectExperience=collectExperience,
                isTestMap=isTestMap,
            )
            self.sessions[sessionId] = session
            self.defaultSessionId = sessionId
            self._syncLegacyAttributes(session)
            state = session.environment.state()
            return {
                "success": True,
                "session_id": sessionId,
                "mode": mode,
                "deterministic": deterministic,
                "collect_experience": collectExperience,
                "model_version": int(self.meta.get("version", 1)),
                "observation": [float(x) for x in session.environment.observe()],
                "available_actions": session.environment.availableActions(),
                "state": state,
                **state,
            }

    def newMap(self, data):
        return self.startEpisode(data)

    def _getSession(self, sessionId=None):
        sid = str(sessionId) if sessionId else self.defaultSessionId
        if sid not in self.sessions:
            raise ValueError("Load a maze or start an episode first")
        return self.sessions[sid]

    def reset(self, sessionId=None):
        with self.lock:
            session = self._getSession(sessionId)
            session.reset(self.model)
            self._syncLegacyAttributes(session)
            state = session.environment.state()
            return {
                "success": True,
                "session_id": session.sessionId,
                "observation": [float(x) for x in session.environment.observe()],
                "available_actions": session.environment.availableActions(),
                "state": state,
                **state,
            }

    def selectAction(self, payload=None):
        payload = payload or {}
        with self.lock:
            sessionId = payload.get("session_id")
            session = self._getSession(sessionId) if (sessionId or self.defaultSessionId in self.sessions) else None

            rawObs = payload.get("observation")
            if rawObs is not None:
                if isinstance(rawObs, dict) and "features" in rawObs:
                    obsVec = validateObservationInput(rawObs["features"])
                elif isinstance(rawObs, (list, tuple)):
                    obsVec = validateObservationInput(rawObs)
                elif session is not None:
                    obsVec = session.environment.observe()
                else:
                    raise ValueError("Invalid observation format")
            elif session is not None:
                obsVec = session.environment.observe()
            else:
                raise ValueError("No active session or observation provided")

            deterministic = bool(payload.get("deterministic", session.deterministic if session else False))
            stateIn = session.memory if session is not None else self.model.initialState()
            actionIdx, logProb, value, nextState = chooseAction(self.model, obsVec, stateIn, deterministic=deterministic)

            if session is not None:
                session.pendingAction = {
                    "observation": obsVec,
                    "action": actionIdx,
                    "logProb": logProb,
                    "value": value,
                    "nextState": nextState,
                }
                if rawObs is not None and not payload.get("defer_state_update", False):
                    session.memory = nextState
                    self._syncLegacyAttributes(session)

            return {
                "success": True,
                "session_id": session.sessionId if session else None,
                "action": actionIdx,
                "action_name": actionToName(actionIdx),
                "log_prob": logProb,
                "value": value,
                "done": bool(session.environment.done) if session else False,
                "available_actions": session.environment.availableActions() if session else list(ACTION_NAMES),
                "model_version": int(self.meta.get("version", 1)),
            }

    def stepEpisode(self, payload=None):
        payload = payload or {}
        with self.lock:
            session = self._getSession(payload.get("session_id"))
            if session.environment.done:
                raise ValueError("Load or reset a maze first")

            deterministic = bool(payload.get("deterministic", session.deterministic))
            obsBefore = session.environment.observe()

            if "action" in payload and payload["action"] is not None:
                requestedAction = parseActionValue(payload["action"])
                if session.pendingAction and session.pendingAction["action"] == requestedAction:
                    actionIdx = requestedAction
                    logProb = session.pendingAction["logProb"]
                    value = session.pendingAction["value"]
                    nextMemory = session.pendingAction["nextState"]
                else:
                    _, logProb, value, nextMemory = chooseAction(self.model, obsBefore, session.memory, deterministic=deterministic)
                    actionIdx = requestedAction
            elif session.pendingAction is not None:
                actionIdx = session.pendingAction["action"]
                logProb = session.pendingAction["logProb"]
                value = session.pendingAction["value"]
                nextMemory = session.pendingAction["nextState"]
            else:
                actionIdx, logProb, value, nextMemory = chooseAction(self.model, obsBefore, session.memory, deterministic=deterministic)

            session.pendingAction = None
            session.memory = nextMemory
            nextObs, reward, done, info = session.environment.step(actionIdx)

            discrepancy = None
            reportedPos = payload.get("reported_position")
            if reportedPos is not None and list(reportedPos) != info["position"]:
                discrepancy = {"expected": info["position"], "reported": list(reportedPos)}

            session.trajectory["observations"].append(obsBefore)
            session.trajectory["actions"].append(actionIdx)
            session.trajectory["logProbs"].append(logProb)
            session.trajectory["values"].append(value)
            session.trajectory["rewards"].append(reward)
            session.trajectory["rawRewards"].append(info["rawReward"])

            self._syncLegacyAttributes(session)
            result = {
                "success": True,
                "session_id": session.sessionId,
                "action": actionIdx,
                "action_name": ACTION_NAMES[actionIdx],
                "observation": [float(x) for x in nextObs],
                "discrepancy": discrepancy,
                **info,
                "state": session.environment.state(),
            }

            if done and bool(payload.get("auto_end", True)):
                endSummary = self._finalizeSession(session, scheduleLearn=session.collectExperience)
                result.update(endSummary)

            return result

    def step(self, deterministic=False):
        return self.stepEpisode({"deterministic": deterministic, "auto_end": True})

    def endEpisode(self, payload=None):
        payload = payload or {}
        with self.lock:
            session = self._getSession(payload.get("session_id"))
            scheduleLearn = bool(payload.get("learn", session.collectExperience))
            summary = self._finalizeSession(session, scheduleLearn=scheduleLearn)
            return {
                "success": True,
                "session_id": session.sessionId,
                **summary,
                "state": session.environment.state(),
            }

    def _finalizeSession(self, session, scheduleLearn=True):
        if session.completed:
            return {"episodeCompleted": True, "learningStarted": self.learning}
        session.completed = True
        self.episodeIndex += 1

        traj = session.trajectory
        traj["won"] = bool(session.environment.position in session.environment.ends)
        traj["timeout"] = bool(not traj["won"] and session.environment.steps >= session.environment.maxSteps)
        traj["score"] = int(session.environment.currentScore())
        traj["bonesCollected"] = int(len(session.environment.bones) - len(session.environment.remainingBones))
        traj["length"] = len(traj["actions"])
        traj["totalReward"] = float(sum(traj["rewards"]))
        traj["rawTotalReward"] = float(sum(traj["rawRewards"]))
        traj["bootstrapValue"] = 0.0

        savedPath = None
        if session.collectExperience and not session.isTestMap:
            savedPath = self.experienceStore.addEpisode(
                traj,
                mazeData=session.mazeData,
                isTestMap=session.isTestMap,
            )

        learningStarted = False
        if scheduleLearn and session.collectExperience and not session.isTestMap and self.learnUpdates > 0:
            if not self.learning:
                self.learn(asyncRun=True)
                learningStarted = True

        out = {
            "episodeCompleted": True,
            "learningStarted": learningStarted,
            "episodeSummary": {
                "won": traj["won"],
                "score": traj["score"],
                "steps": traj["length"],
                "bonesCollected": traj["bonesCollected"],
                "totalReward": round(traj["totalReward"], 4),
            },
        }
        if savedPath is not None:
            out["savedMap"] = savedPath.name
        return out

    def learn(self, asyncRun=True):
        with self.lock:
            if self.learning:
                return {"learning": True, "alreadyRunning": True}
            self.learning = True
            recentEpisodes = self.experienceStore.popEpisodes(maxCount=8)

        def worker():
            try:
                metrics = continualLearnStep(
                    checkpoint=self.checkpoint,
                    recentEpisodes=recentEpisodes,
                    trainMapsFolder=self.trainMapsFolder,
                    playedMapsFolder=self.mapsFolder,
                    validationFolder=self.validationFolder,
                    updates=max(1, self.learnUpdates),
                    maxSteps=self.maxSteps,
                )
                with self.lock:
                    self.meta = loadCheckpointFull(self.checkpoint, self.model)
                    self.model.eval()
                    self.lastTrainingMetrics = metrics
            except Exception as error:
                with self.lock:
                    self.lastTrainingMetrics = {"error": str(error)}
                print(f"Learning failed: {error}", flush=True)
            finally:
                with self.lock:
                    self.learning = False

        if asyncRun:
            threading.Thread(target=worker, daemon=True).start()
            return {"learning": True}
        else:
            worker()
            return {"learning": False, "completed": True, "metrics": self.lastTrainingMetrics}

    def agentStatus(self):
        with self.lock:
            meta = getCheckpointMetadata(self.checkpoint)
            return {
                "status": "ok",
                "modelVersion": int(meta.get("version", self.meta.get("version", 1))),
                "updates": int(meta.get("updates", self.meta.get("updates", 0))),
                "totalEpisodes": int(meta.get("totalEpisodes", 0)),
                "totalSteps": int(meta.get("totalSteps", 0)),
                "bestWinRate": float(meta.get("bestRate", 0.0)),
                "bestScore": meta.get("bestScore", None),
                "learning": self.learning,
                "activeSessions": len(self.sessions),
                "playedMapsCount": len(self.experienceStore.listPlayedMaps()),
                "pendingEpisodes": self.experienceStore.pendingCount(),
            }

    def trainingStatus(self):
        with self.lock:
            status = self.agentStatus()
            status["lastTrainingMetrics"] = self.lastTrainingMetrics
            return status

    def fullStatus(self):
        with self.lock:
            return {
                "learning": self.learning,
                "loaded": self.environment is not None,
                "state": self.environment.state() if self.environment else None,
                "agent": self.agentStatus(),
                "training": self.lastTrainingMetrics,
            }

