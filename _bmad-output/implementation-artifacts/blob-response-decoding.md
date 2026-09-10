# Blob response decoding fix

PATH: B. MODEL ROUTE: codex-only.

Production traceback: Blob GET returned 200, but reconstructed httpx.Response
attempted gzip decoding on bytes already decoded by streamed.iter_bytes().
This is a code defect, separate from earlier environment configuration errors.

Red proof: gzip and deflate streamed response regression cases both failed
before the fix with httpx.DecodingError; identity passed.

Fix: remove Content-Encoding, Content-Length and Transfer-Encoding when
reconstructing the decoded response. Preserve ETag and other headers. Keep the
size limit on decoded bytes, including compressed responses.

Validation scope: Blob adapter and JSON repository tests; no production writes
or deployment. User redeploys main to verify live requests.
