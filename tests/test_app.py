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
        assert created.status_code == 200
        listed = client.get(
            "/v1/story/saves/demo/memories",
            headers=headers,
        )
        assert listed.status_code == 200
        assert listed.json()["data"][0]["content"].startswith("雾港城")
