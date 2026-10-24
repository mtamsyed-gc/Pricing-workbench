# B1 level 2 — claims re-adjudication (design only; build later)

Status: design, WS1 (24 Oct 2026). SPEC §4.3: "Level 2 (re-adjudicating claims with each schedule) … uses Merit
`fact_claims` (FOB/FOC, BeneficiaryShare, Approved, PayerShare)". Not built in WS1. Owner review needed on the
open points at the end before any build.

## Question it answers
Level 1 values a benefit change with pricing relativities (factor tables, market library). Level 2 measures it on the
cedant's own claims: what would the payer have paid on the same claims under the option's schedule?
Output: per option × plan × benefit line, `paid_expiring`, `paid_option`, `value_factor_l2 = paid_option / paid_expiring`,
with credibility against level 1.

## Inputs
- Merit `fact_claims` (contract IP4-8, optional table): claim line, LifeKey/UWY link to `dim_life`, FOB/FOC
  (field of benefit / claim category), Approved, BeneficiaryShare (member cost), PayerShare, InCover, InExperience.
- The canonical BenefitSchedule of expiring and option (SPEC §4.2), co-pay structures in the canonical object
  `{type, pct, amount, cap_per_visit, cap_annual, follow_up_exempt_days}`.
- Mapping table `fob_map.csv` (run input): Merit FOB/FOC → benefit_code (op_diag_copay, consult_deductible,
  pharmacy_copay, ip_copay, mat_*, dental_*, …). Unmapped FOB → MappingRequired, reported with paid share.

## Method
1. **Gross-up to allowed cost.** Per claim line: allowed = Approved (if missing: PayerShare + BeneficiaryShare).
2. **Remove expiring cost-sharing.** Re-apply the expiring schedule to allowed cost and compare with the recorded
   PayerShare — reconciliation gate (L2-R): modelled payer share within tolerance of recorded, by FOB × plan.
   Lines that fail are excluded with their share (e.g. claims where the recorded share reflects a waived co-pay).
3. **Apply option cost-sharing** to the same allowed cost, in the order the schedule defines:
   per-visit deductible → co-insurance → per-visit cap → annual caps by member (needs member-year accumulation,
   ordered by service date) → sub-limits (per benefit, per member-year) → AML.
4. **Behavioural response** (utilisation change from cost-sharing) is not modelled by default; an optional
   elasticity table by FOB (owner input) can scale allowed cost.
5. **Aggregate** paid by option × plan × benefit line on the standard mix (latest UWY, completed claims only:
   InExperience = 1, IBNR handled by scaling with Merit `ultimates` completion factors per TPA × lag).

## Outputs (proposed; contract change needed before build)
`BenefitValueL2` (option × plan × benefit_code): `paid_expiring, paid_option, value_factor_l2, claims, members,
reconciled_share, credibility`. Credibility-weighted blend with level 1 via a limited-fluctuation standard
(e.g. full credibility at 1,082 claims per line), parameters in run config.

## Validation
- Identity: option = expiring schedule → value_factor_l2 = 1 exactly.
- Monotonic: higher co-pay → value_factor_l2 ≤ 1 per line.
- L2-R reconciliation by FOB × plan reported; unreconciled share ≤ threshold (run input) or the line is level-1 only.

## Open points for the owner
1. Is `Approved` the allowed amount in all TPA feeds, or net of co-pay for some TPAs?
2. Annual caps and sub-limits need service dates and member-year ordering: confirm `fact_claims` carries them.
3. Behavioural elasticity: off, or an owner table by FOB?
4. Credibility standard and blend with level 1.
5. Contract: new output `BenefitValueL2` (SPEC §7) via change request.
