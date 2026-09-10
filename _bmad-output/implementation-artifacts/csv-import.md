# CSV sales import

PATH: B. MODEL ROUTE: codex-only.

Add literal CSV cells to the shared mapping pipeline, preserving SKU strings,
Decimal calculations, profile header checks and original source bytes. Require
an explicit mapping profile for CSV rather than guessing financial columns.
Support UTF-8/BOM, UTF-16 BOM and CP874, comma/semicolon/tab, quoted multiline
fields; reject binary/empty/malformed or excessive input. Bound to 25 MB,
50,000 rows, 200 columns, one million cells and Excel's cell text size.

Update inspect/preview/preflight/import, source key validation, backup/restore,
private download allowlist and frontend file pickers. Export remains XLSX.

Verification covers encoding/delimiters, leading-zero SKU, literal formula-like
text, malformed inputs, duplicate rejection, SQLite/JSON import-export-restore,
and browser profile creation/import/download. No production records changed.

Results: 172 Python tests passed; TypeScript passed; browser CSV workflow passed
with production E2E build. Live private Blob CSV import/export, XLSX readback,
backup/restore byte equality, clear history, file deletion and batch clearing
passed in an isolated namespace; test objects cleaned afterward.
