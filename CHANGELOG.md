# Changelog

All notable public changes are recorded here. Local-only character data, credentials, generated
media, model weights, and adult-oriented prompt rules are intentionally excluded.

## 0.3.0 - 2026-10-03

### Added

- Authenticated create, rename, archive, and restore operations for story saves.
- Paginated turn-history queries scoped to one story save.
- Partial update, archive, and restore operations for durable memories.
- Recoverable soft deletion so routine data management does not destroy story data.
- Automatic migration of version 1 SQLite databases to schema version 2.
- Validation and regression coverage for data isolation, pagination, editing, archive/restore,
  archived-memory retrieval exclusion, and legacy database migration.

### Changed

- Save and memory list endpoints support pagination or archived-record visibility where applicable.
- Archived memories are excluded from RAG retrieval and normal counts.
- Archived saves cannot be edited, and the active save cannot be archived accidentally.

### Documentation

- Defined the graduation-project direction around system completeness rather than extensive
  research novelty.
- Added a current completion inventory, engineering-size summary, remaining-system gap analysis,
  phased implementation order, and concrete acceptance criteria.
- Updated the project introduction so the next phase prioritizes the web UI, data management,
  task lifecycle, recovery, export, deployment, and end-to-end verification.

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
