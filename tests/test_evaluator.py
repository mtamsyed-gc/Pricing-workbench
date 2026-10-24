"""Evaluator hand checks (WS0 acceptance): same cell under CAT_ALPHA (factor co-pay) and CAT_BETA (block co-pay),
RETIREE (entry-age rating, payment frequency) and IPMI (USD, area x deductible, modules) with FX."""
import copy

import pandas as pd
from _util import catalogue, raises, source_value

from pw import ProposalRequired, SpecError
from pw.evaluator import evaluate
from pw.trace import format_trace

CELL = {"cell_id": 1, "product_type": "INDIVIDUAL", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "P2", "age": 33,
        "gender": "F", "marital": "MARRIED", "member_category": "EMPLOYEE", "copay_op_diag": "10%",
        "nationality_group": "OTHER", "maternity_eligible": "N"}


def test_same_cell_alpha_factor_copay_hand_check():
    base = source_value("CAT_ALPHA", {"plan": "P2", "age": 33, "gender": "F"})
    res, tr = evaluate(catalogue("CAT_ALPHA"), [CELL], {"trace": True})
    # defaults: ded_consult D30 (1.0), pharmacy 0% (1.0), AML = reference for N_GOLD (1.0), OPT1, TPA_RED 1.0, OTHER 1.0
    expected = round(base * 0.955, 2)
    assert res.loc[0, "status"] == "PRICED"
    assert res.loc[0, "price"] == expected, (res.loc[0, "price"], expected)
    t = tr[tr["cell_id"] == 1]
    assert t.iloc[0]["type"] == "BASE_TABLE" and t.iloc[0]["value"] == base
    op = t[t["component_id"] == "f_opdiag"].iloc[0]
    assert op["option"] == "10%" and op["value"] == 0.955
    assert abs(t.iloc[-1]["running"] - expected) < 1e-9
    assert set(res.loc[0, "defaulted"].split(";")) == {"ded_consult", "copay_pharmacy", "aml", "network_option", "module_maternity"}
    assert "f_opdiag" in format_trace(tr, 1)


def test_same_cell_beta_block_copay_hand_check():
    nil = source_value("CAT_BETA", {"plan": "P2", "age": 33, "gender": "F", "marital": "MARRIED",
                                    "member_category": "PRINCIPAL"}, component_id="blocks", level="NIL")
    src10 = source_value("CAT_BETA", {"plan": "P2", "age": 33, "gender": "F", "marital": "MARRIED",
                                      "member_category": "PRINCIPAL"}, component_id="blocks", level="10%")
    res, tr = evaluate(catalogue("CAT_BETA"), [CELL], {"trace": True})
    expected = round(nil * 0.952, 2)
    assert res.loc[0, "price"] == expected == src10
    t = tr[tr["cell_id"] == 1]
    assert t.iloc[0]["value"] == nil
    assert t[t["component_id"] == "blocks.implied"].iloc[0]["value"] == 0.952
    # EMPLOYEE matched the PRINCIPAL section through the hierarchy
    assert "member_category=PRINCIPAL" in t.iloc[0]["matched_key"]


def test_module_and_loading_and_options():
    cell = dict(CELL, maternity_eligible="Y", module_maternity="M20", aml="300000", tpa="TPA_GREEN", nationality_group="GRP_WEST")
    cat = catalogue("CAT_ALPHA")
    res, tr = evaluate(cat, [cell], {"trace": True, "loading_applied": 0.10})
    base = source_value("CAT_ALPHA", {"plan": "P2", "age": 33, "gender": "F"})
    s = cat.scopes[0]
    aml = next(c for c in s.components if c.component_id == "f_aml")
    f_aml = next(r["value"] for r in aml.rows if r["key"] == {"aml": "300000", "network": "N_GOLD"})
    mat = next(c for c in s.components if c.component_id == "m_mat")
    m = next(r["value"] for r in mat.rows if r["key"] == {"network": "N_GOLD", "module_maternity": "M20"})
    pre = round(base * 0.955 * f_aml * 0.93 * 1.12 + m, 2)
    assert abs(res.loc[0, "price"] - round(pre * 1.10, 2)) < 1e-9
    raises(ProposalRequired, evaluate, cat, [cell], {"loading_applied": 0.35})


def test_refer_unmatched_strict_and_defaults():
    cat = catalogue("CAT_ALPHA")
    cells = [dict(CELL, cell_id=1, plan="P7", age=75), dict(CELL, cell_id=2, tpa="TPA_UNKNOWN"),
             dict(CELL, cell_id=3, copay_op_diag="99%")]
    res, _ = evaluate(cat, cells)
    assert list(res["status"]) == ["REFER", "UNMATCHED", "UNMATCHED"]
    assert res["price"].isna().all()
    raises(ProposalRequired, evaluate, cat, cells, {"strict": True})
    # no catalogue default declared -> ProposalRequired, never a silent default
    c2 = copy.deepcopy(cat)
    for p in c2.scopes[0].plans:
        p.defaults.pop("ded_consult")
    raises(ProposalRequired, evaluate, c2, [dict(CELL)])
    # reference fill prices the base at reference options
    res, _ = evaluate(cat, [dict(CELL, copay_op_diag=None)], {"fill": "reference"})
    assert res.loc[0, "price"] == source_value("CAT_ALPHA", {"plan": "P2", "age": 33, "gender": "F"})


def test_retiree_entry_age_and_payment_frequency():
    cat = catalogue("CAT_RETIREE")
    base = source_value("CAT_RETIREE", {"plan": "R1", "age": 60, "gender": "F"})
    cells = pd.DataFrame([
        {"cell_id": 0, "product_type": "RETIREE", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "R1", "age": 66,
         "entry_age": 60, "gender": "F", "payment_frequency": "MONTHLY"},
        {"cell_id": 1, "product_type": "RETIREE", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "R1", "age": 80,
         "entry_age": 78, "gender": "F"},
        {"cell_id": 2, "product_type": "RETIREE", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "R1", "age": 70,
         "entry_age": None, "gender": "M"}])
    res, tr = evaluate(cat, cells, {"trace": True})
    assert res.loc[0, "price"] == round(base * 1.041, 2)       # rated on entry age 60, not attained 66
    assert res.loc[1, "status"] == "REFER"                       # entry above 75
    assert res.loc[2, "status"] == "UNMATCHED" and "entry_age" in res.loc[2, "reason"]


def test_ipmi_usd_area_deductible_modules_with_fx():
    cat = catalogue("CAT_IPMI")
    base = source_value("CAT_IPMI", {"plan": "PLUS", "age": 42, "gender": "M"})
    ded = source_value("CAT_IPMI", {"deductible": "D1500", "area_of_cover": "WW_INC_USA"}, component_id="f_ded")
    cell = {"product_type": "IPMI", "rating_region": "IPMI_GLOBAL", "tpa": "TPA_INTL", "plan": "PLUS", "age": 42,
            "gender": "M", "area_of_cover": "WW_INC_USA", "deductible": "D1500", "payment_frequency": "MONTHLY"}
    usd, _ = evaluate(cat, [cell])
    exp_usd = round(base * 1.72 * ded * 1.05 + 790.0 + 95.0, 2)
    assert usd.loc[0, "price"] == exp_usd and usd.loc[0, "currency"] == "USD"
    fx = {"USD": 3.6725, "AED": 1.0}
    aed, tr = evaluate(cat, [cell], {"currency": "AED", "fx": fx, "trace": True})
    assert aed.loc[0, "price"] == round(exp_usd * 3.6725, 2) and aed.loc[0, "currency"] == "AED"
    raises(ProposalRequired, evaluate, cat, [cell], {"currency": "AED"})
    fem = dict(cell, gender="F", maternity_eligible="Y", module_maternity="MAT")
    r, _ = evaluate(cat, [fem])
    assert r.loc[0, "modules_add"] == 790.0 + 95.0 + 1720.0


def test_basis_conversion_fees_minimum():
    cat = catalogue("CAT_DELTA")
    cell = {"product_type": "BASIC", "rating_region": "RGN_C", "tpa": "DIRECT", "plan": "BASIC", "age": 30,
            "member_category": "DOMESTIC_UAE_SPONSOR"}
    res, _ = evaluate(cat, [cell])
    assert res.loc[0, "price"] == max(560.0, 400.0) + 18.0
    raises(ProposalRequired, evaluate, cat, [cell], {"basis": "NET"})
    res, _ = evaluate(cat, [cell], {"basis": "NET", "basis_factors": {"GROSS_TO_NET": 0.8}})
    assert res.loc[0, "price"] == round(560.0 * 0.8, 2) + 18.0 * 0.8


def test_ambiguity_and_per_family_raise():
    from pw.spec_parser import parse_catalogue
    spec = {"spec_id": "AMB", "catalogue": {"catalogue_id": "AMB", "owner": "F", "kind": "MARKET", "version": "1",
                                            "currency": "AED", "premium_basis": "NET"},
            "scopes": [{"scope_id": "S", "product_type": "SME", "regulator": "DHA", "rating_region": "R", "tpa_set": ["T"],
                        "plans": [{"plan_id": "P", "label": "P"}],
                        "components": [{"type": "BASE_TABLE", "rows": [
                            {"key": {"gender": "M", "member_category": "ANY"}, "value": 100},
                            {"key": {"gender": "ANY", "member_category": "EMPLOYEE"}, "value": 200}]}]}]}
    cat = parse_catalogue(spec=spec)
    c = {"product_type": "SME", "rating_region": "R", "tpa": "T", "plan": "P", "age": 30, "gender": "M", "member_category": "EMPLOYEE"}
    raises(SpecError, evaluate, cat, [c])
    spec["scopes"][0]["components"][0]["rows"][1]["key"]["gender"] = "F"
    spec["scopes"][0]["components"].append({"type": "MODULE", "family": "module_dental", "unit": "PER_FAMILY",
                                            "default_option": "D", "values": {"D": 50}})
    cat = parse_catalogue(spec=spec)
    raises(ProposalRequired, evaluate, cat, [c])


def test_evaluation_is_deterministic():
    cat = catalogue("CAT_ALPHA")
    cells = pd.DataFrame([dict(CELL, cell_id=i, age=a, gender=g) for i, (a, g) in enumerate([(5, "M"), (33, "F"), (64, "F")])])
    r1, t1 = evaluate(cat, cells, {"trace": True})
    r2, t2 = evaluate(cat, cells.iloc[::-1], {"trace": True})
    assert r1.to_csv() == r2.to_csv() and t1.to_csv() == t2.to_csv()
