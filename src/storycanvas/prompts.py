from __future__ import annotations

import json
from collections.abc import Mapping

from .upstream import OpenAICompatibleClient

DEFAULT_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, flat lighting, bad anatomy, bad hands, "
    "extra fingers, extra limbs, duplicate, text, watermark, logo"
)

FIELD_ORDER = (
    "subjects",
    "face_body_identity",
    "wardrobe_materials",
    "action_interaction",
    "camera_composition",
    "scene_environment",
    "lighting_color",
    "style_quality",
)


def parse_json_object_text(content: str) -> dict[str, object]:
    """Extract the first valid JSON object from prose or a fenced response."""
    decoder = json.JSONDecoder()
    for index, character in enumerate(content):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(content[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No JSON object found")


def _items(value: object) -> list[str]:
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, list):
        raw = [str(item) for item in value]
    else:
        raw = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        normalized = " ".join(item.strip().split())
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def compile_visual_prompt(parsed: Mapping[str, object]) -> tuple[str, str]:
    """Compile a visual-director plan into stable BREAK-delimited prompt sections."""
    sections: list[str] = []
    for field in FIELD_ORDER:
        values = _items(parsed.get(field))
        if values:
            sections.append(", ".join(values))
    quality = (
        "cinematic anime illustration, precise facial features, detailed eyes, "
        "detailed hands, coherent anatomy, controlled line weight, layered depth, "
        "masterpiece, best quality, very aesthetic"
    )
    sections.append(quality)
    negative = ", ".join(_items(parsed.get("negative"))) or DEFAULT_NEGATIVE
    return " BREAK ".join(sections), negative


async def build_visual_prompt(
    client: OpenAICompatibleClient, user_text: str, assistant_text: str
) -> tuple[str, str]:
    instruction = """
Act as a visual director for one SDXL/Illustrious illustration. Return one JSON object only.
Use these fields, each as an array of concise English visual tags:
subjects, face_body_identity, wardrobe_materials, action_interaction,
camera_composition, scene_environment, lighting_color, style_quality, negative.

Rules:
- Preserve the exact number, identity, visible traits, clothing, action, and location established
  by the story. Never merge or duplicate subjects.
- Freeze one decisive instant. Do not describe a timeline or incompatible limb positions.
- Expand details the prose may omit: shot size, viewpoint, lens feel, depth layers, focal hierarchy,
  professional lighting, color contrast, material response, facial expression, and hand placement.
- Keep identity traits separate from temporary action and wardrobe. Prefer 50-75 useful tags total;
  avoid synonyms, filler, dialogue, captions, logos, and text inside the image.
- Keep every scene suitable for a general-audience fictional text-adventure.
""".strip()
    fallback = (
        "one coherent story moment, exact subject count, readable facial expression, "
        "clear hand placement BREAK medium cinematic composition, natural perspective, "
        "foreground midground background separation BREAK environment matching the narrated scene, "
        "motivated key light, soft fill light, controlled rim light, balanced color contrast BREAK "
        "cinematic anime illustration, precise facial features, detailed eyes, detailed hands, "
        "coherent anatomy, controlled line weight, layered depth, masterpiece, best quality, "
        "very aesthetic"
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
            max_tokens=1100,
        )
        parsed = parse_json_object_text(content)
        positive, negative = compile_visual_prompt(parsed)
        return positive or fallback, negative or DEFAULT_NEGATIVE
    except (ValueError, TypeError):
        return fallback, DEFAULT_NEGATIVE
