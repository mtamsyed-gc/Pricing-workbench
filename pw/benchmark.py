"""A market benchmark (SPEC §0, §3.3, §4): where do the catalogue and the proposals sit against the market on price and
richness, and what is missing?

Owner decisions (24 Oct 2026, WS2 thread):
  price      each plan AS SOLD (its own default design, SPEC §3.4); benefit differences sit on the richness axis
  mix        two price columns: the run's exposure mix (latest UWY, lives in force, as B2) and a standard cell set
             (run input standard_cells.csv: age, gender, member_category, marital, maternity_eligible, weight)
  basis      Gross plans put on the run basis with the plan's own gross-to-net factor (intake A_Plan C16, or the
             catalogue's run-config basis_factors); missing factor -> price null, status BASIS_MISSING
  levers     without a registry dimension: benefit lines only until CR #13

Outputs:
  ValueMap        catalogue x scope x plan: tier(s), price_exposure, price_standard (run currency and basis), richness,
                  priced shares, ratio to the tier's market median price (subjects), status
  GapRegister     subject plan x benefit_code vs the market plans of the same tier: subject value, market median /
                  presence share, n_peers, assessment GAP (subject line says not covered while >= gap_share of the
                  market covers it) / WEAKER / IN_LINE / RICHER / NOT_IN_SCHEDULE (subject has no line: data
                  completeness) / NOT_COMPARABLE
  Taxonomy        intake reconciliation (what of each market file is priced, a benefit line only, or unmapped)
Richness (SPEC §4.3, common scale): product over the requested factor families of the market basis relativity of the
plan's default option at its tier (run input market_basis.json, e.g. imported from the SME tool - a SYNTHETIC
placeholder there, flagged). Options are harmonised through option_map.csv (catalogue_id|ANY, family, option ->
canonical option). A family the plan has no option for, or an option with no relativity, makes richness PARTIAL (the
product over the valued families, with the count) - never assumed 1.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import ProposalRequired, SpecError
from .evaluator import evaluate
from .registry import ANY, load_registry
from .tiers import TierMap

STD_COLS = ["age", "gender", "member_category", "marital", "maternity_eligible", "nationality_group", "group_size_band",
            "weight"]


# ------------------------------------------------------------------------------------------------ inputs
def read_standard_cells(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    miss = [c for c in ("age", "gender", "weight") if c not in df.columns]
    if miss:
        raise SpecError(f"standard_cells.csv missing columns {miss}")
    for c in STD_COLS:
        if c not in df.columns:
            df[c] = None
    df["age"] = pd.to_numeric(df["age"]).astype("int64")
    df["group_size_band"] = pd.to_numeric(df["group_size_band"].replace("", None), errors="coerce").astype("Int64")
    df["weight"] = pd.to_numeric(df["weight"])
    if (df["weight"] <= 0).any():
        raise SpecError("standard_cells weights must be > 0")
    for c in ("gender", "member_category", "marital", "maternity_eligible", "nationality_group"):
        df[c] = df[c].map(lambda v: None if v in ("", None) else v).astype(object)
    return df[STD_COLS]


def exposure_mix(exposure_cells: pd.DataFrame, uwy: int | None = None, weight: str = "lives_inforce") -> pd.DataFrame:
    from .rate_index import select_mix
    mix, _ = select_mix(exposure_cells, uwy)
    keys = ["age", "gender", "member_category", "marital", "maternity_eligible", "nationality_group", "group_size_band"]
    df = mix[[k for k in keys if k in mix.columns]].copy()
    for k in keys:
        if k not in df.columns:
            df[k] = None
    txt = [k for k in keys if k not in ("age", "group_size_band")]
    for c in txt:
        df[c] = df[c].astype(object).map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else v)
    df["group_size_band"] = pd.to_numeric(df["group_size_band"], errors="coerce").fillna(-1).astype("int64")
    df["weight"] = pd.to_numeric(mix[weight], errors="coerce").fillna(0.0)
    g = df.groupby(keys, sort=True)["weight"].sum().reset_index()
    for c in txt:
        g[c] = g[c].map(lambda v: None if v == "" else v).astype(object)
    g["group_size_band"] = g["group_size_band"].map(lambda v: None if v < 0 else int(v)).astype("Int64")
    g = g[g["weight"] > 0].reset_index(drop=True)
    if g.empty:
        raise ProposalRequired(f"exposure mix has no '{weight}' weight (snapshot date?)")
    return g


def read_option_map(path) -> dict:
    if not path:
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {(r.catalogue_id, r.family, r.option): r.canonical_option for r in df.itertuples()}


def read_market_basis(path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    tab = {}
    for e in d.get("entries", []):
        tab[(e["family"], str(e["option"]), e.get("network", ANY))] = float(e["relativity"])
    return {"table": tab, "placeholder": bool(d.get("placeholder")), "source": d.get("source", "")}


# ------------------------------------------------------------------------------------------------ pricing
def _basis_options(cat, cfg_basis: str, cfg_factors: dict) -> tuple[dict, str]:
    """Evaluator options to put the catalogue on the run basis; returns (options, note) or raises ProposalRequired."""
    if cat.premium_basis == cfg_basis:
        return {}, ""
    key = f"{cat.premium_basis}_TO_{cfg_basis}"
    f = (cfg_factors.get(cat.catalogue_id) or {}).get(key)
    note = "run config"
    if f is None and key == "GROSS_TO_NET":
        f = ((cat.meta or {}).get("market") or {}).get("gross_to_net")
        note = "intake gross-to-net"
    if not f:
        raise ProposalRequired(f"{cat.catalogue_id}: no {key} factor (intake or run config basis_factors)")
    return {"basis": cfg_basis, "basis_factors": {key: float(f)}}, f"{key} {float(f):.4f} ({note})"


def plan_price(cat, scope, plan_id: str, cells: pd.DataFrame, run_ccy: str, fx: dict, basis_opts: dict) -> dict:
    """Weighted average annual price per life of one plan, as sold (default options), on the given cell mix."""
    tpa = scope.tpa_set[0] if ANY not in scope.tpa_set else "ANY_TPA"
    c = cells.copy()
    c.insert(0, "cell_id", np.arange(len(c), dtype="int64"))
    c["product_type"], c["rating_region"], c["tpa"], c["plan"] = scope.product_type, scope.rating_region, tpa, plan_id
    if scope.regulator is not None:
        c["regulator"] = scope.regulator
    if scope.rating_basis_age == "ENTRY_AGE":
        c["entry_age"] = c["age"]
    w = c.pop("weight").to_numpy(dtype=float)
    opts = {"fill": "default", "currency": run_ccy, "fx": fx, **basis_opts}
    res, _ = evaluate(cat, c, opts)
    res = res.set_index("cell_id").loc[c["cell_id"]]
    pr = (res["status"] == "PRICED").to_numpy()
    tot = w.sum()
    priced_w = w[pr].sum()
    price = float((res["price"].to_numpy()[pr] * w[pr]).sum() / priced_w) if priced_w > 0 else np.nan
    return {"price": price, "priced_share": priced_w / tot if tot else np.nan,
            "refer_share": float(w[(res["status"] == "REFER").to_numpy()].sum() / tot) if tot else np.nan}


def richness(cat, scope, plan_id: str, tiers: list, basis: dict, families: list, option_map: dict) -> dict:
    p = scope.plan(plan_id)
    prod, valued, missing = 1.0, [], []
    for fam in families:
        opt = p.defaults.get(fam, scope.defaults.get(fam))
        if opt is None:
            missing.append(f"{fam}: no option")
            continue
        opt = option_map.get((cat.catalogue_id, fam, str(opt)), option_map.get((ANY, fam, str(opt)), str(opt)))
        rel, ok = 0.0, True
        for t, w in tiers:
            v = basis["table"].get((fam, opt, t), basis["table"].get((fam, opt, ANY)))
            if v is None:
                ok = False
                break
            rel += w * v
        if not ok:
            missing.append(f"{fam}: no relativity for '{opt}'")
            continue
        prod *= rel
        valued.append(fam)
    st = "VALUED" if not missing else ("PARTIAL" if valued else "NOT_VALUED")
    return {"richness": prod if valued else np.nan, "richness_families": len(valued), "richness_status": st,
            "richness_note": "; ".join(missing)}


def value_map(catalogues: list, subjects: set, tmap: TierMap, std_cells: pd.DataFrame | None,
              expo_cells: pd.DataFrame | None, run_ccy: str, fx: dict, run_basis: str, basis_factors: dict,
              mkt_basis: dict | None, families: list, option_map: dict) -> pd.DataFrame:
    rows = []
    for cat in catalogues:
        try:
            bopt, bnote = _basis_options(cat, run_basis, basis_factors)
            bstat = ""
        except ProposalRequired as e:
            bopt, bnote, bstat = None, str(e), "BASIS_MISSING"
        for s in cat.scopes:
            if s.components_of("EXPERIENCE_RATED"):
                continue
            for p in s.plans:
                if s.plan_set and p.plan_id not in s.plan_set:
                    continue
                tiers = tmap.tiers(cat.catalogue_id, p.plan_id)
                r = {"catalogue_id": cat.catalogue_id, "kind": cat.kind, "role": "SUBJECT" if cat.catalogue_id in subjects else "MARKET",
                     "owner": cat.owner, "scope_id": s.scope_id, "plan": p.plan_id, "plan_label": p.label,
                     "product_type": s.product_type, "rating_region": s.rating_region,
                     "tier": max(tiers, key=lambda x: (x[1], -tmap.rank(x[0])))[0],
                     "tier_weights": json.dumps(tiers), "tier_rank": sum(w * tmap.rank(t) for t, w in tiers),
                     "currency": run_ccy, "basis": run_basis, "basis_note": bnote, "status": bstat or "OK"}
                for tag, cells in (("exposure", expo_cells), ("standard", std_cells)):
                    if cells is None or bopt is None:
                        r[f"price_{tag}"], r[f"priced_share_{tag}"] = np.nan, np.nan
                        continue
                    pp = plan_price(cat, s, p.plan_id, cells, run_ccy, fx, bopt)
                    r[f"price_{tag}"], r[f"priced_share_{tag}"] = pp["price"], pp["priced_share"]
                    if pp["priced_share"] == 0:
                        r["status"] = (r["status"] + "; " if r["status"] != "OK" else "") + f"NO_PRICED_CELLS_{tag.upper()}"
                if mkt_basis is not None and families:
                    r.update(richness(cat, s, p.plan_id, tiers, mkt_basis, families, option_map))
                else:
                    r.update({"richness": np.nan, "richness_families": 0, "richness_status": "NO_BASIS", "richness_note": ""})
                rows.append(r)
    vm = pd.DataFrame(rows)
    # ratio of each plan to the market median price of its tier (market plans only in the median)
    for tag in ("exposure", "standard"):
        col = f"price_{tag}"
        med = vm[vm["role"] == "MARKET"].groupby("tier")[col].median()
        n = vm[vm["role"] == "MARKET"].groupby("tier")[col].count()
        vm[f"market_median_{tag}"] = vm["tier"].map(med)
        vm[f"market_n_{tag}"] = vm["tier"].map(n).fillna(0).astype("int64")
        vm[f"ratio_to_median_{tag}"] = vm[col] / vm[f"market_median_{tag}"]
    vm = vm.sort_values(["tier_rank", "role", "catalogue_id", "plan"], kind="stable").reset_index(drop=True)
    return vm


# ------------------------------------------------------------------------------------------------ gaps
def _lines(cat, scope, plan_id):
    return {b.benefit_code: b for b in scope.benefits if b.plan_id == plan_id}


def _as_num(v):
    if isinstance(v, bool):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def gap_register(catalogues: list, subjects: set, tmap: TierMap, gap_share: float = 0.5,
                 peer_same_region: bool = False) -> pd.DataFrame:
    reg = load_registry()
    plans = []
    for cat in catalogues:
        for s in cat.scopes:
            for p in s.plans:
                t = max(tmap.tiers(cat.catalogue_id, p.plan_id), key=lambda x: x[1])[0]
                plans.append((cat, s, p.plan_id, t))
    out = []
    for cat, s, pid, tier in plans:
        if cat.catalogue_id not in subjects:
            continue
        peers = [(c2, s2, p2) for c2, s2, p2, t2 in plans if c2.catalogue_id not in subjects and t2 == tier
                 and (not peer_same_region or s2.rating_region == s.rating_region)]
        sub = _lines(cat, s, pid)
        peer_lines = [_lines(c2, s2, p2) for c2, s2, p2 in peers]
        codes = sorted(set(sub) | {k for pl in peer_lines for k in pl})
        for code in codes:
            info = reg.benefits.get(code, {})
            rule = info.get("comparison_rule", "")
            sv = sub[code].value if code in sub else None
            pv = [pl[code].value for pl in peer_lines if code in pl]
            n = len(pv)
            row = {"subject": cat.catalogue_id, "scope_id": s.scope_id, "plan": pid, "tier": tier, "benefit_code": code,
                   "group": info.get("group"), "comparison_rule": rule,
                   "subject_value": None if sv is None else str(sv), "n_peers": n, "market_median": None,
                   "market_presence_share": np.nan, "share_peers_richer": np.nan, "assessment": "NOT_COMPARABLE", "note": ""}
            if n == 0:
                row["note"] = "no market plan of this tier carries the line"
                out.append(row)
                continue
            pres = [bool(_as_num(v)) if _as_num(v) is not None else (v not in (None, "", False)) for v in pv]
            row["market_presence_share"] = sum(pres) / n
            s_present = sv is not None and (bool(_as_num(sv)) if _as_num(sv) is not None else sv not in ("", False))
            if code not in sub:
                row["assessment"] = "NOT_IN_SCHEDULE"
                row["note"] = (f"subject schedule has no '{code}' line; present in {sum(pres)}/{n} market plans "
                               "(data completeness, not a benefit gap)")
                out.append(row)
                continue
            if not s_present:
                if row["market_presence_share"] >= gap_share:
                    row["assessment"], row["note"] = "GAP", f"absent in subject; present in {sum(pres)}/{n} market plans"
                else:
                    row["assessment"] = "IN_LINE"
                out.append(row)
                continue
            if rule == "categorical-ladder":
                lad = info.get("ladder", [])
                idx = [lad.index(v) for v in pv if v in lad]
                if sv in lad and idx:
                    med = float(np.median(idx))
                    row["market_median"] = lad[int(round(med))]
                    si = lad.index(sv)
                    row["share_peers_richer"] = sum(i > si for i in idx) / len(idx)
                    row["assessment"] = "RICHER" if si > med else ("WEAKER" if si < med else "IN_LINE")
                else:
                    row["note"] = "value not on the ladder"
            elif rule in ("higher-is-richer", "lower-is-richer"):
                nums = [x for x in (_as_num(v) for v in pv) if x is not None]
                s_num = _as_num(sv)
                if s_num is not None and nums:
                    med = float(np.median(nums))
                    row["market_median"] = repr(med)
                    better = (lambda a, b: a > b) if rule == "higher-is-richer" else (lambda a, b: a < b)
                    row["share_peers_richer"] = sum(better(x, s_num) for x in nums) / len(nums)
                    row["assessment"] = "RICHER" if better(s_num, med) else ("WEAKER" if better(med, s_num) else "IN_LINE")
                else:
                    row["note"] = "non-numeric values (structure comparison: MANUAL_REVIEW)"
            elif rule in ("presence", "false-is-richer"):
                row["assessment"] = "IN_LINE"
            else:
                row["note"] = f"comparison rule '{rule}' not automated (MANUAL_REVIEW)"
            out.append(row)
    cols = ["subject", "scope_id", "plan", "tier", "benefit_code", "group", "comparison_rule", "subject_value", "n_peers",
            "market_median", "market_presence_share", "share_peers_richer", "assessment", "note"]
    return pd.DataFrame(out, columns=cols)


# ------------------------------------------------------------------------------------------------ run
def run_benchmark(cfg: dict, runs_root=None) -> dict:
    from .exposure import build_exposure
    from .market_intake import load_layout, load_market_folder
    from .outputs import run_dir, update_manifest, write_table
    from .rate_index import _path, load_catalogue_any
    from .template.ingest import registered_options
    b = cfg.get("benchmark")
    if not b:
        raise ProposalRequired("run config has no 'benchmark' section")
    rd = run_dir(cfg["run_id"], runs_root)
    layout = load_layout(str(_path(cfg, b["layout"])) if b.get("layout") else None)
    market, recon = [], []
    for folder in b.get("market_folders", []):
        cats, rep = load_market_folder(_path(cfg, folder), layout)
        market += cats
        recon += rep
    for p in b.get("market_catalogues", []):
        market.append(load_catalogue_any(_path(cfg, p)))
    subj = []
    for p in b.get("subjects", []):
        if p == "@expiring":
            subj.append(load_catalogue_any(_path(cfg, cfg["expiring"])))
        elif p == "@options":
            subj += list(registered_options(cfg["run_id"], runs_root).values())
        else:
            subj.append(load_catalogue_any(_path(cfg, p)))
    if not subj and not market:
        raise ProposalRequired("benchmark: no subjects and no market catalogues")
    ids = [c.catalogue_id for c in subj + market]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise SpecError(f"benchmark: duplicate catalogue ids {dup}")
    tmap = TierMap.read(_path(cfg, b["tier_map"]), b["tier_ladder"])
    std = read_standard_cells(_path(cfg, b["standard_cells"])) if b.get("standard_cells") else None
    expo = None
    if b.get("use_exposure_mix", True) and cfg.get("exposure"):
        ec = cfg["exposure"]
        ex = build_exposure(_path(cfg, ec["dim_life"]), _path(cfg, ec["maps"]),
                            _path(cfg, ec["manifest"]) if ec.get("manifest") else None,
                            snapshot_date=ec.get("snapshot_date"), strict=False)
        expo = exposure_mix(ex.cells)
    mb = read_market_basis(_path(cfg, b["market_basis"])) if b.get("market_basis") else None
    om = read_option_map(_path(cfg, b["option_map"])) if b.get("option_map") else {}
    vm = value_map(subj + market, {c.catalogue_id for c in subj}, tmap, std, expo, b.get("currency", "AED"),
                   b.get("fx") or {}, b.get("basis", "NET"), b.get("basis_factors") or {}, mb,
                   b.get("richness_families") or [], om)
    if mb is not None:
        vm["richness_basis"] = ("PLACEHOLDER: " if mb["placeholder"] else "") + mb["source"]
    gr = gap_register(subj + market, {c.catalogue_id for c in subj}, tmap, float(b.get("gap_share", 0.5)),
                      bool(b.get("peer_same_region", False)))
    rc = pd.DataFrame(recon, columns=["plan_id", "area", "item", "status", "detail"])
    out = rd / "out"
    m = {"ValueMap": write_table("ValueMap", vm, out, None, contract=False),
         "GapRegister": write_table("GapRegister", gr, out, ["subject", "scope_id", "plan", "benefit_code"], contract=False),
         "TaxonomyReconciliation": write_table("TaxonomyReconciliation", rc, out, ["plan_id", "area", "item"], contract=False)}
    update_manifest(rd, "outputs", m)
    update_manifest(rd, "benchmark", {"market_plans": len(market), "subjects": [c.catalogue_id for c in subj],
                                      "tier_ladder": b["tier_ladder"], "richness_families": b.get("richness_families") or [],
                                      "market_basis_placeholder": None if mb is None else mb["placeholder"]})
    return {"ValueMap": vm, "GapRegister": gr, "Taxonomy": rc, "market": market, "subjects": subj, "dir": rd}
