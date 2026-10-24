"""Shared test helpers (plain Python)."""
from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from openpyxl import load_workbook

REPO = Path(__file__).resolve().parent.parent
FIX = REPO / "fixtures"
CATS = ["CAT_ALPHA", "CAT_BETA", "CAT_GAMMA", "CAT_DELTA", "CAT_RETIREE", "CAT_IPMI"]
TENDER = {"cedant": "FICTIONAL", "deadline": "2026-11-05", "contact": "synthetic", "issue_date": "2026-10-24"}


@lru_cache(maxsize=None)
def catalogue(name: str):
    from pw.spec_parser import parse_catalogue
    return parse_catalogue(FIX / name / "spec.json")


@contextmanager
def tmpdir():
    d = Path(tempfile.mkdtemp(prefix="pw_test_"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc as e:
        return e
    raise AssertionError(f"{fn.__name__} did not raise {exc.__name__}")


def source_value(cat_name: str, key: dict, component_id: str = "base", level=None):
    """Raw source value (read straight from the fixture workbook) for the source cell whose key matches."""
    cat = catalogue(cat_name)
    for e in cat.meta["source_index"]:
        if e["component_id"] != component_id or e["level"] != level:
            continue
        for k in e["keys"]:
            if all(_match(k.get(d), v) for d, v in key.items()) and all(d in key or v == "ANY" for d, v in k.items()):
                sheet, ref = e["ref"].split("!")
                wb = load_workbook(FIX / cat_name / "source.xlsx", data_only=True)
                return wb[sheet][ref].value
    raise KeyError(f"no source cell for {key}")


def _match(row_v, cell_v):
    if isinstance(row_v, list):
        return row_v[0] <= cell_v <= row_v[1]
    return row_v == cell_v


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))
