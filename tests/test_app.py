import json
from pathlib import Path

from fastapi.testclient import TestClient

from storycanvas.app import create_app
from storycanvas.config import Settings


def settings_for_test(tmp_path: Path) -> Settings:
    return Settings(
        root=tmp_path,
        llm_api_key="provider-test",
        llm_base_url="https://example.test",
        llm_model="test-model",
        gateway_api_key="gateway-test",
        gateway_host="127.0.0.1",
        gateway_port=8000,
        public_base_url="http://127.0.0.1:8000",
        comfyui_url="http://127.0.0.1:9",
        checkpoint_name="test.safetensors",
        image_width=832,
        image_height=1216,
        image_steps=24,
        image_cfg=6.0,
        image_sampler="dpmpp_2m",
        image_scheduler="karras",
        image_timeout_seconds=1,
        face_detailer_enabled=False,
        face_detailer_model="bbox/face_yolov8m.pt",
        face_detailer_guide_size=576,
        face_detailer_max_size=768,
        face_detailer_steps=12,
        face_detailer_cfg=5.0,
        face_detailer_denoise=0.16,
        face_detailer_threshold=0.35,
        face_detailer_dilation=16,
        face_detailer_crop_factor=2.4,
        face_detailer_feather=24,
        auto_image_default=False,
        memory_enabled=True,
        memory_extract_enabled=True,
        memory_database_path=tmp_path / "story-memory.sqlite3",
        memory_default_save_id="default",
        memory_top_k=8,
        memory_context_max_chars=6000,
        story_profile_path=tmp_path / "story.md",
        generated_images_dir=tmp_path / "generated_images",
    )


def test_models_requires_gateway_key(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        assert client.get("/v1/models").status_code == 401
        response = client.get(
            "/v1/models", headers={"Authorization": "Bearer gateway-test"}
        )
        assert response.status_code == 200
        assert response.json()["data"][0]["id"] == "storycanvas"


def test_request_id_is_echoed_and_included_in_errors(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        response = client.get(
            "/v1/models",
            headers={"X-Request-ID": "demo-request-001"},
        )
        assert response.status_code == 401
        assert response.headers["X-Request-ID"] == "demo-request-001"
        assert response.json()["request_id"] == "demo-request-001"

        generated = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer gateway-test", "X-Request-ID": "invalid id"},
        )
        assert generated.status_code == 200
        generated_id = generated.headers["X-Request-ID"]
        assert len(generated_id) == 32
        assert generated_id != "invalid id"


def test_control_command_does_not_call_provider(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer gateway-test"},
            json={
                "model": "storycanvas",
                "messages": [{"role": "user", "content": "/图开"}],
            },
        )
        assert response.status_code == 200
        assert "enabled" in response.json()["choices"][0]["message"]["content"]


def test_control_command_stream_uses_bounded_sse_chunks(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer gateway-test"},
            json={
                "model": "storycanvas",
                "stream": True,
                "messages": [{"role": "user", "content": "/图开"}],
            },
        )
        assert response.status_code == 200
        events = [
            line.removeprefix("data: ")
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert events[-1] == "[DONE]"
        chunks = [json.loads(event) for event in events[:-1]]
        assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
        assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
        assert all(
            len(chunk["choices"][0]["delta"].get("content", "")) <= 128
            for chunk in chunks
        )


def test_memory_management_api(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        headers = {"Authorization": "Bearer gateway-test"}
        assert client.delete("/v1/story/saves/default", headers=headers).status_code == 409
        save = client.post(
            "/v1/story/saves",
            headers=headers,
            json={"id": "demo", "name": "演示故事"},
        )
        assert save.status_code == 201
        renamed = client.patch(
            "/v1/story/saves/demo",
            headers=headers,
            json={"name": "雾港故事"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["data"]["name"] == "雾港故事"

        created = client.post(
            "/v1/story/saves/demo/memories",
            headers=headers,
            json={
                "type": "world",
                "content": "雾港城的北门只在满月时开启。",
                "tags": ["雾港城", "北门", "满月"],
                "entities": ["雾港城"],
                "importance": 5,
            },
        )
        assert created.status_code == 201
        memory_id = created.json()["data"]["id"]
        updated = client.patch(
            f"/v1/story/saves/demo/memories/{memory_id}",
            headers=headers,
            json={"importance": 4, "tags": ["北门", "月相"]},
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["importance"] == 4

        listed = client.get(
            "/v1/story/saves/demo/memories?limit=10&offset=0",
            headers=headers,
        )
        assert listed.status_code == 200
        assert listed.json()["data"][0]["content"].startswith("雾港城")

        archived = client.delete(
            f"/v1/story/saves/demo/memories/{memory_id}", headers=headers
        )
        assert archived.status_code == 200
        assert client.get(
            "/v1/story/saves/demo/memories", headers=headers
        ).json()["data"] == []
        duplicate_archived = client.post(
            "/v1/story/saves/demo/memories",
            headers=headers,
            json={
                "type": "world",
                "content": "雾港城的北门只在满月时开启。",
                "tags": ["北门"],
                "importance": 4,
            },
        )
        assert duplicate_archived.status_code == 409
        restored = client.post(
            f"/v1/story/saves/demo/memories/{memory_id}/restore", headers=headers
        )
        assert restored.status_code == 200

        extra = client.post(
            "/v1/story/saves",
            headers=headers,
            json={"id": "archive-me", "name": "待归档"},
        )
        assert extra.status_code == 201
        assert client.delete("/v1/story/saves/archive-me", headers=headers).status_code == 200
        visible = client.get("/v1/story/saves", headers=headers).json()["data"]
        assert all(item["id"] != "archive-me" for item in visible)
        all_saves = client.get(
            "/v1/story/saves?include_archived=true", headers=headers
        ).json()["data"]
        assert any(item["id"] == "archive-me" for item in all_saves)
        assert client.post(
            "/v1/story/saves/archive-me/restore", headers=headers
        ).status_code == 200


def test_story_save_export_import_and_copy_api(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        headers = {"Authorization": "Bearer gateway-test"}
        assert client.post(
            "/v1/story/saves",
            headers=headers,
            json={"id": "source", "name": "源故事"},
        ).status_code == 201
        assert client.post(
            "/v1/story/saves/source/memories",
            headers=headers,
            json={
                "type": "fact",
                "content": "月纹钥匙可以开启钟楼档案室。",
                "tags": ["钥匙", "钟楼"],
                "importance": 5,
            },
        ).status_code == 201

        exported = client.get(
            "/v1/story/saves/source/export",
            headers=headers,
        )
        assert exported.status_code == 200
        assert exported.json()["format"] == "storycanvas-save"

        imported = client.post(
            "/v1/story/saves/import",
            headers=headers,
            json={
                "target_id": "imported",
                "target_name": "导入故事",
                "bundle": exported.json(),
            },
        )
        assert imported.status_code == 201
        assert imported.json()["data"]["memory_count"] == 1
        duplicate_import = client.post(
            "/v1/story/saves/import",
            headers=headers,
            json={"target_id": "imported", "bundle": exported.json()},
        )
        assert duplicate_import.status_code == 409

        copied = client.post(
            "/v1/story/saves/source/copy",
            headers=headers,
            json={"id": "copy", "name": "故事副本"},
        )
        assert copied.status_code == 201
        assert copied.json()["data"]["save_id"] == "copy"


def test_memory_conflict_and_supersede_api(tmp_path: Path) -> None:
    with TestClient(create_app(settings_for_test(tmp_path))) as client:
        headers = {"Authorization": "Bearer gateway-test"}
        created = client.post(
            "/v1/story/saves/default/memories",
            headers=headers,
            json={
                "type": "fact",
                "content": "钟楼北门只在满月时开启。",
                "tags": ["钟楼", "北门"],
                "importance": 5,
            },
        )
        assert created.status_code == 201
        memory_id = created.json()["data"]["id"]

        conflicted = client.post(
            f"/v1/story/saves/default/memories/{memory_id}/conflict",
            headers=headers,
        )
        assert conflicted.status_code == 200
        assert conflicted.json()["data"]["status"] == "conflicted"
        activated = client.post(
            f"/v1/story/saves/default/memories/{memory_id}/activate",
            headers=headers,
        )
        assert activated.status_code == 200
        assert activated.json()["data"]["status"] == "active"

        replacement = client.post(
            f"/v1/story/saves/default/memories/{memory_id}/supersede",
            headers=headers,
            json={
                "type": "fact",
                "content": "钟楼北门改为每天午夜开启。",
                "tags": ["钟楼", "北门", "午夜"],
                "importance": 5,
            },
        )
        assert replacement.status_code == 201
        replacement_data = replacement.json()["data"]
        assert replacement_data["supersedes_memory_id"] == memory_id
        listed = client.get(
            "/v1/story/saves/default/memories",
            headers=headers,
        ).json()["data"]
        assert {item["status"] for item in listed} == {"active", "superseded"}
