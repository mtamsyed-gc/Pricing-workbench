"""Exposure builder, gate V0 (pinned IP4-8 and a synthetic contract version with one renamed column), coverage."""
import csv
import json

from _util import FIX, REPO, catalogue, raises, tmpdir

from pw import GateFailed, MappingRequired
from pw.exposure import build_exposure, check_contract, coverage_report, load_field_map, read_manifest

D = FIX / "EXPO_SYN"
RENAMED_FROM, RENAMED_TO = "Region Group", "RegionGroupName"
SYN_VERSION = "SYN-IP4-9"


def _syn_contract_run(d, with_map: bool):
    """Synthetic Merit contract version: IP4-8 with one renamed dim_life column; the run's dim_life uses it."""
    pinned = json.loads((REPO / "contracts" / "merit_model_contract_IP4-8.json").read_text(encoding="utf-8"))
    syn = json.loads(json.dumps(pinned))
    syn["version"] = SYN_VERSION
    syn["tables"]["dim_life"]["columns"] = [[RENAMED_TO if c == RENAMED_FROM else c, t]
                                            for c, t in syn["tables"]["dim_life"]["columns"]]
    cdir = d / "contracts"
    cdir.mkdir()
    (cdir / "merit_model_contract_IP4-8.json").write_text(json.dumps(pinned), encoding="utf-8")
    (cdir / f"merit_model_contract_{SYN_VERSION}.json").write_text(json.dumps(syn), encoding="utf-8")
    fm = load_field_map()
    if with_map:
        v = json.loads(json.dumps(fm["versions"]["IP4-8"]))
        v["required"]["region_group"] = RENAMED_TO
        fm["versions"][SYN_VERSION] = v
    with (D / "dim_life.csv").open(newline="", encoding="utf-8") as f, (d / "dim_life.csv").open("w", newline="", encoding="utf-8") as g:
        r = csv.reader(f)
        w = csv.writer(g, lineterminator="\n")
        hdr = next(r)
        w.writerow([RENAMED_TO if h == RENAMED_FROM else h for h in hdr])
        w.writerows(r)
    return cdir, fm


def test_v0_same_version_ok():
    r = check_contract(D / "dim_life.csv", read_manifest(D / "run_manifest.csv"))
    assert r["status"] == "OK" and r["version"] == "IP4-8" and not r["missing"]


def test_v0_synthetic_renamed_column_with_field_map_entry_proceeds():
    with tmpdir() as d:
        cdir, fm = _syn_contract_run(d, with_map=True)
        # pinned + field-map entry: same version, proceed
        r = check_contract(d / "dim_life.csv", {"contract_version": SYN_VERSION}, field_map=fm, contracts_dir=cdir)
        assert r["status"] == "OK" and r["map_version"] == SYN_VERSION
        # field-map entry but contract not pinned (new version): proceed with a warning and the column diff
        r = check_contract(d / "dim_life.csv", {"contract_version": SYN_VERSION}, field_map=fm)
        assert r["status"] == "WARN" and r["column_diff"] == {"added": [RENAMED_TO], "removed": [RENAMED_FROM]}
        ex = build_exposure(d / "dim_life.csv", D / "maps", contract_version=SYN_VERSION, field_map=fm, strict=False)
        ex0 = build_exposure(D / "dim_life.csv", D / "maps", D / "run_manifest.csv", strict=False)
        assert ex.cells.drop(columns="cell_id").equals(ex0.cells.drop(columns="cell_id"))


def test_v0_renamed_column_without_map_entry_stops():
    with tmpdir() as d:
        cdir, fm = _syn_contract_run(d, with_map=False)
        r = check_contract(d / "dim_life.csv", {"contract_version": SYN_VERSION}, field_map=fm, contracts_dir=cdir)
        assert r["status"] == "STOP" and r["missing"] == [{"field": "region_group", "column": RENAMED_FROM}]
        e = raises(GateFailed, build_exposure, d / "dim_life.csv", D / "maps", contract_version=SYN_VERSION, field_map=fm)
        assert e.gate == "V0"


def test_v0_unknown_version_all_fields_present_warns():
    r = check_contract(D / "dim_life.csv", {"contract_version": "IP4-99"})
    assert r["status"] == "WARN" and any("not pinned" in m for m in r["messages"])


def test_exposure_cells_and_mapping_required():
    e = raises(MappingRequired, build_exposure, D / "dim_life.csv", D / "maps", D / "run_manifest.csv")
    assert all(i["map"] == "plan_map.csv" and i["source_plan"] == "Plan 9 Legacy" for i in e.items)
    ex = build_exposure(D / "dim_life.csv", D / "maps", D / "run_manifest.csv", strict=False, snapshot_date="2025-07-01")
    c = ex.cells
    assert {"product_type", "tpa", "plan", "age", "member_category", "maternity_eligible", "written_ly", "written_prem",
            "lives_inforce", "uwy"} <= set(c.columns)
    assert set(c["member_category"]) == {"EMPLOYEE", "SPOUSE", "CHILD", "PARENT"}
    assert c["lives_inforce"].sum() > 0
    assert abs(c["written_prem"].sum() + ex.unmatched_rows["written_prem"].sum()
               - sum(float(r["WrittenPrem_Net"]) for r in csv.DictReader((D / "dim_life.csv").open(encoding="utf-8")))) < 1e-4


def test_coverage_report_and_gate():
    ex = build_exposure(D / "dim_life.csv", D / "maps", D / "run_manifest.csv", strict=False)
    rep = coverage_report(catalogue("CAT_ALPHA"), ex)
    assert rep["status"] == "PASS" and rep["matched_share"] >= 0.95
    st = rep["by_status"].set_index("status")
    assert {"PRICED", "REFER", "UNMATCHED"} == set(st.index)
    assert abs(st["written_prem_share"].sum() - 1.0) < 1e-9
    assert rep["defaulted_share"]["copay_op_diag"] > 0.9       # Merit has no co-pay field: catalogue default used
    assert rep["network_mismatch_share"] == 0.0
    raises(GateFailed, coverage_report, catalogue("CAT_ALPHA"), ex, threshold=0.999)
