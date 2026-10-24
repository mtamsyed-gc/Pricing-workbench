# Work order WS4 — Integration and release

Branch: `ws4-integration` · Read: SPEC (all), docs/CHANGE_REQUESTS.md, §13 · Depends on: WS1–WS3 merged

## Goal
One end-to-end synthetic run, cross-stream conflicts resolved, a release zip the team installs on laptops,
and the treaty-tool feed exercised.

## Deliverables
1. `py tools\pw.py run <run_config.json>`: catalogue specs → exposure (V0, coverage gate) → V1–V3 → submissions
   (T ingest, V5) → B2 / B1 → A → D, writing `runs/<RunID>/` with a manifest (versions, hashes, gate results).
2. Apply approved change requests not yet applied; resolve merge conflicts between streams.
3. `TreatyFeed` / `OptionTerms` checked against the treatymodel version in `contracts/treatymodel_version.txt`
   (columns and types; the treaty tool itself is not edited here).
4. Release: `tools/package.py` zip (excludes `reference/`, client examples, `runs/`), install notes for the
   Artifactory pins, versioning.
5. `tools/laptop_check.py` extended with the full `run` on fixtures; this becomes the release gate.

## Files
- May edit any workbench file to integrate; contract / registry changes only via approved CRs.
- Must not edit: ete-dashboard repo, treaty tool, Merit.

## Acceptance criteria
- End-to-end synthetic run reproduces byte-identical outputs on a second run.
- All gates reported in the manifest; the release zip contains no `reference/` or client example files (tested).
- Full suite green; `LAPTOP CHECK PASS` on the owner's laptop from the **installed release zip** (not the repo clone).
