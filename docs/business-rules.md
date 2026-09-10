# Calculation invariants

Normalize each source row before grouping. Group by trimmed SKU only, never barcode. Preserve source identifiers where color/size is unavailable. Retain signed quantities. Unknown discount defaults to editable 0%; reverse from substantiated gross/net when available. Do not use rounded MG as GP. Display and export percentages to 2 decimal places (HALF_UP per compound component). Preserve internal source precision. Export history/header report the net difference caused by rounding after SKU aggregation. Manual financial edits recalculate effective gross/net while source_reference and raw data preserve original evidence; audit before/after includes derived totals. Shop source totals stay original; calculated totals reflect edits.

Price × Qty, source cost, gross sale and settlement are distinct values. Big C: cost L × K, settlement T, ex-VAT sales P. KING POWER: unit cost E, cost amount I. Outcast: cost H and K. PDF: returned cost amount/quantity. Outlet has no actual cost; default-zero settlement is not evidence of cost.

VAT settings normalize cost comparisons only; source/export prices are retained. Keep the exact Sample worksheet columns Items, Price, Qty, Discount. Weighted SKU aggregation must reconstruct the source gross/net to cents.

Existing source audit: 5 sources, 3,896 detail rows, 4,795 signed units, 49 branch groups, 1,008 exported SKU, gross 1,192,677 and calculated net 901,536.74 (includes Outlet default-zero discount). These numbers verify this sample set, not the meaning of future reports. See review-backlog.md for unresolved header/sheet/mapping/net-source gaps.

Custom profile import now requires expected header text for every mapped column, captured via preview and saved with the profile version. Duplicate column assignments are rejected. Old profiles without header evidence require preview/resave; stored sales remain unchanged. Profile net_source defaults to mapped net, never implicitly to cost. Explicit cost-as-settlement requires available cost; none mode ignores a net column. Unknown discount with no net remains editable 0%.

Automatic workbooks with multiple recognized detail sheets require explicit selection. Selected sheets are all parsed; unsupported/skipped sheets are reported. A custom profile can be applied to explicitly selected sheets only when every selected sheet passes its header check. Summary and detail sheet duplication is a user review decision; the parser cannot infer all business duplicates.

Master mappings may replace empty or fallback partner references, with provenance/audit and preview. They preserve actual source SKUs and changed manual SKUs. Saving an unchanged fallback value alongside a discount edit does not promote it to a manual SKU. Grouping remains SKU-only.
