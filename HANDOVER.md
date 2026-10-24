# Handover — Pricing Workbench

Last updated: 2026-10-25 (WS5 cedant rate workbook built on branch `ws5-cedant-workbook`, PR open, laptop check PENDING; UFIC cedant structure provisional on owner items 7–12 below).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests (all decided; CR #17 = work order WS7) |
| docs/workorders/WS1–WS7 | Work orders (WS5: cedant rate workbook, PR open; WS7: structured benefit proposals, CR #17) |
| docs/cedant_workbook_guide.md | WS5 fill guide for GC: what goes where, Nil-base rule, TPA basis, source flags, gate |
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
| OD1 | Owner decisions on HANDOVER items 1–21 (SPEC v0.4; UFIC example; riders; B2 split; B1; V5; scorecard; benchmark) | Merged to main (PR #7, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 32e7a31; GC work laptop run outstanding | Done |
| WS5 | Cedant rate workbook (SPEC §8.5): GC fills current rates in our layout; read back into the expiring catalogue; UFIC structure | Built on branch `ws5-cedant-workbook`, PR #9 open (UFIC deadline 5 Nov) | **PENDING** — run `py tools\laptop_check.py` on the PR head; also open `runs\laptop_check\<stamp>\example_cedant.xlsx` and `example_template.xlsx` in Excel | Owner: laptop check + items 7–12; then GC fills the UFIC copy in `runs\` |
| WS3 | D scorecard | Merged to main (PR #4, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ d5396ef; GC work laptop run outstanding | Set real weights for UFIC; answer WS3 open items 15–17 |
| WS4 | Integration, release | Blocked on WS1–WS3 | — | docs/workorders/WS4.md |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | Ready (RateFactors on fixtures: `py tools\pw.py index fixtures/RUN_SYN/run_config.json`) | — | docs/workorders/WS6.md |
| WS7 | Structured benefit proposals with the owner's accept flag (CR #17) | Ready after OD1 merges | — | docs/workorders/WS7.md |

### WS5 notes for the next sessions
- `pw/template/cedant.py`: `generate_cedant_workbook` (`t cedant`), `read_cedant` / `read_cedant_workbook` (`t cedant-read`,
  report `<out>_read_report.csv`, exit 2 and no catalogue on any problem), `fill_from_catalogue` (fixtures / migration).
  Sheets: Cover, the tender's rate sheets (shared `write_rate_sheets`), Factors, Riders, Plan defaults, Benefits,
  hidden `_LISTS` (dropdown sources), `_KEYS` (kinds FACTOR / RIDER / DEFAULT / BENEFIT / BENEFIT_TEXT beside RATE),
  `_META` (`mode = CEDANT`). Long tables are read by header scan, so spare rows and inserted rows are read too.
- Template spec (structure only), per sheet: `factor_tables`, `riders`, `plan_defaults`, `benefits`, plus
  `scope_id`, `formula`, `premium_basis`, `key_labels`; top level `cedant_workbook` (catalogue_id, version, notes,
  spare_rows, provisional). `spec.cedant_model` normalises and validates them (one implementation for generator and
  reader). These fields are excluded from `spec_hash`, so adding them never changes the issued reinsurer template.
- Read-back scopes: one per sheet × TPA group (TPAs sharing the same factor tables and riders; tables may carry
  `tpas`); the base table keeps `tpa` as a key. Reference levels: one reference option → `reference_level`, else
  `reference_level_by` the key dim; a key without its own reference row inherits the ANY row's.
- Deviation from the work order's column list: Factors / Riders / Plan defaults / Benefits carry a `TPAs` column (TPA
  group) and Factors / Riders a `Key on` column (needed where tables differ by TPA, e.g. F3). Owner item 7.
- Not carried by the workbook (pricing at loading 0 unaffected): LOADING caps, FEE, REFER components, rules, plan
  attributes, benefit co-pay structure objects. `cedant_spec_from_catalogue` lists them in `not_carried`.
- Fixture `fixtures/C_ALPHA` (spec authored from CAT_ALPHA, empty and filled workbooks, read-back `expiring.json`),
  built by `tools/build_submissions.py`. Proven: EXPO_SYN prices cell for cell as CAT_ALPHA (defaults, seeded explicit
  options, fill = reference; traces equal); the reinsurer template from the read-back is byte-identical to T_ALPHA;
  V5 on SUB_Y identical; every gate tested (`tests/test_ws5_cedant.py`); UFIC structure in `tests/test_ws5_ufic.py`.
- Independent review (25 Oct) found 6 defects, all fixed with regression tests: plan defaults checked per key (plan /
  network / TPA); inherited ANY references written per key (fill = reference); formula min / max / refer rules and
  component default_option carried (different formulas on one sheet raise ProposalRequired); `_META.cedant_spec_hash`
  stops a read against a different spec; missing Benefits sheet stops; renamed long-table sheets followed via `_KEYS`;
  negative benefit amounts stop. Known, as in the tender parser: two `_KEYS` formulas swapped by hand swap values
  (only 'moved' warnings).
- UFIC: `examples/ufic_2027/template_spec.json` carries the cedant sections (labels only; Cover notes for F2 / F3 /
  F4 / F6 / F7, AML and maternity column shift, nationality groups). Choices pending the owner are listed in its
  `cedant_workbook.provisional` and items 7–12 below; each is a small JSON edit.

### Owner-decisions batch (OD1) notes for the next sessions
- Riders: `reference_sheets.addons = "FILL"` makes the Add-ons sheet quotable; a blank rider is NOT QUOTED (parser sets the
  row to REFER with source_ref "not quoted ..."; the evaluator marks those cells REFER "rider not quoted"); a rider
  <= 0 or non-numeric is treated the same. V5 adds RIDER_NOT_QUOTED / RIDER_INVALID / RIDER_NO_EXPIRING /
  RIDER_OUTLIER, and RIDERS_UNREAD when `_KEYS` is missing (rider flags are not in V5_FLAG_SHARE).
- Evaluator result adds `base_status, price_base` (base x rating factors) and `price_riders` (premium before loading
  and fees minus price_base: additive and multiplicative riders, any formula order; the parts add up).
  RateFactors / RateIndex add base-only and rider columns (extras; contract columns unchanged); headline index and
  TreatyFeed on full premium.
- B1: override -> catalogue -> library (source shows the replaced value); rider value = expiring rider premium / expiring
  base over the standard mix (`module_values`), richness = product + sum of rider values; `run_benefit` builds the mix
  from the run's exposure (no exposure config -> riders left out when unchanged, MANUAL_REVIEW when changed).
- Scorecard: scale set by single options; panels = lead on every criterion, SHARE = capacity (sum of members' shares).
- Benchmark: CR #13 dimensions in the registry and the intake layout; add-on levels resolved per network
  (`_resolve_level`: exact row, else BRIDGED between the file's own limits; every offered network covered); gap register
  peers same region by default, LOW_PEERS below `gap_min_peers` (3), presence share over all peer plans.
  Fixture `MKT-CEDAR-2026` exercises bridging.
- An independent review of the batch found 9 defects (invalid riders priced, bridging blocked by other networks, rider
  value currency / multiplicative / formula-order errors, unread riders, presence-share denominator, bridging edge
  cases); all fixed with regression tests in `tests/test_owner_decisions.py`.
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
6. Scorecard (SPEC silent): when all single options have the same value on a criterion there is no scale and everyone,
   panels included, scores 100 (e.g. a panel's larger capacity gets no credit if every option offers the same share).
   Keep, or give panels a fixed credit there?
7. WS5 TPA-scoped factor tables (F3): the long tables carry a TPA group column (not in the work order's list). Which
   families apply to Aafiya DXB Individual? Provisional: only its Nil / 10% / 20% block table, read as `copay_op_diag`.
8. WS5 "TPA = 1.0" for Individual: provisional TPA factor table on NC / NAS / Mednet (reference NAS; GC enters the
   values). Confirm, or drop the family for Individual.
9. WS5 reference row ≠ 1.0: the read stops (SPEC "Y = 1.0"). Confirm.
10. WS5 Individual maternity rider: none provisionally (WS5 lists the maternity column shift under SME). Products,
    keys and plan G column if one is wanted.
11. WS5 SME option lists: consultation deductible taken from Factors-Individual; SME DXB-NE IP / day-case co-pay
    present; "AUH IP deductible" = the AED 200 option of the IP table. Confirm.
12. WS5 SME AML reference per plan letter (A 1.5m, B 1m, C 500k, D–F 250k), and network option 2 (DXB plans B, C) kept
    in the expiring catalogue with "GN excl. named hospitals" on SME plan B (with item 3). Confirm.

## Timeline driver
UFIC reinsurer submissions due 5 Nov 2026. Priority order: WS5 (PR open: laptop check + items 7–12; then GC fills the
UFIC copy in `runs\`, reads it back, and the reinsurer template is generated with `--expiring`) → WS4 (integration,
release on GC laptops) → WS6 (Merit as-if, other repo, can run in parallel) → WS7.
