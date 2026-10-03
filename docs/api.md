# HTTP API

## Authentication

All `/v1/*` endpoints require:

```http
Authorization: Bearer <GATEWAY_API_KEY>
```

`/`, `/health`, and generated image URLs do not require authentication so chat clients can render
Markdown images. Remote deployment must therefore remain inside a trusted Tailnet.

Every response includes `X-Request-ID`. A client may provide a safe ID containing up to 64 ASCII
letters, digits, dots, underscores, or hyphens; otherwise the gateway generates one. HTTP and
validation error bodies also include `request_id` for log correlation.

## `GET /health`

Returns configuration flags, ComfyUI availability, GPU name, and automatic illustration state.
Secrets are never returned.

## `GET /v1/models`

Returns one virtual orchestration model named `storycanvas`.

## `POST /v1/chat/completions`

Example:

```json
{
  "model": "storycanvas",
  "stream": false,
  "story_save_id": "observatory-campaign",
  "messages": [
    {"role": "user", "content": "/image I open the observatory door."}
  ]
}
```

The response follows the OpenAI chat-completions shape. When image generation is active, the
assistant content ends with a Markdown image URL served by the gateway.

Streaming requests use Server-Sent Events and finish with `data: [DONE]`. The gateway buffers the
turn so the optional image stays attached to the same assistant message, then emits the result in
small SSE chunks for compatibility with chat clients while keeping text and the optional image in
one logical assistant message.

### Save selection and memory RAG

The active story save is selected, in priority order, by:

1. `X-Story-Save-ID` request header.
2. `story_save_id` request field.
3. `conversation_id` request field.
4. The currently active/default save.

Before narrative generation, the gateway retrieves relevant memories from only that save and adds a
bounded context block. After generation, durable facts are extracted locally and written to SQLite.
Set `MEMORY_ENABLED=false` to disable retrieval and persistence, or
`MEMORY_EXTRACT_ENABLED=false` to keep retrieval while disabling automatic extraction.

## `GET /v1/story/saves`

Lists saves, the active save ID, and per-save counts. Pass `include_archived=true` to include
recoverably archived saves.

## `POST /v1/story/saves`

Creates an explicit story save. `id` is optional and is derived from `name` when omitted.

```json
{"id": "observatory-campaign", "name": "The Observatory Campaign"}
```

## `PATCH /v1/story/saves/{save_id}`

Renames an active save without changing its stable ID.

```json
{"name": "Observatory - Second Playthrough"}
```

## `DELETE /v1/story/saves/{save_id}`

Archives a save instead of physically deleting it. The active save cannot be archived until the
client switches to another save. The configured default save cannot be archived because it is the
fallback for requests that do not specify a save.

## `POST /v1/story/saves/{save_id}/restore`

Restores an archived save with its turns and memories intact.

## `GET /v1/story/saves/{save_id}/export`

Exports one save as a portable, versioned JSON bundle containing save metadata, turns, and active
memories. Pass `include_archived=true` when creating a full backup that must also contain archived
memories.

## `POST /v1/story/saves/import`

Imports an exported bundle as a new save. The operation is atomic and never overwrites an existing
save ID. `target_id` and `target_name` may be supplied to rename the imported copy.

```json
{
  "target_id": "observatory-import",
  "target_name": "Imported Observatory",
  "bundle": {
    "format": "storycanvas-save",
    "version": 1,
    "save": {},
    "turns": [],
    "memories": []
  }
}
```

## `POST /v1/story/saves/{save_id}/copy`

Creates a new branch from an existing save. Active turns and memories are copied; archived memories
remain excluded.

```json
{"id": "observatory-branch", "name": "Observatory Alternate Route"}
```

## `GET /v1/story/saves/{save_id}/turns`

Returns newest-first story turns. Use `limit` (1-200) and `offset` for pagination.

## `GET /v1/story/saves/{save_id}/memories`

Lists memories from one save. Use `limit` (1-500), `offset`, and `include_archived` for pagination
and archive management.

## `POST /v1/story/saves/{save_id}/memories`

Adds a memory explicitly:

```json
{
  "type": "fact",
  "content": "The brass key opens the observatory archive.",
  "tags": ["item", "observatory"],
  "entities": ["brass key"],
  "importance": 4,
  "story_time": "chapter-2"
}
```

## `PATCH /v1/story/saves/{save_id}/memories/{memory_id}`

Partially updates a memory. Any omitted field keeps its current value. The accepted fields are
`type`, `content`, `tags`, `entities`, `importance`, and `story_time`.

## `DELETE /v1/story/saves/{save_id}/memories/{memory_id}`

Archives a memory. Archived memories are excluded from normal lists and RAG retrieval.

## `POST /v1/story/saves/{save_id}/memories/{memory_id}/restore`

Restores an archived memory.

## `POST /v1/story/saves/{save_id}/memories/{memory_id}/conflict`

Marks a questionable memory as `conflicted`. It remains available for review but is immediately
excluded from RAG retrieval.

## `POST /v1/story/saves/{save_id}/memories/{memory_id}/activate`

Returns a conflicted or superseded memory to the active retrieval set.

## `POST /v1/story/saves/{save_id}/memories/{memory_id}/supersede`

Atomically creates a corrected replacement and marks the old memory as `superseded`. The request
body is the same as memory creation. The replacement records the old ID in
`supersedes_memory_id`, retaining a reviewable fact-revision chain.

## `GET /v1/story/tasks`

Lists persistent image-generation tasks. Optional query parameters are `save_id`, `status`,
`limit`, and `offset`. Each task includes its request ID, lifecycle status, timestamps, output
filename or safe error summary, and measured generation duration.

## `GET /v1/story/tasks/{task_id}`

Returns one generation task for diagnostics and later front-end polling. Tasks left queued or
running during an unexpected restart are marked failed when the service starts again.

## `GET /v1/story/backups`

Lists whole-database SQLite snapshots stored in the configured backup directory.

## `POST /v1/story/backups`

Creates a transactionally consistent database snapshot and verifies it with SQLite
`integrity_check`. An optional JSON body such as `{"label": "before-demo"}` adds a safe label to
the generated filename.

## `POST /v1/story/backups/{filename}/restore`

Restores a verified compatible snapshot. Before replacement, the gateway automatically creates a
`pre-restore` safety snapshot of the current database. This authenticated maintenance operation
should only be exposed to a trusted local administrator.

## `GET /images/{filename}`

Serves generated WebP files. Only a basename ending in `.webp` is accepted.
