"""B1 benefit value, level 1 (SPEC §4.3): is each option richer or leaner than expiring, by benefit line and in total?

Per plan (matched by scope product x region x TPA and plan_id), each factor-valued benefit line is the plan's
standard option for a factor family (plan default -> scope default -> component default, SPEC §3.4) linked through
registry/benefit_factors.json 'family_map'. Both schedules are valued on ONE scale, in this order (SPEC §4.3 v0.4,
owner decision 24 Oct 2026):
  1. owner overrides (run input) - always win; the source column shows the value they replace;
  2. the expiring catalogue's own factor table for the family, at the plan's key (network, plan, TPA);
  3. the market library (benefit_factors.json 'entries').
value_factor = relativity(option schedule) / relativity(expiring schedule); > 1 = richer (more cost covered).
Add-on modules (riders): module value = expiring rider premium for the schedule's option / the plan's expiring base
premium (base x rating factors), both summed over the B2 standard mix (latest UWY, lives in force), expiring prices
throughout. richness = product of value_factors + sum of module values (expiring: 1 + its module values);
ratio = richness_option / richness_expiring. Without a mix (no exposure), module lines are left out when unchanged
and MANUAL_REVIEW when changed.
Lines without a relativity / module value are MANUAL_REVIEW and make the plan ratio null - never assumed 1.
Non-factor lines (benefit schedule) are compared by their comparison_rule (direction only, no value_factor).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import REPO_DIR, SpecError
from .evaluator import lookup_component
from .model import Catalogue, RatingScope
from .registry import ANY, load_registry

LIB_PATH = REPO_DIR / "registry" / "benefit_factors.json"


def load_library(path: Path | None = None) -> dict:
    return json.loads(Path(path or LIB_PATH).read_text(encoding="utf-8"))


def _default_option(scope: RatingScope, plan_id: str, family: str):
    p = scope.plan(plan_id)
    if family in p.defaults:
        return p.defaults[family]
    if family in scope.defaults:
        return scope.defaults[family]
    for c in scope.components:
        if c.family == family and c.default_option is not None:
            return c.default_option
    return None


def _match_scope(cat: Catalogue, s: RatingScope):
    for e in cat.scopes:
        if e.product_type == s.product_type and e.rating_region == s.rating_region and \
                (set(s.tpa_set) & set(e.tpa_set) or ANY in e.tpa_set):
            return e
    return None


def _relativity(cat: Catalogue, scope: RatingScope, family: str, option, plan_id: str, tpa: str, lib: dict,
                overrides: dict, reg):
    """(relativity, source) or (None, reason)."""
    if option is None:
        return None, "no option declared"
    base_val, base_src = _relativity_source(cat, scope, family, option, plan_id, tpa, lib, reg)
    if (family, str(option)) in overrides:
        was = "no source value" if base_val is None else f"{base_src}={base_val:.6g}"
        return float(overrides[(family, str(option))]), f"override (replaces {was})"
    if base_val is None:
        return None, "no relativity (override, catalogue table, library)"
    return base_val, base_src


def _relativity_source(cat, scope, family, option, plan_id, tpa, lib, reg):
    comp = next((c for c in scope.components if c.type == "FACTOR_TABLE" and c.family == family and family in c.keys), None)
    if comp is not None:
        plan = scope.plan(plan_id)
        probe = {family: option, "plan": plan_id, "tpa": tpa, "network": plan.network_by_tpa.get(tpa)}
        probe = {k: v for k, v in probe.items() if k in comp.keys and v is not None}
        res = lookup_component(cat, scope.scope_id, comp, [probe], reg)
        if len(res) and res.iloc[0]["__status"] == "VALUE" and comp.rows[int(res.iloc[0]["__row"])]["key"].get(family) == option:
            return float(res.iloc[0]["__value"]), f"catalogue:{comp.component_id}"
    for e in lib.get("entries", []):
        if e.get("family") == family and str(e.get("option")) == str(option):
            sc = e.get("scope") or {}
            if all(v == ANY or {"product_type": scope.product_type, "rating_region": scope.rating_region,
                                "tpa": tpa, "plan": plan_id}.get(k) == v for k, v in sc.items()):
                return float(e["relativity"]), f"library:{e.get('source', '')}"
    return None, None


def module_values(expiring: Catalogue, mix: pd.DataFrame, wanted: set, eval_options: dict | None = None) -> dict:
    """Module (rider) value as a share of base, on the expiring catalogue's prices over the standard mix.
    wanted: {(family, option)}. Returns {(scope_id, plan, family, option): value | None}. Base = sum w x price_base of
    the plan's cells priced without the rider; rider premium = price_riders with the option minus price_riders with NONE
    over the same cells (output currency, like price_base). A plan where any such cell fails to price WITH the option gets None (MANUAL_REVIEW).""" 
    from .evaluator import NONE_OPTION, evaluate
    opts = {"fill": "default", **(eval_options or {})}
    if mix is None or not len(mix):
        return {}
    e, _ = evaluate(expiring, mix, opts)
    keyed = mix[["cell_id", "plan", "w"]].merge(e[["cell_id", "scope_id", "price_base"]], on="cell_id")
    keyed = keyed[keyed["scope_id"].notna()]
    out, none_cache = {}, {}
    for fam, opt in sorted(wanted, key=lambda t: (t[0], str(t[1]))):
        if fam not in none_cache:
            none_cache[fam], _ = evaluate(expiring, mix.assign(**{fam: NONE_OPTION}), opts)
        e0 = none_cache[fam]
        e1, _ = evaluate(expiring, mix.assign(**{fam: opt}), opts)
        # rider premium in the output currency (price_riders: additive and multiplicative riders, any formula order)
        d = keyed.merge(e1[["cell_id", "status", "price_riders"]].rename(columns={"price_riders": "modules_add"}),
                        on="cell_id").merge(
            e0[["cell_id", "status", "price_riders"]].rename(columns={"status": "status0", "price_riders": "add0"}),
            on="cell_id")
        # valid cells: priced without the rider and with a base price; if any of them fails to price WITH the rider
        # option, the option is not priced for the plan -> None. Numerator and denominator use the same cells.
        d["_valid"] = (d["status0"] == "PRICED") & d["price_base"].notna()
        d["_bad"] = d["_valid"] & (d["status"] != "PRICED")
        d["_wm"] = d["w"] * (d["modules_add"] - d["add0"])
        d["_wb"] = d["w"] * d["price_base"]
        for (sid, plan), g in d.groupby(["scope_id", "plan"], sort=True):
            v = g[g["_valid"]]
            b = float(v["_wb"].sum())
            out[(sid, plan, fam, opt)] = (float(v["_wm"].sum() / b) if not g["_bad"].any() and len(v) and b > 0
                                          else None)
    return out


def _direction(rule: str, a, b) -> str:
    if a == b:
        return "SAME"
    if a is None or b is None:
        return "UNKNOWN"
    try:
        if rule == "higher-is-richer":
            return "RICHER" if float(b) > float(a) else "LEANER"
        if rule == "lower-is-richer":
            return "RICHER" if float(b) < float(a) else "LEANER"
        if rule == "false-is-richer":
            return "RICHER" if (not b) and a else "LEANER"
        if rule == "presence":
            return "RICHER" if b and not a else "LEANER"
    except (TypeError, ValueError):
        return "UNKNOWN"
    return "UNKNOWN"


def benefit_diff(expiring: Catalogue, option: Catalogue, option_id: str, overrides: dict | None = None,
                 library: dict | None = None, mix: pd.DataFrame | None = None, eval_options: dict | None = None):
    """Returns (BenefitDiff, BenefitFactors) DataFrames for one option. mix: aggregated standard-mix cells
    (cell_id, pricing key, w) for module values; None leaves modules out of richness (see module docstring)."""
    reg = load_registry()
    lib = library or load_library()
    fmap = lib.get("family_map", {})
    ov = {(k[0], str(k[1])): v for k, v in (overrides or {}).items()}
    diff, fac = [], []
    mvals = {}
    if mix is not None and len(mix):
        wanted = set()
        for s in option.scopes:
            es = _match_scope(expiring, s)
            if es is None:
                continue
            for fam in {c.family for c in es.components if c.type == "MODULE" and c.family}:
                for p in s.plans:
                    try:
                        es.plan(p.plan_id)
                    except SpecError:
                        continue
                    for o in (_default_option(es, p.plan_id, fam), _default_option(s, p.plan_id, fam)):
                        if o is not None:
                            wanted.add((fam, o))
        mvals = module_values(expiring, mix, wanted, eval_options)
    for s in option.scopes:
        es = _match_scope(expiring, s)
        if es is None:
            continue
        tpa = s.tpa_set[0]
        mod_fams = sorted({c.family for c in es.components if c.type == "MODULE" and c.family})
        for p in s.plans:
            try:
                es.plan(p.plan_id)
            except SpecError:
                fac.append({"option_id": option_id, "plan": p.plan_id, "scope_id": s.scope_id, "richness_expiring": np.nan,
                            "richness_option": np.nan, "ratio": np.nan, "status": "NO_EXPIRING_PLAN"})
                continue
            prod, ok = 1.0, True
            for code, fam in sorted(fmap.items()):
                eo = _default_option(es, p.plan_id, fam)
                oo = _default_option(s, p.plan_id, fam)
                if eo is None and oo is None:
                    continue
                re_, src_e = _relativity(expiring, es, fam, eo, p.plan_id, tpa, lib, ov, reg)
                ro, src_o = _relativity(expiring, es, fam, oo, p.plan_id, tpa, lib, ov, reg)
                if re_ is None or ro is None:
                    vf, status, ok = np.nan, "MANUAL_REVIEW", False
                    src = src_e if re_ is None else src_o
                else:
                    vf = ro / re_
                    status, src = "VALUED", src_o
                    prod *= vf
                d = "SAME" if eo == oo else ("UNKNOWN" if vf != vf else ("RICHER" if vf > 1 else "LEANER" if vf < 1 else "SAME"))
                diff.append({"option_id": option_id, "plan": p.plan_id, "benefit_code": code, "expiring_value": eo,
                             "option_value": oo, "direction": d, "value_factor": vf, "scope_id": s.scope_id,
                             "family": fam, "status": status, "source": src})
            m_exp = m_opt = 0.0
            for fam in mod_fams:
                eo, oo = _default_option(es, p.plan_id, fam), _default_option(s, p.plan_id, fam)
                if not mvals:
                    if eo != oo:
                        diff.append({"option_id": option_id, "plan": p.plan_id, "benefit_code": fam, "expiring_value": eo,
                                     "option_value": oo, "direction": "UNKNOWN", "value_factor": np.nan,
                                     "scope_id": s.scope_id, "family": fam, "status": "MANUAL_REVIEW",
                                     "source": "module (no exposure mix to value it)", "module_value_expiring": np.nan,
                                     "module_value_option": np.nan})
                        ok = False
                    continue
                if eo is None and oo is None:
                    continue
                me = 0.0 if eo is None else mvals.get((es.scope_id, p.plan_id, fam, eo))
                mo = 0.0 if oo is None else mvals.get((es.scope_id, p.plan_id, fam, oo))
                if me is None or mo is None:
                    st_m, ok, d = "MANUAL_REVIEW", False, "UNKNOWN"
                    src = "module: option not priced by the expiring catalogue on the plan's mix cells"
                else:
                    m_exp += me
                    m_opt += mo
                    st_m, d = "VALUED", ("SAME" if eo == oo else "RICHER" if mo > me else "LEANER" if mo < me else "SAME")
                    src = "module value % of expiring base (standard mix)"
                diff.append({"option_id": option_id, "plan": p.plan_id, "benefit_code": fam, "expiring_value": eo,
                             "option_value": oo, "direction": d, "value_factor": np.nan, "scope_id": s.scope_id,
                             "family": fam, "status": st_m, "source": src,
                             "module_value_expiring": np.nan if me is None else me,
                             "module_value_option": np.nan if mo is None else mo})
            eb = {b.benefit_code: b for b in es.benefits if b.plan_id == p.plan_id}
            ob = {b.benefit_code: b for b in s.benefits if b.plan_id == p.plan_id}
            for code in sorted(set(eb) | set(ob)):
                if code in fmap:
                    continue
                a, b = eb.get(code), ob.get(code)
                av, bv = (a.value if a else None), (b.value if b else None)
                rule = reg.benefits.get(code, {}).get("comparison_rule", "")
                if rule == "categorical-ladder":
                    lad = reg.benefits[code].get("ladder", [])
                    d = ("SAME" if av == bv else "UNKNOWN" if av not in lad or bv not in lad else
                         "RICHER" if lad.index(bv) > lad.index(av) else "LEANER")
                else:
                    d = _direction(rule, av, bv)
                st = "MANUAL_REVIEW" if (a and a.status == "MANUAL_REVIEW") or (b and b.status == "MANUAL_REVIEW") else "COMPARED"
                diff.append({"option_id": option_id, "plan": p.plan_id, "benefit_code": code,
                             "expiring_value": None if av is None else str(av), "option_value": None if bv is None else str(bv),
                             "direction": d, "value_factor": np.nan, "scope_id": s.scope_id, "family": None,
                             "status": st, "source": "benefit schedule"})
            r_e, r_o = 1.0 + m_exp, prod + m_opt
            fac.append({"option_id": option_id, "plan": p.plan_id, "scope_id": s.scope_id, "richness_expiring": r_e,
                        "richness_option": r_o if ok else np.nan, "ratio": r_o / r_e if ok else np.nan,
                        "status": "VALUED" if ok else "MANUAL_REVIEW"})
    dcols = ["option_id", "plan", "benefit_code", "expiring_value", "option_value", "direction", "value_factor",
             "scope_id", "family", "status", "source", "module_value_expiring", "module_value_option"]
    fcols = ["option_id", "plan", "richness_expiring", "richness_option", "ratio", "scope_id", "status"]
    bd = pd.DataFrame(diff, columns=dcols)
    for c in ("expiring_value", "option_value"):
        bd[c] = bd[c].map(lambda v: None if v is None else str(v)).astype(object)
    bf = pd.DataFrame(fac, columns=fcols)
    return (bd.sort_values(["option_id", "scope_id", "plan", "benefit_code"], kind="stable").reset_index(drop=True),
            bf.sort_values(["option_id", "scope_id", "plan"], kind="stable").reset_index(drop=True))


BENEFIT_DIFF_EXTRAS = ("scope_id", "family", "status", "source", "module_value_expiring", "module_value_option")
BENEFIT_FACTORS_EXTRAS = ("scope_id", "status")


def plan_ratio(bf: pd.DataFrame) -> pd.DataFrame:
    """[option_id, plan, ratio] for the benefit-adjusted index. A plan priced in several scopes (e.g. one per TPA) with
    different ratios cannot be collapsed to one value: ratio is set null there (MANUAL_REVIEW)."""
    g = bf.groupby(["option_id", "plan"], sort=True)["ratio"].agg(
        lambda s: s.iloc[0] if s.notna().all() and np.allclose(s, s.iloc[0]) else np.nan).reset_index()
    return g
