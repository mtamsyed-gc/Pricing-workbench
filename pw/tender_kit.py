"""Tender folders for the release (work order WS8): TENDER_TEMPLATE (blank) and TRAINING_TENDER (synthetic).

A tender folder sits next to the pricing-workbench-<version> folder and holds one evaluation's inputs, the four step
files and the outputs. The step files find the tool folder themselves, so the folder can have any name and live in
any working area. The training tender is built from the synthetic fixtures only (CLAUDE.md data boundary).

    py tools\\pw.py tender new <folder> [--training]
"""
from __future__ import annotations

import json
from pathlib import Path

from . import REPO_DIR, SpecError

FIX = REPO_DIR / "fixtures"
TEMPLATE_NAME = "TENDER_TEMPLATE"
TRAINING_NAME = "TRAINING_TENDER"

_HEAD = r"""@echo off
rem {title}
rem Double-click this file. It finds the pricing-workbench-<version> folder next to this tender folder, shows the
rem command it runs, runs it, and waits so you can read the result.
setlocal
cd /d "%~dp0"
set "PWDIR="
for /d %%D in ("%~dp0..\pricing-workbench-*") do set "PWDIR=%%~fD"
if not defined PWDIR (
  echo Cannot find a pricing-workbench-^<version^> folder next to this tender folder.
  echo Put this tender folder in the same folder as pricing-workbench-^<version^>.
  pause
  exit /b 1
)
set "PY=py -3.12"
py -3.12 --version >nul 2>&1 || set "PY=py"
if not exist work mkdir work
echo ============================================================
echo  {title}
echo  Tool:   %PWDIR%
echo  Tender: %CD%
echo ============================================================
echo.
"""
_TAIL = r"""set RC=%ERRORLEVEL%
echo.
if "%RC%"=="0" (echo DONE - exit code 0.) else (echo STOPPED - exit code %RC%. Read the messages above.)
pause
exit /b %RC%
"""
# (file, title, pw.py arguments) - the arguments are relative to the tender folder
STEPS = [
    ("1_make_cedant_workbook.bat", "Step 1 - make the blank cedant rate workbook",
     r"t cedant inputs\template_spec.json --out work\cedant_workbook_blank.xlsx"),
    ("2_read_cedant_workbook.bat", "Step 2 - read back the filled cedant workbook (expiring catalogue)",
     r"t cedant-read inputs\cedant_filled.xlsx --spec inputs\template_spec.json --out work\expiring.json"),
    ("3_make_tender_template.bat", "Step 3 - make the reinsurer tender template",
     r"t generate inputs\template_spec.json --expiring work\expiring.json --out work\tender_template.xlsx"),
    ("4_run_evaluation.bat", "Step 4 - run the full evaluation (gates, rate index, scorecard)",
     r"run run_config.json --runs-root runs"),
]


# WS9 (SPEC §8.6): optional steps before step 1 - author or change inputs\template_spec.json in Excel
SPEC_STEPS = [
    ("0a_make_spec_builder.bat", "Step 0a - make the Spec Builder workbook (the tender structure in Excel)",
     r"t spec-builder inputs\template_spec.json --blank-if-missing --out work\spec_builder.xlsx"),
    ("0b_read_spec_builder.bat", "Step 0b - read the filled Spec Builder back into the tender spec",
     r"t spec-read inputs\spec_builder.xlsx --base inputs\template_spec.json --out inputs\template_spec.json"),
]


def step_args(i: int) -> list[str]:
    """The pw.py arguments of step i (0-based), split, with Windows separators (also valid on Linux via Path)."""
    return [a.replace("\\", "/") for a in STEPS[i][2].split()]


def _bat(title: str, args: str) -> bytes:
    body = _HEAD.format(title=title) + (f"echo Running: %PY% tools\\pw.py {args}\necho.\n"
                                        f"%PY% \"%PWDIR%\\tools\\pw.py\" {args}\n") + _TAIL
    return body.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii")


def _txt(s: str) -> bytes:
    return s.strip("\n").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8") + b"\r\n"


README = """{name} - Pricing Workbench tender folder
{rule}
{intro}

Keep this folder NEXT TO the pricing-workbench-<version> folder (same parent folder), then double-click the steps
in order. Each step shows the command it runs and waits for a key; exit code 2 means a gate stopped it on purpose
(the messages say what to fix).

Optional, before step 1 - set up or change the tender structure in Excel instead of editing the JSON:
  0a_make_spec_builder.bat     Spec Builder workbook            -> work\\spec_builder.xlsx (pre-filled from
                                                                   inputs\\template_spec.json, blank if there is none)
  0b_read_spec_builder.bat     read the filled builder back     -> inputs\\template_spec.json (the previous one is kept
                               (save it as inputs\\spec_builder.xlsx first)   as template_spec.previous.json)

  1_make_cedant_workbook.bat   blank cedant rate workbook       -> work\\cedant_workbook_blank.xlsx
  2_read_cedant_workbook.bat   read back the filled workbook    -> work\\expiring.json (+ expiring_read_report.csv)
  3_make_tender_template.bat   template to send to reinsurers   -> work\\tender_template.xlsx
  4_run_evaluation.bat         full evaluation                  -> runs\\<run_id>\\ (start with out\\Recommendation_Pack_*.xlsx)

You fill or replace:
  inputs\\        template_spec.json (tender structure; or spec_builder.xlsx, step 0a's workbook filled in, then
                 step 0b), scorecard_weights.json, cedant_filled.xlsx (step 1's workbook after the cedant's current
                 rates are typed in)
  exposure\\      the Merit extract (dim_life.csv, run_manifest.csv) and maps\\ (mapping tables)
  submissions\\   one quote workbook per reinsurer, as returned (filled copies of work\\tender_template.xlsx)
  treaty\\        treaty_book_map.csv, experience.csv
  terms_scores.csv, run_config.json
The tool writes (do not edit): work\\, runs\\

A real tender folder holds client data: keep it on the GC laptop and never send it to a reinsurer. Reinsurers
receive work\\tender_template.xlsx only.
"""

FOLDER_NOTES = {
    "inputs": "Put here: template_spec.json (the tender's structure, from the tool owner, or written by step 0b from "
              "spec_builder.xlsx, step 0a's Spec Builder after you have filled it), age bands if the spec names "
              "a file, scorecard_weights.json, and cedant_filled.xlsx (step 1's workbook after GC has typed in the "
              "cedant's current rates, factors, riders, plan defaults and benefits).",
    "exposure": "Put here the Merit extract for the tender as Merit writes it: dim_life.csv and run_manifest.csv. "
                "Do not edit them by hand. The mapping tables go in maps\\.",
    "exposure/maps": "Mapping tables from Merit labels to the tender's codes: segment_map.csv (policy_type, "
                     "region_group -> product_type, regulator, rating_region), tpa_map.csv (source_tpa, tpa), "
                     "plan_map.csv (product_type, rating_region, tpa, source_plan, plan), network_map.csv (tpa, "
                     "source_network, network), member_category_map.csv (product_type, relation, member_category), "
                     "nationality_map.csv (source_group, nationality_group), value_map.csv (dim, source_value, value "
                     "for gender, marital and maternity_eligible). ANY in a key column matches every value. Add a row "
                     "whenever the coverage report names a MappingRequired label.",
    "submissions": "One workbook per reinsurer, exactly as returned (a filled copy of work\\tender_template.xlsx as "
                   "issued). Add each one to 'submissions' in run_config.json.",
    "treaty": "treaty_book_map.csv (product_type, rating_region, tpa -> treaty_book; ANY matches every value) and "
              "experience.csv (treaty_book, earned_prem, ultimate_claims).",
}

TEMPLATE_CONFIG = {
    "run_id": "CHANGE_ME_RUN_ID",
    "expiring": "work/expiring.json",
    "exposure": {"dim_life": "exposure/dim_life.csv", "maps": "exposure/maps", "manifest": "exposure/run_manifest.csv",
                 "snapshot_date": "YYYY-MM-DD"},
    "treaty": {"book_map": "treaty/treaty_book_map.csv", "experience": "treaty/experience.csv",
               "lapse": {"CHANGE_ME_BOOK": 0.05}, "book_slots": {"CHANGE_ME_BOOK": 1}},
    "v5": {"outlier_band": [0.7, 1.3]},
    "submissions": [{"option_id": "CHANGE_ME_OPTION", "owner": "Reinsurer name", "file": "submissions/CHANGE_ME.xlsx",
                     "template_spec": "inputs/template_spec.json", "issued": "work/tender_template.xlsx"}],
    "gates": {"coverage_threshold": 0.95, "v4": True},
    "benefit_overrides": [],
    "b2": {"basis": "MERIT_CUTS", "headline_modules": ["module_maternity"]},
    "scorecard": {"weights_file": "inputs/scorecard_weights.json", "terms_scores": "terms_scores.csv", "panels": [],
                  "grid_step": 0.1, "show_reinsurer_names": False, "market_facing": False, "incumbent_names": []},
    "duckdb": {"memory_limit": "2GB", "threads": 2},
}


def _json(d) -> bytes:
    return (json.dumps(d, indent=1) + "\n").encode("utf-8")


def _common(name: str, intro: str) -> dict[str, bytes]:
    files = {f: _bat(t, a) for f, t, a in SPEC_STEPS + STEPS}
    files["README.txt"] = _txt(README.format(name=name, rule="=" * (len(name) + 39), intro=intro))
    return files


def template_files() -> dict[str, bytes]:
    """Blank tender folder: step files, README, run config template, a README per input folder."""
    files = _common(TEMPLATE_NAME, "A blank tender folder. Copy it, rename it (any name), put the tender's inputs in "
                                   "the folders below and edit run_config.json (Notepad; paths are relative to it).")
    files["run_config.json"] = _json(TEMPLATE_CONFIG)
    files["terms_scores.csv"] = _txt("option_id,commission_pct,profit_share_pct,corridor_pts,cap_pct,share_pct")
    for d, note in FOLDER_NOTES.items():
        files[f"{d}/README.txt"] = _txt(note)
    return files


def training_files() -> dict[str, bytes]:
    """Synthetic training tender: the fixture cedant spec and filled workbook, EXPO_SYN, the two fixture quotes."""
    run = json.loads((FIX / "RUN_SYN" / "run_config.json").read_text(encoding="utf-8"))
    files = _common(TRAINING_NAME, "A complete synthetic tender for practice: every number is made up and the "
                                   "reinsurers are fictional. Run the four steps in order.")
    files["inputs/template_spec.json"] = (FIX / "C_ALPHA" / "template_spec.json").read_bytes()
    files["inputs/cedant_filled.xlsx"] = (FIX / "C_ALPHA" / "filled.xlsx").read_bytes()
    files["inputs/spec_builder.xlsx"] = (FIX / "C_ALPHA" / "spec_builder.xlsx").read_bytes()
    files["inputs/scorecard_weights.json"] = (REPO_DIR / "examples" / "scorecard_weights.json").read_bytes()
    e = FIX / "EXPO_SYN"
    for p in sorted([e / "dim_life.csv", e / "run_manifest.csv", *sorted((e / "maps").glob("*.csv"))]):
        files[f"exposure/{p.relative_to(e).as_posix()}"] = p.read_bytes()
    subs = []
    for s in run["submissions"]:
        oid = s["option_id"]
        files[f"submissions/{oid}.xlsx"] = (FIX / oid / "submission.xlsx").read_bytes()
        subs.append({"option_id": oid, "owner": s["owner"], "file": f"submissions/{oid}.xlsx",
                     "template_spec": "inputs/template_spec.json", "issued": "work/tender_template.xlsx"})
    for f in ("treaty_book_map.csv", "experience.csv"):
        files[f"treaty/{f}"] = (FIX / "RUN_SYN" / f).read_bytes()
    files["terms_scores.csv"] = (FIX / "RUN_SYN" / "terms_scores.csv").read_bytes()
    cfg = {**TEMPLATE_CONFIG, "run_id": "TRAINING",
           "exposure": {**TEMPLATE_CONFIG["exposure"], "snapshot_date": run["exposure"]["snapshot_date"]},
           "treaty": {**TEMPLATE_CONFIG["treaty"], "lapse": run["treaty"]["lapse"], "book_slots": run["treaty"]["book_slots"]},
           "v5": run["v5"], "submissions": subs,
           "scorecard": {**TEMPLATE_CONFIG["scorecard"], "panels": run["scorecard"]["panels"]}}
    files["run_config.json"] = _json(cfg)
    return files


def write_folder(dest: Path, training: bool = False, overwrite: bool = False) -> list[Path]:
    """Write a tender folder; refuses a non-empty destination unless overwrite."""
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()) and not overwrite:
        raise SpecError(f"{dest} exists and is not empty; choose a new folder name")
    out = []
    for rel, data in sorted((training_files() if training else template_files()).items()):
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        out.append(p)
    return out
