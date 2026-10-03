import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from test_app import settings_for_test

from storycanvas.app import create_app
from storycanvas.memory_store import MemoryStore
from storycanvas.story_export import build_story_archive


def prepare_story(store: MemoryStore, images: Path) -> str:
    store.ensure_save("demo", "钟楼故事")
    store.record_turn(
        "demo",
        "林岚推开钟楼的门。",
        "她在月光下发现一把银钥匙。\n\n![Generated](http://localhost/image.webp)",
    )
    task_id = store.create_generation_task("demo", "export-request")
    assert store.update_generation_task(task_id, "running")
    images.mkdir(parents=True, exist_ok=True)
    (images / "scene.webp").write_bytes(b"test-webp")
    assert store.update_generation_task(
        task_id,
        "succeeded",
        image_filename="scene.webp",
        duration_seconds=1.5,
    )
    return task_id


def test_story_archive_contains_markdown_manifest_and_images(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.sqlite3")
    task_id = prepare_story(store, tmp_path / "generated_images")
    filename, payload = build_story_archive(store, "demo", tmp_path / "generated_images")
    assert filename == "storycanvas-demo.zip"

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {
            "story.md",
            "manifest.json",
            "images/scene.webp",
        }
        story = archive.read("story.md").decode("utf-8")
        manifest = json.loads(archive.read("manifest.json"))
    assert "# 钟楼故事" in story
    assert "林岚推开钟楼的门" in story
    assert "http://localhost/image.webp" not in story
    assert "images/scene.webp" in story
    assert manifest["images"][0]["task_id"] == task_id
    assert "memories" not in manifest


def test_story_publication_api_returns_zip(tmp_path: Path) -> None:
    settings = settings_for_test(tmp_path)
    with TestClient(create_app(settings)) as client:
        store = MemoryStore(settings.memory_database_path)
        prepare_story(store, settings.generated_images_dir)
        response = client.get(
            "/v1/story/saves/demo/publication",
            headers={"Authorization": "Bearer gateway-test"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "storycanvas-demo.zip" in response.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert "story.md" in archive.namelist()
