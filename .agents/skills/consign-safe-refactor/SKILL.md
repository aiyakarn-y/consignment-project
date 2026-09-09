---
name: consign-safe-refactor
description: Reorganize ConsignmentSystem modules while preserving API, calculation and persisted-data behavior.
---

Identify the exact approved refactor boundary and capture relevant tests before moving code. Separate formatting from behavior changes. Keep Decimal math and source/export compatibility; use backend/config.py for anchored paths and the file store for storage keys. Update callers and test fixtures when paths move. For data-layout changes, test a populated legacy migration, checksums, restart and backup restore using temporary data; never migrate by overwriting the only original. Run the affected tests and UI flow, then explain remaining compatibility limits.
