import asyncio
from pathlib import Path

from storycanvas.memory_rag import MemoryRAGService
from storycanvas.memory_store import MemoryStore, normalize_save_id


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
