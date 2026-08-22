from __future__ import annotations

import re
from dataclasses import dataclass

PUBLIC_STORY_SYSTEM_PROMPT = """
You are the narrator of an interactive, fictional text-adventure game. Continue the story from
the player's latest action, preserve established world facts and character motivations, and end
with a concrete situation the player can respond to. Keep the experience suitable for a general
portfolio demo: romance may be implied, but do not produce sexually explicit content, graphic
sexualization, or graphic gore. Never imitate or identify a real person.
""".strip()

_EXPLICIT = re.compile(
    r"\b(nsfw|porn|explicit sex|sexual intercourse|rape|loli|shota)\b|"
    r"色情|性爱|性交|强奸|性侵|露点|全裸|幼女|幼男",
    re.IGNORECASE,
)
_GRAPHIC_GORE = re.compile(
    r"\b(disembowel|decapitat(?:e|ion)|graphic gore)\b|开膛|斩首|血腥肢解",
    re.IGNORECASE,
)
_VISUAL = re.compile(
    r"风景|场景|外貌|服装|城堡|森林|街道|房间|战斗|登场|看见|眼前|"
    r"\b(scene|landscape|portrait|outfit|castle|forest|street|room|battle|appears?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    allowed: bool
    reason: str | None = None


def check_public_image_policy(text: str) -> PolicyResult:
    if _EXPLICIT.search(text):
        return PolicyResult(False, "The public demo does not generate sexually explicit images.")
    if _GRAPHIC_GORE.search(text):
        return PolicyResult(False, "The public demo does not generate graphic gore.")
    return PolicyResult(True)


def is_visually_relevant(text: str) -> bool:
    return bool(_VISUAL.search(text))
