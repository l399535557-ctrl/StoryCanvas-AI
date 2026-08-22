from __future__ import annotations

import asyncio
import io
import secrets
import time
import uuid
from typing import Any

import httpx
from PIL import Image

from .config import Settings


class ComfyError(RuntimeError):
    pass


def build_core_workflow(
    settings: Settings, positive: str, negative: str, seed: int
) -> dict[str, Any]:
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": settings.checkpoint_name},
        },
        "2": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": settings.image_width,
                "height": settings.image_height,
                "batch_size": 1,
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative, "clip": ["1", 1]},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": seed,
                "steps": settings.image_steps,
                "cfg": settings.image_cfg,
                "sampler_name": settings.image_sampler,
                "scheduler": settings.image_scheduler,
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["2", 0],
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
                "tile_size": 512,
                "overlap": 64,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "storycanvas/scene"},
        },
    }


class ComfyClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()

    async def system_stats(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.settings.comfyui_url}/system_stats")
            response.raise_for_status()
            return response.json()

    async def generate(self, positive: str, negative: str) -> tuple[str, float]:
        if not self.settings.checkpoint_name:
            raise ComfyError("CHECKPOINT_NAME is not configured")
        started = time.perf_counter()
        seed = secrets.randbits(63)
        payload = {
            "prompt": build_core_workflow(self.settings, positive, negative, seed),
            "client_id": "storycanvas-ai",
        }
        async with self._lock:
            async with httpx.AsyncClient(timeout=30.0) as client:
                queued = await client.post(f"{self.settings.comfyui_url}/prompt", json=payload)
                if queued.status_code >= 400:
                    raise ComfyError(f"ComfyUI rejected the workflow: {queued.text[:500]}")
                queued_json = queued.json()
                if queued_json.get("node_errors"):
                    raise ComfyError(f"ComfyUI node errors: {queued_json['node_errors']}")
                prompt_id = str(queued_json["prompt_id"])
                deadline = time.monotonic() + self.settings.image_timeout_seconds
                record: dict[str, Any] | None = None
                while time.monotonic() < deadline:
                    response = await client.get(
                        f"{self.settings.comfyui_url}/history/{prompt_id}"
                    )
                    response.raise_for_status()
                    history = response.json()
                    if prompt_id in history:
                        record = history[prompt_id]
                        break
                    await asyncio.sleep(1)
                if record is None:
                    raise ComfyError("ComfyUI generation timed out")
                images = record.get("outputs", {}).get("7", {}).get("images", [])
                if not images:
                    raise ComfyError("ComfyUI returned no image")
                item = images[0]
                view = await client.get(
                    f"{self.settings.comfyui_url}/view",
                    params={
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    },
                )
                view.raise_for_status()
            output_name = f"{uuid.uuid4().hex}.webp"
            output_path = self.settings.generated_images_dir / output_name
            self.settings.generated_images_dir.mkdir(parents=True, exist_ok=True)
            with Image.open(io.BytesIO(view.content)) as source:
                source.convert("RGB").save(output_path, "WEBP", quality=93, method=6)
        return output_name, time.perf_counter() - started
