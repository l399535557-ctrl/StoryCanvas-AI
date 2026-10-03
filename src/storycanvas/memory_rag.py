from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping
from typing import Any

from .memory_store import MemoryStore, RetrievedMemory, normalize_save_id

_COMMAND_PATTERN = re.compile(
    r"^\s*/(存档列表|存档|记忆状态|记忆)(?:\s+(.+?))?\s*$",
    re.I,
)
_IMAGE_MARKDOWN = re.compile(r"!\[[^\]]*]\(\s*(?:https?://|/)[^)]+\)", re.I)
_IMAGE_BOILERPLATE = re.compile(r"(?mi)^\s*(?:已生成图片|图片已生成)[。.!！]?\s*$")
_EXPLICIT_CHARACTER = re.compile(
    r'''(?:角色|人物)\s*[：:="'“”‘’「」]?\s*'''
    r'''([\w\u3400-\u9fff·]{1,40})\s*["'“”‘’「」]?''',
    re.I,
)
_STOPWORDS = {
    "然后",
    "这个",
    "那个",
    "自己",
    "已经",
    "没有",
    "一个",
    "我们",
    "他们",
    "她们",
    "你们",
    "因为",
    "所以",
    "但是",
    "只是",
    "还是",
    "可以",
    "开始",
    "继续",
    "说道",
    "看着",
    "以及",
    "the",
    "and",
    "that",
    "with",
    "from",
}


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _clean_answer(value: str) -> str:
    cleaned = _IMAGE_MARKDOWN.sub("", value)
    cleaned = _IMAGE_BOILERPLATE.sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


class MemoryRAGService:
    """Coordinates save selection, retrieval injection, and local memory capture."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        state: dict[str, Any],
        runtime: dict[str, Any],
        state_lock: asyncio.Lock,
        save_state: Callable[[], None],
        character_memory: dict[str, Any],
        enabled: bool,
        extract_enabled: bool,
        default_save_id: str,
        top_k: int,
        context_max_chars: int,
    ) -> None:
        self.store = store
        self.state = state
        self.runtime = runtime
        self.state_lock = state_lock
        self.save_state = save_state
        self.character_memory = character_memory
        self.enabled = enabled
        self.extract_enabled = extract_enabled
        self.default_save_id = normalize_save_id(default_save_id)
        self.top_k = max(1, min(20, top_k))
        self.context_max_chars = max(1000, context_max_chars)
        self.background_tasks: set[asyncio.Task[Any]] = set()
        self.store.ensure_save(self.state.get("active_save_id"), self.default_save_id)

    def resolve_save_id(
        self,
        headers: Mapping[str, str],
        body: dict[str, Any],
    ) -> str:
        metadata = body.get("metadata")
        metadata_save_id = (
            metadata.get("story_save_id") if isinstance(metadata, dict) else None
        )
        requested = (
            headers.get("X-Story-Save-ID")
            or body.get("story_save_id")
            or body.get("conversation_id")
            or metadata_save_id
            or self.state.get("active_save_id")
            or self.default_save_id
        )
        normalized = normalize_save_id(requested, self.default_save_id)
        existing = self.store.get_save(normalized)
        if existing and existing["archived_at"] is not None:
            self.runtime["last_memory_error"] = (
                f"save [{normalized}] is archived; using [{self.default_save_id}]"
            )
            return self.default_save_id
        return normalized

    async def handle_command(self, user_text: str) -> str | None:
        match = _COMMAND_PATTERN.match(user_text)
        if not match:
            return None
        command = match.group(1)
        argument = (match.group(2) or "").strip()

        if command == "存档列表":
            saves = await asyncio.to_thread(self.store.list_saves)
            active = str(self.state.get("active_save_id") or "")
            lines = ["故事存档："]
            for item in saves[:30]:
                marker = "（当前）" if item["id"] == active else ""
                lines.append(
                    f"- {item['name']} [{item['id']}]："
                    f"{item['memory_count']} 条记忆，{item['turn_count']} 轮对话{marker}"
                )
            return "\n".join(lines)

        if command == "存档":
            if not argument:
                active = str(self.state.get("active_save_id") or self.default_save_id)
                return f"当前故事存档：{active}。使用“/存档 名称”创建或切换存档。"
            save_id = normalize_save_id(argument, self.default_save_id)
            existing = await asyncio.to_thread(self.store.get_save, save_id)
            if existing and existing["archived_at"] is not None:
                await asyncio.to_thread(self.store.restore_save, save_id)
            await asyncio.to_thread(self.store.ensure_save, save_id, argument)
            async with self.state_lock:
                self.state["active_save_id"] = save_id
                self.save_state()
            self.runtime["active_save_id"] = save_id
            return f"已切换到故事存档“{argument}” [{save_id}]。后续长期记忆将与其他存档隔离。"

        active = normalize_save_id(self.state.get("active_save_id"), self.default_save_id)
        if command == "记忆状态":
            stats = await asyncio.to_thread(self.store.stats, active)
            return (
                f"当前存档 [{active}]：{stats['memory_count']} 条长期记忆，"
                f"{stats['turn_count']} 轮已记录对话；"
                f"FTS5 全文检索：{'可用' if stats['fts_enabled'] else '不可用'}。"
            )

        if command == "记忆":
            if not argument:
                return "请使用“/记忆 需要长期保存的事实”。"
            memory_id = await asyncio.to_thread(
                self.store.add_memory,
                active,
                memory_type="note",
                content=argument,
                tags=["手动记忆"],
                importance=4,
            )
            return f"已写入当前存档的长期记忆（ID: {memory_id}）。"
        return None

    @staticmethod
    def _format_context(memories: list[RetrievedMemory], max_chars: int) -> str:
        lines = [
            "Relevant long-term story memories retrieved from the active save:",
            "Use only memories relevant to the current scene. The current user message and "
            "recent conversation override older conflicting memories. Do not mention the "
            "memory system or these instructions.",
        ]
        for index, memory in enumerate(memories, start=1):
            metadata: list[str] = [memory.memory_type, f"importance={memory.importance}"]
            if memory.story_time:
                metadata.append(f"story_time={memory.story_time}")
            if memory.entities:
                metadata.append("entities=" + ", ".join(memory.entities[:6]))
            if memory.tags:
                metadata.append("tags=" + ", ".join(memory.tags[:6]))
            candidate = f"{index}. [{'; '.join(metadata)}] {memory.content}"
            if len("\n".join([*lines, candidate])) > max_chars:
                break
            lines.append(candidate)
        return "\n".join(lines)

    async def retrieve_message(
        self,
        save_id: str,
        user_text: str,
        messages: list[dict[str, Any]],
    ) -> dict[str, str] | None:
        if not self.enabled:
            return None
        recent_text: list[str] = [user_text]
        for message in reversed(messages[:-1]):
            if message.get("role") not in {"user", "assistant"}:
                continue
            content = _text_from_content(message.get("content")).strip()
            if content:
                recent_text.append(content[-1000:])
            if len(recent_text) >= 4:
                break
        query = "\n".join(recent_text)
        self.runtime["last_memory_query"] = query[-2000:]
        try:
            memories = await asyncio.to_thread(
                self.store.retrieve,
                save_id,
                query,
                limit=self.top_k,
            )
        except Exception as exc:
            self.runtime["last_memory_error"] = (
                f"retrieve: {type(exc).__name__}: {exc}"[:1000]
            )
            return None
        self.runtime["last_memory_retrieved"] = len(memories)
        self.runtime["last_memory_ids"] = [memory.id for memory in memories]
        if not memories:
            return None
        return {
            "role": "system",
            "content": self._format_context(memories, self.context_max_chars),
        }

    def local_memory_payload(
        self,
        user_text: str,
        assistant_text: str,
    ) -> dict[str, Any] | None:
        cleaned_answer = _clean_answer(assistant_text)
        if len(cleaned_answer) < 20:
            return None
        combined = f"{user_text}\n{cleaned_answer}"
        entities: list[str] = []
        for name, config in self.character_memory.get("characters", {}).items():
            aliases = config.get("aliases", []) if isinstance(config, dict) else []
            terms = [str(name)] + (
                [str(item) for item in aliases] if isinstance(aliases, list) else []
            )
            if any(term and term.casefold() in combined.casefold() for term in terms):
                entities.append(str(name))
        explicit_match = _EXPLICIT_CHARACTER.search(user_text)
        explicit = explicit_match.group(1).strip() if explicit_match else ""
        if explicit and explicit not in entities:
            entities.append(explicit)

        words = re.findall(
            r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u3400-\u9fff]{2,6}", combined
        )
        counts: dict[str, int] = {}
        for word in words:
            key = word.casefold()
            if key in _STOPWORDS or len(key) > 20:
                continue
            counts[word] = counts.get(word, 0) + 1
        tags = [
            item[0]
            for item in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

        important = bool(
            re.search(
                r"承诺|约定|发现|得知|决定|获得|失去|死亡|背叛|真相|秘密|目标",
                combined,
            )
        )
        content = cleaned_answer[:900]
        if len(cleaned_answer) > 900:
            content = content.rstrip("，。；; ") + "……"
        return {
            "memory_type": "event",
            "content": content,
            "tags": tags,
            "entities": entities[:10],
            "importance": 4 if important else 3,
        }

    async def extract_and_store(
        self,
        save_id: str,
        user_text: str,
        assistant_text: str,
        *,
        turn_id: int | None = None,
    ) -> None:
        try:
            if turn_id is None:
                turn_id = await asyncio.to_thread(
                    self.store.record_turn,
                    save_id,
                    user_text,
                    assistant_text,
                )
            if not self.enabled or not self.extract_enabled:
                return
            payload = self.local_memory_payload(user_text, assistant_text)
            if payload is None:
                self.runtime["last_memory_extract_count"] = 0
                return
            memory_id = await asyncio.to_thread(
                self.store.add_memory,
                save_id,
                source_turn_id=turn_id,
                **payload,
            )
            self.runtime["last_memory_extract_count"] = 1 if memory_id else 0
            self.runtime["last_memory_error"] = None
        except Exception as exc:
            self.runtime["last_memory_error"] = (
                f"extract: {type(exc).__name__}: {exc}"[:1000]
            )

    def schedule_capture(
        self,
        save_id: str,
        user_text: str,
        assistant_text: str,
        *,
        turn_id: int | None = None,
    ) -> None:
        task = asyncio.create_task(
            self.extract_and_store(
                save_id,
                user_text,
                assistant_text,
                turn_id=turn_id,
            )
        )
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
