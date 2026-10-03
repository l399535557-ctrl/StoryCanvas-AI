import asyncio
import sqlite3
from pathlib import Path

from storycanvas.memory_rag import MemoryRAGService
from storycanvas.memory_store import MemoryStore, normalize_save_id


def test_memory_store_migrates_version_one_database(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE story_saves (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE TABLE story_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                save_id TEXT NOT NULL REFERENCES story_saves(id) ON DELETE CASCADE,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE memories (
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
            """
        )

    MemoryStore(database)
    with sqlite3.connect(database) as connection:
        save_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(story_saves)")
        }
        memory_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(memories)")
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert "archived_at" in save_columns
    assert "archived_at" in memory_columns
    assert "status" in memory_columns
    assert "supersedes_memory_id" in memory_columns
    assert user_version == 5


def test_memory_store_isolates_saves_and_retrieves_chinese(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    assert normalize_save_id(" 第一章 / 雨夜 ") == "第一章-雨夜"
    memory_id = store.add_memory(
        "save-a",
        memory_type="event",
        content="林岚在钟楼顶层发现了月纹银钥匙。",
        tags=["钟楼", "银钥匙"],
        entities=["林岚"],
        importance=5,
    )
    store.add_memory(
        "save-b",
        memory_type="world",
        content="海港城每逢满月会关闭城门。",
        tags=["海港城", "满月"],
        entities=["海港城"],
        importance=4,
    )

    retrieved = store.retrieve("save-a", "林岚拿着钥匙返回钟楼")
    assert retrieved and retrieved[0].id == memory_id
    assert store.retrieve("save-b", "林岚和银钥匙") == []


def test_local_rag_capture_and_context_injection(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    state = {"active_save_id": "demo"}
    runtime: dict[str, object] = {}
    service = MemoryRAGService(
        store=store,
        state=state,
        runtime=runtime,
        state_lock=asyncio.Lock(),
        save_state=lambda: None,
        character_memory={"characters": {}},
        enabled=True,
        extract_enabled=True,
        default_save_id="default",
        top_k=8,
        context_max_chars=6000,
    )

    asyncio.run(
        service.extract_and_store(
            "demo",
            "林岚进入钟楼。",
            "林岚在钟楼顶层发现月纹钥匙，并决定把秘密告诉同伴。",
        )
    )
    message = asyncio.run(
        service.retrieve_message(
            "demo",
            "林岚再次前往钟楼寻找钥匙。",
            [{"role": "user", "content": "林岚再次前往钟楼寻找钥匙。"}],
        )
    )
    assert message is not None
    assert "月纹钥匙" in message["content"]
    assert store.stats("demo")["turn_count"] == 1


def test_data_management_is_recoverable_and_save_scoped(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.ensure_save("demo", "演示存档")
    assert store.rename_save("demo", "重命名后的存档") is True
    assert store.get_save("demo")["name"] == "重命名后的存档"

    first_turn = store.record_turn("demo", "第一轮", "第一轮回复")
    second_turn = store.record_turn("demo", "第二轮", "第二轮回复")
    assert [item["id"] for item in store.list_turns("demo", limit=1)] == [second_turn]
    assert store.list_turns("demo", limit=1, offset=1)[0]["id"] == first_turn

    memory_id = store.add_memory(
        "demo",
        memory_type="fact",
        content="旧内容",
        tags=["旧标签"],
        importance=2,
    )
    assert memory_id is not None
    assert store.update_memory(
        "demo",
        memory_id,
        memory_type="world",
        content="钟楼北门只在满月时开启。",
        tags=["钟楼", "满月"],
        entities=["钟楼"],
        importance=5,
        story_time="第二章",
    )
    assert store.get_memory("demo", memory_id)["importance"] == 5
    assert store.retrieve("demo", "满月时去钟楼北门")[0].id == memory_id

    assert store.archive_memory("demo", memory_id) is True
    assert store.list_memories("demo") == []
    assert store.retrieve("demo", "满月时去钟楼北门") == []
    archived = store.list_memories("demo", include_archived=True)
    assert archived[0]["archived_at"] is not None
    assert store.restore_memory("demo", memory_id) is True
    assert store.list_memories("demo")[0]["id"] == memory_id

    assert store.archive_save("demo") is True
    assert store.list_saves() == []
    assert store.list_saves(include_archived=True)[0]["archived_at"] is not None
    store.ensure_save("demo")
    assert store.list_saves() == []
    assert store.restore_save("demo") is True
    assert store.list_saves()[0]["id"] == "demo"


def test_save_export_import_and_copy_preserve_relationships(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    store.ensure_save("source", "源故事")
    turn_id = store.record_turn("source", "推开钟楼门", "林岚发现了月纹钥匙。")
    memory_id = store.add_memory(
        "source",
        memory_type="event",
        content="林岚在钟楼发现月纹钥匙。",
        tags=["钟楼", "钥匙"],
        entities=["林岚"],
        importance=5,
        source_turn_id=turn_id,
    )
    assert memory_id is not None
    archived_id = store.add_memory(
        "source",
        memory_type="note",
        content="这是一条已归档的旧记忆。",
        importance=1,
    )
    assert archived_id is not None
    assert store.archive_memory("source", archived_id)

    bundle = store.export_save("source", include_archived=True)
    imported = store.import_save(
        bundle,
        target_save_id="imported",
        target_name="导入故事",
    )
    assert imported == {
        "save_id": "imported",
        "name": "导入故事",
        "turn_count": 1,
        "memory_count": 2,
    }
    imported_turn = store.list_turns("imported")[0]
    imported_memories = store.list_memories("imported", include_archived=True)
    active_memory = next(item for item in imported_memories if item["archived_at"] is None)
    assert active_memory["source_turn_id"] == imported_turn["id"]
    assert store.retrieve("imported", "林岚回到钟楼寻找钥匙")[0].content.startswith("林岚")

    copied = store.copy_save("source", "copy", "故事副本")
    assert copied["turn_count"] == 1
    assert copied["memory_count"] == 1
    assert len(store.list_memories("copy", include_archived=True)) == 1

    try:
        store.import_save(bundle, target_save_id="imported")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("import must not overwrite an existing save")


def test_conflicted_and_superseded_memories_are_excluded_from_rag(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    old_id = store.add_memory(
        "demo",
        memory_type="fact",
        content="钟楼北门只在满月时开启。",
        tags=["钟楼", "北门", "满月"],
        importance=5,
    )
    assert old_id is not None
    assert store.set_memory_status("demo", old_id, "conflicted")
    assert store.retrieve("demo", "满月时前往钟楼北门") == []
    assert store.set_memory_status("demo", old_id, "active")
    assert store.retrieve("demo", "满月时前往钟楼北门")[0].id == old_id

    replacement_id = store.supersede_memory(
        "demo",
        old_id,
        memory_type="fact",
        content="钟楼北门改为每天午夜开启。",
        tags=["钟楼", "北门", "午夜"],
        importance=5,
    )
    old_memory = store.get_memory("demo", old_id)
    replacement = store.get_memory("demo", replacement_id)
    assert old_memory["status"] == "superseded"
    assert replacement["status"] == "active"
    assert replacement["supersedes_memory_id"] == old_id
    retrieved = store.retrieve("demo", "午夜前往钟楼北门")
    assert [item.id for item in retrieved] == [replacement_id]

    bundle = store.export_save("demo", include_archived=True)
    store.import_save(bundle, target_save_id="imported", target_name="导入修订链")
    imported = store.list_memories("imported", include_archived=True)
    imported_replacement = next(item for item in imported if item["status"] == "active")
    imported_old = next(item for item in imported if item["status"] == "superseded")
    assert imported_replacement["supersedes_memory_id"] == imported_old["id"]


def test_generation_task_lifecycle_and_restart_recovery(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    store = MemoryStore(database)
    task_id = store.create_generation_task("demo", "request-001")
    assert store.get_generation_task(task_id)["status"] == "queued"
    assert store.update_generation_task(task_id, "running")
    running = store.get_generation_task(task_id)
    assert running["started_at"] is not None

    reopened = MemoryStore(database)
    interrupted = reopened.get_generation_task(task_id)
    assert interrupted["status"] == "failed"
    assert interrupted["error"] == "interrupted by service restart"

    success_id = reopened.create_generation_task("demo", "request-002")
    assert reopened.update_generation_task(success_id, "running")
    assert reopened.update_generation_task(
        success_id,
        "succeeded",
        image_filename="scene.webp",
        duration_seconds=3.25,
    )
    succeeded = reopened.list_generation_tasks(save_id="demo", status="succeeded")
    assert [item["id"] for item in succeeded] == [success_id]
    assert succeeded[0]["image_filename"] == "scene.webp"
    assert reopened.stats("demo")["task_count"] == 2

    cancellable_id = reopened.create_generation_task("demo", "request-003")
    assert reopened.set_generation_task_prompts(
        cancellable_id,
        "a moonlit tower",
        "blurry",
    )
    assert reopened.cancel_generation_task(cancellable_id)
    assert not reopened.update_generation_task(
        cancellable_id,
        "succeeded",
        image_filename="late.webp",
    )
    payload = reopened.get_generation_task_payload(cancellable_id)
    assert payload["status"] == "cancelled"
    assert payload["positive_prompt"] == "a moonlit tower"


def test_database_backup_restore_and_safety_snapshot(tmp_path: Path) -> None:
    database = tmp_path / "memory.sqlite3"
    backups = tmp_path / "backups"
    store = MemoryStore(database)
    original_id = store.add_memory(
        "demo",
        memory_type="fact",
        content="原始世界设定。",
        tags=["原始"],
        importance=5,
    )
    assert original_id is not None
    backup = store.create_database_backup(backups, label="manual")
    assert backup["schema_version"] == 5
    later_id = store.add_memory(
        "demo",
        memory_type="fact",
        content="备份后新增的设定。",
        tags=["新增"],
        importance=3,
    )
    assert later_id is not None
    assert len(store.list_memories("demo")) == 2

    restored = store.restore_database_backup(backups, backup["filename"])
    assert restored["restored_from"] == backup["filename"]
    assert restored["safety_backup"].endswith("-pre-restore.sqlite3")
    memories = store.list_memories("demo")
    assert [item["content"] for item in memories] == ["原始世界设定。"]
    assert len(store.list_database_backups(backups)) == 2
