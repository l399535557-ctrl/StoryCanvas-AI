from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException

from .memory_store import MemoryStore, normalize_save_id


def build_memory_router(
    *,
    store: MemoryStore,
    state: dict[str, Any],
    require_gateway_key: Callable[..., Any],
    default_save_id: str,
) -> APIRouter:
    router = APIRouter(prefix="/v1/story", tags=["story-memory"])
    protected = [Depends(require_gateway_key)]

    @router.get("/saves", dependencies=protected)
    async def story_saves() -> dict[str, Any]:
        return {
            "active_save_id": state.get("active_save_id"),
            "data": await asyncio.to_thread(store.list_saves),
        }

    @router.get("/saves/{save_id}/memories", dependencies=protected)
    async def story_memories(save_id: str, limit: int = 100) -> dict[str, Any]:
        normalized = normalize_save_id(save_id, default_save_id)
        return {
            "save_id": normalized,
            "data": await asyncio.to_thread(
                store.list_memories,
                normalized,
                limit=limit,
            ),
        }

    @router.post("/saves/{save_id}/memories", dependencies=protected)
    async def create_story_memory(
        save_id: str,
        body: Annotated[dict[str, Any], Body()],
    ) -> dict[str, Any]:
        normalized = normalize_save_id(save_id, default_save_id)
        memory_id = await asyncio.to_thread(
            store.add_memory,
            normalized,
            memory_type=body.get("type", "note"),
            content=body.get("content", ""),
            tags=body.get("tags", []),
            entities=body.get("entities", []),
            importance=body.get("importance", 3),
            story_time=body.get("story_time"),
        )
        if memory_id is None:
            raise HTTPException(status_code=400, detail="memory content is required")
        return {"save_id": normalized, "memory_id": memory_id}

    return router
