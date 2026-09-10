# Beta runner

PATH B / codex-only. Fix missing beta:start and implement the previously proposed isolated, authenticated local beta. No tunnel/public deployment.

Red proof: npm run beta:start returned Missing script on 2026-09-10 before implementation.

Implementation: beta:setup writes ignored .env.beta with mode 0600 using a hidden password prompt; beta:start uses data/beta-test, loopback ports 3119/8102. beta:stop/status target the beta data directory. Next Proxy protects all requests and FastAPI independently checks Basic credentials. Startup health probe authenticates. Local mode retains existing behavior. Shared beta login is not per-user authorization; testers share the dataset. HTTPS tunnel required for remote access.

Validation: focused runner/auth tests, production build and runtime checks recorded under _wrx-output/evidence/beta-runner. No real data or public tunnel used.

Runtime verification passed: isolated localhost 3129/8122, frontend / and API and direct backend /docs reject unauthenticated requests (401); authenticated page and health requests succeed (200). Supervisor stopped after smoke. Build passed with pre-existing page.tsx named JSON export warning. Focused tests: 6 passed. Initial smoke failed due sandbox bind restrictions; rerun with approved localhost access passed.
