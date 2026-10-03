from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from .comfy import ComfyClient
from .config import Settings

QueuedCallback = Callable[[str], Awaitable[None]]
CancellationCheck = Callable[[], Awaitable[bool]]


@runtime_checkable
class ImageBackend(Protocol):
    """Model-independent contract used by orchestration and task management."""

    @property
    def name(self) -> str: ...

    async def system_stats(self) -> dict[str, Any]: ...

    async def generate(
        self,
        positive: str,
        negative: str,
        *,
        on_queued: QueuedCallback | None = None,
        is_cancelled: CancellationCheck | None = None,
    ) -> tuple[str, float]: ...


def create_image_backend(settings: Settings) -> ImageBackend:
    backend = settings.image_backend.strip().casefold()
    if backend == "comfy-sdxl":
        return ComfyClient(settings, backend_name=backend)
    raise ValueError(f"unsupported image backend: {settings.image_backend}")
