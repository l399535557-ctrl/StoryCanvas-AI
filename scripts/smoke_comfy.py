from __future__ import annotations

import asyncio
from pathlib import Path

from storycanvas.comfy import ComfyClient
from storycanvas.config import Settings

POSITIVE = (
    "one adult explorer, weathered navy coat, brass compass, standing inside a vast floating "
    "observatory above storm clouds, impossible constellations visible through the glass dome, "
    "wide cinematic composition, dramatic amber and blue lighting, detailed architecture, "
    "cinematic anime illustration, coherent anatomy, masterpiece, best quality, very aesthetic"
)
NEGATIVE = (
    "worst quality, low quality, lowres, blurry, bad anatomy, bad hands, extra fingers, "
    "extra limbs, duplicate, text, watermark, logo"
)


async def run() -> None:
    settings = Settings.load(Path.cwd())
    client = ComfyClient(settings)
    filename, elapsed = await client.generate(POSITIVE, NEGATIVE)
    print(f"generated_images/{filename} | {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(run())
