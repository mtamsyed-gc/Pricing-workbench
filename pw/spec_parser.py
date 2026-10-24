"""Catalogue spec parser (SPEC §3, §9): declarative spec + source workbook -> canonical Catalogue.

Spec layout (JSON):
  spec_id, catalogue{catalogue_id, owner, kind, version, effective_date, currency, premium_basis},
  source_file (relative to the spec file), maps{name: {label: value | {dim: v} | [{dim: v}, ...]}},
  band_maps{name: {label: [lo, hi]} | {"parse": [labels]}}, text_values{"Refer": "REFER"}, defaults{family: option},
  scopes[{scope_id, product_type, regulator, rating_region, tpa_set, plan_set?, rating_basis_age?, currency?,
          premium_basis?, plans[], defaults{}, components[], formula{}, benefits{plan_id: [lines]}}], rules[]
Component sources: "sources": [grid, ...] (see io_excel.read_grid), "rows": [{"key": {...}, "value": x}],
or the single-key shorthand "values": {option: value}.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import MappingRequired, SpecError
from .io_excel import WorkbookReader, read_grid
from .model import BenefitLine, Catalogue, Component, Plan, RatingFormula, RatingScope, Rule
from .registry import ANY, BandMap, load_registry

DEFAULT_BLOCK_TOLERANCE_ABS = 0.01
DEFAULT_MULTIPLIER_DECIMALS = 4


def load_spec(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_catalogue(spec_path: Path | None = None, spec: dict | None = None, source_file: Path | None = None,
                    registry=None) -> Catalogue:
    reg = registry or load_registry()
    if spec is None:
        spec = load_spec(spec_path)
    base_dir = Path(spec_path).resolve().parent if spec_path else Path.cwd()
    src_path = None
    if source_file:
        src_path = Path(source_file)
    elif spec.get("source_file"):
        src_path = (base_dir / spec["source_file"]).resolve()
    reader = WorkbookReader(src_path) if src_path else None

    band_maps = {n: BandMap.from_spec(n, b) for n, b in (spec.get("band_maps") or {}).items()}
    maps = spec.get("maps") or {}
    text_values = spec.get("text_values") or {}
    cat_d = spec["catalogue"]
    cat = Catalogue(
        catalogue_id=cat_d["catalogue_id"], owner=cat_d["owner"], kind=cat_d["kind"], version=str(cat_d["version"]),
        effective_date=cat_d.get("effective_date"), currency=cat_d["currency"], premium_basis=cat_d["premium_basis"],
        source_file=src_path.name if src_path else None, spec_id=spec["spec_id"],
        age_band_maps={n: [list(b) for b in bm.bands] for n, bm in band_maps.items()})
    source_index = []
    cat_defaults = spec.get("defaults") or {}

    for s in spec["scopes"]:
        scope = RatingScope(
            scope_id=s["scope_id"], product_type=s["product_type"], regulator=s.get("regulator"),
            rating_region=s.get("rating_region"), tpa_set=list(s["tpa_set"]), plan_set=s.get("plan_set"),
            notes=s.get("notes"), rating_basis_age=s.get("rating_basis_age", "INCEPTION_AGE"),
            currency=s.get("currency") or cat.currency, premium_basis=s.get("premium_basis") or cat.premium_basis,
            defaults={**cat_defaults, **(s.get("defaults") or {})},
            formula=RatingFormula(**(s.get("formula") or {})))
        for code in ("product_type", "regulator"):
            reg.check_value(code, getattr(scope, code), allow_any=False, allow_parent=False)
        for p in s.get("plans", []):
            scope.plans.append(Plan(plan_id=p["plan_id"], label=p.get("label", p["plan_id"]), tier_rank=p.get("tier_rank"),
                                    network_by_tpa=dict(p.get("network_by_tpa") or {}),
                                    attributes=dict(p.get("attributes") or {}), defaults=dict(p.get("defaults") or {})))
            for t in scope.plans[-1].network_by_tpa:
                if t not in scope.tpa_set:
                    raise SpecError(f"{scope.scope_id}: plan {p['plan_id']} maps network for TPA '{t}' not in tpa_set")
        plans_by_label = {p.label: p.plan_id for p in scope.plans}
        ctx = dict(reader=reader, maps=maps, plans_by_label=plans_by_label, band_maps=band_maps,
                   text_values=text_values, reg=reg, scope=scope, index=source_index)
        for i, c in enumerate(s.get("components", [])):
            for comp in _parse_component(c, i, ctx):
                scope.components.append(comp)
        if len(scope.components_of("BASE_TABLE")) > 1:
            raise SpecError(f"{scope.scope_id}: more than one BASE_TABLE (a BLOCK_SET is normalised to a BASE_TABLE)")
        for plan_id, lines in (s.get("benefits") or {}).items():
            scope.plan(plan_id)
            for ln in lines:
                reg.check_benefit(ln["benefit_code"])
                bl = BenefitLine(plan_id=plan_id, **ln)
                if bl.value is None and bl.status == "PARSED":
                    bl.status = "MANUAL_REVIEW"
                scope.benefits.append(bl)
        cat.scopes.append(scope)

    for r in spec.get("rules", []):
        cat.rules.append(Rule(rule_id=r["rule_id"], scope=dict(r.get("scope") or {}), type=r["type"],
                              parameters=dict(r.get("parameters") or {}), text=r.get("text")))
    cat.meta = {"source_index": source_index, "spec_version": spec.get("spec_version", "1")}
    cat.validate()
    return cat


# ---------------------------------------------------------------------------------------------------------------
def _rows_from_sources(sources, ctx, comp_id, level=None):
    rows = []
    if ctx["reader"] is None:
        raise SpecError(f"{comp_id}: component reads a source grid but no source_file was given")
    for src in sources:
        for cell in read_grid(ctx["reader"], src, ctx["maps"], ctx["plans_by_label"], ctx["band_maps"],
                              ctx["text_values"]):
            for k in cell["keys"]:
                rows.append({"key": k, "value": cell.get("value", cell["raw"]), "status": cell["status"],
                             "labels": cell["labels"], "source_ref": cell["ref"]})
            ctx["index"].append({"scope_id": ctx["scope"].scope_id, "component_id": comp_id, "level": level,
                                 "ref": cell["ref"], "raw": cell["raw"], "value": cell.get("value", cell["raw"]),
                                 "status": cell["status"],
                                 "keys": cell["keys"]})
    return rows


def _rows_inline(c, ctx):
    rows = []
    if "values" in c:
        keys = c.get("keys") or [c["family"]]
        if len(keys) != 1:
            raise SpecError(f"{c.get('component_id')}: 'values' shorthand needs exactly one key dimension")
        for opt, v in c["values"].items():
            rows.append({"key": {keys[0]: opt}, "value": None if v is None else float(v),
                         "status": "VALUE" if v is not None else "REFER", "labels": {}, "source_ref": "spec"})
    for r in c.get("rows", []):
        st = r.get("status", "VALUE" if r.get("value") is not None else "REFER")
        rows.append({"key": dict(r["key"]), "value": None if r.get("value") is None else float(r["value"]),
                     "status": st, "labels": dict(r.get("labels") or {}), "source_ref": r.get("source_ref", "spec")})
    return rows


def _normalise_rows(rows, comp_id, ctx, declared_keys=None):
    reg = ctx["reg"]
    scope = ctx["scope"]
    dims = set(declared_keys or [])
    for r in rows:
        dims.update(r["key"].keys())
    dims = reg.sort_dims(dims)
    seen = {}
    plan_ids = {p.plan_id for p in scope.plans}
    for r in rows:
        k = r["key"]
        for d in dims:
            if d not in k:
                k[d] = ANY
            v = k[d]
            if reg.is_range(d):
                if v != ANY:
                    if not (isinstance(v, (list, tuple)) and len(v) == 2):
                        raise SpecError(f"{comp_id}: range dim '{d}' needs [lo, hi] or ANY, got {v!r}")
                    k[d] = [int(v[0]), int(v[1])]
            else:
                reg.check_value(d, v)
                if d == "plan" and v != ANY and v not in plan_ids:
                    raise MappingRequired(f"{comp_id}: plan '{v}' not declared in scope {scope.scope_id}",
                                          [{"plan": v}])
                if d == "tpa" and v != ANY and v not in scope.tpa_set:
                    raise MappingRequired(f"{comp_id}: tpa '{v}' not in scope {scope.scope_id} tpa_set", [{"tpa": v}])
        r["key"] = {d: k[d] for d in dims}
        sig = json.dumps(r["key"], sort_keys=True)
        if sig in seen:
            raise SpecError(f"{comp_id}: duplicate row key {r['key']} ({seen[sig]} and {r.get('source_ref')})")
        seen[sig] = r.get("source_ref")
    rows.sort(key=lambda r: json.dumps(r["key"], sort_keys=True))
    return dims, rows


def _common(c, comp_id, ctx):
    return dict(currency=c.get("currency") or ctx["scope"].currency,
                premium_basis=c.get("premium_basis") or ctx["scope"].premium_basis, notes=c.get("notes"))


def _parse_component(c, i, ctx):
    t = c["type"]
    comp_id = c.get("component_id") or f"{t.lower()}_{i}"
    if t in ("BASE_TABLE", "FACTOR_TABLE", "MODULE", "REFER"):
        rows = _rows_inline(c, ctx)
        if c.get("sources"):
            rows += _rows_from_sources(c["sources"], ctx, comp_id)
        if t == "REFER":
            for r in rows:
                r["status"] = "REFER"
                r["value"] = None
        dims, rows = _normalise_rows(rows, comp_id, ctx, c.get("keys"))
        comp = Component(component_id=comp_id, type=t, family=c.get("family"), keys=dims, rows=rows,
                         reference_level=c.get("reference_level"), reference_level_by=c.get("reference_level_by"),
                         reference_level_by_key=dict(c.get("reference_level_by_key") or {}),
                         unit=c.get("unit"), mode=c.get("mode", "ADD"), eligibility=dict(c.get("eligibility") or {}),
                         default_option=c.get("default_option"), **_common(c, comp_id, ctx))
        if t == "FACTOR_TABLE":
            _check_reference(comp)
        if t == "MODULE" and comp.unit == "PER_ELIGIBLE_FEMALE" and not comp.eligibility:
            comp.eligibility = {"maternity_eligible": "Y"}
        return [comp]
    if t == "BLOCK_SET":
        return _parse_block_set(c, comp_id, ctx)
    if t == "FEE":
        if (c.get("amount") is None) == (c.get("pct") is None):
            raise SpecError(f"{comp_id}: FEE needs exactly one of amount / pct")
        return [Component(component_id=comp_id, type=t, amount=c.get("amount"), pct=c.get("pct"), **_common(c, comp_id, ctx))]
    if t == "LOADING":
        return [Component(component_id=comp_id, type=t, cap=c.get("cap"), pct=c.get("pct"), **_common(c, comp_id, ctx))]
    if t == "EXPERIENCE_RATED":
        return [Component(component_id=comp_id, type=t, basis=dict(c.get("basis") or {}), **_common(c, comp_id, ctx))]
    raise SpecError(f"unknown component type {t}")


def _check_reference(comp: Component):
    fam = comp.family
    if fam is None:
        raise SpecError(f"{comp.component_id}: FACTOR_TABLE needs a family")
    if comp.reference_level is None and not comp.reference_level_by_key:
        raise SpecError(f"{comp.component_id}: FACTOR_TABLE must declare reference_level or reference_level_by_key (SPEC §3.4)")
    if fam in comp.keys:
        opts = {r["key"][fam] for r in comp.rows}
        refs = [comp.reference_level] if comp.reference_level is not None else list(comp.reference_level_by_key.values())
        for ref in refs:
            if ref not in opts:
                raise SpecError(f"{comp.component_id}: reference level '{ref}' is not an option of the table")


def _parse_block_set(c, comp_id, ctx):
    fam = c["family"]
    ref_level = c["reference_level"]
    blocks = {}
    for b in c["blocks"]:
        rows = _rows_inline(b, ctx)
        if b.get("sources"):
            rows += _rows_from_sources(b["sources"], ctx, comp_id, level=b["level"])
        dims, rows = _normalise_rows(rows, f"{comp_id}[{b['level']}]", ctx)
        blocks[b["level"]] = (dims, rows)
    if ref_level not in blocks:
        raise SpecError(f"{comp_id}: reference block '{ref_level}' missing")
    ref_dims, ref_rows = blocks[ref_level]
    for lvl, (dims, _) in blocks.items():
        if dims != ref_dims:
            raise SpecError(f"{comp_id}: block {lvl} keys {dims} differ from reference block keys {ref_dims}")
    ref_by = {json.dumps(r["key"], sort_keys=True): r for r in ref_rows}
    decimals = int(c.get("multiplier_decimals", DEFAULT_MULTIPLIER_DECIMALS))
    declared = c.get("multipliers") or {}
    multipliers, mult_source = {}, {}
    for lvl, (_, rows) in blocks.items():
        if lvl == ref_level:
            continue
        if lvl in declared:
            multipliers[lvl] = float(declared[lvl])
            mult_source[lvl] = "declared"
            continue
        ratios = []
        for r in rows:
            base = ref_by.get(json.dumps(r["key"], sort_keys=True))
            if base and base["status"] == "VALUE" and r["status"] == "VALUE" and base["value"]:
                ratios.append(r["value"] / base["value"])
        if not ratios:
            raise SpecError(f"{comp_id}: block {lvl} has no comparable cells")
        multipliers[lvl] = round(statistics.median(ratios), decimals)
        mult_source[lvl] = "median"
    common = _common(c, comp_id, ctx)
    base = Component(component_id=comp_id, type="BASE_TABLE", keys=ref_dims, rows=ref_rows, derived_from=comp_id,
                     **common)
    f_rows = [{"key": {fam: ref_level}, "value": 1.0, "status": "VALUE", "labels": {}, "source_ref": "BLOCK_SET reference"}]
    for lvl in sorted(multipliers):
        f_rows.append({"key": {fam: lvl}, "value": multipliers[lvl], "status": "VALUE", "labels": {},
                       "source_ref": f"BLOCK_SET implied ({mult_source[lvl]})"})
    implied = Component(
        component_id=f"{comp_id}.implied", type="FACTOR_TABLE", family=fam, keys=[fam], rows=f_rows,
        reference_level=ref_level, derived_from=comp_id,
        source_blocks={lvl: rows for lvl, (_, rows) in blocks.items() if lvl != ref_level},
        block_check={"tolerance_abs": float(c.get("tolerance_abs", DEFAULT_BLOCK_TOLERANCE_ABS)),
                     "resolution": c.get("resolution", "DERIVED"), "decimals": decimals,
                     "multipliers": multipliers, "multiplier_source": mult_source},
        currency=common["currency"], premium_basis=common["premium_basis"])
    if implied.block_check["resolution"] not in ("DERIVED", "SOURCE"):
        raise SpecError(f"{comp_id}: resolution must be DERIVED or SOURCE")
    return [base, implied]
