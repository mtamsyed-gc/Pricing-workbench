"""Plain-Python test runner:  py tests\\run_all.py [-k substring] [-q]

Discovers tests/test_*.py, runs every function named test_*, prints a summary, exits non-zero on failure.
"""
from __future__ import annotations

import importlib.util
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sel = None
    if "-k" in argv:
        sel = argv[argv.index("-k") + 1]
    quiet = "-q" in argv
    passed, failed = 0, []
    t0 = time.time()
    for f in sorted(HERE.glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001
            failed.append((f.stem, "import", traceback.format_exc()))
            print(f"E {f.stem} (import)")
            continue
        for name in sorted(n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))):
            full = f"{f.stem}.{name}"
            if sel and sel not in full:
                continue
            t = time.time()
            try:
                getattr(mod, name)()
                passed += 1
                if not quiet:
                    print(f"ok   {full} ({time.time() - t:.2f}s)")
            except Exception:  # noqa: BLE001
                failed.append((f.stem, name, traceback.format_exc()))
                print(f"FAIL {full}")
    print(f"\n{passed} passed, {len(failed)} failed in {time.time() - t0:.1f}s")
    for mod, name, tb in failed:
        print(f"\n--- {mod}.{name}\n{tb}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
