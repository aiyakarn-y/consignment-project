---
name: consign-code-review
description: Review a ConsignmentSystem change for regressions, maintenance risks and missing test coverage.
---

Read the requested diff and ../../../docs/review-backlog.md to distinguish pre-existing issues from new regressions. Trace changed paths through API, storage, parser and UI. Reproduce suspected bugs in temporary data where possible. Check that clear/restore and import retries cannot lose referenced files, and that money/GP/MG assumptions remain explicit. Rank findings by user impact with file references and evidence, label unverified suspicions, and state checks actually run. Reviewing does not itself authorize implementation or deployment.
