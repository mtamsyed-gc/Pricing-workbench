"""Evaluator (SPEC §3.2, §3.4, §3.5, §6): vectorised pricing of arbitrary cell sets with an optional trace.

    evaluate(catalogue, cells, options) -> (prices DataFrame, trace DataFrame | None)

Formula (default order BASE, FACTORS, MODULES):
    P = round(BASE x prod FACTOR + sum MODULE_add, rounding) x (1 + loading_applied) + FEES, bounded by min/max
Order ["BASE", "MODULES", "FACTORS"] gives round((BASE + sum MODULE_add) x prod FACTOR, rounding) ...
REFER cells return a null price with a reason. Matching: per component, the most specific row wins
(exact value > hierarchy parent > ANY, per dimension); ties with different values raise SpecError.

Options:
  fill               "default" (catalogue default option per plan/scope/component, SPEC §3.4) | "reference"
  trace              bool
  resolution         None (component's declared) | "DERIVED" | "SOURCE"  (BLOCK_SET cells, SPEC §6 V2)
  currency           output currency (default: catalogue currency)
  fx                 {currency: units of a common base}, required when currencies differ
  basis              target premium basis (GROSS|NET); None = no conversion
  basis_factors      {"GROSS_TO_NET": f, "NET_TO_GROSS": g}
  loading_applied    float (default 0: base comparison excludes loadings, SPEC §3.2); must be <= LOADING cap
  include_fees       bool (default True)
  strict             raise ProposalRequired on any UNMATCHED cell
  duckdb             {"memory_limit": "4GB", "threads": 4}
"""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd

from . import ProposalRequired, SpecError
from .model import Catalogue, Component, RatingScope, canonical_key_str
from .registry import ANY, load_registry
from .trace import Trace

DEFAULT_ORDER = ["BASE", "FACTORS", "MODULES"]
ALT_ORDER = ["BASE", "MODULES", "FACTORS"]
NONE_OPTION = "NONE"   # module option meaning "not purchased"

RESULT_COLUMNS = ["cell_id", "scope_id", "status", "reason", "base", "factor_product", "modules_add", "premium_pre_loading",
                  "loading", "fees", "price", "currency", "defaulted", "base_status", "price_base", "price_riders"]


def _connect(options):
    cfg = options.get("duckdb") or {}
    con = duckdb.connect(database=":memory:")
    if cfg.get("memory_limit"):
        con.execute(f"SET memory_limit='{cfg['memory_limit']}'")
    if cfg.get("threads"):
        con.execute(f"SET threads={int(cfg['threads'])}")
    return con


def _rows_frame(comp_rows, keys, reg) -> pd.DataFrame:
    rec = []
    for i, r in enumerate(comp_rows):
        d = {"__row": i, "__value": r.get("value"), "__status": r.get("status", "VALUE")}
        for k in keys:
            v = r["key"].get(k, ANY)
            if reg.is_range(k):
                d[f"{k}__lo"] = None if v == ANY else int(v[0])
                d[f"{k}__hi"] = None if v == ANY else int(v[1])
            else:
                d[k] = str(v)
        rec.append(d)
    df = pd.DataFrame.from_records(rec)
    if df.empty:
        df = pd.DataFrame({"__row": pd.Series(dtype="int64"), "__value": pd.Series(dtype="float64"),
                           "__status": pd.Series(dtype=object)})
    for k in keys:
        if reg.is_range(k):
            for s in ("__lo", "__hi"):
                df[k + s] = pd.array(df.get(k + s, pd.Series([None] * len(df))), dtype="Int64")
        else:
            df[k] = df.get(k, pd.Series([ANY] * len(df))).astype(object)
    df["__value"] = df["__value"].astype("float64")
    df["__status"] = df["__status"].astype(object)
    return df


def lookup(con, comp_rows, keys, cells: pd.DataFrame, reg, age_col: str = "age") -> pd.DataFrame:
    """Vectorised best-match lookup. Returns DataFrame[cell_id, __row, __value, __status, __matched] for matched cells."""
    if cells.empty:
        return pd.DataFrame(columns=["cell_id", "__row", "__value", "__status", "__matched"])
    rows = _rows_frame(comp_rows, keys, reg)
    cell_cols = {"cell_id": cells["cell_id"].to_numpy()}
    conds, scores = [], []
    for k in keys:
        src = age_col if k == "age" else k
        if reg.is_range(k):
            col = cells[src] if src in cells.columns else pd.Series([None] * len(cells), index=cells.index)
            cell_cols[k] = pd.array(pd.to_numeric(col, errors="coerce").round(), dtype="Int64")
            conds.append(f'(r."{k}__lo" IS NULL OR c."{k}" BETWEEN r."{k}__lo" AND r."{k}__hi")')
            scores.append(f'(CASE WHEN r."{k}__lo" IS NULL THEN 0 ELSE 2 END)')
        else:
            col = cells[src] if src in cells.columns else pd.Series([None] * len(cells), index=cells.index)
            col = col.astype(object).where(col.notna(), None)
            cell_cols[k] = col.map(lambda v: None if v is None else str(v)).to_numpy(dtype=object)
            parent = None
            h = reg.dim(k).hierarchy
            if h:
                parent = [None if v is None else h.get(v) for v in cell_cols[k]]
            cell_cols[f"{k}__parent"] = np.array(parent if parent is not None else [None] * len(cells), dtype=object)
            conds.append(f'(r."{k}" = \'ANY\' OR r."{k}" = c."{k}" OR r."{k}" = c."{k}__parent")')
            scores.append(f'(CASE WHEN r."{k}" = c."{k}" THEN 2 WHEN r."{k}" = \'ANY\' THEN 0 ELSE 1 END)')
    cdf = pd.DataFrame(cell_cols)
    for k in keys:
        if not reg.is_range(k):
            cdf[k] = cdf[k].astype(object)
            cdf[f"{k}__parent"] = cdf[f"{k}__parent"].astype(object)
    con.register("c_tbl", cdf)
    con.register("r_tbl", rows)
    on = " AND ".join(conds) if conds else "TRUE"
    score = " + ".join(scores) if scores else "0"
    sql = f"""
        WITH m AS (
          SELECT c.cell_id, r.__row, r.__value, r.__status, {score} AS __score
          FROM c_tbl c JOIN r_tbl r ON {on}
        ), t AS (
          SELECT *, MAX(__score) OVER (PARTITION BY cell_id) AS __best FROM m
        )
        SELECT cell_id, __row, __value, __status,
               COUNT(DISTINCT COALESCE(CAST(__value AS VARCHAR), '') || '|' || __status) OVER (PARTITION BY cell_id) AS __nvals
        FROM t WHERE __score = __best
        QUALIFY ROW_NUMBER() OVER (PARTITION BY cell_id ORDER BY __row) = 1
        ORDER BY cell_id
    """
    res = con.execute(sql).df()
    con.unregister("c_tbl")
    con.unregister("r_tbl")
    amb = res[res["__nvals"] > 1]
    if len(amb):
        raise SpecError(f"ambiguous match: {len(amb)} cells match equally specific rows with different values "
                        f"(first cell_id {amb['cell_id'].iloc[0]}); make the table rows more specific")
    res["__matched"] = [canonical_key_str(comp_rows[i]["key"], reg.order) for i in res["__row"]]
    return res[["cell_id", "__row", "__value", "__status", "__matched"]]


def _fx(options, frm: str, to: str) -> float:
    if frm == to:
        return 1.0
    fx = options.get("fx") or {}
    if frm not in fx or to not in fx:
        raise ProposalRequired(f"FX rate needed to convert {frm} -> {to}: supply options['fx'] (run config)")
    return float(fx[frm]) / float(fx[to])


def _basis_factor(options, comp_basis: str | None) -> float:
    tgt = options.get("basis")
    if not tgt or not comp_basis or comp_basis == tgt:
        return 1.0
    key = f"{comp_basis}_TO_{tgt}"
    bf = options.get("basis_factors") or {}
    if key not in bf:
        raise ProposalRequired(f"premium basis conversion {key} needed (SPEC §3.5: run input, never assumed)")
    return float(bf[key])


def _option_families(scope: RatingScope) -> list[str]:
    fams = []
    for c in scope.components:
        if c.type in ("FACTOR_TABLE", "MODULE") and c.family and c.family in c.keys and c.family not in fams:
            fams.append(c.family)
    return fams


def _fill_options(scope: RatingScope, df: pd.DataFrame, fill: str) -> pd.DataFrame:
    """Fill missing co-pay/module options: catalogue default (plan -> scope -> component) or reference level."""
    defaulted = pd.Series([""] * len(df), index=df.index, dtype=object)
    for fam in _option_families(scope):
        comps = [c for c in scope.components if c.family == fam and c.type in ("FACTOR_TABLE", "MODULE")]
        if fam not in df.columns:
            df[fam] = None
        df[fam] = df[fam].astype(object).where(df[fam].notna(), None)
        miss = df[fam].isna()
        if not miss.any():
            continue
        vals = []
        for idx in df.index[miss]:
            plan_id = df.at[idx, "plan"]
            v = None
            if fill == "reference":
                c0 = comps[0]
                if c0.type == "MODULE":
                    v = NONE_OPTION
                elif c0.reference_level_by_key:
                    by = c0.reference_level_by
                    v = c0.reference_level_by_key.get(str(df.at[idx, by]) if by in df.columns else None)
                else:
                    v = c0.reference_level
            else:
                try:
                    p = scope.plan(plan_id)
                    v = p.defaults.get(fam)
                except SpecError:
                    v = None
                if v is None:
                    v = scope.defaults.get(fam)
                if v is None:
                    v = next((c.default_option for c in comps if c.default_option is not None), None)
            if v is None:
                raise ProposalRequired(f"scope {scope.scope_id}: no {'reference' if fill == 'reference' else 'catalogue default'} "
                                       f"option for '{fam}' (plan {plan_id}); declare it in the catalogue spec (SPEC §3.4)")
            vals.append(v)
        df.loc[miss, fam] = pd.Series(vals, index=df.index[miss], dtype=object)
        defaulted.loc[miss] = defaulted.loc[miss] + (fam + ";")
    df["__defaulted"] = defaulted.str.rstrip(";")
    return df


def _assign_scopes(cat: Catalogue, cells: pd.DataFrame) -> pd.Series:
    sid = pd.Series([None] * len(cells), index=cells.index, dtype=object)
    for s in cat.scopes:
        m = sid.isna()
        m &= cells.get("product_type", pd.Series([None] * len(cells), index=cells.index)) == s.product_type
        if s.regulator is not None and "regulator" in cells.columns:
            m &= cells["regulator"].isna() | (cells["regulator"] == s.regulator)
        if s.rating_region is not None:
            m &= cells.get("rating_region", pd.Series([None] * len(cells), index=cells.index)) == s.rating_region
        if ANY not in s.tpa_set:
            m &= cells.get("tpa", pd.Series([None] * len(cells), index=cells.index)).isin(s.tpa_set)
        plan_ids = s.plan_set or [p.plan_id for p in s.plans]
        m &= cells.get("plan", pd.Series([None] * len(cells), index=cells.index)).isin(plan_ids)
        sid[m] = s.scope_id
    return sid


def evaluate(cat: Catalogue, cells, options: dict | None = None, registry=None):
    options = dict(options or {})
    reg = registry or load_registry()
    fill = options.get("fill", "default")
    if fill not in ("default", "reference"):
        raise SpecError("options.fill must be 'default' or 'reference'")
    out_ccy = options.get("currency") or cat.currency
    df = pd.DataFrame(cells).copy() if not isinstance(cells, pd.DataFrame) else cells.copy()
    if "cell_id" not in df.columns:
        df["cell_id"] = np.arange(len(df), dtype="int64")
    if df["cell_id"].duplicated().any():
        raise SpecError("cell_id must be unique")
    df = df.reset_index(drop=True)
    for c in df.columns:
        if c in reg.dims and not reg.is_range(c):
            df[c] = df[c].astype(object).where(df[c].notna(), None)
    trace = Trace(bool(options.get("trace")))
    df["__scope"] = _assign_scopes(cat, df)
    results = []
    unscoped = df[df["__scope"].isna()]
    if len(unscoped):
        results.append(pd.DataFrame({"cell_id": unscoped["cell_id"], "scope_id": None, "status": "UNMATCHED",
                                     "reason": "no rating scope matches the cell", "currency": out_ccy, "defaulted": ""}))
    con = _connect(options)
    try:
        for s in cat.scopes:
            sub = df[df["__scope"] == s.scope_id].copy()
            if sub.empty:
                continue
            results.append(_evaluate_scope(con, cat, s, sub, options, reg, trace, fill, out_ccy))
    finally:
        con.close()
    res = pd.concat([r for r in results if len(r)], ignore_index=True) if results else pd.DataFrame(columns=RESULT_COLUMNS)
    for c in RESULT_COLUMNS:
        if c not in res.columns:
            res[c] = None
    res = res[RESULT_COLUMNS].sort_values("cell_id", kind="stable").reset_index(drop=True)
    for c in ("base", "factor_product", "modules_add", "premium_pre_loading", "loading", "fees", "price", "price_base",
              "price_riders"):
        res[c] = pd.to_numeric(res[c], errors="coerce").astype("float64")
    if options.get("strict") and (res["status"] == "UNMATCHED").any():
        bad = res[res["status"] == "UNMATCHED"].head(5)
        raise ProposalRequired(f"{(res['status'] == 'UNMATCHED').sum()} cells unmatched, e.g. "
                               + "; ".join(f"{r.cell_id}: {r.reason}" for r in bad.itertuples()))
    return res, trace.frame()


def _evaluate_scope(con, cat, s: RatingScope, sub: pd.DataFrame, options, reg, trace: Trace, fill, out_ccy):
    order = s.formula.order or DEFAULT_ORDER
    if order not in (DEFAULT_ORDER, ALT_ORDER):
        raise ProposalRequired(f"scope {s.scope_id}: formula order {order} has no defined semantics (SPEC §3.2)")
    calc_ccy = s.currency or cat.currency
    rnd = s.formula.rounding
    # network from plan x TPA (SPEC §3.3)
    if "network" not in sub.columns:
        sub["network"] = None
    sub["network"] = sub["network"].astype(object)
    plan_net = {(p.plan_id, t): n for p in s.plans for t, n in p.network_by_tpa.items()}
    miss = sub["network"].isna()
    if miss.any():
        sub.loc[miss, "network"] = [plan_net.get((p, t), plan_net.get((p, ANY))) for p, t in
                                    zip(sub.loc[miss, "plan"], sub.loc[miss, "tpa"])]
    # age used for lookups
    if s.rating_basis_age == "ENTRY_AGE":
        sub["__age_lookup"] = sub["entry_age"] if "entry_age" in sub.columns else np.nan
    else:
        sub["__age_lookup"] = sub["age"] if "age" in sub.columns else np.nan
    sub = _fill_options(s, sub, fill)
    n = len(sub)
    ids = sub["cell_id"].to_numpy()
    st = pd.DataFrame({"cell_id": ids, "scope_id": s.scope_id, "status": "PRICED", "reason": "", "currency": out_ccy,
                       "defaulted": sub["__defaulted"].to_numpy(), "base_status": "PRICED"})
    st = st.set_index("cell_id")
    if s.rating_basis_age == "ENTRY_AGE":
        bad = sub["__age_lookup"].isna().to_numpy()
        st.loc[ids[bad], ["status", "reason", "base_status"]] = ["UNMATCHED", "entry_age required (rating_basis_age = ENTRY_AGE)",
                                                                "UNMATCHED"]

    def tr(df_like, comp, option_col, value, running, note=""):
        if not trace.enabled:
            return
        t = pd.DataFrame({"cell_id": df_like["cell_id"].to_numpy(), "component_id": comp.component_id, "type": comp.type,
                          "family": comp.family,
                          "option": (sub.set_index("cell_id").loc[df_like["cell_id"], option_col].to_numpy()
                                     if option_col and option_col in sub.columns else None),
                          "matched_key": df_like["__matched"].to_numpy() if "__matched" in df_like.columns else None,
                          "value": value, "running": running, "note": note})
        trace.add(t)

    def mark(mask_ids, status, reason, base_too=True):
        # base_status tracks the base-only price (base x rating factors, no modules): module issues leave it PRICED
        cur = st.loc[mask_ids, "status"]
        ok = cur[cur == "PRICED"].index
        st.loc[ok, "status"] = status
        st.loc[ok, "reason"] = reason
        if base_too:
            cb = st.loc[mask_ids, "base_status"]
            st.loc[cb[cb == "PRICED"].index, "base_status"] = status

    if s.components_of("EXPERIENCE_RATED"):
        st["status"] = "EXPERIENCE_RATED"
        st["base_status"] = "EXPERIENCE_RATED"
        st["reason"] = "scope is experience rated (no tabled price)"
        out = st.reset_index()
        return out

    # explicit REFER components
    for comp in s.components_of("REFER"):
        m = lookup(con, comp.rows, comp.keys, sub, reg, "__age_lookup")
        mark(m["cell_id"].to_numpy(), "REFER", f"refer ({comp.component_id})")
        tr(m, comp, None, np.nan, np.nan, "REFER")

    # BASE
    base_c = s.components_of("BASE_TABLE")[0]
    m = lookup(con, base_c.rows, base_c.keys, sub, reg, "__age_lookup").set_index("cell_id")
    base = pd.Series(np.nan, index=ids)
    matched = m.index.intersection(ids)
    unmatched = np.setdiff1d(ids, m.index.to_numpy())
    mark(unmatched, "UNMATCHED", f"no BASE_TABLE row ({base_c.component_id})")
    refer_ids = m.index[m["__status"] == "REFER"]
    mark(refer_ids, "REFER", f"refer cell ({base_c.component_id})")
    k_ccy = _fx(options, base_c.currency or calc_ccy, calc_ccy) * _basis_factor(options, base_c.premium_basis)
    base.loc[matched] = m.loc[matched, "__value"].to_numpy() * k_ccy
    tr(m.reset_index(), base_c, None, m["__value"].to_numpy() * k_ccy, m["__value"].to_numpy() * k_ccy,
       "" if k_ccy == 1 else f"x{k_ccy:.6g} (fx/basis)")
    # BLOCK_SET source values (resolution SOURCE, used by V1): replace BASE x block multiplier by the source cell
    block_src = {}
    for comp in s.components_of("FACTOR_TABLE"):
        res_mode = options.get("resolution") or comp.block_check.get("resolution")
        if not (comp.source_blocks and res_mode == "SOURCE"):
            continue
        hit = []
        for lvl, rows in comp.source_blocks.items():
            lv = sub[sub[comp.family] == lvl]
            if lv.empty:
                continue
            bm = lookup(con, rows, base_c.keys, lv, reg, "__age_lookup").set_index("cell_id")
            bm = bm[bm["__status"] == "VALUE"]
            base.loc[bm.index] = bm["__value"].to_numpy() * k_ccy
            hit.extend(bm.index.tolist())
            tr(bm.reset_index(), comp, comp.family, bm["__value"].to_numpy() * k_ccy, bm["__value"].to_numpy() * k_ccy,
               "block source value replaces BASE x block multiplier")
        block_src[comp.component_id] = np.array(hit, dtype=ids.dtype)
    running = base.copy()
    fprod = pd.Series(1.0, index=ids)
    f_only = pd.Series(1.0, index=ids)      # rating factors only (no MULTIPLY modules): base-only price
    mod_add = pd.Series(0.0, index=ids)

    def apply_factors():
        nonlocal running
        for comp in s.components_of("FACTOR_TABLE"):
            fm = lookup(con, comp.rows, comp.keys, sub, reg, "__age_lookup").set_index("cell_id")
            un = np.setdiff1d(ids, fm.index.to_numpy())
            mark(un, "UNMATCHED", f"no row in FACTOR_TABLE {comp.component_id}")
            mark(fm.index[fm["__status"] == "REFER"], "REFER", f"refer ({comp.component_id})")
            f = pd.Series(1.0, index=ids)
            f.loc[fm.index] = fm["__value"].fillna(1.0).to_numpy()
            note = ""
            if comp.component_id in block_src and len(block_src[comp.component_id]):
                f.loc[block_src[comp.component_id]] = 1.0
                note = "1.0 where the block source value is used"
            fprod.loc[:] = fprod.to_numpy() * f.to_numpy()
            f_only.loc[:] = f_only.to_numpy() * f.to_numpy()
            running = running * f
            fmr = fm.reset_index()
            tr(fmr, comp, comp.family if comp.family in sub.columns else None, f.loc[fmr["cell_id"]].to_numpy(),
               running.loc[fmr["cell_id"]].to_numpy(), note)

    def apply_modules():
        nonlocal running
        for comp in s.components_of("MODULE"):
            if comp.unit == "PER_FAMILY":
                raise ProposalRequired(f"{comp.component_id}: PER_FAMILY module unit has no defined allocation rule "
                                       "(SPEC §3.2 silent); owner to define")
            opt = sub[comp.family] if comp.family in sub.columns else pd.Series([NONE_OPTION] * len(sub), index=sub.index)
            elig = opt.ne(NONE_OPTION)
            for d, v in comp.eligibility.items():
                col = sub[d] if d in sub.columns else pd.Series([None] * len(sub), index=sub.index)
                par = col.map(lambda x: reg.parent_of(d, x) if reg.dims.get(d) and reg.dim(d).hierarchy else None)
                elig &= (col == v) | (par == v)
            take = sub[elig.to_numpy()]
            if take.empty:
                continue
            mm = lookup(con, comp.rows, comp.keys, take, reg, "__age_lookup").set_index("cell_id")
            un = np.setdiff1d(take["cell_id"].to_numpy(), mm.index.to_numpy())
            mark(un, "UNMATCHED", f"no row in MODULE {comp.component_id} for the selected option", base_too=False)
            ref = mm[mm["__status"] == "REFER"]
            nq = ref["__row"].map(lambda i: str(comp.rows[int(i)].get("source_ref") or "").startswith("not quoted"))
            mark(ref.index[nq.to_numpy(dtype=bool)], "REFER", f"rider not quoted ({comp.component_id})", base_too=False)
            mark(ref.index[~nq.to_numpy(dtype=bool)], "REFER", f"refer ({comp.component_id})", base_too=False)
            vals = mm["__value"].fillna(0.0)
            if comp.mode == "MULTIPLY":
                fprod.loc[mm.index] = fprod.loc[mm.index].to_numpy() * vals.to_numpy()
                running.loc[mm.index] = running.loc[mm.index].to_numpy() * vals.to_numpy()
                shown = vals.to_numpy()
            else:
                k = _fx(options, comp.currency or calc_ccy, calc_ccy) * _basis_factor(options, comp.premium_basis)
                mod_add.loc[mm.index] = mod_add.loc[mm.index].to_numpy() + vals.to_numpy() * k
                running.loc[mm.index] = running.loc[mm.index].to_numpy() + vals.to_numpy() * k
                shown = vals.to_numpy() * k
            mmr = mm.reset_index()
            tr(mmr, comp, comp.family, shown, running.loc[mmr["cell_id"]].to_numpy(), comp.unit or "")

    if order == DEFAULT_ORDER:
        apply_factors()
        apply_modules()
        pre = base * fprod + mod_add
    else:
        apply_modules()
        running = base + mod_add
        apply_factors()
        pre = (base + mod_add) * fprod
    pre = pre.round(rnd)

    # loading (distributional, SPEC §3.2): applied only when the run says so, within the cap
    la = float(options.get("loading_applied") or 0.0)
    loads = s.components_of("LOADING")
    if la:
        cap = min((c.cap for c in loads if c.cap is not None), default=None)
        if cap is None and not loads:
            raise ProposalRequired(f"scope {s.scope_id}: loading_applied given but the scope declares no LOADING component")
        if cap is not None and la > cap + 1e-12:
            raise ProposalRequired(f"scope {s.scope_id}: loading_applied {la} exceeds the LOADING cap {cap}")
    post = pre * (1.0 + la)
    fees = pd.Series(0.0, index=ids)
    if options.get("include_fees", True):
        for comp in s.components_of("FEE"):
            if comp.amount is not None:
                fees += comp.amount * _fx(options, comp.currency or calc_ccy, calc_ccy) * _basis_factor(options, comp.premium_basis)
            else:
                fees += post * comp.pct
    price = post + fees
    if s.formula.min_premium is not None:
        price = price.clip(lower=s.formula.min_premium)
    if s.formula.max_premium is not None:
        price = price.clip(upper=s.formula.max_premium)
    conv = _fx(options, calc_ccy, out_ccy)
    price = (price * conv).round(rnd) if conv != 1.0 else price.round(rnd)
    if trace.enabled:
        t = pd.DataFrame({"cell_id": ids, "component_id": "formula", "type": "FORMULA", "family": None, "option": None,
                          "matched_key": None, "value": price.to_numpy(), "running": price.to_numpy(),
                          "note": f"round({rnd}) x (1+{la}) + fees{'' if conv == 1 else f' x fx {conv:.6g} -> {out_ccy}'}"})
        trace.add(t)

    st["base"] = base
    st["factor_product"] = fprod
    st["modules_add"] = mod_add
    # base-only price (base x rating factors; no modules, loading, fees or min/max) and the additive rider premium,
    # for the B2 split (owner decision 24 Oct 2026, HANDOVER item 11)
    pb = (base * f_only * conv).round(rnd)
    st["price_base"] = pb.where(st["base_status"] == "PRICED")
    st["price_riders"] = (mod_add * conv).round(rnd).where(st["status"] == "PRICED")
    st["premium_pre_loading"] = pre
    st["loading"] = la
    st["fees"] = fees
    st["price"] = price
    nonpriced = st["status"] != "PRICED"
    st.loc[nonpriced, "price"] = np.nan
    return st.reset_index()


def lookup_component(cat: Catalogue, scope_id: str, comp: Component, keys_list: list[dict], registry=None) -> pd.DataFrame:
    """Look up explicit keys (dict per cell) in one component; used by V1. Range dims take an int (lo of the source band)."""
    reg = registry or load_registry()
    recs = []
    for i, k in enumerate(keys_list):
        d = {"cell_id": i}
        for dim, v in k.items():
            d[dim] = (int(v[0]) if isinstance(v, (list, tuple)) else v)
        recs.append(d)
    cells = pd.DataFrame.from_records(recs)
    for c in cells.columns:
        if c != "cell_id" and not reg.is_range(c):
            cells[c] = cells[c].astype(object)
    con = duckdb.connect(":memory:")
    try:
        return lookup(con, comp.rows, comp.keys, cells, reg, "age")
    finally:
        con.close()
