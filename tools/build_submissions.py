"""Build SUB_X and SUB_Y (SPEC §10): two synthetic reinsurer submissions generated through T from CAT_ALPHA and
filled with perturbed CAT_ALPHA base rates (seeded), then parsed back to SUBMISSION catalogues.
Also C_ALPHA (WS5, SPEC §8.5): the cedant rate workbook authored from CAT_ALPHA's structure, filled from CAT_ALPHA's
values (scripted) and read back into the EXPIRING catalogue (all fictional).

    py tools\\build_submissions.py [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import numpy as np  # noqa: E402

from pw.evaluator import lookup_component  # noqa: E402
from pw.spec_parser import parse_catalogue  # noqa: E402
from pw.template.generator import generate_template  # noqa: E402
from pw.template.parser import fill_template, parse_submission, to_catalogue  # noqa: E402
from pw.template.cedant import fill_from_catalogue, generate_cedant_workbook, read_cedant_workbook  # noqa: E402
from pw.template.spec import cedant_spec_from_catalogue, spec_from_catalogue  # noqa: E402

TENDER = {"cedant": "FICTIONAL_CEDANT_A", "tender_id": "T_ALPHA_2027", "deadline": "2026-11-05",
          "contact": "synthetic contact", "issue_date": "2026-10-24", "effective_date": "2027-01-01"}
SUBS = {"SUB_X": {"seed": 101, "mean": 0.035, "sd": 0.03, "reinsurer": "Reinsurer X (fictional)", "share": "50%"},
        "SUB_Y": {"seed": 202, "mean": -0.015, "sd": 0.05, "reinsurer": "Reinsurer Y (fictional)", "share": "30%"}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "fixtures"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    alpha = parse_catalogue(out / "CAT_ALPHA" / "spec.json")
    spec = spec_from_catalogue(alpha, TENDER)
    tdir = out / "T_ALPHA"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "template_spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    gen = generate_template(spec, tdir / "template.xlsx", expiring=alpha)
    scope = alpha.scopes[0]
    base = next(c for c in scope.components if c.type == "BASE_TABLE")
    for name, p in SUBS.items():
        rng = np.random.default_rng(p["seed"])

        def value_fn(ck, keys, kind, rng=rng, p=p):
            if kind == "TERM":
                fld = ck.split("=", 1)[1]
                return {"reinsurer": p["reinsurer"], "share_by_book": p["share"], "premium_basis": "NET",
                        "commission": "15%", "validity": "2027-12-31"}.get(fld, f"synthetic {fld}")
            k = keys[0]
            probe = {d: (v[0] if isinstance(v, list) else v) for d, v in k.items() if d in base.keys}
            res = lookup_component(alpha, scope.scope_id, base, [probe])
            exp = float(res["__value"].iloc[0])
            return round(exp * (1.0 + float(rng.normal(p["mean"], p["sd"]))), 2)
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        fill_template(tdir / "template.xlsx", d / "submission.xlsx", value_fn=value_fn)
        parsed = parse_submission(d / "submission.xlsx", template_spec=spec)
        cat = to_catalogue(parsed, spec, catalogue_id=name, owner=p["reinsurer"], expiring=alpha)
        cat.write(d / "catalogue.json")
        print(f"{name}: {len(parsed.values)} values, hash_ok={parsed.hash_ok}, structure {gen.structure_hash[:12]}")
    build_c_alpha(out, alpha)


def build_c_alpha(out: Path, alpha):
    d = out / "C_ALPHA"
    d.mkdir(parents=True, exist_ok=True)
    spec = cedant_spec_from_catalogue(alpha, TENDER)
    (d / "template_spec.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    g = generate_cedant_workbook(spec, d / "cedant_workbook.xlsx")
    fill_from_catalogue(d / "cedant_workbook.xlsx", d / "filled.xlsx", alpha)
    cat = read_cedant_workbook(d / "filled.xlsx", spec)
    cat.write(d / "expiring.json")
    print(f"C_ALPHA: {g.n_inputs} inputs, structure {g.structure_hash[:12]}; read back {cat.catalogue_id} ({len(cat.scopes)} scope)")


if __name__ == "__main__":
    main()
