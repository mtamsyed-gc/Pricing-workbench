# Work order WS0 — Core, contracts, template generator core

Branch: `ws0-core` · Read: SPEC §0–§10 (all), §12 · Reference: reference/ufic/ (structure only)

## Goal
Lay the foundation every other stream builds on: registries, canonical catalogue model, catalogue spec parser,
evaluator, exposure builder, validation gates V1–V4, fictional fixtures, the tender rates template generator (T) core,
and the work orders for WS1–WS3, WS4 and WS6.

## Deliverables
1. **Package layout**
   - `pw/`: `registry.py`, `model.py`, `spec_parser.py`, `evaluator.py`, `exposure.py`, `gates.py`, `template/`
     (generator, `_KEYS` / `_META`), `io_excel.py`, `trace.py`.
   - `tools/pw.py`: CLI.
   - `registry/dimensions.json`, `registry/benefits.json` (v0.1 from the UFIC ToB structure plus the SPEC §4.1 list), `registry/benefit_factors.json` (empty scaffold).
   - `tests/`, `fixtures/`, `examples/`.
2. **Registry** (SPEC §2):
   - all dimensions listed, including RETIREE / IPMI dimensions;
   - hierarchies (member_category → PRINCIPAL / DEPENDANT / DOMESTIC);
   - wildcard ANY semantics;
   - single-year age with band maps.
3. **Catalogue model and spec parser** (SPEC §3, §9):
   - component types BASE_TABLE, FACTOR_TABLE (with reference levels per key), BLOCK_SET (normalised to base + implied factors), MODULE (eligibility, unit), FEE, LOADING, REFER and EXPERIENCE_RATED;
   - dynamic plans and networks (`network_by_tpa`, `tier_rank`, `tier_map`);
   - premium basis and currency per component;
   - rules (SPEC §4.4) stored as non-pricing terms.
4. **Evaluator** (SPEC §6): vectorised (DuckDB / pandas) pricing of arbitrary cell sets, with an optional trace, catalogue default co-pay options, and REFER handling.
5. **Exposure builder** (SPEC §5):
   - reads a Merit-shaped `dim_life` (Parquet or CSV) and aggregates it to canonical cells through the mapping tables;
   - coverage report (priced / refer / unmatched, with lives and premium);
   - gate at 95% of premium matched;
   - Merit contract IP4-8 pinned in `contracts/`.
6. **Gates** (plus V0 contract check, SPEC §5.1, with `contracts/merit_field_map.json` and tests against a second, synthetic contract version with one renamed column):
   - V1 source reproduction, V2 block consistency (planted errors found), V3 premium reconciliation (implied factor by cut), V4 template round trip;
   - V5 is stubbed; WS1 completes it.
7. **Template generator core** (SPEC §8.0–§8.3):
   - `template_spec.json` schema plus validator;
   - generator producing Cover, reference sheets (Existing Rates with derived values and V2 flags, Factor tables, Add-ons), rate blocks per product × emirate × TPA (age × network × gender, 0% co-pay, dynamic networks, optional marital / member section splits), Terms sheet, hidden `_KEYS` and `_META` (structure hash), and protection;
   - parser that reads a filled template back to a SUBMISSION catalogue by key (WS1 adds V5 and multiplier proposals).
8. **Fixtures** (SPEC §10): CAT_ALPHA, CAT_BETA, CAT_GAMMA, CAT_DELTA, CAT_RETIREE, CAT_IPMI, EXPO_SYN, plus SUB_X / SUB_Y generated through T. All fictional.
9. **UFIC structure example** `examples/ufic_2027/template_spec.json`, derived from the reference document (SPEC §8.4):
   - structure only, no rates;
   - age-band labels go in `examples/ufic_2027/age_bands.json`, as placeholders until the owner supplies them;
   - plan → network labels per TPA as in the reference, with F1 flagged in a comment field.
10. **Work orders** `docs/workorders/WS1.md`, `WS2.md`, `WS3.md`, `WS4.md`, `WS6.md`: scope, SPEC sections, files each may and may not touch, fixtures, acceptance criteria.

## Acceptance criteria
- `py tests\run_all.py` green:
  - every fixture passes V1;
  - CAT_BETA's 5 planted block errors are found by V2 with their expected values;
  - V3 runs on EXPO_SYN × CAT_ALPHA and reports implied factors by product × TPA × region × plan;
  - V4 round trip is identical for all fixtures and for the UFIC structure example.
- The evaluator prices the same cell under CAT_ALPHA (factor co-pay) and CAT_BETA (block co-pay) with traces that hand-check.
- A RETIREE cell (entry-age rating, payment frequency) and an IPMI cell (USD, area of cover × deductible) price correctly with FX applied.
- The generated UFIC template has exactly the blocks, plans, bands and columns of SPEC §8.4: one block per TPA, no shared tables, dynamic network counts.
- No UFIC labels or values appear outside `examples/ufic_2027/` and `reference/`. `tools/package.py` excludes reference/.
- HANDOVER.md updated; branch `ws0-core` pushed; PR opened.
- Laptop check (SPEC §13, CR #1): `py tools\laptop_check.py` returns `LAPTOP CHECK PASS` on the owner's laptop for the PR head commit.

## Out of scope
- Rate index and benefit-value engines (WS1).
- Benchmark (WS2).
- Scorecard (WS3).
- Power BI (WS6).
- Claims re-adjudication.

## Owner inputs pending (do not block on them)
- UFIC age-band labels (HANDOVER open item 1): build `examples/ufic_2027/` with clearly marked placeholder bands. The generator takes bands from the file, so real labels drop in without code changes.
- AUH Individual layout (HANDOVER open item 2): implement both options (`marital` / `member_section` splits on or off per block). Default the UFIC example to **off** (age × network × gender, per SPEC §8.0) and record it as pending.
- The UFIC-example acceptance item passes on structure with placeholders and is re-run when the owner answers. Everything else in this work order is independent of these inputs.
