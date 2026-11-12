import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from .session_manager import GameService


def createServer(
    checkpoint="models/dog.pt",
    mapsFolder="maps/played",
    port=8765,
    learnUpdates=3,
    trainMapsFolder="maps/train",
    validationFolder="maps/validation",
):
    service = GameService(
        checkpoint=checkpoint,
        mapsFolder=mapsFolder,
        trainMapsFolder=trainMapsFolder,
        validationFolder=validationFolder,
        learnUpdates=learnUpdates,
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, formatStr, *args):
            return

        def sendJson(self, status, data):
            encoded = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/health":
                self.sendJson(200, {"status": "ok", "service": "doobyscoo-agent", "learning": service.learning})
            elif self.path == "/status":
                self.sendJson(200, service.fullStatus())
            elif self.path == "/agent/status":
                self.sendJson(200, service.agentStatus())
            elif self.path == "/training/status":
                self.sendJson(200, service.trainingStatus())
            else:
                self.sendJson(404, {"error": "Not found"})

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size > 1024 * 1024:
                    raise ValueError("Maze request exceeds 1 MB")
                rawBody = self.rfile.read(size) if size else b""
                data = json.loads(rawBody.decode("utf-8")) if rawBody else {}

                if self.path in ("/map", "/episode/start"):
                    result = service.startEpisode(data)
                elif self.path == "/reset":
                    result = service.reset(data.get("session_id"))
                elif self.path == "/agent/action":
                    result = service.selectAction(data)
                elif self.path in ("/step", "/episode/step"):
                    result = service.stepEpisode(data)
                elif self.path == "/episode/end":
                    result = service.endEpisode(data)
                elif self.path == "/competitive/solve":
                    result = service.solveCompetitiveMaze(data)
                elif self.path == "/competitive/learn":
                    result = service.learnFromCompetitiveSession(data)
                elif self.path == "/learn":
                    asyncRun = bool(data.get("async", True))
                    result = service.learn(asyncRun=asyncRun)
                else:
                    return self.sendJson(404, {"error": "Not found"})
                self.sendJson(200, result)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError) as error:
                self.sendJson(400, {"error": str(error)})

    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    server.service = service
    return server


def serve(
    checkpoint="models/dog.pt",
    mapsFolder="maps/played",
    port=8765,
    learnUpdates=3,
    trainMapsFolder="maps/train",
    validationFolder="maps/validation",
):
    server = createServer(
        checkpoint=checkpoint,
        mapsFolder=mapsFolder,
        port=port,
        learnUpdates=learnUpdates,
        trainMapsFolder=trainMapsFolder,
        validationFolder=validationFolder,
    )
    print(f"DoobyScoo agent at http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

