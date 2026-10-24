# Pricing Workbench — standing instructions for Claude

Read HANDOVER.md first (status, blockers, next step), then the work order you were given in docs/workorders/,
then the SPEC.md sections it names. SPEC.md is the source of truth. If code and SPEC disagree, SPEC wins.
If SPEC is silent or ambiguous, stop and ask the owner — never invent business logic or pricing rules.

## What this repo is
Cedant-agnostic tooling to evaluate medical catalogues (benefits + rates) and reinsurer tender submissions:
canonical catalogue model, evaluator, exposure builder (reads Merit outputs), rate index (B2), benefit value (B1),
market benchmark (A), scorecard (D), tender rates template generator and submission parser (T).
First applied case: UFIC medical QS 2027 tender. No cedant-, TPA- or catalogue-specific logic in code:
everything source-specific lives in catalogue specs, template specs, registries and mapping tables.

## Runtime (same as the team's other tools)
- CPython 3.12 (64-bit), Windows, on team laptops. Packages pinned in requirements-native.txt (installed from GC
  Artifactory). Allowed imports: stdlib + those pins. Anything else needs the owner's approval and a new pin.
- Code must run on pandas 3.x (copy-on-write, string dtype) and numpy 2.x. Config files are JSON (no PyYAML).
- Storage: DuckDB + Parquet in a local run folder runs/<RunID>/ (never committed). Excel outputs via xlsxwriter
  (generated workbooks) or openpyxl (reading). Never round-trip a generated workbook through LibreOffice.
- CLI: `py tools\pw.py <command>` (the `py` launcher; `python` may not be on PATH). Resolve paths from the
  script's own location; never assume the cwd. pathlib only; allow for the 260-char path limit.
- No network calls, no GUI. Design the working set for a 16 GB laptop; DuckDB memory_limit/threads from run config.

## Engineering rules
- Deterministic: same inputs + versions -> byte-identical outputs (sort before write; no unseeded randomness).
- Every evaluation can emit a component trace (base x factors + modules + fees) for audit.
- Unmapped values raise MappingRequired; missing rules raise ProposalRequired. Never default silently, except where
  SPEC names the default (e.g. catalogue default co-pay option when exposure lacks it, SPEC §3.4).
- Contracts in SPEC §7 and the registries are frozen during parallel work. A session that needs a change writes it
  to docs/CHANGE_REQUESTS.md and stops on that point; the owner approves; one session applies it.
- Tests: plain Python, `py tests\run_all.py` (or `python tests/run_all.py` in Linux sandboxes). All pass before commit.

## Data boundary (non-negotiable)
- Repo holds synthetic / fictional data only (fixtures: fictional catalogues, synthetic exposure, synthetic submissions).
- Client catalogues with rates, exposure, Merit outputs and reinsurer submissions live in runs/ or outside the repo.
- TEMPORARY EXCEPTION (owner, 24 Oct 2026): reference/ holds GC material (UFIC catalogue reference document) for
  STRUCTURE ONLY. Never copy its names, labels or values into code, fixtures, tests or releases; packaging excludes
  reference/. UFIC-specific spec files that carry structure only (no rates) may live in examples/ufic_2027/.
- Market-facing outputs never name the incumbent reinsurer.

## Working method
- One work order per session; work on its branch (e.g. ws0-core). Start by restating its acceptance criteria and plan.
- End by running the full test suite, then summarise: what was built, deviations from SPEC (with reason), open questions.
- Laptop acceptance (SPEC §13): every change is tested on the owner's laptop with `py tools\laptop_check.py`. A new or
  changed tool / CLI command gets its end-to-end check in `tools/laptop_check.py` in the same PR. Open the PR with
  "Laptop check: PENDING" and the exact command; the work order is done only when the owner returns
  `LAPTOP CHECK PASS` for the head commit.
- Update your section of HANDOVER.md (status and next step) before committing. Commit as "WS<n>: <summary>".
- Merge to main via pull request with tests green; WS4 (integration) resolves cross-stream conflicts.
