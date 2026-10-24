# Pricing Workbench — Specification: Canonical Model, Contracts, Template Generator

Version 0.3 · 24 Oct 2026 (v0.2: owner's tender-template principle, §8.0; UFIC structure derived from the reference document, §8.4; v0.3: laptop acceptance after every change, §13, CR #1) · Owner: Etam (GC L&H IMEA)
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
| `marital` | cat | SINGLE, MARRIED | `Marital Status` | AUH M/SF vs Married-F = (gender, marital) |
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
| `BASE_TABLE` | plan, age(band), gender, marital, member_category, tpa_set, … | AED per member | Ind DXB-NE base rates 7 plans × 15 bands × 2 genders |
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

- Value relativities come from (in priority order): the catalogue's own factor tables (co-pay, AML, pharmacy, network option); a market factor library (`registry/benefit_factors.json`, versioned); owner overrides.
- Richness index per plan = product of factor relativities vs a reference schedule, plus module values as % of base.
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
- Coverage report: share of lives / premium matched to a priced cell, to a REFER cell, or unmatched (with reasons). Gate: matched ≥ 95% of premium, otherwise run stops with the list.

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
| V5 Submission integrity | Submitted template structure hash = issued hash; all mandatory cells numeric > 0; outliers vs expiring (ratio bands) flagged | Flag to user |

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

---

## 8. Tender Rates Template generator (T)

### 8.0 Owner's template principle (24 Oct 2026)

- **Base table = age × network × gender at 0% co-pay.** Reinsurers price only the base. Co-pay, AML, TPA, nationality and network-option adjustments are separate factor tables (read-only by default).
- **One table per product type × emirate (rating region) × TPA.** Tables are never shared between TPAs in the template, even where the source catalogue shares one (e.g. UFIC AUH NC & Mednet). The parser can map a shared source table to several template blocks.
- The number of networks per block is dynamic: one column group per network/plan of that TPA.
- Extra splits (marital status, e.g. AUH Married-F; member section, e.g. AUH Employee/SI vs Dependant) are spec options, off by default. They are switched on per block only where the cedant's catalogue prices them; see the open question in the WS0 work order.
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
  - Add-on tables (fill or read-only);
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
| Individual | DXB-NE | NC, NAS, Mednet | 7 each (A–G; labels per TPA) | 15 bands × M/F |
| Individual | DXB-NE | Aafiya | 3 (APN Plus, Essential, APN) | 15 bands × M/F |
| Individual | AUH | NC, Mednet, NAS | 6 each (Plan 1–6) | 8 bands × M/F (optional: marital, member section) |
| Individual | AUH | Aafiya | 2 | 8 bands × M/F |
| SME | DXB-NE | NAS, NC, Mednet | 6 each | 8 bands × M/F |
| SME | AUH | NAS, NC, Mednet | 6 each | 8 bands × M/F |
| Basic | AUH | — (direct) | 1 | 6 member categories × up to 4 bands |
| NE Basic / Enhanced 1 / Enhanced 2 | NE | Aafiya | 1 each | member category or age bands as in reference §10–12 |

Reference sheets: Existing Rates (expiring catalogue in the same blocks, with derived values and V2 flags), Co-Pay & Factor tables (reference §3), Add-ons (dental, optical, maternity), Terms.

**Missing from the reference document:** the exact DXB 15-band, AUH 8-band and SME 8-band age boundaries. The owner supplies these as band labels only (no rates) in `examples/ufic_2027/age_bands.json`.

Acceptance check: the generated UFIC template has exactly the blocks, plans, bands and columns above. Its round-trip test (V4) passes.

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

Every work order is also subject to the laptop acceptance check (§13).

---

## 12. UFIC source flags (to confirm with UFIC before the template is final)

| # | Item | Observation | Proposed handling |
|---|---|---|---|
| F1 | Plan → network by TPA (DXB, §1) | Rows A–C look shifted: NC "CN" for Plan A and NAS "GN+" vs the NC GN+/GN/RN… and NAS CN/GN/RN/SRN/WN/VN ladders used elsewhere | Confirm the mapping; it drives exposure matching and AML/maternity factor lookup |
| F2 | AUH Individual co-pay blocks (NC/Mednet, NAS) | 10% → ×0.945 but 20% → ×0.980 (a higher co-pay gives a smaller discount); Aafiya is the intuitive way round. The "HAAD methodology" explanation does not hold actuarially | Likely block labels swapped in source. Confirm; the rate index is unaffected (flat multipliers cancel) but benefit valuation and premium reconstruction are |
| F3 | Aafiya DXB section (§5) | Shows the AUH multipliers 0.98 / 0.945, while §3.1 says Aafiya DXB uses Factors-Individual | Confirm which applies |
| F4 | Consultation deductible "10% flat" = 1.085 | Higher than "10% up to AED 20" (1.05), although uncapped member cost should give a lower factor | Confirm definition |
| F5 | AML factor reference | "Standard" AED 1m has factor 0.9537 for GN+ and 1.0145 for RN, so the base rate's implied AML differs by tier | Store reference per tier (§3.4); confirm intended base AML |
| F6 | NAS AUH 20% block | 13 erroneous cells (known) | V2 flags and uses the derived ×0.9734 values |
| F7 | Premium basis | AUH Basic gross; NE and add-ons net | Declare per component; state the comparison basis in the template |
| F8 | Incumbent references | "Refer to Optio Re" appears in tables and rules | Template and outputs say "refer to the lead reinsurer"; no incumbent name in market-facing files |

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

