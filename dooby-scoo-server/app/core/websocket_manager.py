import json
import threading
import uuid
from ..database.session import getDb
from .security import nowIso

REQUIRED_EVENT_TYPES = (
    "matchmaking.started",
    "matchmaking.opponent_found",
    "match.created",
    "match.map_assigned",
    "match.opponent_submitted",
    "match.verification_started",
    "match.completed",
    "match.expired",
    "player.profile_updated",
    "player.trophies_updated",
    "leaderboard.updated",
)


class WebSocketManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.connections = {}
        self.processedClientEvents = set()
        self._seqCounter = 0

    def _nextSeq(self, db):
        if self._seqCounter == 0:
            row = db.fetchOne("SELECT MAX(seq_id) AS max_seq FROM ws_events")
            if row and row.get("max_seq") is not None:
                self._seqCounter = int(row["max_seq"])
        self._seqCounter += 1
        return self._seqCounter

    def registerConnection(self, userId, connection):
        uid = str(userId)
        with self.lock:
            self.connections.setdefault(uid, set()).add(connection)

    def unregisterConnection(self, userId, connection):
        uid = str(userId)
        with self.lock:
            conns = self.connections.get(uid)
            if conns and connection in conns:
                conns.remove(connection)
                if not conns:
                    self.connections.pop(uid, None)

    def isUserOnline(self, userId):
        with self.lock:
            return bool(self.connections.get(str(userId)))

    def markClientEventProcessed(self, eventId):
        if not eventId:
            return False
        eid = str(eventId)
        with self.lock:
            if eid in self.processedClientEvents:
                return True
            self.processedClientEvents.add(eid)
            if len(self.processedClientEvents) > 5000:
                self.processedClientEvents.pop()
            return False

    def emitEvent(self, eventType, payload, userId=None, matchId=None, db=None):
        session = db or getDb()
        with self.lock:
            seqId = self._nextSeq(session)
            eventId = f"evt_{seqId}_{uuid.uuid4().hex[:10]}"
            timestamp = nowIso()
            envelope = {
                "event_id": eventId,
                "seq_id": seqId,
                "event_type": str(eventType),
                "timestamp": timestamp,
                "player_id": str(userId) if userId else None,
                "match_id": str(matchId) if matchId else None,
                "payload": payload or {},
            }
            session.execute(
                """
                INSERT INTO ws_events (event_id, seq_id, user_id, match_id, event_type, timestamp, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eventId,
                    seqId,
                    str(userId) if userId else None,
                    str(matchId) if matchId else None,
                    str(eventType),
                    timestamp,
                    json.dumps(envelope),
                ),
            )

            targets = []
            if userId is not None:
                targets = list(self.connections.get(str(userId), set()))
            else:
                for connSet in self.connections.values():
                    targets.extend(connSet)

        for conn in targets:
            try:
                conn.sendEventThreadsafe(envelope)
            except Exception:
                pass
        return envelope

    def emitToUsers(self, userIds, eventType, payload, matchId=None, db=None):
        envelopes = []
        for uid in userIds:
            envelopes.append(self.emitEvent(eventType, payload, userId=uid, matchId=matchId, db=db))
        return envelopes

    def getMissedEvents(self, userId, lastEventId=None, sinceSeq=0, db=None):
        session = db or getDb()
        minSeq = int(sinceSeq or 0)
        if lastEventId:
            row = session.fetchOne("SELECT seq_id FROM ws_events WHERE event_id = ?", (str(lastEventId),))
            if row and row.get("seq_id") is not None:
                minSeq = max(minSeq, int(row["seq_id"]))

        rows = session.fetchAll(
            """
            SELECT payload_json FROM ws_events
            WHERE (user_id = ? OR user_id IS NULL) AND seq_id > ?
            ORDER BY seq_id ASC
            LIMIT 200
            """,
            (str(userId), minSeq),
        )
        events = []
        for row in rows:
            try:
                events.append(json.loads(row["payload_json"]))
            except Exception:
                pass
        return events

    def reset(self):
        with self.lock:
            self.connections.clear()
            self.processedClientEvents.clear()
            self._seqCounter = 0


wsManager = WebSocketManager()

