"""Laptop acceptance check (SPEC §13): run on the owner's laptop after every change, before the PR is merged.

    py tools\\laptop_check.py [--quick] [--console <file>]

One check at a time (WS8): a lock in runs/laptop_check/RUNNING.lock; a second start exits 3 (a lock older than
LOCK_STALE_HOURS is stale). Every result line is printed as it is found and, with --console, appended to that file
(RUN_LAPTOP_CHECK.bat writes laptop_check_console.txt beside itself this way, so the window is never blank).

1. Environment: CPython 3.12 64-bit, Windows, every pin in requirements-native.txt installed at the pinned version.
2. Full test suite (tests/run_all.py).
3. End-to-end run of every CLI tool on the synthetic fixtures, in runs/laptop_check/<UTC stamp>/ (never committed),
   from a working directory that is NOT the repo (paths must resolve from the scripts' own location).
4. Path lengths under the repo and the run folder stay below the Windows 260-character limit.
5. WS4 release gate: the end-to-end `run` on the fixtures, twice; the second run must be byte-identical.
Run from an installed release zip (RELEASE.json at the root, no .git) the check also verifies that the release ships no
reference/ or client example, and reports the repo-only cedant-example checks as SKIP (not FAIL).
Writes laptop_check_report.md + .json in the run folder and prints the .md path. Exit code 0 = all PASS.
The owner returns the report (or its summary line) to the session; the work order is not done until it is PASS.
Work orders that add a tool add its check to TOOL_CHECKS below (CLAUDE.md working method).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
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
LOCK_PATH = REPO / "runs" / "laptop_check" / "RUNNING.lock"     # tests point this elsewhere
LOCK_STALE_HOURS = 3
EXIT_LOCKED = 3
_CONSOLE: list = []                         # [Path] when --console is given


def say(msg: str = "", progress: bool = False):
    """Print now (flushed); results also go to the console file. progress=True: screen only."""
    print(msg, flush=True)
    if _CONSOLE and not progress:
        with _CONSOLE[0].open("a", encoding="utf-8") as f:
            f.write(msg + "\n")


def acquire_lock(lock: Path) -> str | None:
    """Create the lock (exclusive). Returns None when acquired, else a message describing the running check."""
    import os
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age_h = (time.time() - lock.stat().st_mtime) / 3600
                info = lock.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if age_h > LOCK_STALE_HOURS:
                try:
                    lock.unlink()
                except OSError:
                    pass
                continue
            return (f"Another laptop check is already running ({info}, {age_h * 60:.0f} min ago). Let it finish "
                    f"(close this window), or, if no other check window is open, delete {lock} and start again.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(f"started {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} pid {os.getpid()}\n")
        return None
    return f"Could not create the lock {lock}"


def _run(cmd, cwd, expect_rc=0, must_contain=None, timeout=900):
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout)
    ok = r.returncode == expect_rc and (must_contain is None or must_contain in (r.stdout + r.stderr))
    lines = (r.stdout + r.stderr).strip().splitlines()
    keep = [ln for ln in lines if ln.startswith(("FAIL ", "E ")) or " passed, " in ln]
    tail = keep + lines[-6:]
    return ok, f"rc={r.returncode} ({time.time() - t:.1f}s)", tail


def step_commands(tender: Path) -> list[list[str]]:
    """The pw.py arguments of each step file in a tender folder, read from the .bat itself (WS8)."""
    out = []
    for bat in sorted(tender.glob("[1-4]_*.bat")):
        for ln in bat.read_text(encoding="ascii").splitlines():
            if ln.startswith('%PY% "%PWDIR%\\tools\\pw.py" '):
                # the .bat holds Windows separators; os.sep is "\\" on Windows (no change) and "/" elsewhere
                out.append([x.replace("\\", os.sep) for x in ln.split(" ", 2)[2].split()])
    return out


def spec_step_commands(tender: Path) -> list[list[str]]:
    """WS9: the pw.py arguments of the optional Spec Builder step files 0a / 0b (read from the .bat files)."""
    out = []
    for bat in sorted(tender.glob("0[ab]_*.bat")):
        for ln in bat.read_text(encoding="ascii").splitlines():
            if ln.startswith('%PY% "%PWDIR%\\tools\\pw.py" '):
                out.append([x.replace("\\", os.sep) for x in ln.split(" ", 2)[2].split()])
    return out


def tender_checks(run: Path):
    """WS8: tender new (blank, training) and the training tender's four steps, run from the tender folder as the
    step files run them (commands read from the .bat files)."""
    t = run / "tenders" / "TRAINING"
    checks = [("tender new (blank folder)", PW + ["tender", "new", str(run / "tenders" / "NEW_TENDER")], 0, "blank tender folder"),
              ("tender new --training", PW + ["tender", "new", str(t), "--training"], 0, "training tender")]
    # WS9: steps 0a / 0b on the training tender first; 0b rewrites inputs\template_spec.json, which steps 1-4 then use
    checks.append(("training tender step 0a spec builder", ("SPECSTEP", 0), 0, "Spec Builder", t))
    checks.append(("training tender step 0b spec read-back", ("SPECSTEP", 1), 0, "SPEC READ PASS", t))
    for i, (name, text) in enumerate(zip(("step 1 cedant workbook", "step 2 cedant read-back", "step 3 tender template",
                                          "step 4 evaluation"), ("structure hash", "CEDANT READ PASS", "structure hash",
                                                                 "RUN COMPLETE"))):
        checks.append((f"training tender {name}", ("STEP", i), 0, text, t))
    return checks


def tool_checks(run: Path):
    """(name, command, expected rc, text that must appear[, cwd]). Add one line per new tool / command."""
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
        ("gates v0 contract check, Merit v7.5.0 (IP4-9, CR #25)", PW + ["gates", "v0", str(e / "dim_life.csv"), "--version", "IP4-9"],
         0, '"OK"'),
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
        # WS4: the end-to-end run (release gate), twice into separate run roots; the second must be byte-identical
        ("run end to end (fixtures)", PW + ["run", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(run / "e2e1"),
                                            "--hashes", str(run / "e2e1_hashes.json")], 0, "RUN COMPLETE"),
        ("run again (second run)", PW + ["run", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(run / "e2e2"),
                                         "--hashes", str(run / "e2e2_hashes.json")], 0, "RUN COMPLETE"),
        # WS9: Spec Builder (SPEC §8.6): pre-filled and blank builders, gated read-back to an unchanged spec, the
        # cedant example's builder
        ("t spec-builder (fixture spec)", PW + ["t", "spec-builder", str(FIX / "C_ALPHA" / "template_spec.json"), "--out",
                                                str(run / "spec_builder.xlsx")], 0, "Spec Builder"),
        ("t spec-builder blank", PW + ["t", "spec-builder", "--out", str(run / "spec_builder_blank.xlsx")], 0, "blank"),
        ("t spec-read (fixture builder)", PW + ["t", "spec-read", str(run / "spec_builder.xlsx"), "--base",
                                                str(FIX / "C_ALPHA" / "template_spec.json"), "--out",
                                                str(run / "spec_read" / "template_spec.json")], 0, "SPEC READ PASS"),
        ("t spec-read blank builder (expects the gate to stop)", PW + ["t", "spec-read", str(run / "spec_builder_blank.xlsx"),
                                                                       "--out", str(run / "spec_blank" / "template_spec.json")],
         2, "SPEC READ FAIL"),
        ("t spec-builder cedant structure example", PW + ["t", "spec-builder", str(REPO / "examples" / "ufic_2027" / "template_spec.json"),
                                                          "--out", str(run / "example_spec_builder.xlsx")], 0, "Spec Builder"),
        *tender_checks(run),
    ]


def needs_example(cmd) -> bool:
    """Checks on the structure-only cedant example: repo only, the release zip does not ship it (CLAUDE.md)."""
    return cmd is not None and any("ufic_2027" in str(x) for x in cmd)


def release_info() -> dict | None:
    """RELEASE.json written by tools/package.py; None in a repo clone."""
    p = REPO / "RELEASE.json"
    if p.exists() and not (REPO / ".git").exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


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
    ap.add_argument("--console", help="also append every result line to this file (started empty)")
    a = ap.parse_args(argv)
    lock = LOCK_PATH
    busy = acquire_lock(lock)
    if busy:                         # screen only: the running check owns the console file
        print(busy, flush=True)
        return EXIT_LOCKED
    if a.console:
        _CONSOLE[:] = [Path(a.console)]
        _CONSOLE[0].write_text("", encoding="utf-8")
    try:
        return _main(a)
    finally:
        try:
            lock.unlink()
        except OSError:
            pass


def _main(a):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = REPO / "runs" / "laptop_check" / stamp
    run.mkdir(parents=True, exist_ok=True)
    cwd = Path(tempfile.gettempdir())          # deliberately not the repo
    results = []

    def add(name, ok, detail, tail=None, status=None):
        st = status or ("PASS" if ok else "FAIL")
        results.append({"check": name, "status": st, "detail": detail, "tail": tail or []})
        say(f"{st}  {name}  {detail}")

    rel = release_info()
    if rel is not None:
        import re                                # tools/pw.py shadows the pw package here: read the version as text
        m = re.search(r'__version__ = "([^"]+)"', (REPO / "pw" / "__init__.py").read_text(encoding="utf-8"))
        __version__ = m.group(1) if m else None
        shipped = [x for x in ("reference", "examples/ufic_2027", "runs/RUN_SYN") if (REPO / x).exists()]
        add("installed release contents", not shipped and rel.get("version") == __version__,
            f"release {rel.get('version')} @ {rel.get('commit')} (pw {__version__}); "
            + (f"must not ship: {shipped}" if shipped else "no reference/ or client example"))
        kits = {k: (len(step_commands(REPO.parent / k)), len(spec_step_commands(REPO.parent / k)))
                for k in ("TENDER_TEMPLATE", "TRAINING_TENDER")}
        guide = REPO.parent / "USER_GUIDE.html"
        add("release tender folders and user guide beside the tool", all(v == (4, 2) for v in kits.values()) and guide.exists(),
            ", ".join(f"{k}: {v[0]} step files + {v[1]} Spec Builder steps" for k, v in kits.items())
            + f"; USER_GUIDE.html {'present' if guide.exists() else 'MISSING'}")

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
        say("....  test suite (the longest step: 10 to 25 minutes on a laptop)", progress=True)
        ok, det, tail = _run([PY, str(REPO / "tests" / "run_all.py"), "-q"], cwd, timeout=3600)
        add("test suite", ok, det, tail)
    # 3. tools
    for name, cmd, rc, text, *ccwd in tool_checks(run):
        ccwd = ccwd[0] if ccwd else cwd
        if isinstance(cmd, tuple) and cmd[0] == "SPECSTEP":       # a training tender Spec Builder step (WS9)
            steps = spec_step_commands(ccwd) if ccwd.exists() else []
            if len(steps) != 2:
                add(name, False, f"{len(steps)} Spec Builder step file command(s) found in {ccwd}")
                continue
            cmd = PW + steps[cmd[1]]
        if isinstance(cmd, tuple) and cmd[0] == "STEP":           # a training tender step file's command
            steps = step_commands(ccwd) if ccwd.exists() else []
            if len(steps) != 4:
                add(name, False, f"{len(steps)} step file command(s) found in {ccwd}")
                continue
            cmd = PW + steps[cmd[1]]
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
        if rel is not None and needs_example(cmd) and not (REPO / "examples" / "ufic_2027").exists():
            add(name, True, "not in the release (repo-only cedant example)", status="SKIP")
            continue
        say(f"....  {name}", progress=True)
        ok, det, tail = _run(cmd, ccwd, expect_rc=rc, must_contain=text)
        add(name, ok, det, tail)
    # WS4 acceptance: the second end-to-end run reproduces every output byte for byte
    try:
        h1 = json.loads((run / "e2e1_hashes.json").read_text(encoding="utf-8"))
        h2 = json.loads((run / "e2e2_hashes.json").read_text(encoding="utf-8"))
        diff = sorted(k for k in set(h1) | set(h2) if h1.get(k) != h2.get(k))
        add("run byte-identical on a second run", bool(h1) and not diff,
            f"{len(h1)} files identical" if not diff else f"{len(diff)} differ: {diff[:5]}")
    except (OSError, ValueError) as ex:
        add("run byte-identical on a second run", False, repr(ex))
    # WS9 acceptance: the read-back of an unchanged builder is the same spec; step 0b leaves the training spec unchanged
    try:
        same = []
        for got, want in ((run / "spec_read" / "template_spec.json", FIX / "C_ALPHA" / "template_spec.json"),
                          (run / "tenders" / "TRAINING" / "inputs" / "template_spec.json",
                           run / "tenders" / "TRAINING" / "inputs" / "template_spec.previous.json")):
            same.append(json.loads(got.read_text(encoding="utf-8")) == json.loads(want.read_text(encoding="utf-8")))
        add("spec builder round trip gives the same spec", all(same), "fixture read-back and training step 0b: "
            + ", ".join("same" if x else "DIFFERENT" for x in same))
    except (OSError, ValueError) as ex:
        add("spec builder round trip gives the same spec", False, repr(ex))
    # generated workbooks open with openpyxl
    try:
        from openpyxl import load_workbook
        for f in ("template.xlsx", "example_template.xlsx", "cedant.xlsx", "example_cedant.xlsx", "template_from_readback.xlsx",
                  "spec_builder.xlsx", "spec_builder_blank.xlsx", "example_spec_builder.xlsx", "tenders/TRAINING/work/spec_builder.xlsx",
                  "runs/RUN_SYN/out/RateIndex.xlsx",
                  "runs/RUN_SYN/out/TreatyFeed.xlsx", "runs/RUN_SYN/out/Recommendation_Pack_RUN_SYN.xlsx", "runs/RUN_SYN/out/ValueMap.xlsx",
                  "e2e1/RUN_SYN/out/TreatyFeed.xlsx", "e2e1/RUN_SYN/out/OptionTerms.xlsx",
                  "e2e1/RUN_SYN/out/Recommendation_Pack_RUN_SYN.xlsx", "tenders/TRAINING/work/tender_template.xlsx",
                  "tenders/TRAINING/runs/TRAINING/out/RateIndex.xlsx",
                  "tenders/TRAINING/runs/TRAINING/out/Recommendation_Pack_TRAINING.xlsx"):
            if f.startswith("example_") and rel is not None and not (run / f).exists():
                continue                                     # repo-only example, skipped above
            load_workbook(run / f).close()
        add("generated workbooks open", True, "openpyxl load ok")
    except Exception as ex:  # noqa: BLE001
        add("generated workbooks open", False, repr(ex))
    # WS5 acceptance: both cedant-example workbooks (cedant mode and reinsurer mode) open in Excel itself
    if is_win:
        books = [run / "example_cedant.xlsx", run / "example_template.xlsx", run / "cedant.xlsx", run / "spec_builder.xlsx",
                 run / "example_spec_builder.xlsx",
                 run / "e2e1" / "RUN_SYN" / "out" / "Recommendation_Pack_RUN_SYN.xlsx",
                 run / "e2e1" / "RUN_SYN" / "out" / "TreatyFeed.xlsx"]
        ok, det = excel_open([b for b in books if b.exists() or not b.name.startswith("example_")])
        add("workbooks open in Excel (cedant example when shipped; fixture cedant; run pack and TreatyFeed)", ok, det)
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
    if rel is not None:
        commit, branch = rel.get("commit") or commit, f"release {rel.get('version')}"
    n_fail = sum(r["status"] == "FAIL" for r in results)
    n_skip = sum(r["status"] == "SKIP" for r in results)
    n_run = len(results) - n_skip
    summary = (f"LAPTOP CHECK {'PASS' if not n_fail else 'FAIL'}: {n_run - n_fail}/{n_run} checks"
               + (f" ({n_skip} skipped: not in release)" if n_skip else "") + f", branch {branch} @ {commit}, {stamp}")
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
    say(f"\n{summary}\nreport: {run / 'laptop_check_report.md'}")
    return 0 if not n_fail else 1


if __name__ == "__main__":
    sys.exit(main())
