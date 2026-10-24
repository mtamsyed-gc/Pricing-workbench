"""Validation gates (SPEC §5.1, §6): V0 contract check, V1 source reproduction, V2 block consistency,
V3 premium reconciliation, V4 template round trip, V5 submission integrity (stub; WS1 completes it)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import GateFailed
from .evaluator import evaluate, lookup_component
from .io_excel import WorkbookReader
from .model import Catalogue, canonical_key_str
from .registry import load_registry


# ------------------------------------------------------------------------------------------------------------ V0
def v0_contract(dim_life_path, manifest=None, contract_version=None, field_map=None, contracts_dir=None) -> dict:
    from .exposure import check_contract
    return check_contract(dim_life_path, manifest, contract_version, field_map, contracts_dir)


# ------------------------------------------------------------------------------------------------------------ V1
def v1_source_reproduction(cat: Catalogue, source_path: Path, raise_on_fail: bool = True) -> dict:
    """Every source cell recorded at parse time is (a) re-read raw from the workbook at its address and compared
    with the parsed value, and (b) looked up through the canonical catalogue (matching engine) at both ends of each
    range key; the lookup must return exactly the source value/status. BLOCK_SET levels are checked against the
    stored source blocks, and the evaluator (resolution SOURCE) must reproduce every block cell."""
    reg = load_registry()
    rd = WorkbookReader(source_path, data_only=True)
    idx = cat.meta.get("source_index", [])
    fails = []
    checked = 0
    by_comp = {}
    for e in idx:
        by_comp.setdefault((e["scope_id"], e["component_id"], e["level"]), []).append(e)
    for (sid, cid, level), entries in sorted(by_comp.items(), key=lambda x: (x[0][0], x[0][1], str(x[0][2]))):
        scope = cat.scope(sid)
        comp = next(c for c in scope.components if c.component_id == cid)
        if level is not None:
            implied = next(c for c in scope.components if c.component_id == f"{cid}.implied")
            ref_level = implied.reference_level
            if level == ref_level:
                rows, keys = comp.rows, comp.keys
            else:
                rows, keys = implied.source_blocks[level], comp.keys
        else:
            rows, keys = comp.rows, comp.keys
        probe_lo, probe_hi, meta = [], [], []
        for e in entries:
            sheet, ref = e["ref"].split("!")
            raw = rd.value(sheet, ref)
            if e["status"] == "VALUE":
                ok_raw = isinstance(raw, (int, float)) and float(raw) == e["raw"]
            else:
                ok_raw = isinstance(raw, str)
            if not ok_raw:
                fails.append({"scope_id": sid, "component_id": cid, "level": level, "ref": e["ref"],
                              "problem": "raw re-read differs", "raw": raw, "parsed": e["raw"]})
            for k in e["keys"]:
                full = {d: k.get(d, "ANY") for d in keys}
                lo = {d: (v[0] if isinstance(v, list) else v) for d, v in full.items()}
                hi = {d: (v[1] if isinstance(v, list) else v) for d, v in full.items()}
                probe_lo.append(lo)
                probe_hi.append(hi)
                meta.append(e)
        from .model import Component
        tmp = Component(component_id=cid, type="BASE_TABLE", keys=keys, rows=rows)
        for probes in (probe_lo, probe_hi):
            res = lookup_component(cat, sid, tmp, probes, reg).set_index("cell_id")
            for i, e in enumerate(meta):
                checked += 1
                if i not in res.index:
                    fails.append({"scope_id": sid, "component_id": cid, "level": level, "ref": e["ref"],
                                  "problem": "no canonical row matches the source key"})
                    continue
                r = res.loc[i]
                if e["status"] != r["__status"] or (e["status"] == "VALUE" and float(r["__value"]) != float(e["raw"])):
                    fails.append({"scope_id": sid, "component_id": cid, "level": level, "ref": e["ref"],
                                  "problem": "lookup differs", "lookup": r["__value"], "source": e["raw"],
                                  "matched": r["__matched"]})
    # evaluator reproduction of BLOCK_SET cells (resolution SOURCE)
    for s in cat.scopes:
        for comp in s.components:
            if comp.type != "FACTOR_TABLE" or not comp.source_blocks:
                continue
            base = next(c for c in s.components if c.component_id == comp.derived_from and c.type == "BASE_TABLE")
            levels = {comp.reference_level: base.rows, **comp.source_blocks}
            cells, expect = [], []
            tpa = s.tpa_set[0]
            for lvl, rows in sorted(levels.items()):
                for r in rows:
                    if r["status"] != "VALUE":
                        continue
                    c = {"product_type": s.product_type, "regulator": s.regulator, "rating_region": s.rating_region,
                         "tpa": tpa, comp.family: lvl}
                    for d, v in r["key"].items():
                        if v == "ANY":
                            continue
                        c[d] = v[0] if isinstance(v, list) else v
                    if "plan" not in c:
                        c["plan"] = s.plans[0].plan_id
                    cells.append(c)
                    expect.append(r["value"])
            if not cells:
                continue
            res, _ = evaluate(cat, pd.DataFrame(cells), {"fill": "reference", "resolution": "SOURCE", "include_fees": False})
            got = res["price"].to_numpy()
            exp = np.round(np.array(expect, dtype=float), s.formula.rounding)
            bad = np.where(~np.isclose(got, exp, rtol=0, atol=1e-9))[0]
            checked += len(cells)
            for i in bad[:50]:
                fails.append({"scope_id": s.scope_id, "component_id": comp.component_id, "problem": "evaluator (SOURCE) differs",
                              "cell": cells[i], "price": got[i], "source": exp[i]})
    out = {"gate": "V1", "status": "PASS" if not fails else "FAIL", "checked": checked, "failures": fails,
           "source_cells": len(idx)}
    if fails and raise_on_fail:
        raise GateFailed("V1", f"{len(fails)} source cells not reproduced (first: {fails[0]})", out)
    return out


# ------------------------------------------------------------------------------------------------------------ V2
def v2_block_consistency(cat: Catalogue) -> pd.DataFrame:
    """For each BLOCK_SET: block / reference block = one flat multiplier; cells deviating by more than the declared
    tolerance are flagged with the expected (derived) value. Resolution per spec (default DERIVED)."""
    reg = load_registry()
    recs = []
    for s in cat.scopes:
        for comp in s.components:
            if comp.type != "FACTOR_TABLE" or not comp.source_blocks:
                continue
            base = next(c for c in s.components if c.component_id == comp.derived_from and c.type == "BASE_TABLE")
            by_key = {json.dumps(r["key"], sort_keys=True): r for r in base.rows}
            tol = comp.block_check["tolerance_abs"]
            rnd = s.formula.rounding
            for lvl in sorted(comp.source_blocks):
                m = comp.block_check["multipliers"][lvl]
                for r in comp.source_blocks[lvl]:
                    b = by_key.get(json.dumps(r["key"], sort_keys=True))
                    if b is None or b["status"] != "VALUE" or r["status"] != "VALUE":
                        continue
                    exp = round(b["value"] * m, rnd)
                    dev = r["value"] - exp
                    recs.append({"scope_id": s.scope_id, "component_id": comp.derived_from, "level": lvl,
                                 "cell_key": canonical_key_str(r["key"], reg.order), "source_ref": r.get("source_ref"),
                                 "labels": json.dumps(r.get("labels", {}), sort_keys=True),
                                 "reference_value": b["value"], "source_value": r["value"], "multiplier": m,
                                 "multiplier_source": comp.block_check["multiplier_source"][lvl],
                                 "expected_value": exp, "ratio": r["value"] / b["value"] if b["value"] else np.nan,
                                 "deviation": dev, "flagged": abs(dev) > tol + 1e-9,
                                 "resolution": comp.block_check["resolution"]})
    cols = ["scope_id", "component_id", "level", "cell_key", "source_ref", "labels", "reference_value", "source_value",
            "multiplier", "multiplier_source", "expected_value", "ratio", "deviation", "flagged", "resolution"]
    return pd.DataFrame(recs, columns=cols)


# ------------------------------------------------------------------------------------------------------------ V3
V3_DEFAULT_CUT = ["product_type", "tpa", "rating_region", "plan"]


def v3_premium_reconciliation(cat: Catalogue, exposure_cells: pd.DataFrame, by=None, options=None) -> pd.DataFrame:
    """Expiring catalogue x exposure (default options) vs actual written premium by cut.
    implied_factor = actual / rated, on PRICED cells (captures co-pay mix, loadings, discounts): reported as a
    calibration, never hidden. Premium on REFER / UNMATCHED cells is reported beside it."""
    by = list(by or V3_DEFAULT_CUT)
    priced, _ = evaluate(cat, exposure_cells, {"fill": "default", **(options or {})})
    m = exposure_cells.merge(priced[["cell_id", "status", "price"]], on="cell_id")
    m["rated_prem"] = np.where(m["status"] == "PRICED", m["price"] * m["written_ly"], 0.0)
    m["actual_prem_priced"] = np.where(m["status"] == "PRICED", m["written_prem"], 0.0)
    m["actual_prem_unpriced"] = np.where(m["status"] != "PRICED", m["written_prem"], 0.0)
    m["written_ly_priced"] = np.where(m["status"] == "PRICED", m["written_ly"], 0.0)
    g = m.groupby(by, dropna=False, sort=True).agg(
        lives_inforce=("lives_inforce", "sum"), written_ly=("written_ly", "sum"), written_ly_priced=("written_ly_priced", "sum"),
        actual_prem=("written_prem", "sum"), actual_prem_priced=("actual_prem_priced", "sum"),
        actual_prem_unpriced=("actual_prem_unpriced", "sum"), rated_prem=("rated_prem", "sum")).reset_index()
    g["implied_factor"] = np.where(g["rated_prem"] > 0, g["actual_prem_priced"] / g["rated_prem"], np.nan)
    tot = g[["written_ly", "actual_prem", "actual_prem_priced", "rated_prem"]].sum()
    total = {c: None for c in by}
    total[by[0]] = "TOTAL"
    total.update({k: float(g[k].sum()) for k in ["lives_inforce", "written_ly", "written_ly_priced", "actual_prem",
                                                  "actual_prem_priced", "actual_prem_unpriced", "rated_prem"]})
    total["implied_factor"] = tot["actual_prem_priced"] / tot["rated_prem"] if tot["rated_prem"] else np.nan
    return pd.concat([g, pd.DataFrame([total])], ignore_index=True)


# ------------------------------------------------------------------------------------------------------------ V4
def v4_round_trip(template_spec: dict, workdir: Path, expiring: Catalogue | None = None, seed: int = 4) -> dict:
    """Generate the template, fill every input cell with a deterministic synthetic value, parse it back by key;
    the parsed values (and the structure hash) must be identical."""
    from .template.generator import generate_template
    from .template.parser import fill_template, parse_submission
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    tid = template_spec.get("tender_id", "T")
    out = workdir / f"{tid}_template.xlsx"
    gen = generate_template(template_spec, out, expiring=expiring)
    filled = workdir / f"{tid}_filled.xlsx"
    written = fill_template(out, filled, seed=seed)
    parsed = parse_submission(filled, template_spec=template_spec)
    got = parsed.values
    diffs = [k for k in sorted(set(written) | set(got)) if written.get(k) != got.get(k)]
    res = {"gate": "V4", "status": "PASS" if not diffs and parsed.hash_ok else "FAIL", "cells": len(written),
           "diffs": diffs[:20], "n_diffs": len(diffs), "hash_ok": parsed.hash_ok, "structure_hash": gen.structure_hash,
           "warnings": parsed.warnings}
    if res["status"] != "PASS":
        raise GateFailed("V4", f"{len(diffs)} differences, hash_ok={parsed.hash_ok}", res)
    return res


# ------------------------------------------------------------------------------------------------------------ V5
def v5_submission_integrity(submission_path: Path, issued_hash: str | None = None) -> dict:
    """STUB (WS0): structure-hash check only. WS1 adds mandatory-cell (numeric > 0) checks and outlier ratio bands
    vs expiring (SPEC §6 V5)."""
    from .template.parser import read_meta
    meta = read_meta(submission_path)
    ok = issued_hash is None or meta.get("structure_hash") == issued_hash
    return {"gate": "V5", "status": "STUB", "hash_ok": ok, "structure_hash": meta.get("structure_hash"),
            "note": "WS1 completes V5: mandatory numeric > 0, outliers vs expiring"}
