# Handover — Pricing Workbench

Last updated: 2026-10-24 (WS0 built on `ws0-core`; SPEC v0.3 adds §13 laptop acceptance, CR #1).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests during parallel work (CR #1 applied; #2–#4 pending owner) |
| docs/workorders/WS1–WS4, WS6 | Work orders for the next streams (written by WS0) |
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
| WS2 | A market benchmark | Built on `ws2-benchmark`, tests green in sandbox, PR open | **pending** | Owner: laptop check on the PR head; CR #13 (lever dimensions); WS2 open items 18–21 |
| WS3 | D scorecard | Merged to main (PR #4, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ d5396ef; GC work laptop run outstanding | Set real weights for UFIC; answer WS3 open items 15–17 |
| WS4 | Integration, release | Blocked on WS1–WS3 | — | docs/workorders/WS4.md |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | Ready (RateFactors on fixtures: `py tools\pw.py index fixtures/RUN_SYN/run_config.json`) | — | docs/workorders/WS6.md |

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
- TPA factor basis: single switch `TPA_FACTOR_BASIS = "PRE"` in `pw/template/parser.py` (option A, provisional); "POST"
  neutralises family `tpa` factor tables. Pinned by `tests/test_ws1_ingest.py`.
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

## Open with the owner (owner will answer items 1–2 later; WS0 proceeds with placeholders)
1. UFIC age band labels: DXB Individual (15 bands), AUH Individual (8), SME (8) — not in the reference document (SPEC §8.4).
   Placeholders in `examples/ufic_2027/age_bands.json`; drop real labels + ranges in there, no code change.
2. AUH Individual blocks: keep the catalogue's Married-F column and Employee/SI vs Dependant sections, or collapse to M/F per the
   template principle (SPEC §8.0)?
3. UFIC source flags F1–F8 (SPEC §12), especially F1 (plan→network mapping) and F2 (AUH co-pay block labels).
4. (WS0) TPA factor basis of a submitted per-TPA base rate. **Decision 24 Oct (provisional): option A** — the value
   in a per-TPA block is the base BEFORE the catalogue TPA factor; the issued TPA factor is still applied (current
   WS0 behaviour; Existing Rates shows the pre-factor base). Owner is verifying how the cedant's adjustment factor
   works and will confirm. If it changes to B (block = the TPA's final rate), raise a CR: amend SPEC §8.0, show
   Existing Rates after the TPA factor, set the TPA factor to 1.0 when parsing submissions, state it on the Cover.
5. (WS0) Coverage gate counts PRICED + REFER premium as "matched" — confirm (SPEC §5 wording is ambiguous).
6. (WS0) MODULE unit PER_FAMILY has no allocation rule in SPEC: raises ProposalRequired until defined.
7. (WS0) NE Basic source bands "00–64" / "64+" overlap at 64: example reads them as 0–64 and 65+; confirm with UFIC.
8. (WS0) SME / AUH-Mednet network labels per TPA are not in the reference: example uses the add-on table labels for all TPAs.
9. (WS0) CRs #2–#4 in docs/CHANGE_REQUESTS.md (extra mapping tables, group_size_band as numeric range, V0 version source).
11. (WS1) The index prices the full rated premium (base × factors + add-on modules + fees). Should add-on modules
    (e.g. maternity per eligible female) be excluded from B2, so the index reflects base-rate change only?
12. (WS1) B1 relativity order follows SPEC §4.3 literally: catalogue table → market library → owner overrides, so an
    override only fills gaps. Should owner overrides win instead?
13. (WS1) SPEC §4.3 "plus module values as % of base" needs a base definition (which cell / mix); modules are left out
    of level-1 richness and module option changes are MANUAL_REVIEW until defined.
14. (WS1) V5 outlier band default 0.7–1.3 (run config `v5.outlier_band`); confirm the band for UFIC.
15. (WS3) Default directions: CORRIDOR lower is better (cedant retains fewer LR points), CAP higher is better
    (reinsurer liability capped higher). Confirm, or override per tender in the run config `scorecard.directions`.
16. (WS3) Panels enter the min-max range alongside single options; a panel's share-weighted spread can be lower than
    either member's, which moves the ROBUSTNESS range. Acceptable, or normalise on single options only?
17. (WS3) One-at-a-time sensitivity rescales the other weights proportionally; if a criterion currently has weight 1,
    the others are taken as equal-weighted. Confirm.
18. (WS2) CR #13: add the lever / add-on dimensions so room type, PEC limit, medication, territory and six add-ons
    enter market prices (today benefit lines only; listed per plan in TaxonomyReconciliation).
19. (WS2) Gap threshold: GAP when the subject does not cover a line that >= 50% of same-tier market plans cover
    (run config `gap_share`). Peers are all same-tier market plans; `peer_same_region` restricts to the subject's region.
20. (WS2) Package add-ons the intake prices only at other levels (the SME tool bridges or uses its reference) are kept
    out of the market price and flagged NOT_PRICED; should the workbench bridge them too?
21. (WS2) Reconciliation to the SME tool's 5_Report on its own subject plan needs a workbook saved by Excel (values);
    not automated here - the adapter's V1 on the intake rates is the tie-out today.
10. (WS0) xlsxwriter cannot lock workbook structure (sheet order/insertion); sheets are protected individually and
    `_KEYS` tolerates moves. Acceptable?

## Timeline driver
UFIC reinsurer submissions due early November 2026. Priority order: WS0 → WS1 (B2 + TreatyFeed) → WS3 + WS6 → WS2.
