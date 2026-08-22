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
  "messages": [
    {"role": "user", "content": "/image I open the observatory door."}
  ]
}
```

The response follows the OpenAI chat-completions shape. When image generation is active, the
assistant content ends with a Markdown image URL served by the gateway.

Streaming requests use Server-Sent Events and finish with `data: [DONE]`. Version 0.1 buffers the
turn so the optional image stays attached to the same assistant message.

## `GET /images/{filename}`

Serves generated WebP files. Only a basename ending in `.webp` is accepted.
