"""WS1: B2 rate index hand check, co-pay independence (SPEC §12 note), benefit-adjusted index, TreatyFeed formula,
output contracts and the end-to-end CLI."""
import copy
import json
import subprocess
import sys

import numpy as np
import pandas as pd
from _util import FIX, REPO, catalogue, raises, tmpdir

from pw import MappingRequired, ProposalRequired, SpecError
from pw.benefit_value import benefit_diff, plan_ratio
from pw.model import Catalogue
from pw.outputs import check_contract, read_table
from pw.rate_index import (RATE_FACTOR_EXTRAS, RATE_INDEX_EXTRAS, rate_factors, rate_index, treaty_feed)

X = Catalogue.read(FIX / "SUB_X" / "catalogue.json")
Y = Catalogue.read(FIX / "SUB_Y" / "catalogue.json")
F_OPDIAG_10 = 0.955
F_TPA = {"TPA_RED": 1.0, "TPA_BLUE": 1.0, "TPA_GREEN": 0.93}
F_NAT = {"OTHER": 1.0, "GRP_SOUTH": 0.915, "GRP_EAST": 0.94, "GRP_WEST": 1.12}

# five males (no maternity module), defaults for every option family except nationality
CELLS = pd.DataFrame([
    {"cell_id": 0, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "P1", "age": 3, "gender": "M", "nationality_group": "OTHER", "w": 10.0},
    {"cell_id": 1, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_GREEN", "plan": "P4", "age": 41, "gender": "M", "nationality_group": "GRP_SOUTH", "w": 25.0},
    {"cell_id": 2, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_BLUE", "plan": "P5", "age": 33, "gender": "M", "nationality_group": "GRP_WEST", "w": 40.0},
    {"cell_id": 3, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_GREEN", "plan": "P7", "age": 58, "gender": "M", "nationality_group": "OTHER", "w": 15.0},
    {"cell_id": 4, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "P7", "age": 75, "gender": "M", "nationality_group": "OTHER", "w": 5.0},
])
for c in ("maternity_eligible",):
    CELLS[c] = "N"


def _base(cat, tpa, plan, age, gender):
    """Base table value read directly from the catalogue rows (source / submitted value), no matching engine."""
    for s in cat.scopes:
        if tpa in s.tpa_set:
            for r in next(c for c in s.components if c.type == "BASE_TABLE").rows:
                k = r["key"]
                if k["plan"] == plan and k["gender"] in (gender, "ANY") and k["age"][0] <= age <= k["age"][1]:
                    return r["value"], r["status"]
    raise KeyError((tpa, plan, age, gender))


def test_index_hand_check_five_cells():
    alpha = catalogue("CAT_ALPHA")
    rf = rate_factors(alpha, X, "SUB_X", CELLS)
    se, so = 0.0, 0.0
    for c in CELLS.itertuples():
        be, ste = _base(alpha, c.tpa, c.plan, c.age, c.gender)
        bo, sto = _base(X, c.tpa, c.plan, c.age, c.gender)
        row = rf[(rf["plan"] == c.plan) & (rf["age"] == c.age) & (rf["tpa"] == c.tpa)].iloc[0]
        if ste == "REFER" or sto == "REFER":           # P7 age 75 is a REFER cell in the expiring catalogue
            assert row["priced_status"] == "REFER" and np.isnan(row["factor"])
            continue
        f = F_OPDIAG_10 * F_TPA[c.tpa] * F_NAT[c.nationality_group]
        re_, ro = round(be * f, 2), round(bo * f, 2)
        assert row["rate_expiring"] == re_ and row["rate_option"] == ro, (c, row)
        assert abs(row["factor"] - ro / re_) < 1e-12
        se += c.w * re_
        so += c.w * ro
    ri = rate_index(rf, [[]])
    tot = ri.iloc[0]
    assert abs(tot["index"] - so / se) < 1e-12
    assert tot["lives"] == 90.0 and tot["lives_refer"] == 5.0 and abs(tot["unpriced_share"] - 5 / 95) < 1e-12
    check_contract("RateFactors", rf, RATE_FACTOR_EXTRAS)
    check_contract("RateIndex", ri, RATE_INDEX_EXTRAS)


def test_cell_factor_independent_of_copay_options():
    """SPEC §12 note: issued co-pay multipliers are flat, so option / expiring does not depend on co-pay options
    (equal up to the 2 dp rounding of each price)."""
    alpha = catalogue("CAT_ALPHA")
    priced = CELLS.iloc[:4]
    facs = []
    for opts in ({"copay_op_diag": "0%", "ded_consult": "NIL", "copay_pharmacy": "0%"},
                 {"copay_op_diag": "20%", "ded_consult": "D60", "copay_pharmacy": "25%"},
                 {"copay_op_diag": "AED25", "ded_consult": "P15_C40", "copay_pharmacy": "15%"}):
        cells = priced.assign(**opts)
        facs.append(rate_factors(alpha, X, "SUB_X", cells)["factor"].to_numpy())
    for f in facs[1:]:
        assert np.allclose(f, facs[0], rtol=0, atol=2e-4)


def test_benefit_adjusted_index_is_index_over_benefit_ratio():
    alpha = catalogue("CAT_ALPHA")
    prop = copy.deepcopy(X)
    for s in prop.scopes:                              # leaner P4: 20% OP diagnostic co-pay instead of 10%
        s.plan("P4").defaults["copay_op_diag"] = "20%"
    bd, bf = benefit_diff(alpha, prop, "PROP")
    ratio = plan_ratio(bf)
    r4 = float(ratio[ratio["plan"] == "P4"]["ratio"].iloc[0])
    assert abs(r4 - 0.915 / 0.955) < 1e-12
    assert (ratio[ratio["plan"] != "P4"]["ratio"] == 1.0).all()
    d = bd[(bd["plan"] == "P4") & (bd["benefit_code"] == "op_diag_copay")]
    assert set(d["direction"]) == {"LEANER"} and set(d["source"]) == {"catalogue:f_opdiag"}
    cells = CELLS[CELLS["plan"] == "P4"]
    rf = rate_factors(alpha, prop, "PROP", cells)
    ri = rate_index(rf, [[]], ratio).iloc[0]
    assert abs(ri["index_benefit_adj"] - ri["index"] / r4) < 1e-12
    # no relativity anywhere -> MANUAL_REVIEW and a null ratio, never 1
    for s in prop.scopes:
        s.plan("P2").defaults["copay_op_diag"] = "35%"
    bd, bf = benefit_diff(alpha, prop, "PROP")
    assert bf[bf["plan"] == "P2"]["ratio"].isna().all()
    _, bf2 = benefit_diff(alpha, prop, "PROP", overrides={("copay_op_diag", "35%"): 0.88})
    assert np.allclose(bf2[bf2["plan"] == "P2"]["ratio"], 0.88 / 0.955)


def test_treaty_feed_formula():
    rf = pd.DataFrame({"option_id": ["A"] * 3, "product_type": ["INDIVIDUAL"] * 3, "rating_region": ["R"] * 3,
                       "tpa": ["T1", "T1", "T2"], "w": [10.0, 30.0, 20.0], "rate_expiring": [100.0, 200.0, 50.0],
                       "rate_option": [110.0, 204.0, 60.0], "priced_status": ["PRICED", "PRICED", "REFER"]})
    bm = pd.DataFrame({"product_type": ["ANY"], "rating_region": ["ANY"], "tpa": ["ANY"], "treaty_book": ["B"]})
    xp = pd.DataFrame({"treaty_book": ["B"], "earned_prem": [1000.0], "ultimate_claims": [700.0]})
    tf = treaty_feed(rf, bm, {"B": 0.05}, xp).iloc[0]
    f = (10 * 110 + 30 * 204) / (10 * 100 + 30 * 200)            # REFER cell excluded
    assert abs(tf["rate_factor"] - f) < 1e-12
    assert abs(tf["premium_change_pct"] - (f * 0.95 - 1) * 100) < 1e-9
    assert abs(tf["lr_adjustment_pts"] - (700 / (1000 * f) - 0.7) * 100) < 1e-9
    raises(ProposalRequired, treaty_feed, rf, bm, {}, xp)
    raises(ProposalRequired, treaty_feed, rf, bm, {"B": 0.05}, xp.assign(treaty_book="Z"))
    raises(MappingRequired, treaty_feed, rf, bm.assign(tpa="T9"), {"B": 0.05}, xp)


def test_output_contract_checker():
    df = pd.DataFrame(columns=["option_id", "plan", "richness_expiring", "richness_option", "ratio"])
    check_contract("BenefitFactors", df)
    raises(SpecError, check_contract, "BenefitFactors", df[["option_id", "plan", "ratio", "richness_option",
                                                            "richness_expiring"]])


def test_cli_ingest_index_benefit_end_to_end():
    pw = [sys.executable, str(REPO / "tools" / "pw.py")]
    with tmpdir() as d:
        for o in ("SUB_X", "SUB_Y"):
            r = subprocess.run(pw + ["t", "ingest", str(FIX / o / "submission.xlsx"), "--spec", str(FIX / "T_ALPHA" / "template_spec.json"),
                                     "--issued", str(FIX / "T_ALPHA" / "template.xlsx"), "--run", str(FIX / "RUN_SYN" / "run_config.json"),
                                     "--id", o, "--owner", o, "--runs-root", str(d)], capture_output=True, text=True, cwd=str(REPO / "docs"))
            assert r.returncode == 0 and "V5 PASS" in r.stdout, r.stderr
        r = subprocess.run(pw + ["index", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(d)],
                           capture_output=True, text=True, cwd=str(REPO / "docs"))
        assert r.returncode == 0 and "coverage PASS" in r.stdout, r.stderr
        out = d / "RUN_SYN" / "out"
        for t in ("RateFactors", "RateIndex", "BenefitDiff", "BenefitFactors", "TreatyFeed", "OptionTerms"):
            assert (out / f"{t}.parquet").exists() and (out / f"{t}.xlsx").exists(), t
        ri = read_table("RateIndex", out)
        assert set(ri["scenario"]) == {"STANDARD", "WRITTEN_LY", "UWY_MINUS_1"}
        tot = ri[(ri["scenario"] == "STANDARD") & (ri["cut"] == "TOTAL")].set_index("option_id")["index"]
        assert tot["SUB_X"] > 1.0 > tot["SUB_Y"]          # SUB_X perturbed up (+3.5% mean), SUB_Y down (-1.5%)
        tf = read_table("TreatyFeed", out)
        assert set(tf["treaty_book"]) == {"BOOK_IND_GREEN", "BOOK_IND_OTHER"}
        m = json.loads((d / "RUN_SYN" / "run_manifest.json").read_text())
        assert m["gates"]["COVERAGE"]["status"] == "PASS" and "RateIndex" in m["outputs"]
        assert m["versions"]["treatymodel_target"].startswith("treatymodel")
        # deterministic: a second run writes identical Parquet
        h1 = m["outputs"]["RateIndex"]["sha256_parquet"]
        subprocess.run(pw + ["index", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(d)], check=True,
                       capture_output=True, cwd=str(REPO / "docs"))
        m2 = json.loads((d / "RUN_SYN" / "run_manifest.json").read_text())
        assert m2["outputs"]["RateIndex"]["sha256_parquet"] == h1
        r = subprocess.run(pw + ["benefit", str(FIX / "RUN_SYN" / "run_config.json"), "--runs-root", str(d)],
                           capture_output=True, text=True, cwd=str(REPO / "docs"))
        assert r.returncode == 0 and "BenefitFactors" in r.stdout
