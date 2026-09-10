# Vercel readiness review — 2026-09-10

PATH C / codex-only. Reviewed commit 4559431. Scope: deployment readiness, no application changes or cloud deployment.

Verdict: not ready for a functional full-stack Vercel deployment unchanged.

## Confirmed code blockers

- backend/config.py:20–28 supports only local storage and a filesystem SQLite database. backend/app.py:22–40 initializes local directories and SQLite on startup. Changing only environment variables cannot enable remote storage.
- backend/storage.py:19–68 implements only LocalFileStore. Imports, exports and backups require durable shared storage; /tmp is not a replacement for persistence.
- frontend/app/api/[...path]/route.ts:8 defaults to localhost:8100. No vercel.json/services configuration exists. Cloud API routing/bindings and backend entrypoint/template packaging must be configured.
- backend/app.py:153 accepts 25 MiB files; operations.py:16 allows 250 MiB backups. Uploads currently pass through the Next proxy. Vercel Functions document a 4.5 MB request/response payload limit. Adapt upload/preflight/profile/master/restore paths to object references and verify large download behavior.
- frontend/package.json build runs a repository-parent standalone helper. Root package.json is a local supervisor wrapper. Configure service roots, dependency installation, cloud build and Python runtime explicitly; actual Vercel build not yet tested.

## Before inviting testers

- No application authentication: protect both UI and API access, including destructive operations.
- backend/app.py:540 uses a process-local lock; this does not coordinate multiple function instances. Use database transaction/concurrency controls when moving to shared remote storage.
- Verify import/edit/export, clear/history, backup/restore, large files, concurrent edits and persistence across new instances/redeploys in an isolated cloud dataset.

## Proposed sequence

1. Configure Next.js + FastAPI Services, environment separation and template packaging.
2. Implement a remote database repository and durable object storage while retaining local mode.
3. Adapt file transport, protect beta access and coordinate writes across instances.
4. Build/deploy preview; run end-to-end and persistence checks before sharing the URL.

Evidence: static inspection of current tracked source/configuration; clean working tree before review. No live data modified. No new build/test/cloud execution in this review. Previous local test results are not Vercel validation.

Official references checked:
- https://vercel.com/docs/services
- https://vercel.com/kb/guide/is-sqlite-supported-in-vercel
- https://vercel.com/docs/functions/limitations
