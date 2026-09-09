# ConsignmentSystem workspace and storage implementation
PATH C / codex-only. User approved single Git root, local runnable system, preserved original demo, independent copy of existing data, separated imports/exports/db/backups, .env/Docker, and product rename. Cloud deployment and the broader review backlog are outside this increment.

Acceptance: migrate all live records and referenced bytes without changing sales values/IDs; legacy ZIP compatibility; clear import files after database commit with durable cleanup retry, preserve export history; atomic writes; source and export downloads; startup from any cwd, restart persistence; synthetic API/UI tests isolated from local data; real five-source reconciliation; no data/secrets in Git or image context.

Progress and evidence are recorded under _wrx-output/evidence. Missing Docker engine must be surfaced, not treated as a successful container execution. No Azure/GCP external mutation is authorized in this increment.

## Completed 2026-09-10
- Renamed the empty workspace to remove its trailing space; source code is directly under Consignment-System with frontend/backend siblings. Product name is ConsignmentSystem.
- Copied the stopped original DB: 0 batches, 0 sales rows, 3 import-registry entries. Business records still match exactly after read-only live smoke. Created a legacy-format migration ZIP and copied the five supplied samples to ignored local data. Original project remains untouched apart from stopping its services.
- New local storage adapter publishes files atomically, stores imports by batch and exports by ID, and cleans files via a durable retry queue after DB deletion. Added cleanup API, source-availability history, ZIP v2 writing/v1+v2 reading and guarded migration.
- Local Start/Stop supervisor, runtime API gateway, standalone build preparation, .env setup, two Dockerfiles/Compose, Git exclusions, AGENTS.md and three validated skills are ready.
- Python regression: 72 passed; TypeScript and production builds passed; final standalone Playwright: 2 workflows passed (36.5s). Real-source audit: 3,896 rows / 1,008 SKU, all source controls and reconstructed Excel amounts passed. Populated synthetic migration, legacy restore, write failure, cleanup retry and restart persistence passed.
- Native local smoke from another cwd passed start/stop/restart/source+export redownload. Read-only live desktop/mobile smoke passed; local user data preserved.
- Docker Compose YAML, services, mounts and referenced Dockerfiles checked statically. Docker engine/CLI are absent, so image build/container recreation are NOT verified. No Azure remote/push or GCP deployment performed.
- Evidence: _wrx-output/evidence/{storage-red-proof.txt,regression-final.txt,migration.json,native-local-smoke.json,workspace-live-smoke.json,playwright-results.json,git-data-exclusion.json}.
- Original broader review backlog remains documented; this increment does not claim to resolve all calculation/import-format gaps.
