from collections import deque
import json
import tempfile
from pathlib import Path
from app.core.dependencies import rateLimiter
from app.core.websocket_manager import wsManager
from app.main import createApp
from app.rl_verification.maze_environment import DIRECTIONS, END, OPPOSITE_WALL, PIT, START, resolvePitChain


class TestApiClient:
    def __init__(self, serverApp):
        self.serverApp = serverApp

    def request(self, method, path, jsonBody=None, token=None, headers=None):
        hdrs = dict(headers or {})
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        rawBody = json.dumps(jsonBody).encode("utf-8") if jsonBody is not None else b""
        status, data = self.serverApp.dispatch(
            method=method,
            rawUrl=path,
            headers=hdrs,
            rawBody=rawBody,
            clientIp="127.0.0.1",
        )
        return status, data

    def get(self, path, token=None, headers=None):
        return self.request("GET", path, token=token, headers=headers)

    def post(self, path, jsonBody=None, token=None, headers=None):
        return self.request("POST", path, jsonBody=jsonBody, token=token, headers=headers)

    def patch(self, path, jsonBody=None, token=None, headers=None):
        return self.request("PATCH", path, jsonBody=jsonBody, token=token, headers=headers)


def createIsolatedTestApp():
    tmpDir = tempfile.TemporaryDirectory()
    dbPath = Path(tmpDir.name) / "test_server.db"
    rateLimiter.reset()
    wsManager.reset()
    app = createApp(databaseUrl=f"sqlite:///{dbPath}", fallbackSqlitePath=str(dbPath), resetDb=True)
    return app, TestApiClient(app), tmpDir


def findWinningActionSequence(mazeData):
    grid = mazeData["grid"]
    height = len(grid)
    width = len(grid[0])
    startPos = None
    ends = set()
    for y in range(height):
        for x in range(width):
            el = int(grid[y][x]["element"])
            if el == START:
                startPos = (x, y)
            elif el == END:
                ends.add((x, y))

    queue = deque([(startPos, [])])
    visited = {startPos}
    while queue:
        (x, y), actions = queue.popleft()
        if (x, y) in ends:
            return actions
        cell = grid[y][x]
        for actionIdx, (dx, dy, wallKey) in enumerate(DIRECTIONS):
            if bool(cell.get(wallKey, False)):
                continue
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if bool(grid[ny][nx].get(OPPOSITE_WALL[actionIdx], False)):
                continue
            resolved, _, invalid = resolvePitChain(grid, (nx, ny))
            if invalid or resolved is None:
                continue
            if resolved not in visited:
                visited.add(resolved)
                queue.append((resolved, actions + [actionIdx]))
    return [0]

