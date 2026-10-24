# Work order WS3 — D: scorecard

Branch: `ws3-scorecard` · Read: SPEC §0, §1, §4.4, §7, §13 · Depends on: WS1 outputs (`RateIndex`, `BenefitFactors`, `OptionTerms`)

## Goal
Recommend an option (or a panel) from price, benefits, terms and conditions, with transparent weights.

## Deliverables
1. `ScoreInputs` (option × criterion: `metric, value, source`) assembled from WS1 outputs and the terms comparison
   (rules are non-pricing terms, SPEC §4.4).
2. Scoring: normalisation per criterion, owner-set weights (run config JSON), weighted score, ranking, panel options
   (shares by book from `OptionTerms`).
3. Sensitivity of the ranking to the weights (one-at-a-time and a grid); recommendation pack inputs (Excel via xlsxwriter).
4. CLI `score`; end-to-end check added to `tools/laptop_check.py`.

## Files
- May create: `pw/scorecard.py`, tests `tests/test_ws3_*.py`, `examples/scorecard_weights.json` (fictional).
- May edit: `tools/pw.py`, `tools/laptop_check.py`.
- Must not edit: contracts, registries, model, evaluator, WS1 output schemas (CR only).

## Fixtures
SUB_X, SUB_Y and their WS1 outputs; add a third synthetic option if a tie case is needed.

## Acceptance criteria
- Weighted scores hand-checked; weights that do not sum to 1 are rejected (no silent renormalisation).
- Sensitivity shows the weight at which the ranking flips, tested on a constructed case.
- No incumbent name in market-facing outputs. Full suite green; `LAPTOP CHECK PASS` (SPEC §13).

## Out of scope
Choosing weights (owner input); Power BI.
