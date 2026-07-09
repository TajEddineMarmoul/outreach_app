from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


def _convert_placeholders(sql: str) -> str:
    return sql.replace("?", "%s")


class PGRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            keys = list(self.keys())
            return super().__getitem__(keys[key]) if key < len(keys) else None
        return super().__getitem__(key)


class PGCursor:
    def __init__(self, cur, conn):
        self._cur = cur
        self._conn = conn
        self._lastrowid: int | None = None

    @property
    def lastrowid(self) -> int | None:
        if self._lastrowid is not None:
            return self._lastrowid
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT LASTVAL()")
            self._lastrowid = int(cur.fetchone()[0])
            cur.close()
        except Exception:
            pass
        return self._lastrowid

    @lastrowid.setter
    def lastrowid(self, value):
        self._lastrowid = value

    def fetchall(self):
        return [PGRow(r) for r in self._cur.fetchall()]

    def fetchone(self):
        row = self._cur.fetchone()
        return PGRow(row) if row else None

    def __iter__(self):
        for r in self._cur:
            yield PGRow(r)

    def close(self):
        if self._cur and not self._cur.closed:
            self._cur.close()


class PGConnection:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False

    def execute(self, sql: str, params: Any = None):
        sql = _convert_placeholders(sql)
        cur = self.conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(sql, params)
            return PGCursor(cur, self.conn)
        except Exception:
            cur.close()
            raise

    def executescript(self, script: str):
        cur = self.conn.cursor()
        try:
            cur.execute(script)
        finally:
            if not cur.closed:
                cur.close()

    def commit(self):
        self.conn.commit()

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


def get_connection(db_path: str | Path | None = None) -> PGConnection | sqlite3.Connection:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return PGConnection(dsn)
    from src.db.core import DEFAULT_DB_PATH
    path = db_path or os.getenv("OUTREACH_DB_PATH") or DEFAULT_DB_PATH
    p = Path(path) if isinstance(path, str) else path
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
