# Work order WS8 — Release hardening from the first laptop dry run (release 0.0.5)

Branch: `ws8-release-hardening` · Read: SPEC §7 (all outputs: Parquet + an Excel view), §13; docs/INSTALL.md ·
Depends on: WS4 (release zip, laptop check), WS5 (cedant workbook), OD4 (0.0.4)

## Goal
The first full dry run of release 0.0.4 on the owner's laptop (25 Oct 2026: unzip, laptop check, cedant workbook,
tender template, three quotes, `run`, outputs in Excel) worked end to end but showed three gaps. Close them before the
GC work laptop check, so that check runs once on the release that will be used for the first tender.

## Deliverables
1. **Tender folder in the release.** The zip root holds, beside `pricing-workbench-<version>/`:
   - `TENDER_TEMPLATE/`: the four step files (`1_make_cedant_workbook.bat` … `4_run_evaluation.bat`), README.txt, a
     run config template and a README in each input folder (inputs, exposure\maps, submissions, treaty). Copy it,
     rename it and replace the inputs for a tender.
   - `TRAINING_TENDER/`: the same step files on synthetic data only (the fixture cedant spec and filled cedant
     workbook, the synthetic Merit extract and maps, the two fixture quotes, the synthetic treaty inputs), so a new
     user can run all four steps before touching client data.
   Each step file finds the `pricing-workbench-*` folder next to the tender folder, uses Python 3.12 through the `py`
   launcher when present (else the default `py`), shows the command it runs and waits for a key.
   CLI: `py tools\pw.py tender new <folder> [--training]` writes the same folders (for a second tender).
2. **Readable Excel views.** Every output table's `.xlsx` view gets a column width per column (from the header and
   the formatted values, capped) and a number format per column: whole numbers without decimals, amounts
   (|x| ≥ 1,000) with thousands separators and 2 decimals, ratios / factors with 4 decimals. Parquet is unchanged.
3. **Laptop check.** One check at a time (a lock under `runs\laptop_check\`; a second start says so and exits 3; a
   lock older than 3 hours is treated as stale), and live progress: each line is printed as the check runs, and the
   batch file writes `laptop_check_console.txt` from the check itself instead of buffering the window.
4. Release 0.0.5 (`pw.__version__`), docs/INSTALL.md, HANDOVER.md.

## Files
- May create: `pw/tender_kit.py`, `tests/test_ws8_*.py`, this work order.
- May edit: `pw/outputs.py` (Excel view only), `tools/pw.py`, `tools/package.py`, `tools/laptop_check.py`,
  `tools/RUN_LAPTOP_CHECK.bat`, `pw/__init__.py`, docs/INSTALL.md, HANDOVER.md.
- Must not edit: contracts, registries, Parquet outputs or their columns.

## Acceptance criteria
- The release zip has `TENDER_TEMPLATE/` and `TRAINING_TENDER/` at its root; neither contains client names or values
  (boundary test).
- The training tender's four steps, run as the step files run them, end in `CEDANT READ PASS`, a template whose
  structure hash matches the quotes, and `RUN COMPLETE` with every gate passed.
- Excel views open with no `#####` columns at default zoom for the run outputs; the run stays byte-identical on a
  second run.
- A second laptop check started while one runs exits 3 with a clear message; the console file is written live.
- `tools/laptop_check.py` covers `tender new` and the training tender's four steps (SPEC §13 coverage rule).
- Full suite green; laptop check PASS on the owner's laptop (environment lines aside on Python 3.14).
