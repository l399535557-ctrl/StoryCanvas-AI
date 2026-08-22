from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


def _as_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


@dataclass(frozen=True, slots=True)
class Settings:
    root: Path
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    gateway_api_key: str
    gateway_host: str
    gateway_port: int
    public_base_url: str
    comfyui_url: str
    checkpoint_name: str
    image_width: int
    image_height: int
    image_steps: int
    image_cfg: float
    image_sampler: str
    image_scheduler: str
    image_timeout_seconds: int
    auto_image_default: bool
    story_profile_path: Path
    generated_images_dir: Path

    @classmethod
    def load(cls, root: Path | None = None) -> Settings:
        project_root = (root or Path.cwd()).resolve()
        load_dotenv(project_root / ".env")
        story_path = Path(os.getenv("STORY_PROFILE_PATH", "examples/story_profile.example.md"))
        if not story_path.is_absolute():
            story_path = project_root / story_path
        return cls(
            root=project_root,
            llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", "deepseek-chat").strip(),
            gateway_api_key=os.getenv("GATEWAY_API_KEY", "").strip(),
            gateway_host=os.getenv("GATEWAY_HOST", "127.0.0.1").strip(),
            gateway_port=_as_int("GATEWAY_PORT", 8000),
            public_base_url=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            comfyui_url=os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/"),
            checkpoint_name=os.getenv("CHECKPOINT_NAME", "").strip(),
            image_width=_as_int("IMAGE_WIDTH", 832),
            image_height=_as_int("IMAGE_HEIGHT", 1216),
            image_steps=_as_int("IMAGE_STEPS", 24),
            image_cfg=_as_float("IMAGE_CFG", 6.0),
            image_sampler=os.getenv("IMAGE_SAMPLER", "dpmpp_2m").strip(),
            image_scheduler=os.getenv("IMAGE_SCHEDULER", "karras").strip(),
            image_timeout_seconds=_as_int("IMAGE_TIMEOUT_SECONDS", 360),
            auto_image_default=_as_bool("AUTO_IMAGE_DEFAULT", False),
            story_profile_path=story_path,
            generated_images_dir=project_root / "generated_images",
        )

    def configuration_status(self) -> dict[str, bool]:
        return {
            "llm_api_key": bool(self.llm_api_key),
            "gateway_api_key": bool(self.gateway_api_key),
            "checkpoint": bool(self.checkpoint_name),
        }
