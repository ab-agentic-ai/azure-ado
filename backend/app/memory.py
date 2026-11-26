"""Small local user memory for DevOps-Agent; stores preferences, never ADO result sets."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone


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


def remember_agent_issue(user_id: str | None, topic: str, error_kind: str) -> int:
    """Persist a privacy-safe failure signature; never store prompts, tokens, or ADO data."""
    allowed_topics = {"projects", "project details", "project overview", "repositories", "branches", "pull requests", "policies", "permissions", "access review", "teams", "pipelines", "pipeline runs", "work items", "areas", "iterations", "test plans", "test runs", "feeds", "packages", "agent pools", "library groups", "environments", "release readiness", "delivery flow", "other"}
    allowed_errors = {"unexpected", "network", "rate_limited", "access_denied", "not_found", "invalid_response"}
    topic = topic if topic in allowed_topics else "other"
    error_kind = error_kind if error_kind in allowed_errors else "unexpected"
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
    try:
        with sqlite3.connect(path, timeout=3) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS agent_issues ("
                "user_key TEXT NOT NULL, topic TEXT NOT NULL, error_kind TEXT NOT NULL, "
                "occurrences INTEGER NOT NULL DEFAULT 1, last_seen TEXT NOT NULL, "
                "PRIMARY KEY (user_key, topic, error_kind))"
            )
            db.execute(
                "INSERT INTO agent_issues (user_key, topic, error_kind, occurrences, last_seen) "
                "VALUES (?, ?, ?, 1, ?) ON CONFLICT(user_key, topic, error_kind) DO UPDATE SET "
                "occurrences = occurrences + 1, last_seen = excluded.last_seen",
                (_user_key(user_id), topic, error_kind, datetime.now(timezone.utc).isoformat()),
            )
            row = db.execute(
                "SELECT occurrences FROM agent_issues WHERE user_key = ? AND topic = ? AND error_kind = ?",
                (_user_key(user_id), topic, error_kind),
            ).fetchone()
            return int(row[0]) if row else 1
    except sqlite3.Error:
        return 1


def clear_agent_issue(user_id: str | None, topic: str) -> None:
    """Clear stored failure fingerprints for an operation after it succeeds."""
    path = _db_path()
    if not os.path.exists(path):
        return
    try:
        with sqlite3.connect(path, timeout=3) as db:
            db.execute("DELETE FROM agent_issues WHERE user_key = ? AND topic = ?", (_user_key(user_id), topic))
    except sqlite3.Error:
        return
