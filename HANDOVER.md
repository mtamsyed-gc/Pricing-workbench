# Handover — Pricing Workbench

Last updated: 2026-10-27 (WS9 built: Spec Builder workbook, `t spec-builder` / `t spec-read`, step files 0a / 0b, release 0.0.7 on branch ws9-spec-builder, laptop check PENDING; before: 2026-10-26 CR #26 / WS9 work order and SPEC §8.6 merged (PR #20); before: CR #25: Merit contract IP4-9 (Merit v7.5.0) pinned beside IP4-8, release 0.0.6 on branch cr25-merit-ip4-9, laptop check PENDING; before: 2026-10-25 release 0.0.5 merged: WS8 release hardening — TENDER_TEMPLATE and TRAINING_TENDER with step files in the release, readable Excel views, one-at-a-time live laptop check. Laptop check of 0.0.5 on the owner's personal laptop 48/49, Python-version line waived by the owner. User guide (private artifact) updated to 0.0.5 with context, data requirements and output analysis. Next: 1.0.0 on the owner's word, then the first real tender run).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests (all decided; CR #17 = work order WS7) |
| docs/workorders/WS1–WS9 | Work orders (WS7: structured benefit proposals, CR #17; WS8: release hardening, 0.0.5; WS9: Spec Builder workbook, CR #26) |
| docs/cedant_workbook_guide.md | WS5 fill guide for GC: what goes where, Nil-base rule, TPA basis, source flags, gate |
| docs/spec_builder_guide.md | WS9 guide for non-technical users: the Spec Builder sheets, the five structured fields, the 0a / 0b loop |
| tools/laptop_check.py | SPEC §13 laptop acceptance: run `py tools\laptop_check.py` on the laptop after every change; since WS4 also the release gate (end-to-end `run` twice, byte-identical), runnable from the installed release zip |
| docs/INSTALL.md | WS4: release contents, versioning, install on a GC laptop, running a tender end to end |
| contracts/treaty_feed_contract.json | WS4: TreatyFeed / OptionTerms columns and types checked on every run; treatymodel 2.0 findings and gaps G1–G4 (CR #23) |
| reference/ufic/UFIC_Medical_Reinsurance_Reference.md | TEMPORARY GC material: UFIC catalogue V10 14.1 reference (ToB, factors, rate-table structure, UW rules). Structure only — see CLAUDE.md data boundary |
| requirements-native.txt | Runtime pins (same as ete-dashboard) |

## Related repos and tools
- ete-dashboard / side_tools/merit (Merit v7.5.0, contract IP4-9; IP4-8 runs from v7.3.x / v7.4.0 still accepted, CR #25):
  exposure and experience source. Contract `side_tools/merit/config/model_contract.json`
  (IP4-8 / IP4-9, same layout): dim_life carries Policy Type, TPA, Region Group, Network, Plan / Category, Relation, Gender Group, Marital Status,
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
| WS1 | B2 rate index, RateFactors, TreatyFeed; B1 level 1; T ingest + V5 | Merged to main (PR #3, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 50d1020; GC work laptop run outstanding | Done (open items 11–14 decided 24 Oct, OD1) |
| WS2 | A market benchmark | Merged to main (PR #6, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ e54e4b7; GC work laptop run outstanding | Done; CR #13 and items 19–21 applied in the owner-decisions batch |
| OD1 | Owner decisions on HANDOVER items 1–21 (SPEC v0.4; UFIC example; riders; B2 split; B1; V5; scorecard; benchmark) | Merged to main (PR #7, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 32e7a31; GC work laptop run outstanding | Done |
| WS5 | Cedant rate workbook (SPEC §8.5): GC fills current rates in our layout; read back into the expiring catalogue; UFIC structure | Merged to main (PR #9, 25 Oct) | **PASS (25 Oct, provisional)** — functional PASS on owner's personal laptop @ 21003ca (Win 11, Py 3.14.6): suite 112/112, every tool check, UFIC cedant + reinsurer workbooks and the fixture cedant workbook open in Excel; only environment lines fail (Py 3.14 not 3.12, unpinned packages). GC work laptop run outstanding | GC fills the UFIC cedant workbook in `runs\`, `t cedant-read` to PASS, then `t generate --expiring` and issue (UFIC deadline 5 Nov) |
| WS3 | D scorecard | Merged to main (PR #4, 24 Oct) | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ d5396ef; GC work laptop run outstanding | Set real weights for UFIC (open item 4); items 15–17 decided 24 Oct (OD1) |
| WS4 | Integration, release: `pw run` end to end, manifest gates, treaty contract check, release zip 0.0.2, laptop check as release gate | Merged to main (PR #13, 25 Oct) | **PASS (25 Oct, provisional)** — from the installed release zip 0.0.2 @ 1accbbb on the owner's personal laptop (Win 11, Py 3.14.6): release contents, test suite, every tool check, `run` twice byte-identical (46 files), pack and TreatyFeed open in Excel; 3 cedant-example checks SKIP (not in release); only environment lines fail. Launched with a default-`py` copy of RUN_LAPTOP_CHECK.bat (the shipped one requires Py 3.12). GC work laptop run outstanding | Done; release a GC test version (1.0.0) from main after the GC work laptop check passes |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | Ready (RateFactors on fixtures: `py tools\pw.py index fixtures/RUN_SYN/run_config.json`) | — | docs/workorders/WS6.md |
| WS7 | Structured benefit proposals with the owner's accept flag (CR #17) | Ready (OD1 merged) | — | docs/workorders/WS7.md |
| WS8 | Release hardening (0.0.5): tender folders + step files in the release, `tender new`, readable Excel views, laptop check lock + live console | Merged to main (PR #17, 25 Oct) | **PASS (owner override, 25 Oct)** — from the installed 0.0.5 release zip @ e0b9e35 on the owner's personal laptop (Win 11, Py 3.14.6): 48/49, 3 skipped (not in release); the only FAIL is the Python 3.12 line, which the owner waived ("assume if it works fine it'll work on the GC laptop"). Every pin, the suite, every tool, the training tender's four steps, byte-identical rerun and Excel open PASS; lock and live console confirmed by hand. The refused second start emptied the running check's console file: fixed in the merge commit (console reset only after the lock is taken) | Cut 1.0.0 when the owner says; GC laptop run optional |
| CR #25 | Merit contract IP4-9 (Merit v7.5.0, ete-dashboard 3eaaa30) pinned beside IP4-8 (same 4 redactions); field map IP4-9 = IP4-8; SPEC §5; V0 OK on both; exposure tests on both; laptop check line "gates v0 contract check, Merit v7.5.0 (IP4-9, CR #25)"; release 0.0.6. Note for runs: where Merit calculates the policy type, PolicyTypeUsed is now 'Group' (was 'Non-SME'): `segment_map.csv` needs a 'Group' row (MappingRequired otherwise) | Branch cr25-merit-ip4-9, PR open | **PENDING**: `py tools\laptop_check.py` (or RUN_LAPTOP_CHECK.bat from the 0.0.6 release zip) | Owner runs the laptop check, then merge |
| WS9 | Spec Builder workbook (SPEC §8.6, CR #26): `pw/template/builder.py`, `t spec-builder` / `t spec-read`, step files 0a / 0b in both tender folders, fixture `fixtures/C_ALPHA/spec_builder.xlsx`, guide `docs/spec_builder_guide.md`, release 0.0.7 | Built on branch ws9-spec-builder (PR open); sandbox: suite green, laptop check --quick every tool / step line PASS (environment lines only fail on Linux) | **PENDING**: `py tools\laptop_check.py` (or RUN_LAPTOP_CHECK.bat from the 0.0.7 release zip); also open `runs\laptop_check\<stamp>\example_spec_builder.xlsx` in Excel and try a dropdown | Owner runs the laptop check, then merge |

### WS9 notes for the next sessions
- `pw/template/builder.py`: `generate_builder(spec | None, out)` (xlsxwriter, deterministic) and
  `read_builder(xlsx, base_spec, previous_spec)` (openpyxl, header scan, gated; spec None on any problem). Sheets:
  Cover, Tender and Cedant workbook (field / value), Lists (user dropdown lists, not read back), Age bands, Columns,
  Sheets, Co-pay basis, Blocks, Plans, Sections, Custom rows, Refer cells, Factor tables, Riders, Options, Plan
  defaults, Benefits, Cedant notes; hidden `_LISTS` (fixed dropdowns), `_META` (mode SPEC_BUILDER, builder version,
  source spec hash, source cedant spec hash).
- Round trip: with the base spec the read gives back the same JSON (content and key order) for T_ALPHA, C_ALPHA and the
  UFIC example; templates and cedant workbooks byte-identical. Mechanism: fields the builder does not model are copied
  from the base per object (top level, sheet, block, plan, factor table / rider, formula, options, cedant_workbook);
  a block whose normalised form is unchanged, and a factor table / rider whose cedant model is unchanged, keep the
  base's raw JSON. Without a base the read writes a canonical form (factor tables as options x key_values when the
  rows are a full grid, else rows; reference as one option when it marks the same rows, else by key) with the same
  meaning (tested: `_semantic` in tests/test_ws9_builder.py).
- Age bands from `age_bands_file` are shown with Source "file ..."; on read they must equal the file (else stop:
  edit the file); the spec keeps the file reference. Bands with no Source are written inline.
- Gates: blank mandatory, not in a fixed list, not a number / whole number / date, duplicates (sheet, block, plan,
  component, option row, band label, column, co-pay family, plan default, benefit), undefined band set / column set /
  sheet / block / component / refer plan, age from > to, overlapping bands, two row sources on one sheet or block,
  reference rows per key, riders with a reference, builder older than the spec (spec_changed; allowed when the
  spec's .previous.json is the builder's source, i.e. the same builder read again), then the spec validator and the
  cedant model (`spec_invalid`).
- Deviations from the work order (reasons in the PR): Plans is a long table (one row per plan), not a plan-letter grid,
  because plan ids are not letters in every spec; Co-pay basis, Options and Cedant notes are sheets of their own (the
  work order's Factors / Riders rows split into a table sheet and one Options sheet); the "TPA twice on one sheet" gate
  is the validator's TPA x plan rule (UFIC NE has three Aafiya blocks with different plans, which is valid); Plan label
  is mandatory (the template generator needs it); families are suggestions, not gated (a family is a label, e.g.
  'nationality', while option dimensions and key dimensions are gated by the registry).
- Laptop check: `t spec-builder` (fixture, blank, UFIC example), `t spec-read` (fixture PASS, blank FAIL), training
  tender steps 0a / 0b before steps 1-4, "spec builder round trip gives the same spec", builders open (openpyxl,
  Excel on Windows). Release check expects 4 step files + 2 Spec Builder steps per tender folder.

### WS8 notes for the next sessions
- Found by the first full dry run of release 0.0.4 on the owner's personal laptop (25 Oct 2026; synthetic UFIC-shaped
  tender kept outside the repo; user guide published as a private artifact): the release had no step files or tender
  folder, output Excel views opened with ##### columns, and a double-click started two laptop checks with a blank window.
- `pw/tender_kit.py` is the single source of the step files, READMEs and run config template; `tools/package.py` writes
  TENDER_TEMPLATE/ and TRAINING_TENDER/ at the zip root, `py tools\pw.py tender new` writes them anywhere. The training
  tender is the fixture cedant spec C_ALPHA (its template has the same structure hash as T_ALPHA, so the SUB_X / SUB_Y
  quotes ingest against the step-3 template) + EXPO_SYN + RUN_SYN treaty inputs; no benchmark section.
- The laptop check reads each step's command from the .bat itself and runs the training tender's four steps from the
  tender folder (SPEC §13 coverage). Lock: runs/laptop_check/RUNNING.lock (stale after 3 h); exit 3 when locked.
- Excel views (`pw/outputs.write_table`): per-column width (header / formatted values, 8-60) and number format (whole
  numbers `#,##0`, year columns `0`, |x| ≥ 1,000 `#,##0.00`, else `0.0000`). Parquet unchanged; still byte-identical.

### WS4 notes for the next sessions
- `pw/pipeline.py` `run_all` (CLI `run <run_config.json> [--runs-root] [--hashes]`): catalogue specs (V1 on the expiring,
  the benchmark's market catalogue specs and `gates.v1_catalogues`; a read-back catalogue.json is NOT_APPLICABLE) and
  V2 → exposure (V0, coverage gate, `gates.coverage_threshold` default 0.95) → V3 (report) → V4 on each issued template
  spec (`gates.v4`, default on) → T ingest + V5 per `submissions[]` (option_id, owner, file, template_spec, issued) →
  `run_b2` (B1, B2, TreatyFeed, OptionTerms; reuses the gated exposure) → treaty contract check → benchmark → scorecard.
- The run owns and clears `run_manifest.json, options.json, options/, gates/, out/, v4/` in the run folder at the start
  (anything else, e.g. a cedant read-back expiring.json, is kept). Manifest: `versions`, `inputs.files` (sha256 of
  every file the config names, paths as written in it, plus each spec's source workbook), `gates` (V0, V1 per
  catalogue, V2, V3, V4, V5 per option, COVERAGE, TREATY_CONTRACT), `run` (status COMPLETE / STOPPED, steps, error).
  Gate details in `gates/`. A stopping gate (V0, V1, coverage, V4, treaty contract) ends the run, exit code 2.
- Byte-identical on a second run (different run roots too), tested in `tests/test_ws4_run.py` and in the laptop check.
- `run_b2(cfg, runs_root, exposure=None, coverage=None)`: optional pre-built exposure / coverage (no behaviour change).
- Treaty tool: `pw/treaty_contract.py` checks TreatyFeed / OptionTerms (Parquet + Excel view) against
  `contracts/treaty_feed_contract.json` (SPEC §7 columns, types, nulls, finiteness, keys) and warns beyond the tool's
  slots (8 books, 6 reinsurers). Compared with treatymodel 2.0 (PBM treatymodel/ and the vendored copy in ete-dashboard
  side_tools/treaty_tool/, same commit a07c945): its machine interface is the config JSON (scenarios[].books.volume /
  lr_adj by book slot; reinsurer terms are owner inputs). CR #23 APPROVED and applied: `run_b2` writes
  `out/TreatyScenarios.json` (`rate_index.treaty_scenarios`; run input `treaty.book_slots` required with a treaty
  section), checked by the treaty contract (`treatymodel_verified` true); engine reproduction tested.
- Release: version `pw.__version__` = 0.0.2 (single source; scheme in docs/INSTALL.md: +0.0.1 per development release, no digit above 9, 1.0.0 only for official GC test releases). `tools/package.py` writes RELEASE.json + COMMIT.txt into
  `pricing-workbench-<version>/` and RUN_LAPTOP_CHECK.bat (finds the folder by pattern) at the root, in both modes.
  Release excludes reference/, examples/ufic_2027/, runs/, out/ (tests/test_boundary.py, tests/test_release.py).
- Tests that need repo-only content carry `REQUIRES = (...)` (module) or `@requires(...)` (tests/_util.py). In an
  installed release (RELEASE.json at the root) they are SKIPPED and listed; in a clone a missing path FAILS. The
  laptop check from a release reports the cedant-example tool checks as SKIP and checks the release contents.
- Run config `fixtures/RUN_SYN/run_config.json` gained `submissions` and `gates` (built by tools/build_fixtures.py).

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
   25 Oct, release 0.0.2 @ 847f6bc from C:\pw: LAPTOP CHECK FAIL 41/42 (3 skipped). Python 3.12.10 and all 11 pins PASS; all
   tool checks, `run` x2 byte-identical and Excel PASS; the test suite failed only test_ws5_cedant.test_gate_failures_one_by_one
   (PermissionError WinError 5 on the .tmp -> .xlsx swap in io_excel.make_reproducible: a corporate antivirus / indexer
   lock). Fixed in 0.0.3 (io_excel.replace_file retries ~6 s); re-run the check on the GC laptop from the 0.0.4 zip (0.0.3 + OD4).
   Owner (25 Oct): runs it once he is happy with the tool and the synthetic runs and testing here.
2. UFIC confirmations (SPEC §12): SME maternity column labels (owner assumption: RNE = RN, RN = RN2, RN2 = RN3) — to
   confirm with UFIC; F4 consultation deductible "10%" = 1.085 (kept, flagged). DECIDED 25 Oct: the maternity "Annual
   Limit" row is ignored; SME has no TPA factor (none on the Factors-SME sheet; removed from the UFIC cedant structure).
3. "GN excl. named hospitals" network factor on Plan 2 (SME): switched off for now (owner, 25 Oct; see item 12).
4. DECIDED (owner, 25 Oct, CR #22): UFIC scorecard weights in `examples/ufic_2027/scorecard_weights.json` (price and
   quality 0.65, terms 0.35; CAP 0). terms_scores.csv records 'none' as 0. examples/scorecard_weights.json stays fictional.
5. F2 swap and F3 multipliers are applied in the run's expiring UFIC catalogue spec (outside the repo, runs/).
6. Scorecard (SPEC silent): when all single options have the same value on a criterion there is no scale and everyone,
   panels included, scores 100 (e.g. a panel's larger capacity gets no credit if every option offers the same share).
   DECIDED (owner, 25 Oct, CR #22): keep 100 and flag NO_SPREAD; SHARE on an absolute scale (share of the order filled).
7. WS5 — DECIDED (owner, 25 Oct): Factors-Individual is switched off for every Individual DXB-NE TPA until clarified
   (no OP diagnostic / consultation / pharmacy / network option / nationality / TPA factor tables); Aafiya DXB-NE keeps
   only its co-pay block factors. The long tables keep the TPA group column (needed for this split).
8. WS5 — DECIDED with 7: no Individual TPA factor table. To restore later: add the tables back to
   `examples/ufic_2027/template_spec.json` (sheet "Ind Rates - DXB-NE") and regenerate the cedant workbook.
9. WS5 — DECIDED (owner, 25 Oct): a reference row ≠ 1.0 is a WARNING, the value is kept as entered (SPEC §8.4 note).
10. WS5 — DECIDED (owner, 25 Oct): no Individual maternity rider; every Individual TPA block is M/SF + Married-F (Married-F
    includes the maternity load). SPEC §8.4 corrected (DXB-NE Individual was M/F); the UFIC tender template changes
    accordingly (not issued yet).
11. WS5 — DECIDED (owner, 25 Oct, from the Factors-SME sheet): SME has its own consultation deductible table (Individual
    none); IP / day-case co-pay is one family, 0–30% on both emirates, NIL / AED 200 deductible rows Abu Dhabi only.
12. WS5 — DECIDED (owner, 25 Oct): the AML-by-network table is SME's (references 1.5m / 1m / 500k / 250k per column,
    confirmed); Individual AML is fixed by the ToB. SME network options (Option 2, "GN excl. named hospitals") switched
    off for now — closes item 3 as "off". Note: reference/ §3.2 labels that AML table as Individual; it is SME's.

13. WS4 — CR #23 DECIDED (owner, 25 Oct): approved as proposed; applied in WS4 (TreatyScenarios.json, treaty.book_slots).
14. WS4 — DECIDED (owner, 25 Oct): version 0.0.2; +0.0.1 per development release, never above 0.0.9 / 0.x.9 (then the next
    digit up, 0.1.0); only official GC test releases move to 1.0.0 and beyond.

### OD4 notes (CR #24, owner 25 Oct 2026)
- Merit's dim_life has no AML, limit, co-pay or deductible fields, so B2 compares only on the Merit cuts. `rate_index.b2_eval_options`: fill = reference for every option family plus `default_families` (evaluator option) for the headline riders, default `module_maternity` at the plan's catalogue default limit. Run config `b2`: basis MERIT_CUTS (default) | FULL (old behaviour), `headline_modules`.
- Headline = base + maternity for every line (Individual's maternity sits in the Married-F rate). TPA (and nationality, where a catalogue has it) factors are Merit-keyed and apply. TreatyFeed rate factor = headline book relativity.
- `RiderIndex` output (not scored): rider family x limit, eligible-lives weighted, not-quoted share; TOTAL and product x emirate. B1 (richness) unchanged and still uses catalogue defaults; V3 and the coverage report also unchanged (defaulted share stays informational).
- UFIC: no nationality factor (removed from the SME structure); no nationality cut.

## Timeline driver
UFIC reinsurer submissions due 5 Nov 2026. Priority order: UFIC data (WS5 merged: GC fills the
UFIC copy in `runs\`, reads it back, and the reinsurer template is generated with `--expiring`) → GC work laptop check of release 0.0.2 →
WS6 (Merit as-if, other repo, can run in parallel) → WS7.
