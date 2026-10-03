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
    face_detailer_enabled: bool
    face_detailer_model: str
    face_detailer_guide_size: int
    face_detailer_max_size: int
    face_detailer_steps: int
    face_detailer_cfg: float
    face_detailer_denoise: float
    face_detailer_threshold: float
    face_detailer_dilation: int
    face_detailer_crop_factor: float
    face_detailer_feather: int
    auto_image_default: bool
    memory_enabled: bool
    memory_extract_enabled: bool
    memory_database_path: Path
    memory_default_save_id: str
    memory_top_k: int
    memory_context_max_chars: int
    story_profile_path: Path
    generated_images_dir: Path
    log_level: str = "INFO"
    log_file: Path | None = None
    memory_backup_dir: Path | None = None

    @classmethod
    def load(cls, root: Path | None = None) -> Settings:
        project_root = (root or Path.cwd()).resolve()
        load_dotenv(project_root / ".env")
        story_path = Path(os.getenv("STORY_PROFILE_PATH", "examples/story_profile.example.md"))
        if not story_path.is_absolute():
            story_path = project_root / story_path
        memory_path = Path(os.getenv("MEMORY_DATABASE", "story_memory.sqlite3"))
        if not memory_path.is_absolute():
            memory_path = project_root / memory_path
        log_file_value = os.getenv("LOG_FILE", "").strip()
        log_file = Path(log_file_value) if log_file_value else None
        if log_file is not None and not log_file.is_absolute():
            log_file = project_root / log_file
        backup_value = os.getenv("MEMORY_BACKUP_DIR", "backups").strip()
        backup_dir = Path(backup_value) if backup_value else project_root / "backups"
        if not backup_dir.is_absolute():
            backup_dir = project_root / backup_dir
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
            face_detailer_enabled=_as_bool("FACE_DETAILER_ENABLED", False),
            face_detailer_model=os.getenv(
                "FACE_DETAILER_MODEL", "bbox/face_yolov8m.pt"
            ).strip(),
            face_detailer_guide_size=_as_int("FACE_DETAILER_GUIDE_SIZE", 576),
            face_detailer_max_size=_as_int("FACE_DETAILER_MAX_SIZE", 768),
            face_detailer_steps=_as_int("FACE_DETAILER_STEPS", 12),
            face_detailer_cfg=_as_float("FACE_DETAILER_CFG", 5.0),
            face_detailer_denoise=_as_float("FACE_DETAILER_DENOISE", 0.16),
            face_detailer_threshold=_as_float("FACE_DETAILER_THRESHOLD", 0.35),
            face_detailer_dilation=_as_int("FACE_DETAILER_DILATION", 16),
            face_detailer_crop_factor=_as_float("FACE_DETAILER_CROP_FACTOR", 2.4),
            face_detailer_feather=_as_int("FACE_DETAILER_FEATHER", 24),
            auto_image_default=_as_bool("AUTO_IMAGE_DEFAULT", False),
            memory_enabled=_as_bool("MEMORY_ENABLED", True),
            memory_extract_enabled=_as_bool("MEMORY_EXTRACT_ENABLED", True),
            memory_database_path=memory_path,
            memory_default_save_id=os.getenv("MEMORY_DEFAULT_SAVE_ID", "default").strip(),
            memory_top_k=_as_int("MEMORY_TOP_K", 8),
            memory_context_max_chars=_as_int("MEMORY_CONTEXT_MAX_CHARS", 6000),
            story_profile_path=story_path,
            generated_images_dir=project_root / "generated_images",
            log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
            log_file=log_file,
            memory_backup_dir=backup_dir,
        )

    def configuration_status(self) -> dict[str, bool]:
        return {
            "llm_api_key": bool(self.llm_api_key),
            "gateway_api_key": bool(self.gateway_api_key),
            "checkpoint": bool(self.checkpoint_name),
        }
