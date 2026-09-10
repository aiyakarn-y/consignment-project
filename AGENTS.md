# ConsignmentSystem engineering instructions

Follow the user's current scope. Wrixon profile is codex-only unless explicitly changed. Before implementation/review state PATH A/B/C, concrete reason/evidence and model route. Use B for nuanced multi-file behavior and C for architecture/migration. For B/C bug fixes reproduce the failure before changing behavior. Record plans in `_bmad-output/implementation-artifacts` and runtime evidence in `_wrx-output`.

## Repository
- Next.js is in `frontend/`; read its local AGENTS.md and installed version's relevant docs before framework changes.
- FastAPI and Decimal business rules are in `backend/`.
- `backend/config.py` anchors .env paths to this Git root. `backend/storage.py` owns filesystem access.
- `data/` and `.env` are local only; never stage them or copy them into images. Samples/real audit output contain business data.
- Use workspace-local `.venv` and frontend dependencies. No dependencies on the old demo location.

## Commands
- `npm run setup`, `npm run build`, `npm start`, `npm run stop`, `npm run status`.
- `npm test` runs isolated Python tests. `npm run typecheck` verifies the frontend.
- `npm run test:e2e` uses isolated data and ports 8101/3118.
- `npm run audit` verifies the five provided local source files when present.
- See README for Docker and first-run setup. Missing Docker is a test limitation, not a passing container test.

## Non-obvious invariants
- Merge by SKU only; money uses Decimal, not JS Number. Preserve signed quantities, exact output columns, source evidence, and full internal discount precision. Export each discount component as two-decimal text (HALF_UP); disclose the resulting net rounding delta.
- Keep GP/MG and source cost/settlement distinct. See `docs/business-rules.md`.
- Do not use live data for clear/restore/edit tests. Migrations copy, validate, and preserve the old workspace.
- Commit database deletions before cleanup; never resurrect records referencing deleted files. Retry cleanup idempotently.
- Keep legacy backup reading and endpoint compatibility when reorganizing storage.
- The seven review findings in `docs/review-backlog.md` are not all resolved by this workspace migration. Do not claim they are.

## Completion
Run checks affected by the change and inspect failures. Report what passed, what could not be run, and material risks. Keep formatting-only work separate from formula changes. Do not deploy, publish, or create external resources outside the user's authorized task.
