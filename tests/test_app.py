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
        auto_image_default=False,
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
