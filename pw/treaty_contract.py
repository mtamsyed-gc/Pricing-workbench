"""Treaty-tool feed check (WS4 deliverable 3): TreatyFeed and OptionTerms as written to runs/<RunID>/out are checked
against the pinned contract contracts/treaty_feed_contract.json (columns in order, types, nulls, finiteness, key
uniqueness) in both the Parquet file and its Excel view. The target treatymodel version is
contracts/treatymodel_version.txt. The treaty tool itself is never edited here (SPEC §5.1)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from . import REPO_DIR

CONTRACT_PATH = REPO_DIR / "contracts" / "treaty_feed_contract.json"
VERSION_PATH = REPO_DIR / "contracts" / "treatymodel_version.txt"


def load_contract(path: Path | None = None) -> dict:
    return json.loads(Path(path or CONTRACT_PATH).read_text(encoding="utf-8"))


def _type_ok(t: pa.DataType, want: str) -> bool:
    if want == "string":
        return pa.types.is_string(t) or pa.types.is_large_string(t) or pa.types.is_null(t)
    if want == "float":
        return pa.types.is_floating(t) or pa.types.is_integer(t)
    raise ValueError(f"unknown contract type {want!r}")


def check_table(name: str, out_dir: Path, spec: dict) -> list[str]:
    probs = []
    pq_path, xl_path = Path(out_dir) / f"{name}.parquet", Path(out_dir) / f"{name}.xlsx"
    if not pq_path.exists():
        return [f"{name}: {pq_path.name} missing"]
    tab = pq.read_table(pq_path)
    cols = tab.column_names
    want = [c["name"] for c in spec["columns"]]
    if cols[:len(want)] != want:
        probs.append(f"{name}: columns {cols[:len(want)]} != contract {want}")
    extra = [c for c in cols[len(want):] if c not in spec.get("extra_columns_allowed", [])]
    if extra:
        probs.append(f"{name}: columns not in the contract {extra}")
    for c in spec["columns"]:
        if c["name"] not in cols:
            continue
        col = tab.column(c["name"])
        if not _type_ok(col.type, c["type"]):
            probs.append(f"{name}.{c['name']}: type {col.type} is not {c['type']}")
            continue
        vals = col.to_pylist()
        if not c.get("nullable", True) and any(v is None for v in vals):
            probs.append(f"{name}.{c['name']}: {sum(v is None for v in vals)} null value(s)")
        if c.get("finite") and any(v is not None and not math.isfinite(v) for v in vals):
            probs.append(f"{name}.{c['name']}: non-finite value(s)")
    key = [k for k in spec.get("key", []) if k in cols]
    if key:
        rows = list(zip(*[tab.column(k).to_pylist() for k in key]))
        if len(rows) != len(set(rows)):
            probs.append(f"{name}: duplicate key rows on {key}")
    if xl_path.exists():
        from openpyxl import load_workbook
        wb = load_workbook(xl_path, read_only=True)
        try:
            hdr = [c for c in next(wb.worksheets[0].iter_rows(min_row=1, max_row=1, values_only=True))]
            n = wb.worksheets[0].max_row - 1
        finally:
            wb.close()
        if [h for h in hdr if h is not None] != cols:
            probs.append(f"{name}: Excel view header differs from the Parquet columns")
        if n != tab.num_rows and tab.num_rows:
            probs.append(f"{name}: Excel view has {n} rows, Parquet {tab.num_rows}")
    else:
        probs.append(f"{name}: Excel view {xl_path.name} missing")
    return probs


def check_treaty_outputs(out_dir: Path, contract_path: Path | None = None) -> dict:
    c = load_contract(contract_path)
    probs = []
    for name, spec in sorted(c["tables"].items()):
        probs += check_table(name, out_dir, spec)
    target = VERSION_PATH.read_text(encoding="utf-8").splitlines()[0].strip() if VERSION_PATH.exists() else None
    warns = []
    slots = ((c.get("treatymodel_findings") or {}).get("inputs") or {}).get("slots") or {}
    tf_p = Path(out_dir) / "TreatyFeed.parquet"
    if slots and tf_p.exists():
        tf = pq.read_table(tf_p, columns=["option_id", "treaty_book"]).to_pydict()
        nb, no = len(set(tf["treaty_book"])), len(set(tf["option_id"]))
        if nb > slots.get("books", nb):
            warns.append(f"{nb} treaty books > {slots['books']} book slots of the treaty tool")
        if no > slots.get("reinsurers", no):
            warns.append(f"{no} options > {slots['reinsurers']} reinsurer slots of the treaty tool")
    return {"status": "PASS" if not probs else "FAIL", "problems": probs, "warnings": warns, "treatymodel_target": target,
            "treatymodel_verified": bool(c.get("treatymodel_verified")),
            "note": None if c.get("treatymodel_verified") else c.get("treatymodel_note")}
