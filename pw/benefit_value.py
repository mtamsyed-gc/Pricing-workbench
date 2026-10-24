"""B1 benefit value, level 1 (SPEC §4.3): is each option richer or leaner than expiring, by benefit line and in total?

Per plan (matched by scope product x region x TPA and plan_id), each factor-valued benefit line is the plan's
standard option for a factor family (plan default -> scope default -> component default, SPEC §3.4) linked through
registry/benefit_factors.json 'family_map'. Both schedules are valued on ONE scale, in this order (SPEC §4.3):
  1. the expiring catalogue's own factor table for the family, at the plan's key (network, plan, TPA);
  2. the market library (benefit_factors.json 'entries');
  3. owner overrides (run input) - used only where 1 and 2 have no value.
value_factor = relativity(option schedule) / relativity(expiring schedule); > 1 = richer (more cost covered).
richness = product of value_factors (expiring = 1.0, the reference schedule); ratio = richness_option / richness_expiring.
Lines without a relativity are MANUAL_REVIEW (value_factor null) and make the plan ratio null - never assumed 1.
Non-factor lines (benefit schedule) are compared by their comparison_rule (direction only, no value_factor).
Add-on modules are not in level-1 richness (SPEC §4.3 'plus module values as % of base' needs a base definition -
open item in HANDOVER); module option changes are listed as MANUAL_REVIEW.
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
    if (family, str(option)) in overrides:
        return float(overrides[(family, str(option))]), "override"
    return None, "no relativity (catalogue table, library, override)"


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
                 library: dict | None = None):
    """Returns (BenefitDiff, BenefitFactors) DataFrames for one option."""
    reg = load_registry()
    lib = library or load_library()
    fmap = lib.get("family_map", {})
    ov = {(k[0], str(k[1])): v for k, v in (overrides or {}).items()}
    diff, fac = [], []
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
            for fam in mod_fams:
                eo, oo = _default_option(es, p.plan_id, fam), _default_option(s, p.plan_id, fam)
                if eo != oo:
                    diff.append({"option_id": option_id, "plan": p.plan_id, "benefit_code": fam, "expiring_value": eo,
                                 "option_value": oo, "direction": "UNKNOWN", "value_factor": np.nan, "scope_id": s.scope_id,
                                 "family": fam, "status": "MANUAL_REVIEW", "source": "module (not in level-1 richness)"})
                    ok = False
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
            fac.append({"option_id": option_id, "plan": p.plan_id, "scope_id": s.scope_id, "richness_expiring": 1.0,
                        "richness_option": prod if ok else np.nan, "ratio": prod if ok else np.nan,
                        "status": "VALUED" if ok else "MANUAL_REVIEW"})
    dcols = ["option_id", "plan", "benefit_code", "expiring_value", "option_value", "direction", "value_factor",
             "scope_id", "family", "status", "source"]
    fcols = ["option_id", "plan", "richness_expiring", "richness_option", "ratio", "scope_id", "status"]
    bd = pd.DataFrame(diff, columns=dcols)
    for c in ("expiring_value", "option_value"):
        bd[c] = bd[c].map(lambda v: None if v is None else str(v)).astype(object)
    bf = pd.DataFrame(fac, columns=fcols)
    return (bd.sort_values(["option_id", "scope_id", "plan", "benefit_code"], kind="stable").reset_index(drop=True),
            bf.sort_values(["option_id", "scope_id", "plan"], kind="stable").reset_index(drop=True))


BENEFIT_DIFF_EXTRAS = ("scope_id", "family", "status", "source")
BENEFIT_FACTORS_EXTRAS = ("scope_id", "status")


def plan_ratio(bf: pd.DataFrame) -> pd.DataFrame:
    """[option_id, plan, ratio] for the benefit-adjusted index. A plan priced in several scopes (e.g. one per TPA) with
    different ratios cannot be collapsed to one value: ratio is set null there (MANUAL_REVIEW)."""
    g = bf.groupby(["option_id", "plan"], sort=True)["ratio"].agg(
        lambda s: s.iloc[0] if s.notna().all() and np.allclose(s, s.iloc[0]) else np.nan).reset_index()
    return g
