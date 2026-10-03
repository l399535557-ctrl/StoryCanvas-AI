from __future__ import annotations

import asyncio
import io
import secrets
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from PIL import Image

from .config import Settings


class ComfyError(RuntimeError):
    pass


def build_core_workflow(
    settings: Settings, positive: str, negative: str, seed: int
) -> dict[str, Any]:
    workflow: dict[str, Any] = {
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
    if not settings.face_detailer_enabled:
        return workflow

    identity = positive.split(" BREAK ", maxsplit=1)[0]
    face_positive = (
        f"{identity}, symmetrical eyes, detailed irises, aligned pupils, well-defined eyebrows, "
        "natural nose bridge, detailed lips, coherent facial proportions, clean facial lineart, "
        "subtle facial shading, best quality"
    )
    face_negative = (
        f"{negative}, cross-eyed, misaligned eyes, uneven eyes, malformed iris, duplicate pupils, "
        "distorted face, asymmetrical face, deformed mouth, blurry face"
    )
    workflow.update(
        {
            "30": {
                "class_type": "UltralyticsDetectorProvider",
                "inputs": {"model_name": settings.face_detailer_model},
            },
            "31": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": face_positive, "clip": ["1", 1]},
            },
            "32": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": face_negative, "clip": ["1", 1]},
            },
            "33": {
                "class_type": "FaceDetailer",
                "inputs": {
                    "image": ["6", 0],
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "vae": ["1", 2],
                    "guide_size": float(settings.face_detailer_guide_size),
                    "guide_size_for": True,
                    "max_size": float(settings.face_detailer_max_size),
                    "seed": seed,
                    "steps": settings.face_detailer_steps,
                    "cfg": settings.face_detailer_cfg,
                    "sampler_name": "dpmpp_2m",
                    "scheduler": "karras",
                    "positive": ["31", 0],
                    "negative": ["32", 0],
                    "denoise": settings.face_detailer_denoise,
                    "feather": settings.face_detailer_feather,
                    "noise_mask": True,
                    "force_inpaint": True,
                    "bbox_threshold": settings.face_detailer_threshold,
                    "bbox_dilation": settings.face_detailer_dilation,
                    "bbox_crop_factor": settings.face_detailer_crop_factor,
                    "sam_detection_hint": "none",
                    "sam_dilation": 0,
                    "sam_threshold": 0.93,
                    "sam_bbox_expansion": 0,
                    "sam_mask_hint_threshold": 0.7,
                    "sam_mask_hint_use_negative": "False",
                    "drop_size": 20,
                    "bbox_detector": ["30", 0],
                    "wildcard": "",
                    "cycle": 1,
                    "noise_mask_feather": 20,
                    "tiled_encode": False,
                    "tiled_decode": False,
                },
            },
        }
    )
    workflow["7"]["inputs"]["images"] = ["33", 0]
    return workflow


class ComfyClient:
    def __init__(self, settings: Settings, *, backend_name: str = "comfy-sdxl") -> None:
        self.settings = settings
        self._backend_name = backend_name
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._backend_name

    async def system_stats(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.settings.comfyui_url}/system_stats")
            response.raise_for_status()
            return response.json()

    async def generate(
        self,
        positive: str,
        negative: str,
        *,
        on_queued: Callable[[str], Awaitable[None]] | None = None,
        is_cancelled: Callable[[], Awaitable[bool]] | None = None,
    ) -> tuple[str, float]:
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
                if on_queued is not None:
                    await on_queued(prompt_id)
                deadline = time.monotonic() + self.settings.image_timeout_seconds
                record: dict[str, Any] | None = None
                while time.monotonic() < deadline:
                    if is_cancelled is not None and await is_cancelled():
                        await client.post(f"{self.settings.comfyui_url}/interrupt")
                        raise ComfyError("ComfyUI generation cancelled")
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
