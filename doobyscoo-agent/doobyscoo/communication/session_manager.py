import copy
import threading
import uuid
from pathlib import Path
from ..agent.network import RecurrentPolicy, chooseAction
from ..environment.maze_environment import MazeEnvironment, ACTION_NAMES
from ..storage.checkpoint import (
    IncompatibleCheckpointError,
    getCheckpointMetadata,
    initializeFreshModel,
    loadCheckpointFull,
)
from ..storage.experience_store import ExperienceStore
from ..training.trainer import continualLearnStep
from .protocol import actionToName, parseActionValue, validateObservationInput


def _rejectSensitiveCredentials(payload):
    if isinstance(payload, dict):
        for forbidden in ("password", "password_hash", "refresh_token", "refreshToken"):
            if forbidden in payload:
                raise ValueError(f"Security violation: local RL agent must never receive '{forbidden}'")


class EpisodeSession:
    def __init__(
        self,
        sessionId,
        mazeData,
        model,
        maxSteps=300,
        mode="training",
        deterministic=False,
        collectExperience=True,
        isTestMap=False,
        matchId=None,
        mapId=None,
        mapHash=None,
        modelVersion=1,
    ):
        self.sessionId = str(sessionId)
        self.mazeData = mazeData
        self.environment = MazeEnvironment(mazeData, maxSteps=maxSteps)
        self.policyModel = copy.deepcopy(model).eval() if str(mode).lower() == "competitive" else model
        self.memory = self.policyModel.initialState()
        self.initialState = self.memory.detach()
        self.mode = str(mode)
        self.deterministic = bool(deterministic)
        self.collectExperience = False if str(mode).lower() == "competitive" else bool(collectExperience)
        self.isTestMap = bool(isTestMap)
        self.matchId = str(matchId) if matchId else None
        self.mapId = str(mapId) if mapId else None
        self.mapHash = str(mapHash) if mapHash else None
        self.modelVersion = int(modelVersion)
        self.pendingAction = None
        self.completed = False
        self.postMatchLearned = False
        self.lastSummary = None
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
        if str(self.mode).lower() != "competitive":
            self.policyModel = model
        self.memory = self.policyModel.initialState()
        self.initialState = self.memory.detach()
        self.pendingAction = None
        self.completed = False
        self.lastSummary = None
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
        try:
            self.meta = loadCheckpointFull(self.checkpoint, self.model)
        except IncompatibleCheckpointError:
            initializeFreshModel(self.checkpoint, self.model, reason="incompatible_checkpoint_replaced")
            self.meta = loadCheckpointFull(self.checkpoint, self.model)
        if not self.checkpoint.exists() or not self.meta.get("loaded", False):
            initializeFreshModel(self.checkpoint, self.model, reason="service_fresh_init")
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
        _rejectSensitiveCredentials(payload)
        with self.lock:
            mazeData = payload.get("maze", payload) if isinstance(payload, dict) else payload
            sessionCfg = payload.get("session", {}) if isinstance(payload, dict) else {}
            matchId = (payload.get("match_id") or sessionCfg.get("match_id")) if isinstance(payload, dict) else None
            mapId = (payload.get("map_id") or sessionCfg.get("map_id") or sessionCfg.get("maze_id")) if isinstance(payload, dict) else None
            mapHash = (payload.get("map_hash") or sessionCfg.get("map_hash")) if isinstance(payload, dict) else None

            rawSessionId = (payload.get("session_id") or sessionCfg.get("session_id")) if isinstance(payload, dict) else None
            if not rawSessionId and matchId:
                rawSessionId = f"match_{matchId}_{uuid.uuid4().hex[:6]}"
            sessionId = str(rawSessionId or uuid.uuid4().hex[:12])

            mode = str((payload.get("mode") if isinstance(payload, dict) else None) or sessionCfg.get("mode") or "training").lower()
            isCompetitive = mode == "competitive"
            if isCompetitive and not self.learning and self.checkpoint.exists():
                self.meta = loadCheckpointFull(self.checkpoint, self.model)
                self.model.eval()

            deterministic = bool(
                payload.get(
                    "deterministic",
                    sessionCfg.get("deterministic", mode in ("evaluation", "inference", "eval", "competitive")),
                )
            ) if isinstance(payload, dict) else False
            collectExperience = False if isCompetitive else (
                bool(payload.get("collect_experience", sessionCfg.get("collect_experience", mode != "evaluation_no_learn")))
                if isinstance(payload, dict)
                else True
            )
            isTestMap = bool(payload.get("is_test_map", sessionCfg.get("is_test_map", False))) if isinstance(payload, dict) else False
            customMaxSteps = int(payload.get("max_steps", self.maxSteps)) if isinstance(payload, dict) else self.maxSteps
            modelVersion = int(self.meta.get("version", 1))

            session = EpisodeSession(
                sessionId=sessionId,
                mazeData=mazeData,
                model=self.model,
                maxSteps=customMaxSteps,
                mode=mode,
                deterministic=deterministic,
                collectExperience=collectExperience,
                isTestMap=isTestMap,
                matchId=matchId,
                mapId=mapId,
                mapHash=mapHash,
                modelVersion=modelVersion,
            )
            self.sessions[sessionId] = session
            self.defaultSessionId = sessionId
            self._syncLegacyAttributes(session)
            state = session.environment.state()
            return {
                "success": True,
                "session_id": sessionId,
                "match_id": session.matchId,
                "map_id": session.mapId,
                "map_hash": session.mapHash,
                "mode": mode,
                "deterministic": deterministic,
                "collect_experience": collectExperience,
                "model_version": modelVersion,
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
        _rejectSensitiveCredentials(payload)
        with self.lock:
            sessionId = payload.get("session_id")
            session = self._getSession(sessionId) if (sessionId or self.defaultSessionId in self.sessions) else None
            sessObs = session.environment.observe() if session is not None else None

            rawObs = payload.get("observation")
            if rawObs is not None:
                if isinstance(rawObs, dict) and "features" in rawObs:
                    obsVec = validateObservationInput(rawObs["features"], sessionObservation=sessObs)
                elif isinstance(rawObs, (list, tuple)):
                    obsVec = validateObservationInput(rawObs, sessionObservation=sessObs)
                elif session is not None:
                    obsVec = sessObs
                else:
                    raise ValueError("Invalid observation format")
            elif session is not None:
                obsVec = sessObs
            else:
                raise ValueError("No active session or observation provided")

            deterministic = bool(payload.get("deterministic", session.deterministic if session else False))
            activeModel = session.policyModel if session is not None else self.model
            stateIn = session.memory if session is not None else activeModel.initialState()
            actionIdx, logProb, value, nextState = chooseAction(activeModel, obsVec, stateIn, deterministic=deterministic)

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
                "model_version": int(session.modelVersion if session else self.meta.get("version", 1)),
            }

    def stepEpisode(self, payload=None):
        payload = payload or {}
        _rejectSensitiveCredentials(payload)
        with self.lock:
            session = self._getSession(payload.get("session_id"))
            if session.environment.done:
                raise ValueError("Load or reset a maze first")

            deterministic = bool(payload.get("deterministic", session.deterministic))
            obsBefore = session.environment.observe()
            activeModel = session.policyModel

            if "action" in payload and payload["action"] is not None:
                requestedAction = parseActionValue(payload["action"])
                if session.pendingAction and session.pendingAction["action"] == requestedAction:
                    actionIdx = requestedAction
                    logProb = session.pendingAction["logProb"]
                    value = session.pendingAction["value"]
                    nextMemory = session.pendingAction["nextState"]
                else:
                    _, logProb, value, nextMemory = chooseAction(activeModel, obsBefore, session.memory, deterministic=deterministic)
                    actionIdx = requestedAction
            elif session.pendingAction is not None:
                actionIdx = session.pendingAction["action"]
                logProb = session.pendingAction["logProb"]
                value = session.pendingAction["value"]
                nextMemory = session.pendingAction["nextState"]
            else:
                actionIdx, logProb, value, nextMemory = chooseAction(activeModel, obsBefore, session.memory, deterministic=deterministic)

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
                "match_id": session.matchId,
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
        _rejectSensitiveCredentials(payload)
        with self.lock:
            session = self._getSession(payload.get("session_id"))
            isCompetitive = str(session.mode).lower() == "competitive"
            scheduleLearn = False if isCompetitive else bool(payload.get("learn", session.collectExperience))
            summary = self._finalizeSession(session, scheduleLearn=scheduleLearn)
            return {
                "success": True,
                "session_id": session.sessionId,
                **summary,
                "state": session.environment.state(),
            }

    def _finalizeSession(self, session, scheduleLearn=True):
        if session.completed and session.lastSummary is not None:
            return dict(session.lastSummary)
        session.completed = True
        self.episodeIndex += 1

        env = session.environment
        traj = session.trajectory
        traj["won"] = bool(env.position in env.ends)
        traj["timeout"] = bool(not traj["won"] and env.steps >= env.maxSteps)
        traj["score"] = int(env.currentScore())
        traj["bonesCollected"] = int(env.bonesCollected())
        traj["totalBones"] = int(len(env.bones))
        traj["length"] = len(traj["actions"])
        traj["revisits"] = int(env.revisits)
        traj["wallBumps"] = int(env.wallBumps)
        traj["uniqueCells"] = int(len(env.visitCounts))
        traj["totalReward"] = float(sum(traj["rewards"]))
        traj["rawTotalReward"] = float(sum(traj["rawRewards"]))
        traj["bootstrapValue"] = 0.0

        isCompetitive = str(session.mode).lower() == "competitive"
        savedPath = None
        if not isCompetitive and session.collectExperience and not session.isTestMap:
            savedPath = self.experienceStore.addEpisode(
                traj,
                mazeData=session.mazeData,
                isTestMap=session.isTestMap,
            )

        learningStarted = False
        if not isCompetitive and scheduleLearn and session.collectExperience and not session.isTestMap and self.learnUpdates > 0:
            if not self.learning:
                self.learn(asyncRun=True)
                learningStarted = True

        actionTrace = [int(a) for a in traj["actions"]]
        finalPosition = [int(env.position[0]), int(env.position[1])]
        submissionId = f"sub_{session.sessionId}_{uuid.uuid4().hex[:8]}"

        submissionPayload = {
            "match_id": session.matchId,
            "map_id": session.mapId,
            "map_hash": session.mapHash,
            "action_trace": actionTrace,
            "claimed_score": int(traj["score"]),
            "claimed_steps": int(traj["length"]),
            "claimed_bones_collected": int(traj["bonesCollected"]),
            "claimed_completed": bool(traj["won"]),
            "final_position": finalPosition,
            "submission_id": submissionId,
            "model_version": int(session.modelVersion),
        }

        out = {
            "episodeCompleted": True,
            "learningStarted": learningStarted,
            "action_trace": actionTrace,
            "action_names": [ACTION_NAMES[a] for a in actionTrace],
            "claimed_score": int(traj["score"]),
            "claimed_steps": int(traj["length"]),
            "claimed_bones_collected": int(traj["bonesCollected"]),
            "claimed_completed": bool(traj["won"]),
            "final_position": finalPosition,
            "model_version": int(session.modelVersion),
            "submission_id": submissionId,
            "submission_payload": submissionPayload,
            "episodeSummary": {
                "won": traj["won"],
                "score": traj["score"],
                "steps": traj["length"],
                "bonesCollected": traj["bonesCollected"],
                "revisits": traj["revisits"],
                "uniqueCells": traj["uniqueCells"],
                "totalReward": round(traj["totalReward"], 4),
                "actionTrace": actionTrace,
                "finalPosition": finalPosition,
                "modelVersion": int(session.modelVersion),
            },
        }
        if savedPath is not None:
            out["savedMap"] = savedPath.name
        session.lastSummary = dict(out)
        return out

    def solveCompetitiveMaze(self, payload):
        payload = dict(payload or {})
        _rejectSensitiveCredentials(payload)
        payload["mode"] = "competitive"
        payload["collect_experience"] = False
        payload.setdefault("deterministic", True)

        startInfo = self.startEpisode(payload)
        sessionId = startInfo["session_id"]
        stepFrames = []

        while True:
            stepRes = self.stepEpisode({
                "session_id": sessionId,
                "deterministic": bool(payload.get("deterministic", True)),
                "auto_end": True,
            })
            stepFrames.append({
                "step": stepRes["steps"],
                "action": stepRes["action"],
                "action_name": stepRes["action_name"],
                "position": stepRes["position"],
                "moved": stepRes["moved"],
                "teleported": stepRes["teleported"],
                "bone": stepRes["bone"],
                "bonesCollected": stepRes["bonesCollected"],
                "score": stepRes["score"],
                "won": stepRes["won"],
                "timeout": stepRes["timeout"],
                "done": stepRes["done"],
            })
            if stepRes["done"]:
                return {
                    "success": True,
                    "session_id": sessionId,
                    "match_id": startInfo.get("match_id"),
                    "map_id": startInfo.get("map_id"),
                    "map_hash": startInfo.get("map_hash"),
                    "model_version": startInfo.get("model_version", 1),
                    "action_trace": stepRes["action_trace"],
                    "action_names": stepRes["action_names"],
                    "claimed_score": stepRes["claimed_score"],
                    "claimed_steps": stepRes["claimed_steps"],
                    "claimed_bones_collected": stepRes["claimed_bones_collected"],
                    "claimed_completed": stepRes["claimed_completed"],
                    "final_position": stepRes["final_position"],
                    "submission_id": stepRes["submission_id"],
                    "submission_payload": stepRes["submission_payload"],
                    "steps_trace": stepFrames,
                }

    def learnFromCompetitiveSession(self, payload=None):
        payload = payload or {}
        _rejectSensitiveCredentials(payload)
        with self.lock:
            session = self._getSession(payload.get("session_id"))
            if not session.completed:
                raise ValueError("Finish the competitive episode before triggering post-match learning")
            if not session.postMatchLearned and not session.isTestMap:
                session.postMatchLearned = True
                self.experienceStore.addEpisode(
                    session.trajectory,
                    mazeData=session.mazeData,
                    isTestMap=False,
                )
        asyncRun = bool(payload.get("async", True))
        learnRes = self.learn(asyncRun=asyncRun)
        return {
            "success": True,
            "session_id": session.sessionId,
            "post_match_learning": True,
            **learnRes,
        }

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
                "modelId": meta.get("modelId") or self.meta.get("modelId"),
                "architecture": meta.get("architecture") or getattr(self.model, "architecture", None),
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
