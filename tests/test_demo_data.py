from pathlib import Path

from storycanvas.demo_data import seed_demo
from storycanvas.memory_store import MemoryStore


def test_seed_demo_is_complete_and_idempotent(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")

    created = seed_demo(store)
    repeated = seed_demo(store)

    assert created["created"] is True
    assert created["turn_count"] == 2
    assert created["memory_count"] == 3
    assert repeated["created"] is False
    assert repeated["turn_count"] == 2
    assert repeated["memory_count"] == 3
    assert all(item["source_turn_id"] for item in store.list_memories("demo-observatory"))
