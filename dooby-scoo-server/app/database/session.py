from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from ..config import settings
from .base import SCHEMA_STATEMENTS, DROP_STATEMENTS

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None


class DatabaseSession:
    def __init__(self, connection, isPostgres=False, lock=None):
        self.connection = connection
        self.isPostgres = bool(isPostgres)
        self.lock = lock or threading.RLock()
        self._txDepth = 0

    def _prepareQuery(self, query):
        if self.isPostgres:
            return query.replace("?", "%s")
        return query

    def execute(self, query, params=()):
        sql = self._prepareQuery(query)
        with self.lock:
            cur = self.connection.cursor()
            cur.execute(sql, tuple(params))
            if self._txDepth == 0:
                self.connection.commit()
            return cur

    def fetchOne(self, query, params=()):
        sql = self._prepareQuery(query)
        with self.lock:
            cur = self.connection.cursor()
            cur.execute(sql, tuple(params))
            row = cur.fetchone()
            if row is None:
                return None
            if isinstance(row, dict):
                return dict(row)
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))

    def fetchAll(self, query, params=()):
        sql = self._prepareQuery(query)
        with self.lock:
            cur = self.connection.cursor()
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            if not rows:
                return []
            if isinstance(rows[0], dict):
                return [dict(r) for r in rows]
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, r)) for r in rows]

    @contextmanager
    def transaction(self):
        with self.lock:
            isOuter = self._txDepth == 0
            self._txDepth += 1
            try:
                if isOuter and not self.isPostgres:
                    self.connection.execute("BEGIN IMMEDIATE")
                yield self
                if isOuter:
                    self.connection.commit()
            except Exception:
                if isOuter:
                    self.connection.rollback()
                raise
            finally:
                self._txDepth -= 1

    def close(self):
        try:
            self.connection.close()
        except Exception:
            pass


class DatabaseEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.isPostgres = False
        self.sqlitePath = None
        self.pgDsn = None
        self._sharedConnection = None
        self.configure()

    def configure(self, databaseUrl=None, fallbackSqlitePath=None):
        with self.lock:
            if self._sharedConnection is not None:
                try:
                    self._sharedConnection.close()
                except Exception:
                    pass
                self._sharedConnection = None

            url = str(databaseUrl or settings.databaseUrl)
            fallback = str(fallbackSqlitePath or settings.fallbackSqlitePath)
            self.isPostgres = False
            self.pgDsn = None

            if url.startswith("postgresql") and psycopg2 is not None:
                cleanDsn = url.replace("postgresql+psycopg2://", "postgresql://")
                try:
                    conn = psycopg2.connect(cleanDsn, connect_timeout=2)
                    conn.close()
                    self.isPostgres = True
                    self.pgDsn = cleanDsn
                except Exception:
                    self.isPostgres = False

            if not self.isPostgres:
                if url.startswith("sqlite:///"):
                    self.sqlitePath = url[len("sqlite:///") :]
                else:
                    self.sqlitePath = fallback
                if self.sqlitePath != ":memory:":
                    Path(self.sqlitePath).parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(self.sqlitePath, check_same_thread=False, timeout=15.0, isolation_level=None)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA busy_timeout = 5000")
                self._sharedConnection = conn

    def getSession(self):
        with self.lock:
            if self.isPostgres and self.pgDsn and psycopg2 is not None:
                conn = psycopg2.connect(self.pgDsn)
                return DatabaseSession(conn, isPostgres=True, lock=self.lock)
            if self._sharedConnection is None:
                self.configure()
            return DatabaseSession(self._sharedConnection, isPostgres=False, lock=self.lock)

    def initSchema(self):
        session = self.getSession()
        with session.transaction():
            for stmt in SCHEMA_STATEMENTS:
                session.execute(stmt)

    def resetSchema(self):
        session = self.getSession()
        with session.transaction():
            for stmt in DROP_STATEMENTS:
                session.execute(stmt)
            for stmt in SCHEMA_STATEMENTS:
                session.execute(stmt)


dbEngine = DatabaseEngine()


def initDatabase(databaseUrl=None, fallbackSqlitePath=None, reset=False):
    if databaseUrl is not None or fallbackSqlitePath is not None:
        dbEngine.configure(databaseUrl=databaseUrl, fallbackSqlitePath=fallbackSqlitePath)
    if reset:
        dbEngine.resetSchema()
    else:
        dbEngine.initSchema()
    return dbEngine


def getDb():
    return dbEngine.getSession()

