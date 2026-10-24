# Work order WS1 — B2 rate index, RateFactors / TreatyFeed, B1 level 1, T ingest + V5

Branch: `ws1-rate-index` · Read: SPEC §0–§7 (all), §8.3, §12 (note under the table), §13 · Depends on: WS0 merged

## Goal
Answer "what is the standardised rate change of each option vs expiring, overall and by cut" (B2) and "is each option
richer or leaner than expiring" at level 1 (B1), and finish the submission ingest path (T ingest, V5).

## Deliverables
1. `pw/rate_index.py` — B2:
   - price expiring and each SUBMISSION/PROPOSED option on the same exposure cells (`pw.evaluator.evaluate`, default options);
   - standard mix = latest UWY, annualised in-force lives (SPEC §5); sensitivities on `written_ly` and the UWY-1 mix;
   - `RateFactors` (option × cell key: `option_id, cell_key…, rate_expiring, rate_option, factor, priced_status`);
   - `RateIndex` by any cut of the cell key (`lives, prem_expiring, prem_option, index, index_benefit_adj`);
   - REFER / UNMATCHED cells excluded from the index and reported with their share.
2. `TreatyFeed` (option × treaty book: `premium_change_pct, lr_adjustment_pts, basis_note`) per SPEC §7 formula;
   target treatymodel version in `contracts/treatymodel_version.txt`. `OptionTerms` from the submission Terms sheet.
3. `pw/benefit_value.py` — B1 level 1 (SPEC §4.3): relativities from the catalogue's own factor tables, then
   `registry/benefit_factors.json`, then owner overrides; `BenefitDiff` and `BenefitFactors`; richness index per plan.
   Design (not build) B1 level 2 in `docs/B1_level2_design.md`.
4. T ingest: `t ingest <submission.xlsx>` = parse (WS0) + **V5** complete (structure hash = issued; mandatory cells
   numeric > 0; outliers vs expiring by ratio bands from run config) + multiplier proposals when the template allowed
   them + registration of the option in the run folder.
5. Outputs as Parquet + Excel view + run manifest (versions, hashes) in `runs/<RunID>/`.
6. CLI commands `index`, `benefit`, `t ingest`; their end-to-end checks added to `tools/laptop_check.py`.

## Decisions carried in
- TPA factor basis (HANDOVER open item 4): provisional option A — submitted per-TPA block values are pre-TPA-factor;
  the issued TPA factor applies. Keep the basis in one place (parser `to_catalogue`) so a switch to B is a one-line
  change plus the CR; add a test that pins the current behaviour.

## Files
- May create: `pw/rate_index.py`, `pw/benefit_value.py`, `pw/outputs.py`, `pw/template/ingest.py`, tests `tests/test_ws1_*.py`, docs.
- May edit: `pw/gates.py` (V5 only), `tools/pw.py` (new commands), `tools/laptop_check.py` (new checks), `registry/benefit_factors.json` (entries).
- Must not edit (frozen, CR only): `registry/dimensions.json`, `contracts/*`, `pw/model.py` dataclass fields, the `_KEYS`/`_META` layout.

## Fixtures
CAT_ALPHA (expiring), SUB_X, SUB_Y, EXPO_SYN; CAT_BETA for the block-set case. Add any new synthetic fixture under `fixtures/` via `tools/build_fixtures.py`.

## Acceptance criteria
- Index on SUB_X / SUB_Y vs CAT_ALPHA hand-checked on a small cut (≤ 5 cells, worked in the test).
- Because co-pay multipliers are flat and issued, the cell-level factor is independent of co-pay options (SPEC §12 note): test it.
- Benefit-adjusted index = index ÷ benefit ratio, tested; TreatyFeed formula tested.
- V5 flags a tampered hash, a blank mandatory cell, a zero, a text value and an outlier.
- Round trip (V4) still green; full suite green; `LAPTOP CHECK PASS` on the owner's laptop (SPEC §13).

## Out of scope
Market benchmark (WS2), scorecard (WS3), Power BI (WS6), B1 level 2 build.
