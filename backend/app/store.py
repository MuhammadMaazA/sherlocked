"""SQLite store for cases and investigation snapshots. Video bytes stay in VAST."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    incident_start TEXT,
                    incident_end TEXT,
                    location TEXT,
                    status TEXT NOT NULL,
                    camera_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS investigations (
                    case_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playback (
                    id TEXT PRIMARY KEY,
                    segment_source TEXT,
                    parent_source TEXT,
                    start_seconds REAL,
                    end_seconds REAL
                );
                CREATE TABLE IF NOT EXISTS hits (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS safety_actions (
                    id TEXT PRIMARY KEY,
                    camera_code TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_case(self, data: dict[str, Any]) -> dict[str, Any]:
        now = utcnow()
        case = {
            "id": new_id("case"),
            "title": data["title"],
            "description": data["description"],
            "incident_start": data.get("incident_start"),
            "incident_end": data.get("incident_end"),
            "location": data.get("location"),
            "status": "open",
            "camera_ids": data.get("camera_ids") or [],
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO cases (
                    id, title, description, incident_start, incident_end, location,
                    status, camera_ids, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case["id"],
                    case["title"],
                    case["description"],
                    case["incident_start"],
                    case["incident_end"],
                    case["location"],
                    case["status"],
                    json.dumps(case["camera_ids"]),
                    case["created_at"],
                    case["updated_at"],
                ),
            )
        return self._with_count(case, 0)

    def _row_case(self, row: sqlite3.Row, count: int = 0) -> dict[str, Any]:
        return self._with_count(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "incident_start": row["incident_start"],
                "incident_end": row["incident_end"],
                "location": row["location"],
                "status": row["status"],
                "camera_ids": json.loads(row["camera_ids"] or "[]"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
            count,
        )

    def _with_count(self, case: dict[str, Any], count: int) -> dict[str, Any]:
        case["evidence_count"] = count
        return case

    def _count_for(self, connection: sqlite3.Connection, case_id: str) -> int:
        row = connection.execute("SELECT payload FROM investigations WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            return 0
        payload = json.loads(row["payload"])
        return len(payload.get("evidence") or [])

    def list_cases(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
            return [self._row_case(row, self._count_for(connection, row["id"])) for row in rows]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if not row:
                return None
            return self._row_case(row, self._count_for(connection, case_id))

    def set_status(self, case_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
                (status, utcnow(), case_id),
            )

    def save_investigation(self, case_id: str, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload)
        now = utcnow()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO investigations (case_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at
                """,
                (case_id, encoded, now),
            )
            connection.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE id = ?",
                ("ready", now, case_id),
            )
            connection.execute("DELETE FROM playback WHERE id IN (SELECT id FROM hits WHERE id LIKE 'ev_%')")
            for item in payload.get("evidence") or []:
                self._upsert_playback(connection, item)

    def get_investigation(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM investigations WHERE case_id = ?", (case_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def clear_messages(self, case_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM messages WHERE case_id = ?", (case_id,))

    def add_message(self, case_id: str, role: str, content: str, evidence_ids: list[str]) -> dict[str, Any]:
        message = {
            "id": new_id("msg"),
            "case_id": case_id,
            "role": role,
            "content": content,
            "evidence_ids": evidence_ids,
            "created_at": utcnow(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages (id, case_id, role, content, evidence_ids, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (message["id"], case_id, role, content, json.dumps(evidence_ids), message["created_at"]),
            )
        return message

    def list_messages(self, case_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE case_id = ? ORDER BY created_at ASC",
                (case_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "case_id": row["case_id"],
                "role": row["role"],
                "content": row["content"],
                "evidence_ids": json.loads(row["evidence_ids"] or "[]"),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_hits(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        saved = []
        with self._connect() as connection:
            for hit in hits:
                item = dict(hit)
                item["id"] = new_id("hit")
                item["case_id"] = None
                connection.execute(
                    "INSERT INTO hits (id, payload, created_at) VALUES (?, ?, ?)",
                    (item["id"], json.dumps(item), utcnow()),
                )
                self._upsert_playback(connection, item)
                saved.append(item)
            connection.execute(
                """
                DELETE FROM hits WHERE id NOT IN (
                    SELECT id FROM hits ORDER BY created_at DESC LIMIT 400
                )
                """
            )
        return saved

    def get_hit(self, hit_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM hits WHERE id = ?", (hit_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def _upsert_playback(self, connection: sqlite3.Connection, item: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT INTO playback (id, segment_source, parent_source, start_seconds, end_seconds)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                segment_source = excluded.segment_source,
                parent_source = excluded.parent_source,
                start_seconds = excluded.start_seconds,
                end_seconds = excluded.end_seconds
            """,
            (
                item["id"],
                item.get("source_segment_id"),
                item.get("source_video_id"),
                item.get("start_seconds"),
                item.get("end_seconds"),
            ),
        )

    def add_safety_action(
        self,
        camera_code: str,
        kind: str,
        title: str,
        body: str,
        status: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        action = {
            "id": new_id("act"),
            "camera_code": camera_code,
            "kind": kind,
            "title": title,
            "body": body,
            "status": status,
            "payload": payload,
            "created_at": utcnow(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO safety_actions (id, camera_code, kind, title, body, status, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action["id"],
                    action["camera_code"],
                    action["kind"],
                    action["title"],
                    action["body"],
                    action["status"],
                    json.dumps(payload),
                    action["created_at"],
                ),
            )
        return action

    def list_safety_actions(self, camera_code: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            if camera_code:
                rows = connection.execute(
                    "SELECT * FROM safety_actions WHERE camera_code = ? ORDER BY created_at DESC",
                    (camera_code,),
                ).fetchall()
            else:
                rows = connection.execute("SELECT * FROM safety_actions ORDER BY created_at DESC").fetchall()
        actions = []
        for row in rows:
            actions.append(
                {
                    "id": row["id"],
                    "camera_code": row["camera_code"],
                    "kind": row["kind"],
                    "title": row["title"],
                    "body": row["body"],
                    "status": row["status"],
                    "payload": json.loads(row["payload"] or "{}"),
                    "created_at": row["created_at"],
                }
            )
        return actions

    def get_safety_action(self, action_id: str) -> dict[str, Any] | None:
        for action in self.list_safety_actions():
            if action["id"] == action_id:
                return action
        return None

    def update_safety_action(self, action_id: str, body: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM safety_actions WHERE id = ?", (action_id,)).fetchone()
            if not row:
                return None
            next_payload = json.loads(row["payload"] or "{}")
            if payload:
                next_payload.update(payload)
            connection.execute(
                "UPDATE safety_actions SET body = ?, payload = ? WHERE id = ?",
                (body, json.dumps(next_payload), action_id),
            )
        return self.get_safety_action(action_id)

    def get_playback(self, item_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM playback WHERE id = ?", (item_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "segment_source": row["segment_source"],
            "parent_source": row["parent_source"],
            "start_seconds": row["start_seconds"],
            "end_seconds": row["end_seconds"],
        }
