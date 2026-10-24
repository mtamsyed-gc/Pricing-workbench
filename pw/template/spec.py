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


def spec_hash(spec: dict) -> str:
    s = {k: v for k, v in spec.items() if not k.startswith("_")}
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
