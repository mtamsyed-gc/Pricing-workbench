"""Canonical catalogue model (SPEC §3, §4.2, §4.4).

Every source (expiring catalogue, tender submission, market catalogue) is parsed into this model; engines read
only this model. Table components hold *rows*: ``{"key": {dim: value | "ANY" | [lo, hi]}, "value": float | None,
"status": "VALUE" | "REFER", "labels": {dim: source label}, "source_ref": "Sheet!B7"}``.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import SpecError

KINDS = ("EXPIRING", "SUBMISSION", "MARKET", "PROPOSED")
BASES = ("GROSS", "NET")
COMPONENT_TYPES = ("BASE_TABLE", "FACTOR_TABLE", "BLOCK_SET", "MODULE", "FEE", "LOADING", "REFER", "EXPERIENCE_RATED")
MODULE_UNITS = ("PER_MEMBER", "PER_ELIGIBLE_FEMALE", "PER_FAMILY")
RULE_TYPES = ("ELIGIBILITY", "UW", "LOADING_CAP", "REFERRAL", "RENEWAL", "REVIEW", "OTHER")
ROW_STATUS = ("VALUE", "REFER")


@dataclass
class Plan:
    plan_id: str
    label: str
    tier_rank: int | None = None
    network_by_tpa: dict = field(default_factory=dict)
    attributes: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)       # catalogue default option per family (SPEC §3.4)


@dataclass
class Component:
    component_id: str
    type: str
    family: str | None = None
    keys: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    reference_level: str | None = None
    reference_level_by: str | None = None              # dim whose value selects the reference level
    reference_level_by_key: dict = field(default_factory=dict)
    unit: str | None = None                            # MODULE
    mode: str = "ADD"                                  # MODULE: ADD | MULTIPLY
    eligibility: dict = field(default_factory=dict)    # MODULE filter, e.g. {"maternity_eligible": "Y"}
    default_option: str | None = None                  # MODULE / FACTOR_TABLE fallback default
    amount: float | None = None                        # FEE fixed
    pct: float | None = None                           # FEE % / LOADING
    cap: float | None = None                           # LOADING cap
    basis: dict = field(default_factory=dict)          # EXPERIENCE_RATED
    currency: str | None = None
    premium_basis: str | None = None
    derived_from: str | None = None                    # BLOCK_SET normalisation link
    source_blocks: dict = field(default_factory=dict)  # BLOCK_SET: level -> rows (as in source)
    block_check: dict = field(default_factory=dict)    # BLOCK_SET: tolerance, resolution, multipliers, decimals
    notes: str | None = None


@dataclass
class RatingFormula:
    order: list = field(default_factory=lambda: ["BASE", "FACTORS", "MODULES"])
    rounding: int = 2
    min_premium: float | None = None
    max_premium: float | None = None
    refer_rules: list = field(default_factory=list)


@dataclass
class BenefitLine:
    plan_id: str
    benefit_code: str
    value: object = None
    structure: dict | None = None
    condition_text: str | None = None
    source_ref: str | None = None
    status: str = "PARSED"


@dataclass
class RatingScope:
    scope_id: str
    product_type: str
    regulator: str | None
    rating_region: str | None
    tpa_set: list
    plan_set: list | None = None
    notes: str | None = None
    rating_basis_age: str = "INCEPTION_AGE"
    currency: str | None = None
    premium_basis: str | None = None
    plans: list = field(default_factory=list)
    components: list = field(default_factory=list)
    formula: RatingFormula = field(default_factory=RatingFormula)
    defaults: dict = field(default_factory=dict)
    benefits: list = field(default_factory=list)

    def plan(self, plan_id: str) -> Plan:
        for p in self.plans:
            if p.plan_id == plan_id:
                return p
        raise SpecError(f"scope {self.scope_id}: unknown plan '{plan_id}'")

    def components_of(self, *types) -> list:
        return [c for c in self.components if c.type in types]


@dataclass
class Rule:
    rule_id: str
    scope: dict
    type: str
    parameters: dict = field(default_factory=dict)
    text: str | None = None


@dataclass
class Catalogue:
    catalogue_id: str
    owner: str
    kind: str
    version: str
    effective_date: str | None
    currency: str
    premium_basis: str
    source_file: str | None = None
    spec_id: str | None = None
    scopes: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    terms: dict = field(default_factory=dict)
    age_band_maps: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    # ---- serialisation ----------------------------------------------------
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=1, ensure_ascii=False, default=_json_default) + "\n"

    def write(self, path: Path):
        Path(path).write_text(self.to_json(), encoding="utf-8", newline="\n")

    def content_hash(self) -> str:
        d = self.to_dict()
        d.pop("meta", None)
        return hashlib.sha256(json.dumps(d, sort_keys=True, default=_json_default).encode()).hexdigest()

    @classmethod
    def from_dict(cls, d: dict) -> "Catalogue":
        scopes = []
        for s in d.get("scopes", []):
            s = dict(s)
            s["plans"] = [Plan(**p) for p in s.get("plans", [])]
            s["components"] = [Component(**c) for c in s.get("components", [])]
            s["formula"] = RatingFormula(**s.get("formula", {}))
            s["benefits"] = [BenefitLine(**b) for b in s.get("benefits", [])]
            scopes.append(RatingScope(**s))
        d = dict(d)
        d["scopes"] = scopes
        d["rules"] = [Rule(**r) for r in d.get("rules", [])]
        return cls(**d)

    @classmethod
    def read(cls, path: Path) -> "Catalogue":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def scope(self, scope_id: str) -> RatingScope:
        for s in self.scopes:
            if s.scope_id == scope_id:
                return s
        raise SpecError(f"catalogue {self.catalogue_id}: unknown scope '{scope_id}'")

    def validate(self):
        if self.kind not in KINDS:
            raise SpecError(f"catalogue kind '{self.kind}' not in {KINDS}")
        if self.premium_basis not in BASES:
            raise SpecError(f"premium_basis '{self.premium_basis}' not in {BASES}")
        ids = set()
        for s in self.scopes:
            if s.scope_id in ids:
                raise SpecError(f"duplicate scope_id {s.scope_id}")
            ids.add(s.scope_id)
            cids = set()
            for c in s.components:
                if c.type not in COMPONENT_TYPES:
                    raise SpecError(f"{s.scope_id}/{c.component_id}: unknown component type {c.type}")
                if c.component_id in cids:
                    raise SpecError(f"{s.scope_id}: duplicate component_id {c.component_id}")
                cids.add(c.component_id)
                if c.type == "MODULE" and c.unit not in MODULE_UNITS:
                    raise SpecError(f"{s.scope_id}/{c.component_id}: MODULE unit must be one of {MODULE_UNITS}")
                if c.premium_basis and c.premium_basis not in BASES:
                    raise SpecError(f"{s.scope_id}/{c.component_id}: premium_basis {c.premium_basis}")
                for r in c.rows:
                    if r.get("status", "VALUE") not in ROW_STATUS:
                        raise SpecError(f"{s.scope_id}/{c.component_id}: row status {r.get('status')}")
            if not s.components_of("BASE_TABLE", "EXPERIENCE_RATED"):
                raise SpecError(f"scope {s.scope_id} has no BASE_TABLE (or EXPERIENCE_RATED) component")
        for r in self.rules:
            if r.type not in RULE_TYPES:
                raise SpecError(f"rule {r.rule_id}: type {r.type} not in {RULE_TYPES}")


def _json_default(o):
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(f"not JSON serialisable: {type(o)}")


def canonical_key_str(key: dict, order: list) -> str:
    """Stable string form of a cell/row key: 'dim=value|dim=lo-hi' in registry order."""
    idx = {c: i for i, c in enumerate(order)}
    parts = []
    for k in sorted(key, key=lambda c: (idx.get(c, 10_000), c)):
        v = key[k]
        if isinstance(v, (list, tuple)):
            v = f"{v[0]}-{v[1]}"
        parts.append(f"{k}={v}")
    return "|".join(parts)
