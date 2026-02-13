from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


class SQLiteCache:
    def __init__(self, db_path: str | Path, ttl_seconds: int = 86400):
        self.db_path = str(db_path)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def get(self, key: str) -> dict | None:
        now = time.time()
        with self._lock, sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value, created_at FROM cache WHERE key = ?", (key,)
            ).fetchone()
            if not row:
                return None
            payload, created_at = row
            if now - float(created_at) > self.ttl_seconds:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None
            conn.execute("UPDATE cache SET hits = hits + 1 WHERE key = ?", (key,))
            conn.commit()
            return json.loads(payload)

    def set(self, key: str, value: dict) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cache(key, value, created_at, hits)
                VALUES (?, ?, ?, 0)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    created_at = excluded.created_at
                """,
                (key, json.dumps(value), time.time()),
            )
            conn.commit()

    def clear(self) -> None:
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()
