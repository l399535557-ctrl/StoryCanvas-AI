from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import uuid
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
        self._maintenance_lock = threading.RLock()
        self._fts_enabled = False
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._maintenance_lock:
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
                    updated_at INTEGER NOT NULL,
                    archived_at INTEGER
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
                    archived_at INTEGER,
                    status TEXT NOT NULL DEFAULT 'active',
                    supersedes_memory_id INTEGER,
                    UNIQUE(save_id, fingerprint)
                );

                CREATE INDEX IF NOT EXISTS idx_turns_save_created
                    ON story_turns(save_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_save_updated
                    ON memories(save_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_save_type
                    ON memories(save_id, memory_type);

                CREATE TABLE IF NOT EXISTS generation_tasks (
                    id TEXT PRIMARY KEY,
                    save_id TEXT NOT NULL REFERENCES story_saves(id) ON DELETE CASCADE,
                    request_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    image_filename TEXT,
                    error TEXT,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    finished_at INTEGER,
                    duration_seconds REAL,
                    prompt_id TEXT,
                    positive_prompt TEXT,
                    negative_prompt TEXT,
                    retry_of_task_id TEXT,
                    backend TEXT NOT NULL DEFAULT 'comfy-sdxl',
                    turn_id INTEGER REFERENCES story_turns(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_generation_tasks_save_created
                    ON generation_tasks(save_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_generation_tasks_status
                    ON generation_tasks(status, created_at DESC);
                """
            )
            save_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(story_saves)").fetchall()
            }
            if "archived_at" not in save_columns:
                connection.execute("ALTER TABLE story_saves ADD COLUMN archived_at INTEGER")
            memory_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "archived_at" not in memory_columns:
                connection.execute("ALTER TABLE memories ADD COLUMN archived_at INTEGER")
            if "status" not in memory_columns:
                connection.execute(
                    "ALTER TABLE memories ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
                )
            if "supersedes_memory_id" not in memory_columns:
                connection.execute(
                    "ALTER TABLE memories ADD COLUMN supersedes_memory_id INTEGER"
                )
            task_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(generation_tasks)").fetchall()
            }
            for column, definition in {
                "prompt_id": "TEXT",
                "positive_prompt": "TEXT",
                "negative_prompt": "TEXT",
                "retry_of_task_id": "TEXT",
                "backend": "TEXT NOT NULL DEFAULT 'comfy-sdxl'",
                "turn_id": "INTEGER REFERENCES story_turns(id) ON DELETE SET NULL",
            }.items():
                if column not in task_columns:
                    connection.execute(
                        f"ALTER TABLE generation_tasks ADD COLUMN {column} {definition}"
                    )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_generation_tasks_turn "
                "ON generation_tasks(turn_id, created_at DESC)"
            )
            connection.execute("PRAGMA user_version = 7")
            connection.execute(
                """
                UPDATE generation_tasks
                SET status = 'failed', error = 'interrupted by service restart',
                    finished_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (int(time.time()),),
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

    def list_saves(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.created_at,
                    s.updated_at,
                    s.archived_at,
                    COUNT(DISTINCT m.id) AS memory_count,
                    COUNT(DISTINCT t.id) AS turn_count
                FROM story_saves AS s
                LEFT JOIN memories AS m ON m.save_id = s.id AND m.archived_at IS NULL
                LEFT JOIN story_turns AS t ON t.save_id = s.id
                WHERE (? = 1 OR s.archived_at IS NULL)
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                """,
                (1 if include_archived else 0,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_save(self, save_id: object) -> dict[str, Any] | None:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    s.id, s.name, s.created_at, s.updated_at, s.archived_at,
                    COUNT(DISTINCT m.id) AS memory_count,
                    COUNT(DISTINCT t.id) AS turn_count
                FROM story_saves AS s
                LEFT JOIN memories AS m ON m.save_id = s.id AND m.archived_at IS NULL
                LEFT JOIN story_turns AS t ON t.save_id = s.id
                WHERE s.id = ?
                GROUP BY s.id
                """,
                (normalized,),
            ).fetchone()
        return dict(row) if row else None

    def rename_save(self, save_id: object, name: object) -> bool:
        normalized = normalize_save_id(save_id)
        clean_name = _clean_text(name, 120)
        if not clean_name:
            raise ValueError("save name is required")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE story_saves
                SET name = ?, updated_at = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (clean_name, int(time.time()), normalized),
            )
        return cursor.rowcount > 0

    def archive_save(self, save_id: object) -> bool:
        normalized = normalize_save_id(save_id)
        now = int(time.time())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE story_saves
                SET archived_at = ?, updated_at = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (now, now, normalized),
            )
        return cursor.rowcount > 0

    def restore_save(self, save_id: object) -> bool:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE story_saves
                SET archived_at = NULL, updated_at = ?
                WHERE id = ? AND archived_at IS NOT NULL
                """,
                (int(time.time()), normalized),
            )
        return cursor.rowcount > 0

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

    def list_turns(
        self,
        save_id: object,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        normalized = normalize_save_id(save_id)
        clean_limit = max(1, min(200, int(limit)))
        clean_offset = max(0, int(offset))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_text, assistant_text, created_at
                FROM story_turns
                WHERE save_id = ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (normalized, clean_limit, clean_offset),
            ).fetchall()
            turn_ids = [int(row["id"]) for row in rows]
            tasks_by_turn: dict[int, list[dict[str, Any]]] = {
                turn_id: [] for turn_id in turn_ids
            }
            if turn_ids:
                placeholders = ",".join("?" for _ in turn_ids)
                task_rows = connection.execute(
                    f"""
                    SELECT id, turn_id, request_id, status, image_filename, error,
                           created_at, started_at, finished_at, duration_seconds,
                           prompt_id, retry_of_task_id, backend
                    FROM generation_tasks
                    WHERE turn_id IN ({placeholders})
                    ORDER BY created_at, id
                    """,
                    turn_ids,
                ).fetchall()
                for task in task_rows:
                    tasks_by_turn[int(task["turn_id"])].append(dict(task))
        return [
            {**dict(row), "image_tasks": tasks_by_turn[int(row["id"])]}
            for row in rows
        ]

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
            existing = connection.execute(
                """
                SELECT id, archived_at FROM memories
                WHERE save_id = ? AND fingerprint = ?
                """,
                (normalized, fingerprint),
            ).fetchone()
            if existing is not None and existing["archived_at"] is not None:
                return int(existing["id"])
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
                WHERE memory_fts MATCH ? AND m.save_id = ? AND m.archived_at IS NULL
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
                WHERE save_id = ? AND archived_at IS NULL AND status = 'active'
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

    def list_memories(
        self,
        save_id: object,
        *,
        limit: int = 100,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, memory_type, content, tags_json, entities_json,
                       importance, story_time, source_turn_id, created_at,
                       updated_at, last_accessed_at, access_count, archived_at,
                       status, supersedes_memory_id
                FROM memories
                WHERE save_id = ? AND (? = 1 OR archived_at IS NULL)
                ORDER BY importance DESC, updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (
                    normalized,
                    1 if include_archived else 0,
                    max(1, min(500, int(limit))),
                    max(0, int(offset)),
                ),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.pop("tags_json") or "[]")
            item["entities"] = json.loads(item.pop("entities_json") or "[]")
            result.append(item)
        return result

    def get_memory(self, save_id: object, memory_id: int) -> dict[str, Any] | None:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, memory_type, content, tags_json, entities_json,
                       importance, story_time, source_turn_id, created_at,
                       updated_at, last_accessed_at, access_count, archived_at,
                       status, supersedes_memory_id
                FROM memories
                WHERE id = ? AND save_id = ?
                """,
                (int(memory_id), normalized),
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["tags"] = json.loads(item.pop("tags_json") or "[]")
        item["entities"] = json.loads(item.pop("entities_json") or "[]")
        return item

    def update_memory(
        self,
        save_id: object,
        memory_id: int,
        *,
        memory_type: object,
        content: object,
        tags: object = None,
        entities: object = None,
        importance: object = 3,
        story_time: object = None,
    ) -> bool:
        normalized = normalize_save_id(save_id)
        clean_type = _clean_text(memory_type, 32).casefold() or "event"
        clean_content = _clean_text(content, 1000)
        if not clean_content:
            raise ValueError("memory content is required")
        clean_tags = _clean_list(tags)
        clean_entities = _clean_list(entities, limit=10)
        try:
            clean_importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            clean_importance = 3
        clean_story_time = _clean_text(story_time, 120) or None
        fingerprint = hashlib.sha256(
            f"{clean_type}|{clean_content.casefold()}".encode()
        ).hexdigest()
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET memory_type = ?, content = ?, tags_json = ?, entities_json = ?,
                        importance = ?, story_time = ?, fingerprint = ?, updated_at = ?
                    WHERE id = ? AND save_id = ? AND archived_at IS NULL
                    """,
                    (
                        clean_type,
                        clean_content,
                        json.dumps(clean_tags, ensure_ascii=False),
                        json.dumps(clean_entities, ensure_ascii=False),
                        clean_importance,
                        clean_story_time,
                        fingerprint,
                        int(time.time()),
                        int(memory_id),
                        normalized,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("an identical memory already exists in this save") from exc
        return cursor.rowcount > 0

    def archive_memory(self, save_id: object, memory_id: int) -> bool:
        normalized = normalize_save_id(save_id)
        now = int(time.time())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET archived_at = ?, updated_at = ?
                WHERE id = ? AND save_id = ? AND archived_at IS NULL
                """,
                (now, now, int(memory_id), normalized),
            )
        return cursor.rowcount > 0

    def restore_memory(self, save_id: object, memory_id: int) -> bool:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET archived_at = NULL, updated_at = ?
                WHERE id = ? AND save_id = ? AND archived_at IS NOT NULL
                """,
                (int(time.time()), int(memory_id), normalized),
            )
        return cursor.rowcount > 0

    def set_memory_status(
        self,
        save_id: object,
        memory_id: int,
        status: str,
    ) -> bool:
        normalized = normalize_save_id(save_id)
        clean_status = str(status).strip().casefold()
        if clean_status not in {"active", "conflicted", "superseded"}:
            raise ValueError("unsupported memory status")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE memories
                SET status = ?, updated_at = ?
                WHERE id = ? AND save_id = ? AND archived_at IS NULL
                """,
                (clean_status, int(time.time()), int(memory_id), normalized),
            )
        return cursor.rowcount > 0

    def supersede_memory(
        self,
        save_id: object,
        memory_id: int,
        *,
        memory_type: object,
        content: object,
        tags: object = None,
        entities: object = None,
        importance: object = 3,
        story_time: object = None,
    ) -> int:
        """Atomically replace an active memory and retain its revision lineage."""
        normalized = normalize_save_id(save_id)
        clean_type = _clean_text(memory_type, 32).casefold() or "event"
        clean_content = _clean_text(content, 1000)
        if not clean_content:
            raise ValueError("memory content is required")
        clean_tags = _clean_list(tags)
        clean_entities = _clean_list(entities, limit=10)
        try:
            clean_importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            clean_importance = 3
        clean_story_time = _clean_text(story_time, 120) or None
        fingerprint = hashlib.sha256(
            f"{clean_type}|{clean_content.casefold()}".encode()
        ).hexdigest()
        now = int(time.time())
        try:
            with self._connect() as connection:
                existing = connection.execute(
                    """
                    SELECT id FROM memories
                    WHERE id = ? AND save_id = ? AND archived_at IS NULL
                    """,
                    (int(memory_id), normalized),
                ).fetchone()
                if existing is None:
                    raise KeyError("memory not found")
                cursor = connection.execute(
                    """
                    INSERT INTO memories(
                        save_id, memory_type, content, tags_json, entities_json,
                        importance, story_time, fingerprint, created_at, updated_at,
                        status, supersedes_memory_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        normalized,
                        clean_type,
                        clean_content,
                        json.dumps(clean_tags, ensure_ascii=False),
                        json.dumps(clean_entities, ensure_ascii=False),
                        clean_importance,
                        clean_story_time,
                        fingerprint,
                        now,
                        now,
                        int(memory_id),
                    ),
                )
                replacement_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE memories
                    SET status = 'superseded', updated_at = ?
                    WHERE id = ? AND save_id = ?
                    """,
                    (now, int(memory_id), normalized),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("an identical memory already exists in this save") from exc
        return replacement_id

    def export_save(
        self,
        save_id: object,
        *,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        """Return a portable, versioned JSON representation of one story save."""
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            save = connection.execute(
                """
                SELECT id, name, created_at, updated_at, archived_at
                FROM story_saves
                WHERE id = ?
                """,
                (normalized,),
            ).fetchone()
            if save is None:
                raise KeyError("story save not found")
            turns = connection.execute(
                """
                SELECT id, user_text, assistant_text, created_at
                FROM story_turns
                WHERE save_id = ?
                ORDER BY id
                """,
                (normalized,),
            ).fetchall()
            memories = connection.execute(
                """
                SELECT id, memory_type, content, tags_json, entities_json,
                       importance, story_time, source_turn_id, created_at,
                       updated_at, archived_at, status, supersedes_memory_id
                FROM memories
                WHERE save_id = ? AND (? = 1 OR archived_at IS NULL)
                ORDER BY id
                """,
                (normalized, 1 if include_archived else 0),
            ).fetchall()

        exported_memories: list[dict[str, Any]] = []
        for row in memories:
            item = dict(row)
            item["tags"] = json.loads(item.pop("tags_json") or "[]")
            item["entities"] = json.loads(item.pop("entities_json") or "[]")
            exported_memories.append(item)
        return {
            "format": "storycanvas-save",
            "version": 1,
            "exported_at": int(time.time()),
            "save": dict(save),
            "turns": [dict(row) for row in turns],
            "memories": exported_memories,
        }

    def import_save(
        self,
        bundle: dict[str, Any],
        *,
        target_save_id: object = None,
        target_name: object = None,
    ) -> dict[str, Any]:
        """Atomically import a portable save bundle without overwriting existing data."""
        if bundle.get("format") != "storycanvas-save" or bundle.get("version") != 1:
            raise ValueError("unsupported story save bundle")
        source_save = bundle.get("save")
        turns = bundle.get("turns", [])
        memories = bundle.get("memories", [])
        if not isinstance(source_save, dict):
            raise ValueError("bundle save metadata is required")
        if not isinstance(turns, list) or len(turns) > 10000:
            raise ValueError("bundle turns must be a list with at most 10000 items")
        if not isinstance(memories, list) or len(memories) > 20000:
            raise ValueError("bundle memories must be a list with at most 20000 items")

        normalized = normalize_save_id(target_save_id or source_save.get("id"))
        clean_name = _clean_text(target_name or source_save.get("name") or normalized, 120)
        now = int(time.time())
        try:
            created_at = int(source_save.get("created_at") or now)
        except (TypeError, ValueError):
            created_at = now

        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM story_saves WHERE id = ?",
                (normalized,),
            ).fetchone()
            if exists is not None:
                raise ValueError("target story save already exists")
            connection.execute(
                """
                INSERT INTO story_saves(id, name, created_at, updated_at, archived_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (normalized, clean_name or normalized, created_at, now),
            )

            turn_id_map: dict[int, int] = {}
            for item in turns:
                if not isinstance(item, dict):
                    raise ValueError("invalid turn in story save bundle")
                user_text = _clean_text(item.get("user_text"), 12000)
                assistant_text = _clean_text(item.get("assistant_text"), 24000)
                try:
                    item_created_at = int(item.get("created_at") or now)
                except (TypeError, ValueError):
                    item_created_at = now
                cursor = connection.execute(
                    """
                    INSERT INTO story_turns(save_id, user_text, assistant_text, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (normalized, user_text, assistant_text, item_created_at),
                )
                try:
                    old_id = int(item.get("id"))
                except (TypeError, ValueError):
                    old_id = 0
                if old_id:
                    turn_id_map[old_id] = int(cursor.lastrowid)

            imported_memory_count = 0
            memory_id_map: dict[int, int] = {}
            for item in memories:
                if not isinstance(item, dict):
                    raise ValueError("invalid memory in story save bundle")
                clean_type = _clean_text(item.get("memory_type"), 32).casefold() or "event"
                clean_content = _clean_text(item.get("content"), 1000)
                if not clean_content:
                    continue
                clean_tags = _clean_list(item.get("tags"))
                clean_entities = _clean_list(item.get("entities"), limit=10)
                try:
                    importance = max(1, min(5, int(item.get("importance", 3))))
                except (TypeError, ValueError):
                    importance = 3
                story_time = _clean_text(item.get("story_time"), 120) or None
                fingerprint = hashlib.sha256(
                    f"{clean_type}|{clean_content.casefold()}".encode()
                ).hexdigest()
                try:
                    old_source_turn_id = int(item.get("source_turn_id"))
                except (TypeError, ValueError):
                    old_source_turn_id = 0
                source_turn_id = turn_id_map.get(old_source_turn_id)
                archived_at = item.get("archived_at")
                try:
                    archived_at = int(archived_at) if archived_at is not None else None
                except (TypeError, ValueError):
                    archived_at = None
                status = str(item.get("status") or "active").strip().casefold()
                if status not in {"active", "conflicted", "superseded"}:
                    status = "active"
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO memories(
                        save_id, memory_type, content, tags_json, entities_json,
                        importance, story_time, source_turn_id, fingerprint,
                        created_at, updated_at, archived_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized,
                        clean_type,
                        clean_content,
                        json.dumps(clean_tags, ensure_ascii=False),
                        json.dumps(clean_entities, ensure_ascii=False),
                        importance,
                        story_time,
                        source_turn_id,
                        fingerprint,
                        now,
                        now,
                        archived_at,
                        status,
                    ),
                )
                imported_memory_count += cursor.rowcount
                try:
                    old_memory_id = int(item.get("id"))
                except (TypeError, ValueError):
                    old_memory_id = 0
                if old_memory_id and cursor.rowcount:
                    memory_id_map[old_memory_id] = int(cursor.lastrowid)

            for item in memories:
                if not isinstance(item, dict):
                    continue
                try:
                    old_memory_id = int(item.get("id"))
                    old_supersedes_id = int(item.get("supersedes_memory_id"))
                except (TypeError, ValueError):
                    continue
                new_memory_id = memory_id_map.get(old_memory_id)
                new_supersedes_id = memory_id_map.get(old_supersedes_id)
                if new_memory_id and new_supersedes_id:
                    connection.execute(
                        """
                        UPDATE memories SET supersedes_memory_id = ?
                        WHERE id = ? AND save_id = ?
                        """,
                        (new_supersedes_id, new_memory_id, normalized),
                    )

        return {
            "save_id": normalized,
            "name": clean_name or normalized,
            "turn_count": len(turns),
            "memory_count": imported_memory_count,
        }

    def copy_save(
        self,
        source_save_id: object,
        target_save_id: object,
        target_name: object,
    ) -> dict[str, Any]:
        bundle = self.export_save(source_save_id, include_archived=False)
        return self.import_save(
            bundle,
            target_save_id=target_save_id,
            target_name=target_name,
        )

    def create_generation_task(
        self,
        save_id: object,
        request_id: object,
        *,
        retry_of_task_id: object = None,
        backend: object = "comfy-sdxl",
        turn_id: int | None = None,
    ) -> str:
        normalized = self.ensure_save(save_id)
        task_id = uuid.uuid4().hex
        now = int(time.time())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_tasks(
                    id, save_id, request_id, status, created_at, retry_of_task_id,
                    backend, turn_id
                ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    task_id,
                    normalized,
                    _clean_text(request_id, 64) or "-",
                    now,
                    _clean_text(retry_of_task_id, 64) or None,
                    _clean_text(backend, 64) or "comfy-sdxl",
                    turn_id,
                ),
            )
        return task_id

    def link_generation_task_to_turn(
        self,
        task_id: object,
        save_id: object,
        turn_id: int,
    ) -> bool:
        normalized = normalize_save_id(save_id)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks SET turn_id = ?
                WHERE id = ? AND save_id = ? AND EXISTS (
                    SELECT 1 FROM story_turns
                    WHERE id = ? AND save_id = ?
                )
                """,
                (
                    int(turn_id),
                    _clean_text(task_id, 64),
                    normalized,
                    int(turn_id),
                    normalized,
                ),
            )
        return cursor.rowcount > 0

    def set_generation_task_prompts(
        self,
        task_id: object,
        positive_prompt: object,
        negative_prompt: object,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks
                SET positive_prompt = ?, negative_prompt = ?
                WHERE id = ? AND status = 'queued'
                """,
                (
                    _clean_text(positive_prompt, 12000),
                    _clean_text(negative_prompt, 6000),
                    _clean_text(task_id, 64),
                ),
            )
        return cursor.rowcount > 0

    def set_generation_task_prompt_id(self, task_id: object, prompt_id: object) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks SET prompt_id = ?
                WHERE id = ? AND status = 'running'
                """,
                (_clean_text(prompt_id, 120), _clean_text(task_id, 64)),
            )
        return cursor.rowcount > 0

    def cancel_generation_task(self, task_id: object) -> bool:
        now = int(time.time())
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks
                SET status = 'cancelled', finished_at = ?, error = 'cancelled by user'
                WHERE id = ? AND status IN ('queued', 'running')
                """,
                (now, _clean_text(task_id, 64)),
            )
        return cursor.rowcount > 0

    def update_generation_task(
        self,
        task_id: str,
        status: str,
        *,
        image_filename: object = None,
        error: object = None,
        duration_seconds: float | None = None,
    ) -> bool:
        clean_status = str(status).strip().casefold()
        if clean_status not in {"queued", "running", "succeeded", "failed", "cancelled"}:
            raise ValueError("unsupported generation task status")
        now = int(time.time())
        started_at = now if clean_status == "running" else None
        finished_at = now if clean_status in {"succeeded", "failed", "cancelled"} else None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE generation_tasks
                SET status = ?,
                    image_filename = COALESCE(?, image_filename),
                    error = ?,
                    started_at = COALESCE(started_at, ?),
                    finished_at = ?,
                    duration_seconds = COALESCE(?, duration_seconds)
                WHERE id = ? AND (? = 'cancelled' OR status != 'cancelled')
                """,
                (
                    clean_status,
                    _clean_text(image_filename, 255) or None,
                    _clean_text(error, 1000) or None,
                    started_at,
                    finished_at,
                    duration_seconds,
                    _clean_text(task_id, 64),
                    clean_status,
                ),
            )
        return cursor.rowcount > 0

    def get_generation_task(self, task_id: object) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, save_id, request_id, status, image_filename, error,
                       created_at, started_at, finished_at, duration_seconds,
                       prompt_id, retry_of_task_id, backend, turn_id
                FROM generation_tasks WHERE id = ?
                """,
                (_clean_text(task_id, 64),),
            ).fetchone()
        return dict(row) if row else None

    def get_generation_task_payload(self, task_id: object) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, save_id, request_id, status, positive_prompt,
                       negative_prompt, retry_of_task_id, backend, turn_id
                FROM generation_tasks WHERE id = ?
                """,
                (_clean_text(task_id, 64),),
            ).fetchone()
        return dict(row) if row else None

    def list_generation_tasks(
        self,
        *,
        save_id: object = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        normalized = normalize_save_id(save_id) if save_id is not None else None
        clean_status = status.strip().casefold() if status else None
        if clean_status not in {None, "queued", "running", "succeeded", "failed", "cancelled"}:
            raise ValueError("unsupported generation task status")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, save_id, request_id, status, image_filename, error,
                       created_at, started_at, finished_at, duration_seconds,
                       prompt_id, retry_of_task_id, backend, turn_id
                FROM generation_tasks
                WHERE (? IS NULL OR save_id = ?) AND (? IS NULL OR status = ?)
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    normalized,
                    normalized,
                    clean_status,
                    clean_status,
                    max(1, min(500, int(limit))),
                    max(0, int(offset)),
                ),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _validated_backup_path(backup_directory: Path, filename: object) -> Path:
        raw_name = str(filename or "").strip()
        safe_name = Path(raw_name).name
        if raw_name != safe_name or not safe_name.startswith("storycanvas-"):
            raise ValueError("invalid backup filename")
        if not safe_name.endswith(".sqlite3"):
            raise ValueError("backup must be a .sqlite3 file")
        return backup_directory / safe_name

    def create_database_backup(
        self,
        backup_directory: Path,
        *,
        label: object = None,
    ) -> dict[str, Any]:
        backup_directory.mkdir(parents=True, exist_ok=True)
        clean_label = normalize_save_id(label, "") if label else ""
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        suffix = f"-{clean_label}" if clean_label else ""
        filename = f"storycanvas-{stamp}-{uuid.uuid4().hex[:8]}{suffix}.sqlite3"
        destination = backup_directory / filename
        with self._maintenance_lock:
            source = sqlite3.connect(self.path, timeout=10.0)
            target = sqlite3.connect(destination, timeout=10.0)
            try:
                source.backup(target)
                result = target.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise ValueError("database backup failed integrity check")
                schema_version = int(target.execute("PRAGMA user_version").fetchone()[0])
            finally:
                target.close()
                source.close()
        stat = destination.stat()
        return {
            "filename": filename,
            "size_bytes": stat.st_size,
            "created_at": int(stat.st_mtime),
            "schema_version": schema_version,
        }

    def list_database_backups(self, backup_directory: Path) -> list[dict[str, Any]]:
        if not backup_directory.is_dir():
            return []
        result: list[dict[str, Any]] = []
        for path in backup_directory.glob("storycanvas-*.sqlite3"):
            if not path.is_file():
                continue
            stat = path.stat()
            result.append(
                {
                    "filename": path.name,
                    "size_bytes": stat.st_size,
                    "created_at": int(stat.st_mtime),
                }
            )
        return sorted(result, key=lambda item: (-item["created_at"], item["filename"]))

    def restore_database_backup(
        self,
        backup_directory: Path,
        filename: object,
    ) -> dict[str, Any]:
        source_path = self._validated_backup_path(backup_directory, filename)
        if not source_path.is_file():
            raise FileNotFoundError("database backup not found")
        with sqlite3.connect(source_path, timeout=10.0) as validation:
            result = validation.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise ValueError("database backup failed integrity check")
            schema_version = int(validation.execute("PRAGMA user_version").fetchone()[0])
            if schema_version > 7:
                raise ValueError("database backup uses a newer unsupported schema")

        safety_backup = self.create_database_backup(
            backup_directory,
            label="pre-restore",
        )
        with self._maintenance_lock:
            source = sqlite3.connect(source_path, timeout=10.0)
            destination = sqlite3.connect(self.path, timeout=10.0)
            try:
                source.backup(destination)
                destination.commit()
            finally:
                destination.close()
                source.close()
            self._initialize()
        return {
            "restored_from": source_path.name,
            "safety_backup": safety_backup["filename"],
            "schema_version": schema_version,
        }

    def stats(self, save_id: object | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            if save_id is None:
                save_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM story_saves WHERE archived_at IS NULL"
                    ).fetchone()[0]
                )
                archived_save_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM story_saves WHERE archived_at IS NOT NULL"
                    ).fetchone()[0]
                )
                memory_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM memories WHERE archived_at IS NULL"
                    ).fetchone()[0]
                )
                archived_memory_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM memories WHERE archived_at IS NOT NULL"
                    ).fetchone()[0]
                )
                turn_count = int(
                    connection.execute("SELECT COUNT(*) FROM story_turns").fetchone()[0]
                )
                task_count = int(
                    connection.execute("SELECT COUNT(*) FROM generation_tasks").fetchone()[0]
                )
                failed_task_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM generation_tasks WHERE status = 'failed'"
                    ).fetchone()[0]
                )
            else:
                normalized = normalize_save_id(save_id)
                save_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM story_saves
                        WHERE id = ? AND archived_at IS NULL
                        """,
                        (normalized,),
                    ).fetchone()[0]
                )
                archived_save_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM story_saves
                        WHERE id = ? AND archived_at IS NOT NULL
                        """,
                        (normalized,),
                    ).fetchone()[0]
                )
                memory_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM memories
                        WHERE save_id = ? AND archived_at IS NULL
                        """,
                        (normalized,),
                    ).fetchone()[0]
                )
                archived_memory_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM memories
                        WHERE save_id = ? AND archived_at IS NOT NULL
                        """,
                        (normalized,),
                    ).fetchone()[0]
                )
                turn_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM story_turns WHERE save_id = ?", (normalized,)
                    ).fetchone()[0]
                )
                task_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM generation_tasks WHERE save_id = ?",
                        (normalized,),
                    ).fetchone()[0]
                )
                failed_task_count = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM generation_tasks
                        WHERE save_id = ? AND status = 'failed'
                        """,
                        (normalized,),
                    ).fetchone()[0]
                )
        return {
            "database": str(self.path),
            "fts_enabled": self._fts_enabled,
            "save_count": save_count,
            "archived_save_count": archived_save_count,
            "memory_count": memory_count,
            "archived_memory_count": archived_memory_count,
            "turn_count": turn_count,
            "task_count": task_count,
            "failed_task_count": failed_task_count,
        }
