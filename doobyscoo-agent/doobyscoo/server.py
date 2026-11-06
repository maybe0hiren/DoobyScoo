import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import torch
from .agent import RecurrentPolicy, chooseAction
from .environment import MazeEnvironment
from .training import loadCheckpoint, train


class GameService:
    def __init__(self, checkpoint, mapsFolder, maxSteps=300, learnUpdates=5):
        self.checkpoint = Path(checkpoint)
        self.mapsFolder = Path(mapsFolder)
        self.mapsFolder.mkdir(parents=True, exist_ok=True)
        self.maxSteps = maxSteps
        self.learnUpdates = learnUpdates
        self.model = RecurrentPolicy()
        loadCheckpoint(checkpoint, self.model)
        self.model.eval()
        self.environment = None
        self.memory = None
        self.mazeData = None
        self.lock = threading.RLock()
        self.learning = False
        self.episodeIndex = 0

    def newMap(self, data):
        with self.lock:
            if self.learning:
                raise ValueError("Training in progress; retry shortly")
            self.mazeData = data
            self.environment = MazeEnvironment(data, self.maxSteps)
            self.memory = self.model.initialState()
            return self.environment.state()

    def reset(self):
        with self.lock:
            if self.environment is None:
                raise ValueError("Load a maze first")
            self.environment.reset()
            self.memory = self.model.initialState()
            return self.environment.state()

    def step(self, deterministic=False):
        with self.lock:
            if self.learning:
                raise ValueError("Training in progress; retry shortly")
            if self.environment is None or self.environment.done:
                raise ValueError("Load or reset a maze first")
            action, _, _, self.memory = chooseAction(self.model, self.environment.observe(), self.memory, deterministic)
            _, _, done, info = self.environment.step(action)
            result = {"action": action, **info, "state": self.environment.state()}
            if done:
                self.episodeIndex += 1
                path = self.mapsFolder / f"played_{self.episodeIndex:06d}.json"
                while path.exists():
                    self.episodeIndex += 1
                    path = self.mapsFolder / f"played_{self.episodeIndex:06d}.json"
                path.write_text(json.dumps(self.mazeData), encoding="utf-8")
                result["savedMap"] = path.name
                self.learn()
                result["learningStarted"] = True
            return result

    def learn(self):
        with self.lock:
            if self.learning:
                raise ValueError("Training already in progress")
            self.learning = True
        def worker():
            try:
                train(self.mapsFolder, self.checkpoint, updates=self.learnUpdates, maxSteps=self.maxSteps)
                with self.lock:
                    loadCheckpoint(self.checkpoint, self.model)
                    self.model.eval()
            except Exception as error:
                print(f"Learning failed: {error}", flush=True)
            finally:
                with self.lock:
                    self.learning = False
        threading.Thread(target=worker, daemon=True).start()
        return {"learning": True}


def serve(checkpoint, mapsFolder, port=8765, learnUpdates=5):
    service = GameService(checkpoint, mapsFolder, learnUpdates=learnUpdates)
    class Handler(BaseHTTPRequestHandler):
        def sendJson(self, status, data):
            encoded = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/status":
                with service.lock:
                    self.sendJson(200, {"learning": service.learning, "loaded": service.environment is not None, "state": service.environment.state() if service.environment else None})
            else:
                self.sendJson(404, {"error": "Not found"})

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size > 1024 * 1024:
                    raise ValueError("Maze request exceeds 1 MB")
                data = json.loads(self.rfile.read(size)) if size else {}
                if self.path == "/map":
                    result = service.newMap(data)
                elif self.path == "/reset":
                    result = service.reset()
                elif self.path == "/step":
                    result = service.step(bool(data.get("deterministic", False)))
                elif self.path == "/learn":
                    result = service.learn()
                else:
                    return self.sendJson(404, {"error": "Not found"})
                self.sendJson(200, result)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as error:
                self.sendJson(400, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"DoobyScoo agent at http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
