from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from . import __version__
from .comfy import ComfyError
from .commands import ImageCommand, parse_command
from .config import Settings
from .image_backend import create_image_backend
from .memory_api import build_memory_router
from .memory_rag import MemoryRAGService
from .memory_store import MemoryStore
from .observability import configure_logging, request_id_context
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
    story_save_id: str | None = None
    conversation_id: str | None = None


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
    logger = configure_logging(cfg.log_level, cfg.log_file)
    state = StateStore(
        cfg.root / "state.json",
        cfg.auto_image_default,
        cfg.memory_default_save_id,
    )
    upstream = OpenAICompatibleClient(cfg)
    image_backend = create_image_backend(cfg)
    memory_store = MemoryStore(cfg.memory_database_path)
    memory_state: dict[str, Any] = {"active_save_id": state.active_save_id}
    memory_runtime: dict[str, Any] = {
        "active_save_id": state.active_save_id,
        "last_memory_query": None,
        "last_memory_retrieved": 0,
        "last_memory_ids": [],
        "last_memory_extract_count": 0,
        "last_memory_error": None,
    }
    memory_lock = asyncio.Lock()
    background_generation_tasks: set[asyncio.Task[Any]] = set()

    def safe_memory_runtime() -> dict[str, Any]:
        return {
            "last_memory_retrieved": memory_runtime["last_memory_retrieved"],
            "last_memory_ids": memory_runtime["last_memory_ids"],
            "last_memory_extract_count": memory_runtime["last_memory_extract_count"],
            "has_error": memory_runtime["last_memory_error"] is not None,
        }

    def save_memory_state() -> None:
        state.set_active_save_id(str(memory_state["active_save_id"]))

    memory_service = MemoryRAGService(
        store=memory_store,
        state=memory_state,
        runtime=memory_runtime,
        state_lock=memory_lock,
        save_state=save_memory_state,
        character_memory={"characters": {}},
        enabled=cfg.memory_enabled,
        extract_enabled=cfg.memory_extract_enabled,
        default_save_id=cfg.memory_default_save_id,
        top_k=cfg.memory_top_k,
        context_max_chars=cfg.memory_context_max_chars,
    )
    app = FastAPI(
        title="StoryCanvas AI",
        version="0.13.0",
        description="OpenAI-compatible text-adventure gateway with local ComfyUI illustrations.",
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next: Any) -> Any:
        requested_id = request.headers.get("X-Request-ID", "").strip()
        request_id = (
            requested_id
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", requested_id)
            else uuid.uuid4().hex
        )
        token = request_id_context.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "error_type": type(exc).__name__,
                },
            )
            raise
        else:
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            request_id_context.reset(token)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "request_id": getattr(request.state, "request_id", "-"),
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "request_id": getattr(request.state, "request_id", "-"),
            },
        )

    async def require_key(authorization: str | None = Header(default=None)) -> None:
        if not cfg.gateway_api_key:
            raise HTTPException(status_code=503, detail="GATEWAY_API_KEY is not configured")
        if authorization != f"Bearer {cfg.gateway_api_key}":
            raise HTTPException(status_code=401, detail="Invalid gateway API key")

    async def run_generation_task(
        task_id: str,
        positive: str,
        negative: str,
    ) -> tuple[str, float]:
        started = await asyncio.to_thread(
            memory_store.update_generation_task,
            task_id,
            "running",
        )
        if not started:
            raise ComfyError("generation task was cancelled before starting")

        async def on_queued(prompt_id: str) -> None:
            await asyncio.to_thread(
                memory_store.set_generation_task_prompt_id,
                task_id,
                prompt_id,
            )

        async def is_cancelled() -> bool:
            item = await asyncio.to_thread(memory_store.get_generation_task, task_id)
            return item is None or item["status"] == "cancelled"

        try:
            filename, elapsed = await image_backend.generate(
                positive,
                negative,
                on_queued=on_queued,
                is_cancelled=is_cancelled,
            )
        except (ComfyError, httpx.HTTPError) as exc:
            item = await asyncio.to_thread(memory_store.get_generation_task, task_id)
            if item is not None and item["status"] != "cancelled":
                await asyncio.to_thread(
                    memory_store.update_generation_task,
                    task_id,
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            if isinstance(exc, ComfyError):
                raise
            raise ComfyError(f"ComfyUI request failed: {exc}") from exc
        updated = await asyncio.to_thread(
            memory_store.update_generation_task,
            task_id,
            "succeeded",
            image_filename=filename,
            duration_seconds=elapsed,
        )
        if not updated:
            raise ComfyError("generation task was cancelled before completion")
        return filename, elapsed

    async def capture_successful_turn(
        save_id: str,
        user_text: str,
        assistant_text: str,
        generation_task_id: str | None,
    ) -> None:
        try:
            turn_id = await asyncio.to_thread(
                memory_store.record_turn,
                save_id,
                user_text,
                assistant_text,
            )
            if generation_task_id is not None:
                linked = await asyncio.to_thread(
                    memory_store.link_generation_task_to_turn,
                    generation_task_id,
                    save_id,
                    turn_id,
                )
                if not linked:
                    logger.warning(
                        "generation_task_turn_link_failed",
                        extra={"generation_task_id": generation_task_id, "turn_id": turn_id},
                    )
            memory_service.schedule_capture(
                save_id,
                user_text,
                assistant_text,
                turn_id=turn_id,
            )
        except Exception as exc:
            memory_runtime["last_memory_error"] = (
                f"history: {type(exc).__name__}: {exc}"[:1000]
            )
            logger.exception("story_turn_capture_failed")

    app.include_router(
        build_memory_router(
            store=memory_store,
            state=memory_state,
            require_gateway_key=require_key,
            default_save_id=cfg.memory_default_save_id,
            backup_directory=(
                cfg.memory_backup_dir or cfg.memory_database_path.parent / "backups"
            ),
            generated_images_dir=cfg.generated_images_dir,
        )
    )

    @app.post(
        "/v1/story/tasks/{task_id}/cancel",
        dependencies=[Depends(require_key)],
    )
    async def cancel_generation_task(task_id: str) -> dict[str, Any]:
        cancelled = await asyncio.to_thread(memory_store.cancel_generation_task, task_id)
        if not cancelled:
            item = await asyncio.to_thread(memory_store.get_generation_task, task_id)
            if item is None:
                raise HTTPException(status_code=404, detail="generation task not found")
            raise HTTPException(status_code=409, detail="generation task is already finished")
        return {"data": await asyncio.to_thread(memory_store.get_generation_task, task_id)}

    @app.post(
        "/v1/story/tasks/{task_id}/retry",
        dependencies=[Depends(require_key)],
        status_code=202,
    )
    async def retry_generation_task(task_id: str) -> JSONResponse:
        original = await asyncio.to_thread(memory_store.get_generation_task_payload, task_id)
        if original is None:
            raise HTTPException(status_code=404, detail="generation task not found")
        if original["status"] not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="only failed or cancelled tasks can retry")
        positive = str(original["positive_prompt"] or "")
        negative = str(original["negative_prompt"] or "")
        if not positive:
            raise HTTPException(status_code=409, detail="generation prompts are unavailable")
        retry_id = await asyncio.to_thread(
            memory_store.create_generation_task,
            original["save_id"],
            request_id_context.get(),
            retry_of_task_id=task_id,
            backend=original["backend"],
            turn_id=original["turn_id"],
        )
        await asyncio.to_thread(
            memory_store.set_generation_task_prompts,
            retry_id,
            positive,
            negative,
        )

        async def retry_worker() -> None:
            try:
                await run_generation_task(retry_id, positive, negative)
            except ComfyError:
                logger.info(
                    "generation_retry_finished_with_error",
                    extra={"error_type": "ComfyError"},
                )

        task = asyncio.create_task(retry_worker())
        background_generation_tasks.add(task)
        task.add_done_callback(background_generation_tasks.discard)
        return JSONResponse(
            status_code=202,
            content={"data": await asyncio.to_thread(memory_store.get_generation_task, retry_id)},
        )

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"name": "StoryCanvas AI", "docs": "/docs", "health": "/health"}

    @app.get("/health")
    async def health() -> JSONResponse:
        comfy_ok = False
        device = None
        try:
            stats = await image_backend.system_stats()
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
                "image_backend": image_backend.name,
                "device": device,
                "auto_image": state.auto_image,
                "memory": {
                    "enabled": cfg.memory_enabled,
                    "extract_enabled": cfg.memory_extract_enabled,
                    "active_save_id": memory_state["active_save_id"],
                    "top_k": cfg.memory_top_k,
                    "context_max_chars": cfg.memory_context_max_chars,
                    **memory_store.stats(),
                    "runtime": safe_memory_runtime(),
                },
                "face_detailer": {
                    "enabled": cfg.face_detailer_enabled,
                    "model": cfg.face_detailer_model if cfg.face_detailer_enabled else None,
                },
            }
        )

    @app.get("/v1/story/diagnostics", dependencies=[Depends(require_key)])
    async def story_diagnostics() -> dict[str, Any]:
        return {
            "version": __version__,
            "configuration": cfg.configuration_status(),
            "image_backend": image_backend.name,
            "active_save_id": memory_state["active_save_id"],
            "database": await asyncio.to_thread(memory_store.diagnostics),
            "memory_runtime": safe_memory_runtime(),
        }

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
        base_chunk = {
            "id": result["id"],
            "object": "chat.completion.chunk",
            "created": result["created"],
            "model": result["model"],
            "choices": [],
        }
        role_chunk = dict(base_chunk)
        role_chunk["choices"] = [
            {"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}
        ]
        yield f"data: {json.dumps(role_chunk, ensure_ascii=True)}\n\n".encode()

        for start in range(0, len(content), 128):
            content_chunk = dict(base_chunk)
            content_chunk["choices"] = [
                {
                    "index": 0,
                    "delta": {"content": content[start : start + 128]},
                    "finish_reason": None,
                }
            ]
            yield f"data: {json.dumps(content_chunk, ensure_ascii=True)}\n\n".encode()
            await asyncio.sleep(0.02)

        stop_chunk = dict(base_chunk)
        stop_chunk["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop"}]
        yield f"data: {json.dumps(stop_chunk, ensure_ascii=True)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    @app.post(
        "/v1/chat/completions",
        dependencies=[Depends(require_key)],
        response_model=None,
    )
    async def chat_completions(
        http_request: Request,
        request: ChatRequest,
    ) -> JSONResponse | StreamingResponse:
        latest_index = max(
            (index for index, item in enumerate(request.messages) if item.role == "user"),
            default=-1,
        )
        if latest_index < 0:
            raise HTTPException(status_code=400, detail="A user message is required")
        latest = _text(request.messages[latest_index].content)
        request_payload = request.model_dump()
        request_payload.update(request.model_extra or {})
        save_id = memory_service.resolve_save_id(http_request.headers, request_payload)
        await asyncio.to_thread(memory_store.ensure_save, save_id)
        memory_runtime["active_save_id"] = save_id
        memory_command = await memory_service.handle_command(latest)
        if memory_command is not None:
            result = _result(memory_command)
            if request.stream:
                return StreamingResponse(stream_result(result), media_type="text/event-stream")
            return JSONResponse(result)
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
            memory_message = await memory_service.retrieve_message(
                save_id,
                parsed.text or latest,
                messages,
            )
            system_content = PUBLIC_STORY_SYSTEM_PROMPT
            profile = _story_profile(cfg.story_profile_path)
            if profile:
                system_content += f"\n\nStory profile:\n{profile}"
            messages.insert(0, {"role": "system", "content": system_content})
            if memory_message is not None:
                messages.insert(1, memory_message)
            try:
                answer, upstream_payload = await upstream.complete(
                    messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                generation_task_id: str | None = None
                generate = parsed.command is ImageCommand.FORCE or (
                    state.auto_image and is_visually_relevant(f"{parsed.text}\n{answer}")
                )
                if generate:
                    combined_policy = check_public_image_policy(f"{parsed.text}\n{answer}")
                    if combined_policy.allowed:
                        generation_task_id = await asyncio.to_thread(
                            memory_store.create_generation_task,
                            save_id,
                            request_id_context.get(),
                            backend=image_backend.name,
                        )
                        try:
                            positive, negative = await build_visual_prompt(
                                upstream, parsed.text or latest, answer
                            )
                            await asyncio.to_thread(
                                memory_store.set_generation_task_prompts,
                                generation_task_id,
                                positive,
                                negative,
                            )
                            filename, elapsed = await run_generation_task(
                                generation_task_id,
                                positive,
                                negative,
                            )
                        except UpstreamError as task_error:
                            await asyncio.to_thread(
                                memory_store.update_generation_task,
                                generation_task_id,
                                "failed",
                                error=f"{type(task_error).__name__}: {task_error}",
                            )
                            raise
                        image_url = f"{cfg.public_base_url}/images/{filename}"
                        answer = f"{answer.rstrip()}\n\n![Generated scene]({image_url})"
                        answer += f"\n\n_Image generated locally in {elapsed:.1f}s._"
                await capture_successful_turn(
                    save_id,
                    parsed.text or latest,
                    answer,
                    generation_task_id,
                )
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
