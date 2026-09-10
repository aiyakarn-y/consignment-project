# Storage modes

The server selects storage at startup. Restart to change mode; there is no
browser switch that could move every connected user to another dataset.

| Mode | Start / stop | URL | Metadata | Files |
| --- | --- | --- | --- | --- |
| Original Local | `npm start` / `npm run stop` | 127.0.0.1:3117 | SQLite, `data/local/database/` | `data/local/` |
| SQLite Beta | `npm run beta:start` / `npm run beta:stop` | 127.0.0.1:3119 | SQLite, `data/beta-test/database/` | `data/beta-test/` |
| JSON Beta | `npm run json:start` / `npm run json:stop` | 127.0.0.1:3120 | `data/json-beta/state/system.json` | `data/json-beta/` |
| Blob Beta on this machine | `npm run blob:start` / `npm run blob:stop` | 127.0.0.1:3121 | Private Blob: `<namespace>/state/system.json` | Private Blob, same namespace |

Each Beta mode has a matching `*:status` command. Backend ports are 8102, 8103
and 8104 respectively. First run `npm run beta:setup` once for the shared Beta
username `beta` and password, then `npm run build`. Existing `.env.beta` stays
valid for all Beta modes. No tunnel is started automatically.

To share JSON Beta, point an existing cloudflared installation to
`cloudflared tunnel --url http://localhost:3120`. The host must stay awake.
All testers share one dataset and password. This is not per-user authorization.

## Switching and transferring data

Switching modes does not copy data. Each mode reopens its own dataset, so
switching back preserves the old records. Use the existing Backup / Restore UI
to transfer a populated dataset: create and download a backup from the source,
open the destination, preview the ZIP and confirm restore. Restore replaces
destination records and creates a safety backup first. Keep the source backup.
Both old SQLite backup formats and new JSON mode use the existing version-2
portable archive; no live SQLite file is uploaded to Blob.

## Configuration

- `CONSIGN_STATE_DRIVER=sqlite|json`
- `CONSIGN_STORAGE_DRIVER=local|vercel_blob`
- `CONSIGN_DATA_DIR`: local state/files for local mode; local logs only for the
  Blob runner. `/tmp` in Vercel is scratch space, not persistence.
- `CONSIGN_BLOB_PREFIX`: required environment namespace, letters/numbers/`_`/`-`.
- `BLOB_READ_WRITE_TOKEN`: server secret for a Private Blob store.

For Blob testing, manually create ignored `.env.blob` with the last two values.
Use a distinct namespace such as `consignment-dev`; never share it with
Production or Preview. Protect that file with `chmod 600 .env.blob`.
No provider account, store, trial, subscription or deployment is created by
these commands. Cloud calls may incur provider usage charges.

## JSON design and limits

One metadata snapshot contains tables as JSON objects, with money retained as
decimal strings. A successful request publishes the complete snapshot once,
so rows, mappings and history change together. Local JSON uses a filesystem
lock plus atomic rename; Blob uses a private uncached read and ETag conditional
write. Concurrent requests based on an older snapshot return HTTP 409 instead
of overwriting newer data. The UI asks the user to reload/retry; it does not
silently replay financial edits.

This guards concurrent server writes, not stale forms that are submitted after
another request has already completed. Per-row client revisions remain future
work; coordinate edits during Beta. JSON loads the metadata snapshot in memory
and has a 64 MiB maximum persisted snapshot. SQLite keeps SQL history paging;
JSON pages the loaded snapshot. This is a small-dataset Beta design, not a
replacement for a database at large scale.

Uploaded/exported files have unique immutable keys. Logical deletion commits
before removing files; a durable cleanup queue allows retry after failed
deletion. A failed or interrupted write may leave an unreferenced object. Do
not sweep unreferenced objects during active traffic: another request may be
about to reference them. Retention/garbage collection needs a maintenance
window and is not automatic in this version. Cancelled browser uploads can
also leave staging objects; completed staged requests remove their staging file.

## Vercel preparation (not a deployment result)

`vercel.json` defines Next.js and FastAPI Services with `/api/*` routed to the
backend and other paths to the frontend. Select Services in project settings;
keep repository root as the project root. Both services need the same Blob
namespace and token plus `CONSIGN_BETA_MODE=1`, `CONSIGN_BETA_USER=beta`, and a
strong `CONSIGN_BETA_PASSWORD`. Set `CONSIGN_STATE_DRIVER=json` and
`CONSIGN_STORAGE_DRIVER=vercel_blob`; clear local data/template overrides.
Use a separate namespace for every shared deployment environment.

Multipart payloads over 2 MiB are staged directly from the browser to Private
Blob using a short-lived token scoped to one random staging key. The backend
rehydrates the request for the existing parsers. Source/export/backup downloads
use short-lived signed GET URLs; server storage tokens never reach the browser.
The backend uses the API v12 contract verified against @vercel/blob 2.8.0;
Python SDK 0.0.8 lacks conditional-write and uncached-read options, so the small
HTTP adapter is explicit and tested with mocked transport.

Before deploy, verify the actual Private Blob service with development
credentials, including ETags, create-only collisions, large upload/download,
signed URL CORS, restart persistence and concurrent requests. Then run a Vercel
Preview and test the same flows. Local and mocked tests do not prove cloud
connectivity, plan eligibility, billing, runtime bundling or production capacity.

References: https://vercel.com/docs/vercel-blob,
https://vercel.com/docs/vercel-blob/using-blob-sdk,
https://vercel.com/docs/services.
