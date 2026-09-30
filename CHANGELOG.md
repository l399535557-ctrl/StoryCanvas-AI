# Changelog

All notable public changes are recorded here. Local-only character data, credentials, generated
media, model weights, and adult-oriented prompt rules are intentionally excluded.

## 0.2.0 - 2026-09-30

### Added

- Save-isolated SQLite storage for story turns and durable memories.
- Tagged memory records with entities, importance, story time, access metadata, and fingerprint
  deduplication.
- Local hybrid RAG using FTS5, token overlap, Chinese bigrams, recency, and importance scoring.
- Deterministic local memory extraction and bounded context injection.
- Memory commands and authenticated save/memory management endpoints.
- Request-level save selection through body fields and `X-Story-Save-ID`.
- Unit coverage for save isolation, retrieval, extraction, injection, and management APIs.

### Changed

- Streaming responses now emit role, bounded content chunks, stop reason, and `[DONE]` as separate
  SSE events.
- Health output includes non-secret memory status and counts.
- Public documentation now describes local data retention and memory configuration.

### Public-sync boundary

- No credentials, chat histories, private character profiles, generated images, model weights, or
  adult-oriented prompt vocabulary were copied into this release.
