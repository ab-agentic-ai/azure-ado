"""Small local user memory for DevOps-Agent; stores preferences, never ADO result sets."""

from __future__ import annotations

import hashlib
import os
import sqlite3


def _db_path() -> str:
    return os.getenv("DEVOPS_AGENT_MEMORY_DB", "/data/devops-agent-memory.sqlite3")


def _user_key(user_id: str | None) -> str:
    return hashlib.sha256((user_id or "default-user").encode("utf-8")).hexdigest()


def read_context(user_id: str | None) -> dict[str, str]:
    path = _db_path()
    if not os.path.exists(path):
        return {}
    try:
        with sqlite3.connect(path, timeout=3) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS user_context ("
                "user_key TEXT PRIMARY KEY, last_project TEXT, last_topic TEXT)"
            )
            row = db.execute(
                "SELECT last_project, last_topic FROM user_context WHERE user_key = ?",
                (_user_key(user_id),),
            ).fetchone()
        if not row:
            return {}
        return {key: value for key, value in zip(("last_project", "last_topic"), row) if value}
    except sqlite3.Error:
        return {}


def remember_context(user_id: str | None, project: str | None, topic: str | None) -> None:
    """Persist the latest useful project/topic hint for follow-up questions in new chats."""
    if not project and not topic:
        return
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
    try:
        with sqlite3.connect(path, timeout=3) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS user_context ("
                "user_key TEXT PRIMARY KEY, last_project TEXT, last_topic TEXT)"
            )
            db.execute(
                "INSERT INTO user_context (user_key, last_project, last_topic) VALUES (?, ?, ?) "
                "ON CONFLICT(user_key) DO UPDATE SET "
                "last_project = COALESCE(excluded.last_project, user_context.last_project), "
                "last_topic = COALESCE(excluded.last_topic, user_context.last_topic)",
                (_user_key(user_id), project[:200] if project else None, topic[:60] if topic else None),
            )
    except sqlite3.Error:
        # Memory is helpful context, not a dependency for answering ADO queries.
        return
