import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from src.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE TABLE IF NOT EXISTS audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    query_type  TEXT,
    query       TEXT,
    intent      TEXT,
    confidence  REAL,
    reply       TEXT,
    action_logs TEXT,
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit(session_id, id);
"""


class LyraStore:
    """
    Single SQLite-backed store that unifies conversational memory and the audit
    trail (A3), replacing the previous throwaway ``history`` list and the two
    ad-hoc flat files (``lyra_audit.jsonl`` + ``lyra.log``).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        if self._conn is None:
            self._conn = await aiosqlite.connect(self.db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.executescript(_SCHEMA)
            await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        assert self._conn is not None
        await self._conn.execute(
            "INSERT INTO messages (session_id, role, content, ts) VALUES (?, ?, ?, ?)",
            (session_id, role, content, self._now()),
        )
        await self._conn.commit()

    async def get_history(self, session_id: str, limit: int = 8) -> List[Dict[str, str]]:
        """Return the most recent ``limit`` turns in chronological order."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def log_audit(
        self,
        session_id: str,
        query_type: str,
        query: str,
        final_state: Dict[str, Any],
    ) -> None:
        assert self._conn is not None
        await self._conn.execute(
            """INSERT INTO audit
               (session_id, query_type, query, intent, confidence, reply, action_logs, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                query_type,
                query,
                final_state.get("intent", "unknown"),
                float(final_state.get("confidence", 0.0)),
                final_state.get("final_response", ""),
                json.dumps(final_state.get("action_logs", []), ensure_ascii=False),
                self._now(),
            ),
        )
        await self._conn.commit()

    async def get_audit(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        assert self._conn is not None
        if session_id:
            cursor = await self._conn.execute(
                "SELECT * FROM audit WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            entry = dict(r)
            try:
                entry["action_logs"] = json.loads(entry.get("action_logs") or "[]")
            except json.JSONDecodeError:
                entry["action_logs"] = []
            result.append(entry)
        return result


store = LyraStore(settings.db_path)
