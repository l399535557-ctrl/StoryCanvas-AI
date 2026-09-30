from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SAVE_ID_CLEANER = re.compile(r"[^0-9A-Za-z_\-\u3400-\u9fff]+")
_ENGLISH_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{1,}")
_HAN_SEQUENCE = re.compile(r"[\u3400-\u9fff]{2,}")


def normalize_save_id(value: object, default: str = "default") -> str:
    cleaned = _SAVE_ID_CLEANER.sub("-", str(value or "").strip()).strip("-_")
    return (cleaned or default)[:80]


def _clean_text(value: object, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _clean_list(values: object, *, limit: int = 12) -> list[str]:
    if isinstance(values, str):
        raw: Iterable[object] = re.split(r"[,，、;；]", values)
    elif isinstance(values, (list, tuple, set)):
        raw = values
    else:
        raw = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        cleaned = _clean_text(item, 80)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _search_units(value: str) -> set[str]:
    folded = value.casefold()
    units = {match.group(0) for match in _ENGLISH_WORD.finditer(folded)}
    for match in _HAN_SEQUENCE.finditer(folded):
        sequence = match.group(0)
        units.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return units


@dataclass(frozen=True, slots=True)
class RetrievedMemory:
    id: int
    memory_type: str
    content: str
    tags: list[str]
    entities: list[str]
    importance: int
    story_time: str | None
    score: float


class MemoryStore:
    """SQLite-backed, save-isolated story memory with hybrid local retrieval."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_enabled = False
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS story_saves (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS story_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    save_id TEXT NOT NULL REFERENCES story_saves(id) ON DELETE CASCADE,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    save_id TEXT NOT NULL REFERENCES story_saves(id) ON DELETE CASCADE,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    entities_json TEXT NOT NULL DEFAULT '[]',
                    importance INTEGER NOT NULL DEFAULT 3,
                    story_time TEXT,
                    source_turn_id INTEGER REFERENCES story_turns(id) ON DELETE SET NULL,
                    fingerprint TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_accessed_at INTEGER,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    embedding_json TEXT,
                    UNIQUE(save_id, fingerprint)
                );

                CREATE INDEX IF NOT EXISTS idx_turns_save_created
                    ON story_turns(save_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_save_updated
                    ON memories(save_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_save_type
                    ON memories(save_id, memory_type);
                """
            )
            try:
                connection.executescript(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                        content,
                        tags,
                        entities,
                        content='memories',
                        content_rowid='id',
                        tokenize='unicode61'
                    );

                    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memory_fts(rowid, content, tags, entities)
                        VALUES (
                            new.id,
                            new.content,
                            new.tags_json,
                            new.entities_json
                        );
                    END;

                    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                        INSERT INTO memory_fts(memory_fts, rowid, content, tags, entities)
                        VALUES (
                            'delete',
                            old.id,
                            old.content,
                            old.tags_json,
                            old.entities_json
                        );
                    END;

                    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                        INSERT INTO memory_fts(memory_fts, rowid, content, tags, entities)
                        VALUES (
                            'delete',
                            old.id,
                            old.content,
                            old.tags_json,
                            old.entities_json
                        );
                        INSERT INTO memory_fts(rowid, content, tags, entities)
                        VALUES (
                            new.id,
                            new.content,
                            new.tags_json,
                            new.entities_json
                        );
                    END;
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False

    @property
    def fts_enabled(self) -> bool:
        return self._fts_enabled

    def ensure_save(self, save_id: object, name: str | None = None) -> str:
        normalized = normalize_save_id(save_id)
        display_name = _clean_text(name or normalized, 120) or normalized
        now = int(time.time())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO story_saves(id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = CASE
                        WHEN excluded.name = story_saves.id THEN story_saves.name
                        ELSE excluded.name
                    END,
                    updated_at = excluded.updated_at
                """,
                (normalized, display_name, now, now),
            )
        return normalized

    def list_saves(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.created_at,
                    s.updated_at,
                    COUNT(DISTINCT m.id) AS memory_count,
                    COUNT(DISTINCT t.id) AS turn_count
                FROM story_saves AS s
                LEFT JOIN memories AS m ON m.save_id = s.id
                LEFT JOIN story_turns AS t ON t.save_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_turn(self, save_id: object, user_text: str, assistant_text: str) -> int:
        normalized = self.ensure_save(save_id)
        now = int(time.time())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO story_turns(save_id, user_text, assistant_text, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    normalized,
                    _clean_text(user_text, 12000),
                    _clean_text(assistant_text, 24000),
                    now,
                ),
            )
            connection.execute(
                "UPDATE story_saves SET updated_at = ? WHERE id = ?",
                (now, normalized),
            )
            return int(cursor.lastrowid)

    def add_memory(
        self,
        save_id: object,
        *,
        memory_type: object,
        content: object,
        tags: object = None,
        entities: object = None,
        importance: object = 3,
        story_time: object = None,
        source_turn_id: int | None = None,
    ) -> int | None:
        normalized = self.ensure_save(save_id)
        clean_type = _clean_text(memory_type, 32).casefold() or "event"
        clean_content = _clean_text(content, 1000)
        if not clean_content:
            return None
        clean_tags = _clean_list(tags)
        clean_entities = _clean_list(entities, limit=10)
        try:
            clean_importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            clean_importance = 3
        clean_story_time = _clean_text(story_time, 120) or None
        fingerprint_source = f"{clean_type}|{clean_content.casefold()}"
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        now = int(time.time())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO memories(
                    save_id, memory_type, content, tags_json, entities_json,
                    importance, story_time, source_turn_id, fingerprint,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(save_id, fingerprint) DO UPDATE SET
                    tags_json = excluded.tags_json,
                    entities_json = excluded.entities_json,
                    importance = MAX(memories.importance, excluded.importance),
                    story_time = COALESCE(excluded.story_time, memories.story_time),
                    source_turn_id = COALESCE(excluded.source_turn_id, memories.source_turn_id),
                    updated_at = excluded.updated_at
                """,
                (
                    normalized,
                    clean_type,
                    clean_content,
                    json.dumps(clean_tags, ensure_ascii=False),
                    json.dumps(clean_entities, ensure_ascii=False),
                    clean_importance,
                    clean_story_time,
                    source_turn_id,
                    fingerprint,
                    now,
                    now,
                ),
            )
            if cursor.lastrowid:
                return int(cursor.lastrowid)
            row = connection.execute(
                "SELECT id FROM memories WHERE save_id = ? AND fingerprint = ?",
                (normalized, fingerprint),
            ).fetchone()
            return int(row["id"]) if row else None

    def _fts_candidates(
        self, connection: sqlite3.Connection, save_id: str, query: str, limit: int
    ) -> dict[int, float]:
        if not self._fts_enabled:
            return {}
        terms = []
        for match in _ENGLISH_WORD.finditer(query):
            term = match.group(0).casefold()
            if term not in terms:
                terms.append(term)
            if len(terms) >= 12:
                break
        if not terms:
            return {}
        match_query = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        try:
            rows = connection.execute(
                """
                SELECT m.id, bm25(memory_fts, 1.0, 1.7, 2.0) AS rank
                FROM memory_fts
                JOIN memories AS m ON m.id = memory_fts.rowid
                WHERE memory_fts MATCH ? AND m.save_id = ?
                ORDER BY rank
                LIMIT ?
                """,
                (match_query, save_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return {}
        return {
            int(row["id"]): 1.0 / (1.0 + max(0.0, float(row["rank"])))
            for row in rows
        }

    def retrieve(
        self,
        save_id: object,
        query: str,
        *,
        limit: int = 8,
        candidate_limit: int = 300,
    ) -> list[RetrievedMemory]:
        normalized = self.ensure_save(save_id)
        clean_query = _clean_text(query, 6000)
        query_units = _search_units(clean_query)
        query_folded = clean_query.casefold()
        if not query_units and not query_folded:
            return []

        with self._connect() as connection:
            fts_scores = self._fts_candidates(
                connection, normalized, clean_query, candidate_limit
            )
            rows = connection.execute(
                """
                SELECT * FROM memories
                WHERE save_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (normalized, candidate_limit),
            ).fetchall()

        now = int(time.time())
        ranked: list[RetrievedMemory] = []
        for row in rows:
            tags = json.loads(row["tags_json"] or "[]")
            entities = json.loads(row["entities_json"] or "[]")
            searchable = " ".join([row["content"], *tags, *entities])
            memory_units = _search_units(searchable)
            overlap = len(query_units & memory_units)
            lexical = overlap / max(1.0, math.sqrt(len(query_units) * len(memory_units)))
            entity_hits = sum(
                1 for entity in entities if entity and entity.casefold() in query_folded
            )
            tag_hits = sum(
                1 for tag in tags if tag and tag.casefold() in query_folded
            )
            age_days = max(0.0, (now - int(row["updated_at"])) / 86400.0)
            recency = 1.0 / (1.0 + age_days / 30.0)
            score = (
                lexical * 4.0
                + entity_hits * 1.5
                + tag_hits * 0.9
                + fts_scores.get(int(row["id"]), 0.0) * 1.2
                + (int(row["importance"]) - 1) * 0.12
                + recency * 0.15
            )
            if lexical <= 0 and entity_hits == 0 and tag_hits == 0 and row["id"] not in fts_scores:
                continue
            ranked.append(
                RetrievedMemory(
                    id=int(row["id"]),
                    memory_type=str(row["memory_type"]),
                    content=str(row["content"]),
                    tags=list(tags),
                    entities=list(entities),
                    importance=int(row["importance"]),
                    story_time=str(row["story_time"]) if row["story_time"] else None,
                    score=round(score, 4),
                )
            )

        selected = sorted(ranked, key=lambda item: (-item.score, -item.importance))[:limit]
        if selected:
            accessed_at = int(time.time())
            placeholders = ",".join("?" for _ in selected)
            with self._connect() as connection:
                connection.execute(
                    f"""
                    UPDATE memories
                    SET last_accessed_at = ?, access_count = access_count + 1
                    WHERE id IN ({placeholders})
                    """,
                    (accessed_at, *(item.id for item in selected)),
                )
        return selected

    def list_memories(self, save_id: object, *, limit: int = 100) -> list[dict[str, Any]]:
        normalized = self.ensure_save(save_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, memory_type, content, tags_json, entities_json,
                       importance, story_time, source_turn_id, created_at,
                       updated_at, last_accessed_at, access_count
                FROM memories
                WHERE save_id = ?
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (normalized, max(1, min(500, int(limit)))),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.pop("tags_json") or "[]")
            item["entities"] = json.loads(item.pop("entities_json") or "[]")
            result.append(item)
        return result

    def stats(self, save_id: object | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if save_id is None:
                save_count = int(
                    connection.execute("SELECT COUNT(*) FROM story_saves").fetchone()[0]
                )
                memory_count = int(
                    connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
                )
                turn_count = int(
                    connection.execute("SELECT COUNT(*) FROM story_turns").fetchone()[0]
                )
            else:
                normalized = normalize_save_id(save_id)
                save_count = 1
                memory_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM memories WHERE save_id = ?", (normalized,)
                    ).fetchone()[0]
                )
                turn_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM story_turns WHERE save_id = ?", (normalized,)
                    ).fetchone()[0]
                )
        return {
            "database": str(self.path),
            "fts_enabled": self._fts_enabled,
            "save_count": save_count,
            "memory_count": memory_count,
            "turn_count": turn_count,
        }
