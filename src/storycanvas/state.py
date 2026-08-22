from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class StateStore:
    def __init__(self, path: Path, auto_image_default: bool) -> None:
        self.path = path
        self._lock = Lock()
        self._state = {"auto_image": auto_image_default}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self._state.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass

    @property
    def auto_image(self) -> bool:
        return bool(self._state.get("auto_image", False))

    def set_auto_image(self, enabled: bool) -> None:
        with self._lock:
            self._state["auto_image"] = enabled
            self.path.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
