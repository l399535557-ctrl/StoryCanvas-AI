from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ImageCommand(StrEnum):
    FORCE = "force"
    ENABLE = "enable"
    DISABLE = "disable"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    command: ImageCommand
    text: str


_COMMAND = re.compile(
    r"^\s*(/图开|/图关|/图|#图开|#图关|#图|/image-on|/image-off|/image)(?:\s*[:：]?\s*)",
    re.IGNORECASE,
)


def parse_command(text: str) -> ParsedCommand:
    match = _COMMAND.match(text)
    if not match:
        return ParsedCommand(ImageCommand.NONE, text.strip())
    token = match.group(1).lower()
    command = {
        "/图": ImageCommand.FORCE,
        "#图": ImageCommand.FORCE,
        "/image": ImageCommand.FORCE,
        "/图开": ImageCommand.ENABLE,
        "#图开": ImageCommand.ENABLE,
        "/image-on": ImageCommand.ENABLE,
        "/图关": ImageCommand.DISABLE,
        "#图关": ImageCommand.DISABLE,
        "/image-off": ImageCommand.DISABLE,
    }[token]
    return ParsedCommand(command, text[match.end() :].strip())
