"""OD4 / CR #24 (owner, 25 Oct 2026): the B2 comparison is on the Merit cuts: base x Merit-keyed factors + maternity at
the plan's default limit; options Merit does not carry sit at their reference (factor 1.0); other riders compared in
RiderIndex; TreatyFeed on the headline relativity."""
import copy

import numpy as np
import pandas as pd
from _util import FIX, catalogue, raises

from pw import SpecError
from pw.evaluator import evaluate
from pw.exposure import build_exposure
from pw.rate_index import (B2_DEFAULTS, STANDARD_WEIGHT, aggregate_cells, b2_eval_options, rate_factors, rate_index,
                           rider_index, select_mix)


def _mix():
    d = FIX / "EXPO_SYN"
    ex = build_exposure(d / "dim_life.csv", d / "maps", d / "run_manifest.csv", strict=False, snapshot_date="2025-07-01")
    mix, _ = select_mix(ex.cells)
    return aggregate_cells(mix, STANDARD_WEIGHT)


def _total(rf):
    return rate_index(rf).query("cut == 'TOTAL'").iloc[0]


def test_basis_options_and_validation():
    assert B2_DEFAULTS == {"basis": "MERIT_CUTS", "headline_modules": ["module_maternity"]}
    o = b2_eval_options(None, {"duckdb": {"threads": 2}})
    assert o == {"duckdb": {"threads": 2}, "fill": "reference", "default_families": ["module_maternity"]}
    assert b2_eval_options({"basis": "FULL"})["fill"] == "default"
    raises(SpecError, b2_eval_options, {"basis": "OTHER"})
    raises(SpecError, b2_eval_options, {"headline_modules": ["copay_op_diag"]})


def test_headline_cell_is_base_times_merit_factors_plus_maternity_at_plan_default():
    a = catalogue("CAT_ALPHA")
    cell = pd.DataFrame([{"cell_id": 0, "product_type": "INDIVIDUAL", "rating_region": "RGN_A", "tpa": "TPA_GREEN",
                          "plan": "P2", "age": 33, "gender": "F", "nationality_group": "GRP_EAST", "maternity_eligible": "Y"}])
    r, tr = evaluate(a, cell, {**b2_eval_options(None), "trace": True})
    t = tr.set_index("component_id")
    # co-pay, consultation, pharmacy, AML, network option at reference (1.0); TPA and nationality (Merit fields) apply
    for cid in ("f_opdiag", "f_consult", "f_pharm", "f_aml", "f_netopt"):
        assert t.loc[cid, "value"] == 1.0, cid
    assert t.loc["f_tpa", "value"] == 0.93 and t.loc["f_nat", "value"] == 0.94
    assert t.loc["m_mat", "option"] == "M10"                                   # P2's catalogue default limit
    base = t.loc["base", "value"]
    assert abs(r["price"].iloc[0] - round(base * 0.93 * 0.94 + t.loc["m_mat", "value"], 2)) < 1e-9


def test_non_merit_factor_changes_do_not_move_the_headline():
    """An option that changes a co-pay multiplier (not in Merit) leaves the headline unchanged under MERIT_CUTS; under
    FULL (catalogue defaults, P1-P7 sold at 10% OP co-pay) it would move."""
    a = catalogue("CAT_ALPHA")
    o = copy.deepcopy(a)
    f = next(c for c in o.scopes[0].components if c.component_id == "f_opdiag")
    for r in f.rows:
        if r["key"]["copay_op_diag"] == "10%":
            r["value"] = 0.80
    cells = _mix()
    merit = _total(rate_factors(a, o, "O", cells, b2_eval_options(None)))
    full = _total(rate_factors(a, o, "O", cells, b2_eval_options({"basis": "FULL"})))
    assert abs(merit["index"] - 1.0) < 1e-12
    assert full["index"] < 0.9


def test_dental_optical_out_of_headline_maternity_in():
    a = catalogue("CAT_ALPHA")
    o = copy.deepcopy(a)
    m = next(c for c in o.scopes[0].components if c.component_id == "m_mat")
    for r in m.rows:
        r["value"] = round(r["value"] * 1.10, 2)
    cells = _mix()
    t = _total(rate_factors(a, o, "O", cells, b2_eval_options(None)))
    assert abs(t["index_base"] - 1.0) < 1e-12 and abs(t["index_riders"] - 1.10) < 1e-3 and t["index"] > 1.0
    t0 = _total(rate_factors(a, o, "O", cells, b2_eval_options({"headline_modules": []})))
    assert abs(t0["index"] - 1.0) < 1e-12                                      # maternity switched out of the headline


def test_rider_index_per_limit_and_not_quoted():
    a = catalogue("CAT_ALPHA")
    o = copy.deepcopy(a)
    m = next(c for c in o.scopes[0].components if c.component_id == "m_mat")
    for r in m.rows:
        if r["key"]["module_maternity"] == "M20":
            r["value"] = round(r["value"] * 1.2, 2)
        if r["key"]["module_maternity"] == "MAML" and r["key"]["network"] == "N_PLAT":
            r["value"], r["status"], r["source_ref"] = None, "REFER", "not quoted (test)"
    ri = rider_index(a, {"O": o}, _mix(), b2_eval_options(None))
    tot = ri[ri["cut"] == "TOTAL"].set_index("limit")
    assert set(tot.index) == {"M10", "M20", "MAML"} and (tot["rider_family"] == "module_maternity").all()
    assert abs(tot.loc["M10", "index"] - 1.0) < 1e-9 and abs(tot.loc["M20", "index"] - 1.2) < 2e-3
    assert tot.loc["MAML", "not_quoted_share"] > 0 and tot.loc["M10", "not_quoted_share"] == 0
    assert (tot["lives_eligible"] > 0).all()
    assert set(ri["cut"]) == {"TOTAL", "product_typexrating_region"}


def test_treaty_feed_uses_the_headline_relativity():
    from pw.rate_index import treaty_feed
    a = catalogue("CAT_ALPHA")
    o = copy.deepcopy(a)
    b = next(c for c in o.scopes[0].components if c.type == "BASE_TABLE")
    for r in b.rows:
        if r.get("value") is not None:
            r["value"] = round(r["value"] * 1.05, 2)
    rf = rate_factors(a, o, "O", _mix(), b2_eval_options(None))
    bm = pd.DataFrame({"product_type": ["ANY"], "rating_region": ["ANY"], "tpa": ["ANY"], "treaty_book": ["B"]})
    tf = treaty_feed(rf, bm, {"B": 0.0}, pd.DataFrame({"treaty_book": ["B"], "earned_prem": [100.0], "ultimate_claims": [70.0]}))
    head = _total(rf)["index"]
    assert abs(tf["rate_factor"].iloc[0] - head) < 1e-12
    assert abs(tf["lr_adjustment_pts"].iloc[0] - (70 / (100 * head) - 0.7) * 100) < 1e-9
    assert np.isclose(head, _total(rf)["prem_option"] / _total(rf)["prem_expiring"])
