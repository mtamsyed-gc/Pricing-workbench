"""Run folder outputs (SPEC §7): every output table is written as Parquet + an Excel view, and the run manifest
records versions and hashes. Layout: runs/<RunID>/{run_manifest.json, options.json, options/<id>/..., out/<Table>.*}.
Deterministic: rows sorted by the table's key, fixed Parquet/xlsx metadata."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import REPO_DIR, SpecError, __version__
from .io_excel import new_workbook

RUNS_DIR = REPO_DIR / "runs"

# Output contracts (SPEC §7). Leading columns are fixed; "…" columns (cell key / cut dims) are inserted after them.
CONTRACTS = {
    "RateFactors": {"lead": ["option_id"], "dyn": "cell_key", "tail": ["rate_expiring", "rate_option", "factor", "priced_status"]},
    "RateIndex": {"lead": ["option_id"], "dyn": "cut_dims", "tail": ["lives", "prem_expiring", "prem_option", "index", "index_benefit_adj"]},
    "BenefitDiff": {"lead": ["option_id", "plan", "benefit_code"], "dyn": None,
                    "tail": ["expiring_value", "option_value", "direction", "value_factor"]},
    "BenefitFactors": {"lead": ["option_id", "plan"], "dyn": None, "tail": ["richness_expiring", "richness_option", "ratio"]},
    "TreatyFeed": {"lead": ["option_id", "treaty_book"], "dyn": None, "tail": ["premium_change_pct", "lr_adjustment_pts", "basis_note"]},
    "OptionTerms": {"lead": ["option_id"], "dyn": None,
                    "tail": ["reinsurer", "share_by_book", "premium_basis", "commission", "corridor", "cap", "profit_share",
                             "conditions", "validity"]},
}


def run_dir(run_id: str, root: Path | None = None) -> Path:
    if not run_id or any(c in run_id for c in '\\/:*?"<>|'):
        raise SpecError(f"invalid RunID {run_id!r}")
    d = Path(root or RUNS_DIR) / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def check_contract(name: str, df: pd.DataFrame, extra_ok: tuple = ()) -> list[str]:
    """Columns = lead + (dynamic dims) + tail, in that order; extra trailing columns allowed only if listed."""
    c = CONTRACTS[name]
    cols = list(df.columns)
    lead, tail = c["lead"], c["tail"]
    if cols[:len(lead)] != lead:
        raise SpecError(f"{name}: leading columns {cols[:len(lead)]} != {lead}")
    rest = cols[len(lead):]
    extra = [x for x in rest if x in extra_ok]
    rest = [x for x in rest if x not in extra_ok]
    if rest[len(rest) - len(tail):] != tail:
        raise SpecError(f"{name}: trailing columns {rest[len(rest) - len(tail):]} != {tail}")
    dyn = rest[:len(rest) - len(tail)]
    if c["dyn"] is None and dyn:
        raise SpecError(f"{name}: unexpected columns {dyn}")
    return dyn + extra


def _file_hash(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_table(name: str, df: pd.DataFrame, out_dir: Path, sort_by: list | None = None, contract: bool = True,
                extra_ok: tuple = ()) -> dict:
    if contract and name in CONTRACTS:
        check_contract(name, df, extra_ok)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    if sort_by:
        df = df.sort_values(sort_by, kind="stable", na_position="last").reset_index(drop=True)
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and v != v) else
                              (v if isinstance(v, (str, bool, int, float)) else json.dumps(v, sort_keys=True)))
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({"pw_table": name, "pw_version": __version__})
    pq_path = out_dir / f"{name}.parquet"
    pq.write_table(table, pq_path, compression="zstd", write_statistics=False)
    xl_path = out_dir / f"{name}.xlsx"
    wb = new_workbook(xl_path, title=name)
    ws = wb.add_worksheet(name[:31])
    hdr = wb.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
    num = wb.add_format({"num_format": "#,##0.0000"})
    ws.write_row(0, 0, list(df.columns), hdr)
    for i, row in enumerate(df.itertuples(index=False), start=1):
        for j, v in enumerate(row):
            if v is None or (isinstance(v, float) and v != v):
                continue
            if isinstance(v, bool):
                ws.write_boolean(i, j, v)
            elif isinstance(v, (int, float)):
                ws.write_number(i, j, float(v), num)
            else:
                ws.write_string(i, j, str(v))
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns) - 1, 0))
    wb.close()
    return {"table": name, "rows": int(len(df)), "parquet": pq_path.name, "xlsx": xl_path.name,
            "sha256_parquet": _file_hash(pq_path)}


def read_table(name: str, out_dir: Path) -> pd.DataFrame:
    return pq.read_table(Path(out_dir) / f"{name}.parquet").to_pandas()


def update_manifest(rdir: Path, section: str, entry) -> dict:
    """runs/<RunID>/run_manifest.json: versions, inputs/outputs with hashes, gate results. Section values are
    dicts keyed by a stable id so re-running a step replaces its entry."""
    p = Path(rdir) / "run_manifest.json"
    m = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    m.setdefault("versions", {"pricing_workbench": __version__, "python": platform.python_version(),
                              "pandas": pd.__version__, "pyarrow": pa.__version__})
    try:
        import duckdb
        m["versions"]["duckdb"] = duckdb.__version__
    except ImportError:  # pragma: no cover
        pass
    tm = REPO_DIR / "contracts" / "treatymodel_version.txt"
    if tm.exists():
        m["versions"]["treatymodel_target"] = tm.read_text(encoding="utf-8").splitlines()[0].strip()
    m.setdefault(section, {})
    for k, v in entry.items():
        m[section][k] = v
    p.write_text(json.dumps(m, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")
    return m


def load_manifest(rdir: Path) -> dict:
    p = Path(rdir) / "run_manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
