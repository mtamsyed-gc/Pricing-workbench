# Handover — Pricing Workbench

Last updated: 2026-10-24 (repo seeded: SPEC v0.2, CLAUDE.md, WS0 work order, UFIC structure reference).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests during parallel work |
| reference/ufic/UFIC_Medical_Reinsurance_Reference.md | TEMPORARY GC material: UFIC catalogue V10 14.1 reference (ToB, factors, rate-table structure, UW rules). Structure only — see CLAUDE.md data boundary |
| requirements-native.txt | Runtime pins (same as ete-dashboard) |

## Related repos and tools
- ete-dashboard / side_tools/merit (Merit v7.3.x): exposure and experience source. Contract `side_tools/merit/config/model_contract.json`
  (IP4-8): dim_life carries Policy Type, TPA, Region Group, Network, Plan / Category, Relation, Gender Group, Marital Status,
  AgeAtInception, NewRenewal, Distribution, WrittenLY/Prem, EarnedLY/Prem; no co-pay field. Merit itself is not changed by this repo.
- ete-dashboard / side_tools/treaty_tool (treatymodel 2.0, master in PBM): P&L by scenario; fed by `TreatyFeed` (premium change %,
  LR adjustment per treaty book) and `OptionTerms`. Do not edit it here.
- Owner's existing product benchmarking tool (separate repo): input to WS2 (market benchmark) and to the benefit taxonomy
  reconciliation; attach read-only when WS2 starts.

## Status
| WS | Scope | Status | Next step |
|---|---|---|---|
| WS0 | Core: registries, catalogue model + spec parser, evaluator, exposure builder, gates V1–V4, fixtures, template generator core, work orders WS1–WS6 | Not started | Start session with docs/workorders/WS0.md |
| WS1 | B2 rate index, RateFactors, TreatyFeed; B1 level 1; submission ingest + V5 | Blocked on WS0 | — |
| WS2 | A market benchmark | Blocked on WS0 | — |
| WS3 | D scorecard | Blocked on WS0 | — |
| WS4 | Integration, release | Blocked | — |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | Blocked on WS0 RateFactors schema | — |

## Open with the owner
1. UFIC age band labels: DXB Individual (15 bands), AUH Individual (8), SME (8) — not in the reference document (SPEC §8.4).
2. AUH Individual blocks: keep the catalogue's Married-F column and Employee/SI vs Dependant sections, or collapse to M/F per the
   template principle (SPEC §8.0)?
3. UFIC source flags F1–F8 (SPEC §12), especially F1 (plan→network mapping) and F2 (AUH co-pay block labels).

## Timeline driver
UFIC reinsurer submissions due early November 2026. Priority order: WS0 → WS1 (B2 + TreatyFeed) → WS3 + WS6 → WS2.
