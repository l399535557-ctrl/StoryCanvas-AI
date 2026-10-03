# Changelog

All notable public changes are recorded here. Local-only character data, credentials, generated
media, model weights, and adult-oriented prompt rules are intentionally excluded.

## 0.6.0 - 2026-10-03

### Added

- Request ID middleware with safe client ID validation and generated fallback IDs.
- `X-Request-ID` on every HTTP response and the same ID in structured error responses.
- Privacy-conscious JSON access logs containing method, path, status, duration, and request ID,
  without credentials, request bodies, story text, or memory content.
- Optional `LOG_LEVEL` and `LOG_FILE` configuration for persistent operational logs.

### Changed

- HTTP and validation errors now include a traceable request ID.
- The FastAPI application metadata now reports version 0.6.0.

### Verification

- Added request ID echo, rejection/fallback, and error-correlation coverage. The full suite now
  contains 21 passing tests.

## 0.5.0 - 2026-10-03

### Added

- Explicit `active`, `conflicted`, and `superseded` lifecycle states for durable memories.
- Authenticated endpoints to quarantine a conflicting memory, reactivate it, or atomically replace
  it with a corrected fact.
- Revision lineage through `supersedes_memory_id`, preserved across JSON export and import.
- Automatic schema migration from earlier databases to SQLite schema version 3.

### Changed

- RAG retrieval now uses only active memories; conflicted and superseded facts remain visible for
  audit and recovery but are not injected into model context.
- Memory list and detail responses expose lifecycle and revision-lineage fields.

### Verification

- Added migration, retrieval exclusion, atomic supersession, lineage import, and API lifecycle
  coverage. The full suite now contains 20 passing tests.

## 0.4.0 - 2026-10-03

### Added

- Versioned JSON export for a complete story save, including turns and durable memories.
- Atomic story-save import with turn-to-memory source relationship remapping.
- Save duplication for safe branching and alternate story development.
- Optional inclusion of archived memories in backup exports.
- API and storage regression coverage for export, import, copy, relationship preservation, RAG
  availability after import, and collision protection.

### Safety and data integrity

- Imports never overwrite an existing save ID and return a conflict instead.
- Import validation limits bundles to 10,000 turns and 20,000 memories.
- A failed import is rolled back as one SQLite transaction, so partial saves are not retained.
- Copies include active story data while leaving archived memories behind by default.

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
