from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from .memory_store import MemoryStore, normalize_save_id


class SaveCreate(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    name: str = Field(min_length=1, max_length=120)


class SaveUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SaveCopy(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)


class SaveImport(BaseModel):
    target_id: str | None = Field(default=None, max_length=120)
    target_name: str | None = Field(default=None, max_length=120)
    bundle: dict[str, Any]


class BackupCreate(BaseModel):
    label: str | None = Field(default=None, max_length=80)


class MemoryCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    memory_type: str = Field(default="note", alias="type", max_length=32)
    content: str = Field(min_length=1, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    entities: list[str] = Field(default_factory=list, max_length=10)
    importance: int = Field(default=3, ge=1, le=5)
    story_time: str | None = Field(default=None, max_length=120)


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    memory_type: str | None = Field(default=None, alias="type", max_length=32)
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    tags: list[str] | None = Field(default=None, max_length=12)
    entities: list[str] | None = Field(default=None, max_length=10)
    importance: int | None = Field(default=None, ge=1, le=5)
    story_time: str | None = Field(default=None, max_length=120)


def build_memory_router(
    *,
    store: MemoryStore,
    state: dict[str, Any],
    require_gateway_key: Callable[..., Any],
    default_save_id: str,
    backup_directory: Path,
) -> APIRouter:
    router = APIRouter(prefix="/v1/story", tags=["story-data"])
    protected = [Depends(require_gateway_key)]

    def normalized_save(save_id: str) -> str:
        return normalize_save_id(save_id, default_save_id)

    async def require_save(save_id: str) -> tuple[str, dict[str, Any]]:
        normalized = normalized_save(save_id)
        item = await asyncio.to_thread(store.get_save, normalized)
        if item is None:
            raise HTTPException(status_code=404, detail="story save not found")
        return normalized, item

    @router.get("/saves", dependencies=protected)
    async def story_saves(
        include_archived: Annotated[bool, Query()] = False,
    ) -> dict[str, Any]:
        return {
            "active_save_id": state.get("active_save_id"),
            "data": await asyncio.to_thread(
                store.list_saves,
                include_archived=include_archived,
            ),
        }

    @router.post(
        "/saves",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_story_save(body: SaveCreate) -> dict[str, Any]:
        normalized = normalize_save_id(body.id or body.name, default_save_id)
        if await asyncio.to_thread(store.get_save, normalized) is not None:
            raise HTTPException(status_code=409, detail="story save already exists")
        await asyncio.to_thread(store.ensure_save, normalized, body.name)
        return {"data": await asyncio.to_thread(store.get_save, normalized)}

    @router.patch("/saves/{save_id}", dependencies=protected)
    async def update_story_save(save_id: str, body: SaveUpdate) -> dict[str, Any]:
        normalized, item = await require_save(save_id)
        if item["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        updated = await asyncio.to_thread(store.rename_save, normalized, body.name)
        if not updated:
            raise HTTPException(status_code=404, detail="story save not found")
        return {"data": await asyncio.to_thread(store.get_save, normalized)}

    @router.delete("/saves/{save_id}", dependencies=protected)
    async def archive_story_save(save_id: str) -> dict[str, Any]:
        normalized, item = await require_save(save_id)
        if normalized == normalize_save_id(default_save_id):
            raise HTTPException(status_code=409, detail="the default save cannot be archived")
        if normalized == normalize_save_id(state.get("active_save_id"), default_save_id):
            raise HTTPException(
                status_code=409,
                detail="switch to another save before archiving the active save",
            )
        if item["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="story save is already archived")
        await asyncio.to_thread(store.archive_save, normalized)
        return {"save_id": normalized, "archived": True}

    @router.post("/saves/{save_id}/restore", dependencies=protected)
    async def restore_story_save(save_id: str) -> dict[str, Any]:
        normalized, item = await require_save(save_id)
        if item["archived_at"] is None:
            raise HTTPException(status_code=409, detail="story save is not archived")
        await asyncio.to_thread(store.restore_save, normalized)
        return {"save_id": normalized, "archived": False}

    @router.get("/saves/{save_id}/export", dependencies=protected)
    async def export_story_save(
        save_id: str,
        include_archived: Annotated[bool, Query()] = False,
    ) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        return await asyncio.to_thread(
            store.export_save,
            normalized,
            include_archived=include_archived,
        )

    @router.post(
        "/saves/import",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def import_story_save(body: SaveImport) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(
                store.import_save,
                body.bundle,
                target_save_id=body.target_id,
                target_name=body.target_name,
            )
        except ValueError as exc:
            message = str(exc)
            code = 409 if "already exists" in message else 400
            raise HTTPException(status_code=code, detail=message) from exc
        return {"data": result}

    @router.post(
        "/saves/{save_id}/copy",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def copy_story_save(save_id: str, body: SaveCopy) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        target_id = normalize_save_id(body.id, default_save_id)
        try:
            result = await asyncio.to_thread(
                store.copy_save,
                normalized,
                target_id,
                body.name,
            )
        except ValueError as exc:
            message = str(exc)
            code = 409 if "already exists" in message else 400
            raise HTTPException(status_code=code, detail=message) from exc
        return {"data": result}

    @router.get("/saves/{save_id}/turns", dependencies=protected)
    async def story_turns(
        save_id: str,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        return {
            "save_id": normalized,
            "limit": limit,
            "offset": offset,
            "data": await asyncio.to_thread(
                store.list_turns,
                normalized,
                limit=limit,
                offset=offset,
            ),
        }

    @router.get("/tasks", dependencies=protected)
    async def generation_tasks(
        save_id: Annotated[str | None, Query()] = None,
        task_status: Annotated[str | None, Query(alias="status")] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> dict[str, Any]:
        try:
            data = await asyncio.to_thread(
                store.list_generation_tasks,
                save_id=save_id,
                status=task_status,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"limit": limit, "offset": offset, "data": data}

    @router.get("/tasks/{task_id}", dependencies=protected)
    async def generation_task(task_id: str) -> dict[str, Any]:
        item = await asyncio.to_thread(store.get_generation_task, task_id)
        if item is None:
            raise HTTPException(status_code=404, detail="generation task not found")
        return {"data": item}

    @router.get("/backups", dependencies=protected)
    async def database_backups() -> dict[str, Any]:
        return {
            "data": await asyncio.to_thread(
                store.list_database_backups,
                backup_directory,
            )
        }

    @router.post(
        "/backups",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_database_backup(body: BackupCreate | None = None) -> dict[str, Any]:
        item = await asyncio.to_thread(
            store.create_database_backup,
            backup_directory,
            label=body.label if body else None,
        )
        return {"data": item}

    @router.post("/backups/{filename}/restore", dependencies=protected)
    async def restore_database_backup(filename: str) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(
                store.restore_database_backup,
                backup_directory,
                filename,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"data": result}

    @router.get("/saves/{save_id}/memories", dependencies=protected)
    async def story_memories(
        save_id: str,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
        include_archived: Annotated[bool, Query()] = False,
    ) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        return {
            "save_id": normalized,
            "limit": limit,
            "offset": offset,
            "data": await asyncio.to_thread(
                store.list_memories,
                normalized,
                limit=limit,
                offset=offset,
                include_archived=include_archived,
            ),
        }

    @router.post(
        "/saves/{save_id}/memories",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_story_memory(save_id: str, body: MemoryCreate) -> dict[str, Any]:
        normalized, item = await require_save(save_id)
        if item["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        memory_id = await asyncio.to_thread(
            store.add_memory,
            normalized,
            memory_type=body.memory_type,
            content=body.content,
            tags=body.tags,
            entities=body.entities,
            importance=body.importance,
            story_time=body.story_time,
        )
        if memory_id is None:
            raise HTTPException(status_code=400, detail="memory content is required")
        created = await asyncio.to_thread(store.get_memory, normalized, memory_id)
        if created and created["archived_at"] is not None:
            raise HTTPException(
                status_code=409,
                detail="an identical archived memory exists; restore it instead",
            )
        return {
            "save_id": normalized,
            "data": created,
        }

    @router.patch("/saves/{save_id}/memories/{memory_id}", dependencies=protected)
    async def update_story_memory(
        save_id: str,
        memory_id: int,
        body: MemoryUpdate,
    ) -> dict[str, Any]:
        normalized, save = await require_save(save_id)
        if save["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        existing = await asyncio.to_thread(store.get_memory, normalized, memory_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="memory not found")
        if existing["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the memory before editing")
        values = body.model_dump(exclude_unset=True)
        try:
            await asyncio.to_thread(
                store.update_memory,
                normalized,
                memory_id,
                memory_type=values.get("memory_type", existing["memory_type"]),
                content=values.get("content", existing["content"]),
                tags=values.get("tags", existing["tags"]),
                entities=values.get("entities", existing["entities"]),
                importance=values.get("importance", existing["importance"]),
                story_time=values.get("story_time", existing["story_time"]),
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"data": await asyncio.to_thread(store.get_memory, normalized, memory_id)}

    @router.delete("/saves/{save_id}/memories/{memory_id}", dependencies=protected)
    async def archive_story_memory(save_id: str, memory_id: int) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        archived = await asyncio.to_thread(store.archive_memory, normalized, memory_id)
        if not archived:
            raise HTTPException(status_code=404, detail="active memory not found")
        return {"save_id": normalized, "memory_id": memory_id, "archived": True}

    @router.post(
        "/saves/{save_id}/memories/{memory_id}/conflict",
        dependencies=protected,
    )
    async def mark_story_memory_conflicted(save_id: str, memory_id: int) -> dict[str, Any]:
        normalized, save = await require_save(save_id)
        if save["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        updated = await asyncio.to_thread(
            store.set_memory_status,
            normalized,
            memory_id,
            "conflicted",
        )
        if not updated:
            raise HTTPException(status_code=404, detail="active memory not found")
        return {"data": await asyncio.to_thread(store.get_memory, normalized, memory_id)}

    @router.post(
        "/saves/{save_id}/memories/{memory_id}/activate",
        dependencies=protected,
    )
    async def activate_story_memory(save_id: str, memory_id: int) -> dict[str, Any]:
        normalized, save = await require_save(save_id)
        if save["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        updated = await asyncio.to_thread(
            store.set_memory_status,
            normalized,
            memory_id,
            "active",
        )
        if not updated:
            raise HTTPException(status_code=404, detail="memory not found")
        return {"data": await asyncio.to_thread(store.get_memory, normalized, memory_id)}

    @router.post(
        "/saves/{save_id}/memories/{memory_id}/supersede",
        dependencies=protected,
        status_code=status.HTTP_201_CREATED,
    )
    async def supersede_story_memory(
        save_id: str,
        memory_id: int,
        body: MemoryCreate,
    ) -> dict[str, Any]:
        normalized, save = await require_save(save_id)
        if save["archived_at"] is not None:
            raise HTTPException(status_code=409, detail="restore the story save before editing")
        try:
            replacement_id = await asyncio.to_thread(
                store.supersede_memory,
                normalized,
                memory_id,
                memory_type=body.memory_type,
                content=body.content,
                tags=body.tags,
                entities=body.entities,
                importance=body.importance,
                story_time=body.story_time,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="memory not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "superseded_memory_id": memory_id,
            "data": await asyncio.to_thread(store.get_memory, normalized, replacement_id),
        }

    @router.post(
        "/saves/{save_id}/memories/{memory_id}/restore",
        dependencies=protected,
    )
    async def restore_story_memory(save_id: str, memory_id: int) -> dict[str, Any]:
        normalized, _ = await require_save(save_id)
        restored = await asyncio.to_thread(store.restore_memory, normalized, memory_id)
        if not restored:
            raise HTTPException(status_code=404, detail="archived memory not found")
        return {"save_id": normalized, "memory_id": memory_id, "archived": False}

    return router
