"""D scorecard (SPEC §0, §7 ScoreInputs): which option (or panel) do we recommend?

Owner decisions (24 Oct 2026, WS3 thread):
  criteria   price, benefit-adjusted price, price robustness, commercial terms (no qualitative scores)
  normalise  min-max per criterion to 0-100 (best = 100, worst = 0); when the single options show no spread every
             option and panel scores 100 and the Scorecard / pack flag the criterion NO_SPREAD (owner, 25 Oct 2026, CR #22)
  SHARE      absolute scale, not min-max: score = 100 x min(share, 100%) / 100% - the share of the order filled
             (owner, 25 Oct 2026, CR #22), so a panel's capacity is credited up to a full placement
  terms      numeric terms from a structured run input terms_scores.csv (Terms sheet text kept beside for audit)
  panels     followers write at the lead's rates AND terms (owner, 24 Oct 2026, amends CR #12): a panel scores as
             its lead on every criterion except SHARE, which is the panel's capacity (sum of members' offered shares)
  scale      min-max is set by single options only; panels are placed on that scale and may fall outside 0-100
             (owner, 24 Oct 2026, HANDOVER item 16), so adding a panel never moves an option's score

Criteria (metric, direction, source):
  PRICE              RateIndex STANDARD TOTAL index                            lower is better   WS1 RateIndex
  PRICE_BENEFIT_ADJ  RateIndex STANDARD TOTAL index_benefit_adj                lower is better   WS1 RateIndex
  ROBUSTNESS_SPREAD  max - min TOTAL index over scenarios                      lower is better   WS1 RateIndex
  UNPRICED_SHARE     STANDARD TOTAL unpriced share                             lower is better   WS1 RateIndex
  V5_FLAG_SHARE      V5 flagged rate cells / rate cells                        lower is better   options.json
  COMMISSION         commission %                                              higher is better  terms_scores.csv
  PROFIT_SHARE       profit share %                                            higher is better  terms_scores.csv
  CORRIDOR           loss corridor (LR points retained by the cedant)          lower is better   terms_scores.csv
  CAP                loss-ratio cap on the reinsurer's liability (%)           higher is better  terms_scores.csv
  SHARE              share offered (%)                                         higher is better  terms_scores.csv
Directions are defaults; the run config may override them per criterion ("directions"). Weights must be given for
every criterion used, be >= 0 and sum to 1 (tolerance 1e-9): never renormalised silently. A criterion with weight 0
is still shown. An option missing a value for a weighted criterion is UNRANKED with the reason (never scored 0).

Panels: every metric is the lead's (the followers' own quotes are not used); SHARE = sum of the members' offered
shares, so a panel shows whether the lead's quote can be filled.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import ProposalRequired, SpecError

SCALES = {"SHARE": "ABSOLUTE"}            # criterion -> scale; others MINMAX (CR #22)
SHARE_FULL = 100.0                          # share_pct of a full placement (100% of the order)
CRITERIA = {
    "PRICE": ("index", "LOWER", "RateIndex STANDARD TOTAL"),
    "PRICE_BENEFIT_ADJ": ("index_benefit_adj", "LOWER", "RateIndex STANDARD TOTAL"),
    "ROBUSTNESS_SPREAD": ("index_spread", "LOWER", "RateIndex all scenarios TOTAL"),
    "UNPRICED_SHARE": ("unpriced_share", "LOWER", "RateIndex STANDARD TOTAL"),
    "V5_FLAG_SHARE": ("v5_flag_share", "LOWER", "options.json V5 counts"),
    "COMMISSION": ("commission_pct", "HIGHER", "terms_scores.csv"),
    "PROFIT_SHARE": ("profit_share_pct", "HIGHER", "terms_scores.csv"),
    "CORRIDOR": ("corridor_pts", "LOWER", "terms_scores.csv"),
    "CAP": ("cap_pct", "HIGHER", "terms_scores.csv"),
    "SHARE": ("share_pct", "HIGHER", "terms_scores.csv"),
}
TERM_CRITERIA = ("COMMISSION", "PROFIT_SHARE", "CORRIDOR", "CAP", "SHARE")
TERMS_COLUMNS = ["option_id", "commission_pct", "profit_share_pct", "corridor_pts", "cap_pct", "share_pct"]
WEIGHT_TOL = 1e-9
CELL_FLAGS = ("BLANK", "NON_NUMERIC", "NOT_POSITIVE", "OUTLIER", "NO_EXPIRING")


# ------------------------------------------------------------------------------------------------ inputs
def validate_weights(weights: dict) -> dict:
    if not weights:
        raise ProposalRequired("scorecard weights missing (run config 'scorecard.weights'; owner input)")
    unknown = sorted(set(weights) - set(CRITERIA))
    if unknown:
        raise SpecError(f"unknown criteria in weights: {unknown} (known: {sorted(CRITERIA)})")
    w = {k: float(v) for k, v in weights.items()}
    neg = [k for k, v in w.items() if v < 0 or v != v]
    if neg:
        raise SpecError(f"weights must be >= 0: {neg}")
    tot = sum(w.values())
    if abs(tot - 1.0) > WEIGHT_TOL:
        raise SpecError(f"weights sum to {tot:.12g}, not 1 (no silent renormalisation)")
    return w


def directions(cfg_dirs: dict | None = None) -> dict:
    d = {k: v[1] for k, v in CRITERIA.items()}
    for k, v in (cfg_dirs or {}).items():
        if k not in CRITERIA or v not in ("LOWER", "HIGHER"):
            raise SpecError(f"direction override {k}={v!r}: criterion must be known and direction LOWER/HIGHER")
        if SCALES.get(k) == "ABSOLUTE" and v != CRITERIA[k][1]:
            raise SpecError(f"direction override {k}={v!r}: {k} is scored on an absolute scale ({CRITERIA[k][1]} is "
                            "better); it cannot be reversed")
        d[k] = v
    return d


def read_terms_scores(path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"option_id": str})
    miss = [c for c in TERMS_COLUMNS if c not in df.columns]
    if miss:
        raise SpecError(f"terms_scores.csv missing columns {miss}")
    if df["option_id"].duplicated().any():
        raise SpecError("terms_scores.csv: duplicate option_id")
    for c in TERMS_COLUMNS[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def score_inputs(rate_index: pd.DataFrame, options_registry: dict, terms_scores: pd.DataFrame | None,
                 option_terms: pd.DataFrame | None = None) -> pd.DataFrame:
    """ScoreInputs (SPEC §7): option x criterion -> metric, value, source (+ text: the submitted Terms text)."""
    ri = rate_index[rate_index["cut"] == "TOTAL"]
    std = ri[ri["scenario"] == "STANDARD"].set_index("option_id")
    spread = ri.groupby("option_id")["index"].agg(lambda s: float(s.max() - s.min()))
    ts = terms_scores.set_index("option_id") if terms_scores is not None else None
    ot = option_terms.set_index("option_id") if option_terms is not None and len(option_terms) else None
    text_field = {"COMMISSION": "commission", "PROFIT_SHARE": "profit_share", "CORRIDOR": "corridor", "CAP": "cap",
                  "SHARE": "share_by_book"}
    rows = []
    for oid in sorted(std.index):
        e = options_registry.get(oid, {})
        n_cells = e.get("rate_cells") or 0
        flagged = sum(int(v) for k, v in (e.get("v5_counts") or {}).items() if k in CELL_FLAGS)
        vals = {"PRICE": std.loc[oid, "index"], "PRICE_BENEFIT_ADJ": std.loc[oid, "index_benefit_adj"],
                "ROBUSTNESS_SPREAD": spread.get(oid, np.nan), "UNPRICED_SHARE": std.loc[oid, "unpriced_share"],
                "V5_FLAG_SHARE": (flagged / n_cells) if n_cells else np.nan}
        for c in TERM_CRITERIA:
            col = CRITERIA[c][0]
            vals[c] = float(ts.loc[oid, col]) if ts is not None and oid in ts.index and pd.notna(ts.loc[oid, col]) else np.nan
        for c, v in vals.items():
            txt = None
            if c in text_field and ot is not None and oid in ot.index:
                t = ot.loc[oid, text_field[c]]
                txt = None if t is None or (isinstance(t, float) and t != t) else str(t)
            rows.append({"option_id": oid, "criterion": c, "metric": CRITERIA[c][0],
                         "value": float(v) if v is not None and v == v else np.nan, "source": CRITERIA[c][2],
                         "submitted_text": txt})
    return pd.DataFrame(rows, columns=["option_id", "criterion", "metric", "value", "source", "submitted_text"])


def panel_inputs(si: pd.DataFrame, rate_index: pd.DataFrame, panels: list) -> pd.DataFrame:
    """Panels: followers write at the lead's rates and terms, so every criterion is the lead's value; SHARE is the
    panel's capacity = sum of the members' offered shares (NaN if any member has none). Member shares (the intended
    allocation) must sum to 1."""
    if not panels:
        return si.iloc[0:0].copy()
    base = si.set_index(["option_id", "criterion"])["value"]
    rows = []
    for p in panels:
        pid, mem, lead = p["panel_id"], {k: float(v) for k, v in p["members"].items()}, p["lead"]
        if abs(sum(mem.values()) - 1.0) > WEIGHT_TOL:
            raise SpecError(f"panel {pid}: member shares sum to {sum(mem.values())}, not 1")
        if lead not in mem:
            raise SpecError(f"panel {pid}: lead {lead} is not a member")
        missing = [m for m in mem if m not in set(si["option_id"])]
        if missing:
            raise SpecError(f"panel {pid}: unknown member options {missing}")
        if pid in set(si["option_id"]):
            raise SpecError(f"panel id {pid} clashes with an option id")
        for c in CRITERIA:
            if c == "SHARE":
                vals = [base.get((m, c), np.nan) for m in sorted(mem)]
                v = float(sum(vals)) if all(x == x for x in vals) else np.nan
                src = "capacity: sum of members' offered shares"
            else:
                v, src = base.get((lead, c), np.nan), f"lead {lead} (followers write at the lead's rates and terms)"
            rows.append({"option_id": pid, "criterion": c, "metric": CRITERIA[c][0], "value": v, "source": src,
                         "submitted_text": None})
    return pd.DataFrame(rows, columns=si.columns)


# ------------------------------------------------------------------------------------------------ scoring
def normalise(values: pd.Series, direction: str, ref: pd.Series | None = None) -> pd.Series:
    """Min-max to 0-100, best = 100. NaN stays NaN. All equal (or a single value) -> 100. ref: boolean mask of the
    rows that set the scale (single options); other rows (panels) are placed on it and may fall outside 0-100."""
    v = values.astype(float)
    ok = v.notna()
    out = pd.Series(np.nan, index=v.index)
    if not ok.any():
        return out
    sc = ok & (ref if ref is not None else True)
    if not sc.any():
        sc = ok
    lo, hi = v[sc].min(), v[sc].max()
    if hi - lo <= 1e-15:          # no spread among the scale-setting rows: no scale, everyone scores 100
        out[ok] = 100.0
        return out
    out[ok] = (v[ok] - lo) / (hi - lo) * 100.0 if direction == "HIGHER" else (hi - v[ok]) / (hi - lo) * 100.0
    return out


def normalise_absolute(values: pd.Series, full: float = SHARE_FULL) -> pd.Series:
    """Absolute scale (SHARE): 100 x min(value, full) / full; negative values score 0; NaN stays NaN."""
    v = values.astype(float)
    return (v.clip(lower=0.0, upper=full) / full * 100.0).where(v.notna())


def scale_note(values: pd.Series, criterion: str, ref: pd.Series | None = None) -> str:
    """ABSOLUTE for absolute-scale criteria; NO_SPREAD when the scale-setting (single) options all have the same value,
    so the criterion separated nobody; '' otherwise."""
    if SCALES.get(criterion) == "ABSOLUTE":
        return "ABSOLUTE"
    v = values.astype(float)
    sc = v.notna() & (ref if ref is not None else True)
    if not sc.any():
        sc = v.notna()
    if sc.any() and v[sc].max() - v[sc].min() <= 1e-15:
        return "NO_SPREAD"
    return ""


def score(inputs: pd.DataFrame, weights: dict, dirs: dict | None = None, kinds: dict | None = None):
    """Returns (Scorecard long table, Ranking). kinds: option_id -> 'OPTION' | 'PANEL'."""
    w = validate_weights(weights)
    d = directions(dirs)
    used = [c for c in CRITERIA if c in w]
    wide = inputs.pivot_table(index="option_id", columns="criterion", values="value", aggfunc="first", dropna=False)
    for c in used:
        if c not in wide.columns:
            wide[c] = np.nan
    wide = wide[used].sort_index()
    ref = pd.Series([(kinds or {}).get(o, "OPTION") == "OPTION" for o in wide.index], index=wide.index)
    norm = pd.DataFrame({c: (normalise_absolute(wide[c]) if SCALES.get(c) == "ABSOLUTE" else normalise(wide[c], d[c], ref))
                         for c in used}, index=wide.index)
    notes = {c: scale_note(wide[c], c, ref) for c in used}
    long = []
    for oid in wide.index:
        for c in used:
            long.append({"option_id": oid, "criterion": c, "value": wide.loc[oid, c], "direction": d[c],
                         "normalised": norm.loc[oid, c], "weight": w[c],
                         "contribution": norm.loc[oid, c] * w[c] if norm.loc[oid, c] == norm.loc[oid, c] else np.nan,
                         "scale_note": notes[c]})
    sc = pd.DataFrame(long, columns=["option_id", "criterion", "value", "direction", "normalised", "weight", "contribution",
                                     "scale_note"])
    rk = []
    for oid in wide.index:
        miss = [c for c in used if w[c] > 0 and not norm.loc[oid, c] == norm.loc[oid, c]]
        tot = float(sum(norm.loc[oid, c] * w[c] for c in used if w[c] > 0)) if not miss else np.nan
        rk.append({"option_id": oid, "kind": (kinds or {}).get(oid, "OPTION"), "score": tot,
                   "status": "RANKED" if not miss else "UNRANKED",
                   "reason": "" if not miss else "missing value for weighted criteria: " + ", ".join(miss)})
    r = pd.DataFrame(rk)
    r = r.sort_values(["status", "score", "option_id"], ascending=[True, False, True], kind="stable").reset_index(drop=True)
    ranked = r["status"] == "RANKED"
    r["rank"] = np.nan
    # competition ranking with exact-score ties (1, 1, 3)
    sc_r = r.loc[ranked, "score"].round(9)
    r.loc[ranked, "rank"] = sc_r.rank(method="min", ascending=False).to_numpy()
    return sc, r[["option_id", "kind", "score", "rank", "status", "reason"]]


# ------------------------------------------------------------------------------------------------ sensitivity
def _norm_matrix(inputs, weights, dirs, kinds=None):
    w = validate_weights(weights)
    sc, rk = score(inputs, weights, dirs, kinds)
    ranked = rk[rk["status"] == "RANKED"]["option_id"].tolist()
    allc = [c for c in CRITERIA if c in w]
    piv = sc.pivot_table(index="option_id", columns="criterion", values="normalised", aggfunc="first")
    return piv.loc[ranked, allc], {c: w[c] for c in allc}


def one_at_a_time(inputs: pd.DataFrame, weights: dict, dirs: dict | None = None, kinds: dict | None = None) -> pd.DataFrame:
    """For each criterion c: weight t in [0, 1], the other weights scaled by (1 - t) / (1 - w_c) (keeping their
    proportions and the sum at 1). Scores are linear in t, so the leader changes exactly where two score lines cross.
    Output: criterion, t_from, t_to, leader, runner_up (intervals over [0, 1]) and the current weight."""
    N, w = _norm_matrix(inputs, weights, dirs, kinds)
    if len(N) < 2:
        return pd.DataFrame(columns=["criterion", "current_weight", "t_from", "t_to", "leader", "margin_at_mid"])
    out = []
    crits = list(w)
    for c in crits:
        wc = w[c]
        others = [k for k in crits if k != c]
        so = sum(w[k] for k in others)
        if so <= 0:
            base = N[others].mean(axis=1) if others else pd.Series(0.0, index=N.index)   # c had weight 1
        else:
            base = sum(N[k] * (w[k] / so) for k in others)
        a = base.to_numpy()                       # score at t = 0
        b = N[c].to_numpy() - a                   # slope
        ts = {0.0, 1.0}
        for i, j in itertools.combinations(range(len(N)), 2):
            if abs(b[i] - b[j]) > 1e-15:
                t = (a[j] - a[i]) / (b[i] - b[j])
                if 0.0 < t < 1.0:
                    ts.add(round(float(t), 12))
        ts = sorted(ts)
        prev = None
        for t0, t1 in zip(ts, ts[1:]):
            tm = (t0 + t1) / 2
            s = a + b * tm
            order = np.argsort(-s, kind="stable")
            leader = N.index[order[0]]
            margin = float(s[order[0]] - s[order[1]])
            if prev is not None and prev["leader"] == leader:
                prev["t_to"] = t1
                prev["margin_at_mid"] = min(prev["margin_at_mid"], margin)
                continue
            prev = {"criterion": c, "current_weight": wc, "t_from": t0, "t_to": t1, "leader": leader, "margin_at_mid": margin}
            out.append(prev)
    return pd.DataFrame(out, columns=["criterion", "current_weight", "t_from", "t_to", "leader", "margin_at_mid"])


def flip_points(oat: pd.DataFrame) -> pd.DataFrame:
    """The weight at which the leader changes, per criterion (nearest to the current weight first)."""
    rows = []
    for c, g in oat.groupby("criterion", sort=False):
        g = g.sort_values("t_from")
        for (_, r0), (_, r1) in zip(g.iterrows(), list(g.iterrows())[1:]):
            rows.append({"criterion": c, "current_weight": r0["current_weight"], "flip_weight": r0["t_to"],
                         "leader_below": r0["leader"], "leader_above": r1["leader"],
                         "distance": abs(r0["t_to"] - r0["current_weight"])})
    df = pd.DataFrame(rows, columns=["criterion", "current_weight", "flip_weight", "leader_below", "leader_above", "distance"])
    return df.sort_values(["distance", "criterion"], kind="stable").reset_index(drop=True)


def grid(inputs: pd.DataFrame, weights: dict, dirs: dict | None = None, step: float = 0.1,
         max_points: int = 200_000, kinds: dict | None = None) -> pd.DataFrame:
    """Every weight vector on the simplex grid (multiples of step summing to 1) over the weighted criteria:
    share of grid points where each option ranks first (ties split equally)."""
    N, w = _norm_matrix(inputs, weights, dirs, kinds)
    crits = [c for c in w if w[c] > 0]
    k = round(1 / step)
    if abs(k * step - 1) > 1e-9:
        raise SpecError("grid step must divide 1")
    from math import comb
    n_pts = comb(k + len(crits) - 1, len(crits) - 1)
    if n_pts > max_points:
        raise ProposalRequired(f"grid has {n_pts} points (> {max_points}); use a coarser step")
    M = N[crits].to_numpy()
    wins = np.zeros(len(N))
    pts = 0
    for comp in _compositions(k, len(crits)):
        s = M @ (np.array(comp) / k)
        best = np.isclose(s, s.max(), rtol=0, atol=1e-9)
        wins[best] += 1.0 / best.sum()
        pts += 1
    return pd.DataFrame({"option_id": N.index, "win_share": wins / pts, "grid_points": pts, "step": step})


def _compositions(n, k):
    if k == 1:
        yield (n,)
        return
    for i in range(n + 1):
        for rest in _compositions(n - i, k - 1):
            yield (i,) + rest


# ------------------------------------------------------------------------------------------------ run + pack
def load_scorecard_config(cfg: dict) -> dict:
    sc = cfg.get("scorecard")
    if not sc:
        raise ProposalRequired("run config has no 'scorecard' section (weights, terms_scores, panels)")
    return sc


def run_scorecard(cfg: dict, runs_root=None) -> dict:
    from .outputs import read_table, run_dir, update_manifest, write_table
    from .rate_index import _path
    rd = run_dir(cfg["run_id"], runs_root)
    sc_cfg = load_scorecard_config(cfg)
    wpath = sc_cfg.get("weights_file")
    weights = json.loads(_path(cfg, wpath).read_text(encoding="utf-8"))["weights"] if wpath else sc_cfg.get("weights")
    out = rd / "out"
    if not (out / "RateIndex.parquet").exists():
        raise ProposalRequired(f"run {cfg['run_id']}: RateIndex not found - run 'index' first")
    ri = read_table("RateIndex", out)
    ot = read_table("OptionTerms", out) if (out / "OptionTerms.parquet").exists() else None
    reg_p = rd / "options.json"
    reg = json.loads(reg_p.read_text(encoding="utf-8")) if reg_p.exists() else {}
    ts = read_terms_scores(_path(cfg, sc_cfg["terms_scores"])) if sc_cfg.get("terms_scores") else None
    si = score_inputs(ri, reg, ts, ot)
    pi = panel_inputs(si, ri, sc_cfg.get("panels") or [])
    allin = pd.concat([si, pi], ignore_index=True)
    kinds = {**{o: "OPTION" for o in si["option_id"].unique()}, **{p: "PANEL" for p in pi["option_id"].unique()}}
    card, rank = score(allin, weights, sc_cfg.get("directions"), kinds)
    oat = one_at_a_time(allin, weights, sc_cfg.get("directions"), kinds)
    flips = flip_points(oat)
    gr = grid(allin, weights, sc_cfg.get("directions"), sc_cfg.get("grid_step", 0.1), kinds=kinds)
    m = {"ScoreInputs": write_table("ScoreInputs", allin, out, ["option_id", "criterion"], contract=False),
         "Scorecard": write_table("Scorecard", card, out, ["option_id", "criterion"], contract=False),
         "Ranking": write_table("Ranking", rank, out, None, contract=False),
         "WeightSensitivity": write_table("WeightSensitivity", oat, out, ["criterion", "t_from"], contract=False),
         "WeightFlips": write_table("WeightFlips", flips, out, None, contract=False),
         "WeightGrid": write_table("WeightGrid", gr, out, ["option_id"], contract=False)}
    pack = write_pack(out / f"Recommendation_Pack_{cfg['run_id']}.xlsx", cfg["run_id"], allin, card, rank, oat, flips, gr,
                      weights, sc_cfg, ot)
    update_manifest(rd, "outputs", {**m, "RecommendationPack": {"xlsx": pack.name}})
    update_manifest(rd, "scorecard", {"weights": weights, "directions": directions(sc_cfg.get("directions")),
                                      "panels": sc_cfg.get("panels") or []})
    return {"ScoreInputs": allin, "Scorecard": card, "Ranking": rank, "Sensitivity": oat, "Flips": flips, "Grid": gr,
            "pack": pack, "dir": rd}


def check_market_facing(texts: list, banned: list) -> None:
    """No incumbent name in market-facing outputs (CLAUDE.md data boundary)."""
    low = [b.lower() for b in banned if b]
    hits = sorted({b for t in texts if t for b in low if b in str(t).lower()})
    if hits:
        raise SpecError(f"market-facing output would name the incumbent: {hits}")


def write_pack(path: Path, run_id, inputs, card, rank, oat, flips, gr, weights, sc_cfg, option_terms) -> Path:
    """Recommendation pack inputs (Excel). Options are shown by option_id; reinsurer names only when the run config
    sets show_reinsurer_names. With market_facing true, the configured incumbent names must not appear anywhere."""
    from .io_excel import new_workbook
    show_names = bool(sc_cfg.get("show_reinsurer_names"))
    names = {}
    if show_names and option_terms is not None:
        names = {r.option_id: r.reinsurer for r in option_terms.itertuples() if r.reinsurer}
    label = lambda oid: f"{oid} ({names[oid]})" if oid in names else oid  # noqa: E731
    texts = []
    wb = new_workbook(path, title=f"Recommendation pack {run_id}")
    h = wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1})
    t = wb.add_format({"bold": True, "font_size": 14})
    n2 = wb.add_format({"num_format": "0.00"})
    n4 = wb.add_format({"num_format": "0.0000"})
    pct = wb.add_format({"num_format": "0.0%"})

    def table(ws, r0, cols, rows, fmts=None):
        ws.write_row(r0, 0, cols, h)
        for i, row in enumerate(rows, start=1):
            for j, v in enumerate(row):
                if v is None or (isinstance(v, float) and v != v):
                    continue
                if isinstance(v, (int, float, np.floating)) and not isinstance(v, bool):
                    ws.write_number(r0 + i, j, float(v), (fmts or {}).get(cols[j]))
                else:
                    ws.write_string(r0 + i, j, str(v))
                    texts.append(str(v))
        return r0 + len(rows) + 2

    ws = wb.add_worksheet("Summary")
    ws.set_column(0, 0, 28)
    ws.set_column(1, 6, 16)
    ws.write(0, 0, f"Scorecard - run {run_id}", t)
    r = table(ws, 2, ["option", "kind", "score", "rank", "status", "reason"],
              [[label(x.option_id), x.kind, x.score, x.rank, x.status, x.reason] for x in rank.itertuples()],
              {"score": n2, "rank": None})
    notes = card.drop_duplicates("criterion").set_index("criterion")["scale_note"].to_dict() if "scale_note" in card else {}
    r = table(ws, r, ["criterion", "weight", "direction", "scale_note"],
              [[c, w, directions(sc_cfg.get("directions"))[c], notes.get(c, "")] for c, w in weights.items()],
              {"weight": pct})
    nospread = [c for c, n in notes.items() if n == "NO_SPREAD" and weights.get(c, 0) > 0]
    if nospread:
        ws.write(r, 0, "NO_SPREAD: every single option has the same value on " + ", ".join(nospread) + " - these "
                       "weights add the same points to everyone and separate no one.", wb.add_format({"italic": True}))
        r += 2
    ws.write(r, 0, "Nearest ranking flips (one-at-a-time)", wb.add_format({"bold": True}))
    table(ws, r + 1, ["criterion", "current_weight", "flip_weight", "leader_below", "leader_above"],
          [[f.criterion, f.current_weight, f.flip_weight, label(f.leader_below), label(f.leader_above)]
           for f in flips.head(10).itertuples()], {"current_weight": pct, "flip_weight": pct})
    ws = wb.add_worksheet("Scorecard")
    ws.set_column(0, 6, 16)
    table(ws, 0, ["option", "criterion", "value", "direction", "normalised", "weight", "contribution", "scale_note"],
          [[label(x.option_id), x.criterion, x.value, x.direction, x.normalised, x.weight, x.contribution, x.scale_note]
           for x in card.itertuples()], {"value": n4, "normalised": n2, "weight": pct, "contribution": n2})
    ws = wb.add_worksheet("Inputs")
    ws.set_column(0, 5, 18)
    table(ws, 0, ["option", "criterion", "metric", "value", "source", "submitted_text"],
          [[label(x.option_id), x.criterion, x.metric, x.value, x.source, x.submitted_text] for x in inputs.itertuples()],
          {"value": n4})
    ws = wb.add_worksheet("Sensitivity")
    ws.set_column(0, 5, 16)
    r = table(ws, 0, ["criterion", "current_weight", "t_from", "t_to", "leader", "margin_at_mid"],
              [[x.criterion, x.current_weight, x.t_from, x.t_to, label(x.leader), x.margin_at_mid] for x in oat.itertuples()],
              {"current_weight": pct, "t_from": pct, "t_to": pct, "margin_at_mid": n2})
    table(ws, r, ["option", "win_share", "grid_points", "step"],
          [[label(x.option_id), x.win_share, x.grid_points, x.step] for x in gr.itertuples()], {"win_share": pct})
    wb.close()
    if sc_cfg.get("market_facing"):
        try:
            check_market_facing(texts, sc_cfg.get("incumbent_names") or [])
        except SpecError:
            Path(path).unlink(missing_ok=True)
            raise
    return Path(path)
