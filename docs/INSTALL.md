# Pricing Workbench — install and release notes

## Versioning
- One version number, `pw.__version__` (pw/__init__.py), shown in the zip folder name `pricing-workbench-<version>/`,
  in `RELEASE.json`, in every run manifest (`versions.pricing_workbench`) and in the Parquet metadata of every output.
- Scheme (owner, 25 Oct 2026): development releases count up by 0.0.1 and a digit never exceeds 9, so 0.0.9 is
  followed by 0.1.0 (and 0.1.9 by 0.2.0). Only official GC test releases move to 1.0.0 and beyond. 0.0.2 is the first
  integrated release (WS4); 0.0.3 adds the Windows file-lock retry found on the GC work laptop; the WS0–WS5 development line carried 0.1.0-ws0. Enforced by `tests/test_release.py`.
- A release is built from a commit on `main` whose laptop check passed; `RELEASE.json` and `COMMIT.txt` record it.

## What the zip holds
`tools\package.py` (default mode) writes `out\pricing-workbench.zip`:
- `pricing-workbench-<version>/`: pw/, registry/, contracts/, specs/, fixtures/ (synthetic only), tests/, tools/, docs/,
  examples/scorecard_weights.json (fictional), SPEC.md, HANDOVER.md, CLAUDE.md, requirements-native.txt, RELEASE.json, COMMIT.txt.
- `RUN_LAPTOP_CHECK.bat` at the zip root.
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
3. Acceptance: double-click `RUN_LAPTOP_CHECK.bat` (or `py -3.12 tools\laptop_check.py` inside
   `pricing-workbench-<version>\`). It checks the runtime and pins, runs the test suite (repo-only tests are reported
   skipped), every CLI tool, the end-to-end run twice (byte-identical), and writes
   `runs\laptop_check\<stamp>\laptop_check_report.md`. Send the `LAPTOP CHECK ...` line back.

## Running a tender
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
