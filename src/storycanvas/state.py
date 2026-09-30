from __future__ import annotations

import json
from pathlib import Path
from threading import Lock


class StateStore:
    def __init__(
        self,
        path: Path,
        auto_image_default: bool,
        default_save_id: str = "default",
    ) -> None:
        self.path = path
        self._lock = Lock()
        self._state = {
            "auto_image": auto_image_default,
            "active_save_id": default_save_id,
        }
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
            self._save()

    @property
    def active_save_id(self) -> str:
        return str(self._state.get("active_save_id") or "default")

    def set_active_save_id(self, save_id: str) -> None:
        with self._lock:
            self._state["active_save_id"] = save_id
            self._save()

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
