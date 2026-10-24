"""Validation gates (SPEC §5.1, §6): V0 contract check, V1 source reproduction, V2 block consistency,
V3 premium reconciliation, V4 template round trip, V5 submission integrity (stub; WS1 completes it)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import GateFailed, SpecError
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
                ev = e.get("value", e["raw"])
                if e["status"] != r["__status"] or (e["status"] == "VALUE" and float(r["__value"]) != float(ev)):
                    fails.append({"scope_id": sid, "component_id": cid, "level": level, "ref": e["ref"],
                                  "problem": "lookup differs", "lookup": r["__value"], "source": ev,
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
DEFAULT_OUTLIER_BAND = (0.7, 1.3)
V5_FLAGS = ("HASH_MISMATCH", "KEYS_TAMPERED", "POSITIONAL_PARSE", "BLANK", "NON_NUMERIC", "NOT_POSITIVE", "OUTLIER",
            "NO_EXPIRING", "MULTIPLIER_OUTLIER")


def v5_submission_integrity(parsed, template_spec: dict, issued_hash: str | None, expiring: Catalogue | None = None,
                            outlier_band=None, multiplier_band=None) -> dict:
    """V5 (SPEC §6): structure hash = issued; every mandatory cell numeric > 0; outliers vs expiring flagged
    (ratio submitted / expiring base outside the run's band). Failure action: flag to user (never stops).
    Returns {status: PASS|FLAGGED, flags: DataFrame[cell_key, flag, value, expiring, ratio, detail], invalid: set}.
    'invalid' = cells whose value cannot be used (BLANK, NON_NUMERIC, NOT_POSITIVE): ingest excludes them."""
    from .evaluator import lookup_component
    from .registry import load_registry
    reg = load_registry()
    lo, hi = outlier_band or DEFAULT_OUTLIER_BAND
    recs = []

    def flag(ck, f, value=None, exp=None, ratio=None, detail=""):
        recs.append({"cell_key": ck, "flag": f, "value": value, "expiring": exp, "ratio": ratio, "detail": detail})

    meta_hash = parsed.meta.get("structure_hash")
    if issued_hash is None:
        flag("_META", "HASH_MISMATCH", detail="no issued hash supplied to compare against")
    elif meta_hash != issued_hash:
        flag("_META", "HASH_MISMATCH", detail=f"submitted {str(meta_hash)[:12]} != issued {issued_hash[:12]}")
    if parsed.recomputed_hash != issued_hash and not parsed.positional:
        flag("_KEYS", "KEYS_TAMPERED", detail="_KEYS content does not hash to the issued structure hash")
    if parsed.positional:
        flag("_KEYS", "POSITIONAL_PARSE", detail="_KEYS sheet missing: values read by position")
    invalid = set()
    probes = {}
    for ck, kind in sorted(parsed.kinds.items()):
        if kind != "RATE":
            continue
        v = parsed.values.get(ck)
        if v is None:
            flag(ck, "BLANK", detail="mandatory rate cell is blank")
            invalid.add(ck)
        elif not isinstance(v, float):
            flag(ck, "NON_NUMERIC", value=str(v))
            invalid.add(ck)
        elif v <= 0:
            flag(ck, "NOT_POSITIVE", value=v)
            invalid.add(ck)
        else:
            probes[ck] = v
    if expiring is not None and probes:
        by_scope = {}
        for ck in probes:
            k = parsed.keys[ck][0]
            scope = next((s for s in expiring.scopes if s.product_type == k.get("product_type")
                          and s.rating_region == k.get("rating_region")
                          and (k.get("tpa") in s.tpa_set or "ANY" in s.tpa_set)), None)
            if scope is None:
                flag(ck, "NO_EXPIRING", value=probes[ck], detail="no expiring scope for this block")
                continue
            by_scope.setdefault(scope.scope_id, []).append(ck)
        for sid, cks in sorted(by_scope.items()):
            scope = expiring.scope(sid)
            base = next(c for c in scope.components if c.type == "BASE_TABLE")
            keys = []
            for ck in cks:
                k = parsed.keys[ck][0]
                keys.append({d: (v[0] if isinstance(v, list) else v) for d, v in k.items() if d in base.keys})
            res = lookup_component(expiring, sid, base, keys, reg).set_index("cell_id")
            for i, ck in enumerate(cks):
                v = probes[ck]
                if i not in res.index or res.loc[i, "__status"] != "VALUE":
                    flag(ck, "NO_EXPIRING", value=v, detail="no priced expiring base cell")
                    continue
                e = float(res.loc[i, "__value"])
                r = v / e
                if r < lo or r > hi:
                    flag(ck, "OUTLIER", value=v, exp=e, ratio=r, detail=f"ratio outside [{lo}, {hi}]")
    if parsed.positional and ((template_spec or {}).get("reference_sheets") or {}).get("addons") == "FILL":
        flag("_KEYS", "RIDERS_UNREAD", detail="_KEYS sheet missing: rider quotes cannot be located, every rider is priced "
                                               "as not quoted - ask for the file with its _KEYS sheet")
    # riders (Add-ons sheet in FILL mode): blank = not quoted (priced as missing, not invalid); quoted values vs the
    # expiring rider rate on the same band (owner decision 24 Oct 2026, HANDOVER items 11 and 14)
    for ck, kind in sorted(parsed.kinds.items()):
        if kind != "ADDON":
            continue
        v = parsed.values.get(ck)
        if v is None:
            flag(ck, "RIDER_NOT_QUOTED", detail="rider rate left blank: priced as missing")
            continue
        if not isinstance(v, float) or v <= 0:
            flag(ck, "RIDER_INVALID", value=str(v), detail="rider rate must be a number > 0: treated as not quoted")
            continue
        if expiring is None:
            continue
        k = dict(parsed.keys[ck][0])
        sid, cid = k.pop("scope_id", None), k.pop("component_id", None)
        e = None
        try:
            comp = next(c for c in expiring.scope(sid).components if c.component_id == cid)
            want = json.dumps(k, sort_keys=True)
            row = next((r for r in comp.rows if json.dumps(r["key"], sort_keys=True) == want), None)
            e = row["value"] if row is not None and row.get("status", "VALUE") == "VALUE" else None
        except (StopIteration, KeyError, SpecError):
            e = None
        if e is None or not float(e) > 0:
            flag(ck, "RIDER_NO_EXPIRING", value=v, detail="no priced expiring rider rate")
            continue
        r = v / float(e)
        if r < lo or r > hi:
            flag(ck, "RIDER_OUTLIER", value=v, exp=float(e), ratio=r, detail=f"ratio outside [{lo}, {hi}]")
    if multiplier_band is not None:
        mlo, mhi = multiplier_band
        for ck, kind in sorted(parsed.kinds.items()):
            v = parsed.values.get(ck)
            if kind == "MULTIPLIER" and isinstance(v, float) and not (mlo <= v <= mhi):
                flag(ck, "MULTIPLIER_OUTLIER", value=v, detail=f"proposed multiplier outside [{mlo}, {mhi}]")
    flags = pd.DataFrame(recs, columns=["cell_key", "flag", "value", "expiring", "ratio", "detail"])
    n_rate = sum(1 for k in parsed.kinds.values() if k == "RATE")
    counts = flags["flag"].value_counts().to_dict() if len(flags) else {}
    return {"gate": "V5", "status": "PASS" if flags.empty else "FLAGGED", "flags": flags, "invalid": invalid,
            "counts": {k: int(v) for k, v in sorted(counts.items())}, "rate_cells": n_rate,
            "hash_ok": not any(f in counts for f in ("HASH_MISMATCH", "KEYS_TAMPERED", "POSITIONAL_PARSE")),
            "band": [lo, hi]}
