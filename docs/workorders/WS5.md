# Work order WS5 — Cedant rate workbook (current rates in, our own layout)

Branch: `ws5-cedant-workbook` · Read: SPEC §2, §3 (catalogue model, §3.4 defaults and reference levels), §4.1–4.3,
§8 (incl. §8.5), §12, §13 · Depends on: OD1 merged (SPEC v0.4, UFIC example structure)

## Goal
Get the cedant's current (expiring) catalogue into the tool through a workbook the tool generates in its own clean,
fill-in layout, instead of mapping the cedant's source workbook (owner decision 25 Oct 2026). GC fills it (from the
cedant's catalogue); the tool reads it back into an EXPIRING catalogue that drives Existing Rates, V5, B2, B1 and A.
UFIC submissions are due 5 Nov 2026: the filled UFIC copy and the reinsurer template must be ready well before.

## Design (SPEC §8.5)
One rate-workbook layout, two modes, one parser:
- **Cedant mode (new):** Cover; the same rate sheets as the tender (product x emirate x TPA blocks, plans across,
  M/F or M/SF + Married-F columns, age bands down; Nil / 0% co-pay base, before the TPA factor); and four long tables:
  - **Factors:** product, emirate, family, key (network / plan where the factor varies, else ANY), option, factor,
    reference (Y on the option = 1.0). Option labels pre-filled from the spec; only `factor` is entered.
  - **Riders:** product, emirate, rider family (dental / optical / maternity / ...), limit (option), network, unit
    (PER_MEMBER / PER_ELIGIBLE_FEMALE), eligibility, rate.
  - **Plan defaults:** product x emirate x plan x family -> the option the plan is sold with (dropdown of the
    family's options). The evaluator's catalogue default (SPEC §3.4).
  - **Benefits:** product x emirate x plan x benefit_code (registry/benefits.json, dropdown) -> value (number, text
    or ladder value as the code's comparison rule needs), condition text.
  Yellow input cells only; every input carries its canonical key in `_KEYS` (as the tender template); dropdowns for
  options and benefit codes; numeric validation on rates and factors; rows can be added to the long tables.
- **Reinsurer mode (exists):** unchanged, with Existing Rates generated from the catalogue read back above; Factor
  Tables read only; riders quotable (FILL); Terms.

## Deliverables
1. Template spec additions (structure only): `factor_tables` (family, keys, options, reference option per key),
   `riders` (family, options, networks, unit, eligibility), `plan_defaults` (families per scope), `benefits`
   (codes per scope). Validation in `pw/template/spec.py`.
2. Generator: `generate_cedant_workbook(spec, out)` (`py tools\pw.py t cedant <template_spec.json> --out <xlsx>`).
3. Reader: `read_cedant_workbook(xlsx, spec) -> Catalogue` (kind EXPIRING; BASE_TABLE per block, FACTOR_TABLE per
   family with reference levels, MODULE per rider, plan defaults, benefit lines)
   (`py tools\pw.py t cedant-read <filled.xlsx> --spec <template_spec.json> --out runs\<RunID>\expiring.json`).
4. Gate on read-back (stops, never defaults): blank / non-numeric / <= 0 mandatory rate; factor table without exactly
   one reference row per key; a plan default naming an option its table lacks; unknown benefit code or ladder value;
   duplicate rows in a long table. Report lists every problem with sheet and cell.
5. UFIC structure (labels only, no rates or factors) in `examples/ufic_2027/template_spec.json`: factor families and
   options from SPEC §12 / the reference document as corrected on 24 Oct (Individual: OP co-pay, consultation
   deductible, pharmacy co-pay, network option, nationality, TPA = 1.0, AUH co-pay blocks as flat multipliers with the
   F2 swap and F3 Aafiya multipliers; SME: OP co-pay, IP / day-case co-pay, AUH IP deductible, consultation
   deductible, pharmacy limit and co-pay, AML by network column via plan letter, nationality, TPA, maternity columns
   per the provisional shift), riders (dental, optical, maternity), plan defaults and benefit codes from the ToB.
   Values are entered by GC in the filled copy, which lives only in `runs/`.
6. Fixtures and tests: generate the cedant workbook from CAT_ALPHA's structure, fill it from CAT_ALPHA's values
   (seeded, scripted), read it back and prove the catalogue prices EXPO_SYN identically to CAT_ALPHA (cell level).
   Gate failures tested one by one. Reinsurer template generated from the read-back catalogue = T_ALPHA content.
7. `tools/laptop_check.py`: `t cedant` and `t cedant-read` end-to-end on fixtures; workbook opens in Excel.
8. A short fill guide (docs/cedant_workbook_guide.md): what goes where, the Nil-base rule, the TPA basis, F2 / F3.

## Files
- May create: `pw/template/cedant.py`, tests `tests/test_ws5_*.py`, fixture folder `fixtures/C_ALPHA/` (synthetic),
  `docs/cedant_workbook_guide.md`.
- May edit: `pw/template/spec.py`, `pw/template/generator.py` (shared formats / `_KEYS` helpers), `tools/pw.py`,
  `tools/laptop_check.py`, `tools/build_submissions.py`, `examples/ufic_2027/*` (structure only).
- Must not edit: contracts, registries (CR only); the reinsurer-mode layout except to share code.

## Acceptance criteria
- Round trip on fixtures: CAT_ALPHA -> cedant workbook -> filled -> read back prices EXPO_SYN cell for cell as
  CAT_ALPHA (tolerance 0); gate failures produce the expected messages.
- The UFIC cedant workbook generates from `examples/ufic_2027/template_spec.json` with every block, factor family,
  rider and plan default of SPEC §8.4 / §8.5, and contains no rates or factor values.
- Full suite green; `LAPTOP CHECK PASS` (SPEC §13), including opening both UFIC workbooks in Excel.

## Out of scope
Entering UFIC's values (GC does that on the laptop, into `runs/`); terms and UW rules input (later); WS7 proposals.
