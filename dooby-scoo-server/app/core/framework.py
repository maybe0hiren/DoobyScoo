import asyncio
import json
import re
import socket
import threading
from urllib.parse import parse_qs, urlparse
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.websocket

from ..config import settings
from ..database.session import getDb
from .dependencies import extractBearerToken, getCurrentUserFromToken, rateLimiter
from .exceptions import AppError, BadRequestError, UnauthorizedError
from .security import nowIso
from .websocket_manager import wsManager


class RequestContext:
    def __init__(self, method, path, headers=None, queryParams=None, pathParams=None, body=None, rawBody=b"", clientIp="127.0.0.1"):
        self.method = str(method).upper()
        self.path = str(path)
        self.headers = headers or {}
        self.queryParams = queryParams or {}
        self.pathParams = pathParams or {}
        self.body = body if body is not None else {}
        self.rawBody = rawBody or b""
        self.clientIp = str(clientIp or "127.0.0.1")

    def getQuery(self, key, default=None):
        if key not in self.queryParams:
            return default
        val = self.queryParams[key]
        if isinstance(val, list):
            return val[0] if val else default
        return val


def _compileRoutePattern(routePath):
    paramNames = []
    def repl(match):
        name = match.group(1)
        paramNames.append(name)
        return f"(?P<{name}>[^/]+)"
    regexStr = "^" + re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, routePath.rstrip("/") or "/") + "/?$"
    return re.compile(regexStr), paramNames


class APIRouter:
    def __init__(self, prefix="", tags=None):
        self.prefix = str(prefix).rstrip("/")
        self.tags = tags or []
        self.routes = []

    def addRoute(self, method, path, handler, statusCode=200):
        fullPath = (self.prefix + "/" + str(path).lstrip("/")).rstrip("/") or "/"
        self.routes.append((str(method).upper(), fullPath, handler, int(statusCode)))
        return handler

    def get(self, path, status_code=200):
        def decorator(fn):
            return self.addRoute("GET", path, fn, statusCode=status_code)
        return decorator

    def post(self, path, status_code=200):
        def decorator(fn):
            return self.addRoute("POST", path, fn, statusCode=status_code)
        return decorator

    def patch(self, path, status_code=200):
        def decorator(fn):
            return self.addRoute("PATCH", path, fn, statusCode=status_code)
        return decorator

    def put(self, path, status_code=200):
        def decorator(fn):
            return self.addRoute("PUT", path, fn, statusCode=status_code)
        return decorator

    def delete(self, path, status_code=200):
        def decorator(fn):
            return self.addRoute("DELETE", path, fn, statusCode=status_code)
        return decorator


class ServerApplication:
    def __init__(self, title="DoobyScoo Multiplayer Server", version="1.0.0"):
        self.title = title
        self.version = version
        self.routes = []

    def include_router(self, router, prefix=""):
        extraPrefix = str(prefix).rstrip("/")
        for method, routePath, handler, statusCode in router.routes:
            fullPath = (extraPrefix + "/" + routePath.lstrip("/")).rstrip("/") or "/" if extraPrefix else routePath
            pattern, paramNames = _compileRoutePattern(fullPath)
            self.routes.append({
                "method": method,
                "path": fullPath,
                "pattern": pattern,
                "paramNames": paramNames,
                "handler": handler,
                "statusCode": statusCode,
            })

    def get(self, path, status_code=200):
        def decorator(fn):
            pattern, paramNames = _compileRoutePattern(path)
            self.routes.append({
                "method": "GET",
                "path": path,
                "pattern": pattern,
                "paramNames": paramNames,
                "handler": fn,
                "statusCode": status_code,
            })
            return fn
        return decorator

    def post(self, path, status_code=200):
        def decorator(fn):
            pattern, paramNames = _compileRoutePattern(path)
            self.routes.append({
                "method": "POST",
                "path": path,
                "pattern": pattern,
                "paramNames": paramNames,
                "handler": fn,
                "statusCode": status_code,
            })
            return fn
        return decorator

    def dispatch(self, method, rawUrl, headers=None, rawBody=b"", clientIp="127.0.0.1"):
        parsedUrl = urlparse(str(rawUrl))
        path = parsedUrl.path or "/"
        queryParams = {k: (v[0] if len(v) == 1 else v) for k, v in parse_qs(parsedUrl.query).items()}
        headersDict = dict(headers or {})

        if str(method).upper() == "OPTIONS":
            return 204, {}

        try:
            rateLimiter.check(clientIp)
            if rawBody and len(rawBody) > settings.maxRequestBytes:
                raise BadRequestError("Request payload exceeds maximum allowed size", code="payload_too_large")

            bodyData = {}
            if rawBody:
                try:
                    bodyData = json.loads(rawBody.decode("utf-8"))
                except Exception as exc:
                    raise BadRequestError("Invalid JSON request body") from exc

            matchedPath = False
            for route in self.routes:
                match = route["pattern"].match(path)
                if match:
                    matchedPath = True
                    if route["method"] != str(method).upper():
                        continue
                    req = RequestContext(
                        method=method,
                        path=path,
                        headers=headersDict,
                        queryParams=queryParams,
                        pathParams=match.groupdict(),
                        body=bodyData,
                        rawBody=rawBody,
                        clientIp=clientIp,
                    )
                    db = getDb()
                    result = route["handler"](req, db)
                    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], int):
                        return result[0], result[1]
                    return route["statusCode"], result

            if matchedPath:
                return 405, {"success": False, "error": "Method not allowed", "code": "method_not_allowed"}
            return 404, {"success": False, "error": "Endpoint not found", "code": "not_found"}

        except AppError as err:
            return err.statusCode, err.toDict()
        except ValueError as err:
            return 400, {"success": False, "error": str(err), "detail": str(err), "code": "bad_request"}
        except Exception as err:
            return 500, {"success": False, "error": f"Internal server error: {err}", "code": "internal_error"}


class _TornadoHttpHandler(tornado.web.RequestHandler):
    def initialize(self, serverApp):
        self.serverApp = serverApp

    def set_default_headers(self):
        origin = self.request.headers.get("Origin", "*")
        allowed = origin if ("*" in settings.corsOrigins or origin in settings.corsOrigins) else (settings.corsOrigins[0] if settings.corsOrigins else "*")
        self.set_header("Access-Control-Allow-Origin", allowed)
        self.set_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.set_header("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
        self.set_header("Content-Type", "application/json")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def _handleMethod(self, method):
        headers = {k: v for k, v in self.request.headers.get_all()}
        clientIp = self.request.remote_ip or "127.0.0.1"
        status, payload = self.serverApp.dispatch(
            method=method,
            rawUrl=self.request.uri,
            headers=headers,
            rawBody=self.request.body or b"",
            clientIp=clientIp,
        )
        self.set_status(status)
        if status != 204:
            self.write(json.dumps(payload))
        self.finish()

    def get(self, *args, **kwargs):
        self._handleMethod("GET")

    def post(self, *args, **kwargs):
        self._handleMethod("POST")

    def patch(self, *args, **kwargs):
        self._handleMethod("PATCH")

    def put(self, *args, **kwargs):
        self._handleMethod("PUT")

    def delete(self, *args, **kwargs):
        self._handleMethod("DELETE")


class _TornadoWsHandler(tornado.websocket.WebSocketHandler):
    def initialize(self, serverApp):
        self.serverApp = serverApp
        self.user = None
        self.ioLoop = None

    def check_origin(self, origin):
        return True

    def open(self):
        self.ioLoop = tornado.ioloop.IOLoop.current()
        queryParams = {k: [v.decode("utf-8") for v in vals] for k, vals in self.request.query_arguments.items()}
        headers = {k: v for k, v in self.request.headers.get_all()}
        try:
            token = extractBearerToken(headers, queryParams)
            self.user = getCurrentUserFromToken(token)
            wsManager.registerConnection(self.user.id, self)
            lastEventId = self.get_query_argument("last_event_id", default=None)
            sinceSeq = int(self.get_query_argument("since_seq", default="0") or 0)
            self._sendAuthAck(lastEventId=lastEventId, sinceSeq=sinceSeq)
        except UnauthorizedError:
            self.user = None

    def _sendAuthAck(self, lastEventId=None, sinceSeq=0):
        if not self.user:
            return
        self.write_message(json.dumps({
            "event_id": f"auth_{self.user.id}",
            "event_type": "connection.authenticated",
            "timestamp": nowIso(),
            "player_id": self.user.id,
            "payload": {
                "user_id": self.user.id,
                "username": self.user.username,
                "status": "authenticated",
            },
        }))
        missed = wsManager.getMissedEvents(self.user.id, lastEventId=lastEventId, sinceSeq=sinceSeq)
        for ev in missed:
            self.write_message(json.dumps(ev))

    def sendEventThreadsafe(self, envelope):
        if self.ioLoop is not None:
            self.ioLoop.add_callback(self._safeWrite, envelope)

    def _safeWrite(self, envelope):
        try:
            self.write_message(json.dumps(envelope))
        except Exception:
            pass

    def on_message(self, message):
        try:
            data = json.loads(message) if isinstance(message, str) else {}
        except Exception:
            self.write_message(json.dumps({"event_type": "error", "error": "Invalid JSON message"}))
            return

        clientEventId = data.get("event_id") or data.get("client_event_id")
        if clientEventId and wsManager.markClientEventProcessed(clientEventId):
            self.write_message(json.dumps({
                "event_type": "event.duplicate_ignored",
                "client_event_id": str(clientEventId),
                "timestamp": nowIso(),
            }))
            return

        msgType = str(data.get("type") or data.get("action") or "").lower()
        if msgType in ("auth", "authenticate"):
            token = data.get("token") or data.get("access_token")
            try:
                self.user = getCurrentUserFromToken(token)
                wsManager.registerConnection(self.user.id, self)
                self._sendAuthAck(
                    lastEventId=data.get("last_event_id"),
                    sinceSeq=int(data.get("since_seq") or 0),
                )
            except UnauthorizedError as err:
                self.write_message(json.dumps({
                    "event_type": "connection.error",
                    "error": err.message,
                    "code": err.code,
                }))
                self.close(code=4001, reason=err.message)
            return

        if not self.user:
            self.write_message(json.dumps({
                "event_type": "connection.error",
                "error": "Authenticate first",
                "code": "unauthorized",
            }))
            self.close(code=4001, reason="Unauthorized")
            return

        if msgType in ("ping", "heartbeat"):
            self.write_message(json.dumps({
                "event_type": "pong",
                "timestamp": nowIso(),
                "player_id": self.user.id,
            }))
            return

        if msgType in ("recover", "sync", "recover_events"):
            missed = wsManager.getMissedEvents(
                self.user.id,
                lastEventId=data.get("last_event_id"),
                sinceSeq=int(data.get("since_seq") or 0),
            )
            for ev in missed:
                self.write_message(json.dumps(ev))
            self.write_message(json.dumps({
                "event_type": "connection.synced",
                "timestamp": nowIso(),
                "player_id": self.user.id,
                "payload": {"recovered_count": len(missed)},
            }))

    def on_close(self):
        if self.user:
            wsManager.unregisterConnection(self.user.id, self)


class LiveServerHandle:
    def __init__(self, host, port, loopReadyEvent, stateHolder):
        self.host = host
        self.port = port
        self._ready = loopReadyEvent
        self._state = stateHolder

    @property
    def baseUrl(self):
        return f"http://{self.host}:{self.port}"

    @property
    def wsUrl(self):
        return f"ws://{self.host}:{self.port}/ws"

    def stop(self):
        ioLoop = self._state.get("ioLoop")
        httpServer = self._state.get("httpServer")
        thread = self._state.get("thread")
        if ioLoop is not None:
            def _shutdown():
                if httpServer is not None:
                    httpServer.stop()
                ioLoop.stop()
            ioLoop.add_callback(_shutdown)
        if thread is not None and thread.is_alive():
            thread.join(timeout=3.0)


def startBackgroundServer(serverApp, host="127.0.0.1", port=0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, int(port)))
    sock.listen(128)
    sock.setblocking(False)
    actualPort = sock.getsockname()[1]

    readyEvent = threading.Event()
    stateHolder = {}

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ioLoop = tornado.ioloop.IOLoop.current()
        tornadoApp = tornado.web.Application([
            (r"/ws", _TornadoWsHandler, {"serverApp": serverApp}),
            (r"/api/v1/ws", _TornadoWsHandler, {"serverApp": serverApp}),
            (r"/.*", _TornadoHttpHandler, {"serverApp": serverApp}),
        ])
        httpServer = tornado.httpserver.HTTPServer(tornadoApp)
        httpServer.add_socket(sock)
        stateHolder["ioLoop"] = ioLoop
        stateHolder["httpServer"] = httpServer
        ioLoop.add_callback(readyEvent.set)
        ioLoop.start()
        sock.close()

    thread = threading.Thread(target=_run, daemon=True)
    stateHolder["thread"] = thread
    thread.start()
    readyEvent.wait(timeout=5.0)
    return LiveServerHandle(host, actualPort, readyEvent, stateHolder)

