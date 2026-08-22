# Architecture

## Components

### Chat client

Any OpenAI-compatible client can connect to the gateway. The client never talks directly to
ComfyUI and does not need to understand workflow JSON.

### FastAPI gateway

The gateway is the orchestration boundary. It authenticates requests, parses image commands,
maintains the automatic-illustration flag, calls the text provider, builds visual prompts, queues
ComfyUI jobs, stores WebP output, and composes the final response.

### Text provider

The provider performs two logically separate jobs:

1. Narrative continuation from the full conversation.
2. Visual prompt planning from only the latest action and narrated result. The planner emits
   separate identity, wardrobe, action, camera, environment, lighting, style, and negative fields.

This separation prevents raw conversation history from becoming an unstructured diffusion prompt.

### ComfyUI

The default workflow uses only Core nodes:

- `CheckpointLoaderSimple`
- `EmptyLatentImage`
- `CLIPTextEncode`
- `KSampler`
- `VAEDecodeTiled`
- `SaveImage`

The default public profile deliberately avoids ControlNet, IP-Adapter, custom nodes, and bundled
model weights. An opt-in FaceDetailer adapter can add one conservative detected-region pass through
Impact Pack; it is disabled unless the operator installs the extension and enables it explicitly.

## Request lifecycle

1. Validate the gateway bearer key.
2. Parse the latest user message for a control command.
3. Apply the public image policy before forced generation.
4. Add the story-system prompt and optional story profile.
5. Request the next narrative turn from the text provider.
6. Decide whether the turn is visually relevant.
7. Ask the provider for a structured, single-frame visual plan. The compiler deduplicates tags and
   emits stable `BREAK` sections for subject identity, action, camera, depth, lighting, and quality.
8. Queue a serialized ComfyUI job and poll its history.
9. Convert the returned image to WebP.
10. Append Markdown to the same assistant response.

## Reliability decisions

- Generation is serialized with an asynchronous lock to prevent 8 GB GPUs from receiving
  overlapping jobs.
- Batch size is fixed at one and VAE decoding is tiled.
- Face refinement, when enabled, uses a low-denoise single cycle to recover facial detail without
  intentionally restyling the full image.
- Provider and ComfyUI failures are surfaced as HTTP 502 with short, non-secret diagnostics.
- Streaming clients receive valid SSE, but the MVP buffers the narrative until the optional image
  is ready so that text and image remain one logical assistant message.
- Generated files use random UUID names and the file route strips path components.

## Extension points

- Replace the keyword visual heuristic with a classifier.
- Add Redis or SQLite for multi-user state.
- Add WebSocket progress events for long image jobs.
- Add opt-in style/identity adapters with license-aware model manifests.
- Add OpenTelemetry spans and Prometheus metrics.
- Split generation into a worker queue for multiple GPUs.
