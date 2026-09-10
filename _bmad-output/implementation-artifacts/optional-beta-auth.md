# Optional Beta login on Vercel

PATH: B — shared frontend/backend authentication behavior.
MODEL ROUTE: codex-only.

User requested temporarily removing Beta login after deployment reported missing credentials.
Explicit CONSIGN_BETA_MODE=0 disables Basic authentication on both services, while unset
or invalid values on Vercel retain authentication. Mode 1 enables it again.
Cloud download ticket verification and storage token requirements remain in force.
Vercel API responses retain no-store even with login disabled.

Red proof: test_vercel_auth_can_be_explicitly_disabled[0-200] failed before implementation
with actual 503 versus expected 200; other five Beta tests passed.
Verification: focused backend tests, frontend cloud/auth handler tests, and TypeScript.
No deployment performed; user sets the environment variable and redeploys.
