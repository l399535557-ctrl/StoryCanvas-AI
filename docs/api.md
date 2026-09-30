# HTTP API

## Authentication

All `/v1/*` endpoints require:

```http
Authorization: Bearer <GATEWAY_API_KEY>
```

`/`, `/health`, and generated image URLs do not require authentication so chat clients can render
Markdown images. Remote deployment must therefore remain inside a trusted Tailnet.

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

Streaming requests use Server-Sent Events and finish with `data: [DONE]`. Version 0.2 buffers the
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

Lists saves, the active save ID, and per-save counts. Requires bearer authentication.

## `GET /v1/story/saves/{save_id}/memories`

Lists up to 100 memories from one save. The optional `limit` query parameter controls the result
count.

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

## `GET /images/{filename}`

Serves generated WebP files. Only a basename ending in `.webp` is accepted.
