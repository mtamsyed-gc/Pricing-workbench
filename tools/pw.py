"""Pricing Workbench CLI.   py tools\\pw.py <command> ...

  catalogue parse <spec.json> [--source <xlsx>] [--out <catalogue.json>]
  evaluate <catalogue|spec> <cells.csv> [--out prices.csv] [--trace trace.csv] [--fill default|reference] [--run-config run.json]
  exposure build <dim_life> --maps <dir> [--manifest <csv>] [--snapshot YYYY-MM-DD] [--uwy N] [--catalogue <cat|spec>] [--out <dir>]
  gates v0 <dim_life> [--manifest <csv>] [--version V]
  gates v1 <spec.json>
  gates v2 <spec.json|catalogue> [--out v2.csv]
  gates v3 <catalogue|spec> <dim_life> --maps <dir> [--manifest <csv>] [--out v3.csv]
  gates v4 <template_spec.json> [--expiring <catalogue|spec>] [--workdir <dir>]
  t generate <template_spec.json> --out <xlsx> [--expiring <catalogue|spec>]
  t generate --from-catalogue <catalogue|spec> --tender <tender.json> [--select s1,s2] --out-spec <json> --out <xlsx>
  t parse <submission.xlsx> --spec <template_spec.json> [--expiring <catalogue|spec>] [--id ID] [--owner NAME] --out <catalogue.json>
  t ingest <submission.xlsx> --spec <template_spec.json> --issued <template.xlsx> --run <run_config.json> --id ID --owner NAME
  index <run_config.json>          B1 + B2: RateFactors, RateIndex (+ sensitivities), TreatyFeed, OptionTerms
  benefit <run_config.json>        B1 level 1 only: BenefitDiff, BenefitFactors
  fixtures build

Paths are resolved from this script's location for repo resources; arguments are taken as given (or relative to
the current directory). Run outputs default to <repo>/runs/adhoc/ (never committed).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from pw import PWError  # noqa: E402
from pw.model import Catalogue  # noqa: E402

RUNS = REPO / "runs" / "adhoc"


def load_catalogue(path: str) -> Catalogue:
    p = Path(path)
    d = json.loads(p.read_text(encoding="utf-8"))
    if "catalogue_id" in d:
        return Catalogue.from_dict(d)
    from pw.spec_parser import parse_catalogue
    return parse_catalogue(p)


def run_config(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def _out(path: str | None, default: str) -> Path:
    p = Path(path) if path else RUNS / default
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _print(obj):
    print(json.dumps(obj, indent=1, default=str, ensure_ascii=False))


def cmd_catalogue(a):
    from pw.spec_parser import parse_catalogue
    cat = parse_catalogue(Path(a.spec), source_file=Path(a.source) if a.source else None)
    out = _out(a.out, f"{cat.catalogue_id}.json")
    cat.write(out)
    print(f"{cat.catalogue_id}: {len(cat.scopes)} scope(s) -> {out}")


def cmd_evaluate(a):
    from pw.evaluator import evaluate
    cat = load_catalogue(a.catalogue)
    cells = pd.read_csv(a.cells, dtype=str, keep_default_na=False).replace("", None)
    for c in ("age", "entry_age", "group_size_band", "cell_id"):
        if c in cells.columns:
            cells[c] = pd.to_numeric(cells[c])
    opts = {**run_config(a.run_config), "fill": a.fill, "trace": bool(a.trace)}
    res, tr = evaluate(cat, cells, opts)
    out = _out(a.out, "prices.csv")
    res.to_csv(out, index=False, lineterminator="\n")
    if a.trace:
        tr.to_csv(_out(a.trace, "trace.csv"), index=False, lineterminator="\n")
    print(res["status"].value_counts().to_string())


def cmd_exposure(a):
    from pw.exposure import build_exposure, coverage_report
    ex = build_exposure(Path(a.dim_life), Path(a.maps), Path(a.manifest) if a.manifest else None,
                        snapshot_date=a.snapshot, uwy=a.uwy, strict=a.catalogue is None)
    od = Path(a.out) if a.out else RUNS / "exposure"
    od.mkdir(parents=True, exist_ok=True)
    ex.cells.to_csv(od / "exposure_cells.csv", index=False, lineterminator="\n")
    print(f"V0 {ex.v0['status']}; {len(ex.cells)} cells; {len(ex.unmapped)} unmapped group(s)")
    if a.catalogue:
        rep = coverage_report(load_catalogue(a.catalogue), ex, raise_on_fail=False)
        rep["by_status"].to_csv(od / "coverage_by_status.csv", index=False, lineterminator="\n")
        rep["by_reason"].to_csv(od / "coverage_by_reason.csv", index=False, lineterminator="\n")
        print(f"coverage {rep['status']}: matched {rep['matched_share']:.2%} of premium (gate {rep['threshold']:.0%})")
        print(rep["by_status"].to_string(index=False))
        if rep["status"] != "PASS":
            sys.exit(2)


def cmd_gates(a):
    from pw import gates
    if a.gate == "v0":
        from pw.exposure import read_manifest
        r = gates.v0_contract(Path(a.args[0]), read_manifest(Path(a.manifest)) if a.manifest else None, a.version)
        _print(r)
        sys.exit(0 if r["status"] != "STOP" else 2)
    if a.gate == "v1":
        from pw.spec_parser import load_spec, parse_catalogue
        spec_p = Path(a.args[0])
        cat = parse_catalogue(spec_p)
        src = (spec_p.resolve().parent / load_spec(spec_p)["source_file"]).resolve()
        r = gates.v1_source_reproduction(cat, src, raise_on_fail=False)
        print(f"V1 {r['status']}: {r['checked']} checks over {r['source_cells']} source cells")
        for f in r["failures"][:20]:
            print("  ", f)
        sys.exit(0 if r["status"] == "PASS" else 2)
    if a.gate == "v2":
        df = gates.v2_block_consistency(load_catalogue(a.args[0]))
        out = _out(a.out, "v2.csv")
        df.to_csv(out, index=False, lineterminator="\n")
        print(f"V2: {int(df['flagged'].sum()) if len(df) else 0} flagged of {len(df)} block cells -> {out}")
        if len(df):
            print(df[df["flagged"]][["scope_id", "level", "cell_key", "source_value", "expected_value"]].to_string(index=False))
    if a.gate == "v3":
        from pw.exposure import build_exposure
        cat = load_catalogue(a.args[0])
        ex = build_exposure(Path(a.args[1]), Path(a.maps), Path(a.manifest) if a.manifest else None, strict=False)
        df = gates.v3_premium_reconciliation(cat, ex.cells)
        out = _out(a.out, "v3.csv")
        df.to_csv(out, index=False, lineterminator="\n")
        print(df.to_string(index=False))
    if a.gate == "v4":
        from pw.template.spec import load_template_spec
        exp = load_catalogue(a.expiring) if a.expiring else None
        r = gates.v4_round_trip(load_template_spec(Path(a.args[0])), Path(a.workdir) if a.workdir else RUNS / "v4", exp)
        print(f"V4 {r['status']}: {r['cells']} cells, hash {r['structure_hash'][:16]}")


def cmd_t(a):
    from pw.template.generator import generate_template
    from pw.template.spec import load_template_spec, spec_from_catalogue
    if a.action == "generate":
        exp = load_catalogue(a.expiring) if a.expiring else None
        if a.from_catalogue:
            cat = load_catalogue(a.from_catalogue)
            tender = json.loads(Path(a.tender).read_text(encoding="utf-8"))
            spec = spec_from_catalogue(cat, tender, a.select.split(",") if a.select else None)
            sp = _out(a.out_spec, "template_spec.json")
            sp.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            exp = exp or cat
        else:
            spec = load_template_spec(Path(a.spec))
        g = generate_template(spec, _out(a.out, "template.xlsx"), expiring=exp)
        print(f"{g.path}: {g.n_inputs} input cells, {g.n_refer} refer cells, structure hash {g.structure_hash}")
    elif a.action == "ingest":
        from pw.rate_index import load_run_config, load_catalogue_any, _path
        from pw.template.ingest import ingest
        cfg = load_run_config(a.run)
        spec = load_template_spec(Path(a.spec_file))
        exp = load_catalogue_any(a.expiring) if a.expiring else load_catalogue_any(_path(cfg, cfg["expiring"]))
        band = (cfg.get("v5") or {}).get("outlier_band")
        r = ingest(Path(a.spec), spec, cfg["run_id"], a.id, a.owner or a.id, issued_template=Path(a.issued),
                   expiring=exp, outlier_band=band, runs_root=Path(a.runs_root) if a.runs_root else None)
        e = r["entry"]
        print(f"ingested {a.id}: V5 {e['v5_status']} {e['v5_counts']}; excluded {e['excluded_cells']} of "
              f"{e['rate_cells']} rate cells; registered in run {cfg['run_id']}")
    elif a.action == "parse":
        from pw.template.parser import parse_submission, to_catalogue
        spec = load_template_spec(Path(a.spec_file))
        parsed = parse_submission(Path(a.spec), template_spec=spec)
        exp = load_catalogue(a.expiring) if a.expiring else None
        cat = to_catalogue(parsed, spec, catalogue_id=a.id or Path(a.spec).stem, owner=a.owner or "UNKNOWN", expiring=exp)
        out = _out(a.out, f"{cat.catalogue_id}.json")
        cat.write(out)
        print(f"parsed {len(parsed.values)} values (hash_ok={parsed.hash_ok}, {len(parsed.warnings)} warnings) -> {out}")


def cmd_index(a):
    from pw.rate_index import load_run_config, run_b2
    cfg = load_run_config(a.run_config)
    r = run_b2(cfg, Path(a.runs_root) if a.runs_root else None)
    ri = r["RateIndex"]
    tot = ri[(ri["scenario"] == "STANDARD") & (ri["cut"] == "TOTAL")]
    print(f"coverage {r['coverage']['status']} ({r['coverage']['matched_share']:.2%}); outputs in {r['dir'] / 'out'}")
    print(tot[["option_id", "lives", "index", "index_benefit_adj", "unpriced_share"]].to_string(index=False))
    if r["TreatyFeed"] is not None:
        print(r["TreatyFeed"][["option_id", "treaty_book", "premium_change_pct", "lr_adjustment_pts"]].to_string(index=False))


def cmd_benefit(a):
    from pw.rate_index import load_run_config, run_benefit
    cfg = load_run_config(a.run_config)
    bd, bf = run_benefit(cfg, Path(a.runs_root) if a.runs_root else None)
    print(f"BenefitDiff {len(bd)} rows ({int((bd['status'] == 'MANUAL_REVIEW').sum())} MANUAL_REVIEW); "
          f"BenefitFactors {len(bf)} rows")
    print(bf.groupby("option_id")["ratio"].agg(["min", "max", "count"]).to_string())


def cmd_fixtures(a):
    import subprocess
    for s in ("build_fixtures.py", "build_submissions.py"):
        subprocess.run([sys.executable, str(HERE / s)], check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pw", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("catalogue")
    p.add_argument("action", choices=["parse"])
    p.add_argument("spec")
    p.add_argument("--source")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_catalogue)
    p = sub.add_parser("evaluate")
    p.add_argument("catalogue")
    p.add_argument("cells")
    p.add_argument("--out")
    p.add_argument("--trace")
    p.add_argument("--fill", default="default", choices=["default", "reference"])
    p.add_argument("--run-config")
    p.set_defaults(fn=cmd_evaluate)
    p = sub.add_parser("exposure")
    p.add_argument("action", choices=["build"])
    p.add_argument("dim_life")
    p.add_argument("--maps", required=True)
    p.add_argument("--manifest")
    p.add_argument("--snapshot")
    p.add_argument("--uwy", type=int)
    p.add_argument("--catalogue")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_exposure)
    p = sub.add_parser("gates")
    p.add_argument("gate", choices=["v0", "v1", "v2", "v3", "v4"])
    p.add_argument("args", nargs="+")
    p.add_argument("--manifest")
    p.add_argument("--version")
    p.add_argument("--maps")
    p.add_argument("--out")
    p.add_argument("--expiring")
    p.add_argument("--workdir")
    p.set_defaults(fn=cmd_gates)
    p = sub.add_parser("t")
    p.add_argument("action", choices=["generate", "parse", "ingest"])
    p.add_argument("spec", nargs="?")
    p.add_argument("--out")
    p.add_argument("--expiring")
    p.add_argument("--from-catalogue")
    p.add_argument("--tender")
    p.add_argument("--select")
    p.add_argument("--out-spec")
    p.add_argument("--spec", dest="spec_file")
    p.add_argument("--id")
    p.add_argument("--owner")
    p.add_argument("--issued")
    p.add_argument("--run")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_t)
    p = sub.add_parser("index")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_index)
    p = sub.add_parser("benefit")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_benefit)
    p = sub.add_parser("fixtures")
    p.add_argument("action", choices=["build"])
    p.set_defaults(fn=cmd_fixtures)
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except PWError as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        items = getattr(e, "items", None)
        if items:
            for it in items[:50]:
                print("   ", it, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
