"""Dimension and benefit registries (SPEC §2, §4.1).

Wildcard semantics: a table row value ``ANY`` matches every cell value (including a missing one).
Hierarchies: a row value equal to a parent group (e.g. PRINCIPAL) matches every child value.
Age is single-year canonical; source bands are mapped to inclusive [lo, hi] ranges.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import REPO_DIR, MappingRequired, SpecError

REGISTRY_DIR = REPO_DIR / "registry"
ANY = "ANY"
RANGE_TYPES = ("numeric-range",)


@dataclass(frozen=True)
class Dimension:
    code: str
    type: str
    values: tuple | None          # None when dynamic
    hierarchy: dict
    parents: tuple
    cell_key: bool
    rng: tuple | None
    exposure_source: str | None

    @property
    def is_range(self) -> bool:
        return self.type in RANGE_TYPES


class Registry:
    def __init__(self, dims_doc: dict, benefits_doc: dict | None = None):
        self.wildcard = dims_doc.get("wildcard", ANY)
        if self.wildcard != ANY:
            raise SpecError("registry wildcard must be 'ANY'")
        self.version = dims_doc.get("version")
        self.dims: dict[str, Dimension] = {}
        for d in dims_doc["dimensions"]:
            vals = d.get("values")
            self.dims[d["code"]] = Dimension(
                code=d["code"], type=d["type"],
                values=None if vals in (None, "dynamic") else tuple(vals),
                hierarchy=dict(d.get("hierarchy") or {}),
                parents=tuple(d.get("parents") or ()),
                cell_key=bool(d.get("cell_key", True)),
                rng=tuple(d["range"]) if d.get("range") else None,
                exposure_source=d.get("exposure_source"))
        self.order = [c for c, d in self.dims.items() if d.cell_key]
        self.benefits = {}
        if benefits_doc:
            for line in benefits_doc["lines"]:
                self.benefits[line["code"]] = line

    # ---- dimension helpers -------------------------------------------------
    def dim(self, code: str) -> Dimension:
        try:
            return self.dims[code]
        except KeyError:
            raise SpecError(f"unknown dimension '{code}' (not in registry/dimensions.json)") from None

    def is_range(self, code: str) -> bool:
        return self.dim(code).is_range

    def parent_of(self, code: str, value):
        return self.dim(code).hierarchy.get(value)

    def hierarchical_dims(self) -> list[str]:
        return [c for c, d in self.dims.items() if d.hierarchy]

    def check_value(self, code: str, value, allow_any: bool = True, allow_parent: bool = True):
        """Validate a categorical value against the registry (dynamic dims accept any string)."""
        d = self.dim(code)
        if value is None:
            return
        if d.is_range:
            return
        if allow_any and value == ANY:
            return
        if allow_parent and value in d.parents:
            return
        if d.values is not None and value not in d.values:
            raise MappingRequired(f"value '{value}' is not registered for dimension '{code}'",
                                  [{"dim": code, "value": value}])

    def sort_dims(self, dims) -> list[str]:
        idx = {c: i for i, c in enumerate(self.order)}
        return sorted(dims, key=lambda c: (idx.get(c, 10_000), c))

    def check_benefit(self, code: str):
        if code not in self.benefits:
            raise MappingRequired(f"benefit code '{code}' is not in registry/benefits.json",
                                  [{"benefit_code": code}])


@lru_cache(maxsize=4)
def _load(path_dims: str, path_ben: str) -> Registry:
    dims = json.loads(Path(path_dims).read_text(encoding="utf-8"))
    ben = json.loads(Path(path_ben).read_text(encoding="utf-8")) if Path(path_ben).exists() else None
    return Registry(dims, ben)


def load_registry(registry_dir: Path | None = None) -> Registry:
    rd = Path(registry_dir) if registry_dir else REGISTRY_DIR
    return _load(str(rd / "dimensions.json"), str(rd / "benefits.json"))


# ---- age / numeric bands ---------------------------------------------------------
_BAND_RE = [
    (re.compile(r"^\s*(\d{1,3})\s*(?:-|–|—|to)\s*(\d{1,3})\s*$", re.I), lambda m: (int(m[1]), int(m[2]))),
    (re.compile(r"^\s*(\d{1,3})\s*\+\s*$"), lambda m: (int(m[1]), None)),
    (re.compile(r"^\s*(\d{1,3})\s*$"), lambda m: (int(m[1]), int(m[1]))),
]


def parse_band_label(label, open_max: int = 120):
    """Generic band parser: 'a-b', 'a–b', 'a to b', 'a+', 'a'. Anything else -> MappingRequired."""
    s = str(label)
    for rx, fn in _BAND_RE:
        m = rx.match(s)
        if m:
            lo, hi = fn(m)
            return lo, (open_max if hi is None else hi)
    raise MappingRequired(f"age/numeric band label '{label}' cannot be parsed; declare it in the spec's band map",
                          [{"band_label": s}])


@dataclass(frozen=True)
class BandMap:
    name: str
    bands: tuple   # ((label, lo, hi), ...)

    @classmethod
    def from_spec(cls, name: str, spec, open_max: int = 120) -> "BandMap":
        """spec: {"label": [lo, hi], ...} | [[label, lo, hi], ...] | {"parse": [labels...]}"""
        out = []
        if isinstance(spec, dict) and "parse" in spec:
            for lab in spec["parse"]:
                lo, hi = parse_band_label(lab, spec.get("open_max", open_max))
                out.append((str(lab), lo, hi))
        elif isinstance(spec, dict):
            for lab, rng in spec.items():
                out.append((str(lab), int(rng[0]), int(rng[1])))
        else:
            for lab, lo, hi in spec:
                out.append((str(lab), int(lo), int(hi)))
        bm = cls(name, tuple(out))
        bm.validate()
        return bm

    def validate(self):
        seen = sorted(self.bands, key=lambda b: (b[1], b[2]))
        for (la, lo_a, hi_a), (lb, lo_b, hi_b) in zip(seen, seen[1:]):
            if lo_b <= hi_a:
                raise SpecError(f"band map '{self.name}': bands '{la}' and '{lb}' overlap")
        for lab, lo, hi in self.bands:
            if lo > hi:
                raise SpecError(f"band map '{self.name}': band '{lab}' has lo > hi")

    def range_of(self, label):
        for lab, lo, hi in self.bands:
            if lab == str(label):
                return lo, hi
        raise MappingRequired(f"band label '{label}' not in band map '{self.name}'",
                              [{"band_map": self.name, "label": str(label)}])

    def label_of(self, value: int):
        for lab, lo, hi in self.bands:
            if lo <= value <= hi:
                return lab
        return None
