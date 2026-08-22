from __future__ import annotations

import json
import re

from .upstream import OpenAICompatibleClient

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

DEFAULT_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, flat lighting, bad anatomy, bad hands, "
    "extra fingers, extra limbs, duplicate, text, watermark, logo"
)


async def build_visual_prompt(
    client: OpenAICompatibleClient, user_text: str, assistant_text: str
) -> tuple[str, str]:
    instruction = """
Convert the story beat into one SDXL/Illustrious illustration prompt. Return JSON only with
two string fields: positive and negative. Describe exact subject count, adult or child only when
the story establishes it, stable physical traits, clothing, action, pose, camera, setting, lighting,
and materials. Keep it suitable for a general-audience text-adventure demo. The positive prompt
must end with: cinematic anime illustration, detailed face, detailed eyes, detailed hands,
coherent anatomy, masterpiece, best quality, very aesthetic. Do not add dialogue or text in image.
""".strip()
    fallback = (
        f"{assistant_text[-1400:]}, cinematic anime illustration, detailed face, detailed eyes, "
        "detailed hands, coherent anatomy, masterpiece, best quality, very aesthetic"
    )
    try:
        content, _ = await client.complete(
            [
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": f"Player action:\n{user_text}\n\nNarrated result:\n{assistant_text}",
                },
            ],
            temperature=0.2,
            max_tokens=700,
        )
        match = _JSON_BLOCK.search(content)
        parsed = json.loads(match.group(0) if match else content)
        positive = str(parsed.get("positive") or "").strip()
        negative = str(parsed.get("negative") or "").strip()
        return positive or fallback, negative or DEFAULT_NEGATIVE
    except (ValueError, TypeError, json.JSONDecodeError):
        return fallback, DEFAULT_NEGATIVE
