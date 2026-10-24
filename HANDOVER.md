# Handover — Pricing Workbench

Last updated: 2026-10-24 (owner-decisions batch on `owner-decisions-1`: HANDOVER items 1–21 decided, SPEC v0.4, CRs #2–#4, #13, #18–#21 approved, CR #12 amended, CR #17 → WS7).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests (all decided; CR #17 = work order WS7) |
| docs/workorders/WS1–WS4, WS6, WS7 | Work orders for the next streams (WS7: structured benefit proposals, CR #17) |
| tools/laptop_check.py | SPEC §13 laptop acceptance: run `py tools\laptop_check.py` on the laptop after every change |
| reference/ufic/UFIC_Medical_Reinsurance_Reference.md | TEMPORARY GC material: UFIC catalogue V10 14.1 reference (ToB, factors, rate-table structure, UW rules). Structure only — see CLAUDE.md data boundary |
| requirements-native.txt | Runtime pins (same as ete-dashboard) |

## Related repos and tools
- ete-dashboard / side_tools/merit (Merit v7.3.x): exposure and experience source. Contract `side_tools/merit/config/model_contract.json`
  (IP4-8): dim_life carries Policy Type, TPA, Region Group, Network, Plan / Category, Relation, Gender Group, Marital Status,
  AgeAtInception, NewRenewal, Distribution, WrittenLY/Prem, EarnedLY/Prem; no co-pay field. Merit itself is not changed by this repo.
- ete-dashboard / side_tools/treaty_tool (treatymodel 2.0, master in PBM): P&L by scenario; fed by `TreatyFeed` (premium change %,
  LR adjustment per treaty book) and `OptionTerms`. Do not edit it here.
- Owner's product benchmarking tool: **SME Product Benchmarking Tool v3.1**, repo `mtamsyed-gc/PBM`, branch
  `claude/keen-babbage-efpwps` (not the default branch), folder `sme_benchmarking/`. Input to WS2 and to the benefit
  taxonomy reconciliation; attach read-only. Key parts: `build/taxonomy.py` (levers, add-ons, networks CN/GN/RN/RN2/RN3/VN,
  reference factor basis - SYNTHETIC placeholder, DHA minimums), intake template `SME-INTAKE v2.4` (one Excel file per plan,
  EXPORT sheet), 40 shipped plans in `intake_shipped/` (synthetic / anonymised), `qa/reprice.py` (independent re-pricer),
  `lenai/` companion. `data/nas_dxb/` holds the NAS Dubai industry burning cost **as received (authentic)**: never copy it,
  or the shipped intake files, into this repo; read them at run time from the PBM clone or the run folder.

## Status
| WS | Scope | Status | Laptop check | Next step |
|---|---|---|---|---|
| WS0 | Core: registries, catalogue model + spec parser, evaluator, exposure builder, gates V0–V4 (V5 stub), fixtures, template generator core, work orders WS1–WS6, laptop check | Merged to main (PR #1, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 777c8e8 (Win 11, Py 3.14); GC work laptop (pinned Py 3.12) run outstanding | Run the check on the GC work laptop when available; answer open items below |
| WS1 | B2 rate index, RateFactors, TreatyFeed; B1 level 1; T ingest + V5 | Merged to main (PR #3, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 50d1020; GC work laptop run outstanding | WS3 + WS6 next (WS2 in parallel); answer WS1 open items 11–14 |
| WS2 | A market benchmark | Merged to main (PR #6, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ e54e4b7; GC work laptop run outstanding | Done; CR #13 and items 19–21 applied in the owner-decisions batch |
| OD1 | Owner decisions on HANDOVER items 1–21 (SPEC v0.4; UFIC example; riders; B2 split; B1; V5; scorecard; benchmark) | Built on `owner-decisions-1`, tests green in sandbox, PR open | **pending** | Owner: laptop check on the PR head, then merge |
| WS3 | D scorecard | Merged to main (PR #4, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ d5396ef; GC work laptop run outstanding | Set real weights for UFIC; answer WS3 open items 15–17 |
| WS4 | Integration, release | Blocked on WS1–WS3 | — | docs/workorders/WS4.md |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | Ready (RateFactors on fixtures: `py tools\pw.py index fixtures/RUN_SYN/run_config.json`) | — | docs/workorders/WS6.md |
| WS7 | Structured benefit proposals with the owner's accept flag (CR #17) | Ready after OD1 merges | — | docs/workorders/WS7.md |

### Owner-decisions batch (OD1) notes for the next sessions
- Riders: `reference_sheets.addons = "FILL"` makes the Add-ons sheet quotable; a blank rider is NOT QUOTED (parser sets the
  row to REFER with source_ref "not quoted ..."; the evaluator marks those cells REFER "rider not quoted"). V5 adds
  RIDER_NOT_QUOTED / RIDER_INVALID / RIDER_NO_EXPIRING / RIDER_OUTLIER (rider flags are not in V5_FLAG_SHARE).
- Evaluator result adds `base_status, price_base` (base x rating factors) and `price_riders` (additive modules).
  RateFactors / RateIndex add base-only and rider columns (extras; contract columns unchanged); headline index and
  TreatyFeed on full premium.
- B1: override -> catalogue -> library (source shows the replaced value); rider value = expiring rider premium / expiring
  base over the standard mix (`module_values`), richness = product + sum of rider values; `run_benefit` builds the mix
  from the run's exposure (no exposure config -> riders left out when unchanged, MANUAL_REVIEW when changed).
- Scorecard: scale set by single options; panels = lead on every criterion, SHARE = capacity (sum of members' shares).
- Benchmark: CR #13 dimensions in the registry and the intake layout; bridging of add-on levels (BRIDGED); gap register
  peers same region by default, LOW_PEERS below `gap_min_peers` (3). Fixture `MKT-CEDAR-2026` exercises bridging.
- UFIC example: real bands, master-table networks (plan letters A..G on every TPA), AUH splits on, SME AUH sections,
  Add-ons FILL, Cover states the TPA basis. `tests/test_owner_decisions.py` pins the decisions.

### WS2 notes for the next sessions
- `pw/market_intake.py` + `specs/market/sme_intake_v2_4.json`: one adapter for the SME-INTAKE v2.4 template (layout +
  taxonomy map as data). Writes a catalogue spec; the standard parser reads the rates, so V1 runs on market files.
  All 40 intake files shipped with the SME tool load and pass V1 (sandbox, `PBM_SME_DIR=<PBM>/sme_benchmarking`).
- `io_excel.read_grid` gained `row_keys` (explicit per-row keys) and `value_scale` (monthly x 12); V1 compares the scaled value.
- `pw/tiers.py` (tier_map.csv, ANY precedence, weights sum to 1), `pw/benchmark.py` (ValueMap, GapRegister,
  TaxonomyReconciliation), CLI `benchmark`, `tools/import_sme_basis.py` (tool's REF_LEVER -> runs/<id>/market_basis.json,
  flagged PLACEHOLDER).
- Fixtures: `fixtures/MARKET_SYN` (3 fictional intake files, tier map, option map, standard cells, fictional basis).
- Evaluator: a plan network keyed on TPA `ANY` now resolves for any TPA (market plans have no TPA).

### WS3 notes for the next sessions
- `pw/scorecard.py`: ScoreInputs (SPEC §7) from RateIndex / options.json / `terms_scores.csv`; lead-only panels;
  min-max 0-100; `score` -> Scorecard + Ranking (competition ranks, UNRANKED with reason); weight sensitivity:
  exact one-at-a-time leader intervals and flip weights (scores are linear in the weight), simplex grid win shares.
- Recommendation pack `out/Recommendation_Pack_<RunID>.xlsx` (Summary, Scorecard, Inputs, Sensitivity). Options are
  shown by option_id unless `show_reinsurer_names`; with `market_facing` the `incumbent_names` must not appear (else the
  pack is refused and removed).
- Run config `scorecard` section: weights / weights_file, terms_scores, panels, directions (overrides), grid_step.
  Example: `fixtures/RUN_SYN/run_config.json` + `examples/scorecard_weights.json` (fictional weights).

### WS1 notes for the next sessions
- `pw/template/ingest.py`: `t ingest` = parse + V5 + SUBMISSION catalogue + registration in `runs/<RunID>/options.json`.
  V5 flags HASH_MISMATCH, KEYS_TAMPERED, POSITIONAL_PARSE, BLANK, NON_NUMERIC, NOT_POSITIVE, OUTLIER (ratio vs expiring
  base, band from run config, default 0.7–1.3), NO_EXPIRING, MULTIPLIER_OUTLIER. Never stops; invalid cells are left
  out of the option catalogue (they price UNMATCHED and show in the index's unpriced share).
- TPA factor basis: single switch `TPA_FACTOR_BASIS = "PRE"` in `pw/template/parser.py` (option A, FINAL 24 Oct 2026);
  "POST" neutralises family `tpa` factor tables. Pinned by `tests/test_ws1_ingest.py`.
- `pw/rate_index.py`: RateFactors / RateIndex (scenarios STANDARD = latest UWY × lives in force at snapshot,
  WRITTEN_LY, UWY_MINUS_1; cuts TOTAL → product × region × TPA × plan), TreatyFeed, OptionTerms, `run_b2` orchestration.
- `pw/benefit_value.py`: B1 level 1 on the expiring catalogue's factor scale → library → overrides; MANUAL_REVIEW never 1.
- `pw/outputs.py`: SPEC §7 column contracts checked on write; Parquet + Excel view; `run_manifest.json` with hashes.
- Run config: `fixtures/RUN_SYN/run_config.json` is the template (paths relative to the config file).
- B1 level 2: design only, `docs/B1_level2_design.md` (owner open points listed there).

### WS0 notes for the next sessions
- Package: `pw/` (registry, model, spec_parser, evaluator, exposure, gates, trace, io_excel, template/{spec,generator,parser}).
  CLI `tools/pw.py`; fixture builders `tools/build_fixtures.py`, `tools/build_submissions.py` (byte-reproducible, tested).
- Matching rule: per component the most specific row wins (exact > hierarchy parent > ANY per dimension); equal-specificity
  rows with different values raise. Missing options take the catalogue default (plan -> scope -> component) or raise.
- BLOCK_SET -> BASE_TABLE (reference block) + `<id>.implied` FACTOR_TABLE (median ratio, 4 dp, or declared multipliers);
  resolution DERIVED by default; V1 checks SOURCE reproduction, V2 lists deviating cells with expected values.
- Template: one block per product x region x TPA (a TPA may have several blocks only for disjoint plans, e.g. NE plans);
  `_KEYS` holds live `='Sheet'!$C$7` formulas, so renamed sheets / moved cells are followed; positional fallback if lost.
- Merit contract IP4-8 pinned in `contracts/` with 4 description strings redacted (client names); columns verbatim.
- Determinism: byte-identical on one platform/library build; across platforms (Linux sandbox vs Windows, CPython 3.14
  zlib-ng, openpyxl XML backend) xlsx bytes differ but canonical XML content is identical (tested).
- Data-boundary test scans pw/, registry/, fixtures/, tests/, tools/, contracts/ for the tokens listed in
  `examples/ufic_2027/expected_structure.json`.

## Open with the owner
Items 1–21 were decided on 24 Oct 2026 (log: docs/CHANGE_REQUESTS.md #2–#4, #12 amended, #13, #17–#21; SPEC v0.4 §4.3,
§4.5, §5, §6, §7, §8.0, §8.4, §12). Still open:
1. GC work laptop: run `py tools\laptop_check.py` (pinned Py 3.12) for the merged heads; personal-laptop PASSes are provisional.
2. UFIC confirmations (SPEC §12): SME maternity column labels (owner assumption: RNE = RN, RN = RN2, RN2 = RN3); the
   maternity "Annual Limit" row (ignored for now); F4 consultation deductible "10%" = 1.085 (kept, flagged).
3. "GN excl. named hospitals" network factor on Plan 2 (SME): read as an available network option, not in the base —
   owner to confirm or switch off.
4. Real scorecard weights for UFIC (examples/scorecard_weights.json is fictional).
5. F2 swap and F3 multipliers are applied in the run's expiring UFIC catalogue spec (outside the repo, runs/).

## Timeline driver
UFIC reinsurer submissions due early November 2026. Priority order: OD1 merge → WS6 → WS4 (integration, release) → WS7.
