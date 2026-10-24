"""Import the SME Benchmarking Tool's reference lever basis as a run's market_basis.json (WS2).

    py tools\\import_sme_basis.py <PBM clone>\\sme_benchmarking --out runs\\<RunID>\\market_basis.json

Reads build/taxonomy.py (REF_LEVER, NETS) from the tool at run time and maps levers to factor families through the
intake layout (specs/market/sme_intake_v2_4.json lever_map). The tool labels this basis a SYNTHETIC placeholder: the
output is flagged placeholder=true and the benchmark marks richness as PLACEHOLDER. Output goes to runs/ (never
committed). Levers without a registry dimension (CR #13) are skipped and listed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from pw.market_intake import _opt, load_layout  # noqa: E402


def load_taxonomy(sme_dir: Path):
    p = Path(sme_dir) / "build" / "taxonomy.py"
    if not p.exists():
        raise SystemExit(f"taxonomy.py not found under {sme_dir} (expected <PBM>/sme_benchmarking)")
    spec = importlib.util.spec_from_file_location("sme_taxonomy", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def convert(tax, layout: dict) -> dict:
    entries, skipped = [], []
    for lever, rows in tax.REF_LEVER.items():
        fam = (layout["lever_map"].get(lever) or {}).get("family")
        if not fam:
            skipped.append(lever)
            continue
        for option, per_net in rows:
            for net, v in zip(tax.NETS, per_net):
                entries.append({"family": fam, "option": _opt(option), "network": net, "relativity": float(v)})
    entries.sort(key=lambda e: (e["family"], e["option"], e["network"]))
    return {"_note": "Imported at run time from the SME Benchmarking Tool reference lever basis (labelled SYNTHETIC "
                     "placeholder by the tool). Not a calibrated market library.",
            "source": f"SME tool {getattr(tax, 'TOOL_VERSION', '?')} REF_LEVER", "placeholder": True,
            "skipped_levers": skipped, "entries": entries}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("sme_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--layout")
    a = ap.parse_args(argv)
    d = convert(load_taxonomy(Path(a.sme_dir)), load_layout(a.layout))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{out}: {len(d['entries'])} relativities; skipped levers (no dimension yet): {d['skipped_levers']}")


if __name__ == "__main__":
    main()
