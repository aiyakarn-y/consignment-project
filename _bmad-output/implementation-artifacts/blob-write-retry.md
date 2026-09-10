# Recover temporary Blob PUT failures

PATH: B. MODEL ROUTE: codex-only.

Production export failed with upstream metadata PUT 503. Previous adapter made
one write attempt and treated even an ambiguous successful commit as failure.

Red proof: five new fault-injection cases failed before implementation; permanent
403 rejection passed. Added a further lost-write-response plus failed-verification
read case to cover a later conditional-write conflict after successful commit.

PUT retries at most three times for 429/500/502/503/504 and transport failures,
with 0.5/1 second delays. Read back exact bytes after ambiguous outcomes. Preserve
the original path, content and expected ETag on every retry. Never replace the
ETag with a newer version, blindly retry application operations or disable CAS.
If a retry conflicts, accept only an exact byte match to the intended write.
Authentication failures and ordinary conflicts are not retried.

Focused Blob/JSON suite: 22 passed. Includes failures before/after commit,
verification read failure, timeout, competing writer, persistent outage, 403,
import/export, history clear and file/batch removal. Persistent outages remain
errors after bounded attempts; this does not eliminate provider outages.

Live Blob run passed sequential writes, stale-write rejection, import, export,
clear history, backup, file deletion and clear batches using an isolated test
namespace. Test objects cleaned afterward. No production data changed or deploy
performed. The live run did not inject a provider outage; fault recovery was
verified using deterministic transport tests.
