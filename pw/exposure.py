"""Exposure builder (SPEC §5, §5.1): Merit-shaped dim_life -> canonical ExposureCells, with gate V0 and the
coverage report (priced / refer / unmatched; gate at 95% of premium matched).

The workbench depends on Merit only through its output contract (contracts/merit_model_contract_<v>.json) and
contracts/merit_field_map.json (canonical field -> Merit column). Mapping tables live per run in runs/<id>/maps/:

  segment_map.csv          policy_type, region_group -> product_type, regulator, rating_region
  tpa_map.csv              source_tpa -> tpa                                  (optional; identity when absent)
  plan_map.csv             product_type, rating_region, tpa, source_plan -> plan
  network_map.csv          tpa, source_network -> network                     (consistency check vs plan network)
  member_category_map.csv  product_type, relation -> member_category
  nationality_map.csv      source_group -> nationality_group
  value_map.csv            dim, source_value -> value   (gender, marital, maternity_eligible from Gender Group)
Key columns accept ANY. Unmapped values raise MappingRequired (strict) or are carried as UNMATCHED with the reason.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import REPO_DIR, GateFailed, MappingRequired
from .registry import ANY

CONTRACTS_DIR = REPO_DIR / "contracts"
NUMERIC_FIELDS = {"age": "int", "uwy": "int", "group_size": "int", "written_ly_net": "float", "written_ly_gross": "float",
                  "written_prem_net": "float", "written_prem_gross": "float", "earned_ly_net": "float",
                  "earned_prem_net": "float", "earned_ly_gross": "float", "earned_prem_gross": "float",
                  "zp_net": "int", "zp_gross": "int"}
CELL_KEY = ["product_type", "regulator", "rating_region", "tpa", "plan", "network_exposure", "age", "gender", "marital",
            "member_category", "maternity_eligible", "nationality_group", "group_size_band", "uwy", "new_renewal", "distribution"]
MEASURES = ["records", "lives_inforce", "written_ly", "written_prem", "earned_ly", "earned_prem"]
DEFAULT_COVERAGE_THRESHOLD = 0.95


# ------------------------------------------------------------------------------------------------- V0 contract check
def _columns_of(path: Path) -> list[str]:
    path = Path(path)
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq
        return list(pq.read_schema(path).names)
    with path.open(newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f))


def read_manifest(path: Path | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        return {row["Key"]: row["Value"] for row in r}


def load_field_map(path: Path | None = None) -> dict:
    return json.loads(Path(path or CONTRACTS_DIR / "merit_field_map.json").read_text(encoding="utf-8"))


def _version_key(v: str):
    """Order Merit contract versions by number (IP4-8 < IP4-9 < IP4-11); plain string order puts IP4-9 last."""
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(v))]


def pinned_contracts(contracts_dir: Path | None = None) -> dict:
    out = {}
    for p in sorted(Path(contracts_dir or CONTRACTS_DIR).glob("merit_model_contract_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        out[d["version"]] = d
    return out


def check_contract(dim_life_path: Path, manifest: dict | None = None, contract_version: str | None = None,
                   field_map: dict | None = None, contracts_dir: Path | None = None, table: str = "dim_life") -> dict:
    """Gate V0 (SPEC §5.1). Returns {status: OK | WARN | STOP, version, map_version, missing, column_diff, messages}."""
    fm = field_map or load_field_map()
    pins = pinned_contracts(contracts_dir)
    cols = _columns_of(dim_life_path)
    version = contract_version or (manifest or {}).get("contract_version")
    msgs = []
    if version in fm["versions"]:
        map_version = version
    else:
        map_version = max(fm["versions"], key=_version_key)
        msgs.append(f"contract version {version!r} has no field map entry; checking against field map {map_version}"
                    if version else f"run declares no contract version; checking against field map {map_version}")
    req = fm["versions"][map_version]["required"]
    missing = [{"field": f, "column": c} for f, c in req.items() if c not in cols]
    ref = pins.get(version) or pins.get(map_version) or (pins[max(pins, key=_version_key)] if pins else None)
    ref_cols = [c for c, _ in ref["tables"][table]["columns"]] if ref else []
    diff = {"added": [c for c in cols if c not in ref_cols], "removed": [c for c in ref_cols if c not in cols]}
    if missing:
        status = "STOP"
        msgs.append("required field(s) missing or renamed without a field-map entry: "
                    + ", ".join(f"{m['field']} ({m['column']})" for m in missing))
    elif version in pins and not diff["added"] and not diff["removed"]:
        status = "OK"
    else:
        status = "WARN"
        if version not in pins:
            msgs.append(f"contract version {version!r} is not pinned in contracts/; proceeding (all required fields present)")
        if diff["added"] or diff["removed"]:
            msgs.append(f"column diff vs pinned {ref['version'] if ref else '?'}: {diff}")
    return {"gate": "V0", "status": status, "version": version, "map_version": map_version, "missing": missing,
            "column_diff": diff, "messages": msgs}


# ------------------------------------------------------------------------------------------------- mapping tables
def _read_map(maps_dir: Path, name: str, required: bool = True) -> pd.DataFrame | None:
    p = Path(maps_dir) / name
    if not p.exists():
        if required:
            raise MappingRequired(f"mapping table {name} not found in {maps_dir}", [{"map": name}])
        return None
    return pd.read_csv(p, dtype=str, keep_default_na=False).astype(object)


def _resolve(df: pd.DataFrame, mp: pd.DataFrame, keys: dict, outs: list[str], map_name: str):
    """keys: df column -> map column. Wildcard ANY in map key columns; most specific map row wins.
    Returns (resolved DataFrame aligned to df.index with outs columns, list of unmapped combos)."""
    kcols = list(keys)
    combos = df[kcols].drop_duplicates()
    rows = mp.to_dict("records")
    resolved, unmapped = {}, []
    for combo in combos.itertuples(index=False, name=None):
        best, best_score = None, -1
        for r in rows:
            score, ok = 0, True
            for dc, mc in keys.items():
                want = combo[kcols.index(dc)]
                mv = r[mc]
                if mv == ANY:
                    continue
                if str(mv) != ("" if want is None else str(want)):
                    ok = False
                    break
                score += 1
            if ok and score > best_score:
                best, best_score = r, score
            elif ok and score == best_score and best is not None and any(best[o] != r[o] for o in outs):
                raise MappingRequired(f"{map_name}: ambiguous rows for {dict(zip(kcols, combo))}",
                                      [{"map": map_name, **dict(zip(kcols, combo))}])
        if best is None:
            unmapped.append(dict(zip(kcols, combo)))
            resolved[combo] = {o: None for o in outs}
        else:
            resolved[combo] = {o: best[o] for o in outs}
    keys_series = list(df[kcols].itertuples(index=False, name=None))
    out = pd.DataFrame([resolved[k] for k in keys_series], index=df.index, columns=outs).astype(object)
    return out, unmapped


@dataclass
class ExposureResult:
    cells: pd.DataFrame
    unmapped: list = field(default_factory=list)          # [{map, keys..., records, written_prem}]
    unmatched_rows: pd.DataFrame | None = None            # aggregated rows that failed mapping
    v0: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def read_dim_life(path: Path, field_map: dict, map_version: str) -> pd.DataFrame:
    fmv = field_map["versions"][map_version]
    cols = _columns_of(path)
    sel = {**fmv["required"], **{k: v for k, v in fmv.get("optional", {}).items() if v in cols}}
    con = duckdb.connect(":memory:")
    try:
        if Path(path).suffix.lower() == ".parquet":
            src = f"read_parquet('{Path(path).as_posix()}')"
        else:
            src = f"read_csv('{Path(path).as_posix()}', header=true, all_varchar=true)"
        proj = ", ".join(f'"{c}" AS "{k}"' for k, c in sel.items())
        df = con.execute(f"SELECT {proj} FROM {src}").df()
    finally:
        con.close()
    for k, t in NUMERIC_FIELDS.items():
        if k in df.columns:
            v = pd.to_numeric(df[k].replace("", None), errors="coerce")
            df[k] = v.astype("Int64") if t == "int" else v.astype("float64")
    for k in df.columns:
        if k not in NUMERIC_FIELDS:
            df[k] = df[k].astype(object).where(df[k].notna(), None)
            df[k] = df[k].map(lambda x: None if x is None or x == "" else x)
    return df


def build_exposure(dim_life_path: Path, maps_dir: Path, manifest_path: Path | None = None, contract_version: str | None = None,
                   field_map: dict | None = None, snapshot_date: str | None = None, uwy: int | None = None,
                   basis: str = "NET", strict: bool = True) -> ExposureResult:
    fm = field_map or load_field_map()
    v0 = check_contract(dim_life_path, read_manifest(manifest_path), contract_version, fm)
    if v0["status"] == "STOP":
        raise GateFailed("V0", "; ".join(v0["messages"]), v0)
    df = read_dim_life(dim_life_path, fm, v0["map_version"])
    notes = list(v0["messages"])
    if uwy is not None:
        df = df[df["uwy"] == uwy].copy()
    b = basis.lower()
    df["written_ly"] = df[f"written_ly_{b}"]
    df["written_prem"] = df[f"written_prem_{b}"]
    df["earned_ly"] = df.get(f"earned_ly_{b}", pd.Series(np.nan, index=df.index))
    df["earned_prem"] = df.get(f"earned_prem_{b}", pd.Series(np.nan, index=df.index))
    df["records"] = 1
    df["group_size_band"] = df["group_size"]     # numeric-range dim: cells carry the integer group size
    if snapshot_date and "cov_start" in df.columns and "cov_end" in df.columns:
        zp = df.get(f"zp_{b}", pd.Series(1, index=df.index)).fillna(1)
        inf = (df["cov_start"] <= snapshot_date) & (df["cov_end"] >= snapshot_date) & (zp == 1)
        df["lives_inforce"] = inf.astype("int64")
    else:
        df["lives_inforce"] = np.nan
        notes.append("lives_inforce not computed (no snapshot_date or CovStart/CovEnd); use written_ly")

    unmapped = []
    reason = pd.Series([None] * len(df), index=df.index, dtype=object)

    def flag(mask_idx, txt):
        cur = reason.loc[mask_idx]
        reason.loc[cur[cur.isna()].index] = txt

    def run_map(name, keys, outs, rename=None, required=True):
        mp = _read_map(maps_dir, name, required)
        if mp is None:
            return None
        res, um = _resolve(df, mp, keys, outs, name)
        for u in um:
            m = np.ones(len(df), dtype=bool)
            for k, v in u.items():
                m &= (df[k].astype(object).map(lambda x: "" if x is None else str(x)) == ("" if v is None else str(v))).to_numpy()
            unmapped.append({"map": name, **{k: v for k, v in u.items()}, "records": int(m.sum()),
                             "written_prem": float(df.loc[m, "written_prem"].sum())})
            flag(df.index[m], f"MappingRequired: {name} {u}")
        for o in outs:
            df[(rename or {}).get(o, o)] = res[o]
        return res

    run_map("segment_map.csv", {"policy_type": "policy_type", "region_group": "region_group"},
            ["product_type", "regulator", "rating_region"])
    tm = _read_map(maps_dir, "tpa_map.csv", required=False)
    df["source_tpa"] = df["tpa"]
    if tm is not None:
        run_map("tpa_map.csv", {"source_tpa": "source_tpa"}, ["tpa"])
    df["source_plan"] = df["plan_label"]
    run_map("plan_map.csv", {"product_type": "product_type", "rating_region": "rating_region", "tpa": "tpa",
                             "source_plan": "source_plan"}, ["plan"])
    df["source_network"] = df["network"]
    run_map("network_map.csv", {"tpa": "tpa", "source_network": "source_network"}, ["network"],
            rename={"network": "network_exposure"})
    run_map("member_category_map.csv", {"product_type": "product_type", "relation": "relation"}, ["member_category"])
    df["source_group"] = df["nationality_group"]
    run_map("nationality_map.csv", {"source_group": "source_group"}, ["nationality_group"])
    vm = _read_map(maps_dir, "value_map.csv")
    for dim, src in (("gender", "gender"), ("marital", "marital"), ("maternity_eligible", "gender_group")):
        sub = vm[vm["dim"] == dim][["source_value", "value"]]
        df[f"__src_{dim}"] = df[src]
        res, um = _resolve(df, sub, {f"__src_{dim}": "source_value"}, ["value"], f"value_map.csv[{dim}]")
        for u in um:
            v = u[f"__src_{dim}"]
            m = (df[f"__src_{dim}"].astype(object).map(lambda x: "" if x is None else str(x)) == ("" if v is None else str(v))).to_numpy()
            unmapped.append({"map": f"value_map.csv[{dim}]", "source_value": v, "records": int(m.sum()),
                             "written_prem": float(df.loc[m, "written_prem"].sum())})
            flag(df.index[m], f"MappingRequired: value_map.csv[{dim}] '{v}'")
        df[dim] = res["value"]
    miss_age = df["age"].isna()
    if miss_age.any():
        flag(df.index[miss_age], "missing age (DOB) - flagged, not banded")
        unmapped.append({"map": "age", "records": int(miss_age.sum()), "written_prem": float(df.loc[miss_age, "written_prem"].sum())})
    if strict and unmapped:
        raise MappingRequired(f"{len(unmapped)} unmapped value group(s); see items", unmapped)

    df["__reason"] = reason
    for c in CELL_KEY:
        if c not in df.columns:
            df[c] = None
    key_obj = [c for c in CELL_KEY if c not in ("age", "group_size_band", "uwy")]
    for c in key_obj:
        df[c] = df[c].astype(object).map(lambda x: "" if x is None else str(x))
    good = df[df["__reason"].isna()]
    bad = df[df["__reason"].notna()]
    agg = {m: "sum" for m in MEASURES}
    cells = good.groupby(CELL_KEY, dropna=False, sort=True).agg(agg).reset_index()
    bad_agg = bad.groupby(["__reason"], dropna=False, sort=True).agg(agg).reset_index() if len(bad) else None
    for c in key_obj:
        cells[c] = cells[c].map(lambda x: None if x == "" else x).astype(object)
    cells.insert(0, "cell_id", np.arange(len(cells), dtype="int64"))
    return ExposureResult(cells=cells, unmapped=unmapped, unmatched_rows=bad_agg, v0=v0, notes=notes)


# ------------------------------------------------------------------------------------------------- coverage report
def coverage_report(cat, expo: ExposureResult, options: dict | None = None, threshold: float = DEFAULT_COVERAGE_THRESHOLD,
                    measure: str = "written_prem", raise_on_fail: bool = True) -> dict:
    """Share of lives / premium matched to a priced cell, to a REFER cell, or unmatched (with reasons).
    Gate: (PRICED + REFER) premium share >= threshold. Also reports the share defaulted per option family (SPEC §3.4)
    and the plan-network vs exposure-network mismatch share (SPEC §3.3 / §12 F1)."""
    from .evaluator import evaluate
    opts = {"fill": "default", **(options or {})}
    cells = expo.cells.copy()
    priced, _ = evaluate(cat, cells, opts)
    m = cells.merge(priced[["cell_id", "scope_id", "status", "reason", "price", "defaulted"]], on="cell_id", how="left")
    parts = [m[["status", "reason"] + MEASURES]]
    if expo.unmatched_rows is not None and len(expo.unmatched_rows):
        u = expo.unmatched_rows.rename(columns={"__reason": "reason"}).copy()
        u["status"] = "UNMATCHED"
        parts.append(u[["status", "reason"] + MEASURES])
    allr = pd.concat(parts, ignore_index=True)
    tot = {k: float(allr[k].sum()) for k in MEASURES}
    by_status = allr.groupby("status", sort=True)[MEASURES].sum().reset_index()
    by_reason = allr[allr["status"] != "PRICED"].groupby(["status", "reason"], sort=True)[MEASURES].sum().reset_index()
    for df_ in (by_status, by_reason):
        for k in ("lives_inforce", "written_ly", "written_prem"):
            df_[f"{k}_share"] = df_[k] / tot[k] if tot[k] else np.nan
    matched = float(allr.loc[allr["status"].isin(["PRICED", "REFER"]), measure].sum())
    share = matched / tot[measure] if tot[measure] else 0.0
    # defaulted share per family, on priced+refer premium
    pm = m[m["status"].isin(["PRICED", "REFER"])]
    fams = sorted({f for s in pm["defaulted"].fillna("") for f in s.split(";") if f})
    defaulted = {f: float(pm.loc[pm["defaulted"].fillna("").str.split(";").map(lambda xs, f=f: f in xs), measure].sum())
                    / tot[measure] for f in fams} if tot[measure] else {}
    # network consistency (exposure network vs plan network for the TPA)
    plan_net = {}
    for s in cat.scopes:
        for p in s.plans:
            for t, n in p.network_by_tpa.items():
                plan_net[(s.scope_id, p.plan_id, t)] = n
    exp_net = [plan_net.get((sc, p, t)) for sc, p, t in zip(m["scope_id"], m["plan"], m["tpa"])]
    mism = (m["network_exposure"].notna()) & (pd.Series(exp_net, index=m.index) != m["network_exposure"]) & m["scope_id"].notna()
    rep = {"gate": "COVERAGE", "threshold": threshold, "measure": measure, "matched_share": share,
           "status": "PASS" if share >= threshold else "FAIL", "totals": tot,
           "by_status": by_status, "by_reason": by_reason, "unmapped": expo.unmapped,
           "defaulted_share": defaulted, "network_mismatch_share": float(m.loc[mism, measure].sum()) / tot[measure] if tot[measure] else 0.0,
           "priced_cells": m}
    if raise_on_fail and share < threshold:
        raise GateFailed("COVERAGE", f"matched {share:.2%} of {measure} < {threshold:.0%}", by_reason)
    return rep
