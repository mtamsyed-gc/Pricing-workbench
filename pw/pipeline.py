"""End-to-end run (WS4): `py tools\\pw.py run <run_config.json>`.

    catalogue specs (parse, V1, V2) -> exposure (V0, coverage gate) -> V3 -> V4 (issued template structure) ->
    submissions (T ingest, V5) -> B1 / B2 (RateFactors, RateIndex, TreatyFeed, OptionTerms) -> A benchmark -> D scorecard

Everything is written to runs/<RunID>/ (or <runs_root>/<RunID>/):
    run_manifest.json          versions, inputs and outputs with hashes, every gate result, run status and steps
    gates/                     gate detail tables (V1 failures, V2 block cells, V3 reconciliation, coverage, V5 flags)
    options.json, options/     the submissions registered by T ingest
    out/                       SPEC §7 tables (Parquet + Excel view), benchmark, scorecard, recommendation pack

The run owns the files it generates: at the start it clears run_manifest.json, options.json, options/, gates/, out/
and v4/ of the run folder (anything else there, e.g. a cedant read-back expiring.json, is left alone), so a run never
mixes with an earlier one and two runs on the same inputs are byte-identical (WS4 acceptance).

Run config sections used here (beside those of index / benchmark / score, see pw.rate_index.load_run_config):
    "submissions": [{"option_id", "owner", "file", "template_spec", "issued"}]   (paths relative to the config)
    "gates": {"v1_catalogues": [spec.json, ...], "coverage_threshold": 0.95, "v4": true}
V1 runs on every spec-sourced catalogue of the run (the expiring, the benchmark's market_catalogues, and any listed in
gates.v1_catalogues); a read-back catalogue (catalogue.json, e.g. from `t cedant-read`) has no source workbook and is
reported NOT_APPLICABLE (its gate is the cedant read report). A stopping gate (V0, V1, coverage, V4) ends the run with
status STOPPED; the manifest is written either way.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from . import GateFailed, PWError, ProposalRequired, __version__

GENERATED = ("run_manifest.json", "options.json", "options", "gates", "out", "v4")


def _is_spec(path: Path) -> bool:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return "catalogue_id" not in d


def _csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")


def _clean(rd: Path):
    for name in GENERATED:
        p = rd / name
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()


def run_all(cfg: dict, runs_root=None, log=print) -> dict:
    """The full synthetic / tender run. Returns {"status", "dir", "gates", "steps", "manifest"}."""
    from .exposure import build_exposure, coverage_report
    from .gates import v1_source_reproduction, v2_block_consistency, v3_premium_reconciliation, v4_round_trip
    from .outputs import load_manifest, run_dir, update_manifest
    from .rate_index import _path, load_catalogue_any, run_b2
    from .spec_parser import load_spec, parse_catalogue

    rd = run_dir(cfg["run_id"], runs_root)
    _clean(rd)
    gdir = rd / "gates"
    gates, steps = {}, []
    gcfg = cfg.get("gates") or {}
    eopts = {**(cfg.get("eval_options") or {}), **({"duckdb": cfg["duckdb"]} if cfg.get("duckdb") else {})}

    def step(name, detail=""):
        steps.append({"step": name, "detail": detail})
        log(f"[{len(steps):2d}] {name}" + (f": {detail}" if detail else ""))

    def finish(status, error=None):
        run = {"status": status, "steps": steps, "pricing_workbench": __version__}
        if error is not None:
            run["error"] = f"{type(error).__name__}: {error}"
        update_manifest(rd, "gates", gates)
        update_manifest(rd, "run", run)
        return {"status": status, "dir": rd, "gates": gates, "steps": steps, "manifest": load_manifest(rd)}

    update_manifest(rd, "inputs", {"files": input_hashes(cfg)})
    try:
        # 1. catalogues: expiring (+ V1 / V2), market catalogue specs (V1)
        exp_path = _path(cfg, cfg["expiring"])
        expiring = load_catalogue_any(exp_path)
        v1_paths = [("expiring", exp_path)]
        for p in (cfg.get("benchmark") or {}).get("market_catalogues", []):
            v1_paths.append(("market", _path(cfg, p)))
        for p in gcfg.get("v1_catalogues", []):
            v1_paths.append(("listed", _path(cfg, p)))
        gates["V1"] = {}
        for role, p in v1_paths:
            if not _is_spec(p):
                cid = json.loads(p.read_text(encoding="utf-8"))["catalogue_id"]
                gates["V1"][cid] = {"status": "NOT_APPLICABLE", "role": role,
                                    "note": "read-back catalogue (no source workbook): gated by its read report"}
                continue
            spec = load_spec(p)
            cat = parse_catalogue(p)
            if not spec.get("source_file"):
                gates["V1"][cat.catalogue_id] = {"status": "NOT_APPLICABLE", "role": role, "note": "spec has no source_file"}
                continue
            r = v1_source_reproduction(cat, (p.parent / spec["source_file"]).resolve(), raise_on_fail=False)
            gates["V1"][cat.catalogue_id] = {"status": r["status"], "role": role, "checked": r["checked"],
                                             "source_cells": r["source_cells"], "failures": len(r["failures"])}
            if r["failures"]:
                _csv(pd.DataFrame({"failure": [str(f) for f in r["failures"]]}), gdir / f"V1_{cat.catalogue_id}.csv")
            if r["status"] != "PASS":
                raise GateFailed("V1", f"{cat.catalogue_id}: {len(r['failures'])} source cell(s) not reproduced")
        step("catalogues + V1", ", ".join(f"{k} {v['status']}" for k, v in sorted(gates["V1"].items())))
        v2 = v2_block_consistency(expiring)
        _csv(v2, gdir / "V2_block_consistency.csv")
        nfl = int(v2["flagged"].sum()) if len(v2) else 0
        gates["V2"] = {"status": "FLAGGED" if nfl else "PASS", "block_cells": int(len(v2)), "flagged": nfl,
                       "catalogue_id": expiring.catalogue_id}
        step("V2 block consistency", f"{nfl} flagged of {len(v2)} block cells")

        # 2. exposure: V0 + coverage gate
        ec = cfg.get("exposure") or {}
        if not ec.get("snapshot_date"):
            raise ProposalRequired("exposure.snapshot_date is required for the standard mix (lives in force, SPEC §5)")
        try:
            ex = build_exposure(_path(cfg, ec["dim_life"]), _path(cfg, ec["maps"]),
                                _path(cfg, ec["manifest"]) if ec.get("manifest") else None,
                                contract_version=ec.get("contract_version"), snapshot_date=ec["snapshot_date"], strict=False)
        except GateFailed as e:
            if e.gate == "V0":
                d = e.details or {}
                gates["V0"] = {"status": "STOP", "missing": d.get("missing"), "messages": d.get("messages")}
            raise
        gates["V0"] = {"status": ex.v0["status"], "version": ex.v0.get("version"), "messages": ex.v0.get("messages")}
        thr = float(gcfg.get("coverage_threshold", 0.95))
        cov = coverage_report(expiring, ex, eopts, threshold=thr, raise_on_fail=False)
        _csv(cov["by_status"], gdir / "coverage_by_status.csv")
        _csv(cov["by_reason"], gdir / "coverage_by_reason.csv")
        gates["COVERAGE"] = {"status": cov["status"], "matched_share": round(float(cov["matched_share"]), 10),
                             "threshold": thr, "measure": cov["measure"], "unmapped_groups": len(ex.unmapped)}
        step("exposure V0 + coverage", f"V0 {ex.v0['status']}; coverage {cov['status']} {cov['matched_share']:.2%}")
        if cov["status"] != "PASS":
            raise GateFailed("COVERAGE", f"matched {cov['matched_share']:.2%} < {thr:.0%} (gates/coverage_by_reason.csv)")

        # 3. V3 premium reconciliation (report)
        v3 = v3_premium_reconciliation(expiring, ex.cells, options=eopts)
        _csv(v3, gdir / "V3_premium_reconciliation.csv")
        tot = v3.iloc[-1]
        imp = tot["implied_factor"]
        gates["V3"] = {"status": "REPORTED", "implied_factor_total": None if pd.isna(imp) else round(float(imp), 10),
                       "actual_prem": round(float(tot["actual_prem"]), 6), "rated_prem": round(float(tot["rated_prem"]), 6)}
        step("V3 premium reconciliation", f"implied factor {gates['V3']['implied_factor_total']}")

        # 4. submissions: V4 on each issued template structure, then T ingest + V5
        subs = cfg.get("submissions") or []
        if not subs:
            raise ProposalRequired("run config has no 'submissions' (option_id, owner, file, template_spec, issued)")
        from .template.ingest import ingest
        from .template.spec import load_template_spec
        gates["V4"], gates["V5"] = {}, {}
        specs = {}
        for s in subs:
            for k in ("option_id", "file", "template_spec", "issued"):
                if not s.get(k):
                    raise ProposalRequired(f"submission {s.get('option_id', '?')}: '{k}' missing in run config")
            sp = _path(cfg, s["template_spec"])
            specs.setdefault(str(sp), load_template_spec(sp))
        if gcfg.get("v4", True):
            for sp, spec in sorted(specs.items()):
                tid = spec.get("tender_id", Path(sp).stem)
                r = v4_round_trip(spec, rd / "v4" / tid, expiring=expiring)
                gates["V4"][tid] = {"status": r["status"], "cells": r["cells"], "structure_hash": r["structure_hash"]}
            step("V4 template round trip", ", ".join(f"{k} {v['status']}" for k, v in sorted(gates["V4"].items())))
        band = (cfg.get("v5") or {}).get("outlier_band")
        for s in sorted(subs, key=lambda x: x["option_id"]):
            r = ingest(_path(cfg, s["file"]), specs[str(_path(cfg, s["template_spec"]))], cfg["run_id"], s["option_id"],
                       s.get("owner") or s["option_id"], issued_template=_path(cfg, s["issued"]), expiring=expiring,
                       outlier_band=band, runs_root=runs_root)
            e = r["entry"]
            gates["V5"][s["option_id"]] = {"status": e["v5_status"], "counts": e["v5_counts"],
                                           "excluded_cells": e["excluded_cells"], "rate_cells": e["rate_cells"],
                                           "hash_ok": r["v5"]["hash_ok"]}
        step("T ingest + V5", ", ".join(f"{k} {v['status']}" for k, v in sorted(gates["V5"].items())))

        # 5. B1 / B2 / TreatyFeed / OptionTerms
        b2 = run_b2(cfg, runs_root, exposure=ex, coverage=cov)
        if b2["TreatyFeed"] is not None:
            from .treaty_contract import check_treaty_outputs
            tc = check_treaty_outputs(b2["dir"] / "out")
            gates["TREATY_CONTRACT"] = tc
            if tc["status"] != "PASS":
                raise GateFailed("TREATY_CONTRACT", "; ".join(tc["problems"][:5]))
        step("B1 + B2 (index, TreatyFeed, OptionTerms)",
             f"{len(b2['RateFactors'])} rate factors; treaty contract {gates.get('TREATY_CONTRACT', {}).get('status', 'n/a')}")

        # 6. A benchmark, 7. D scorecard (when configured)
        if cfg.get("benchmark"):
            from .benchmark import run_benchmark
            bm = run_benchmark(cfg, runs_root)
            step("A benchmark", f"{len(bm['market'])} market catalogues, {len(bm['subjects'])} subjects")
        if cfg.get("scorecard"):
            from .scorecard import run_scorecard
            sc = run_scorecard(cfg, runs_root)
            step("D scorecard", f"pack {Path(sc['pack']).name}")
    except PWError as e:
        log(f"STOPPED: {type(e).__name__}: {e}")
        res = finish("STOPPED", e)
        res["error"] = e
        return res
    return finish("COMPLETE")


def input_hashes(cfg: dict) -> dict:
    """sha256 of every input file the run config names (paths as written in the config, relative to it), the
    run config itself included; folders (maps, market intake) are hashed file by file."""
    import hashlib
    from .rate_index import _path
    base = Path(cfg["_base"])
    refs = set()

    def walk(v, key=""):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and not v.startswith("@") and key not in ("run_id", "option_id", "owner", "snapshot_date",
                                                                          "contract_version", "panel_id", "lead"):
            if ("/" in v or "\\" in v or "." in v) and _path(cfg, v).exists():
                refs.add(v)
    walk({k: v for k, v in cfg.items() if not k.startswith("_")})
    out = {}
    cfg_file = base / cfg.get("_file", "")
    if cfg.get("_file") and cfg_file.is_file():
        out[cfg_file.name] = hashlib.sha256(cfg_file.read_bytes()).hexdigest()
    for r in sorted(refs):                     # a catalogue spec's own source workbook (V1) is an input too
        p = _path(cfg, r)
        if p.is_file() and p.suffix == ".json":
            try:
                src = json.loads(p.read_text(encoding="utf-8")).get("source_file")
            except (ValueError, AttributeError):
                src = None
            if isinstance(src, str) and (p.parent / src).is_file():
                refs.add(f"{r.rsplit('/', 1)[0]}/{src}" if "/" in r else src)
    for r in sorted(refs):
        p = _path(cfg, r)
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
        for f in files:
            rel = r if f == p else f"{r.rstrip('/')}/{f.relative_to(p).as_posix()}"
            out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return dict(sorted(out.items()))


def output_hashes(rd: Path) -> dict:
    """sha256 of every file the run wrote (relative path -> hash): the byte-identity check of the WS4 acceptance."""
    import hashlib
    rd = Path(rd)
    out = {}
    for name in GENERATED:
        p = rd / name
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else []
        for f in files:
            out[f.relative_to(rd).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return dict(sorted(out.items()))
