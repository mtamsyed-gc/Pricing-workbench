"""Build a release zip of the workbench.   py tools\\package.py [--out <zip>]

Always excluded: reference/ (temporary GC material, CLAUDE.md data boundary), runs/, out/, VCS and cache folders.
Also excluded: examples/ufic_2027/ (client-derived structure; CLAUDE.md: never in releases) - the template spec is
supplied in the run folder instead. Deterministic: sorted entries, fixed timestamps.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

EXCLUDE_DIRS = {"reference", "runs", "out", ".git", "__pycache__", ".venv", ".pytest_cache"}
EXCLUDE_PATHS = {("examples", "ufic_2027")}
EXCLUDE_SUFFIX = {".pyc", ".parquet", ".tmp"}


def included(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS or p.startswith(".venv") for p in parts):
        return False
    if any(tuple(parts[:len(x)]) == x for x in EXCLUDE_PATHS):
        return False
    if rel.suffix in EXCLUDE_SUFFIX or rel.name.startswith("~$"):
        return False
    return True


def build(out: Path) -> list[str]:
    from pw import __version__
    names = []
    files = sorted(p for p in REPO.rglob("*") if p.is_file() and included(p.relative_to(REPO)))
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(REPO)
            if out.resolve() == p.resolve():
                continue
            arc = f"pricing-workbench-{__version__}/{rel.as_posix()}"
            zi = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, p.read_bytes())
            names.append(arc)
    return names


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "out" / "pricing-workbench.zip"))
    a = ap.parse_args(argv)
    names = build(Path(a.out))
    print(f"{a.out}: {len(names)} files")


if __name__ == "__main__":
    main()
