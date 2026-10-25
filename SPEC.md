# Pricing Workbench — Specification: Canonical Model, Contracts, Template Generator

Version 0.4 · 24 Oct 2026 (v0.2: owner's tender-template principle, §8.0; UFIC structure derived from the reference document, §8.4; v0.3: laptop acceptance after every change, §13, CR #1; v0.4: owner decisions on HANDOVER items 1–21 — UFIC bands, plan → network map and source flags, §8.4 / §12; B1 order and rider value, §4.3; benchmark rules, §4.5; coverage rule, §5; riders and V5, §6 / §8; B2 split and scorecard rules, §7; v0.5: cedant rate workbook, §8.5) · Owner: Etam (GC L&H IMEA)
Status: design baseline for WS0. WS1–WS6 build against this document; changes only via `docs/CHANGE_REQUESTS.md`.
First applied case: UFIC medical QS 2027 tender. The model is cedant-agnostic: no cedant, TPA or catalogue logic in code.

---

## 0. Purpose and scope

The workbench evaluates medical catalogues (benefits and rates) and reinsurer tender submissions on a common basis:

| Engine | Question it answers | Main outputs |
|---|---|---|
| B2 Rate index | What is the standardised rate change of each option vs expiring, overall and by cut? | Rate index tables, `RateFactors` (cell level), `TreatyFeed` (book level) |
| B1 Benefit value | Is each option richer or leaner than expiring, by benefit line and in total? | Benefit diff, richness index, `BenefitFactors` |
| A Benchmark | Where do the catalogue and proposals sit against the market on price and richness, and what is missing? | Value map, gap register |
| D Scorecard | Which option (or panel) do we recommend? | Scorecard, recommendation pack inputs |
| T Template generator | Produce a tender rates template from a user specification, and read submissions back | `Tender_Rates_<cedant>_<date>.xlsx`, parsed submissions |

**Product types in scope of the model** (registry values, extensible): `INDIVIDUAL`, `SME`, `GROUP` (experience-rated or tabled), `BASIC` (regulatory basic / low-salary plans, e.g. AUH Basic, DHA EBP), `NE_COMPULSORY` (Northern Emirates basic and enhanced), `RETIREE`, `IPMI`. UFIC 2027 uses the first five; RETIREE and IPMI must be supported by the model and fixtures now, with no UFIC data.

Out of scope for WS0: market data collection, claims re-adjudication (B1 level 2, designed in WS1, built later), Power BI changes (WS6, ete-dashboard repo).

---

## 1. Design principles

1. **Separate layout from pricing.** Every source (catalogue, tender template, reinsurer submission, market catalogue) is parsed by a declarative *catalogue spec* into the canonical model. Engines never read source layouts.
2. **Dimension registry, not fixed columns.** Rating dimensions are declared in `registry/dimensions.json`. A new product type (e.g. IPMI area of cover) adds dimensions and values without code changes.
3. **Wildcards.** A table that does not vary by a dimension matches `ANY` for it (e.g. unified principal/dependant rates; one table shared by NC and Mednet).
4. **Single-year age is canonical** (0–120). Source age bands map to age ranges; exposure carries single age. Band structures never need to align.
5. **Price only what is needed.** The evaluator prices exposure cells and template cells on demand; it never materialises full grids.
6. **Reference levels are explicit.** Every factor table records its reference option (factor = 1.0) per scope, because the base rate's implied benefit level is defined by it.
7. **Deterministic and auditable.** Same inputs + versions → byte-identical outputs; every evaluation can emit a component trace (base × factors + modules + fees).
8. **Data boundary.** Repo holds synthetic/fictional data only. Client catalogues, exposure and submissions live in the local run folder.

---

## 2. Dimension registry

`registry/dimensions.json` — each dimension: `code`, `type` (categorical | ordinal | numeric-range | money), `values` (for categorical), `hierarchy` (optional parent mapping), `exposure_source` (Merit field or derivation), `notes`.

| Code | Type | Example values | Exposure source (Merit `dim_life`) | Notes |
|---|---|---|---|---|
| `product_type` | cat | INDIVIDUAL, SME, GROUP, BASIC, NE_COMPULSORY, RETIREE, IPMI | `PolicyTypeUsed` + catalogue plan → product map | |
| `regulator` | cat | DHA, DOH, MOH_NE, NONE (IPMI) | `Region Group` | DOH = HAAD |
| `rating_region` | cat | DXB_NE, AUH, NE, plus IPMI residence groups | derived from regulator + catalogue scope | UFIC rates "DXB-NE" jointly |
| `tpa` | cat | dynamic per catalogue | `TPA` | Tables may scope a set of TPAs |
| `plan` | cat | dynamic per catalogue | `Plan / Category` → plan map | Dynamic count (§3.3) |
| `network` | cat | dynamic per catalogue × TPA | `Network` → network map | Attribute of plan × TPA, also a factor key |
| `network_option` | cat | OPT1, OPT2 (split IP/OP), … | not in Merit → default reference | |
| `age` | int 0–120 | single year | `AgeAtInception` | Bands mapped per table |
| `gender` | cat | M, F | `Gender` | |
| `marital` | cat | SINGLE, MARRIED | `Marital Status` | Individual M/SF vs Married-F = (gender, marital) |
| `member_category` | cat, hierarchical | EMPLOYEE, SMALL_INVESTOR, DEP_OF_EMPLOYEE, DEP_OF_INDIVIDUAL, SPOUSE, CHILD, PARENT, DOMESTIC_NONUAE_SPONSOR, DOMESTIC_UAE_SPONSOR, PARTNER_INVESTOR | `Relation` + catalogue rules | Parent groups: PRINCIPAL / DEPENDANT / DOMESTIC |
| `maternity_eligible` | bool | Y/N | `Gender Group` (F 18–45) or catalogue rule | Drives maternity module eligibility |
| `nationality_group` | cat | ISC, PHL, LEVANT_EGY, OTHER, … | `Nationality Group` | Factor key (UFIC Individual DXB) |
| `salary_band` | cat | LOW (≤ threshold), STANDARD | not in Merit → assumption | DHA EBP / AUH Basic eligibility |
| `group_size_band` | ordinal | dynamic | `GroupSize` | SME / Group factors |
| `copay_*` | cat | one dimension per co-pay family: `copay_op_diag`, `ded_consult`, `copay_pharmacy`, `copay_ip`, `pharmacy_limit`, `aml` | not in Merit → reference option unless supplied | §3.4 |
| `module_*` | cat | `module_maternity` (limit), `module_dental` (limit), `module_optical` (limit), IPMI: `module_op`, `module_evac`, … | not in Merit → per scenario | Additive or multiplicative |
| `area_of_cover` | cat | WW_INC_USA, WW_EXC_USA, REGIONAL, … | IPMI only | |
| `deductible` | money/cat | IPMI excess options | IPMI only | Factor key |
| `currency` | cat | AED, USD, … | catalogue attribute | FX table in run config |
| `payment_frequency` | cat | ANNUAL, SEMI, QUARTERLY, MONTHLY | IPMI/Retiree | Factor key |
| `rating_basis_age` | cat | INCEPTION_AGE, ATTAINED_AGE, ENTRY_AGE | catalogue attribute | Retiree (entry-age products) |

Mapping tables (per run, in `runs/<id>/maps/`): `plan_map.csv` (source plan label × TPA → catalogue plan), `network_map.csv`, `member_category_map.csv` (Relation × sponsor rules → member_category), `nationality_map.csv`. Unmapped values raise `MappingRequired` (never silently defaulted) and are listed in the run report with exposure share.

---

## 3. Catalogue model

### 3.1 Entities

```
Catalogue(catalogue_id, owner, kind[EXPIRING|SUBMISSION|MARKET|PROPOSED], version, effective_date, currency, premium_basis[GROSS|NET], source_file, spec_id)
 └─ RatingScope(scope_id, product_type, regulator, rating_region, tpa_set, plan_set, notes)   # one per rate sheet/block
     ├─ Plan(plan_id, label, tier_rank, network_by_tpa{tpa: network}, attributes{clinic_restricted, gp_referral, split_ip_op})
     ├─ Component[]   # ordered; see 3.2
     ├─ RatingFormula(order, rounding, min_premium, max_premium, refer_rules)
     └─ BenefitSchedule(plan_id → BenefitLine[])   # see §4
 └─ RuleSet(rules[])   # UW, eligibility, loading caps, referral thresholds, renewal triggers (§4.4)
```

### 3.2 Component types

| Type | Key dims (any subset) | Value | Example (UFIC) |
|---|---|---|---|
| `BASE_TABLE` | plan, age(band), gender, marital, member_category, tpa_set, … | AED per member | Ind DXB-NE base rates 7 plans × 15 bands × M/SF, Married-F |
| `FACTOR_TABLE` | any dims incl. co-pay families, plus `reference_level` | multiplier | OP diagnostic co-pay; AML factor by AML × network tier (2-D); TPA factor (NC 0.90); nationality factor; network option factor by plan |
| `BLOCK_SET` | co-pay level → separate base tables | AED | AUH Individual Nil/10%/20% blocks; normalised to BASE_TABLE (Nil) + implied FACTOR_TABLE, with block-consistency check (§6 V2) |
| `MODULE` | plan, limit option, eligibility filter, unit[PER_MEMBER|PER_ELIGIBLE_FEMALE|PER_FAMILY] | AED additive, or multiplier | SME dental/optical by plan × limit; maternity per eligible female by plan × IP limit |
| `FEE` | scope | AED fixed or % | policy/ICP fees, VAT (if in scope) |
| `LOADING` | scope | % (distributional) | MAF/UW loadings: cap per segment (e.g. 25%–32.5%); used in premium reconciliation, not in base comparison |
| `REFER` | cells | marker | "Above 64: refer to reinsurer"; not priced; counted in exposure coverage |
| `EXPERIENCE_RATED` | scope | basis (target LR / loading / credibility rule) | Group schemes |

Formula (default; order and rounding declared per scope):
`P = round( BASE × Π FACTOR + Σ MODULE_additive , rounding ) × (1 + LOADING_applied) + FEES`, bounded by min/max; `REFER` cells return null with reason.

### 3.3 Dynamic plans and networks

- Plans and networks are catalogue data, never schema: any number per catalogue, per TPA, per region.
- `network_by_tpa` maps a plan to each TPA's network label (UFIC: Plan A → NC/NAS/Mednet networks differ).
- `tier_rank` (1 = richest) enables cross-catalogue comparison; `tier_map.csv` maps catalogue plans to a canonical tier ladder per regulator when catalogues have different plan counts (e.g. 7 DXB plans vs 6 AUH plans vs 3 Aafiya plans). Many-to-one and one-to-many allowed, with weights.
- Factor tables keyed on network/tier (e.g. AML factor by GN+…PCP-RN3) resolve via the plan's network for the TPA.

### 3.4 Co-pay families and reference levels

- Each co-pay family is a dimension (`copay_op_diag`, `ded_consult`, `copay_pharmacy`, `copay_ip`, `pharmacy_limit`, `aml`, `network_option`).
- Each FACTOR_TABLE declares `reference_level` per scope (the option with factor 1.0 that the BASE_TABLE assumes). Where the reference differs by key (UFIC AML: 1.0 at AED 1.5m for GN+, AED 1m for GN, AED 500k for RN), the table stores it explicitly.
- Exposure cells without a known option take the **catalogue default option** (declared per plan), not the factor reference, and the run report states the share defaulted.

### 3.5 Premium basis and currency

- `premium_basis` per component (UFIC: Basic table gross, NE tables and add-ons net). Comparisons are made on one declared basis per run; conversion factors (gross→net) are run inputs, never assumed.
- Multi-currency catalogues convert at run FX rates (IPMI typically USD).

---

## 4. Benefit model

### 4.1 Benefit taxonomy (`registry/benefits.json`)

Hierarchical list; each line has `code`, `group`, `value_type`, `unit`, `comparison_rule` (higher-is-richer, lower-is-richer, presence, categorical ladder).

Groups and illustrative codes:
- **General:** `aml` (money), `territory` (ladder: NE_ONLY < UAE < WW_EMERG < WW), `days_abroad` (int), `pec_cover` (money/ladder), `pec_waiting` (months, lower richer), `room_type` (ladder: WARD < SHARED < SEMI_PRIVATE < PRIVATE), `network` (tier rank), `gp_referral` (bool, false richer), `reimb_out_network` (% UCR).
- **In-patient:** `ip_copay` (structure), `ip_sublimit`, `ip_per_admission_limit`, `companion_accom` (AED/day), `parent_accom`, `organ_transplant`, `prosthesis`.
- **Out-patient:** `consult_deductible` (structure), `op_diag_copay`, `op_sublimit`, `physio_sessions` + `physio_copay`, `pharmacy_limit`, `pharmacy_copay`, `pharmacy_formulary` (bool), `telehealth`, `alt_medicine_limit`.
- **Maternity:** `mat_ip_limit`, `mat_ip_coins`, `mat_op_visits`, `mat_scans`, `newborn_days`, `mat_waiting`.
- **Dental / Optical:** `dental_limit` + `dental_copay`, `optical_limit` + `optical_copay`, `emergency_dental`.
- **Other:** `repatriation`, `intl_assistance`, `vaccinations`, `preventive`, `cancer_psp`, `hepatitis`, `hiv`, `work_injury`, `evacuation` (IPMI), `chronic_limit`.

Co-pay structures use one canonical object: `{type: PCT|FIXED|PCT_CAPPED|DEDUCTIBLE, pct, amount, cap_per_visit, cap_annual, follow_up_exempt_days}`.

### 4.2 Benefit schedule

`BenefitLine(plan_id, benefit_code, value, structure, condition_text, source_ref)`; free text is kept beside the parsed value for audit. Lines not parseable → `value = null`, `status = MANUAL_REVIEW`.

### 4.3 Valuation (B1 level 1)

- Value relativities come from (in priority order, owner decision 24 Oct 2026): **owner overrides** (run input; they always win, and the trace and BenefitDiff `source` show the value they replace); the catalogue's own factor tables (co-pay, AML, pharmacy, network option); a market factor library (`registry/benefit_factors.json`, versioned). Benefit valuation only: pricing always uses the catalogue's own factors.
- Richness index per plan = product of factor relativities vs a reference schedule, plus module values as % of base.
- **Module (rider) value** = the expiring catalogue's rider premium for the schedule's option ÷ the plan's expiring base premium (base × rating factors), both summed over the B2 standard mix (latest UWY, lives in force) on the cells priced without the rider. Expiring prices throughout, so a change of rider limit is valued on one fixed price scale. richness_expiring = 1 + Σ module values (expiring options); richness_option = Π relativities + Σ module values (option's options); ratio = richness_option ÷ richness_expiring. A rider option the expiring catalogue does not price on the plan's cells is MANUAL_REVIEW.
- Level 2 (re-adjudicating claims with each schedule) is designed in WS1 and uses Merit `fact_claims` (FOB/FOC, BeneficiaryShare, Approved, PayerShare).

### 4.4 Rules (non-pricing terms)

`Rule(rule_id, scope, type[ELIGIBILITY|UW|LOADING_CAP|REFERRAL|RENEWAL|REVIEW|OTHER], parameters, text)`. UFIC examples:
- SME group size 3–200;
- maximum loading by TPA;
- claim referral above AED 15k (all TPAs) or AED 50k (NC);
- SME renewal: NLR ≤ 75% renews automatically, above 75% is referred;
- AUH Basic salary ≤ AED 5k, group of 150–500 lives;
- quarterly price review.

Rules feed the terms comparison (B and D) and are never used in pricing unless declared as LOADING or REFER.

### 4.5 Market benchmark (A) rules (owner decisions 24 Oct 2026)

- Market plans are priced **as sold** (own default design; CR #14) over the exposure mix and the standard cell set (CR #15), on the run basis with the file's own gross-to-net factor (CR #16).
- Levers and add-ons with registry dimensions (incl. CR #13: room type, PEC limit, medication type, territory; physiotherapy, OP psychiatric, alternative medicine, home nursing, health check, repatriation) enter the market price.
- A package add-on level the intake file does not price exactly is **interpolated linearly on the limit between the file's own two nearest priced limits** (same benefit, co-pay, network, form and applies-to), status BRIDGED. Resolved per network ('All' and each offered network; an exact row wins, limits compared as numbers); every offered network must be covered by its own row or by 'All'. No extrapolation beyond the file's priced range, ambiguous rows are not used, and no other source's reference basis; otherwise NOT_PRICED.
- Gap register: GAP when the subject does not cover a line that ≥ `gap_share` (0.5) of the peer plans cover (share of all peer plans; a peer without the line does not count as covering). **Peers = market plans of the same tier and the same rating region** (`peer_same_region`, default true: DHA and DOH mandatory benefits differ). Fewer than `gap_min_peers` (3) peer plans → LOW_PEERS, no call.
- No reconciliation to the SME Benchmarking Tool's report is required (owner: that tool has not been used); the adapter's V1 and hand-checked tests are the control.

---

## 5. Exposure model

Source: Merit run outputs (`dim_life`, contract IP4-8), read-only, pinned contract copy in `contracts/merit_model_contract_IP4-8.json`.

`ExposureCell` = aggregation of `dim_life` by the canonical key, carrying:
- `lives_inforce` (at the snapshot date);
- `written_ly` (`WrittenLY_Net`) and `written_prem` (`WrittenPrem_Net`);
- `earned_ly` and `earned_prem`;
- `uwy`;
- `new_renewal`;
- `distribution`.

Rules:
- Standard mix = UWY latest, annualised in-force lives (`written_ly` sensitivity; UWY-1 mix sensitivity).
- Age = `AgeAtInception` (single year); missing DOB → flagged, not banded by default.
- `member_category` from `member_category_map.csv`; `maternity_eligible` from `Gender Group` unless the catalogue defines its own rule.
- Co-pay/module options: not in Merit → catalogue default option (§3.4). Optional `exposure_options.csv` override if UFIC supplies product codes.
- Coverage report: share of lives / premium matched to a priced cell, to a REFER cell, or unmatched (with reasons). Gate: matched (= priced + REFER) ≥ 95% of premium, otherwise run stops with the list. The gate tests mapping quality; the REFER share is reported separately and the unpriced share is carried by B2 and D (owner decision 24 Oct 2026).

---

### 5.1 Merit contract compatibility (Merit changes independently)

- The workbench depends on Merit **only through its output contract**: no Merit code or logic is copied.
- `contracts/merit_model_contract_<version>.json` is a pinned copy of `side_tools/merit/config/model_contract.json`.
- `contracts/merit_field_map.json` maps the canonical exposure fields to Merit column names. A Merit column rename is a one-line config change, not a code change.
- **Gate V0 (contract check)** runs before every exposure build. It reads the contract version and columns of the Merit run being loaded and compares them with the pinned contract and field map:
  - same version: proceed;
  - new version with all required fields present: proceed with a warning and the column diff;
  - required field missing or renamed without a map entry: stop, listing the fields.
- When Merit publishes a new contract version, update the pinned copy and field map through a change request. Exposure-builder tests run against both contract versions until the old one is retired.
- Required fields: the `dim_life` columns used in §5 (Policy Type / PolicyTypeUsed, TPA, Region Group, Network, Plan / Category, Relation, Gender, Gender Group, Marital Status, Nationality Group, AgeAtInception, UWY, NewRenewal, Distribution, GroupSize, WrittenLY_Net / _Gross, WrittenPrem_Net / _Gross, EarnedLY_Net, EarnedPrem_Net). `fact_claims` is optional (B1 level 2).
- The treaty tool is treated the same way: `TreatyFeed` targets the treatymodel version recorded in `contracts/treatymodel_version.txt`.

## 6. Evaluator and validation gates

`evaluate(catalogue, cells, options) → price, trace` (DuckDB-backed; vectorised by scope).

| Gate | Test | Failure action |
|---|---|---|
| V1 Source reproduction | Spec-parsed catalogue reproduces every source cell (or a declared sample) exactly | Stop; spec fix |
| V2 Block consistency | For BLOCK_SETs, each block ÷ Nil block = one flat multiplier; cells deviating > tolerance flagged with expected value (UFIC NAS AUH 20%: 13 cells) | Flag; use declared resolution (derived value) |
| V3 Premium reconciliation | Expiring catalogue × exposure (default options) vs actual written premium by product × TPA × region × plan; implied factor = actual ÷ rated (captures co-pay mix, loadings, discounts) | Report; implied factor carried as calibration, never hidden |
| V4 Template round-trip | Generated template → filled with synthetic values → parsed back = identical | Stop |
| V5 Submission integrity | Submitted template structure hash = issued hash; all mandatory cells numeric > 0; outliers vs expiring (ratio band, default 0.7–1.3, run config `v5.outlier_band`) flagged. Quoted riders (Add-ons in FILL mode) are checked against the expiring rider rate on the same band (RIDER_OUTLIER); a blank rider is RIDER_NOT_QUOTED and a rider ≤ 0 or non-numeric is RIDER_INVALID (both priced as missing, never used); without `_KEYS` the riders cannot be located: RIDERS_UNREAD | Flag to user |

---

## 7. Output contracts (consumed by other tools)

| Table | Grain | Columns | Consumer |
|---|---|---|---|
| `RateFactors` | option × exposure cell key | `option_id, cell_key…, rate_expiring, rate_option, factor, priced_status` | WS6 Merit Annex (as-if), B2 cuts |
| `RateIndex` | option × cut | `option_id, cut_dims…, lives, prem_expiring, prem_option, index, index_benefit_adj` | Reports, D |
| `BenefitDiff` | option × plan × benefit_code | `expiring_value, option_value, direction, value_factor` | Reports, D |
| `BenefitFactors` | option × plan | `richness_expiring, richness_option, ratio` | B2 benefit-adjusted index, A |
| `TreatyFeed` | option × treaty book | `premium_change_pct, lr_adjustment_pts, basis_note` | Treaty restructuring tool scenario columns (premium change = rate factor × (1 − lapse) − 1; LR adjustment = as-if LR − experience LR) |
| `OptionTerms` | option | `reinsurer, share_by_book, premium_basis, commission, corridor, cap, profit_share, conditions, validity` | Treaty tool, D |
| `ScoreInputs` | option × criterion | `metric, value, source` | D |

All outputs: Parquet + an Excel view; run manifest with versions and hashes.

Additional columns (owner decision 24 Oct 2026; the contract columns above are unchanged):
- `RateFactors` adds `rate_expiring_base, rate_option_base` (base × rating factors, no riders / loading / fees; priced where the base prices) and `rate_expiring_riders, rate_option_riders` (rider premium = premium before loading and fees − base-only price, so additive and multiplicative riders and any formula order are covered and the two parts add up; priced where the full premium prices).
- `RateIndex` adds `prem_expiring_base, prem_option_base, index_base` and `prem_expiring_riders, prem_option_riders, index_riders`. The headline `index` and the `TreatyFeed` stay on full premium; the split shows where an option's change comes from (e.g. cheap base, loaded riders).
- `TreatyScenarios.json` (owner, 25 Oct 2026, CR #23) beside `TreatyFeed`: the same figures in the treaty tool's config schema (treatymodel 2.0, `scenarios`), one scenario per option with `books.volume[slot] = 1 + premium_change_pct / 100` and `books.lr_adj[slot] = lr_adjustment_pts / 100` per book slot (run input `treaty.book_slots`, treaty book → slot 1–8; an unmapped book raises MappingRequired), `prem_chg = lr_chg = 0`. In the tool's engine this reproduces the as-if (premium × rate factor × (1 − lapse), claims × (1 − lapse)). Reinsurer terms are owner inputs in the tool and are not written; `OptionTerms` stays reference text.

Scorecard (D) rules: min-max to 0–100 per criterion, **scale set by single options only**; when the single options show no spread on a criterion everyone (panels included) scores 100 and the Scorecard and pack flag it `NO_SPREAD`; **SHARE is on an absolute scale**, 100 × min(share, 100%) ÷ 100% = the share of the order filled, so a panel's capacity counts up to a full placement (owner, 25 Oct 2026, CR #22); panels are placed on that scale and may fall outside 0–100. **Followers write at the lead's rates and terms**: a panel takes the lead's value on every criterion except SHARE, which is the panel's capacity (sum of the members' offered shares) — CR #12 as amended 24 Oct 2026. Default directions: commission, profit share, cap, share higher is better; corridor width, price, unpriced share, V5 flag share and robustness spread lower is better (run config `scorecard.directions` overrides per tender). One-at-a-time sensitivity rescales the other weights proportionally (equal shares if they are all 0).

---

## 8. Tender Rates Template generator (T)

### 8.0 Owner's template principle (24 Oct 2026)

- **Base table = age × network × gender at 0% co-pay.** Reinsurers price the base. Co-pay, AML, TPA, nationality and network-option adjustments are separate factor tables (read-only by default).
- **TPA basis (owner decision 24 Oct 2026, final):** the rate in each TPA block is the base **before** the TPA factor; the issued TPA factor applies on top. The Cover states it.
- **Riders:** reinsurers may quote their own rider (add-on module) rates when the spec sets `reference_sheets.addons = "FILL"`. A blank rider cell means **not quoted**: the rider is priced as missing (cells needing it are REFER "rider not quoted", counted in the unpriced share), never the expiring rate carried over.
- **One table per product type × emirate (rating region) × TPA.** Tables are never shared between TPAs in the template, even where the source catalogue shares one (e.g. UFIC AUH NC & Mednet). The parser can map a shared source table to several template blocks.
- The number of networks per block is dynamic: one column group per network/plan of that TPA.
- Extra splits (marital status, e.g. AUH Married-F; member section, e.g. AUH Employee/SI vs Dependant) are spec options, off by default. They are switched on per block only where the cedant's catalogue prices them (UFIC: on for every AUH Individual block, owner decision 24 Oct 2026). A section may carry its own band set (e.g. an Employee section without an under-18 row where principals under 18 are not offered).
- Simple tables (regulatory basic / compulsory plans) use member category × age band, or age band only, as their spec declares.
- The tender structure is generated fresh by the tool from a `template_spec.json`. There is no reliance on a previously issued workbook.

### 8.1 Input: `template_spec.json` (user specification)

- `cedant`, `tender_id`, `currency`, `premium_basis`, `deadline`, `contact`.
- `sheets[]`, where each sheet has:
  - `scope`: product_type, regulator / rating_region, tpa blocks;
  - `plans` (dynamic list; labels per TPA);
  - `age_bands` (per sheet; any structure);
  - column dimensions: e.g. [gender] or [gender × marital], or [member_category];
  - row sections: e.g. EMPLOYEE_SI / DEPENDANT;
  - `copay_basis` (base only, reference options stated);
  - `refer_cells`;
  - mandatory/optional flags.
- `reference_sheets`:
  - Existing Rates (from the expiring catalogue, with derived co-pay values and V2 flags);
  - Co-Pay Multipliers (read-only, or an optional "proposed multipliers" column);
  - Add-on tables (`addons`: `"READ_ONLY"` default, or `"FILL"`: a submitted column per rider row; blank = not quoted);
  - TOB summary;
  - Terms sheet (share, basis, conditions, validity, comments).
- `options`:
  - `allow_proposed_multipliers` (bool);
  - `allow_benefit_comments` (bool);
  - `protect_structure` (bool);
  - `language`;
  - `rounding`.

The spec can be authored from a catalogue (`t generate --from-catalogue expiring.json --select ...`) or edited directly.

### 8.2 Output workbook

- **Cover:** instructions, sheet directory, basis statement, deadline, version and structure hash.
- **Reference sheets:** read-only.
- **Rate sheets:** one block per TPA × scope.
  - Yellow input cells, numeric validation (> 0) and conditional outlier shading against expiring (optional, toggle).
  - Every input cell carries its canonical cell key, held in a hidden key column / defined names and in a hidden `_KEYS` sheet, so parsing back needs no mapping.
- **Terms sheet:** structured fields for share, premium basis, commission, corridor, cap, profit share, conditions, validity, plus free-text comments.
- **Protection:** structure locked; input cells unlocked; the hash is written to `_META`.

### 8.3 Round trip

`t ingest <submission.xlsx>`:
- validates the hash (V5);
- reads input cells by key into a SUBMISSION catalogue;
- applies the issued multipliers, or proposed ones if allowed and supplied;
- registers the option for B2/B1/D.

Deviations (renamed sheets, inserted rows) are tolerated through the `_KEYS` map. If the keys are lost, the parser falls back to positional parsing with warnings.

### 8.4 UFIC 2027 instance

The UFIC structure is derived from `reference/ufic/UFIC_Medical_Reinsurance_Reference.md` (temporary GC material: read for structure only, never copied into code, fixtures or releases). It is expressed as `examples/ufic_2027/template_spec.json`, kept outside the repo if it holds client values; the repo copy carries structure only, with no rates.

Blocks under §8.0:

| Product | Emirate | TPA blocks | Plans / networks | Ages × columns |
|---|---|---|---|---|
| Individual | DXB-NE | NC, NAS, Mednet | 7 each (A–G) | 15 bands × M/SF, Married-F |
| Individual | DXB-NE | Aafiya | 3 (plans E–G) | 15 bands × M/SF, Married-F |
| Individual | AUH | NC, Mednet, NAS | 6 each (A–F) | Employee/SI (7 bands, no under-18 row) + Dependant (8 bands) × M/SF, Married-F |
| Individual | AUH | Aafiya | 2 (plans E–F) | as above |
| SME | DXB-NE | NAS, NC, Mednet | 6 each (A–F) | 9 bands × M/F |
| SME | AUH | NAS, NC, Mednet | 6 each (A–F) | Employee (3 bands, no under-18 row) + Dependent (4 bands) × M/F |
| Basic | AUH | — (direct) | 1 | 6 member categories × up to 4 bands |
| NE Basic / Enhanced 1 / Enhanced 2 | NE | Aafiya | 1 each | member category or age bands as in reference §10–12 |

Reference sheets: Existing Rates (expiring catalogue in the same blocks, with derived values and V2 flags), Co-Pay & Factor tables (reference §3), Add-ons (dental, optical, maternity), Terms.

**Confirmed by the owner from the catalogue (24 Oct 2026), labels only, no rates:**
- Age bands in `examples/ufic_2027/age_bands.json`: DXB Individual 15 bands (top band [71-99] read as 71+); AUH Individual 8 bands (Employee/SI section 7, no 00-17); SME DXB/NE 9 bands; SME AUH 4 bands (Employee section 3, no 0-17). SME differs from the reference's "8 bands" (v0.3), corrected here.
- Plan → network per TPA from the catalogue's master plan table: plan letter A… = plan number 1…, the same plan letter across TPAs, with each TPA's own network label (Mednet labels are the Mednet network names). Aafiya sits at E–G (IND DXB), E–F (IND AUH); **no Aafiya SME block**. The map is in `examples/ufic_2027/template_spec.json` (each plan carries `plan_id` = letter and `plan_number`).
- Individual AML is fixed by the table of benefits: no AML factor for Individual. SME AML reference (factor 1.0) per network column, and the SME AML / maternity column of a NAS or Mednet plan is taken through its plan letter (A GN+, B GN, C RN, D RN2, E RN3, F PCP-RN3).
- Network options: Option 1 only (Option 2 for DXB Plan B / C switched off for Individual and SME; "RN3 Open" left off).
- Riders (dental, optical, maternity) are quotable (`addons = "FILL"`); NE Basic bands read 0–64 / 65+.
- **Owner 25 Oct 2026 (WS5):** every Individual TPA block is priced M/SF and Married-F (DXB-NE corrected from M/F); the Married-F rate includes the maternity load, so Individual has no maternity rider. Factors-Individual is switched off until clarified (Aafiya DXB-NE keeps its co-pay block multipliers, F3). SME network options are switched off. In the cedant workbook a reference factor that is not 1.0 is a warning (value kept).

Acceptance check: the generated UFIC template has exactly the blocks, plans, bands and columns above. Its round-trip test (V4) passes.

### 8.5 Cedant rate workbook (owner decision 25 Oct 2026; work order WS5)

The expiring catalogue does not have to be mapped from the cedant's own workbook. The tool generates a **cedant-mode
rate workbook** from the same `template_spec.json`; GC fills it from the cedant's catalogue and the tool reads it back
into the EXPIRING catalogue. One layout, two modes, one parser:

| Sheet | Cedant mode (GC fills current rates) | Reinsurer mode (§8.2) |
|---|---|---|
| Rate sheets | Same blocks as the tender; Nil / 0% co-pay base, before the TPA factor | Same; Existing Rates from the read-back catalogue |
| Factors | Long table: product, emirate, family, key (network / plan or ANY), option, factor, reference (Y = 1.0). Options pre-filled; one reference per key | Read only |
| Riders | Long table: product, emirate, rider family, limit, network, unit, eligibility, rate | Quotable (`addons = "FILL"`) |
| Plan defaults | Plan × family → the option the plan is sold with (§3.4 catalogue default) | — |
| Benefits | Plan × benefit_code (registry) → value, condition text | — |
| Terms | — | Fill |

Co-pay variants are never entered: the Nil base and the factor tables generate them. Read-back is gated (blank or
non-numeric mandatory cells, missing / duplicate reference rows, defaults naming unknown options, unknown benefit
codes stop the read with the cell list). The filled cedant copy holds client rates and lives only in `runs/`; the
repo holds the spec (structure only).

---

## 9. Catalogue spec format (sketch)

```json
{
  "spec_id": "UFIC_V10_14_1",
  "catalogue": {"owner": "UFIC", "kind": "EXPIRING", "currency": "AED", "premium_basis": "NET"},
  "scopes": [
    {
      "scope_id": "IND_DXBNE_NC_NAS_MEDNET",
      "product_type": "INDIVIDUAL", "regulator": "DHA", "rating_region": "DXB_NE",
      "tpa_set": ["NEXTCARE", "NAS", "MEDNET"],
      "plans": [{"plan_id": "A", "tier_rank": 1, "network_by_tpa": {"NEXTCARE": "GN+", "NAS": "CN", "MEDNET": "GOLD"}}],
      "components": [
        {"type": "BASE_TABLE", "source": {"sheet": "...", "range": "..."},
         "dims": {"plan": "col_header", "age": {"bands": "row_labels", "map": "age_bands_dxb_15"}, "gender": "col_subheader"}},
        {"type": "FACTOR_TABLE", "family": "copay_op_diag", "reference_level": "0%", "values": {"0%": 1.0, "10%": 0.96, "20%": 0.92}},
        {"type": "FACTOR_TABLE", "family": "aml", "keys": ["aml", "network"], "reference_level_by_key": {"GN+": "1500000", "GN": "1000000"}},
        {"type": "FACTOR_TABLE", "family": "tpa", "values": {"NAS": 1.0, "MEDNET": 1.0, "NEXTCARE": 0.90}},
        {"type": "MODULE", "family": "module_maternity", "unit": "PER_ELIGIBLE_FEMALE", "keys": ["network", "limit"]}
      ],
      "formula": {"order": ["BASE", "FACTORS", "MODULES"], "rounding": 2}
    }
  ]
}
```

(Values illustrative; network labels per TPA to be confirmed, see §12.)

---

## 10. Synthetic fixtures (all fictional)

| Fixture | Purpose |
|---|---|
| `CAT_ALPHA` | Unified rates, 15 DXB bands, co-pay as factor tables, 7 plans, 3 TPAs with TPA factor |
| `CAT_BETA` | Principal/dependant split, AUH 8 bands, gender × marital columns, co-pay as BLOCK_SET with 5 planted inconsistent cells |
| `CAT_GAMMA` | Base-only table with dental/optical/maternity modules; SME group-size factors; 4 plans |
| `CAT_DELTA` | Basic/compulsory style: member-category rows, few bands, REFER cells above 64, gross basis |
| `CAT_RETIREE` | Ages 55–99 single-year, entry-age rating, max entry age rule, payment-frequency factor |
| `CAT_IPMI` | USD, area of cover × deductible factors, 5-year bands to 80+, OP/maternity/evac modules |
| `EXPO_SYN` | Synthetic exposure cube in Merit `dim_life` shape (columns only, values random seeded) |
| `SUB_X`, `SUB_Y` | Two synthetic reinsurer submissions generated through T and filled with perturbed rates |

---

## 11. Work orders (summary; full texts in `docs/workorders/`)

| WS | Deliverable | Acceptance (headline) |
|---|---|---|
| WS0 | Registry, catalogue model, spec parser, evaluator, exposure builder, V1–V4, fixtures, T generator core, work orders | All fixtures pass V1/V2/V4; evaluator traces; exposure coverage report on EXPO_SYN |
| WS1 | B2 rate index + cuts + `RateFactors` / `TreatyFeed`; B1 level 1; T ingest + V5 | Index on SUB_X/SUB_Y hand-checked; benefit-adjusted index; round trip |
| WS2 | A: market catalogue intake via specs, tier matching, value map, gap register | CAT_ALPHA vs CAT_GAMMA vs CAT_IPMI comparisons |
| WS3 | D: scorecard, option pack template | Weighted scores, sensitivity to weights |
| WS4 | Integration, release zip, treaty tool feed | End-to-end synthetic run |
| WS6 | Merit Annex option slicer + as-if page reading `RateFactors` (ete-dashboard repo) | As-if equals workbench numbers on fixtures |
| WS5 | Cedant rate workbook (§8.5): generate, fill (GC), read back into the expiring catalogue; UFIC structure | Round trip prices EXPO_SYN identically to CAT_ALPHA; UFIC cedant workbook generates with every block, factor family, rider and default |
| WS7 | Structured benefit proposals with the owner's accept flag (CR #17) | Accepted proposal changes richness by a hand-checked amount; ignored changes nothing |

Every work order is also subject to the laptop acceptance check (§13).

---

## 12. UFIC source flags (outcomes recorded 24 Oct 2026)

| # | Item | Observation | Outcome (owner, 24 Oct 2026) |
|---|---|---|---|
| F1 | Plan → network by TPA (DXB, §1) | The reference rows A–C looked shifted (NC CN / NAS GN+ on Plan A) | **Resolved** from the catalogue's master plan table: NC GN+ / NAS CN on Plan A; full map in the UFIC template spec |
| F2 | AUH Individual co-pay blocks (NC/Mednet, NAS) | 10% → ×0.945 but 20% → ×0.980 (a higher co-pay gives a smaller discount); Aafiya is the intuitive way round | **Swap the labels**: 10% → ×0.980, 20% → ×0.945 (mathematically logical; same as Aafiya). Applied in the run's expiring catalogue spec (outside the repo) |
| F3 | Aafiya DXB section (§5) | Shows the AUH multipliers 0.98 / 0.945, while §3.1 says Aafiya DXB uses Factors-Individual | **Aafiya co-pay block multipliers apply** (the Aafiya sheets' 10% / 20% blocks are flat ×0.980 / ×0.945 of the Nil rate in every cell) |
| F4 | Consultation deductible "10% flat" = 1.085 | Higher than "10% up to AED 20" (1.05), although uncapped member cost should give a lower factor | **Keep the source value, flagged**; may be updated later (an owner override can correct it for B1) |
| F5 | AML factor reference | The base rate's implied AML differs by tier | **Resolved (SME only):** reference AML per network column; Individual has no AML factor |
| F6 | NAS AUH 20% block | 13 erroneous cells (known) | **Agreed:** V2 flags and uses the derived ×0.9734 values |
| F7 | Premium basis | AUH Basic gross; NE and add-ons net | **Agreed:** declare per component; state the comparison basis in the template |
| F8 | Incumbent references | Incumbent named in tables and rules | **Agreed:** template and outputs say "refer to the lead reinsurer"; no incumbent name in market-facing files |
| — | SME maternity columns | Columns GN+, GN, RNE, RN, RN2, RN3/PCP-RN3; RNE is not in the master plan table | **Provisional (owner assumption):** column RNE = RN (plan C), RN = RN2 (D), RN2 = RN3 (E), RN3/PCP-RN3 = PCP-RN3 (F); "Annual Limit" row ignored (owner, 25 Oct 2026). Column shift to confirm with UFIC |
| — | Network factor "GN excl. named hospitals" on Plan 2 (SME) | Network option not in the base | Kept as a network option (not offered in the base table) |

Note for the rate index: because every co-pay adjustment is a flat multiplier fixed by UFIC, the cell-level rate ratio (option ÷ expiring) does not depend on members' co-pay options. Missing co-pay fields in Merit therefore matter only for V3 (premium reconciliation) and B1, not for B2, unless a reinsurer proposes different multipliers.

---

## 13. Laptop acceptance after every change (owner, 24 Oct 2026; CR #1)

Every change to the workbench (every work order, every PR, every change request applied) is tested on the owner's
laptop before it counts as done. Sandbox tests are necessary but not sufficient: the target runtime is the laptop
(CPython 3.12 64-bit, Windows, Artifactory pins, `py` launcher, 260-character paths).

- **Tool:** `py tools\laptop_check.py` (from any folder). It checks the environment (Python version and bitness,
  Windows, every pin in `requirements-native.txt`), runs the full test suite, runs every CLI tool end to end on the
  synthetic fixtures from a working directory that is not the repo, opens the generated workbooks, and checks path
  lengths. It writes `runs/laptop_check/<UTC stamp>/laptop_check_report.md` (+ `.json`); exit code 0 = all PASS.
- **Coverage rule:** a work order that adds or changes a tool or CLI command adds its end-to-end check to
  `TOOL_CHECKS` in `tools/laptop_check.py` in the same PR. A tool without a laptop check is not complete.
- **Definition of done:** the PR description carries a "Laptop check" line, `PENDING` when opened. The owner runs the
  check on the PR branch and returns the report's summary line (or the report). The work order is done, and the PR
  may be merged, only when that line reads `LAPTOP CHECK PASS` for the PR's head commit. A FAIL goes back to the
  session that owns the work order, with the report.
- HANDOVER.md records the laptop-check status per work stream (`pending` / `PASS <commit>` / `FAIL`).
- Reports stay in `runs/` (never committed); they contain synthetic data only.

