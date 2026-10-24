"""B2 rate index (SPEC §0, §5, §7): standardised rate change of each option vs expiring, overall and by cut.

Both catalogues are priced on the SAME exposure cells with catalogue default options (SPEC §3.4):
    RateFactors  option x cell:  rate_expiring, rate_option, factor = rate_option / rate_expiring, priced_status
    RateIndex    option x cut:   lives = sum w, prem_x = sum w * rate_x over cells priced under both,
                                 index = prem_option / prem_expiring,
                                 index_benefit_adj = sum w * rate_option / ratio(plan) / prem_expiring
Weights w (standard mix, SPEC §5): latest UWY, lives in force at the snapshot date. Sensitivities: written_ly
weights, and the UWY-1 mix. REFER / UNMATCHED cells (under either catalogue) are excluded from the index and
reported with their weight share. The headline index uses the full rated premium (base x factors + modules + fees);
the split columns show the base-only change (base x rating factors, cells whose base prices under both) and the rider
change (additive modules, cells fully priced under both) (owner decision 24 Oct 2026, HANDOVER item 11). The
TreatyFeed stays on full premium.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import ProposalRequired, SpecError
from .evaluator import evaluate
from .model import Catalogue

STANDARD_WEIGHT = "lives_inforce"
CELL_KEY_COLS = ["product_type", "regulator", "rating_region", "tpa", "plan", "age", "gender", "marital", "member_category",
                 "maternity_eligible", "nationality_group", "group_size_band"]
DEFAULT_CUTS = [[], ["product_type"], ["product_type", "rating_region"], ["product_type", "rating_region", "tpa"],
                ["product_type", "rating_region", "tpa", "plan"]]


def select_mix(cells: pd.DataFrame, uwy: int | None = None, offset: int = 0) -> tuple[pd.DataFrame, int]:
    """Cells of the latest UWY (or the given UWY) minus offset years (offset=1: UWY-1 sensitivity)."""
    if "uwy" not in cells.columns:
        raise SpecError("exposure cells carry no 'uwy' column")
    years = sorted(int(y) for y in cells["uwy"].dropna().unique())
    if not years:
        raise SpecError("exposure cells have no UWY")
    base = uwy if uwy is not None else years[-1]
    target = base - offset
    sub = cells[cells["uwy"] == target]
    if sub.empty:
        raise ProposalRequired(f"no exposure for UWY {target} (available {years})")
    return sub.copy(), target


def aggregate_cells(cells: pd.DataFrame, weight: str) -> pd.DataFrame:
    """Collapse exposure cells to the pricing key (drops uwy / new_renewal / distribution / network splits)."""
    if weight not in cells.columns:
        raise SpecError(f"weight column '{weight}' not in exposure cells")
    w = pd.to_numeric(cells[weight], errors="coerce")
    if w.isna().all():
        raise ProposalRequired(f"weight '{weight}' is empty: build exposure with a snapshot date for lives_inforce, "
                               "or choose written_ly")
    keys = [c for c in CELL_KEY_COLS if c in cells.columns]
    df = cells[keys].copy()
    df["w"] = w.fillna(0.0)
    for c in keys:
        if c not in ("age", "group_size_band"):
            df[c] = df[c].astype(object).map(lambda v: "" if v is None or (isinstance(v, float) and v != v) else v)
    g = df.groupby(keys, sort=True, dropna=False)["w"].sum().reset_index()
    for c in keys:
        if c not in ("age", "group_size_band"):
            g[c] = g[c].map(lambda v: None if v == "" else v).astype(object)
    g = g[g["w"] > 0].reset_index(drop=True)
    g.insert(0, "cell_id", np.arange(len(g), dtype="int64"))
    return g


def rate_factors(expiring: Catalogue, option: Catalogue, option_id: str, cells: pd.DataFrame,
                 options: dict | None = None) -> pd.DataFrame:
    """RateFactors for one option on aggregated cells (must carry cell_id, the pricing key and 'w')."""
    opts = {"fill": "default", **(options or {})}
    e, _ = evaluate(expiring, cells, opts)
    o, _ = evaluate(option, cells, opts)
    m = cells.merge(e[["cell_id", "status", "price", "reason", "price_base", "price_riders"]].rename(
        columns={"status": "status_expiring", "price": "rate_expiring", "reason": "reason_expiring",
                 "price_base": "rate_expiring_base", "price_riders": "rate_expiring_riders"}), on="cell_id")
    m = m.merge(o[["cell_id", "status", "price", "reason", "price_base", "price_riders"]].rename(
        columns={"status": "status_option", "price": "rate_option", "reason": "reason_option",
                 "price_base": "rate_option_base", "price_riders": "rate_option_riders"}), on="cell_id")
    both = (m["status_expiring"] == "PRICED") & (m["status_option"] == "PRICED")
    refer = (m["status_expiring"] == "REFER") | (m["status_option"] == "REFER")
    m["priced_status"] = np.where(both, "PRICED", np.where(refer, "REFER", "UNMATCHED"))
    m["factor"] = np.where(both & (m["rate_expiring"] > 0), m["rate_option"] / m["rate_expiring"], np.nan)
    m.insert(0, "option_id", option_id)
    keys = [c for c in CELL_KEY_COLS if c in cells.columns]
    cols = ["option_id"] + keys + ["rate_expiring", "rate_option", "factor", "priced_status",
                                   "w", "status_expiring", "status_option", "reason_expiring", "reason_option",
                                   "rate_expiring_base", "rate_option_base", "rate_expiring_riders", "rate_option_riders"]
    return m[cols].sort_values(keys, kind="stable").reset_index(drop=True)


RATE_FACTOR_EXTRAS = ("w", "status_expiring", "status_option", "reason_expiring", "reason_option",
                      "rate_expiring_base", "rate_option_base", "rate_expiring_riders", "rate_option_riders")
RATE_INDEX_EXTRAS = ("cut", "lives_unpriced", "lives_refer", "unpriced_share", "weight", "mix_uwy",
                     "prem_expiring_base", "prem_option_base", "index_base",
                     "prem_expiring_riders", "prem_option_riders", "index_riders")


def rate_index(rf: pd.DataFrame, cuts=None, benefit_ratio: pd.DataFrame | None = None, weight: str = STANDARD_WEIGHT,
               mix_uwy: int | None = None) -> pd.DataFrame:
    """RateIndex from RateFactors. benefit_ratio: DataFrame[option_id, plan, ratio] (BenefitFactors); the
    benefit-adjusted index divides each cell's option rate by its plan's ratio. Missing ratio -> NaN, never 1."""
    cuts = DEFAULT_CUTS if cuts is None else cuts
    rf = rf.copy()
    pr = rf["priced_status"] == "PRICED"
    rf["_we"] = np.where(pr, rf["w"] * rf["rate_expiring"], 0.0)
    rf["_wo"] = np.where(pr, rf["w"] * rf["rate_option"], 0.0)
    rf["_wl"] = np.where(pr, rf["w"], 0.0)
    rf["_wu"] = np.where(~pr, rf["w"], 0.0)
    rf["_wr"] = np.where(rf["priced_status"] == "REFER", rf["w"], 0.0)
    if "rate_expiring_base" in rf.columns:
        pb = rf["rate_expiring_base"].notna() & rf["rate_option_base"].notna()
        rf["_web"] = np.where(pb, rf["w"] * rf["rate_expiring_base"].fillna(0.0), 0.0)
        rf["_wob"] = np.where(pb, rf["w"] * rf["rate_option_base"].fillna(0.0), 0.0)
        rf["_wer"] = np.where(pr, rf["w"] * rf["rate_expiring_riders"].fillna(0.0), 0.0)
        rf["_wor"] = np.where(pr, rf["w"] * rf["rate_option_riders"].fillna(0.0), 0.0)
    else:
        for c in ("_web", "_wob", "_wer", "_wor"):
            rf[c] = np.nan
    if benefit_ratio is not None and len(benefit_ratio):
        br = benefit_ratio[["option_id", "plan", "ratio"]].drop_duplicates(["option_id", "plan"])
        rf = rf.merge(br, on=["option_id", "plan"], how="left")
        rf["_woa"] = np.where(pr, rf["w"] * rf["rate_option"] / rf["ratio"], 0.0)
        rf.loc[pr & rf["ratio"].isna(), "_woa"] = np.nan
    else:
        rf["_woa"] = np.nan
    all_dims = []
    for c in cuts:
        for d in c:
            if d not in all_dims:
                all_dims.append(d)
    out = []
    for cut in cuts:
        gcols = ["option_id"] + list(cut)
        g = rf.groupby(gcols, sort=True, dropna=False).agg(
            lives=("_wl", "sum"), prem_expiring=("_we", "sum"), prem_option=("_wo", "sum"),
            prem_option_adj=("_woa", lambda s: s.sum(min_count=len(s)) if s.notna().all() else np.nan),
            lives_unpriced=("_wu", "sum"), lives_refer=("_wr", "sum"),
            prem_expiring_base=("_web", "sum"), prem_option_base=("_wob", "sum"),
            prem_expiring_riders=("_wer", "sum"), prem_option_riders=("_wor", "sum")).reset_index()
        g["cut"] = "TOTAL" if not cut else "x".join(cut)
        for d in all_dims:
            if d not in cut:
                g[d] = None
        out.append(g)
    r = pd.concat(out, ignore_index=True)
    r["index"] = np.where(r["prem_expiring"] > 0, r["prem_option"] / r["prem_expiring"], np.nan)
    r["index_benefit_adj"] = np.where(r["prem_expiring"] > 0, r["prem_option_adj"] / r["prem_expiring"], np.nan)
    r["index_base"] = np.where(r["prem_expiring_base"] > 0, r["prem_option_base"] / r["prem_expiring_base"], np.nan)
    r["index_riders"] = np.where(r["prem_expiring_riders"] > 0, r["prem_option_riders"] / r["prem_expiring_riders"], np.nan)
    tot = r["lives"] + r["lives_unpriced"]
    r["unpriced_share"] = np.where(tot > 0, r["lives_unpriced"] / tot, np.nan)
    r["weight"] = weight
    r["mix_uwy"] = mix_uwy
    cols = ["option_id", "cut"] + all_dims + ["lives", "prem_expiring", "prem_option", "index", "index_benefit_adj",
                                              "lives_unpriced", "lives_refer", "unpriced_share", "weight", "mix_uwy",
                                              "prem_expiring_base", "prem_option_base", "index_base",
                                              "prem_expiring_riders", "prem_option_riders", "index_riders"]
    return r[cols]


def run_index(expiring: Catalogue, options: dict, exposure_cells: pd.DataFrame, cuts=None, benefit_ratio=None,
              eval_options: dict | None = None, uwy: int | None = None):
    """Standard index plus sensitivities. options: {option_id: Catalogue}.
    Returns (RateFactors on the standard mix, RateIndex with a 'scenario' column: STANDARD, WRITTEN_LY, UWY_MINUS_1)."""
    mix, y = select_mix(exposure_cells, uwy)
    scen = [("STANDARD", mix, STANDARD_WEIGHT, y), ("WRITTEN_LY", mix, "written_ly", y)]
    try:
        prev, y1 = select_mix(exposure_cells, uwy if uwy is not None else y, offset=1)
        scen.append(("UWY_MINUS_1", prev, STANDARD_WEIGHT, y1))
    except ProposalRequired:
        pass
    rfs, ris = [], []
    std_rf = None
    for name, cells, w, yy in scen:
        try:
            agg = aggregate_cells(cells, w)
        except ProposalRequired:
            if name == "STANDARD":
                raise
            continue
        parts = [rate_factors(expiring, cat, oid, agg, eval_options) for oid, cat in sorted(options.items())]
        rf = pd.concat(parts, ignore_index=True)
        ri = rate_index(rf, cuts, benefit_ratio, w, yy)
        ri.insert(1, "scenario", name)
        ris.append(ri)
        if name == "STANDARD":
            std_rf = rf
    return std_rf, pd.concat(ris, ignore_index=True)


# ------------------------------------------------------------------------------------------- TreatyFeed / OptionTerms
def treaty_books(rf: pd.DataFrame, book_map: pd.DataFrame) -> pd.Series:
    """treaty_book_map.csv (run input, owner decision 24 Oct 2026): product_type, rating_region, tpa -> treaty_book;
    ANY allowed; most specific row wins. Unmapped cells raise MappingRequired."""
    from . import MappingRequired
    from .exposure import _resolve
    need = ["product_type", "rating_region", "tpa"]
    for c in need + ["treaty_book"]:
        if c not in book_map.columns:
            raise SpecError(f"treaty_book_map needs column '{c}'")
    df = rf[need].astype(object).map(lambda v: "" if v is None else str(v))
    res, um = _resolve(df, book_map.astype(object), {c: c for c in need}, ["treaty_book"], "treaty_book_map.csv")
    if um:
        raise MappingRequired(f"{len(um)} cell group(s) have no treaty book", um)
    return res["treaty_book"]


def treaty_feed(rf: pd.DataFrame, book_map: pd.DataFrame, lapse: dict, experience: pd.DataFrame) -> pd.DataFrame:
    """TreatyFeed (SPEC §7) per option x treaty book, on the standard-mix RateFactors:
        rate factor            = book index (sum w * rate_option / sum w * rate_expiring, priced cells)
        premium_change_pct     = rate factor x (1 - lapse) - 1                     (lapse: run input per book)
        lr_adjustment_pts      = (as-if LR - experience LR) x 100, as-if LR = claims / (earned premium x rate factor)
                                 (experience.csv per book: treaty_book, earned_prem, ultimate_claims; run input)
    Missing lapse or experience for a book raises ProposalRequired (never 0)."""
    rf = rf.copy()
    rf["treaty_book"] = treaty_books(rf, book_map).to_numpy()
    pr = rf["priced_status"] == "PRICED"
    rf["we"] = np.where(pr, rf["w"] * rf["rate_expiring"], 0.0)
    rf["wo"] = np.where(pr, rf["w"] * rf["rate_option"], 0.0)
    g = rf.groupby(["option_id", "treaty_book"], sort=True)[["we", "wo"]].sum().reset_index()
    exp = experience.set_index("treaty_book")
    out = []
    for r in g.itertuples(index=False):
        if r.treaty_book not in lapse:
            raise ProposalRequired(f"lapse assumption missing for treaty book '{r.treaty_book}' (run config 'lapse')")
        if r.treaty_book not in exp.index:
            raise ProposalRequired(f"experience missing for treaty book '{r.treaty_book}' (experience.csv)")
        if r.we <= 0:
            raise ProposalRequired(f"treaty book '{r.treaty_book}': no priced exposure for option {r.option_id}")
        f = r.wo / r.we
        lp = float(lapse[r.treaty_book])
        prem, clm = float(exp.loc[r.treaty_book, "earned_prem"]), float(exp.loc[r.treaty_book, "ultimate_claims"])
        if prem <= 0:
            raise ProposalRequired(f"treaty book '{r.treaty_book}': earned premium must be > 0")
        lr = clm / prem
        asif = clm / (prem * f)
        out.append({"option_id": r.option_id, "treaty_book": r.treaty_book, "premium_change_pct": (f * (1 - lp) - 1) * 100,
                    "lr_adjustment_pts": (asif - lr) * 100,
                    "basis_note": f"rate factor {f:.6f} (standard mix index); lapse {lp:.4f}; experience LR {lr:.4%}; "
                                  f"as-if LR {asif:.4%}",
                    "rate_factor": f, "lapse": lp, "experience_lr": lr, "asif_lr": asif})
    return pd.DataFrame(out, columns=["option_id", "treaty_book", "premium_change_pct", "lr_adjustment_pts", "basis_note",
                                      "rate_factor", "lapse", "experience_lr", "asif_lr"])


TREATY_FEED_EXTRAS = ("rate_factor", "lapse", "experience_lr", "asif_lr")
TERM_FIELDS = ["reinsurer", "share_by_book", "premium_basis", "commission", "corridor", "cap", "profit_share",
               "conditions", "validity"]


def option_terms(terms_by_option: dict) -> pd.DataFrame:
    """OptionTerms (SPEC §7) from each submission's Terms sheet (free text kept as submitted)."""
    rows = []
    for oid, t in sorted(terms_by_option.items()):
        rows.append({"option_id": oid, **{f: t.get(f) for f in TERM_FIELDS}, "comments": t.get("comments")})
    return pd.DataFrame(rows, columns=["option_id"] + TERM_FIELDS + ["comments"])


# ------------------------------------------------------------------------------------------- run orchestration
def load_run_config(path) -> dict:
    """run_config.json (paths relative to the config file):
    {"run_id", "expiring": catalogue.json | spec.json,
     "exposure": {"dim_life", "maps", "manifest"?, "snapshot_date", "contract_version"?},
     "cuts"?: [[dims], ...], "eval_options"?: {...evaluator options...},
     "treaty"?: {"book_map": csv, "lapse": {book: x}, "experience": csv},
     "benefit_overrides"?: [{"family", "option", "relativity"}], "v5"?: {"outlier_band": [lo, hi]},
     "duckdb"?: {"memory_limit", "threads"}}"""
    import json
    from pathlib import Path
    p = Path(path).resolve()
    cfg = json.loads(p.read_text(encoding="utf-8"))
    cfg["_base"] = str(p.parent)
    return cfg


def _path(cfg, rel):
    from pathlib import Path
    return (Path(cfg["_base"]) / rel).resolve()


def load_catalogue_any(path):
    import json
    from pathlib import Path
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if "catalogue_id" in d:
        return Catalogue.from_dict(d)
    from .spec_parser import parse_catalogue
    return parse_catalogue(Path(path))


def _standard_mix(cfg: dict, exposure=None) -> pd.DataFrame | None:
    """Aggregated standard-mix cells (latest UWY, lives in force) for B1 module values; None without exposure config."""
    ec = cfg.get("exposure") or {}
    if exposure is None:
        if not (ec.get("dim_life") and ec.get("maps") and ec.get("snapshot_date")):
            return None
        from .exposure import build_exposure
        exposure = build_exposure(_path(cfg, ec["dim_life"]), _path(cfg, ec["maps"]),
                                  _path(cfg, ec["manifest"]) if ec.get("manifest") else None,
                                  contract_version=ec.get("contract_version"), snapshot_date=ec["snapshot_date"],
                                  strict=False)
    mix, _ = select_mix(exposure.cells)
    return aggregate_cells(mix, STANDARD_WEIGHT)


def run_benefit(cfg: dict, runs_root=None, exposure=None):
    from .benefit_value import BENEFIT_DIFF_EXTRAS, BENEFIT_FACTORS_EXTRAS, benefit_diff
    from .outputs import run_dir, update_manifest, write_table
    from .template.ingest import registered_options
    rd = run_dir(cfg["run_id"], runs_root)
    expiring = load_catalogue_any(_path(cfg, cfg["expiring"]))
    opts = registered_options(cfg["run_id"], runs_root)
    if not opts:
        raise ProposalRequired(f"run {cfg['run_id']}: no options registered (t ingest first)")
    ov = {(o["family"], str(o["option"])): o["relativity"] for o in cfg.get("benefit_overrides", [])}
    mix = _standard_mix(cfg, exposure)
    eopts = {**(cfg.get("eval_options") or {}), **({"duckdb": cfg["duckdb"]} if cfg.get("duckdb") else {})}
    bds, bfs = [], []
    for oid, cat in sorted(opts.items()):
        bd, bf = benefit_diff(expiring, cat, oid, ov, mix=mix, eval_options=eopts)
        bds.append(bd)
        bfs.append(bf)
    bd, bf = pd.concat(bds, ignore_index=True), pd.concat(bfs, ignore_index=True)
    out = rd / "out"
    m = {"BenefitDiff": write_table("BenefitDiff", bd, out, ["option_id", "scope_id", "plan", "benefit_code"],
                                    extra_ok=BENEFIT_DIFF_EXTRAS),
         "BenefitFactors": write_table("BenefitFactors", bf, out, ["option_id", "scope_id", "plan"],
                                       extra_ok=BENEFIT_FACTORS_EXTRAS)}
    update_manifest(rd, "outputs", m)
    return bd, bf


def run_b2(cfg: dict, runs_root=None) -> dict:
    """Exposure (V0 + coverage report) -> B1 level 1 -> RateFactors / RateIndex (+ sensitivities) -> TreatyFeed ->
    OptionTerms, written to runs/<RunID>/out with the manifest."""
    import json
    from .benefit_value import plan_ratio
    from .exposure import build_exposure, coverage_report
    from .outputs import run_dir, update_manifest, write_table
    from .template.ingest import registered_options
    rd = run_dir(cfg["run_id"], runs_root)
    expiring = load_catalogue_any(_path(cfg, cfg["expiring"]))
    opts = registered_options(cfg["run_id"], runs_root)
    if not opts:
        raise ProposalRequired(f"run {cfg['run_id']}: no options registered (t ingest first)")
    ec = cfg["exposure"]
    if not ec.get("snapshot_date"):
        raise ProposalRequired("exposure.snapshot_date is required for the standard mix (lives in force, SPEC §5)")
    ex = build_exposure(_path(cfg, ec["dim_life"]), _path(cfg, ec["maps"]),
                        _path(cfg, ec["manifest"]) if ec.get("manifest") else None,
                        contract_version=ec.get("contract_version"), snapshot_date=ec["snapshot_date"], strict=False)
    eopts = {**(cfg.get("eval_options") or {}), **({"duckdb": cfg["duckdb"]} if cfg.get("duckdb") else {})}
    cov = coverage_report(expiring, ex, eopts)
    bd, bf = run_benefit(cfg, runs_root, exposure=ex)
    rf, ri = run_index(expiring, opts, ex.cells, cfg.get("cuts"), plan_ratio(bf), eopts)
    out = rd / "out"
    keys = [c for c in CELL_KEY_COLS if c in rf.columns]
    m = {"RateFactors": write_table("RateFactors", rf, out, ["option_id"] + keys, extra_ok=RATE_FACTOR_EXTRAS),
         "RateIndex": write_table("RateIndex", ri, out, None, extra_ok=RATE_INDEX_EXTRAS + ("scenario",))}
    tf = None
    if cfg.get("treaty"):
        t = cfg["treaty"]
        bm = pd.read_csv(_path(cfg, t["book_map"]), dtype=str, keep_default_na=False)
        xp = pd.read_csv(_path(cfg, t["experience"]))
        tf = treaty_feed(rf, bm, t.get("lapse") or {}, xp)
        m["TreatyFeed"] = write_table("TreatyFeed", tf, out, ["option_id", "treaty_book"], extra_ok=TREATY_FEED_EXTRAS)
    terms = {}
    for oid in opts:
        tp = rd / "options" / oid / "terms.json"
        terms[oid] = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
    m["OptionTerms"] = write_table("OptionTerms", option_terms(terms), out, ["option_id"], extra_ok=("comments",))
    update_manifest(rd, "outputs", m)
    update_manifest(rd, "gates", {"V0": ex.v0["status"], "COVERAGE": {"status": cov["status"],
                                                                     "matched_share": cov["matched_share"]}})
    update_manifest(rd, "inputs", {"expiring": {"catalogue_id": expiring.catalogue_id, "hash": expiring.content_hash()},
                                   "exposure": {"snapshot_date": ec["snapshot_date"], "cells": int(len(ex.cells))}})
    return {"RateFactors": rf, "RateIndex": ri, "BenefitDiff": bd, "BenefitFactors": bf, "TreatyFeed": tf,
            "coverage": cov, "dir": rd}
