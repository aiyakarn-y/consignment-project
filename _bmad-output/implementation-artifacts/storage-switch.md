# Switchable storage — Path C / codex-only

Scope: preserve Local SQLite and Beta access; add Local JSON and Private Blob
JSON modes with isolated data and startup commands. User requested develop
branch and merge to main after passing tests. No cloud subscription authorized.

Plan:
1. Replace application SQL calls with key/value repositories; retain SQLite
   adapter and legacy backup compatibility.
2. Add request-level JSON snapshot transaction with atomic local publish and
   Blob ETag conditional writes. Defer asset deletion until committed.
3. Introduce portable file-store operations; stage large uploads directly to
   Blob and sign large downloads. Require Beta auth for both public services.
4. Add isolated mode commands, UI mode label and setup/deployment documentation.
5. Verify SQLite regressions, JSON restart/restore/CAS/failure cases, mocked
   Blob contracts, source arithmetic, production build and browser flows.
6. Commit and push develop; merge/push main. Real Blob/Preview validation awaits
   credentials and user plan selection; do not imply local tests prove deploy.

Design decision: one JSON metadata snapshot (maximum 64 MiB) instead of a
separate object per table, preserving atomic multi-table operations without a
distributed transaction coordinator. Immutable original/export/backup files
remain separate. No SQLite engine is used for JSON mode.

Evidence directory: `_wrx-output/evidence/storage-switch/`.
Existing data and running user tunnels are not migrated or restarted.

Final user steering: push/merge Git only; user will deploy themselves. Do not
create a Vercel project/store or deploy. Added docs/vercel-deploy.md in Thai.

Verified: SQLite and JSON browser suites each passed all four workflows,
including real input reports, financial edits, exact Excel download,
profile/sheet safeguards, history paging and backup/restore. Cloud handler
security test passed (unauthenticated, invalid/expired/cross-namespace tickets).
Authenticated JSON supervisor smoke passed on temporary localhost ports.
Source audit: gross 1192677, internal net 901536.74, 4795 units; exported net
rounding delta remains +1.41. Build and final typecheck passed. One intermediate
typecheck overlapped E2E's generated files and failed TS6053; sequential rerun
passed. Private Blob config is absent; only mocked Blob protocol tests ran.
