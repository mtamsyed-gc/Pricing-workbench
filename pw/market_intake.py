"""Market plan intake (WS2): SME Benchmarking Tool intake files (SME-INTAKE v2.4) -> MARKET catalogues.

One adapter per intake TEMPLATE (layout + taxonomy map in specs/market/<layout>.json), never per market source: the
adapter reads the plan's identity, offered networks, age bands, default design, own lever factors, add-on prices and
package, and writes a catalogue spec; the standard spec parser then reads the base rates from the workbook (so V1
source reproduction applies to market files too).

Mapping (owner decisions 24 Oct 2026, WS2):
  plans          one plan per offered network (plan_id = network code, tier_rank from the layout)
  base rates     network x age band x Principal/Dependent x gender; monthly rates x 12 (value_scale)
  premium basis  as filed; a Gross plan carries its own gross-to-net factor (meta) used to put it on the run basis
  levers         a lever with a registry dimension becomes a FACTOR_TABLE (keys family x network; 'All' -> ANY; default
                 option per network = factor 1.0, the reference); plan defaults = the default design (B4)
  levers without a dimension (room type, PEC limit, medication type, territory - CR #13) are benefit lines only
  add-ons        package level (E_TOB) priced from D_Optional at the exact level -> MODULE (flat: ADD per unit; multiplier:
                 MULTIPLY 1 + x); included-in-base -> no module; level not priced / no module dimension / 'Adults (18+)'
                 -> not in the price, reported (MANUAL_REVIEW) in the reconciliation report
  benefit lines  lever defaults, add-on limits, plan terms and other benefits mapped to registry/benefits.json codes
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter

from . import REPO_DIR, SpecError
from .model import Catalogue
from .spec_parser import parse_catalogue

LAYOUT_DIR = REPO_DIR / "specs" / "market"
DEFAULT_LAYOUT = "sme_intake_v2_4.json"


def load_layout(name: str | None = None) -> dict:
    p = Path(name) if name and Path(name).exists() else LAYOUT_DIR / (name or DEFAULT_LAYOUT)
    return json.loads(p.read_text(encoding="utf-8"))


def _s(v):
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.date().isoformat() if isinstance(v, _dt.datetime) else v.isoformat()
    s = str(v).strip()
    return s if s != "" else None


def _opt(v):
    """Lever / add-on option as a canonical string (numbers without decimals: 1000000 -> '1000000')."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        f = float(v)
        return str(int(f)) if f.is_integer() else repr(f)
    return _s(v)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _Report:
    def __init__(self, plan_id):
        self.plan_id = plan_id
        self.rows = []

    def add(self, area, item, status, detail=""):
        self.rows.append({"plan_id": self.plan_id, "area": area, "item": item, "status": status, "detail": detail})


def spec_from_sme_intake(path: Path, layout: dict | None = None, catalogue_id: str | None = None) -> tuple[dict, list]:
    """Return (catalogue spec dict, reconciliation report rows) for one intake file."""
    L = layout or load_layout()
    path = Path(path)
    wb = load_workbook(path, data_only=True, read_only=False)
    A = wb[L["plan"]["sheet"]]
    pc = {k: A[v].value for k, v in L["plan"]["cells"].items()}
    pid = _s(pc["plan_id"])
    if not pid:
        raise SpecError(f"{path.name}: plan id ({L['plan']['sheet']}!{L['plan']['cells']['plan_id']}) is blank")
    rep = _Report(pid)
    em = _s(pc["emirate"])
    if em not in L["emirates"]:
        raise SpecError(f"{path.name}: emirate {em!r} not in the layout's emirate map")
    reg = L["emirates"][em]
    period = _s(pc["rate_period"]) or "Annual"
    if period not in ("Annual", "Monthly"):
        raise SpecError(f"{path.name}: rate period {period!r}")
    scale = 12.0 if period == "Monthly" else 1.0
    basis = (_s(pc["premium_basis"]) or "Net").upper()
    if basis not in ("NET", "GROSS"):
        raise SpecError(f"{path.name}: premium basis {basis!r}")
    g2n = _num(pc["gross_to_net"]) if basis == "GROSS" else None
    if basis == "GROSS" and not g2n:
        rep.add("basis", "gross_to_net", "MISSING", "Gross plan without a gross-to-net factor: cannot be put on a net basis")
    ccy = _s(pc["currency"]) or "AED"

    R = wb[L["rates"]["sheet"]]
    rl = L["rates"]
    nets = rl["networks"]
    oc = column_index_from_string(rl["offered_col"])
    offered = [n for j, n in enumerate(nets) if _s(R.cell(rl["offered_row0"] + j, oc).value) == "Yes"]
    if not offered:
        raise SpecError(f"{path.name}: no network offered")
    lo_c, hi_c = column_index_from_string(rl["band_lower_col"]), column_index_from_string(rl["band_upper_col"])
    bands = []
    for i in range(rl["max_bands"]):
        lo, hi = R.cell(rl["band_row0"] + i, lo_c).value, R.cell(rl["band_row0"] + i, hi_c).value
        if lo is None and hi is None:
            continue
        if _num(lo) is None or _num(hi) is None:
            raise SpecError(f"{path.name}: age band row {rl['band_row0'] + i} is not numeric")
        bands.append((i, int(lo), min(int(hi), 120)))
    if not bands:
        raise SpecError(f"{path.name}: no age bands")
    if [b[0] for b in bands] != list(range(len(bands))):
        raise SpecError(f"{path.name}: age bands must be contiguous rows from the first band row")
    design = {}
    for k, lev in enumerate(rl["levers"]):
        for j, n in enumerate(nets):
            if n in offered:
                design[(lev, n)] = _opt(R.cell(rl["design_row0"] + k, rl["design_first_col"] + j).value)

    # ---- plans and base table
    plans = []
    for n in offered:
        dflt = {}
        for lev in rl["levers"]:
            m = L["lever_map"].get(lev) or {}
            if m.get("family") and design.get((lev, n)) is not None:
                dflt[m["family"]] = design[(lev, n)]
        plans.append({"plan_id": n, "label": f"{pid} {n}", "tier_rank": L["network_tier_rank"][n],
                      "network_by_tpa": {t: n for t in L["tpa_set"]}, "defaults": dflt})
    sources = []
    for j, n in enumerate(nets):
        if n not in offered:
            continue
        c0 = rl["first_rate_col"] + j * rl["cols_per_network"]
        sources.append({"sheet": rl["sheet"], "anchor": f"{get_column_letter(c0)}{rl['header_row']}",
                        "row_keys": [{"age": [lo, hi]} for _, lo, hi in bands],
                        "col_dims": [{"dims": ["member_category", "gender"], "labels": rl["columns"]}],
                        "n_cols": rl["cols_per_network"], "fixed": {"plan": n}, "value_scale": scale})
    components = [{"component_id": "base", "type": "BASE_TABLE", "sources": sources}]

    # ---- own lever factors
    F = wb[L["factors"]["sheet"]]
    fc = {k: column_index_from_string(v) for k, v in L["factors"]["cols"].items()}
    by_lever = {}
    for i in range(L["factors"]["max_rows"]):
        r = L["factors"]["row0"] + i
        lev, opt, net, fac = (F.cell(r, fc["lever"]).value, F.cell(r, fc["option"]).value, F.cell(r, fc["network"]).value,
                              F.cell(r, fc["factor"]).value)
        if lev is None and opt is None and net is None and fac is None:
            continue
        lev, opt, net = _s(lev), _opt(opt), _s(net)
        if _num(fac) is None or not lev or opt is None or not net:
            rep.add("factors", f"{F.title}!row {r}", "SKIPPED", "incomplete factor row")
            continue
        if net != "All" and net not in offered:
            continue
        by_lever.setdefault(lev, []).append((opt, net, float(fac), f"{F.title}!{get_column_letter(fc['factor'])}{r}"))
    for lev, rows_ in sorted(by_lever.items()):
        m = L["lever_map"].get(lev)
        if not m or not m.get("family"):
            rep.add("factors", lev, "NOT_PRICED", f"no registry dimension ({(m or {}).get('pending_dim') or 'unmapped'}); "
                                                  "factors kept out of the price")
            continue
        fam = m["family"]
        rows, seen = [], set()
        for opt, net, fac, ref in rows_:
            k = (opt, "ANY" if net == "All" else net)
            if k in seen:
                raise SpecError(f"{path.name}: duplicate factor row {lev} / {opt} / {net}")
            seen.add(k)
            rows.append({"key": {fam: opt, "network": k[1]}, "value": fac, "source_ref": ref})
        ref_by_net = {n: design[(lev, n)] for n in offered if design.get((lev, n)) is not None}
        for n, d in ref_by_net.items():                       # default option = factor 1.0 by definition (template rule)
            if (d, n) not in seen and (d, "ANY") not in seen:
                rows.append({"key": {fam: d, "network": n}, "value": 1.0, "source_ref": "default design (factor 1 by definition)"})
                seen.add((d, n))
        components.append({"component_id": f"f_{fam}", "type": "FACTOR_TABLE", "family": fam, "keys": [fam, "network"],
                           "reference_level_by": "network", "reference_level_by_key": ref_by_net, "rows": rows})

    # ---- add-ons: package level priced as modules
    P = wb[L["package"]["sheet"]]
    pk = {k: column_index_from_string(v) for k, v in L["package"]["cols"].items()}
    O = wb[L["optional"]["sheet"]]
    ocol = {k: column_index_from_string(v) for k, v in L["optional"]["cols"].items()}
    opt_rows = []
    for i in range(L["optional"]["max_rows"]):
        r = L["optional"]["row0"] + i
        vals = {k: O.cell(r, c).value for k, c in ocol.items()}
        if all(v is None for v in vals.values()):
            continue
        opt_rows.append((r, vals))
    benefits = {n: [] for n in offered}
    for k, ben in enumerate(L["package"]["benefits"]):
        r = L["package"]["row0"] + k
        lim, cop, inb = _opt(P.cell(r, pk["limit"]).value), _s(P.cell(r, pk["copay"]).value), _s(P.cell(r, pk["in_base"]).value)
        am = L["addon_map"].get(ben) or {}
        covered = lim is not None and lim != L["not_covered"]
        if am.get("benefit_code"):
            for n in offered:
                benefits[n].append({"benefit_code": am["benefit_code"], "value": _num(lim) if covered else 0,
                                    "condition_text": f"{ben}: {lim} / {cop}" + (" (in base)" if inb == "Yes" else ""),
                                    "source_ref": f"{P.title}!B{r}"})
        if not covered or inb == "Yes":
            continue
        level = f"{lim}|{cop}"
        if not am.get("module"):
            rep.add("addons", ben, "NOT_PRICED", f"package level {level} has no module dimension "
                                                 f"({am.get('pending_dim') or 'unmapped'}); kept out of the price")
            continue
        priced, bridged, why = _resolve_level(opt_rows, ben, lim, cop, offered)
        if not priced:
            rep.add("addons", ben, "NOT_PRICED", f"package level {level} not priced on {O.title} ({why}); "
                                                 "kept out of the price")
            continue
        forms = {(_s(v["form"]), _s(v["applies"])) for _, v in priced}
        if len(forms) > 1:
            rep.add("addons", ben, "NOT_PRICED", f"mixed pricing forms {sorted(forms)}; kept out of the price")
            continue
        form, applies = forms.pop()
        ap = L["applies_map"].get(applies)
        if ap is None:
            rep.add("addons", ben, "NOT_PRICED", f"applies-to {applies!r} has no eligibility rule; kept out of the price")
            continue
        fam = am["module"]
        rows = []
        for rr, v in priced:
            net = _s(v["network"])
            if net != "All" and net not in offered:
                continue
            val = float(v["value"]) * (scale if form == "Flat per member" else 1.0)
            rows.append({"key": {fam: level, "network": "ANY" if net == "All" else net},
                         "value": (1.0 + float(v["value"])) if form == "Multiplier on base" else val,
                         "source_ref": (f"{O.title}!G{rr[0]}:G{rr[1]} bridged (linear on limit)" if isinstance(rr, tuple)
                                        else f"{O.title}!G{rr}")})
        components.append({"component_id": f"m_{fam}", "type": "MODULE", "family": fam, "keys": [fam, "network"],
                           "unit": ap["unit"], "eligibility": ap["eligibility"],
                           "mode": "MULTIPLY" if form == "Multiplier on base" else "ADD", "rows": rows})
        for p in plans:
            p["defaults"][fam] = level
        rep.add("addons", ben, "BRIDGED" if bridged else "PRICED",
                f"{level}: {form}, {applies}" + (" - interpolated between the file's own priced limits" if bridged else ""))

    # ---- benefit lines: lever defaults, terms, other benefits
    for n in offered:
        for lev in rl["levers"]:
            m = L["lever_map"].get(lev) or {}
            v = design.get((lev, n))
            if not m.get("benefit_code"):
                continue
            vm = m.get("value_map")
            val = vm.get(v, v) if vm else (_num(v) if _num(v) is not None and m["benefit_code"] in ("aml", "pec_cover") else v)
            benefits[n].append({"benefit_code": m["benefit_code"], "value": val, "condition_text": f"{lev}: {v}",
                                "source_ref": f"{rl['sheet']}!design {lev} {n}"})
        tc = column_index_from_string(L["plan"]["terms_col"])
        for i, t in enumerate(L["plan"]["terms"]):
            code = L["terms_map"].get(t)
            if code:
                benefits[n].append({"benefit_code": code, "value": _num(A.cell(L["plan"]["terms_row0"] + i, tc).value),
                                    "condition_text": t, "source_ref": f"{A.title}!C{L['plan']['terms_row0'] + i}"})
        oc2 = column_index_from_string(L["plan"]["other_col"])
        for i, (ob, code) in enumerate(L["other_map"].items()):
            if code:
                yes = _s(A.cell(L["plan"]["other_row0"] + i, oc2).value) == "Yes"
                benefits[n].append({"benefit_code": code, "value": yes, "condition_text": ob,
                                    "source_ref": f"{A.title}!C{L['plan']['other_row0'] + i}"})
    for lev, m in L["lever_map"].items():
        if not m.get("family"):
            rep.add("levers", lev, "BENEFIT_LINE_ONLY" if m.get("benefit_code") else "UNMAPPED",
                    f"pending dimension {m.get('pending_dim')}" if m.get("pending_dim") else "no registry home")
    for t, code in L["terms_map"].items():
        if not code:
            rep.add("terms", t, "UNMAPPED", "no benefit code")
    for ob, code in L["other_map"].items():
        if not code:
            rep.add("other_benefits", ob, "UNMAPPED", "no benefit code")

    cid = catalogue_id or f"MKT_{pid}"
    spec = {"spec_id": f"{L['layout_id']}::{pid}", "spec_version": "1",
            "catalogue": {"catalogue_id": cid, "owner": _s(pc["insurer"]) or "UNKNOWN", "kind": "MARKET", "version": "1",
                          "effective_date": _s(pc["effective_date"]), "currency": ccy, "premium_basis": basis},
            "scopes": [{"scope_id": f"{cid}|SME", "product_type": L["product_type"], "regulator": reg["regulator"],
                        "rating_region": reg["rating_region"], "tpa_set": list(L["tpa_set"]), "plans": plans,
                        "components": components, "formula": {"rounding": 2}, "benefits": benefits,
                        "notes": f"{_s(pc['name'])}; status {_s(pc['status'])}; include {_s(pc['include'])}"}],
            "rules": [],
            "_meta": {"plan_id": pid, "name": _s(pc["name"]), "status": _s(pc["status"]), "include": _s(pc["include"]),
                      "emirate": em, "rate_period": period, "gross_to_net": g2n, "max_age": _num(pc["max_age"]),
                      "small_group_size": _num(pc["small_group_size"]), "small_group_loading": _num(pc["small_group_loading"]),
                      "layout": L["layout_id"], "source_file": path.name}}
    sg = _num(pc["small_group_loading"])
    if sg:
        spec["rules"].append({"rule_id": f"{pid}_SG", "scope": {}, "type": "LOADING_CAP",
                              "parameters": {"small_group_size_max": _num(pc["small_group_size"]), "loading": sg},
                              "text": "small-group loading (not in the base price)"})
    wb.close()
    return spec, rep.rows


def _same_limit(a, b) -> bool:
    na, nb = _num(a), _num(b)
    return (na is not None and nb is not None and na == nb) or (a is not None and a == b)


def _resolve_level(opt_rows, ben, lim, cop, offered):
    """Rows pricing a package add-on level, per network (owner decision 24 Oct 2026, HANDOVER item 20).
    For 'All' and each OFFERED network that has rows: an exact row at the level wins (limit compared as a number when
    numeric); otherwise the level is interpolated linearly on the limit between that network's own two nearest priced
    limits of one pricing form / applies-to (BRIDGED). No extrapolation; ambiguous rows (two exact rows, or the same
    limit at different values, or brackets in two forms) fail that network. Every offered network must be resolved
    by its own row or by 'All', otherwise the add-on is not priced. Returns ([(ref, vals)], bridged, reason);
    ref is the row number, or (row_lo, row_hi) when bridged."""
    target = _num(lim)
    by_net = {}
    for rr, v in opt_rows:
        if _s(v["benefit"]) != ben or _s(v["copay"]) != cop:
            continue
        net = _s(v["network"])
        if net == "All" or net in offered:
            by_net.setdefault(net, []).append((rr, v))
    if not by_net:
        return [], False, "no priced rows for this benefit and co-pay"
    out, bridged, why = [], False, {}
    for net, rows in sorted(by_net.items()):
        exact = [(rr, v) for rr, v in rows if _same_limit(_opt(v["limit"]), lim)]
        if len(exact) == 1:
            out.append(exact[0])
            continue
        if len(exact) > 1:
            why[net] = "several rows at this exact level"
            continue
        if target is None:
            why[net] = f"limit {lim!r} is not numeric"
            continue
        groups = {}
        for rr, v in rows:
            x, y = _num(_opt(v["limit"])), _num(v["value"])
            if x is not None and y is not None:
                groups.setdefault((_s(v["form"]), _s(v["applies"])), []).append((x, y, rr, v))
        hits = []
        for g, pts in sorted(groups.items(), key=lambda t: str(t[0])):
            xs = {}
            for x, y, rr, v in pts:
                xs.setdefault(x, set()).add(y)
            if any(len(ys) > 1 for ys in xs.values()):
                continue                                   # same limit at two values: ambiguous form group
            pts = sorted({x: (x, y, rr, v) for x, y, rr, v in pts}.values(), key=lambda t: t[0])
            lo = [p_ for p_ in pts if p_[0] < target]
            hi = [p_ for p_ in pts if p_[0] > target]
            if lo and hi:
                hits.append((lo[-1], hi[0]))
        if len(hits) != 1:
            why[net] = ("limit outside the file's priced range" if not hits else "brackets in several pricing forms")
            continue
        a, b = hits[0]
        val = a[1] + (b[1] - a[1]) * (target - a[0]) / (b[0] - a[0])
        out.append(((a[2], b[2]), {**a[3], "limit": lim, "value": val}))
        bridged = True
    got = {_s(v["network"]) for _, v in out}
    missing = [n for n in offered if n not in got and "All" not in got]
    if missing or not out:
        detail = "; ".join(f"{n}: {r}" for n, r in sorted(why.items())) or "no row for these networks"
        return [], False, f"not resolved for {missing or 'any network'} ({detail})"
    return out, bridged, ""


def load_sme_intake(path: Path, layout: dict | None = None, catalogue_id: str | None = None) -> tuple[Catalogue, list]:
    spec, report = spec_from_sme_intake(path, layout, catalogue_id)
    meta = spec.pop("_meta")
    cat = parse_catalogue(spec=spec, source_file=Path(path))
    cat.meta.update({"market": meta})
    return cat, report


def load_market_folder(folder: Path, layout: dict | None = None) -> tuple[list, list]:
    """All *.xlsx intake files in a folder (sorted). Returns (catalogues, reconciliation report rows)."""
    cats, rep = [], []
    ids = set()
    for p in sorted(Path(folder).glob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        c, r = load_sme_intake(p, layout)
        if c.catalogue_id in ids:
            raise SpecError(f"duplicate market plan id {c.catalogue_id} ({p.name})")
        ids.add(c.catalogue_id)
        cats.append(c)
        rep.extend(r)
    return cats, rep
