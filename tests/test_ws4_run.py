"""WS4: the end-to-end run (`pw run`): every gate in the manifest, byte-identical on a second run, gate stops recorded,
the run clears only what it generates; the treaty-tool feed contract check."""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from _util import FIX, REPO, tmpdir

from pw.pipeline import GENERATED, output_hashes, run_all
from pw.rate_index import load_run_config
from pw.treaty_contract import check_treaty_outputs

CFG = FIX / "RUN_SYN" / "run_config.json"
_KEEP = Path(__file__).resolve().parent.parent / "runs" / "_ws4_test"      # never committed (runs/)


def _cfg(**over):
    c = load_run_config(CFG)
    c.update(over)
    return c


@lru_cache(maxsize=None)
def _two_runs():
    """Two full runs into separate roots: in-process, and through the CLI from another working directory (kept for the
    module's tests, removed by the last one). Returns (result of run 1, run 2 folder, run 2 hashes, CLI output)."""
    import shutil
    shutil.rmtree(_KEEP, ignore_errors=True)
    r1 = run_all(_cfg(), _KEEP / "a", log=lambda *_: None)
    cmd = [sys.executable, str(REPO / "tools" / "pw.py"), "run", str(CFG), "--runs-root", str(_KEEP / "b"),
           "--hashes", str(_KEEP / "b_hashes.json")]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO / "docs"))
    h2 = json.loads((_KEEP / "b_hashes.json").read_text(encoding="utf-8")) if p.returncode == 0 else {}
    return r1, _KEEP / "b" / "RUN_SYN", h2, p


def test_run_end_to_end_every_gate_in_manifest():
    r1 = _two_runs()[0]
    assert r1["status"] == "COMPLETE", r1.get("error")
    m = json.loads((r1["dir"] / "run_manifest.json").read_text(encoding="utf-8"))
    g = m["gates"]
    for k in ("V0", "V1", "V2", "V3", "V4", "V5", "COVERAGE", "TREATY_CONTRACT"):
        assert k in g, k
    assert g["V0"]["status"] == "OK" and g["COVERAGE"]["status"] == "PASS" and g["V3"]["status"] == "REPORTED"
    assert set(g["V1"]) == {"CAT_ALPHA", "CAT_BETA", "CAT_DELTA", "CAT_GAMMA", "CAT_IPMI", "CAT_RETIREE"}
    assert all(v["status"] == "PASS" for v in g["V1"].values())
    assert set(g["V5"]) == {"SUB_X", "SUB_Y"} and g["V4"]["T_ALPHA_2027"]["status"] == "PASS"
    assert m["run"]["status"] == "COMPLETE" and len(m["run"]["steps"]) == 9
    assert m["versions"]["pricing_workbench"] and m["versions"]["treatymodel_target"].startswith("treatymodel")
    files = m["inputs"]["files"]
    assert "run_config.json" in files and "../SUB_X/submission.xlsx" in files and "../CAT_ALPHA/source.xlsx" in files
    assert "../EXPO_SYN/maps/plan_map.csv" in files
    for t in ("RateFactors", "RateIndex", "BenefitDiff", "BenefitFactors", "TreatyFeed", "OptionTerms", "ValueMap",
              "GapRegister", "ScoreInputs", "Scorecard", "Ranking"):
        assert (r1["dir"] / "out" / f"{t}.parquet").exists(), t
    assert (r1["dir"] / "out" / "Recommendation_Pack_RUN_SYN.xlsx").exists()
    for f in ("V2_block_consistency.csv", "V3_premium_reconciliation.csv", "coverage_by_status.csv"):
        assert (r1["dir"] / "gates" / f).exists(), f
    txt = (r1["dir"] / "run_manifest.json").read_text(encoding="utf-8")
    assert str(REPO) not in txt and str(_KEEP) not in txt                  # no machine paths: portable, reproducible


def test_second_run_is_byte_identical():
    r1, d2, h2, p = _two_runs()
    assert p.returncode == 0 and "RUN COMPLETE" in p.stdout, p.stdout + p.stderr
    h1 = output_hashes(r1["dir"])
    assert len(h1) > 40 and h1 == h2 == output_hashes(d2)


def test_run_clears_only_what_it_generates():
    with tmpdir() as d:
        rd = d / "RUN_SYN"
        (rd / "options" / "STALE").mkdir(parents=True)
        (rd / "options.json").write_text(json.dumps({"STALE": {"catalogue": "options/STALE/catalogue.json"}}), encoding="utf-8")
        (rd / "out").mkdir()
        (rd / "out" / "Old.parquet").write_text("x", encoding="utf-8")
        (rd / "expiring.json").write_text("{}", encoding="utf-8")              # e.g. a cedant read-back: not the run's
        r = run_all(_cfg(gates={"coverage_threshold": 0.999}), d, log=lambda *_: None)   # stops early, after the clean
        assert r["status"] == "STOPPED"
        assert not (rd / "options.json").exists() and not (rd / "options").exists() and not (rd / "out").exists()
        assert (rd / "expiring.json").read_text(encoding="utf-8") == "{}"


def test_coverage_gate_stops_the_run_and_is_recorded():
    with tmpdir() as d:
        c = _cfg(gates={"coverage_threshold": 0.999})
        r = run_all(c, d, log=lambda *_: None)
        assert r["status"] == "STOPPED"
        m = json.loads((d / "RUN_SYN" / "run_manifest.json").read_text(encoding="utf-8"))
        assert m["run"]["status"] == "STOPPED" and m["run"]["error"].startswith("GateFailed: COVERAGE")
        assert m["gates"]["COVERAGE"]["status"] == "FAIL" and m["gates"]["V0"]["status"] == "OK"
        assert "V5" not in m["gates"] and not (d / "RUN_SYN" / "out").exists() and not (d / "RUN_SYN" / "options.json").exists()
        # the CLI exits 2 on a stopped run (config with absolute paths, written outside the fixtures)
        base = FIX / "RUN_SYN"
        cfg = {"run_id": "RUN_STOP", "expiring": str((base / c["expiring"]).resolve()),
               "exposure": {k: (str((base / v).resolve()) if k in ("dim_life", "maps", "manifest") else v)
                            for k, v in c["exposure"].items()},
               "gates": {"coverage_threshold": 0.999}}
        (d / "stop.json").write_text(json.dumps(cfg), encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "pw.py"), "run", str(d / "stop.json"), "--runs-root", str(d)],
                           capture_output=True, text=True, cwd=str(REPO / "docs"))
        assert p.returncode == 2 and "RUN STOPPED" in p.stdout, p.stdout + p.stderr


def test_v1_failure_stops_the_run():
    """The pipeline's handling of a V1 failure (V1 itself is tested in test_gates.py): stop, record, detail file."""
    import pw.gates as gates
    real = gates.v1_source_reproduction

    def failing(cat, src, raise_on_fail=True):
        r = real(cat, src, raise_on_fail=False)
        if cat.catalogue_id == "CAT_BETA":
            r = {**r, "status": "FAIL", "failures": [{"problem": "planted", "cell": "B5"}]}
        return r
    gates.v1_source_reproduction = failing
    try:
        with tmpdir() as d:
            r = run_all(_cfg(), d, log=lambda *_: None)
            assert r["status"] == "STOPPED" and r["manifest"]["run"]["error"].startswith("GateFailed: V1"), r["gates"]
            assert r["gates"]["V1"]["CAT_BETA"] == {"status": "FAIL", "role": "listed", "checked": r["gates"]["V1"]["CAT_BETA"]["checked"],
                                                    "source_cells": r["gates"]["V1"]["CAT_BETA"]["source_cells"], "failures": 1}
            assert (d / "RUN_SYN" / "gates" / "V1_CAT_BETA.csv").exists()
            assert "COVERAGE" not in r["gates"] and not (d / "RUN_SYN" / "out").exists()
    finally:
        gates.v1_source_reproduction = real


def test_treaty_feed_contract_check():
    import shutil
    r1 = _two_runs()[0]
    out = r1["dir"] / "out"
    ok = check_treaty_outputs(out)
    assert ok["status"] == "PASS" and ok["treatymodel_target"].startswith("treatymodel"), ok
    from pw.outputs import write_table
    with tmpdir() as d:
        for f in out.glob("*"):
            shutil.copy(f, d / f.name)
        tf = pd.read_parquet(d / "TreatyFeed.parquet")
        bad = tf.copy()
        bad.loc[0, "premium_change_pct"] = float("nan")
        write_table("TreatyFeed", bad, d, contract=False)
        r = check_treaty_outputs(d)
        assert r["status"] == "FAIL" and any("premium_change_pct" in p for p in r["problems"])
        write_table("TreatyFeed", tf.drop(columns=["basis_note"]), d, contract=False)
        assert any("columns" in p for p in check_treaty_outputs(d)["problems"])
        write_table("TreatyFeed", pd.concat([tf, tf.head(1)], ignore_index=True), d, contract=False)
        assert any("duplicate key" in p for p in check_treaty_outputs(d)["problems"])
        write_table("TreatyFeed", tf, d, contract=False)
        (d / "OptionTerms.xlsx").unlink()
        assert any("Excel view" in p for p in check_treaty_outputs(d)["problems"])



def test_treaty_scenarios_unit_and_gates():
    """CR #23: TreatyFeed in the treaty tool's config schema (fractions, per-book volume / lr_adj by slot)."""
    from _util import raises
    from pw import MappingRequired, ProposalRequired, SpecError
    from pw.rate_index import treaty_scenarios
    tf = pd.DataFrame({"option_id": ["B", "A", "A"], "treaty_book": ["K1", "K2", "K1"],
                       "premium_change_pct": [3.0, -2.5, 10.0], "lr_adjustment_pts": [-1.5, 2.0, -6.25]})
    d = treaty_scenarios(tf, {"K1": 3, "K2": 1})
    assert [x["name"] for x in d["scenarios"]] == ["A", "B"]
    a = d["scenarios"][0]
    assert a["prem_chg"] == 0.0 and a["lr_chg"] == 0.0 and "ri" not in a
    assert a["books"]["volume"] == [0.975, 1.0, 1.1, 1.0, 1.0, 1.0, 1.0, 1.0]
    assert a["books"]["lr_adj"] == [0.02, 0.0, -0.0625, 0.0, 0.0, 0.0, 0.0, 0.0]
    assert d["scenarios"][1]["books"]["volume"][2] == 1.03 and d["scenarios"][1]["books"]["lr_adj"][0] == 0.0
    raises(ProposalRequired, treaty_scenarios, tf, None)
    raises(MappingRequired, treaty_scenarios, tf, {"K1": 1})
    raises(SpecError, treaty_scenarios, tf, {"K1": 1, "K2": 1})
    raises(SpecError, treaty_scenarios, tf, {"K1": 1, "K2": 9})
    raises(SpecError, treaty_scenarios, tf, {"K1": 1, "K2": "2"})


def test_treaty_scenarios_reproduce_the_asif_in_the_tool_engine():
    """The tool's engine: premium = experience x volume x (1 + prem_chg); claims = premium x (LR + lr_adj + lr_chg).
    With the run's TreatyScenarios the tool's premium is experience x rate factor x (1 - lapse) and its claims are
    experience claims x (1 - lapse): the workbench as-if."""
    r1 = _two_runs()[0]
    out = r1["dir"] / "out"
    tf = pd.read_parquet(out / "TreatyFeed.parquet")
    ts = json.loads((out / "TreatyScenarios.json").read_text(encoding="utf-8"))
    xp = pd.read_csv(FIX / "RUN_SYN" / "experience.csv").set_index("treaty_book")
    slots = ts["meta"]["book_slots"]
    assert slots == {"BOOK_IND_GREEN": 1, "BOOK_IND_OTHER": 2} and len(ts["scenarios"]) == tf["option_id"].nunique()
    for r in tf.itertuples(index=False):
        sc = next(x for x in ts["scenarios"] if x["name"] == r.option_id)
        i = slots[r.treaty_book] - 1
        vol, adj = sc["books"]["volume"][i], sc["books"]["lr_adj"][i]
        prem, clm = float(xp.loc[r.treaty_book, "earned_prem"]), float(xp.loc[r.treaty_book, "ultimate_claims"])
        tool_prem = prem * vol * (1 + sc["prem_chg"])
        tool_clm = tool_prem * (clm / prem + adj + sc["lr_chg"])
        assert abs(tool_prem - prem * r.rate_factor * (1 - r.lapse)) < 1e-6 * prem
        assert abs(tool_clm - clm * (1 - r.lapse)) < 1e-6 * clm
    m = json.loads((r1["dir"] / "run_manifest.json").read_text(encoding="utf-8"))
    assert m["outputs"]["TreatyScenarios"]["scenarios"] == 2 and m["gates"]["TREATY_CONTRACT"]["treatymodel_verified"]


def test_treaty_scenarios_contract_check_catches_schema_errors():
    import shutil
    out = _two_runs()[0]["dir"] / "out"
    with tmpdir() as d:
        for f in out.glob("*"):
            shutil.copy(f, d / f.name)
        good = json.loads((d / "TreatyScenarios.json").read_text(encoding="utf-8"))
        assert check_treaty_outputs(d)["status"] == "PASS"
        for mutate, text in ((lambda x: x["scenarios"][0].update(prem_chg=0.05), "prem_chg"),
                             (lambda x: x["scenarios"][0]["books"]["volume"].pop(), "books.volume"),
                             (lambda x: x["scenarios"][0]["books"]["lr_adj"].__setitem__(0, float("nan")), "books.lr_adj"),
                             (lambda x: x["scenarios"][0].update(ri=[]), "keys"),
                             (lambda x: x["scenarios"][1].update(name=x["scenarios"][0]["name"]), "unique")):
            bad = json.loads(json.dumps(good))
            mutate(bad)
            (d / "TreatyScenarios.json").write_text(json.dumps(bad), encoding="utf-8")
            r = check_treaty_outputs(d)
            assert r["status"] == "FAIL" and any(text in p for p in r["problems"]), (text, r["problems"])
        (d / "TreatyScenarios.json").unlink()
        assert any("missing" in p for p in check_treaty_outputs(d)["problems"])

def test_zz_cleanup():
    import shutil
    shutil.rmtree(_KEEP, ignore_errors=True)
    assert set(GENERATED) >= {"out", "options", "options.json", "run_manifest.json"}
