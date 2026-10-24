# Work order WS7 — Structured benefit proposals (CR #17)

Branch: `ws7-benefit-proposals` · Read: SPEC §2, §4.3, §6 (V5), §8, §13; docs/CHANGE_REQUESTS.md CR #13, #17 ·
Depends on: owner-decisions batch (CR #13 dimensions, riders in FILL mode, B1 override order and rider value)

## Goal
Let a reinsurer propose benefit improvements in a structured form, and let the owner decide which proposals earn
richness credit in B1 and the scorecard (owner decision 24 Oct 2026, HANDOVER item 18).

## Deliverables
1. Template: optional "Proposed benefit changes" sheet (template spec option `allow_benefit_proposals`). Each row:
   product, plans affected, benefit dimension (dropdown of registry dimensions / benefit codes), option offered, and
   whether it is included in the quoted rates or carries an extra premium (amount, unit).
2. Parser: reads the rows into the SUBMISSION catalogue as proposals; every dimension / option checked against the
   registry; an unknown option raises MappingRequired (never credited by guess). V5 flags incomplete rows.
3. Run input `benefit_proposals.csv`: one row per proposal with `decision` ACCEPT | IGNORE; a proposal not listed is
   IGNORE (no silent credit). The CLI writes the file with every proposal set to IGNORE for the owner to edit.
4. B1: an accepted proposal changes that option's benefit schedule for the plans named (factor-valued lines through the
   relativity order of SPEC §4.3; riders through the rider value); an extra premium is added to the option's price.
   PRICE stays what was quoted; PRICE_BENEFIT_ADJ reflects the accepted proposals.
5. Recommendation pack: accepted and ignored proposals per reinsurer.
6. Tests and the end-to-end check in `tools/laptop_check.py`.

## Files
- May create: `pw/template/proposals.py`, tests `tests/test_ws7_*.py`, a synthetic fixture submission with proposals.
- May edit: `pw/template/generator.py`, `pw/template/parser.py`, `pw/gates.py`, `pw/benefit_value.py`,
  `pw/scorecard.py`, `tools/pw.py`, `tools/laptop_check.py`, `tools/build_submissions.py`.
- Must not edit: contracts and registries (CR only).

## Acceptance criteria
- A proposal with IGNORE (or not listed) changes nothing; ACCEPT changes the plan's richness by a hand-checked amount.
- Unknown dimension / option stops with MappingRequired. Extra premium enters the price and the B2 rider column.
- Full suite green; `LAPTOP CHECK PASS` (SPEC §13).

## Out of scope
Judging whether a proposal is acceptable to the cedant or the regulator (owner decision per proposal).
