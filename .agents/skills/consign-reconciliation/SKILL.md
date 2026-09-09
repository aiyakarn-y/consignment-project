---
name: consign-reconciliation
description: Verify ConsignmentSystem sales arithmetic after parser, discount, grouping or Excel export changes.
---

Read ../../../docs/business-rules.md and identify the affected source columns. Run relevant domain/parser tests with isolated data. If the five local sample files are present, run `npm run audit` from the repository root and inspect the report under `_wrx-output/evidence/price-cost-audit`. Compare source control totals as well as normalized rows; a matching grand total alone cannot catch swapped price/quantity. Read the generated Excel back and verify SKU quantities and cent-level gross/net. Preserve precision and explain unknown VAT/cost semantics. Report source/row, expected/actual and exact failed check; do not claim real-file verification if samples are missing.
