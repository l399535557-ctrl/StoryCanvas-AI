# Architecture

## Components

### Chat client

Any OpenAI-compatible client can connect to the gateway. The client never talks directly to
ComfyUI and does not need to understand workflow JSON.

### FastAPI gateway

The gateway is the orchestration boundary. It authenticates requests, parses image commands,
maintains the automatic-illustration flag, calls the text provider, builds visual prompts, queues
ComfyUI jobs, stores WebP output, and composes the final response.

### SQLite memory and local RAG

Each save has an isolated namespace. Durable memories store a type, normalized content, tags,
entities, importance, optional story time, and access metadata. A content fingerprint prevents
duplicate writes. Retrieval combines SQLite FTS5 when available with token overlap, Chinese
bigrams, recency, and importance, then formats only the top bounded results for the model context.

Memories retain an auditable lifecycle state. Conflicted and superseded facts stay in SQLite for
review and recovery, but only active facts are eligible for RAG context injection. A corrected fact
links back to the memory it supersedes so revisions remain traceable across export and import.

Memory extraction is deterministic and local: it recognizes durable facts from the completed turn
without making another provider request. This keeps cost and latency predictable, and the feature
can be disabled independently from retrieval.

### Text provider

The provider performs two logically separate jobs:

1. Narrative continuation from the full conversation.
2. Visual prompt planning from only the latest action and narrated result. The planner emits
   separate identity, wardrobe, action, camera, environment, lighting, style, and negative fields.

This separation prevents raw conversation history from becoming an unstructured diffusion prompt.

### Persistent generation tasks

Every accepted illustration job receives a durable task ID linked to its story save and HTTP
request ID. The database records queued, running, succeeded, failed, or cancelled state together
with timestamps, duration, output filename, and a bounded error summary. On restart, unfinished
tasks are marked interrupted so task history never remains falsely active.

Failed or cancelled tasks may be retried from locally retained visual prompts. Retry lineage and
the ComfyUI prompt ID are stored for diagnosis. Task APIs intentionally omit positive and negative
prompts because they can contain private story details. Cancellation is cooperative: the database
state changes first, then the active poll requests ComfyUI interruption.

### Backup and recovery

The data service uses SQLite's online backup API to create consistent whole-database snapshots.
Every snapshot passes `integrity_check`. Restore accepts only safe filenames and compatible schema
versions, serializes maintenance against in-process database work, and creates a pre-restore safety
snapshot before changing the live database.

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
2. Resolve and normalize the save ID from the header, request body, or active state.
3. Parse the latest user message for image or memory control commands.
4. Retrieve relevant save-scoped memories and inject a bounded RAG context.
5. Apply the public image policy before forced generation.
6. Add the story-system prompt and optional story profile.
7. Request the next narrative turn from the text provider.
8. Extract durable facts locally and persist them asynchronously.
9. Decide whether the turn is visually relevant.
10. Ask the provider for a structured, single-frame visual plan. The compiler deduplicates tags and
   emits stable `BREAK` sections for subject identity, action, camera, depth, lighting, and quality.
11. Queue a serialized ComfyUI job and poll its history.
12. Convert the returned image to WebP.
13. Append Markdown to the same assistant response.

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
- SQLite uses WAL mode, foreign keys, parameterized queries, and save-scoped retrieval.
- Memory context has a strict character budget so long-running saves do not exhaust the model
  context window.

## Extension points

- Replace the keyword visual heuristic with a classifier.
- Add authenticated user ownership on top of save isolation for multi-user deployments.
- Add WebSocket progress events for long image jobs.
- Add opt-in style/identity adapters with license-aware model manifests.
- Add OpenTelemetry spans and Prometheus metrics.
- Split generation into a worker queue for multiple GPUs.
