# Changelog

All notable public changes are recorded here. Local-only character data, credentials, generated
media, model weights, and adult-oriented prompt rules are intentionally excluded.

## 0.8.0 - 2026-10-03

### Added

- Consistent whole-database SQLite snapshots using the native online backup API.
- Backup listing, integrity verification, schema compatibility checks, and authenticated backup
  creation and restore endpoints.
- Automatic pre-restore safety backup so an operator can reverse an accidental restore.
- Configurable `MEMORY_BACKUP_DIR`, excluded from public Git history by default.

### Reliability

- Database operations share a maintenance lock so backup and restore cannot interleave with normal
  writes inside the process.
- Restores reject malformed filenames, missing files, corrupt databases, and unsupported newer
  schema versions.

### Verification

- Added storage and HTTP coverage for snapshot creation, mutation, restore, safety backup, and
  restored data visibility. The full suite now contains 25 passing tests.

## 0.7.0 - 2026-10-03

### Added

- Persistent image-generation task records linked to story saves and request IDs.
- Task lifecycle fields for queued, running, succeeded, failed, and cancelled states, including
  output filename, safe error summary, timestamps, and measured generation duration.
- Authenticated task-history and task-detail endpoints with save, status, and pagination filters.
- Startup recovery that marks unfinished tasks as failed after a service restart instead of
  leaving them permanently in a running state.
- Task totals and failed-task counts in health and memory statistics.

### Changed

- Visual planning and ComfyUI generation now update one durable task record across success and
  failure paths.
- SQLite schema version increased to 4.

### Verification

- Added lifecycle, restart-recovery, filtering, statistics, and task API tests. The full suite now
  contains 23 passing tests.

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
