# Blob conditional writes and delivery encoding

PATH: B. MODEL ROUTE: codex-only.

Reported: repeated metadata PUT 412 blocks imports, history clearing and deletes.
Installed @vercel/blob 2.8.0 confirms x-if-match and allowOverwrite headers match
the adapter. Production logs do not include the received ETag, so the exact live
cause cannot yet be confirmed. No local Blob token was available for inspection.

Potential defect: HTTPX advertises compression by default. Delivery compression
can supply a representation-specific or weak ETag that is unsuitable for object
conditional writes. Request Accept-Encoding: identity for versioned reads;
retain cache=0 and pass the original ETag unchanged. No unconditional overwrite,
blind conflict retry, ETag stripping or replacement with a newer metadata ETag.

Red proof: a mock with compressed-delivery ETag versus stored-object ETag rejects
the second sequential write with 412 before the change. Afterward sequential
writes work while a stale transaction remains rejected. This reproduces a
plausible mechanism, not proof of the live service's exact headers.

Regression scope: plain/compressed HTTP decoding, sequential and concurrent
metadata writes, import/export, clear history, file deletion, batch deletion,
backup and JSON repository behavior. Live isolated Blob verification pending
user-provided local credentials; no production records changed.
