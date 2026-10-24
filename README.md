# Pricing Workbench

Cedant-agnostic tooling to compare medical catalogues and reinsurer tender submissions on a common basis: canonical catalogue model and evaluator, exposure from Merit, rate index (B2), benefit value (B1), market benchmark (A), scorecard (D) and a tender rates template generator / submission parser (T).

Start with HANDOVER.md, then CLAUDE.md, then SPEC.md.

Quick start (team laptop): `py tests\run_all.py`, then `py tools\laptop_check.py` (SPEC §13; required after every change).
CLI: `py tools\pw.py --help`. Fixtures (synthetic): `py tools\pw.py fixtures build`.
