from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .memory_store import MemoryStore, normalize_save_id


def seed_demo(
    store: MemoryStore,
    *,
    save_id: str = "demo-observatory",
    name: str = "星海观测站",
) -> dict[str, Any]:
    """Create one small, repeatable public demo without overwriting existing data."""
    normalized = normalize_save_id(save_id, "demo-observatory")
    existing = store.get_save(normalized)
    if existing is not None:
        counts = store.stats(normalized)
        if counts["turn_count"] or counts["memory_count"]:
            return {"created": False, "save_id": normalized, **counts}

    store.ensure_save(normalized, name)
    first_turn = store.record_turn(
        normalized,
        "我在暴雨中抵达废弃的星海观测站。",
        "你推开铜门，发现中央星图仍在运转，控制台旁放着一枚刻有月纹的钥匙。",
    )
    second_turn = store.record_turn(
        normalized,
        "我用月纹钥匙启动控制台。",
        "穹顶缓缓开启，星图显示北侧档案室将在午夜解锁，同时记录下一组未知坐标。",
    )
    memories = [
        {
            "memory_type": "world",
            "content": "星海观测站的中央星图在停电后仍能独立运转。",
            "tags": ["观测站", "星图"],
            "entities": ["星海观测站"],
            "importance": 4,
            "source_turn_id": first_turn,
        },
        {
            "memory_type": "item",
            "content": "月纹钥匙可以启动观测站控制台。",
            "tags": ["月纹钥匙", "控制台"],
            "entities": ["月纹钥匙"],
            "importance": 5,
            "source_turn_id": second_turn,
        },
        {
            "memory_type": "event",
            "content": "北侧档案室将在午夜解锁。",
            "tags": ["档案室", "午夜"],
            "entities": ["北侧档案室"],
            "importance": 5,
            "story_time": "第一章",
            "source_turn_id": second_turn,
        },
    ]
    for item in memories:
        store.add_memory(normalized, **item)
    return {"created": True, "save_id": normalized, **store.stats(normalized)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the public StoryCanvas demo save.")
    parser.add_argument("--database", type=Path, help="Override the configured SQLite path.")
    parser.add_argument("--save-id", default="demo-observatory")
    parser.add_argument("--name", default="星海观测站")
    args = parser.parse_args()

    settings = Settings.load(Path.cwd())
    store = MemoryStore(args.database or settings.memory_database_path)
    print(
        json.dumps(
            seed_demo(store, save_id=args.save_id, name=args.name),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
