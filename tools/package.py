"""Build a release zip of the workbench.   py tools\\package.py [--out <zip>] [--check-bundle]

Release (default): pricing-workbench-<version>/ with the code, registry, contracts, specs, synthetic fixtures, tests,
tools and docs, plus RELEASE.json (version, commit, exclusions) and COMMIT.txt in that folder and RUN_LAPTOP_CHECK.bat
at the zip root. Install notes: docs/INSTALL.md. The version is pw.__version__ (single source).

--check-bundle: the laptop-acceptance bundle for the GC work laptop (SPEC §13): release contents plus the
structure-only examples/ (the cedant example checks need them), COMMIT.txt and RUN_LAPTOP_CHECK.bat at the root.
reference/ is excluded in both modes. Unzip on the work laptop and double-click RUN_LAPTOP_CHECK.bat.

Always excluded: reference/ (temporary GC material, CLAUDE.md data boundary), runs/, out/, VCS and cache folders.
Also excluded: examples/ufic_2027/ (client-derived structure; CLAUDE.md: never in releases) - the template spec is
supplied in the run folder instead. Deterministic: sorted entries, fixed timestamps.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

EXCLUDE_DIRS = {"reference", "runs", "out", ".git", "__pycache__", ".venv", ".pytest_cache"}
EXCLUDE_PATHS = {("examples", "ufic_2027")}
EXCLUDE_SUFFIX = {".pyc", ".parquet", ".tmp"}
EXCLUDE_NAMES = {"RELEASE.json", "COMMIT.txt"}          # written fresh into every package


def included(rel: Path, check_bundle: bool = False) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS or p.startswith(".venv") for p in parts):
        return False
    if not check_bundle and any(tuple(parts[:len(x)]) == x for x in EXCLUDE_PATHS):
        return False
    if rel.suffix in EXCLUDE_SUFFIX or rel.name.startswith("~$") or (len(parts) == 1 and rel.name in EXCLUDE_NAMES):
        return False
    return True


def _commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True).stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def build(out: Path, check_bundle: bool = False) -> list[str]:
    from pw import __version__
    names = []
    files = sorted(p for p in REPO.rglob("*") if p.is_file() and included(p.relative_to(REPO), check_bundle))
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
        commit = _commit()
        info = {"name": "pricing-workbench", "version": __version__, "commit": commit,
                "mode": "check-bundle" if check_bundle else "release",
                "excluded": sorted(EXCLUDE_DIRS) + ([] if check_bundle else ["/".join(x) for x in sorted(EXCLUDE_PATHS)]),
                "python": "CPython 3.12 64-bit (Windows)", "requirements": "requirements-native.txt"}
        extra = {f"pricing-workbench-{__version__}/COMMIT.txt": (commit + "\n").encode(),
                 f"pricing-workbench-{__version__}/RELEASE.json": (json.dumps(info, indent=1, sort_keys=True) + "\n").encode(),
                 "RUN_LAPTOP_CHECK.bat": (HERE / "RUN_LAPTOP_CHECK.bat").read_bytes()}
        if True:
            for arc, data in extra.items():
                zi = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o644 << 16
                z.writestr(zi, data)
                names.append(arc)
    return names


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "out" / "pricing-workbench.zip"))
    ap.add_argument("--check-bundle", action="store_true")
    a = ap.parse_args(argv)
    names = build(Path(a.out), a.check_bundle)
    from pw import __version__
    print(f"{a.out}: {len(names)} files (pricing-workbench {__version__}, {'check bundle' if a.check_bundle else 'release'})")


if __name__ == "__main__":
    main()
