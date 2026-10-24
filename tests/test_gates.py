import copy

from _util import CATS, FIX, catalogue, load_json, raises

from pw import GateFailed
from pw.exposure import build_exposure
from pw.gates import v1_source_reproduction, v2_block_consistency, v3_premium_reconciliation, v5_submission_integrity


def test_v1_every_fixture():
    for name in CATS:
        r = v1_source_reproduction(catalogue(name), FIX / name / "source.xlsx")
        assert r["status"] == "PASS" and r["checked"] >= r["source_cells"], name


def test_v1_detects_a_changed_cell():
    cat = copy.deepcopy(catalogue("CAT_ALPHA"))
    base = cat.scopes[0].components[0]
    row = next(r for r in base.rows if r["status"] == "VALUE")
    row["value"] += 0.01
    r = v1_source_reproduction(cat, FIX / "CAT_ALPHA" / "source.xlsx", raise_on_fail=False)
    assert r["status"] == "FAIL" and any(f["problem"] == "lookup differs" for f in r["failures"])
    raises(GateFailed, v1_source_reproduction, cat, FIX / "CAT_ALPHA" / "source.xlsx")


def test_v2_finds_the_five_planted_cells_with_expected_values():
    exp = load_json(FIX / "CAT_BETA" / "expected_v2.json")
    df = v2_block_consistency(catalogue("CAT_BETA"))
    flagged = df[df["flagged"]]
    assert len(flagged) == 5
    got = sorted((round(r.source_value, 2), round(r.expected_value, 2)) for r in flagged.itertuples())
    want = sorted((p["source_value"], p["expected_value"]) for p in exp["planted"])
    assert got == want
    assert set(flagged["level"]) == {"20%"}
    mult = df.drop_duplicates("level").set_index("level")["multiplier"].to_dict()
    assert mult == exp["multipliers"]
    for name in ("CAT_ALPHA", "CAT_GAMMA"):
        assert v2_block_consistency(catalogue(name)).empty


def test_v3_on_expo_syn_by_product_tpa_region_plan():
    d = FIX / "EXPO_SYN"
    ex = build_exposure(d / "dim_life.csv", d / "maps", d / "run_manifest.csv", strict=False)
    v3 = v3_premium_reconciliation(catalogue("CAT_ALPHA"), ex.cells)
    body = v3[v3["product_type"] != "TOTAL"]
    assert list(v3.columns[:4]) == ["product_type", "tpa", "rating_region", "plan"]
    assert len(body) == 21                              # 3 TPAs x 7 plans
    assert body["implied_factor"].between(0.9, 1.1).all()
    blue = body[body["tpa"] == "TPA_BLUE"]["actual_prem_priced"].sum() / body[body["tpa"] == "TPA_BLUE"]["rated_prem"].sum()
    red = body[body["tpa"] == "TPA_RED"]["actual_prem_priced"].sum() / body[body["tpa"] == "TPA_RED"]["rated_prem"].sum()
    assert 1.01 < blue / red < 1.03                     # the synthetic +2% on TPA_BLUE is recovered
    tot = v3[v3["product_type"] == "TOTAL"].iloc[0]
    assert abs(tot["actual_prem"] - (tot["actual_prem_priced"] + tot["actual_prem_unpriced"])) < 1e-6
    assert tot["actual_prem_unpriced"] > 0              # REFER premium reported beside, not hidden


def test_v5_clean_submission_passes():
    import json
    from pw.template.parser import parse_submission, read_meta
    spec = json.loads((FIX / "T_ALPHA" / "template_spec.json").read_text(encoding="utf-8"))
    p = parse_submission(FIX / "SUB_X" / "submission.xlsx", template_spec=spec)
    r = v5_submission_integrity(p, spec, read_meta(FIX / "T_ALPHA" / "template.xlsx")["structure_hash"], catalogue("CAT_ALPHA"))
    assert r["status"] == "PASS" and r["hash_ok"] and not r["invalid"] and r["rate_cells"] == 618
