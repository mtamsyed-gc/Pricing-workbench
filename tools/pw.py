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
  t cedant <template_spec.json> --out <xlsx>                     cedant rate workbook (SPEC §8.5): GC fills current rates
  t cedant-read <filled.xlsx> --spec <template_spec.json> --out runs\\<RunID>\\expiring.json [--id ID] [--owner NAME]
                                                                 read back into the EXPIRING catalogue (gated; report beside --out)
  t spec-builder [<template_spec.json>] --out <builder.xlsx> [--blank-if-missing]
                                   Spec Builder workbook (SPEC §8.6): the spec in Excel (blank without a spec)
  t spec-read <builder.xlsx> --out <template_spec.json> [--base <template_spec.json>]
                                   read the builder back into the spec (gated; report beside --out; the old --out
                                   is kept as <name>.previous.json)
  run <run_config.json> [--runs-root <dir>] [--hashes <json>]
                                   end-to-end run (WS4): catalogue specs (V1, V2) -> exposure (V0, coverage) -> V3 ->
                                   V4 -> submissions (T ingest, V5) -> B1 / B2 / TreatyFeed (treaty contract) -> A -> D;
                                   every gate in runs/<RunID>/run_manifest.json; exit 2 when a gate stops the run
  index <run_config.json>          B1 + B2: RateFactors, RateIndex (+ sensitivities), TreatyFeed, OptionTerms
  benefit <run_config.json>        B1 level 1 only: BenefitDiff, BenefitFactors
  benchmark <run_config.json>      A market benchmark: ValueMap, GapRegister, TaxonomyReconciliation
  score <run_config.json>          D scorecard: ScoreInputs, Scorecard, Ranking, weight sensitivity, recommendation pack
  tender new <folder> [--training]  a tender folder (WS8): the four step files, README and input folders; --training
                                   fills it with the synthetic training tender
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
    elif a.action == "cedant":
        from pw.template.cedant import generate_cedant_workbook
        g = generate_cedant_workbook(load_template_spec(Path(a.spec)), _out(a.out, "cedant_workbook.xlsx"))
        c = g.counts
        print(f"{g.path}: {c['RATE']} rate cells, {g.n_refer} refer cells, {c['Factors']} factor rows, {c['Riders']} rider rows, "
              f"{c['Plan defaults']} plan defaults, {c['Benefits']} benefit rows; structure hash {g.structure_hash}")
    elif a.action == "cedant-read":
        from pw.template.cedant import read_cedant
        spec = load_template_spec(Path(a.spec_file))
        out = _out(a.out, "expiring.json")
        cat, rep = read_cedant(Path(a.spec), spec, catalogue_id=a.id, owner=a.owner)
        rp = out.with_name(out.stem + "_read_report.csv")
        rep.to_frame().to_csv(rp, index=False, lineterminator="\n")
        print(rep.summary())
        for p in rep.problems[:40]:
            print(f"  {p['sheet']}!{p['cell']}  [{p['check']}] {p['message']}" + (f"  (value: {p['value']})" if p["value"] else ""))
        if len(rep.problems) > 40:
            print(f"  ... {len(rep.problems) - 40} more: see {rp}")
        print(f"report: {rp}")
        if cat is None:
            if out.exists():
                out.unlink()                           # never leave a stale catalogue beside a failed read
            raise SystemExit(2)
        cat.write(out)
        print(f"{cat.catalogue_id} ({cat.kind}): {len(cat.scopes)} scope(s) -> {out}")
    elif a.action == "spec-builder":
        from pw.template.builder import generate_builder
        src = Path(a.spec) if a.spec else None
        if src is not None and not src.exists():
            if not a.blank_if_missing:
                raise SystemExit(f"{src} not found (use --blank-if-missing for a blank builder)")
            print(f"{src} not found: making a blank builder")
            src = None
        g = generate_builder(load_template_spec(src) if src else None, _out(a.out, "spec_builder.xlsx"))
        kind = f"pre-filled from {src.name}" if src else "blank"
        print(f"{g.path}: Spec Builder ({kind}); " + ", ".join(f"{k} {v}" for k, v in g.counts.items() if v)
              + (f"; kept from the spec, not shown: {len(g.not_carried)} field(s)" if g.not_carried else ""))
    elif a.action == "spec-read":
        from pw.template.builder import read_builder, write_spec
        out = _out(a.out, "template_spec.json")
        base = None
        if a.base and Path(a.base).exists():
            base = load_template_spec(Path(a.base))
        elif a.base:
            print(f"{a.base} not found: reading without a base spec (a new spec)")
        prev_p = out.with_name(out.stem + ".previous" + out.suffix)
        prev = load_template_spec(prev_p) if base is not None and prev_p.exists() else None
        try:
            spec, rep = read_builder(Path(a.spec), base, prev)
        except Exception:  # noqa: BLE001  (an unreadable previous spec must not block the read)
            spec, rep = read_builder(Path(a.spec), base)
        if spec is not None and spec.get("age_bands_file"):
            bdir = Path(spec.get("_base_dir") or ".")
            if (out.parent.resolve() != bdir.resolve() and not (out.parent / spec["age_bands_file"]).exists()):
                rep.add("", "", "age_bands_file", f"the spec names {spec['age_bands_file']}: copy it next to {out} first")
                spec = None
        rp = out.with_name(out.stem + "_read_report.csv")
        rep.to_frame().to_csv(rp, index=False, lineterminator="\n")
        print(rep.summary())
        for p in rep.problems[:40]:
            print(f"  {p['sheet']}!{p['cell']}  [{p['check']}] {p['message']}" + (f"  (value: {p['value']})" if p["value"] else ""))
        if len(rep.problems) > 40:
            print(f"  ... {len(rep.problems) - 40} more: see {rp}")
        for w in rep.warnings[:20]:
            print(f"  warning: {w}")
        print(f"report: {rp}")
        if spec is None:
            raise SystemExit(2)                       # the spec on disk is left untouched
        if out.exists():
            prev_p.write_bytes(out.read_bytes())
            print(f"previous spec kept as {prev_p}")
        write_spec(spec, out)
        print(f"{spec['tender_id']}: {len(spec['sheets'])} sheet(s) -> {out}")
    elif a.action == "parse":
        from pw.template.parser import parse_submission, to_catalogue
        spec = load_template_spec(Path(a.spec_file))
        parsed = parse_submission(Path(a.spec), template_spec=spec)
        exp = load_catalogue(a.expiring) if a.expiring else None
        cat = to_catalogue(parsed, spec, catalogue_id=a.id or Path(a.spec).stem, owner=a.owner or "UNKNOWN", expiring=exp)
        out = _out(a.out, f"{cat.catalogue_id}.json")
        cat.write(out)
        print(f"parsed {len(parsed.values)} values (hash_ok={parsed.hash_ok}, {len(parsed.warnings)} warnings) -> {out}")


def cmd_run(a):
    from pw.pipeline import output_hashes, run_all
    from pw.rate_index import load_run_config
    r = run_all(load_run_config(a.run_config), Path(a.runs_root) if a.runs_root else None)
    g = r["gates"]
    print("gates: " + "; ".join(f"{k} {v['status']}" if "status" in v else
                                f"{k} " + ", ".join(f"{i} {x['status']}" for i, x in sorted(v.items()))
                                for k, v in sorted(g.items())))
    if a.hashes:
        h = output_hashes(r["dir"])
        hp = Path(a.hashes)
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(json.dumps(h, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"{len(h)} output file hashes -> {hp}")
    print(f"RUN {r['status']}: {r['dir']} (manifest: run_manifest.json)")
    if r["status"] != "COMPLETE":
        sys.exit(2)


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
        print(f"treaty tool scenarios: {r['dir'] / 'out' / 'TreatyScenarios.json'}")


def cmd_benefit(a):
    from pw.rate_index import load_run_config, run_benefit
    cfg = load_run_config(a.run_config)
    bd, bf = run_benefit(cfg, Path(a.runs_root) if a.runs_root else None)
    print(f"BenefitDiff {len(bd)} rows ({int((bd['status'] == 'MANUAL_REVIEW').sum())} MANUAL_REVIEW); "
          f"BenefitFactors {len(bf)} rows")
    print(bf.groupby("option_id")["ratio"].agg(["min", "max", "count"]).to_string())


def cmd_score(a):
    from pw.rate_index import load_run_config
    from pw.scorecard import run_scorecard
    r = run_scorecard(load_run_config(a.run_config), Path(a.runs_root) if a.runs_root else None)
    print(r["Ranking"].to_string(index=False))
    if len(r["Flips"]):
        print("nearest ranking flips:")
        print(r["Flips"].head(5).to_string(index=False))
    print(f"recommendation pack: {r['pack']}")


def cmd_benchmark(a):
    from pw.benchmark import run_benchmark
    from pw.rate_index import load_run_config
    r = run_benchmark(load_run_config(a.run_config), Path(a.runs_root) if a.runs_root else None)
    vm = r["ValueMap"]
    print(f"{len(r['market'])} market catalogues, {len(r['subjects'])} subjects; outputs in {r['dir'] / 'out'}")
    cols = ["tier", "role", "catalogue_id", "plan", "price_standard", "ratio_to_median_standard", "richness", "richness_status", "status"]
    print(vm[cols].to_string(index=False))
    g = r["GapRegister"]
    if len(g):
        print(g["assessment"].value_counts().to_string())


def cmd_tender(a):
    from pw.tender_kit import write_folder
    files = write_folder(Path(a.folder), training=a.training)
    kind = "training tender (synthetic)" if a.training else "blank tender folder"
    print(f"{kind}: {len(files)} files -> {Path(a.folder).resolve()}")
    print("Keep it next to the pricing-workbench-<version> folder and double-click the step files in order.")


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
    p.add_argument("action", choices=["generate", "parse", "ingest", "cedant", "cedant-read", "spec-builder", "spec-read"])
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
    p.add_argument("--base")
    p.add_argument("--blank-if-missing", action="store_true")
    p.set_defaults(fn=cmd_t)
    p = sub.add_parser("run")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.add_argument("--hashes")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("index")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_index)
    p = sub.add_parser("benefit")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_benefit)
    p = sub.add_parser("benchmark")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_benchmark)
    p = sub.add_parser("score")
    p.add_argument("run_config")
    p.add_argument("--runs-root")
    p.set_defaults(fn=cmd_score)
    p = sub.add_parser("tender")
    p.add_argument("action", choices=["new"])
    p.add_argument("folder")
    p.add_argument("--training", action="store_true")
    p.set_defaults(fn=cmd_tender)
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
