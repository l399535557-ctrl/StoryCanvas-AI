from __future__ import annotations

import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any

from .memory_store import MemoryStore, normalize_save_id

_REMOTE_IMAGE = re.compile(r"\n*!\[[^\]]*]\(https?://[^)]+\)", re.I)


def _clean_story_text(value: object) -> str:
    text = str(value or "").strip()
    return _REMOTE_IMAGE.sub("", text).strip()


def build_story_archive(
    store: MemoryStore,
    save_id: object,
    generated_images_dir: Path,
) -> tuple[str, bytes]:
    """Build a self-contained story ZIP without exporting private RAG internals."""
    normalized = normalize_save_id(save_id)
    bundle = store.export_save(normalized, include_archived=False)
    save = bundle["save"]
    turns = bundle["turns"]
    tasks = store.list_generation_tasks(save_id=normalized, status="succeeded", limit=500)
    exported_at = int(time.time())

    lines = [f"# {save['name']}", "", f"> StoryCanvas AI 导出时间：{exported_at}", ""]
    for index, turn in enumerate(turns, start=1):
        lines.extend(
            [
                f"## 第 {index} 节",
                "",
                "### 用户输入",
                "",
                _clean_story_text(turn.get("user_text")),
                "",
                "### 故事内容",
                "",
                _clean_story_text(turn.get("assistant_text")),
                "",
            ]
        )

    image_items: list[dict[str, Any]] = []
    for task in reversed(tasks):
        raw_name = str(task.get("image_filename") or "")
        safe_name = Path(raw_name).name
        path = generated_images_dir / safe_name
        if raw_name != safe_name or path.suffix.lower() != ".webp" or not path.is_file():
            continue
        image_items.append(
            {
                "task_id": task["id"],
                "request_id": task["request_id"],
                "filename": safe_name,
                "created_at": task["created_at"],
                "duration_seconds": task["duration_seconds"],
            }
        )

    if image_items:
        lines.extend(["## 插图", ""])
        for index, item in enumerate(image_items, start=1):
            lines.extend(
                [
                    f"### 插图 {index}",
                    "",
                    f"![插图 {index}](images/{item['filename']})",
                    "",
                ]
            )

    manifest = {
        "format": "storycanvas-publication",
        "version": 1,
        "exported_at": exported_at,
        "save": {"id": normalized, "name": save["name"]},
        "turn_count": len(turns),
        "image_count": len(image_items),
        "images": image_items,
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("story.md", "\n".join(lines).rstrip() + "\n")
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
        for item in image_items:
            archive.write(
                generated_images_dir / item["filename"],
                f"images/{item['filename']}",
            )
    return f"storycanvas-{normalized}.zip", output.getvalue()
