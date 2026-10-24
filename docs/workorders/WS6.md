# Work order WS6 — Merit Annex as-if page (ete-dashboard repo)

Repo: `mtamsyed-gc/ete-dashboard` · Branch there: `ws6-asif` · Read here: SPEC §5.1, §7 (`RateFactors`), §13
Depends on: WS0 `RateFactors` schema (SPEC §7), WS1 producing `RateFactors` on fixtures

## Goal
An option slicer and an as-if page in the Merit Annex Power BI model that re-rates experience with `RateFactors`
so that the dashboard's as-if numbers equal the workbench's.

## Deliverables
1. Import of `RateFactors` (Parquet) keyed on the canonical cell key; join to Merit `dim_life` via the same mapping
   tables the workbench uses (no re-implementation of mapping logic in DAX beyond the join).
2. Option slicer; as-if premium and LR measures; reconciliation page vs the workbench `RateIndex`.
3. Laptop check for the PBIP/Power BI side (refresh on fixtures, as-if totals compared with a workbench export),
   documented in the ete-dashboard repo and referenced from `tools/laptop_check.py` here.

## Files
- Edit only the ete-dashboard repo (Merit Annex model and its docs). Do not change Merit, its output contract, or
  this repo's contracts; contract needs go to docs/CHANGE_REQUESTS.md here.

## Acceptance criteria
- As-if equals workbench numbers on fixtures (cell level and by cut, tolerance 0.01 AED).
- Synthetic data only. Owner's laptop refresh succeeds and the reconciliation page shows zero differences
  (`LAPTOP CHECK PASS`, SPEC §13).
