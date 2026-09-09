# Calculation invariants

Normalize each source row before grouping. Group by trimmed SKU only, never barcode. Preserve source identifiers where color/size is unavailable. Retain signed quantities. Unknown discount defaults to editable 0%; reverse from substantiated gross/net when available. Do not use rounded MG as GP. Display percentages to 2 decimal places without rounding stored/export calculation precision.

Price × Qty, source cost, gross sale and settlement are distinct values. Big C: cost L × K, settlement T, ex-VAT sales P. KING POWER: unit cost E, cost amount I. Outcast: cost H and K. PDF: returned cost amount/quantity. Outlet has no actual cost; default-zero settlement is not evidence of cost.

VAT settings normalize cost comparisons only; source/export prices are retained. Keep the exact Sample worksheet columns Items, Price, Qty, Discount. Weighted SKU aggregation must reconstruct the source gross/net to cents.

Existing source audit: 5 sources, 3,896 detail rows, 4,795 signed units, 49 branch groups, 1,008 exported SKU, gross 1,192,677 and calculated net 901,536.74 (includes Outlet default-zero discount). These numbers verify this sample set, not the meaning of future reports. See review-backlog.md for unresolved header/sheet/mapping/net-source gaps.
