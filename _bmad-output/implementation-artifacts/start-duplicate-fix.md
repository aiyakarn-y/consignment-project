# Local duplicate-start fix
PATH B / codex-only. Reported port-in-use traceback when starting the already-running new workspace. Confirmed that ports 8100/3117 belonged to ConsignmentSystem v0.2.0, not the old demo. User requested shutdown; local services were stopped and must remain stopped after testing.

Root cause: socket probe ran before checking the supervisor record. Change: identify a live owning supervisor first and return its recorded URL successfully; preserve the existing process and runtime record. Probe unrelated port occupancy with bind/listen and report service/port through a clean nonzero CLI error. Stale records cannot be treated as running. Include host in new records; retain compatibility with existing records without host.

Red proof: _wrx-output/evidence/start-duplicate-red.txt (4 failures). Focused tests: start-duplicate-green.txt (4 passed). Native lifecycle smoke runs only on isolated data/ports and also checks repeat start, unrelated occupied socket, stop and restart persistence. No production data edits or frontend/calculation changes.
