"""Component trace (SPEC §1.7, CLAUDE.md): base x factors + modules + fees, one row per step per cell."""
from __future__ import annotations

import pandas as pd

TRACE_COLUMNS = ["cell_id", "step", "component_id", "type", "family", "option", "matched_key", "value", "running", "note"]


class Trace:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self._parts: list[pd.DataFrame] = []

    def add(self, df: pd.DataFrame):
        """df must carry TRACE_COLUMNS except 'step' (assigned at the end in add order)."""
        if self.enabled and len(df):
            self._parts.append(df.copy())

    def frame(self) -> pd.DataFrame | None:
        if not self.enabled:
            return None
        if not self._parts:
            return pd.DataFrame(columns=TRACE_COLUMNS)
        out = []
        for i, p in enumerate(self._parts):
            p = p.copy()
            p["_order"] = i
            out.append(p)
        df = pd.concat(out, ignore_index=True)
        df = df.sort_values(["cell_id", "_order"], kind="stable").reset_index(drop=True)
        df["step"] = df.groupby("cell_id").cumcount() + 1
        for c in TRACE_COLUMNS:
            if c not in df.columns:
                df[c] = None
        return df[TRACE_COLUMNS]


def format_trace(trace: pd.DataFrame, cell_id) -> str:
    """Human-readable trace of one cell (hand-check aid)."""
    t = trace[trace["cell_id"] == cell_id]
    lines = [f"cell {cell_id}"]
    for r in t.itertuples(index=False):
        opt = f" [{r.option}]" if r.option not in (None, "") and r.option == r.option else ""
        note = f"  ({r.note})" if r.note not in (None, "") and r.note == r.note else ""
        lines.append(f"  {r.step:>2}. {r.type:<14} {r.component_id}{opt}: {r.value} -> {r.running}{note}")
    return "\n".join(lines)
