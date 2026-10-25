"""Laptop acceptance check (SPEC §13): run on the owner's laptop after every change, before the PR is merged.

    py tools\\laptop_check.py [--quick]

1. Environment: CPython 3.12 64-bit, Windows, every pin in requirements-native.txt installed at the pinned version.
2. Full test suite (tests/run_all.py).
3. End-to-end run of every CLI tool on the synthetic fixtures, in runs/laptop_check/<UTC stamp>/ (never committed),
   from a working directory that is NOT the repo (paths must resolve from the scripts' own location).
4. Path lengths under the repo and the run folder stay below the Windows 260-character limit.
Writes laptop_check_report.md + .json in the run folder and prints the .md path. Exit code 0 = all PASS.
The owner returns the report (or its summary line) to the session; the work order is not done until it is PASS.
Work orders that add a tool add its check to TOOL_CHECKS below (CLAUDE.md working method).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import struct
import subprocess
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
FIX = REPO / "fixtures"
PY = sys.executable
PW = [PY, str(HERE / "pw.py")]
MAX_PATH = 260


def _run(cmd, cwd, expect_rc=0, must_contain=None, timeout=900):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout)
    ok = r.returncode == expect_rc and (must_contain is None or must_contain in (r.stdout + r.stderr))
    lines = (r.stdout + r.stderr).strip().splitlines()
    keep = [ln for ln in lines if ln.startswith(("FAIL ", "E ")) or " passed, " in ln]
    tail = keep + lines[-6:]
    return ok, f"rc={r.returncode} ({time.time() - t:.1f}s)", tail


def tool_checks(run: Path):
    """(name, command, expected rc, text that must appear). Add one line per new tool / command."""
    a = FIX / "CAT_ALPHA" / "spec.json"
    e = FIX / "EXPO_SYN"
    tender = run / "tender.json"
    tender.write_text(json.dumps({"cedant": "FICTIONAL_CEDANT_A", "tender_id": "LAPTOP_CHECK", "deadline": "2026-11-05",
                                  "contact": "laptop check", "issue_date": "2026-10-24"}), encoding="utf-8")
    cells = run / "cells.csv"
    cells.write_text("cell_id,product_type,rating_region,tpa,plan,age,gender,copay_op_diag,nationality_group,maternity_eligible\n"
                     "1,INDIVIDUAL,RGN_A,TPA_RED,P2,33,F,10%,OTHER,N\n2,INDIVIDUAL,RGN_A,TPA_GREEN,P7,75,M,,OTHER,N\n",
                     encoding="utf-8")
    return [
        ("catalogue parse (all fixtures)", None, 0, None),
        ("evaluate with trace", PW + ["evaluate", str(a), str(cells), "--out", str(run / "prices.csv"), "--trace",
                                      str(run / "trace.csv")], 0, "PRICED"),
        ("gates v0 contract check", PW + ["gates", "v0", str(e / "dim_life.csv"), "--manifest", str(e / "run_manifest.csv")], 0, '"OK"'),
        ("gates v1 (all fixtures)", None, 0, None),
        ("gates v2 block consistency", PW + ["gates", "v2", str(FIX / "CAT_BETA" / "spec.json"), "--out", str(run / "v2.csv")], 0, "5 flagged"),
        ("exposure build strict (expects MappingRequired)", PW + ["exposure", "build", str(e / "dim_life.csv"), "--maps", str(e / "maps")],
         2, "MappingRequired"),
        ("exposure build + coverage", PW + ["exposure", "build", str(e / "dim_life.csv"), "--maps", str(e / "maps"), "--manifest",
                                            str(e / "run_manifest.csv"), "--catalogue", str(a), "--out", str(run / "exposure")], 0, "coverage PASS"),
        ("gates v3 premium reconciliation", PW + ["gates", "v3", str(a), str(e / "dim_life.csv"), "--maps", str(e / "maps"),
                                                  "--manifest", str(e / "run_manifest.csv"), "--out", str(run / "v3.csv")], 0, "TOTAL"),
        ("t generate --from-catalogue", PW + ["t", "generate", "--from-catalogue", str(a), "--tender", str(tender), "--out-spec",
                                              str(run / "template_spec.json"), "--out", str(run / "template.xlsx")], 0, "structure hash"),
        ("gates v4 round trip (fixture template)", PW + ["gates", "v4", str(FIX / "T_ALPHA" / "template_spec.json"), "--expiring", str(a),
                                                         "--workdir", str(run / "v4")], 0, "V4 PASS"),
        ("gates v4 round trip (cedant structure example)", PW + ["gates", "v4", str(REPO / "examples" / "ufic_2027" / "template_spec.json"),
                                                                 "--workdir", str(run / "v4_example")], 0, "V4 PASS"),
        ("t generate cedant structure example", PW + ["t", "generate", str(REPO / "examples" / "ufic_2027" / "template_spec.json"),
                                                      "--out", str(run / "example_template.xlsx")], 0, "structure hash"),
        ("t parse submission", PW + ["t", "parse", str(FIX / "SUB_X" / "submission.xlsx"), "--spec", str(FIX / "T_ALPHA" / "template_spec.json"),
                                     "--expiring", str(a), "--id", "SUB_X", "--owner", "Reinsurer X", "--out", str(run / "sub_x.json")],
         0, "hash_ok=True"),
        ("package release zip", [PY, str(HERE / "package.py"), "--out", str(run / "release.zip")], 0, "files"),
        # WS1: T ingest + V5, B1 / B2 / TreatyFeed on the synthetic run (runs root inside this check's run folder)
        ("t ingest SUB_X (V5)", PW + ["t", "ingest", str(FIX / "SUB_X" / "submission.xlsx"), "--spec",
                                     str(FIX / "T_ALPHA" / "template_spec.json"), "--issued", str(FIX / "T_ALPHA" / "template.xlsx"),
                                     "--run", str(FIX / "RUN_SYN" / "run_config.json"), "--id", "SUB_X", "--owner", "Reinsurer X",
                                     "--runs-root", str(run / "runs")], 0, "V5 PASS"),
        ("t ingest SUB_Y (V5)", PW + ["t", "ingest", str(FIX / "SUB_Y" / "submission.xlsx"), "--spec",
                                     str(FIX / "T_ALPHA" / "template_spec.json"), "--issued", str(FIX / "T_ALPHA" / "template.xlsx"),
                                     "--run", str(FIX / "RUN_SYN" / "run_config.json"), "--id", "SUB_Y", "--owner", "Reinsurer Y",
                                     "--runs-root", str(run / "runs")], 0, "V5 PASS"),
        ("index (B1 + B2 + TreatyFeed)", PW + ["index", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(run / "runs")],
         0, "coverage PASS"),
        ("benefit (B1 level 1)", PW + ["benefit", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(run / "runs")],
         0, "BenefitFactors"),
        # WS2: market benchmark (fictional SME intake files + CAT_GAMMA / CAT_IPMI vs the expiring and the options)
        ("benchmark (A: value map, gap register)", PW + ["benchmark", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root",
                                                         str(run / "runs")], 0, "market catalogues"),
        # WS3: scorecard on the same run (needs the index outputs above)
        ("score (D scorecard + pack)", PW + ["score", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(run / "runs")],
         0, "recommendation pack"),
        # WS5: cedant rate workbook (SPEC §8.5): generate, gated read-back (stop on blanks, PASS when filled), reinsurer
        # template from the read-back catalogue, and the cedant example's cedant workbook
        ("t cedant (fixture spec)", PW + ["t", "cedant", str(FIX / "C_ALPHA" / "template_spec.json"), "--out",
                                          str(run / "cedant.xlsx")], 0, "structure hash"),
        ("t cedant-read unfilled (expects the gate to stop)", PW + ["t", "cedant-read", str(run / "cedant.xlsx"), "--spec",
                                                                    str(FIX / "C_ALPHA" / "template_spec.json"), "--out",
                                                                    str(run / "cedant_empty" / "expiring.json")],
         2, "blank mandatory rate"),
        ("t cedant-read filled fixture", PW + ["t", "cedant-read", str(FIX / "C_ALPHA" / "filled.xlsx"), "--spec",
                                               str(FIX / "C_ALPHA" / "template_spec.json"), "--out",
                                               str(run / "cedant_read" / "expiring.json")], 0, "CEDANT READ PASS"),
        ("t generate from the read-back", PW + ["t", "generate", str(FIX / "C_ALPHA" / "template_spec.json"), "--expiring",
                                                str(run / "cedant_read" / "expiring.json"), "--out",
                                                str(run / "template_from_readback.xlsx")], 0, "structure hash"),
        ("t cedant cedant structure example", PW + ["t", "cedant", str(REPO / "examples" / "ufic_2027" / "template_spec.json"),
                                                    "--out", str(run / "example_cedant.xlsx")], 0, "structure hash"),
    ]


def excel_open(paths) -> tuple[bool, str]:
    """Open each workbook read-only in Microsoft Excel (COM, invisible, via PowerShell): the WS5 acceptance 'opens in
    Excel'. A workbook Excel would repair or cannot open fails the check."""
    lines = ["$ErrorActionPreference = 'Stop'", "$x = New-Object -ComObject Excel.Application",
             "$x.Visible = $false", "$x.DisplayAlerts = $false", "try {"]
    for p in paths:
        q = str(p).replace("'", "''")
        lines += [f"  $wb = $x.Workbooks.Open('{q}', 0, $true)", f"  Write-Output ('OPEN ' + $wb.Worksheets.Count + ' {Path(p).name}')",
                  "  $wb.Close($false)"]
    lines += ["} finally { $x.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($x) }"]
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "\n".join(lines)],
                           capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return False, f"Excel automation unavailable ({ex!r}): open the workbooks in the run folder by hand"
    opened = [ln for ln in r.stdout.splitlines() if ln.startswith("OPEN ")]
    ok = r.returncode == 0 and len(opened) == len(paths)
    return ok, ("; ".join(opened) if ok else (r.stderr.strip().splitlines() or ["Excel did not open every workbook"])[-1])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the full test suite (tool checks only)")
    a = ap.parse_args(argv)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = REPO / "runs" / "laptop_check" / stamp
    run.mkdir(parents=True, exist_ok=True)
    cwd = Path(tempfile.gettempdir())          # deliberately not the repo
    results = []

    def add(name, ok, detail, tail=None):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail, "tail": tail or []})
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")

    # 1. environment
    is_win = platform.system() == "Windows"
    add("python 3.12 64-bit", sys.version_info[:2] == (3, 12) and struct.calcsize("P") == 8,
        f"{platform.python_version()} {struct.calcsize('P') * 8}-bit {platform.system()} {platform.release()}")
    if not is_win:
        add("windows host", False, f"running on {platform.system()}: this check is meant for the owner's Windows laptop")
    for line in (REPO / "requirements-native.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, ver = line.split("==")
        try:
            got = metadata.version(name)
        except metadata.PackageNotFoundError:
            got = None
        add(f"pin {name}", got == ver, f"installed {got}, pinned {ver}")
    # 2. test suite
    if not a.quick:
        ok, det, tail = _run([PY, str(REPO / "tests" / "run_all.py"), "-q"], cwd, timeout=3600)
        add("test suite", ok, det, tail)
    # 3. tools
    for name, cmd, rc, text in tool_checks(run):
        if name == "catalogue parse (all fixtures)":
            outs = [_run(PW + ["catalogue", "parse", str(FIX / c / "spec.json"), "--out", str(run / f"{c}.json")], cwd)
                    for c in ("CAT_ALPHA", "CAT_BETA", "CAT_GAMMA", "CAT_DELTA", "CAT_RETIREE", "CAT_IPMI")]
            add(name, all(o[0] for o in outs), "; ".join(o[1] for o in outs), [t for o in outs for t in o[2]][-6:])
            continue
        if name == "gates v1 (all fixtures)":
            outs = [_run(PW + ["gates", "v1", str(FIX / c / "spec.json")], cwd, must_contain="V1 PASS")
                    for c in ("CAT_ALPHA", "CAT_BETA", "CAT_GAMMA", "CAT_DELTA", "CAT_RETIREE", "CAT_IPMI")]
            add(name, all(o[0] for o in outs), "; ".join(o[1] for o in outs), [t for o in outs for t in o[2]][-6:])
            continue
        ok, det, tail = _run(cmd, cwd, expect_rc=rc, must_contain=text)
        add(name, ok, det, tail)
    # generated workbooks open with openpyxl
    try:
        from openpyxl import load_workbook
        for f in ("template.xlsx", "example_template.xlsx", "cedant.xlsx", "example_cedant.xlsx", "template_from_readback.xlsx",
                  "runs/RUN_SYN/out/RateIndex.xlsx",
                  "runs/RUN_SYN/out/TreatyFeed.xlsx", "runs/RUN_SYN/out/Recommendation_Pack_RUN_SYN.xlsx", "runs/RUN_SYN/out/ValueMap.xlsx"):
            load_workbook(run / f).close()
        add("generated workbooks open", True, "openpyxl load ok")
    except Exception as ex:  # noqa: BLE001
        add("generated workbooks open", False, repr(ex))
    # WS5 acceptance: both cedant-example workbooks (cedant mode and reinsurer mode) open in Excel itself
    if is_win:
        ok, det = excel_open([run / "example_cedant.xlsx", run / "example_template.xlsx", run / "cedant.xlsx"])
        add("workbooks open in Excel (cedant example: cedant + reinsurer; fixture cedant)", ok, det)
    # 4. path lengths
    longest = max((len(str(p)) for root in (REPO, run) for p in root.rglob("*")), default=0)
    add("path length < 260", longest < MAX_PATH, f"longest {longest} chars")

    try:
        commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        branch = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = branch = ""
    if not commit and (REPO / "COMMIT.txt").exists():      # package copied without git history
        commit, branch = (REPO / "COMMIT.txt").read_text(encoding="utf-8").strip(), "package"
    commit, branch = commit or "unknown", branch or "unknown"
    n_fail = sum(r["status"] == "FAIL" for r in results)
    summary = (f"LAPTOP CHECK {'PASS' if not n_fail else 'FAIL'}: {len(results) - n_fail}/{len(results)} checks, "
               f"branch {branch} @ {commit}, {stamp}")
    rep = {"summary": summary, "branch": branch, "commit": commit, "stamp": stamp, "python": platform.python_version(),
           "platform": platform.platform(), "results": results}
    (run / "laptop_check_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    md = [f"# {summary}", "", "| Check | Status | Detail |", "|---|---|---|"]
    md += [f"| {r['check']} | {r['status']} | {r['detail']} |" for r in results]
    fails = [r for r in results if r["status"] == "FAIL"]
    if fails:
        md += ["", "## Failure output (last lines)"]
        for r in fails:
            md += ["", f"### {r['check']}", "```", *r["tail"], "```"]
    (run / "laptop_check_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n{summary}\nreport: {run / 'laptop_check_report.md'}")
    return 0 if not n_fail else 1


if __name__ == "__main__":
    sys.exit(main())
