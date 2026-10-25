"""Owner decisions of 24 Oct 2026 (HANDOVER items 1-21, SPEC v0.4): quotable riders (blank = not quoted), the B2
base / rider split, B1 override order and rider valuation, V5 on riders, single-option scorecard scale with panels as
their lead, gap-register peers, and the Cover's TPA basis statement. Hand checks use independent arithmetic."""
import copy
import json

import numpy as np
import pandas as pd
from _util import FIX, REPO, catalogue, requires, tmpdir
from openpyxl import load_workbook

from pw.benefit_value import benefit_diff, module_values
from pw.evaluator import NONE_OPTION, evaluate
from pw.gates import v5_submission_integrity
from pw.rate_index import rate_index
from pw.scorecard import panel_inputs, score, score_inputs
from pw.template.generator import generate_template
from pw.template.parser import fill_template, parse_submission, to_catalogue

SPEC = json.loads((FIX / "T_ALPHA" / "template_spec.json").read_text(encoding="utf-8"))


def _fill_spec():
    s = copy.deepcopy(SPEC)
    s["reference_sheets"] = {"addons": "FILL"}
    return s


def _module_row(cat, keys):
    k = dict(keys)
    sid, cid = k.pop("scope_id"), k.pop("component_id")
    comp = next(c for c in cat.scope(sid).components if c.component_id == cid)
    return next(r for r in comp.rows if json.dumps(r["key"], sort_keys=True) == json.dumps(k, sort_keys=True))


def _submission(d, rider_fn):
    """Generate the fixture template with quotable riders, fill rates at expiring x 1.0 (via a lookup-free copy of
    the existing SUB_X values is not needed: synthetic values are fine) and riders through rider_fn."""
    alpha = catalogue("CAT_ALPHA")
    spec = _fill_spec()
    generate_template(spec, d / "t.xlsx", expiring=alpha)

    def fn(ck, keys, kind):
        if kind == "ADDON":
            return rider_fn(_module_row(alpha, keys[0]))
        return None if kind == "TERM" else 1000.0
    fill_template(d / "t.xlsx", d / "s.xlsx", value_fn=fn)
    return alpha, spec, parse_submission(d / "s.xlsx", template_spec=spec)


def test_cover_states_tpa_basis_and_rider_mode():
    with tmpdir() as d:
        generate_template(_fill_spec(), d / "t.xlsx", expiring=catalogue("CAT_ALPHA"))
        wb = load_workbook(d / "t.xlsx")
        text = " ".join(str(v) for row in wb["Cover"].iter_rows(values_only=True) for v in row if v)
        assert "BEFORE the TPA factor" in text and "a blank cell means not quoted" in text
        assert "submitted" in [c.value for c in wb["Add-ons"][4]] or any(
            c.value == "submitted" for row in wb["Add-ons"].iter_rows() for c in row)


@requires("examples/ufic_2027")
def test_cedant_example_quotes_riders():
    ufic = json.loads((REPO / "examples" / "ufic_2027" / "template_spec.json").read_text(encoding="utf-8"))
    assert ufic["reference_sheets"]["addons"] == "FILL"


def test_blank_rider_is_not_quoted_and_base_still_priced():
    with tmpdir() as d:
        alpha, spec, parsed = _submission(d, lambda r: None)                   # every rider left blank
        sub = to_catalogue(parsed, spec, "S", "synthetic", expiring=alpha)
        mods = [c for s in sub.scopes for c in s.components if c.type == "MODULE"]
        assert mods and all(r["value"] is None and r["source_ref"].startswith("not quoted") for c in mods for r in c.rows)
        cells = pd.DataFrame([{"cell_id": 0, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A",
                               "tpa": "TPA_RED", "plan": "P1", "age": 30, "gender": "F", "marital": "MARRIED",
                               "maternity_eligible": "Y", "nationality_group": "OTHER"},
                              {"cell_id": 1, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A",
                               "tpa": "TPA_RED", "plan": "P1", "age": 30, "gender": "M", "marital": "MARRIED",
                               "maternity_eligible": "N", "nationality_group": "OTHER"}])
        res, _ = evaluate(sub, cells, {"fill": "default"})
        f, m = res.iloc[0], res.iloc[1]
        assert f["status"] == "REFER" and "rider not quoted" in f["reason"] and np.isnan(f["price"])
        assert f["price_base"] > 0 and np.isnan(f["price_riders"])               # base-only price survives
        assert m["status"] == "PRICED" and m["price_riders"] == 0.0 and m["price"] == m["price_base"]
        v5 = v5_submission_integrity(parsed, spec, parsed.meta.get("structure_hash"), alpha, (0.7, 1.3))
        n_addon = sum(1 for t in parsed.kinds.values() if t == "ADDON")
        assert n_addon and v5["counts"].get("RIDER_NOT_QUOTED", 0) == n_addon
        assert not (set(v5["invalid"]) & {k for k, t in parsed.kinds.items() if t == "ADDON"})


def test_quoted_riders_apply_and_v5_flags_rider_outliers():
    with tmpdir() as d:
        alpha, spec, parsed = _submission(d, lambda r: None if r["value"] is None else round(r["value"] * 1.5, 2))
        sub = to_catalogue(parsed, spec, "S", "synthetic", expiring=alpha)
        mods = [c for s in sub.scopes for c in s.components if c.type == "MODULE"]
        exp = {c.component_id: c for s in alpha.scopes for c in s.components if c.type == "MODULE"}
        for c in mods:
            for r, e in zip(c.rows, exp[c.component_id].rows):
                if e["value"] is not None:
                    assert r["value"] == round(e["value"] * 1.5, 2) and r["source_ref"] == "submitted addon"
        v5 = v5_submission_integrity(parsed, spec, parsed.meta.get("structure_hash"), alpha, (0.7, 1.3))
        n_priced = sum(1 for c in exp.values() for r in c.rows if r["value"] is not None)
        assert v5["counts"].get("RIDER_OUTLIER") == n_priced                    # 1.5 is outside [0.7, 1.3]
        fl = v5["flags"][v5["flags"]["flag"] == "RIDER_OUTLIER"]
        assert np.allclose(fl["ratio"].astype(float), 1.5, atol=1e-3)


def test_rate_index_base_and_rider_split_hand_checked():
    # two cells; cell 1's rider is not quoted under the option (full price REFER, base priced)
    rf = pd.DataFrame([
        {"option_id": "O", "plan": "P1", "w": 10.0, "rate_expiring": 1400.0, "rate_option": 1540.0, "priced_status": "PRICED",
         "rate_expiring_base": 1000.0, "rate_option_base": 1100.0, "rate_expiring_riders": 400.0, "rate_option_riders": 440.0},
        {"option_id": "O", "plan": "P1", "w": 30.0, "rate_expiring": 2000.0, "rate_option": np.nan, "priced_status": "REFER",
         "rate_expiring_base": 2000.0, "rate_option_base": 2300.0, "rate_expiring_riders": 0.0, "rate_option_riders": np.nan}])
    ri = rate_index(rf, cuts=[[]])
    t = ri.iloc[0]
    assert abs(t["index"] - 1540.0 / 1400.0) < 1e-12                             # full premium, priced cells only
    assert abs(t["index_base"] - (10 * 1100 + 30 * 2300) / (10 * 1000 + 30 * 2000)) < 1e-12
    assert abs(t["index_riders"] - 440.0 / 400.0) < 1e-12
    assert t["unpriced_share"] == 30.0 / 40.0


def test_b1_override_wins_and_shows_the_value_it_replaces():
    alpha = catalogue("CAT_ALPHA")
    opt = copy.deepcopy(alpha)
    p1 = opt.scopes[0].plan("P1")
    p1.defaults["copay_op_diag"] = "0%"                                           # option richer than expiring 10%
    bd0, _ = benefit_diff(alpha, opt, "O")
    row0 = bd0[(bd0["plan"] == "P1") & (bd0["family"] == "copay_op_diag")].iloc[0]
    assert row0["source"].startswith("catalogue:")
    bd, bf = benefit_diff(alpha, opt, "O", overrides={("copay_op_diag", "0%"): 1.10, ("copay_op_diag", "10%"): 1.0})
    row = bd[(bd["plan"] == "P1") & (bd["family"] == "copay_op_diag")].iloc[0]
    assert abs(row["value_factor"] - 1.10) < 1e-12                                # override beats the catalogue table
    assert row["source"].startswith("override (replaces catalogue:")


def test_b1_rider_value_share_of_expiring_base_hand_checked():
    alpha = catalogue("CAT_ALPHA")
    s = alpha.scopes[0]
    cells = pd.DataFrame([
        {"cell_id": 0, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED",
         "plan": "P1", "age": 30, "gender": "F", "marital": "MARRIED", "maternity_eligible": "Y", "nationality_group": "OTHER", "w": 3.0},
        {"cell_id": 1, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED",
         "plan": "P1", "age": 40, "gender": "M", "marital": "MARRIED", "maternity_eligible": "N", "nationality_group": "OTHER", "w": 7.0}])
    mv = module_values(alpha, cells, {("module_maternity", "M10")})
    v = mv[(s.scope_id, "P1", "module_maternity", "M10")]
    # independent: the maternity row for the plan's network and option, read straight from the catalogue rows
    net = s.plan("P1").network_by_tpa["TPA_RED"]
    mat = next(c for c in s.components if c.type == "MODULE" and c.family == "module_maternity")
    rate = next(r["value"] for r in mat.rows if r["key"]["module_maternity"] == "M10" and r["key"]["network"] in (net, "ANY"))
    e0, _ = evaluate(alpha, cells.assign(module_maternity=NONE_OPTION), {"fill": "default"})
    base = float((cells["w"] * e0["price_base"]).sum())
    assert abs(v - 3.0 * rate / base) < 1e-9                                      # only the eligible female carries it


def test_scorecard_scale_set_by_single_options_and_panel_is_its_lead():
    ri = pd.DataFrame([{"option_id": o, "scenario": "STANDARD", "cut": "TOTAL", "index": i, "index_benefit_adj": i,
                        "unpriced_share": 0.0} for o, i in (("X", 1.04), ("Y", 0.98), ("Z", 1.00))])
    ts = pd.DataFrame({"option_id": ["X", "Y", "Z"], "commission_pct": [15, 15, 15], "profit_share_pct": [0, 0, 0],
                       "corridor_pts": [0, 0, 0], "cap_pct": [150, 150, 150], "share_pct": [40, 30, 20]})
    si = score_inputs(ri, {}, ts)
    w = {"PRICE": 0.6, "SHARE": 0.4}
    alone, _ = score(si, w)
    pi = panel_inputs(si, ri, [{"panel_id": "P", "lead": "Y", "members": {"Y": 0.5, "X": 0.25, "Z": 0.25}}])
    p = pi.set_index("criterion")["value"]
    assert p["PRICE"] == 0.98 and p["SHARE"] == 90.0                             # lead's rates; capacity 30+40+20
    kinds = {"X": "OPTION", "Y": "OPTION", "Z": "OPTION", "P": "PANEL"}
    card, rank = score(pd.concat([si, pi], ignore_index=True), w, kinds=kinds)
    a = alone.set_index(["option_id", "criterion"])["normalised"]
    b = card.set_index(["option_id", "criterion"])["normalised"]
    for o in ("X", "Y", "Z"):
        for c in w:
            assert abs(a[(o, c)] - b[(o, c)]) < 1e-12                              # adding a panel moves nothing
    assert b[("P", "SHARE")] == 90.0      # CR #22 (25 Oct): SHARE absolute = 90% of the order (was min-max 350)
    assert b[("P", "PRICE")] == b[("Y", "PRICE")] == 100.0


def test_gap_register_low_peers_and_same_region():
    from pw.benchmark import gap_register
    from pw.model import BenefitLine
    from pw.tiers import TierMap
    base = catalogue("CAT_ALPHA")

    def mk(cid, region, covered):
        c = copy.deepcopy(base)
        c.catalogue_id = cid
        c.scopes = [c.scopes[0]]
        c.scopes[0].rating_region = region
        c.scopes[0].plans = [c.scopes[0].plan("P1")]
        c.scopes[0].benefits = [BenefitLine(plan_id="P1", benefit_code="physio_sessions", value=10 if covered else 0)]
        return c
    subj = mk("SUBJ", "R1", False)
    market = [mk(f"M{i}", "R1" if i < 3 else "R2", True) for i in range(5)]
    tm = TierMap(pd.DataFrame({"catalogue_id": ["ANY"], "plan": ["P1"], "tier": ["T1"], "weight": ["1"]}), ["T1"])
    g = gap_register([subj] + market, {"SUBJ"}, tm)                               # defaults: same region, >= 3 peers
    row = g[g["benefit_code"] == "physio_sessions"].iloc[0]
    assert row["assessment"] == "GAP" and row["n_peers"] == 3                     # R2 plans are not peers
    g2 = gap_register([subj] + market[:2], {"SUBJ"}, tm)
    assert (g2["assessment"] == "LOW_PEERS").all() and "only 2" in g2["note"].iloc[0]
    g3 = gap_register([subj] + market, {"SUBJ"}, tm, peer_same_region=False)
    assert g3[g3["benefit_code"] == "physio_sessions"].iloc[0]["n_peers"] == 5


# ---------------------------------------------------------------------------- independent review findings (24 Oct)
def _cells2():
    return pd.DataFrame([
        {"cell_id": 0, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED",
         "plan": "P1", "age": 30, "gender": "F", "marital": "MARRIED", "maternity_eligible": "Y", "nationality_group": "OTHER", "w": 3.0},
        {"cell_id": 1, "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "RGN_A", "tpa": "TPA_RED",
         "plan": "P1", "age": 40, "gender": "M", "marital": "MARRIED", "maternity_eligible": "N", "nationality_group": "OTHER", "w": 7.0}])


def test_review_invalid_rider_quote_is_not_quoted_never_priced():
    with tmpdir() as d:
        alpha, spec, parsed = _submission(d, lambda r: -500.0)
        v5 = v5_submission_integrity(parsed, spec, parsed.meta.get("structure_hash"), alpha, (0.7, 1.3))
        assert v5["counts"].get("RIDER_INVALID", 0) == sum(1 for t in parsed.kinds.values() if t == "ADDON")
        sub = to_catalogue(parsed, spec, "S", "synthetic", expiring=alpha, exclude=v5["invalid"])
        mods = [c for s in sub.scopes for c in s.components if c.type == "MODULE"]
        assert all(r["value"] is None and "not a number > 0" in r["source_ref"] for c in mods for r in c.rows)
        res, _ = evaluate(sub, _cells2(), {"fill": "default"})
        assert res.iloc[0]["status"] == "REFER" and "rider not quoted" in res.iloc[0]["reason"]


def test_review_riders_unread_without_keys_is_flagged():
    with tmpdir() as d:
        alpha, spec, parsed = _submission(d, lambda r: 100.0)
        wb = load_workbook(d / "s.xlsx")
        del wb["_KEYS"]
        wb.save(d / "nokeys.xlsx")
        p2 = parse_submission(d / "nokeys.xlsx", template_spec=spec)
        assert p2.positional
        v5 = v5_submission_integrity(p2, spec, p2.meta.get("structure_hash"), alpha, (0.7, 1.3))
        assert v5["counts"].get("RIDERS_UNREAD") == 1


def _opt_rows(rows):
    return [(i + 10, {"benefit": "Dental", "limit": lim, "copay": "20%", "network": net, "form": form,
                      "applies": app, "value": val}) for i, (lim, net, form, app, val) in enumerate(rows)]


def test_review_add_on_resolution_per_network():
    from pw.market_intake import _resolve_level
    F, A = "Flat per member", "All members"
    # exact GN row + other networks bridged from 'All'
    rows = _opt_rows([(1000, "All", F, A, 250.0), (5000, "All", F, A, 450.0), (2000, "GN", F, A, 300.0)])
    out, bridged, why = _resolve_level(rows, "Dental", "2000", "20%", ["CN", "GN", "VN"])
    got = {v["network"]: v["value"] for _, v in out}
    assert bridged and got == {"All": 300.0, "GN": 300.0}
    # an unoffered network with one row does not block bridging
    rows = _opt_rows([(1000, "All", F, A, 250.0), (5000, "All", F, A, 450.0), (1000, "RN", F, A, 999.0)])
    out, bridged, _ = _resolve_level(rows, "Dental", "2000", "20%", ["CN", "GN"])
    assert bridged and [(v["network"], v["value"]) for _, v in out] == [("All", 300.0)]
    # an exact limit stored as text "2000.0" is an exact match, not a bridge
    rows = _opt_rows([(1000, "All", F, A, 250.0), ("2000.0", "All", F, A, 400.0), (5000, "All", F, A, 450.0)])
    out, bridged, _ = _resolve_level(rows, "Dental", "2000", "20%", ["CN"])
    assert not bridged and out[0][1]["value"] == 400.0
    # a second form at the same limit is ignored only if it does not bracket; order of rows does not matter
    for order in ((0, 1, 2), (1, 0, 2)):
        base = [(1000, "All", F, A, 250.0), (1000, "All", F, "Principals", 200.0), (5000, "All", F, A, 450.0)]
        out, bridged, _ = _resolve_level(_opt_rows([base[i] for i in order]), "Dental", "2000", "20%", ["CN"])
        assert bridged and out[0][1]["value"] == 300.0 and out[0][1]["applies"] == A
    # same limit at two values in one form: ambiguous -> not priced; an offered network left uncovered -> not priced
    rows = _opt_rows([(1000, "All", F, A, 250.0), (1000, "All", F, A, 260.0), (5000, "All", F, A, 450.0)])
    assert _resolve_level(rows, "Dental", "2000", "20%", ["CN"])[0] == []
    rows = _opt_rows([(1000, "GN", F, A, 250.0), (5000, "GN", F, A, 450.0)])
    out, _, why = _resolve_level(rows, "Dental", "2000", "20%", ["CN", "GN"])
    assert out == [] and "CN" in why


def test_review_rider_value_currency_invariant_and_multiply_modules():
    alpha = catalogue("CAT_ALPHA")
    s = alpha.scopes[0]
    key = (s.scope_id, "P1", "module_maternity", "M10")
    v_aed = module_values(alpha, _cells2(), {key[2:]})[key]
    v_usd = module_values(alpha, _cells2(), {key[2:]}, {"currency": "USD", "fx": {"AED": 1.0, "USD": 3.6725}})[key]
    assert abs(v_aed - v_usd) < 1e-3                                              # a ratio has no currency
    mult = copy.deepcopy(alpha)
    mm = next(c for c in mult.scopes[0].components if c.type == "MODULE" and c.family == "module_maternity")
    mm.mode = "MULTIPLY"
    for r in mm.rows:
        if r["value"] is not None:
            r["value"] = 1.25
    v = module_values(mult, _cells2(), {key[2:]})[key]
    e0, _ = evaluate(mult, _cells2().assign(module_maternity=NONE_OPTION), {"fill": "default"})
    pb = e0["price_base"].to_numpy()
    assert abs(v - 3.0 * 0.25 * pb[0] / (3.0 * pb[0] + 7.0 * pb[1])) < 1e-4      # only the eligible female carries it


def test_review_split_adds_up_under_both_formula_orders():
    alpha = catalogue("CAT_ALPHA")
    for order in (None, ["BASE", "MODULES", "FACTORS"]):
        cat = copy.deepcopy(alpha)
        if order:
            for sc in cat.scopes:
                sc.formula.order = order
        res, _ = evaluate(cat, _cells2(), {"fill": "default"})
        for r in res.itertuples():
            assert abs(r.price_base + r.price_riders - r.premium_pre_loading) < 0.011, (order, r)
        assert res.iloc[0]["price_riders"] > 0 and res.iloc[1]["price_riders"] == 0.0


def test_review_presence_share_counts_all_peer_plans():
    from pw.benchmark import gap_register
    from pw.model import BenefitLine
    from pw.tiers import TierMap
    base = catalogue("CAT_ALPHA")

    def mk(cid, lines):
        c = copy.deepcopy(base)
        c.catalogue_id = cid
        c.scopes = [c.scopes[0]]
        c.scopes[0].plans = [c.scopes[0].plan("P1")]
        c.scopes[0].benefits = [BenefitLine(plan_id="P1", benefit_code=k, value=v) for k, v in lines.items()]
        return c
    subj = mk("SUBJ", {"physio_sessions": 0})
    market = [mk("M0", {"physio_sessions": 10})] + [mk(f"M{i}", {}) for i in range(1, 4)]
    tm = TierMap(pd.DataFrame({"catalogue_id": ["ANY"], "plan": ["P1"], "tier": ["T1"], "weight": ["1"]}), ["T1"])
    row = gap_register([subj] + market, {"SUBJ"}, tm).query("benefit_code == 'physio_sessions'").iloc[0]
    assert row["market_presence_share"] == 0.25 and row["assessment"] == "IN_LINE"   # 1 of 4 peers, not 1 of 1
