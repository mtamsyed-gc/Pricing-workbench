# Handover — Pricing Workbench

Last updated: 2026-10-24 (WS0 built on `ws0-core`; SPEC v0.3 adds §13 laptop acceptance, CR #1).

Read this, then CLAUDE.md, then your work order in docs/workorders/, then the SPEC sections it names.

## Documents
| File | What |
|---|---|
| SPEC.md | Canonical model, registries, catalogue/benefit/exposure models, evaluator and gates V1–V5, output contracts, tender template generator, fixtures, work-order summary, UFIC source flags F1–F8 |
| docs/workorders/WS0.md | Full work order for the first session (core + contracts + generator core + other work orders) |
| docs/CHANGE_REQUESTS.md | Contract change requests during parallel work (CR #1 applied; #2–#4 pending owner) |
| docs/workorders/WS1–WS4, WS6 | Work orders for the next streams (written by WS0) |
| tools/laptop_check.py | SPEC §13 laptop acceptance: run `py tools\laptop_check.py` on the laptop after every change |
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
| WS | Scope | Status | Laptop check | Next step |
|---|---|---|---|---|
| WS0 | Core: registries, catalogue model + spec parser, evaluator, exposure builder, gates V0–V4 (V5 stub), fixtures, template generator core, work orders WS1–WS6, laptop check | Built on `ws0-core`, 49 tests green, PR #1 open | **PASS (owner, 24 Oct, provisional)** — functional PASS on owner's personal laptop @ 777c8e8 (Win 11, Py 3.14); GC work laptop (pinned Py 3.12) run outstanding | Merge PR #1; run the check on the GC work laptop when available; answer open items below |
| WS1 | B2 rate index, RateFactors, TreatyFeed; B1 level 1; T ingest + V5 | Ready after WS0 merge | — | Start with docs/workorders/WS1.md |
| WS2 | A market benchmark | Ready after WS0 merge (needs WS1 BenefitFactors for richness) | — | docs/workorders/WS2.md |
| WS3 | D scorecard | Blocked on WS1 outputs | — | docs/workorders/WS3.md |
| WS4 | Integration, release | Blocked on WS1–WS3 | — | docs/workorders/WS4.md |
| WS6 | Merit Annex as-if page (ete-dashboard repo) | RateFactors schema fixed in SPEC §7; needs WS1 outputs on fixtures | — | docs/workorders/WS6.md |

### WS0 notes for the next sessions
- Package: `pw/` (registry, model, spec_parser, evaluator, exposure, gates, trace, io_excel, template/{spec,generator,parser}).
  CLI `tools/pw.py`; fixture builders `tools/build_fixtures.py`, `tools/build_submissions.py` (byte-reproducible, tested).
- Matching rule: per component the most specific row wins (exact > hierarchy parent > ANY per dimension); equal-specificity
  rows with different values raise. Missing options take the catalogue default (plan -> scope -> component) or raise.
- BLOCK_SET -> BASE_TABLE (reference block) + `<id>.implied` FACTOR_TABLE (median ratio, 4 dp, or declared multipliers);
  resolution DERIVED by default; V1 checks SOURCE reproduction, V2 lists deviating cells with expected values.
- Template: one block per product x region x TPA (a TPA may have several blocks only for disjoint plans, e.g. NE plans);
  `_KEYS` holds live `='Sheet'!$C$7` formulas, so renamed sheets / moved cells are followed; positional fallback if lost.
- Merit contract IP4-8 pinned in `contracts/` with 4 description strings redacted (client names); columns verbatim.
- Determinism: byte-identical on one platform/library build; across platforms (Linux sandbox vs Windows, CPython 3.14
  zlib-ng, openpyxl XML backend) xlsx bytes differ but canonical XML content is identical (tested).
- Data-boundary test scans pw/, registry/, fixtures/, tests/, tools/, contracts/ for the tokens listed in
  `examples/ufic_2027/expected_structure.json`.

## Open with the owner (owner will answer items 1–2 later; WS0 proceeds with placeholders)
1. UFIC age band labels: DXB Individual (15 bands), AUH Individual (8), SME (8) — not in the reference document (SPEC §8.4).
   Placeholders in `examples/ufic_2027/age_bands.json`; drop real labels + ranges in there, no code change.
2. AUH Individual blocks: keep the catalogue's Married-F column and Employee/SI vs Dependant sections, or collapse to M/F per the
   template principle (SPEC §8.0)?
3. UFIC source flags F1–F8 (SPEC §12), especially F1 (plan→network mapping) and F2 (AUH co-pay block labels).
4. (WS0) TPA factor basis of a submitted per-TPA base rate. **Decision 24 Oct (provisional): option A** — the value
   in a per-TPA block is the base BEFORE the catalogue TPA factor; the issued TPA factor is still applied (current
   WS0 behaviour; Existing Rates shows the pre-factor base). Owner is verifying how the cedant's adjustment factor
   works and will confirm. If it changes to B (block = the TPA's final rate), raise a CR: amend SPEC §8.0, show
   Existing Rates after the TPA factor, set the TPA factor to 1.0 when parsing submissions, state it on the Cover.
5. (WS0) Coverage gate counts PRICED + REFER premium as "matched" — confirm (SPEC §5 wording is ambiguous).
6. (WS0) MODULE unit PER_FAMILY has no allocation rule in SPEC: raises ProposalRequired until defined.
7. (WS0) NE Basic source bands "00–64" / "64+" overlap at 64: example reads them as 0–64 and 65+; confirm with UFIC.
8. (WS0) SME / AUH-Mednet network labels per TPA are not in the reference: example uses the add-on table labels for all TPAs.
9. (WS0) CRs #2–#4 in docs/CHANGE_REQUESTS.md (extra mapping tables, group_size_band as numeric range, V0 version source).
10. (WS0) xlsxwriter cannot lock workbook structure (sheet order/insertion); sheets are protected individually and
    `_KEYS` tolerates moves. Acceptable?

## Timeline driver
UFIC reinsurer submissions due early November 2026. Priority order: WS0 → WS1 (B2 + TreatyFeed) → WS3 + WS6 → WS2.
