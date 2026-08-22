from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .comfy import ComfyClient, ComfyError
from .commands import ImageCommand, parse_command
from .config import Settings
from .policy import PUBLIC_STORY_SYSTEM_PROMPT, check_public_image_policy, is_visually_relevant
from .prompts import build_visual_prompt
from .state import StateStore
from .upstream import OpenAICompatibleClient, UpstreamError


class Message(BaseModel):
    role: str
    content: Any


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "storycanvas"
    messages: list[Message] = Field(min_length=1)
    stream: bool = False
    temperature: float = 0.8
    max_tokens: int | None = None


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")) for item in content if isinstance(item, dict)
        )
    return str(content or "")


def _result(content: str, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "storycanvas",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage or {},
    }


def _story_profile(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings.load(Path.cwd())
    state = StateStore(cfg.root / "state.json", cfg.auto_image_default)
    upstream = OpenAICompatibleClient(cfg)
    comfy = ComfyClient(cfg)
    app = FastAPI(
        title="StoryCanvas AI",
        version="0.1.0",
        description="OpenAI-compatible text-adventure gateway with local ComfyUI illustrations.",
    )

    async def require_key(authorization: str | None = Header(default=None)) -> None:
        if not cfg.gateway_api_key:
            raise HTTPException(status_code=503, detail="GATEWAY_API_KEY is not configured")
        if authorization != f"Bearer {cfg.gateway_api_key}":
            raise HTTPException(status_code=401, detail="Invalid gateway API key")

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": "StoryCanvas AI", "docs": "/docs", "health": "/health"}

    @app.get("/health")
    async def health() -> JSONResponse:
        comfy_ok = False
        device = None
        try:
            stats = await comfy.system_stats()
            devices = stats.get("devices") or []
            comfy_ok = True
            device = devices[0].get("name") if devices else None
        except (httpx.HTTPError, KeyError):
            pass
        return JSONResponse(
            {
                "status": "ok" if comfy_ok else "degraded",
                "configuration": cfg.configuration_status(),
                "comfyui_ok": comfy_ok,
                "device": device,
                "auto_image": state.auto_image,
            }
        )

    @app.get("/images/{filename}")
    async def image(filename: str) -> FileResponse:
        safe_name = Path(filename).name
        path = cfg.generated_images_dir / safe_name
        if not path.is_file() or path.suffix.lower() != ".webp":
            raise HTTPException(status_code=404, detail="Image not found")
        return FileResponse(path, media_type="image/webp")

    @app.get("/v1/models", dependencies=[Depends(require_key)])
    async def models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": "storycanvas",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "local",
                }
            ],
        }

    async def stream_result(result: dict[str, Any]) -> AsyncIterator[bytes]:
        content = result["choices"][0]["message"]["content"]
        chunk = {
            "id": result["id"],
            "object": "chat.completion.chunk",
            "created": result["created"],
            "model": result["model"],
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": content},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
        chunk["choices"][0] = {"index": 0, "delta": {}, "finish_reason": "stop"}
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    @app.post(
        "/v1/chat/completions",
        dependencies=[Depends(require_key)],
        response_model=None,
    )
    async def chat_completions(request: ChatRequest) -> JSONResponse | StreamingResponse:
        latest_index = max(
            (index for index, item in enumerate(request.messages) if item.role == "user"),
            default=-1,
        )
        if latest_index < 0:
            raise HTTPException(status_code=400, detail="A user message is required")
        latest = _text(request.messages[latest_index].content)
        parsed = parse_command(latest)
        if parsed.command is ImageCommand.ENABLE:
            state.set_auto_image(True)
            result = _result("Automatic scene illustration is now enabled.")
        elif parsed.command is ImageCommand.DISABLE:
            state.set_auto_image(False)
            result = _result("Automatic scene illustration is now disabled.")
        else:
            policy = check_public_image_policy(parsed.text)
            if parsed.command is ImageCommand.FORCE and not policy.allowed:
                raise HTTPException(status_code=400, detail=policy.reason)
            messages = [item.model_dump() for item in request.messages]
            messages[latest_index]["content"] = parsed.text or latest
            system_content = PUBLIC_STORY_SYSTEM_PROMPT
            profile = _story_profile(cfg.story_profile_path)
            if profile:
                system_content += f"\n\nStory profile:\n{profile}"
            messages.insert(0, {"role": "system", "content": system_content})
            try:
                answer, upstream_payload = await upstream.complete(
                    messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                generate = parsed.command is ImageCommand.FORCE or (
                    state.auto_image and is_visually_relevant(f"{parsed.text}\n{answer}")
                )
                if generate:
                    combined_policy = check_public_image_policy(f"{parsed.text}\n{answer}")
                    if combined_policy.allowed:
                        positive, negative = await build_visual_prompt(
                            upstream, parsed.text or latest, answer
                        )
                        filename, elapsed = await comfy.generate(positive, negative)
                        image_url = f"{cfg.public_base_url}/images/{filename}"
                        answer = f"{answer.rstrip()}\n\n![Generated scene]({image_url})"
                        answer += f"\n\n_Image generated locally in {elapsed:.1f}s._"
                result = _result(answer, upstream_payload.get("usage"))
            except (UpstreamError, ComfyError) as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
        if request.stream:
            return StreamingResponse(stream_result(result), media_type="text/event-stream")
        return JSONResponse(result)

    return app


app = create_app()


def main() -> None:
    settings = Settings.load(Path.cwd())
    uvicorn.run("storycanvas.app:app", host=settings.gateway_host, port=settings.gateway_port)


if __name__ == "__main__":
    main()
