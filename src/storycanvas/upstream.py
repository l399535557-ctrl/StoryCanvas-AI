from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class UpstreamError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.8,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if not self.settings.llm_api_key:
            raise UpstreamError("LLM_API_KEY is not configured")
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        timeout = httpx.Timeout(120.0, connect=20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.settings.llm_base_url}/v1/chat/completions",
                headers=headers,
                json=body,
            )
        if response.status_code >= 400:
            raise UpstreamError(f"Text provider returned HTTP {response.status_code}")
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise UpstreamError("Text provider returned no choices")
        content = str(choices[0].get("message", {}).get("content") or "")
        return content, payload
