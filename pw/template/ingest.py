"""T ingest (SPEC §8.3): parse a filled tender template, run V5, build the SUBMISSION catalogue (issued multipliers,
or proposed ones where the template allowed them), and register the option in the run folder.

    runs/<RunID>/options.json                      registry: option_id -> catalogue path, owner, hashes, V5 summary
    runs/<RunID>/options/<option_id>/catalogue.json
    runs/<RunID>/options/<option_id>/v5_flags.csv
    runs/<RunID>/options/<option_id>/terms.json
V5 never stops the ingest (SPEC §6: flag to user). Cells V5 marks invalid (blank, non-numeric, <= 0) are left out of the
SUBMISSION catalogue - they price as UNMATCHED and appear in the index's unpriced share - and are listed in the registry.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .. import SpecError
from ..gates import v5_submission_integrity
from ..model import Catalogue
from ..outputs import run_dir, update_manifest
from .parser import parse_submission, read_meta, to_catalogue

_ID_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")


def issued_hash_of(template_path: Path) -> str:
    h = read_meta(template_path).get("structure_hash")
    if not h:
        raise SpecError(f"{Path(template_path).name}: no structure hash in _META (not an issued template?)")
    return h


def ingest(submission: Path, template_spec: dict, run_id: str, option_id: str, owner: str,
           issued_hash: str | None = None, issued_template: Path | None = None, expiring: Catalogue | None = None,
           outlier_band=None, multiplier_band=None, runs_root: Path | None = None) -> dict:
    if not option_id or set(option_id) - _ID_OK:
        raise SpecError(f"option_id {option_id!r}: use letters, digits, '_' or '-'")
    if issued_hash is None and issued_template is not None:
        issued_hash = issued_hash_of(issued_template)
    parsed = parse_submission(Path(submission), template_spec=template_spec)
    v5 = v5_submission_integrity(parsed, template_spec, issued_hash, expiring, outlier_band, multiplier_band)
    cat = to_catalogue(parsed, template_spec, catalogue_id=option_id, owner=owner, expiring=expiring,
                       exclude=v5["invalid"])
    cat.meta["v5"] = {"status": v5["status"], "counts": v5["counts"], "hash_ok": v5["hash_ok"]}
    rd = run_dir(run_id, runs_root)
    od = rd / "options" / option_id
    od.mkdir(parents=True, exist_ok=True)
    cat.write(od / "catalogue.json")
    v5["flags"].to_csv(od / "v5_flags.csv", index=False, lineterminator="\n")
    (od / "terms.json").write_text(json.dumps(parsed.terms(), indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                   encoding="utf-8", newline="\n")
    sub_hash = hashlib.sha256(Path(submission).read_bytes()).hexdigest()
    entry = {"option_id": option_id, "owner": owner, "kind": "SUBMISSION",
             "catalogue": f"options/{option_id}/catalogue.json", "submission_file": Path(submission).name,
             "submission_sha256": sub_hash, "issued_hash": issued_hash,
             "submitted_hash": parsed.meta.get("structure_hash"), "v5_status": v5["status"], "v5_counts": v5["counts"],
             "excluded_cells": len(v5["invalid"]), "rate_cells": v5["rate_cells"],
             "tpa_factor_basis": cat.meta.get("tpa_factor_basis"), "catalogue_hash": cat.content_hash(),
             "expiring": expiring.catalogue_id if expiring is not None else None}
    reg_p = rd / "options.json"
    reg = json.loads(reg_p.read_text(encoding="utf-8")) if reg_p.exists() else {}
    reg[option_id] = entry
    reg_p.write_text(json.dumps(dict(sorted(reg.items())), indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    update_manifest(rd, "options", {option_id: {k: entry[k] for k in ("submission_sha256", "catalogue_hash", "v5_status",
                                                                      "issued_hash", "tpa_factor_basis")}})
    return {"entry": entry, "v5": v5, "catalogue": cat, "dir": od}


def registered_options(run_id: str, runs_root: Path | None = None) -> dict:
    """option_id -> Catalogue for every option registered in the run."""
    rd = run_dir(run_id, runs_root)
    reg_p = rd / "options.json"
    if not reg_p.exists():
        return {}
    reg = json.loads(reg_p.read_text(encoding="utf-8"))
    return {oid: Catalogue.read(rd / e["catalogue"]) for oid, e in sorted(reg.items())}
