"""Notes: editable, human-authored annotations linked to experiments, agent versions,
tournaments, hands and decisions. Free text is never treated as verified data."""

from __future__ import annotations

import sqlite3
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from poker_lab.persistence.db import dumps, now_iso
from poker_lab.persistence.repositories import new_id

Category = Literal["observation", "hypothesis", "hand_review", "bug", "experiment_log", "decision_review"]
Severity = Literal["info", "low", "medium", "high"]
Status = Literal["open", "investigating", "resolved"]

LINK_TABLES = {
    "experiment_id": ("experiments", "experiment_id"),
    "agent_version_id": ("agent_versions", "agent_version_id"),
    "tournament_id": ("tournaments", "tournament_id"),
    "hand_id": ("hands", "hand_id"),
    "decision_id": ("decisions", "decision_id"),
}


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body_markdown: str = Field(default="", max_length=20_000)
    category: Category = "observation"
    severity: Severity = "info"
    status: Status = "open"
    tags: list[str] = Field(default_factory=list, max_length=20)
    author: str = Field(default="local", min_length=1, max_length=80)
    experiment_id: str | None = None
    agent_version_id: str | None = None
    tournament_id: str | None = None
    hand_id: str | None = None
    decision_id: str | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        out = []
        for t in v:
            t = t.strip().lower()
            if not t:
                continue
            if len(t) > 40:
                raise ValueError("tag too long")
            out.append(t)
        return sorted(set(out))

    @field_validator("experiment_id", "agent_version_id", "tournament_id", "hand_id", "decision_id", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Any) -> Any:
        return None if isinstance(v, str) and not v.strip() else v


class NoteLinkError(ValueError):
    pass


def _validate_links(conn: sqlite3.Connection, note: NoteIn) -> dict[str, str | None]:
    links: dict[str, str | None] = {}
    for field, (table, col) in LINK_TABLES.items():
        val = getattr(note, field)
        if val is not None and conn.execute(f"SELECT 1 FROM {table} WHERE {col}=?", (val,)).fetchone() is None:  # noqa: S608
            raise NoteLinkError(f"{field} {val!r} does not exist")
        links[field] = val
    # derive parent links from the most specific one so filters work at every level
    if links["decision_id"] and not links["hand_id"]:
        links["hand_id"] = conn.execute("SELECT hand_id FROM decisions WHERE decision_id=?", (links["decision_id"],)).fetchone()[0]
    if links["hand_id"] and not links["tournament_id"]:
        row = conn.execute("SELECT tournament_id FROM hands WHERE hand_id=?", (links["hand_id"],)).fetchone()
        links["tournament_id"] = row[0] if row else None
    if links["tournament_id"] and not links["experiment_id"]:
        row = conn.execute("SELECT experiment_id FROM tournaments WHERE tournament_id=?", (links["tournament_id"],)).fetchone()
        links["experiment_id"] = row[0] if row else None
    return links


def create_note(conn: sqlite3.Connection, note: NoteIn) -> str:
    links = _validate_links(conn, note)
    nid = new_id()
    ts = now_iso()
    conn.execute(
        "INSERT INTO notes(note_id,title,body_markdown,category,severity,status,tags_json,author,experiment_id,agent_version_id,"
        "tournament_id,hand_id,decision_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            nid,
            note.title,
            note.body_markdown,
            note.category,
            note.severity,
            note.status,
            dumps(note.tags),
            note.author,
            links["experiment_id"],
            links["agent_version_id"],
            links["tournament_id"],
            links["hand_id"],
            links["decision_id"],
            ts,
            ts,
        ),
    )
    return nid


def update_note(conn: sqlite3.Connection, note_id: str, note: NoteIn) -> None:
    if get_note(conn, note_id) is None:
        raise KeyError(note_id)
    links = _validate_links(conn, note)
    conn.execute(
        "UPDATE notes SET title=?, body_markdown=?, category=?, severity=?, status=?, tags_json=?, author=?, experiment_id=?,"
        " agent_version_id=?, tournament_id=?, hand_id=?, decision_id=?, updated_at=? WHERE note_id=?",
        (
            note.title,
            note.body_markdown,
            note.category,
            note.severity,
            note.status,
            dumps(note.tags),
            note.author,
            links["experiment_id"],
            links["agent_version_id"],
            links["tournament_id"],
            links["hand_id"],
            links["decision_id"],
            now_iso(),
            note_id,
        ),
    )


def delete_note(conn: sqlite3.Connection, note_id: str) -> bool:
    return conn.execute("DELETE FROM notes WHERE note_id=?", (note_id,)).rowcount > 0


def get_note(conn: sqlite3.Connection, note_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM notes WHERE note_id=?", (note_id,)).fetchone()
    return dict(row) if row else None


def list_notes(
    conn: sqlite3.Connection,
    *,
    tournament_id: str | None = None,
    hand_id: str | None = None,
    decision_id: str | None = None,
    experiment_id: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    clauses, params = [], []
    for col, val in (
        ("tournament_id", tournament_id),
        ("hand_id", hand_id),
        ("decision_id", decision_id),
        ("experiment_id", experiment_id),
        ("status", status),
    ):
        if val:
            clauses.append(f"{col}=?")
            params.append(val)
    if tag:
        clauses.append("EXISTS (SELECT 1 FROM json_each(notes.tags_json) WHERE value=?)")
        params.append(tag.lower())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM notes {where} ORDER BY updated_at DESC LIMIT ?", (*params, limit)).fetchall()  # noqa: S608
    return [dict(r) for r in rows]
