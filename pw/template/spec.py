"""template_spec.json: schema validator, normaliser and authoring from a catalogue (SPEC §8.0, §8.1).

Top level: template_spec_version, cedant, tender_id, currency, premium_basis, deadline, contact, issue_date,
age_band_sets{name: [{"label", "range": [lo, hi] | null}]}, age_bands_file (optional, relative to the spec file),
column_sets{name: [{"label", "keys": [{dim: value}, ...]}]}, sheets[], reference_sheets{}, options{}.

Sheet: sheet_name, title, product_type, regulator, rating_region, mandatory, copay_basis{family: option},
  rows source: "age_bands": set | "sections": [{"label", "key", "age_bands": set}] | "rows": [{"label", "section", "key"}]
  "column_set": name | [inline columns], "split_options": {"marital": {"column_set": name},
                                                          "member_section": {"sections": [...]}}
  blocks[]: {block_id, tpa, label, plans[{plan_id, label, network}], splits{marital, member_section},
             refer_cells[{partial key}], refer_text, and optional row/column overrides as on the sheet}
One block per product x rating region x TPA: a TPA appears at most once per sheet (SPEC §8.0).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from .. import ProposalRequired, SpecError
from ..registry import ANY, load_registry
from . import TEMPLATE_SPEC_VERSION

REQUIRED_TOP = ["cedant", "tender_id", "currency", "premium_basis", "deadline", "sheets"]
DEFAULT_COLUMN_SETS = {"MF": [{"label": "Male", "keys": [{"gender": "M"}]}, {"label": "Female", "keys": [{"gender": "F"}]}],
                       "RATE": [{"label": "Rate", "keys": [{}]}]}
DEFAULT_OPTIONS = {"allow_proposed_multipliers": False, "allow_benefit_comments": False, "protect_structure": True,
                   "language": "en", "rounding": 2, "outlier_shading": False, "outlier_band": [0.7, 1.3]}
DEFAULT_REFERENCE = {"existing_rates": True, "factor_tables": True, "addons": "READ_ONLY", "tob_summary": False, "terms": True}
TERMS_FIELDS = ["reinsurer", "share_by_book", "premium_basis", "commission", "corridor", "cap", "profit_share",
                "conditions", "validity", "comments"]
DEFAULT_REFER_TEXT = "REFER - lead reinsurer"
_BAD_SHEET = re.compile(r"[\[\]\*\?/\\:]")


def load_template_spec(path: Path) -> dict:
    p = Path(path)
    spec = json.loads(p.read_text(encoding="utf-8"))
    spec["_base_dir"] = str(p.resolve().parent)
    return spec


def _band_sets(spec: dict) -> dict:
    sets = copy.deepcopy(spec.get("age_band_sets") or {})
    f = spec.get("age_bands_file")
    if f:
        base = Path(spec.get("_base_dir") or ".")
        doc = json.loads((base / f).read_text(encoding="utf-8"))
        for name, bands in (doc.get("age_band_sets") or {}).items():
            if name in sets:
                raise SpecError(f"age band set '{name}' defined twice (spec and {f})")
            sets[name] = bands
    return sets


def validate_template_spec(spec: dict) -> list[str]:
    """Return a list of problems (empty = valid). normalise() raises on the same problems."""
    errs = []
    reg = load_registry()
    for k in REQUIRED_TOP:
        if k not in spec:
            errs.append(f"missing top-level field '{k}'")
    if errs:
        return errs
    if spec["premium_basis"] not in ("GROSS", "NET"):
        errs.append("premium_basis must be GROSS or NET")
    try:
        bsets = _band_sets(spec)
    except (SpecError, OSError, ValueError) as e:
        return [str(e)]
    for name, bands in bsets.items():
        labels = [b.get("label") for b in bands]
        if len(set(labels)) != len(labels):
            errs.append(f"age band set '{name}': duplicate labels")
        rngs = sorted([b["range"] for b in bands if b.get("range")])
        for a, b in zip(rngs, rngs[1:]):
            if b[0] <= a[1]:
                errs.append(f"age band set '{name}': ranges {a} and {b} overlap")
    csets = {**DEFAULT_COLUMN_SETS, **(spec.get("column_sets") or {})}
    names = set()
    for si, sh in enumerate(spec["sheets"]):
        where = f"sheets[{si}] '{sh.get('sheet_name')}'"
        n = sh.get("sheet_name")
        if not n or len(n) > 31 or _BAD_SHEET.search(n) or n.startswith("_"):
            errs.append(f"{where}: invalid sheet_name (1-31 chars, no []*?/\\:, not starting with '_')")
        if n in names:
            errs.append(f"{where}: duplicate sheet_name")
        names.add(n)
        for code in ("product_type", "regulator"):
            try:
                reg.check_value(code, sh.get(code), allow_any=False, allow_parent=False)
            except Exception as e:  # noqa: BLE001
                errs.append(f"{where}: {e}")
        if not sh.get("blocks"):
            errs.append(f"{where}: no blocks")
        tp = [(b.get("tpa"), p.get("plan_id")) for b in sh.get("blocks", []) for p in b.get("plans", [])]
        if len(set(tp)) != len(tp):
            errs.append(f"{where}: a TPA x plan appears in more than one block (one table per product x region x TPA; "
                        "a TPA has several blocks only for disjoint plans, SPEC §8.0)")
        for bi, b in enumerate(sh.get("blocks", [])):
            bw = f"{where} block[{bi}] {b.get('block_id')}"
            plans = [p.get("plan_id") for p in b.get("plans", [])]
            if not plans:
                errs.append(f"{bw}: no plans")
            if len(set(plans)) != len(plans):
                errs.append(f"{bw}: duplicate plan_id")
            src = {**sh, **{k: v for k, v in b.items() if k in ("age_bands", "sections", "rows", "column_set")}}
            if not any(k in src for k in ("age_bands", "sections", "rows")):
                errs.append(f"{bw}: no row definition (age_bands / sections / rows)")
            for sec in src.get("sections") or []:
                if sec.get("age_bands") and sec["age_bands"] not in bsets:
                    errs.append(f"{bw}: unknown age band set '{sec['age_bands']}'")
            if isinstance(src.get("age_bands"), str) and src["age_bands"] not in bsets:
                errs.append(f"{bw}: unknown age band set '{src['age_bands']}'")
            cs = src.get("column_set", "MF")
            if isinstance(cs, str) and cs not in csets:
                errs.append(f"{bw}: unknown column set '{cs}'")
            for sp, on in (b.get("splits") or {}).items():
                if sp not in ("marital", "member_section"):
                    errs.append(f"{bw}: unknown split '{sp}'")
                elif on and sp not in (sh.get("split_options") or {}):
                    errs.append(f"{bw}: split '{sp}' switched on but the sheet declares no split_options.{sp}")
    errs += cedant_errors(spec)
    opts = spec.get("options") or {}
    for k, v in opts.items():
        if k not in DEFAULT_OPTIONS:
            errs.append(f"options: unknown option '{k}'")
        elif isinstance(DEFAULT_OPTIONS[k], bool) and not isinstance(v, bool):
            errs.append(f"options.{k} must be true/false")
    return errs


def _rows_for(src: dict, bsets: dict) -> list[dict]:
    def bands(name_or_list):
        if isinstance(name_or_list, list):
            return name_or_list
        return bsets[name_or_list]

    def band_rows(bl, section_label=None, key=None):
        out = []
        for b in bands(bl):
            rk = dict(key or {})
            rk["age"] = list(b["range"]) if b.get("range") else str(b["label"])
            out.append({"section": section_label, "label": str(b["label"]), "key": rk,
                        "placeholder": not b.get("range")})
        return out
    if src.get("rows"):
        out = []
        for r in src["rows"]:
            alts = [dict(k) for k in r["keys"]] if r.get("keys") else [dict(r.get("key") or {})]
            out.append({"section": r.get("section"), "label": str(r["label"]), "key": alts[0], "alt_keys": alts[1:],
                        "placeholder": bool(r.get("placeholder"))})
        return out
    if src.get("sections"):
        out = []
        for sec in src["sections"]:
            if sec.get("age_bands"):
                out += band_rows(sec["age_bands"], sec["label"], sec.get("key"))
            else:
                out.append({"section": sec["label"], "label": sec.get("row_label", ""), "key": dict(sec.get("key") or {}),
                            "placeholder": False})
        return out
    return band_rows(src["age_bands"])


def normalise(spec: dict) -> dict:
    """Validate and expand to explicit rows x columns per block. Output is what the generator lays out."""
    errs = validate_template_spec(spec)
    if errs:
        raise SpecError("template_spec invalid:\n  " + "\n  ".join(errs))
    reg = load_registry()
    bsets = _band_sets(spec)
    csets = {**DEFAULT_COLUMN_SETS, **(spec.get("column_sets") or {})}
    out = {k: v for k, v in spec.items() if k not in ("sheets", "_base_dir")}
    out["template_spec_version"] = spec.get("template_spec_version", TEMPLATE_SPEC_VERSION)
    out["options"] = {**DEFAULT_OPTIONS, **(spec.get("options") or {})}
    out["reference_sheets"] = {**DEFAULT_REFERENCE, **(spec.get("reference_sheets") or {})}
    out["terms_fields"] = list(spec.get("terms_fields") or TERMS_FIELDS)
    out["age_band_sets"] = bsets
    out["sheets"] = []
    for sh in spec["sheets"]:
        nsh = {k: v for k, v in sh.items() if k != "blocks"}
        nsh["blocks"] = []
        for b in sh["blocks"]:
            splits = {"marital": False, "member_section": False, **(b.get("splits") or {})}
            src = {k: sh[k] for k in ("age_bands", "sections", "rows", "column_set") if k in sh}
            src.update({k: b[k] for k in ("age_bands", "sections", "rows", "column_set") if k in b})
            if splits["member_section"]:
                src.pop("rows", None)
                src["sections"] = sh["split_options"]["member_section"]["sections"]
            cs = src.get("column_set", "MF")
            if splits["marital"]:
                cs = sh["split_options"]["marital"]["column_set"]
            cols = csets[cs] if isinstance(cs, str) else cs
            rows = _rows_for(src, bsets)
            bkey = {"product_type": sh["product_type"], "regulator": sh.get("regulator"),
                    "rating_region": sh.get("rating_region"), "tpa": b["tpa"]}
            nb = {"block_id": b.get("block_id") or f"{sh['sheet_name']}|{b['tpa']}", "tpa": b["tpa"],
                  "label": b.get("label") or b["tpa"], "plans": [dict(p) for p in b["plans"]], "splits": splits,
                  "refer_cells": [dict(r) for r in b.get("refer_cells", [])],
                  "refer_text": b.get("refer_text") or sh.get("refer_text") or DEFAULT_REFER_TEXT,
                  "rows": rows, "columns": [{"label": c["label"], "keys": [dict(k) for k in c["keys"]]} for c in cols],
                  "column_set": cs if isinstance(cs, str) else "inline", "block_key": bkey,
                  "comment": b.get("comment")}
            for r in rows:
                for d in r["key"]:
                    reg.dim(d)
            for c in nb["columns"]:
                for k in c["keys"]:
                    for d in k:
                        reg.dim(d)
            nsh["blocks"].append(nb)
        out["sheets"].append(nsh)
    return out


# Cedant-mode only fields (SPEC §8.5): excluded from the tender template's spec hash, so adding the cedant sections to a
# spec never changes the issued reinsurer template ("reinsurer mode unchanged").
CEDANT_SHEET_FIELDS = ("scope_id", "formula", "premium_basis", "factor_tables", "riders", "plan_defaults", "benefits")
CEDANT_TOP_FIELDS = ("cedant_workbook",)


def spec_hash(spec: dict) -> str:
    s = {k: v for k, v in spec.items() if not k.startswith("_") and k not in CEDANT_TOP_FIELDS}
    if isinstance(s.get("sheets"), list):
        s["sheets"] = [{k: v for k, v in sh.items() if k not in CEDANT_SHEET_FIELDS} for sh in s["sheets"]]
    return hashlib.sha256(json.dumps(s, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# ---------------------------------------------------------------------------------------------- authoring
_COL_DIMS = ("gender", "marital")
_ROW_SECTION_DIMS = ("member_category",)


def spec_from_catalogue(cat, tender: dict, select: list[str] | None = None) -> dict:
    """Author a template_spec from a catalogue (SPEC §8.1 't generate --from-catalogue'): one sheet per
    product x rating region, one block per TPA, rows = (member category sections x) the base table's age bands,
    columns = the base table's gender / marital combinations, plans as column groups. REFER base cells become
    refer_cells. select: optional list of scope_ids."""
    reg = load_registry()
    sheets = {}
    column_sets = {}
    band_sets = {}
    for s in cat.scopes:
        if select and s.scope_id not in select:
            continue
        base = next((c for c in s.components if c.type == "BASE_TABLE"), None)
        if base is None:
            continue
        other = [d for d in base.keys if d not in ("plan", "age", *_COL_DIMS, *_ROW_SECTION_DIMS)]
        varying = [d for d in other if any(r["key"][d] != ANY for r in base.rows)]
        if varying:
            raise ProposalRequired(f"scope {s.scope_id}: base table varies by {varying}; the template principle "
                                   "(SPEC §8.0) has no column/row rule for these dims")
        # columns
        combos = []
        for r in base.rows:
            k = {d: r["key"][d] for d in _COL_DIMS if d in r["key"] and r["key"][d] != ANY}
            lab = "/".join(r.get("labels", {}).get(x, "") for x in r.get("labels", {}) if x in ("gender", "gender/marital", "marital"))
            if k not in [c[0] for c in combos]:
                combos.append((k, lab))
        def _ord(d, v):
            vals = reg.dim(d).values or ()
            return vals.index(v) if v in vals else 99
        combos.sort(key=lambda c: tuple(_ord(d, c[0].get(d)) for d in _COL_DIMS))
        if combos == [({}, "")] or not combos:
            cols = [{"label": "Rate", "keys": [{}]}]
        else:
            cols = [{"label": lab or "/".join(k.values()), "keys": [k]} for k, lab in combos]
        cs_name = "CS_" + hashlib.sha1(json.dumps(cols, sort_keys=True).encode()).hexdigest()[:8]
        column_sets[cs_name] = cols
        # rows
        secs = sorted({r["key"].get("member_category", ANY) for r in base.rows},
                      key=lambda v: reg.dim("member_category").values.index(v) if v in (reg.dim("member_category").values or ()) else
                      (100 + list(reg.dim("member_category").parents).index(v) if v in reg.dim("member_category").parents else 999))
        sections = []
        for sec in secs:
            bands = {}
            for r in base.rows:
                if r["key"].get("member_category", ANY) != sec:
                    continue
                rng = tuple(r["key"]["age"]) if r["key"].get("age", ANY) != ANY else (0, 120)
                bands[rng] = r.get("labels", {}).get("age", f"{rng[0]}-{rng[1]}")
            bl = [{"label": bands[k], "range": list(k)} for k in sorted(bands)]
            bname = "B_" + hashlib.sha1(json.dumps(bl, sort_keys=True).encode()).hexdigest()[:8]
            band_sets[bname] = bl
            sections.append({"label": sec.title() if sec != ANY else "All", "key": {} if sec == ANY else {"member_category": sec},
                             "age_bands": bname})
        refer = []
        for r in base.rows:
            if r["status"] == "REFER":
                refer.append({d: v for d, v in r["key"].items() if v != ANY})
        sname = f"{s.product_type[:10]} {s.rating_region or ''}".strip()[:31]
        sh = sheets.setdefault(sname, {"sheet_name": sname, "title": f"{s.product_type} - {s.rating_region}",
                                       "product_type": s.product_type, "regulator": s.regulator,
                                       "rating_region": s.rating_region, "mandatory": True, "blocks": [],
                                       "copay_basis": {}})
        for c in s.components:
            if c.type == "FACTOR_TABLE" and c.reference_level is not None:
                sh["copay_basis"][c.family] = c.reference_level
        plan_ids = [p.plan_id for p in s.plans if not s.plan_set or p.plan_id in s.plan_set]
        base_plans = {r["key"].get("plan", ANY) for r in base.rows}
        if base_plans == {ANY}:
            plan_ids = plan_ids[:1]
        for t in s.tpa_set:
            if any(b["tpa"] == t for b in sh["blocks"]):
                raise ProposalRequired(f"sheet {sname}: TPA {t} appears in two scopes; split the selection")
            blk = {"block_id": f"{s.scope_id}|{t}", "tpa": t, "label": t,
                   "plans": [{"plan_id": p, "label": s.plan(p).label, "network": s.plan(p).network_by_tpa.get(t)} for p in plan_ids],
                   "column_set": cs_name, "refer_cells": refer}
            if len(sections) == 1 and not sections[0]["key"]:
                blk["age_bands"] = sections[0]["age_bands"]
            else:
                blk["sections"] = sections
            sh["blocks"].append(blk)
    spec = {"template_spec_version": TEMPLATE_SPEC_VERSION, **tender, "currency": tender.get("currency", cat.currency),
            "premium_basis": tender.get("premium_basis", cat.premium_basis), "column_sets": column_sets,
            "age_band_sets": band_sets, "sheets": list(sheets.values()),
            "source_catalogue": cat.catalogue_id}
    return spec


# ---------------------------------------------------------------------------------------------- cedant workbook (§8.5)
# Sheet-level structure for the cedant-mode rate workbook (structure only, no values):
#   scope_id        read-back scope id (one TPA group) or prefix (several groups: "<scope_id>|<TPA>+<TPA>")
#   formula         {"order": [...], "rounding": n} of the read-back scope (default BASE, FACTORS, MODULES; options.rounding)
#   premium_basis   basis of the sheet's base table when it differs from the workbook's (SPEC §3.5, F7)
#   factor_tables[] {component_id, family, option_dim (default family), key_dim (network / plan / tpa / ... or none),
#                    keys (component key order, default registry order), tpas (default: every TPA of the sheet),
#                    rows [{"key", "option"} | [key, option] | option] or options x key_values,
#                    reference: option (same for every key) | {key: option}}
#   riders[]        {component_id, family (module_*), key_dim, keys, unit, mode (ADD | MULTIPLY), eligibility, tpas,
#                    premium_basis, rows | options x key_values}
#   plan_defaults[] option families sold per plan (catalogue default, SPEC §3.4): the family of a factor table or rider;
#                   a TPA group is asked only for the families its own tables carry
#   key_labels      (factor tables / riders) {key: text} shown beside the key, e.g. the source column a plan takes
#   benefits[]      benefit codes (registry/benefits.json) per plan: "code" | {"code", "plans": [...]}
# Top level: cedant_workbook {catalogue_id, version, effective_date, spare_rows, notes[]}.
CEDANT_SECTIONS = ("factor_tables", "riders", "plan_defaults", "benefits")
CEDANT_DEFAULTS = {"spare_rows": 10, "notes": []}
ALL_TPAS = "ALL"
NONE_OPTION = "NONE"          # rider option meaning "not purchased" (evaluator NONE_OPTION)
_MODULE_UNITS = ("PER_MEMBER", "PER_ELIGIBLE_FEMALE", "PER_FAMILY")


def has_cedant_sections(spec: dict) -> bool:
    return any(sh.get(k) for sh in spec.get("sheets", []) for k in CEDANT_SECTIONS)


def _sid(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.|+-]+", "_", str(s)).strip("_")


def tpas_label(tpas, all_tpas) -> str:
    return ALL_TPAS if list(tpas) == list(all_tpas) else ", ".join(tpas)


def _table_rows(t: dict, where: str, errs: list, rider: bool) -> list:
    """Rows of a factor table / rider spec as [{"key": value | ANY, "option": str}] in spec order."""
    out = []
    if t.get("rows") is not None and (t.get("options") is not None or t.get("key_values") is not None):
        errs.append(f"{where}: give rows, or options (x key_values), not both")
        return out
    if t.get("rows") is not None:
        for i, r in enumerate(t["rows"]):
            if isinstance(r, dict):
                k, o = r.get("key", ANY), r.get("option")
            elif isinstance(r, (list, tuple)) and len(r) == 2:
                k, o = r
            elif isinstance(r, str):
                k, o = ANY, r
            else:
                errs.append(f"{where}: rows[{i}] must be {{key, option}}, [key, option] or an option")
                continue
            out.append({"key": ANY if k is None else str(k), "option": None if o is None else str(o)})
    else:
        opts = t.get("options") or []
        kvs = t.get("key_values") or [ANY]
        for k in kvs:
            for o in opts:
                out.append({"key": str(k), "option": str(o)})
    if not out:
        errs.append(f"{where}: no rows")
    for r in out:
        if not r["option"] or not str(r["option"]).strip():
            errs.append(f"{where}: blank option label")
        if rider and r["option"] == NONE_OPTION:
            errs.append(f"{where}: option '{NONE_OPTION}' is reserved (rider not purchased)")
    seen = set()
    for r in out:
        kk = (r["key"], r["option"])
        if kk in seen:
            errs.append(f"{where}: duplicate row key={r['key']} option={r['option']}")
        seen.add(kk)
    return out


def cedant_model(spec: dict) -> tuple[dict, list[str]]:
    """Normalise the cedant-mode sections of a template spec. Returns (model, problems); the generator and the
    reader both work from this model, so the workbook and its read-back cannot disagree on structure."""
    reg = load_registry()
    errs: list[str] = []
    top = {**CEDANT_DEFAULTS, **(spec.get("cedant_workbook") or {})}
    if not isinstance(top.get("spare_rows"), int) or top["spare_rows"] < 0:
        errs.append("cedant_workbook.spare_rows must be an integer >= 0")
    model = {"options": top, "sheets": []}
    pe_seen = {}
    for si, sh in enumerate(spec.get("sheets", [])):
        where = f"sheets[{si}] '{sh.get('sheet_name')}'"
        blocks = sh.get("blocks") or []
        tpas = []
        for b in blocks:
            if b.get("tpa") not in tpas:
                tpas.append(b.get("tpa"))
        pe = (sh.get("product_type"), sh.get("rating_region"))
        if pe in pe_seen:
            errs.append(f"{where}: product x emirate {pe} also on sheet '{pe_seen[pe]}' (the long tables are keyed on "
                        "product x emirate)")
        pe_seen[pe] = sh.get("sheet_name")
        if sh.get("premium_basis") is not None and sh["premium_basis"] not in ("GROSS", "NET"):
            errs.append(f"{where}: premium_basis must be GROSS or NET")
        plans_all = []
        for b in blocks:
            for p in b.get("plans") or []:
                if p.get("plan_id") not in plans_all:
                    plans_all.append(p.get("plan_id"))
        msh = {"sheet_name": sh.get("sheet_name"), "product_type": sh.get("product_type"),
               "regulator": sh.get("regulator"), "rating_region": sh.get("rating_region"), "tpas": tpas,
               "premium_basis": sh.get("premium_basis"), "formula": sh.get("formula"),
               "factor_tables": [], "riders": [], "plan_defaults": [], "benefits": [], "groups": []}
        cids = set()

        def _common(t, kind, ti):
            tw = f"{where} {kind}[{ti}]"
            fam = t.get("family")
            if not fam:
                errs.append(f"{tw}: no family")
                return None
            tw = f"{tw} ({fam})"
            odim = t.get("option_dim") or fam
            if odim not in reg.dims:
                errs.append(f"{tw}: option dimension '{odim}' is not in the registry (set option_dim)")
                return None
            kdim = t.get("key_dim")
            if kdim is not None and kdim not in reg.dims:
                errs.append(f"{tw}: key_dim '{kdim}' is not in the registry")
                return None
            if kdim == odim:
                errs.append(f"{tw}: key_dim equals the option dimension")
                return None
            want = {odim} | ({kdim} if kdim else set())
            keys = list(t.get("keys") or reg.sort_dims(want))
            if set(keys) != want or len(keys) != len(want):
                errs.append(f"{tw}: keys {keys} must be exactly {sorted(want)}")
                return None
            ttp = list(t.get("tpas") or tpas)
            bad = [x for x in ttp if x not in tpas]
            if bad:
                errs.append(f"{tw}: tpas {bad} have no block on the sheet")
            cid = t.get("component_id") or _sid(f"{'f' if kind == 'factor_tables' else 'm'}_{fam}")
            if cid in cids:
                errs.append(f"{tw}: duplicate component_id '{cid}' on the sheet")
            cids.add(cid)
            rows = _table_rows(t, tw, errs, kind == "riders")
            for r in rows:
                for d, v in ((odim, r["option"]), (kdim, r["key"])):
                    if d is None or v is None:
                        continue
                    try:
                        reg.check_value(d, v, allow_any=(d == kdim), allow_parent=True)
                    except Exception as e:  # noqa: BLE001
                        errs.append(f"{tw}: {e}")
                if kdim is None and r["key"] != ANY:
                    errs.append(f"{tw}: row key '{r['key']}' given but the table has no key_dim")
                if kdim == "plan" and r["key"] != ANY and r["key"] not in plans_all:
                    errs.append(f"{tw}: plan '{r['key']}' is not a plan of the sheet")
                if kdim == "tpa" and r["key"] != ANY and r["key"] not in ttp:
                    errs.append(f"{tw}: TPA key '{r['key']}' is outside the table's tpas")
            klab = dict(t.get("key_labels") or {})
            bad = [k for k in klab if k not in {r["key"] for r in rows}]
            if bad:
                errs.append(f"{tw}: key_labels for keys without rows: {bad}")
            return {"component_id": cid, "family": fam, "option_dim": odim, "key_dim": kdim, "keys": keys,
                    "tpas": ttp, "tpas_label": tpas_label(ttp, tpas), "label": t.get("label"), "rows": rows,
                    "key_labels": klab}

        for ti, t in enumerate(sh.get("factor_tables") or []):
            m = _common(t, "factor_tables", ti)
            if m is None:
                continue
            tw = f"{where} factor_tables[{ti}] ({m['family']})"
            ref = t.get("reference")
            if ref is None:
                errs.append(f"{tw}: no reference option (the option with factor 1.0, SPEC §3.4)")
                continue
            keys_present = []
            for r in m["rows"]:
                if r["key"] not in keys_present:
                    keys_present.append(r["key"])
            for r in m["rows"]:
                want = ref.get(r["key"]) if isinstance(ref, dict) else ref
                r["reference"] = want is not None and r["option"] == want
            if isinstance(ref, dict):
                for k in ref:
                    if k not in keys_present:
                        errs.append(f"{tw}: reference given for key '{k}' that has no rows")
            for k in keys_present:
                n = sum(1 for r in m["rows"] if r["key"] == k and r["reference"])
                inherited = k != ANY and any(r["key"] == ANY and r["reference"] for r in m["rows"])
                if n > 1:
                    errs.append(f"{tw}: key '{k}' has {n} reference rows")
                elif n == 0 and not inherited:
                    errs.append(f"{tw}: key '{k}' has no reference row (reference option not among its rows)")
            m["reference"] = ref
            msh["factor_tables"].append(m)
        for ti, t in enumerate(sh.get("riders") or []):
            m = _common(t, "riders", ti)
            if m is None:
                continue
            tw = f"{where} riders[{ti}] ({m['family']})"
            unit = t.get("unit")
            if unit not in _MODULE_UNITS:
                errs.append(f"{tw}: unit must be one of {_MODULE_UNITS}")
            mode = t.get("mode", "ADD")
            if mode not in ("ADD", "MULTIPLY"):
                errs.append(f"{tw}: mode must be ADD or MULTIPLY")
            elig = dict(t.get("eligibility") or ({"maternity_eligible": "Y"} if unit == "PER_ELIGIBLE_FEMALE" else {}))
            for d, v in elig.items():
                if d not in reg.dims:
                    errs.append(f"{tw}: eligibility dimension '{d}' is not in the registry")
            if t.get("premium_basis") is not None and t["premium_basis"] not in ("GROSS", "NET"):
                errs.append(f"{tw}: premium_basis must be GROSS or NET")
            m.update({"unit": unit, "mode": mode, "eligibility": elig, "premium_basis": t.get("premium_basis"),
                      "mandatory": bool(t.get("mandatory", True))})
            msh["riders"].append(m)
        fams = {}
        for m in msh["factor_tables"] + msh["riders"]:
            if (m["tpas_label"], m["family"]) in fams:
                errs.append(f"{where}: two tables of family '{m['family']}' for TPAs {m['tpas_label']}")
            fams[(m["tpas_label"], m["family"])] = m
        for fam in sh.get("plan_defaults") or []:
            src = [m for m in msh["factor_tables"] + msh["riders"] if m["family"] == fam]
            if not src:
                errs.append(f"{where}: plan default family '{fam}' has no factor table or rider on the sheet")
            elif any(m["option_dim"] != fam for m in src):
                errs.append(f"{where}: plan default family '{fam}' is not an option family (its option dimension is "
                            f"'{src[0]['option_dim']}'; exposure supplies it)")
            if fam in msh["plan_defaults"]:
                errs.append(f"{where}: plan default family '{fam}' listed twice")
            msh["plan_defaults"].append(fam)
        for bi, bdef in enumerate(sh.get("benefits") or []):
            code = bdef if isinstance(bdef, str) else (bdef or {}).get("code")
            plans = None if isinstance(bdef, str) else (bdef or {}).get("plans")
            if code not in reg.benefits:
                errs.append(f"{where} benefits[{bi}]: benefit code '{code}' is not in registry/benefits.json")
                continue
            if plans is not None:
                bad = [p for p in plans if p not in plans_all]
                if bad:
                    errs.append(f"{where} benefits[{bi}] ({code}): plans {bad} are not plans of the sheet")
            if code in [b["code"] for b in msh["benefits"]]:
                errs.append(f"{where} benefits[{bi}]: benefit code '{code}' listed twice")
            msh["benefits"].append({"code": code, "plans": list(plans) if plans is not None else None})
        # TPA groups: TPAs sharing the same factor tables and riders form one read-back scope
        sig_groups = []
        for t in tpas:
            sig = (tuple(m["component_id"] for m in msh["factor_tables"] if t in m["tpas"]),
                   tuple(m["component_id"] for m in msh["riders"] if t in m["tpas"]))
            g = next((g for g in sig_groups if g["sig"] == sig), None)
            if g is None:
                sig_groups.append({"sig": sig, "tpas": [t]})
            else:
                g["tpas"].append(t)
        base_id = sh.get("scope_id")
        if not base_id:
            pref = {str(b.get("block_id") or "").split("|")[0] for b in blocks}
            base_id = pref.pop() if len(pref) == 1 and "|" in str(blocks[0].get("block_id") or "") else _sid(sh.get("sheet_name"))
        for g in sig_groups:
            plans = []
            for b in blocks:
                if b.get("tpa") not in g["tpas"]:
                    continue
                for pos, p in enumerate(b.get("plans") or []):
                    cur = next((x for x in plans if x["plan_id"] == p["plan_id"]), None)
                    if cur is None:
                        cur = {"plan_id": p["plan_id"], "label": p.get("label") or p["plan_id"],
                               "tier_rank": p.get("tier_rank", p.get("plan_number", pos + 1)), "network_by_tpa": {}}
                        plans.append(cur)
                    cur["network_by_tpa"][b["tpa"]] = p.get("network")
            sid = base_id if len(sig_groups) == 1 else f"{base_id}|{'+'.join(g['tpas'])}"
            msh["groups"].append({"scope_id": sid, "tpas": g["tpas"], "label": tpas_label(g["tpas"], tpas),
                                  "factor_tables": list(g["sig"][0]), "riders": list(g["sig"][1]), "plans": plans})
        for g in msh["groups"]:          # a group is asked only for the families its own tables carry
            g["default_families"] = [fam for fam in msh["plan_defaults"]
                                     if any(m["family"] == fam and set(g["tpas"]) <= set(m["tpas"])
                                            for m in msh["factor_tables"] + msh["riders"])]
        model["sheets"].append(msh)
    return model, errs


def cedant_errors(spec: dict) -> list[str]:
    if not has_cedant_sections(spec) and "cedant_workbook" not in spec:
        return []
    return cedant_model(spec)[1]


def cedant_spec_from_catalogue(cat, tender: dict, select: list[str] | None = None) -> dict:
    """Author a cedant-mode template spec from an existing catalogue's STRUCTURE (SPEC §8.5; WS5 fixtures): the
    tender layout of spec_from_catalogue plus, per sheet, the catalogue's factor tables, riders, plan default families
    and benefit codes (labels only; values stay in the catalogue). Components the workbook does not carry (loading,
    fees, refer components, experience rating, rules) are listed in cedant_workbook.not_carried."""
    spec = spec_from_catalogue(cat, tender, select)
    by_sheet = {sh["sheet_name"]: sh for sh in spec["sheets"]}
    scopes_by_sheet = {}
    for s in cat.scopes:
        if select and s.scope_id not in select:
            continue
        if not any(c.type == "BASE_TABLE" for c in s.components):
            continue
        sname = f"{s.product_type[:10]} {s.rating_region or ''}".strip()[:31]
        scopes_by_sheet.setdefault(sname, []).append(s)
    not_carried = []
    for sname, scopes in scopes_by_sheet.items():
        sh = by_sheet[sname]
        multi = len(scopes) > 1
        if not multi:
            sh["scope_id"] = scopes[0].scope_id
        ft, rd, defaults, codes = [], [], [], {}
        plan_ids = []
        for s in scopes:
            tp = list(s.tpa_set) if multi else None
            sh["formula"] = {"order": list(s.formula.order), "rounding": s.formula.rounding}
            base = next(c for c in s.components if c.type == "BASE_TABLE")
            if base.premium_basis and base.premium_basis != cat.premium_basis:
                sh["premium_basis"] = base.premium_basis
            for c in s.components:
                if c.type not in ("FACTOR_TABLE", "MODULE"):
                    if c.type != "BASE_TABLE":
                        not_carried.append(f"{s.scope_id}/{c.component_id} ({c.type})")
                    continue
                if c.family in c.keys:
                    odim = c.family
                elif len(c.keys) == 1:
                    odim = c.keys[0]
                else:
                    raise ProposalRequired(f"{s.scope_id}/{c.component_id}: option dimension of family '{c.family}' "
                                           "is ambiguous (the long table needs one option and at most one key)")
                rest = [k for k in c.keys if k != odim]
                if len(rest) > 1:
                    raise ProposalRequired(f"{s.scope_id}/{c.component_id}: keyed on {rest}; the long table holds one key")
                kdim = rest[0] if rest else None
                rows = []
                for r in c.rows:
                    kv = r["key"].get(kdim, ANY) if kdim else ANY
                    if isinstance(kv, list) or isinstance(r["key"][odim], list):
                        raise ProposalRequired(f"{s.scope_id}/{c.component_id}: range keys have no long-table form")
                    rows.append({"key": str(kv), "option": str(r["key"][odim])})
                t = {"component_id": c.component_id, "family": c.family, "keys": list(c.keys), "rows": rows}
                if odim != c.family:
                    t["option_dim"] = odim
                if kdim:
                    t["key_dim"] = kdim
                if tp:
                    t["tpas"] = tp
                if c.type == "FACTOR_TABLE":
                    if c.reference_level_by_key:
                        if c.reference_level_by != kdim:
                            raise ProposalRequired(f"{s.scope_id}/{c.component_id}: reference varies by "
                                                   f"'{c.reference_level_by}', not by the table key '{kdim}'")
                        t["reference"] = dict(c.reference_level_by_key)
                    else:
                        t["reference"] = c.reference_level
                    ft.append(t)
                else:
                    t.update({"unit": c.unit, "mode": c.mode, "eligibility": dict(c.eligibility)})
                    if c.premium_basis:
                        t["premium_basis"] = c.premium_basis
                    rd.append(t)
            fams = {t["option_dim"] if "option_dim" in t else t["family"] for t in ft + rd}
            for p in s.plans:
                for fam in list(p.defaults) + list(s.defaults):
                    if fam in fams and fam not in defaults:
                        defaults.append(fam)
            plan_ids += [p.plan_id for p in s.plans if p.plan_id not in plan_ids]
            for b in s.benefits:
                codes.setdefault(b.benefit_code, [])
                if b.plan_id not in codes[b.benefit_code]:
                    codes[b.benefit_code].append(b.plan_id)
        sh["factor_tables"] = ft
        sh["riders"] = rd
        sh["plan_defaults"] = [f for f in defaults if f in {t["family"] for t in ft + rd}]
        sh["benefits"] = [c if sorted(ps) == sorted(plan_ids) else {"code": c, "plans": ps} for c, ps in codes.items()]
    spec["cedant_workbook"] = {"catalogue_id": cat.catalogue_id, "version": cat.version,
                               "effective_date": cat.effective_date, "spare_rows": CEDANT_DEFAULTS["spare_rows"],
                               "notes": [], "not_carried": sorted(not_carried) + [f"rules ({len(cat.rules)})"] * bool(cat.rules)}
    return spec
