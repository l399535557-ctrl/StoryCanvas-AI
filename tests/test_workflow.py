from dataclasses import replace
from pathlib import Path

from storycanvas.comfy import build_core_workflow
from storycanvas.config import Settings


def test_core_workflow_has_only_expected_nodes(tmp_path: Path) -> None:
    settings = Settings(
        root=tmp_path,
        llm_api_key="test",
        llm_base_url="https://example.test",
        llm_model="test-model",
        gateway_api_key="gateway-test",
        gateway_host="127.0.0.1",
        gateway_port=8000,
        public_base_url="http://127.0.0.1:8000",
        comfyui_url="http://127.0.0.1:8188",
        checkpoint_name="test.safetensors",
        image_width=832,
        image_height=1216,
        image_steps=24,
        image_cfg=6.0,
        image_sampler="dpmpp_2m",
        image_scheduler="karras",
        image_timeout_seconds=360,
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
        story_profile_path=tmp_path / "story.md",
        generated_images_dir=tmp_path / "generated_images",
    )
    workflow = build_core_workflow(settings, "positive", "negative", 42)
    assert {node["class_type"] for node in workflow.values()} == {
        "CheckpointLoaderSimple",
        "EmptyLatentImage",
        "CLIPTextEncode",
        "KSampler",
        "VAEDecodeTiled",
        "SaveImage",
    }
    assert workflow["2"]["inputs"]["batch_size"] == 1
    assert workflow["5"]["inputs"]["seed"] == 42

    refined = build_core_workflow(
        replace(settings, face_detailer_enabled=True), "identity BREAK scene", "bad", 42
    )
    assert refined["30"]["class_type"] == "UltralyticsDetectorProvider"
    assert refined["33"]["class_type"] == "FaceDetailer"
    assert refined["33"]["inputs"]["denoise"] == 0.16
    assert refined["7"]["inputs"]["images"] == ["33", 0]
