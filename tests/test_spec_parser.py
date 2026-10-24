import copy
import json

from _util import CATS, FIX, catalogue, raises, tmpdir

from pw import MappingRequired, SpecError
from pw.model import Catalogue
from pw.spec_parser import load_spec, parse_catalogue


def test_all_fixtures_parse_and_serialise_deterministically():
    for name in CATS:
        cat = catalogue(name)
        cat.validate()
        j1 = cat.to_json()
        j2 = parse_catalogue(FIX / name / "spec.json").to_json()
        assert j1 == j2, name
        again = Catalogue.from_dict(json.loads(j1))
        assert again.to_json() == j1, name


def test_component_types_present():
    seen = set()
    for name in CATS:
        for s in catalogue(name).scopes:
            seen.update(c.type for c in s.components)
    assert {"BASE_TABLE", "FACTOR_TABLE", "MODULE", "FEE", "LOADING", "REFER"} <= seen


def test_block_set_normalised_to_base_plus_implied_factor():
    s = catalogue("CAT_BETA").scopes[0]
    base = [c for c in s.components if c.type == "BASE_TABLE"]
    imp = [c for c in s.components if c.component_id == "blocks.implied"]
    assert len(base) == 1 and base[0].derived_from == "blocks"
    assert imp[0].reference_level == "NIL"
    vals = {r["key"]["copay_op_diag"]: r["value"] for r in imp[0].rows}
    assert vals == {"NIL": 1.0, "10%": 0.952, "20%": 0.916}
    assert set(imp[0].source_blocks) == {"10%", "20%"}


def test_reference_levels_explicit_per_key():
    s = catalogue("CAT_ALPHA").scopes[0]
    aml = next(c for c in s.components if c.component_id == "f_aml")
    assert aml.reference_level_by == "network" and aml.reference_level_by_key["N_PLAT"] == "2000000"
    for r in aml.rows:
        if aml.reference_level_by_key[r["key"]["network"]] == r["key"]["aml"]:
            assert r["value"] == 1.0


def test_dynamic_plans_networks_premium_basis_rules():
    a = catalogue("CAT_ALPHA")
    assert len(a.scopes[0].plans) == 7 and a.scopes[0].plan("P3").network_by_tpa["TPA_GREEN"] == "N_SILV"
    assert len(catalogue("CAT_GAMMA").scopes[0].plans) == 4
    d = catalogue("CAT_DELTA")
    assert d.premium_basis == "GROSS" and d.scopes[0].components[0].premium_basis == "GROSS"
    assert catalogue("CAT_IPMI").currency == "USD"
    assert {r.type for r in a.rules} == {"REFERRAL", "LOADING_CAP", "REVIEW"}
    assert any(b.status == "MANUAL_REVIEW" for b in a.scopes[0].benefits)


def test_spec_errors():
    spec = load_spec(FIX / "CAT_ALPHA" / "spec.json")
    bad = copy.deepcopy(spec)
    bad["scopes"][0]["components"][1]["reference_level"] = "5%"
    raises(SpecError, parse_catalogue, spec=bad, source_file=FIX / "CAT_ALPHA" / "source.xlsx")
    bad = copy.deepcopy(spec)
    del bad["maps"]["gender"]["Female"]
    raises(MappingRequired, parse_catalogue, spec=bad, source_file=FIX / "CAT_ALPHA" / "source.xlsx")
    bad = copy.deepcopy(spec)
    bad["scopes"][0]["components"][5]["rows"].append({"key": {"plan": "P2", "network_option": "OPT2"}, "value": 0.5})
    raises(SpecError, parse_catalogue, spec=bad, source_file=FIX / "CAT_ALPHA" / "source.xlsx")
    bad = copy.deepcopy(spec)
    bad["scopes"][0]["components"][6]["values"]["TPA_NOT_HERE"] = 1.0
    raises(MappingRequired, parse_catalogue, spec=bad, source_file=FIX / "CAT_ALPHA" / "source.xlsx")


def test_experience_rated_scope():
    spec = {"spec_id": "ER", "catalogue": {"catalogue_id": "ER", "owner": "F", "kind": "MARKET", "version": "1",
                                           "currency": "AED", "premium_basis": "NET"},
            "scopes": [{"scope_id": "GRP", "product_type": "GROUP", "regulator": "DHA", "rating_region": "RGN_A",
                        "tpa_set": ["TPA_RED"], "plans": [{"plan_id": "G", "label": "G"}],
                        "components": [{"type": "EXPERIENCE_RATED", "basis": {"target_lr": 0.8}}]}]}
    from pw.evaluator import evaluate
    cat = parse_catalogue(spec=spec)
    res, _ = evaluate(cat, [{"product_type": "GROUP", "rating_region": "RGN_A", "tpa": "TPA_RED", "plan": "G", "age": 40}])
    assert res.loc[0, "status"] == "EXPERIENCE_RATED" and res["price"].isna().all()


def test_catalogue_round_trip_file():
    with tmpdir() as d:
        c = catalogue("CAT_GAMMA")
        c.write(d / "c.json")
        assert Catalogue.read(d / "c.json").to_json() == c.to_json()
