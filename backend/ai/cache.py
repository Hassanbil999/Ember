"""ai_cache (SPEC §5): key = sha256 of prompt + inputs + model, response JSON, created_at. SQLite next to the
processed tables; a cache miss or a write error never breaks a request."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone

from ..core.config import PROCESSED

_lock = threading.Lock()
PATH = PROCESSED / "ai_cache.sqlite"


def key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _con():
    con = sqlite3.connect(PATH)
    con.execute("CREATE TABLE IF NOT EXISTS ai_cache (key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at TEXT NOT NULL)")
    return con


def get(k: str) -> dict | None:
    try:
        with _lock, _con() as con:
            row = con.execute("SELECT response FROM ai_cache WHERE key = ?", (k,)).fetchone()
        return json.loads(row[0]) if row else None
    except Exception:
        return None


def put(k: str, response: dict) -> None:
    try:
        with _lock, _con() as con:
            con.execute("INSERT OR REPLACE INTO ai_cache VALUES (?, ?, ?)",
                        (k, json.dumps(response, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
    except Exception:
        pass
