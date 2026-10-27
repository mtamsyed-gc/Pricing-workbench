# Pricing Workbench — install and release notes

## Versioning
- One version number, `pw.__version__` (pw/__init__.py), shown in the zip folder name `pricing-workbench-<version>/`,
  in `RELEASE.json`, in every run manifest (`versions.pricing_workbench`) and in the Parquet metadata of every output.
- Scheme (owner, 25 Oct 2026): development releases count up by 0.0.1 and a digit never exceeds 9, so 0.0.9 is
  followed by 0.1.0 (and 0.1.9 by 0.2.0). Only official GC test releases move to 1.0.0 and beyond. 0.0.2 is the first
  integrated release (WS4); 0.0.3 adds the Windows file-lock retry found on the GC work laptop; 0.0.4 adds the B2 comparison on the Merit cuts (CR #24); 0.0.5 adds the tender folders, readable Excel views and a one-at-a-time, live laptop check (WS8); 0.0.6 pins Merit contract IP4-9 (Merit v7.5.0) beside IP4-8 (CR #25); 0.0.7 adds the Spec Builder workbook and step files 0a / 0b (WS9, CR #26); the WS0–WS5 development line carried 0.1.0-ws0. Enforced by `tests/test_release.py`.
- A release is built from a commit on `main` whose laptop check passed; `RELEASE.json` and `COMMIT.txt` record it.

## What the zip holds
`tools\package.py` (default mode) writes `out\pricing-workbench.zip`:
- `pricing-workbench-<version>/`: pw/, registry/, contracts/, specs/, fixtures/ (synthetic only), tests/, tools/, docs/,
  examples/scorecard_weights.json (fictional), SPEC.md, HANDOVER.md, CLAUDE.md, requirements-native.txt, RELEASE.json, COMMIT.txt.
- `RUN_LAPTOP_CHECK.bat` at the zip root.
- `TENDER_TEMPLATE/` and `TRAINING_TENDER/` at the zip root (WS8, `pw/tender_kit.py`): tender folders with the four
  step files (`1_make_cedant_workbook.bat`, `2_read_cedant_workbook.bat`, `3_make_tender_template.bat`,
  `4_run_evaluation.bat`), the optional Spec Builder steps `0a_make_spec_builder.bat` / `0b_read_spec_builder.bat`
  (0.0.7, WS9), README.txt and the input folders. TENDER_TEMPLATE is blank (a README in each folder says what
  goes there; `run_config.json` has CHANGE_ME placeholders). TRAINING_TENDER is complete on synthetic data only (fixture
  cedant spec and filled cedant workbook, EXPO_SYN, the two fixture quotes): run its four steps before a real tender.
  `py tools\pw.py tender new <folder> [--training]` writes another one. A tender folder must sit next to the
  `pricing-workbench-<version>` folder; the step files find it and use `py -3.12` when present.
- **Never included:** `reference/` (GC material), `examples/ufic_2027/` (client-derived structure), `runs/`, `out/`, VCS and
  cache folders. Tested by `tests/test_boundary.py` and `tests/test_release.py`; the laptop check run from an
  installed release verifies it again (`installed release contents`).
- The tender's own `template_spec.json` (e.g. the UFIC one) is supplied in the run folder, not in the release.

`tools\package.py --check-bundle` builds the laptop-acceptance bundle instead: the same plus the structure-only
`examples/ufic_2027/` so the cedant-example checks run too. It is for the owner's acceptance runs only; do not distribute it.

## Install on a GC laptop
1. Runtime: CPython 3.12 64-bit, Windows, `py` launcher. Install the pins from GC Artifactory:
   `py -3.12 -m pip install -r requirements-native.txt` (inside the unzipped folder; pip configured for Artifactory as
   for the team's other tools). No other packages are needed.
2. Unzip the release to a short path (e.g. `C:\pw\`): paths stay below 260 characters.
3. Acceptance: double-click `RUN_LAPTOP_CHECK.bat` once (or `py -3.12 tools\laptop_check.py` inside
   `pricing-workbench-<version>\`). It checks the runtime and pins, runs the test suite (repo-only tests are reported
   skipped), every CLI tool, the end-to-end run twice (byte-identical), and writes
   `runs\laptop_check\<stamp>\laptop_check_report.md`. Results print as they are found (also into
   `laptop_check_console.txt` beside the batch file); the test suite step takes 10 to 25 minutes. Only one check runs
   at a time: a second start says so and exits 3. Send the `LAPTOP CHECK ...` line back.

## Running a tender
The simple way (0.0.5): copy `TENDER_TEMPLATE`, rename it, fill its folders and `run_config.json`, and double-click the
four step files in order (each shows its command and waits). The commands they run are these:

Setting up the tender structure without editing JSON (0.0.7, SPEC §8.6, guide: `docs/spec_builder_guide.md`): step
`0a_make_spec_builder.bat` writes `work\spec_builder.xlsx` (pre-filled from `inputs\template_spec.json`, blank when there
is none); fill or change it, save it as `inputs\spec_builder.xlsx`, and run `0b_read_spec_builder.bat`. SPEC READ PASS
writes `inputs\template_spec.json` (the previous one kept as `template_spec.previous.json`); SPEC READ FAIL lists each
problem with its sheet and cell and leaves the spec untouched. Commands:
`py tools\pw.py t spec-builder [<template_spec.json>] --out <builder.xlsx> [--blank-if-missing]` and
`py tools\pw.py t spec-read <builder.xlsx> --out <template_spec.json> [--base <template_spec.json>]`.

Client inputs (the filled cedant workbook, Merit outputs, submissions, the tender's template spec) stay in a folder of
their own, never in the repo; outputs go to `runs\<RunID>\` under the release folder (or `--runs-root`):
1. `py tools\pw.py t cedant <template_spec.json> --out <run>\cedant.xlsx`; GC fills it;
   `py tools\pw.py t cedant-read <filled.xlsx> --spec <template_spec.json> --out <run>\expiring.json` (must PASS).
2. `py tools\pw.py t generate <template_spec.json> --expiring <run>\expiring.json --out <run>\Tender_Rates_<...>.xlsx`; issue it.
3. Run config (template: `fixtures\RUN_SYN\run_config.json`): `expiring`, `exposure` (Merit dim_life, maps, manifest,
   snapshot date), `submissions` (option_id, owner, file, template_spec, issued template), `treaty` (book map, lapse,
   experience, `book_slots`: treaty book -> treaty-tool slot 1-8), `v5`, `gates`,
   `benchmark`, `scorecard`; paths relative to the config.
4. `py tools\pw.py run <run_config.json>`: every gate and every output in `runs\<RunID>\` (manifest:
   `run_manifest.json`, status COMPLETE or STOPPED with the gate that stopped it; exit code 2 when stopped).
5. Treaty tool: `out\TreatyScenarios.json` holds one scenario per option in the tool's config schema (per-book volume
   and LR adjustment); add the reinsurer terms and merge it into the tool's config, or type the values into its
   Scenarios sheet.
