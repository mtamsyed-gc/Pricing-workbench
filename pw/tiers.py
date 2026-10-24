"""Tier matching (SPEC §3.3): catalogue plans -> a canonical tier ladder through tier_map.csv (run input).

tier_map.csv: catalogue_id, plan, tier, weight. catalogue_id or plan may be ANY (most specific row set wins:
exact catalogue + exact plan > exact catalogue + ANY plan > ANY catalogue + exact plan > ANY + ANY).
Many-to-one (several plans -> one tier) and one-to-many (one plan -> several tiers, weights) are allowed; the weights of
one plan's rows must sum to 1. Unmapped plans raise MappingRequired. The ladder (run config 'tier_ladder') orders tiers,
richest first; every tier used must be on it.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import MappingRequired, SpecError
from .registry import ANY

TOL = 1e-9


class TierMap:
    def __init__(self, df: pd.DataFrame, ladder: list):
        need = ["catalogue_id", "plan", "tier", "weight"]
        miss = [c for c in need if c not in df.columns]
        if miss:
            raise SpecError(f"tier_map.csv missing columns {miss}")
        self.ladder = list(ladder or [])
        if not self.ladder or len(set(self.ladder)) != len(self.ladder):
            raise SpecError("tier_ladder must be a non-empty list of distinct tiers")
        df = df.copy()
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
        if df["weight"].isna().any() or (df["weight"] <= 0).any():
            raise SpecError("tier_map weights must be numbers > 0")
        bad = sorted(set(df["tier"]) - set(self.ladder))
        if bad:
            raise SpecError(f"tiers {bad} are not on the tier ladder")
        self.groups = {}
        for (c, p), g in df.groupby(["catalogue_id", "plan"], sort=True):
            if g["tier"].duplicated().any():
                raise SpecError(f"tier_map: duplicate tier for {c} / {p}")
            if abs(g["weight"].sum() - 1.0) > TOL:
                raise SpecError(f"tier_map: weights for {c} / {p} sum to {g['weight'].sum()}, not 1")
            self.groups[(str(c), str(p))] = [(str(t), float(w)) for t, w in zip(g["tier"], g["weight"])]

    @classmethod
    def read(cls, path, ladder):
        return cls(pd.read_csv(Path(path), dtype=str, keep_default_na=False), ladder)

    def tiers(self, catalogue_id: str, plan: str) -> list:
        for key in ((catalogue_id, plan), (catalogue_id, ANY), (ANY, plan), (ANY, ANY)):
            if key in self.groups:
                return self.groups[key]
        raise MappingRequired(f"no tier for {catalogue_id} / {plan} in tier_map.csv",
                              [{"catalogue_id": catalogue_id, "plan": plan}])

    def rank(self, tier: str) -> int:
        return self.ladder.index(tier) + 1
