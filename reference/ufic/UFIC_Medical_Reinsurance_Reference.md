


# UFIC Medical — Reinsurance Renewal Reference Document

 

> **Cedant:** UFIC (United Fidelity Insurance Company)  

> **Reinsurer (incumbent):** Optio Re MENA Limited 

> **Purpose:** Complete LLM-readable reference for evaluating and responding to the UFIC reinsurance renewal tender. Covers the full product catalogue — Table of Benefits (ToB), pricing mechanics, co-pay structure, underwriting rules, and tender template guidance. 

> **Source:** UFIC Product Catalogue V10 14.1 (original workbook + Marsh Re tender template) 

> **Currency:** AED (UAE Dirham) throughout unless stated otherwise

 

---

 

## DOCUMENT MAP

 

| Section | Content |

|---|---|

| §1 | Product Universe — segment overview |

| §2 | Tender Template — how the rate workbook is structured and what to fill in |

| §3 | Co-Pay & Pricing Mechanics — multipliers, factors, adjustment logic |

| §4–§13 | Table of Benefits — one sub-section per product segment |

| §14 | Underwriting Guidelines — Individual, SME, AUH Basic, NE |

| §15 | Known Data Quality Issues |

 

---

 

## §1 — PRODUCT UNIVERSE

 

UFIC operates a tiered health insurance catalogue across three UAE emirates (Dubai/Other Emirates, Abu Dhabi, Northern Emirates) with two TPA ecosystems (NC/NAS/Mednet and Aafiya). Reinsurance is required across all segments.

 

### Segment Map

 

| # | Segment | Regulator | Emirates | TPA(s) | Plans | Member Types |

|---|---|---|---|---|---|---|

| 1 | Individual | DHA | Dubai & Other Emirates | NC, NAS, Mednet | A–G (7) | Employee / Dependant |

| 2 | Individual | DHA | Dubai & Other Emirates | Aafiya | APN Plus, Essential, APN (3) | Employee / Dependant |

| 3 | Individual | HAAD | Abu Dhabi | NC & Mednet | Plan 1–6 (Gold→Silk Road) | Employee/SI / Dependant |

| 4 | Individual | HAAD | Abu Dhabi | NAS | Plan 1–6 (Gold→Silk Road) | Employee/SI / Dependant |

| 5 | Individual | HAAD | Abu Dhabi | Aafiya | APN Plus, Essential (2) | Employee/SI |

| 6 | SME | DHA | Dubai & Northern Emirates | NAS, Nextcare, Mednet | Plan 1–6 | Employee / Dependant |

| 7 | SME | HAAD | Abu Dhabi | NAS, Nextcare, Mednet | Plan 1–6 | Employee / Dependant |

| 8 | Basic | HAAD | Abu Dhabi | — | Single plan | Employee / Small Investor / Dependant / Maid |

| 9 | NE Basic | MOH-NE | Northern Emirates | Aafiya APN | Group & Individual | All |

| 10 | NE Enhanced 1 | MOH-NE | Northern Emirates | Aafiya APN | Group & Individual | All |

| 11 | NE Enhanced 2 | MOH-NE | Northern Emirates | Aafiya APN | Group & Individual | All |

 

### Plan Hierarchy — Network Tiers (Highest to Lowest)

 

**DXB/NE — NC & Mednet:**

 

| Plan | NC Network | NAS Network | Mednet Network | Approx. Tier |

|---|---|---|---|---|

| A (GN+) | CN | GN+ | Gold Mednet | Highest |

| B (GN) | GN | CN | Silver Premium | High |

| C (RN) | RN | GN | Silver Classic | Mid-High |

| D (RN2) | RN2 | RN | Green | Mid |

| E (RN3) | RN3 | SRN | Emerald (clinic-restricted) | Lower-Mid |

| F (PCP-RN3) | PCP-RN3 | WN | Pearl (clinic-restricted) | Low |

| G (PCP-C) | PCP-C | VN/VL | Silk Road (clinic-restricted) | Lowest |

 

**DXB/NE — Aafiya:** APN Plus > Essential > APN

 

**AUH Individual & SME (all TPAs):**

 

| Plan | NC Network | NAS Network | Approx. Tier |

|---|---|---|---|

| 1 (Gold / GN+) | GN+ | GN+ (Gold) | Highest |

| 2 (Silver Premium / GN) | GN | GN | High |

| 3 (Silver Classic / RN) | RN | RN | Mid-High |

| 4 (Green / RN2) | RN2 | SRN | Mid |

| 5 (Emerald) | RN3 | WN (Emerald) | Lower-Mid |

| 6 (Silk Road) | PCP-AUH | VN (Silk Road) | Lowest |

 

 

---

 

## §2 — TENDER TEMPLATE STRUCTURE

 

The Marsh Re tender workbook (`UFIC_Tender_Rates.xlsx`) is the instrument through which competing reinsurers submit their rates. Each tendering reinsurer should understand the following structure before completing it.

 

### Workbook Sheet Directory

 

| Sheet | Purpose | Action Required |

|---|---|---|

| **Cover** | Instructions and sheet directory | Read only — no input |

| **Existing Rates** | Cross-check reference — source catalogue rates extracted verbatim, with derived co-pay values and outlier flags | Read only — reference for reinsurer validation |

| **Co-Pay Multipliers** | Pre-filled reference of all co-pay adjustment multipliers by segment | Read only — informs how base rates flow to co-pay variants |

| **Ind Rates - DXB-NE** | Individual Dubai/NE base rates (0% co-pay) — one block per TPA | **Fill yellow cells** — base rates for each plan/age band/gender |

| **Ind Rates - AUH** | Individual Abu Dhabi base rates — one block per TPA | **Fill yellow cells** |

| **SME Rates - DXB-NE** | SME Dubai/NE 0% base rates — NAS, Nextcare, Mednet | **Fill yellow cells** |

| **SME Rates - AUH** | SME Abu Dhabi 0% base rates | **Fill yellow cells** |

| **AUH Basic Rates** | Abu Dhabi Basic single rate table | **Fill yellow cells** |

| **NE Rates** | NE Basic, Enhanced 1, Enhanced 2 | **Fill yellow cells** |

 

### Key Principles for Completing the Template

 

1. **Base rates only (0% / Nil co-pay).** All rate sheets request only the 0% co-pay base rate. Do not embed co-pay variants — these are derived by applying the multipliers from the Co-Pay Multipliers sheet.

 

2. **Co-pay variants are derived, not submitted.** Once the base rate is provided, UFIC/Marsh Re will apply the flat multipliers shown in the Co-Pay Multipliers sheet to generate all co-pay variants. The reinsurer does not need to price each co-pay tier separately.

 

3. **Age bands are fixed.** The age band structure in each rate sheet matches the source catalogue exactly. Do not add or remove age bands.

 

4. **Male / Female columns are separate.** Where applicable, the template has separate columns for Male/Single Female and Married Female. AUH uses M/SF (Male/Single Female) and Married-F columns.

 

5. **Employee/SI and Dependant sections.** AUH Individual sheets have two sub-sections: Employee/Small Investor and Dependants. Both must be completed.

 

6. **NE and AUH Basic are simple tables.** No age-band/gender split beyond what is shown; complete the single premium column.

 

### Rate Submission Dimensions

 

| Segment | Dimensions |

|---|---|

| Ind DXB-NE (NC/NAS/Mednet) | 7 plans × 15 age bands × 2 genders = 210 cells per TPA |

| Ind DXB-NE (Aafiya) | 3 plans × 15 age bands × 2 genders = 90 cells |

| Ind AUH (NC/NAS) | 6 plans × 8 age bands × 2 genders × 2 sections (Emp/Dep) = 192 cells per TPA |

| Ind AUH (Aafiya) | 2 plans × 8 age bands × 2 genders = 32 cells |

| SME DXB-NE / AUH | 6 plans × 8 age bands × 2 genders = 96 cells per TPA × 3 TPAs |

| AUH Basic | 6 member categories × up to 4 age bands = ~20 cells |

| NE Plans | 3 plan tiers × up to 5 age bands = ~15 cells |

 

 

---

 

## §3 — CO-PAY & PRICING MECHANICS

 

### 3.1 Co-Pay Structure by Segment

 

| Segment | Emirate | TPA | Co-Pay Method | Notes |

|---|---|---|---|---|

| Individual | DXB/NE | NC, NAS, Mednet | **Post-hoc factor** — rate table is 0% only; co-pay applied via Factors-Individual lookup | Same factor across all plans/ages/genders |

| Individual | DXB/NE | Aafiya | **Post-hoc factor** — same Factors-Individual lookup | Same as NC/NAS/Mednet |

| Individual | AUH | NC & Mednet | **Pre-computed blocks** — Nil, 10%, 20% blocks sit side-by-side in source | Multiplier is flat: ×0.9450 (10%), ×0.9800 (20%) |

| Individual | AUH | NAS | **Pre-computed blocks** — same structure | ×0.9450 (10%), ×0.9734 (20% intended); 13 source data errors in 20% block |

| Individual | AUH | Aafiya | **Pre-computed blocks** — Nil, 20%, 10% (note order differs in source) | ×0.9800 (10%), ×0.9450 (20%) |

| SME | DXB/NE | All TPAs | **Post-hoc factor** — rate table is 0% only; Factors-SME lookup | Flat multiplier across all dimensions |

| SME | AUH | All TPAs | **Post-hoc factor** — Factors-SME lookup | Flat multiplier |

| AUH Basic | AUH | — | **No co-pay variant** — single rate | N/A |

| NE Plans | NE | Aafiya | **No co-pay variant** — single rate | N/A |

 

**Key Principle:** All co-pay adjustments across every segment are flat multipliers — the same scalar applies to every plan, age band, and gender. There is no cell-specific variation. This means the reinsurer only needs to price the 0% base.

 

### 3.2 Co-Pay Adjustment Multipliers — Individual DXB/NE (Factors-Individual sheet)

 

#### OP Diagnostic Co-Pay

 

| Co-Pay Option | Multiplier |

|---|---|

| 0% | 1.000 |

| 10% | 0.960 |

| 20% | 0.920 |

| AED 10 | 0.997 |

| AED 20 | 0.9939 |

| AED 50 | 0.9848 |

| AED 100 | 0.9696 |

 

#### Consultation Deductible

 

| Deductible | Multiplier |

|---|---|

| Nil | 1.100 |

| AED 20 | 1.050 |

| AED 50 (standard) | 1.000 |

| AED 100 | 0.9637 |

| 20% up to AED 20 | 1.030 |

| 20% up to AED 50 (standard) | 1.000 |

| 20% up to AED 75 | 0.9855 |

| 20% up to AED 100 | 0.9822 |

| 10% up to AED 20 | 1.050 |

| 10% up to AED 50 | 1.025 |

| 10% up to AED 75 | 1.010 |

| 10% up to AED 100 | 1.0097 |

| 10% flat | 1.085 |

 

#### Pharmacy Co-Pay

 

| Co-Pay | Multiplier |

|---|---|

| 0% | 1.000 |

| 10% | 0.980 |

| 20% | 0.960 |

| 30% | 0.940 |

 

#### Annual Medical Limit Adjustment (Individual — by network tier)

 

| AML | GN+ | GN | RN | RN2 | RN3 | PCP-RN3 |

|---|---|---|---|---|---|---|

| AED 150,000 | 0.8901 | 0.9333 | 0.9469 | 0.9800 | 0.9800 | 0.9800 |

| AED 250,000 | 0.9083 | 0.9524 | 0.9662 | 1.0000 | 1.0000 | 1.0000 |

| AED 500,000 | 0.9401 | 0.9857 | 1.0000 | 1.0350 | 1.0350 | 1.0350 |

| AED 1,000,000 (standard) | 0.9537 | 1.0000 | 1.0145 | 1.0500 | 1.0500 | 1.0500 |

| AED 1,500,000 | 1.0000 | 1.0486 | 1.0638 | 1.1010 | 1.1010 | 1.1010 |

 

#### Network Option Factor (DXB Plans B & C — Option 2 vs Option 1)

 

| Option | Plan B | Plan C |

|---|---|---|

| Option 1 (standard) | 1.00 | 1.00 |

| Option 2 (split IP/OP networks) | 0.86 | 0.89 |

 

#### TPA Factor

 

| TPA | Factor |

|---|---|

| NAS | 1.00 |

| Mednet | 1.00 |

| Nextcare | 0.90 |

 

#### Nationality Loading Factor

 

| Nationality Group | Factor |

|---|---|

| India / Bangladesh / Pakistan | 0.90 |

| Philippines | 0.925 |

| Egypt, Jordan, Syria, Palestine, Lebanon | 1.20 |

| All others | 1.00 |

 

#### Maternity Add-On Rates (net premium per eligible female, by network)

 

| IP Limit | GN+ | GN | RNE | RN | RN2 | RN3/PCP |

|---|---|---|---|---|---|---|

| AED 10,000 | 1,852.60 | 1,691.76 | 1,679.07 | 1,662.89 | 1,662.32 | 1,579.21 |

| AED 15,000 | 2,487.17 | 2,271.24 | 2,222.71 | 2,132.48 | 2,130.48 | 2,025.86 |

| AED 20,000 | 3,264.42 | 2,981.00 | 2,931.95 | 2,830.13 | 2,829.13 | 2,687.67 |

| AED 25,000 | 4,818.90 | 4,400.52 | 4,387.74 | 4,325.44 | 4,323.96 | 4,107.76 |

| Annual limit (AML) | 3,139.70 | 3,005.79 | 2,780.06 | 2,619.83 | 2,191.31 | 2,081.74 |

 

### 3.3 Co-Pay Adjustment Multipliers — SME (Factors-SME sheet)

 

#### OP Diagnostic Co-Pay

 

| Co-Pay | Multiplier |

|---|---|

| 0% | 1.000 |

| 10% | 0.960 |

| 20% | 0.920 |

| AED 10 | 0.997 |

| AED 20 | 0.9939 |

| AED 50 | 0.9848 |

| AED 100 | 0.9696 |

| 10% up to AED 50 | 0.9888 |

| 20% up to AED 50 | 0.9853 |

 

#### IP/Day-Case Co-Pay (Abu Dhabi SME)

 

| Co-Pay | Multiplier |

|---|---|

| Nil | 1.000 |

| 10% | 0.980 |

| 20% | 0.960 |

| 30% | 0.940 |

| AED 200 deductible (cap AED 500 p.a.) | 0.970 |

 

#### Pharmacy Limit Adjustment (SME)

 

| Pharmacy Limit | Multiplier |

|---|---|

| AML (unlimited) | 1.000 |

| AED 5,000 | 0.950 |

| AED 7,000 | 0.960 |

 

#### SME Pharmacy Co-Pay

 

| Co-Pay | Multiplier |

|---|---|

| 0% | 1.000 |

| 10% | 0.980 |

| 20% | 0.960 |

| 30% | 0.940 |

 

### 3.4 AUH Individual — Pre-Computed Block Multipliers

 

These are the exact flat multipliers confirmed by cell-by-cell analysis of the source workbook:

 

| Segment | TPA | 0%→10% | 0%→20% | Notes |

|---|---|---|---|---|

| Ind AUH | NC & Mednet | ×0.9450 | ×0.9800 | Perfect — zero deviation across all 180 cells |

| Ind AUH | NAS | ×0.9450 | ×0.9734 (intended) | 10% clean; 20% has 13 erroneous source cells |

| Ind AUH | Aafiya | ×0.9800 | ×0.9450 | Perfect — note reversed direction vs NC/NAS |

 

> **Note on direction:** Higher co-pay = smaller premium discount. This follows HAAD methodology — the insured bears more direct cost, so the net premium reduction to the insurer is modest.

 

### 3.5 Known Source Data Errors (NAS AUH 20% Block)

 

The following 13 cells in the NAS AUH 20% block contain erroneous values (ratios of 0.99–1.63 vs expected ×0.9734). These are confirmed copy-paste errors in the original catalogue and are flagged RED in the Existing Rates tab of the tender workbook:

 

| Age Band | Gender | Plan | Source 0% | Source 20% | Ratio | Expected (×0.9734) |

|---|---|---|---|---|---|---|

| 60+ | Married-F | Silver Premium | 14,145.55 | 15,931.57 | 1.126 | 13,769.99 |

| 60+ | Married-F | Silver Classic | 9,104.18 | 14,809.81 | 1.627 | 8,861.01 |

| 60+ | Married-F | Green | 8,699.20 | 14,091.16 | 1.620 | 8,469.20 |

| 60+ | M/SF | Emerald | 6,066.99 | 6,986.81 | 1.152 | 5,907.61 |

| 00-17 | Dep | Emerald | 1,348.24 | 1,333.94 | 0.989 | 1,312.75 |

| 18-30 | Dep | Emerald | 1,579.41 | 1,645.47 | 1.042 | 1,537.74 |

| 31-40 | Dep | Emerald | 1,658.38 | 2,154.93 | 1.299 | 1,614.72 |

| 60+ | Married-F | Emerald | 8,642.34 | 13,819.52 | 1.599 | 8,414.67 |

| 60+ | M/SF | Silk Road | 4,238.99 | 6,397.17 | 1.509 | 4,127.26 |

| 00-17 | Dep | Silk Road | 1,276.29 | 1,298.88 | 1.018 | 1,242.73 |

| 18-30 | Dep | Silk Road | 1,512.76 | 1,580.59 | 1.045 | 1,473.52 |

| 31-40 | Dep | Silk Road | 1,588.39 | 1,654.21 | 1.041 | 1,546.27 |

| 60+ | Married-F | Silk Road | 8,378.00 | 13,237.78 | 1.580 | 8,155.41 |

 

> **Tender implication:** Reinsurers should use the corrected derived values (Nil × 0.9734) for these cells, not the erroneous source values.

 

 

---

 

## §4 — TABLE OF BENEFITS: Individual — Dubai & Other Emirates (NC / NAS / Mednet)

 

> **Segment:** Individual | **Emirate:** Dubai / Other Emirates | **Regulator:** DHA | **TPA:** NC (Nextcare), NAS, Mednet 

> **Plans:** A (highest) → G (lowest) — mapped to networks GN+, GN, RN, RN2, RN3, PCP-RN3, PCP-C

 

### 4.1 Core Benefits Summary

 

| Benefit | Plans A–E | Plan F | Plan G |

|---|---|---|---|

| Aggregate Annual Limit | AED 1,000,000 | AED 750,000 | AED 500,000 |

| Room Type | Private | Private | Private |

| Territorial Scope | Worldwide (max 90 days/trip outside UAE) | Worldwide (max 90 days/trip) | Worldwide (max 90 days/trip) |

| Pre-existing & Chronic | Covered up to AED 150,000 PMPY — MAF required; 6-month waiting period (waived with COC) | Same | Same |

| Emergency Road Ambulance | Covered | Covered | Covered |

| Emergency Dental | Covered | Covered | Covered |

| Emergency Vision/Hearing | Covered | Covered | Covered |

 

### 4.2 Out-Patient Benefits

 

| Benefit | Plans A–D | Plan E | Plans F–G |

|---|---|---|---|

| Consultation Deductible | 20% up to AED 50 | 20% up to AED 50 | 20% up to AED 50 (GP referral required for Specialist) |

| OP Diagnostic (Lab, X-ray, MRI, CT, Ultrasound, Endoscopy) | Covered — Nil / 10% / 20% co-pay options | Same | Same |

| Prescribed Drugs & Medicines | Covered — Nil / 10% / 20% / 30% co-pay options | Same | Same |

| Physiotherapy | 15 sessions PMPA, 10% co-pay, subject to pre-approval | Same | Same |

| Specialist Access | Direct (no GP referral required) | Direct | GP referral required |

| Tele-Health | Covered | Covered | Covered |

 

### 4.3 In-Patient Benefits

 

| Benefit | All Plans A–G |

|---|---|

| IP Hospitalization | Covered up to Annual Aggregate Limit |

| Surgery, Anaesthesia | Covered |

| ICU / Emergency Ward | Covered |

| Day Care Treatment | Covered |

| Parent Accommodation (child <18) | AED 100/day |

| Companion Accommodation (medical necessity) | AED 100/day |

| Internal Surgical Appliances & Prosthesis | Covered if surgically required |

 

### 4.4 Maternity (All Plans)

 

| Benefit | Plans A–B | Plans C–F | Plan G |

|---|---|---|---|

| IP Maternity | Covered, 10% co-insurance, up to AED 10,000 | Same | Same |

| OP Maternity Visits | Max 15 visits, 8 ante-natal ultrasounds | Max 12 visits, 6 scans (C–F) / 10 visits, 4 scans (G) | 10 visits, 4 scans |

| New Born Cover | 30 days from birth | Same | Same |

 

### 4.5 Additional Benefits (All Plans)

 

| Benefit | Cover |

|---|---|

| Organ Transplant | Up to AED 100,000 PMPA — recipient costs only; heart, lung, kidney, pancreas, liver, bone marrow |

| Alternative Medicine (Chiro, Osteo, Homeo, Ayurvedic) | Up to AED 1,600 PMPY — reimbursement only |

| Repatriation of Mortal Remains | Up to AED 7,500 PMPA — no co-pay |

| International Assistance Services | Covered |

| Dental (Free Access) | Plans A–F: up to AED 3,500 with 20% co-pay; Plan G: up to AED 500 with 20% co-pay |

| Cancer Treatment (DHA Patient Support Programme) | Covered per DHA programme terms |

| HCV / Hepatitis C (DHA Patient Support Programme) | Covered per DHA programme terms |

| Hepatitis B | Covered per DHA programme terms |

| Influenza Vaccine | Once per annum, reimbursement only |

| Shingrix Vaccine | Covered for DHA-eligible members only |

| Adult Pneumococcal Vaccine | Per DHA adult vaccination guidelines |

| Preventive Services | Per DHA regulations |

| Child Vaccinations | In-network: 100% actual cost; Out-of-network: network UCR rates |

 

### 4.6 Claims Settlement

 

| Scenario | Basis |

|---|---|

| Within network | Direct billing, applicable co-pay |

| Outside network, within UAE | Reimbursement at 80% of UCR rates of selected network |

| Outside UAE | Reimbursement at 100% of actual cost or 100% of UAE UCR, whichever is less |

 

---

 

## §5 — TABLE OF BENEFITS: Individual — Dubai & Other Emirates (Aafiya)

 

> **Segment:** Individual | **Emirate:** Dubai / Other Emirates | **Regulator:** DHA | **TPA:** Aafiya 

> **Plans:** APN Plus (highest) > Essential > APN (lowest)

 

Benefits structure mirrors §4 (NC/NAS/Mednet) for Plans A–G equivalents. Key differences:

 

| Benefit | APN Plus | Essential | APN |

|---|---|---|---|

| Network | Aafiya APN Plus | Aafiya Essential | Aafiya APN |

| Aggregate Annual Limit | AED 1,000,000 | AED 1,000,000 | AED 500,000 |

| OP Co-pay | Nil / 10% / 20% options via Factors-Individual | Same | Same |

| Consultation Deductible | As per Factors-Individual | Same | Same |

| Maternity | Covered with 10% co-insurance | Same | Same |

| Co-pay multipliers | 10%: ×0.9800 | — | — |

| Co-pay multipliers | 20%: ×0.9450 | — | — |

 

> Note: Aafiya AUH multipliers are directionally reversed vs NC/NAS (10% discount is smaller at ×0.980, 20% discount is larger at ×0.945).

 

---

 

## §6 — TABLE OF BENEFITS: Individual — Abu Dhabi (NC & Mednet, NAS, Aafiya)

 

> **Segment:** Individual | **Emirate:** Abu Dhabi | **Regulator:** HAAD | **TPA:** NC & Mednet / NAS / Aafiya 

> **Plans:** Plan 1 (Gold/GN+) → Plan 6 (Silk Road) for NC & NAS; APN Plus + Essential for Aafiya

 

### 6.1 General Terms (All AUH Individual Plans)

 

| Benefit | All Plans |

|---|---|

| Territorial Scope | Worldwide — emergency IP abroad up to 45 days/trip at 100% UAE equivalent cost; non-emergency abroad at 80% UAE equivalent cost |

| Pre-existing & Chronic | Covered up to Annual Benefit Limit PMPY — MAF required for all members; 6-month waiting period (waived with COC) |

| IP Room Type | Plan 1: Private; Plan 2: Private; Plan 3: Private; Plan 4: Semi-Private; Plans 5–6: Shared |

 

### 6.2 In-Patient Benefits

 

| Benefit | Plans 1–6 |

|---|---|

| IP Hospitalization, Surgery, ICU | Covered up to Annual Benefit Limit (AML) |

| Day Care | Covered |

| IP Co-pay (Abu Dhabi) | Options: Nil / 10% / 20% / 30% / AED 200 deductible (cap AED 500) — per Factors-SME IP table |

| Physiotherapy (IP-linked, AUH) | No capping in Abu Dhabi; outside AUH: Plans 1→15 sessions / Plan 2→10 / Plans 3–6→6 sessions |

| Companion Accommodation (child <16) | Plan 1–2: AED 500/day; Plan 3: AED 300/day; Plans 4–6: AED 250/day |

| Companion Accommodation (critical, medical necessity) | Same as above |

 

### 6.3 Out-Patient Benefits

 

| Benefit | Plans 1–5 | Plan 6 |

|---|---|---|

| Consultation Deductible | Options per Factors sheet | Same (GP referral required for Specialist) |

| OP Diagnostic Co-Pay | Options: 0% / 10% / 20% / AED fixed amounts | Same |

| Specialist Access | Direct (no GP referral) | GP referral required |

| Prescribed Medicines | Covered — Branded medicines; limit options; co-pay options | Same |

| Pharmacy Co-pay | Options per Factors-SME sheet | Same |

| Physiotherapy (OP) | Plans 1→20 sessions; Plan 2→12; Plans 3–6→6 sessions; 10%–20% co-insurance | Same (6 sessions, 20% co-ins) |

| Tele-Health | Covered | Covered |

 

### 6.4 Maternity (AUH Plans)

 

| Benefit | Plans 1–6 |

|---|---|

| IP Maternity | Covered — subject to MAF and HAAD guidelines |

| OP Antenatal Visits | Covered — visits and scans per HAAD Antenatal Care Protocols |

| New Born | As per HAAD requirements |

 

### 6.5 Additional Benefits (AUH Plans)

 

| Benefit | Cover |

|---|---|

| Dental | Covered — emergency cases only, as per HAAD |

| Vision / Hearing | Emergency cases only |

| Organ Transplant | As per HAAD |

| Alternative Medicine | As per HAAD |

| Repatriation | As per HAAD |

| Oncology / Cancer | As per HAAD Patient Support Programme |

| Vaccination (children) | As per HAAD schedule |

| Preventive Services | As per HAAD |

 

 

---

 

## §7 — TABLE OF BENEFITS: SME — Dubai / Northern Emirates (All TPAs)

 

> **Segment:** SME | **Emirate:** Dubai / Other Emirates / Northern Emirates | **Regulator:** DHA 

> **TPA:** NAS, Nextcare, Mednet | **Plans:** 1 (highest) → 6 (lowest) | **Group Size:** 3–200 employees

 

### 7.1 General Terms

 

| Parameter | Detail |

|---|---|

| Annual Benefit Limit | Plan 1–2: AED 1,000,000; Plan 3: AED 500,000; Plans 4–6: AED 250,000 |

| Coverage Type | IP + OP |

| Territorial Scope | Worldwide — emergency IP abroad at 100% UAE equivalent cost; non-emergency at 80% UAE equivalent cost; max 45 days per trip |

| Pre-existing & Chronic | Covered up to ABL PMPY — MAF required for groups <20 members or <10 employees; 6-month waiting period (waived with COC); no waiting period for groups ≥11 employees |

 

### 7.2 In-Patient Benefits

 

| Benefit | Plan 1 | Plan 2 | Plan 3 | Plan 4 | Plan 5 | Plan 6 |

|---|---|---|---|---|---|---|

| IP Room Type | Private | Private | Private | Semi-Private | Shared | Shared |

| IP Co-pay (DXB) | Options — see Factors-SME | Same | Same | Same | Same | Same |

| IP Hospitalization, Surgery, Day Care, ICU | Up to AML | Up to AML | Up to AML | Up to AML | Up to AML | Up to AML |

| Physiotherapy (IP-linked, post-procedure) | 15 sessions outside AUH | 10 sessions | 6 sessions | 6 sessions | 6 sessions | 6 sessions |

| Companion Accommodation (child <16) | AED 500/day | AED 500/day | AED 300/day | AED 250/day | AED 250/day | AED 250/day |

| Companion Accommodation (critical) | AED 500/day | AED 500/day | AED 300/day | AED 250/day | AED 250/day | AED 250/day |

 

### 7.3 Out-Patient Benefits

 

| Benefit | Plans 1–5 | Plan 6 |

|---|---|---|

| Consultation Deductible | Options per Factors-SME | Same |

| Specialist Access | Direct (no GP referral) | GP referral required |

| OP Diagnostic Co-Pay | Options per Factors-SME | Same |

| Prescribed Medicines | Branded medicines; limit options; co-pay options | Same |

| Physiotherapy (OP) | Plan 1→20 sessions; Plan 2→12; Plans 3–6→6 sessions | 6 sessions |

| Tele-Health | Covered | Covered |

 

### 7.4 Optional Add-On Benefits (DXB/NE/AUH — rates additive to base)

 

These are priced separately via the SME Factors sheet and added to base rates:

 

| Add-On | Plans Available | Limits Available | Note |

|---|---|---|---|

| Dental | All plans | AED 1,000 / 2,000 / 2,500 / 3,000 / 3,500 / 5,000 / 7,500 / 10,000 | 20% co-pay; separate net premium per plan/limit |

| Optical | All plans | AED 300 / 500 / 750 / 1,000 / 1,500 / 2,000 / 2,500 | 20% co-pay; separate net premium per plan/limit |

| Maternity | All plans | AED 10,000 / 15,000 / 20,000 / 25,000 / AML | Per eligible female; separate net premium by plan |

 

**Dental net premiums by plan (AED, 20% co-pay):**

 

| Limit | Plan 1 | Plan 2 | Plan 3 | Plan 4–6 |

|---|---|---|---|---|

| AED 1,000 | 381.57 | 252.99 | 135.43 | 98.10 |

| AED 2,000 | 419.31 | 278.01 | 148.82 | 107.80 |

| AED 2,500 | 532.52 | 353.08 | 189.00 | 136.91 |

| AED 3,000 | 570.26 | 378.10 | 202.39 | 146.61 |

| AED 3,500 | 612.19 | 405.90 | 217.28 | 157.39 |

| AED 5,000 | 725.40 | 480.96 | 257.46 | 186.50 |

| AED 7,500 | 800.88 | 531.01 | 284.24 | 205.90 |

| AED 10,000 | 1,017.52 | 674.65 | 361.13 | 261.60 |

 

**Optical net premiums by plan (AED, 20% co-pay):**

 

| Limit | Plan 1 | Plan 2 | Plan 3 | Plan 4–6 |

|---|---|---|---|---|

| AED 300 | 104.27 | 86.87 | 46.83 | 25.20 |

| AED 500 | 155.19 | 129.30 | 69.70 | 37.51 |

| AED 750 | 208.54 | 173.74 | 93.65 | 50.40 |

| AED 1,000 | 242.48 | 202.03 | 108.90 | 58.60 |

| AED 1,500 | 312.80 | 260.62 | 140.48 | 75.60 |

| AED 2,000 | 346.75 | 288.90 | 155.73 | 83.80 |

| AED 2,500 | 380.70 | 317.18 | 170.97 | 92.01 |

 

---

 

## §8 — TABLE OF BENEFITS: SME — Abu Dhabi (All TPAs)

 

> **Segment:** SME | **Emirate:** Abu Dhabi | **Regulator:** HAAD 

> **TPA:** NAS, Nextcare, Mednet | **Plans:** 1–6 | Same plan hierarchy as DXB SME

 

Core benefits mirror §7 with the following HAAD-specific differences:

 

| Parameter | HAAD-Specific Rule |

|---|---|

| IP Room Type | Plans 1–3: Private; Plan 4: Semi-Private; Plans 5–6: Shared |

| IP Co-pay Options | Nil / 10% / 20% / 30% / AED 200 deductible (cap AED 500) — per Factors-SME IP/Day-case table |

| Physiotherapy (IP, AUH) | No capping within Abu Dhabi; outside AUH subject to plan limits |

| Pharmacy | Branded medicines only |

| Specialist Access (Plan 6) | GP referral required |

| Pre-existing Conditions | Same as DXB — 6-month waiting period, waived with COC |

| MAF requirement | Members >65 years always; groups <20 members or <10 employees always |

 

Optional add-ons (Dental, Optical, Maternity) apply identically as per §7.4.

 

---

 

## §9 — TABLE OF BENEFITS: Abu Dhabi Basic Plan

 

> **Segment:** Basic | **Emirate:** Abu Dhabi | **Regulator:** HAAD 

> **TPA:** — (direct) | **Target:** Low-income AUH visa holders, salary ≤ AED 5,000

 

### 9.1 Eligibility Summary

 

| Member Category | Conditions |

|---|---|

| Employee | AUH employment visa holder, salary ≤ AED 5,000 |

| Small Investor | AUH self-sponsor visa holder |

| Dependant by Employee | Additional wives, children >18 not employed, children >3rd, family sponsored by individual resident — AUH visa only, non-employed |

| Dependant by Individual | Same eligibility as above — sponsored by individual (not company) |

| Maid (Non-UAE Sponsored) | Domestic helpers (maid, cook, driver, nanny etc.) sponsored by non-UAE national resident — AUH visa, salary <AED 5,000 |

| Maid (UAE Sponsored) | Same designations — sponsored by UAE national — AUH visa, salary <AED 5,000 |

 

> Investors and golden visa holders are excluded. Product is **not** available to company-sponsored members except employees meeting the salary cap.

 

### 9.2 Rate Table (Gross Premium, subject to loading defined in UW Guidelines)

 

| Category | Age Band | Gross Premium (AED) |

|---|---|---|

| Employee | 18–40 | 998 |

| Employee | 41–59 | 1,523 |

| Employee | 60+ | 8,674 |

| Small Investor | 18–40 | 2,835 |

| Small Investor | 41–59 | 3,465 |

| Small Investor | 60+ | 8,673 |

| Dependant by Employee | 0–17 | 1,754 |

| Dependant by Employee | 18–40 | 2,100 |

| Dependant by Employee | 41–59 | 4,988 |

| Dependant by Employee | 60+ | 18,072 |

| Dependant by Individual | 0–17 | 1,523 |

| Dependant by Individual | 18–40 | 2,100 |

| Dependant by Individual | 41–59 | 7,172 |

| Dependant by Individual | 60+ | 18,072 |

| Maid (Non-UAE Sponsored) | 18–40 | 920 |

| Maid (Non-UAE Sponsored) | 41–59 | 1,922 |

| Maid (Non-UAE Sponsored) | 60+ | 8,673 |

| Maid (UAE Sponsored) | 18–40 | 750 |

| Maid (UAE Sponsored) | 41–59 | 750 |

| Maid (UAE Sponsored) | 60+ | 8,673 |

 

### 9.3 Benefits

 

Benefits as per HAAD essential benefits package for low-income members. No co-pay variants — single rate table only. No optional add-ons.

 

---

 

## §10 — TABLE OF BENEFITS: Northern Emirates — Compulsory Basic Plan

 

> **Segment:** NE Basic | **Emirate:** Northern Emirates (Sharjah, Ajman, Fujairah, RAK, UAQ) 

> **Regulator:** MOH-NE | **TPA:** Aafiya APN/NE | **Policy Type:** Group & Individual 

> **Compulsory:** Yes — per Ministry of Labour List

 

### 10.1 Rate Table

 

| Category | Age Band | Net Premium (AED) |

|---|---|---|

| Employee & Dependants | 00–64 | 256 |

| Partners & Investors | 00–64 | 386 |

| Parents / Parents-In-Law (With MAF) | 64+ | Refer to Optio Re |

 

### 10.2 Key Benefits

 

| Benefit | Cover |

|---|---|

| Annual Upper Aggregate Limit | IP: AED 50,000 / OP: AED 10,000 |

| Geographic Scope | Northern Emirates only — on UAE Network tariff for NE |

| Network | Aafiya APN/NE |

| OP Access | Clinics only within agreed network |

| IP Access | Authorized network hospitals only |

| Pre-existing Conditions | Covered without waiting period |

| Maternity | Not Covered |

| Dental | Not Covered |

| IP Co-pay | 20% co-insurance; cap AED 500/encounter, AED 1,000 annual aggregate — above caps insurer covers 100% |

| IP Room Type | Semi-Private |

| OP Consultation | 25% co-insurance per visit, max AED 100; no co-pay for follow-up within 7 days |

| OP Diagnostics / Radiology | 25% co-insurance |

| OP Laboratory | 25% co-insurance |

| Physiotherapy | Up to 6 sessions/year, 25% co-insurance |

| Pharmacy | Up to AED 1,500; 30% co-insurance; formulary only |

| Tele-Health | Covered — Nil co-pay for consultations and lab; pharmacy excluded |

| GP Referral Requirement | GP referral required for specialist access |

| Reimbursement (outside network) | Not covered |

| Reimbursement (outside UAE) | Not covered |

| Loading Cap | 25% |

 

---

 

## §11 — TABLE OF BENEFITS: Northern Emirates — Enhanced Plan 1

 

> **Segment:** NE Enhanced 1 | **Emirate:** Northern Emirates | **Regulator:** MOH-NE 

> **TPA:** Aafiya APN | **Policy Type:** Group & Individual

 

### 11.1 Rate Table

 

| Age Band | Net Premium (AED) |

|---|---|

| 0–17 | 206.36 |

| 18–45 | 224.46 |

| 46–59 | 234.21 |

| 60–64 | 835.73 |

| Above 64 | Refer to Optio Re |

 

### 11.2 Key Benefits

 

| Benefit | Cover |

|---|---|

| Annual Aggregate Limit | AED 50,000 (inclusive of co-pay) |

| Geographic Scope | UAE excluding Dubai & Abu Dhabi |

| Elective Treatment | IP/OP within NE network only — direct billing; reimbursement not covered |

| Emergency Outside UAE | Not Covered |

| Network | Aafiya APN |

| OP Access | Clinics only within agreed network |

| IP Sublimit | AED 40,000; AED 10,000 per admission |

| IP Room Type | Shared (two beds or more) |

| IP Co-pay | 20% co-insurance up to AED 500 per admission |

| OP Sublimit | AED 10,000 |

| OP Consultation (GP) | 25% co-pay up to AED 100; follow-up within 7 days exempt |

| OP Consultation (Specialist) | GP referral required |

| OP Diagnostics | 25% co-insurance |

| OP Laboratory | 25% co-insurance |

| Physiotherapy | Not Covered |

| Pharmacy | 30% co-insurance; AED 1,500 annual limit; formulary only; pre-approval required |

| Pre-existing / Chronic | Covered — 9-month waiting period; AED 1,500 annual limit after waiting period |

| Maternity | Not Covered |

| Dental | Not Covered (50% discount at specific providers) |

| Oncology / Cancer | Not Covered |

| HIV / Hepatitis / STD | Not Covered |

| Vision / Hearing | Not Covered |

| Loading Cap | 30% |

 

---

 

## §12 — TABLE OF BENEFITS: Northern Emirates — Enhanced Plan 2 (Aafiya APN)

 

> **Segment:** NE Enhanced 2 | **Emirate:** Northern Emirates | **Regulator:** MOH-NE 

> **TPA:** Aafiya APN (lowest network) | **Policy Type:** Group & Individual 

> **Note:** Net premiums subject to review after 3 months per RI agreement

 

### 12.1 Rate Table

 

| Age Band | Net Premium (AED) |

|---|---|

| 00–64 | 172.50 |

| 65–74 | 420.00 |

| 75–90 | 626.25 |

 

### 12.2 Key Benefits

 

| Benefit | Cover |

|---|---|

| Annual Limits | IP: AED 20,000; OP: AED 5,000 |

| Network | Aafiya APN (lowest) |

| Territorial Limit | Northern Emirates visa holders (Sharjah, Ajman, UAQ, RAK, Fujairah) |

| Direct Billing | 100% subject to applicable co-pay |

| Reimbursement (outside network, inside UAE) | Not Covered |

| Reimbursement (outside UAE) | Not Covered |

| Pre-existing & Chronic | Covered — 12-month waiting period; sublimit AED 3,000 IP / AED 1,000 OP after waiting period |

| IP (emergency only) | Sublimit AED 20,000; AED 5,000 per admission |

| IP Room Type | General Ward |

| IP Co-pay | 30% inclusive co-insurance |

| IP GP Referral | Required before specialist |

| OP Consultation | AED 30 deductible (GP) / AED 60 (Specialist on referral); max 4 GP visits/year |

| OP Diagnostics | 30% inclusive co-insurance; MRI/CT/Endoscopy require pre-authorization |

| Pharmacy | 30% co-insurance; AED 1,000 annual limit; formulary only |

| Maternity | Not Covered |

| Vaccinations | Not Covered |

| Oncology / Cancer | Not Covered |

| HIV / Hepatitis / STD | Not Covered |

| Vision / Hearing | Not Covered |

| New Born | Not Covered |

| Work Related Injury | Not Covered |

| Loading Cap | 25% |

 

 

---

 

## §13 — OPTIONAL BENEFIT ADD-ONS: SME (DXB / NE / AUH)

 

> These add-on premiums are **additive** to the base rate. They apply to both principals and dependants across all DXB, NE, and AUH SME plans.

 

### Maternity Add-On Rates (AED net premium per eligible female)

 

| IP Limit | Plan 1 (GN+) | Plan 2 (GN) | Plan 3 (RNE) | Plan 4 (RN) | Plan 5 (RN2) | Plan 6 (RN3/PCP) |

|---|---|---|---|---|---|---|

| AED 10,000 | 1,852.60 | 1,691.76 | 1,679.07 | 1,662.89 | 1,662.32 | 1,579.21 |

| AED 15,000 | 2,487.17 | 2,271.24 | 2,222.71 | 2,132.48 | 2,130.48 | 2,025.86 |

| AED 20,000 | 3,264.42 | 2,981.00 | 2,931.95 | 2,830.13 | 2,829.13 | 2,687.67 |

| AED 25,000 | 4,818.90 | 4,400.52 | 4,387.74 | 4,325.44 | 4,323.96 | 4,107.76 |

| Annual Limit | 3,139.70 | 3,005.79 | 2,780.06 | 2,619.83 | 2,191.31 | 2,081.74 |

 

---

 

## §14 — UNDERWRITING GUIDELINES

 

### 14.1 Individual Plans (DXB / NE / AUH — all TPAs)

 

| Rule | Detail |

|---|---|

| Eligibility | UAE visa holders only |

| MAF requirement | Mandatory for **all** members and all ages |

| MAF process | Forms completed → shared with TPA → referred to Optio Re for review/approval |

| Pre-existing waiting period | 6 months for first UAE scheme; waived with proof of continuous coverage ≥6 months (COC required) |

| Major condition declarations | Refer to Optio Re |

| Multiple declarations (>2) | Refer to Optio Re |

| Claim referral threshold | Claims >AED 15,000: refer to Optio Re for all TPAs; claims >AED 50,000: refer to Optio Re for Nextcare TPA |

| Benefit changes | Any change to fixed ToB must be referred to Optio Re |

| Standard exclusions | DHA / AUH exclusion list applicable |

| Applicable networks | Per ToB — no deviation without Optio Re approval |

| Price review | Rates subject to quarterly review and adjustment |

| Maximum loading | Nextcare & Mednet TPA: 32.5%; NAS TPA: 30%; Aafiya TPA: 30% |

| Auto-loading | UFIC auto-loads based on Digital MAF logic approved by Optio Re; complex cases referred to Optio Re |

 

### 14.2 SME Plans (DXB / NE / AUH — all TPAs)

 

| Rule | Detail |

|---|---|

| Minimum group size | 3 employees and 5 members total |

| Maximum group size | 200 insured members (>200 → refer to Optio Re) |

| MAF requirement | Groups <20 members or <10 employees: MAF for all; groups ≥11 employees: no UW required |

| Members >65 years | MAF always required; refer to Optio Re |

| Sub-category limits | 5–15 insured: 1 category; 16–30: up to 2 categories; 31–200: up to 3 categories |

| MOL (Ministry of Labour) | Compulsory for all SME groups; deviations >±5% → refer to Optio Re for repricing |

| Eligibility | UAE visa holders only |

| Groups requiring referral | Outside UAE; Universities/Schools; Nurseries; Hospitals/Medical centres; Military; Government; Sports clubs; TPAs; Insurance companies; Insurance-affiliated groups; Groups with >30% members outside UAE |

| Claim referral | Same as Individual: >AED 15,000 all TPAs; >AED 50,000 Nextcare |

| Benefit changes | All changes to fixed ToB → Optio Re |

| Pre-existing waiting period | 6 months (first UAE scheme); waived with COC |

| Standard exclusions | DHA / AUH exclusion list applicable |

| Maximum loading | 25% for all TPAs |

| SME + PI split | Where a cedant books an account part under SME and part under PI, the same reinsurer must be on both policies |

| **Renewal Guidelines** | |

| Auto-renewal trigger | NLR ≤ 75%: renew at expiring rates/benefits |

| Referral trigger | NLR > 75%: refer to Optio Re |

| NLR definition | (Paid Claims + Outstanding Claims + IBNR 30 days) ÷ Net Earned Reinsurance Premium |

 

### 14.3 Abu Dhabi Basic Plan

 

| Rule | Detail |

|---|---|

| Eligibility | AUH employment or self-sponsor visa; salary ≤ AED 5,000; non-employed dependants and domestic workers only |

| Excluded | Investors, golden visa holders, company-sponsored above salary cap |

| MAF | Mandatory with Labour contract to verify eligibility |

| Individual/Domestic loading cap | 24% (reviewed after 3 months); Optio Re may adjust rates or reduce loading to where NLR >90% |

| Group loading cap | Inception: 20% provisional; reviewed after 3 months; Optio Re may adjust if NLR >90% or reduce to 15% |

| Group eligibility | Full scheme required; minimum 150 members, maximum 500 members |

| Broker commission | If account is not through a broker, commission must be retained under Net Premium |

| NLR definition | Claims (Paid + Outstanding + IBNR) ÷ Net Earned Reinsurance Premium |

 

### 14.4 Northern Emirates Plans

 

| Rule | Detail |

|---|---|

| Eligibility | Non-Abu Dhabi / non-Dubai UAE visa holders only |

| Compulsory | Per Ministry of Labour List (Basic plan) |

| Groups requiring referral | Universities/Schools, Nurseries, Hospitals, Medical centres, Military, Government, Associations, Sports clubs, TPAs, Insurance companies, affiliated groups, groups with >30% outside UAE |

| Members >64 years | MAF required; refer to reinsurer |

| Claim referral threshold | Claims >AED 5,000 → refer to reinsurer |

| Standard exclusions | Applicable |

| Pharmacy | MOH-approved formulary drug list only |

| Parent proof | Proof of parent's insurance mandatory for child-alone policy |

| Premium refund | No refund in first year — non-refundable |

| Additions | Added at full annual premium |

| Maximum loadings | Basic: 25%; Enhanced 1: 30%; Enhanced 2: 25% |

 

---

 

## §15 — KNOWN DATA QUALITY ISSUES

 

| Issue | Segment | Location | Detail | Action |

|---|---|---|---|---|

| NAS AUH 20% block — 13 erroneous cells | Ind AUH NAS | Source workbook `Net Rates - Ind AUH (NAS)`, 20% co-pay block, cols 30–41 | Cells concentrated in 60+ Married-Female and Dependant rows for Emerald and Silk Road plans contain values implying multipliers of 0.98–1.63 instead of intended ×0.9734 — confirmed copy-paste errors | Use derived values (Nil × 0.9734) for these cells; flagged RED in Existing Rates tab of tender workbook |

| NAS AUH 20% — Dep Emerald/Silk Road rows | Ind AUH NAS | Same block, Dependant section rows | Same pattern of errors in Dependant rows for Emerald and Silk Road age bands 00–17, 18–30, 31–40, and 60+ | Same resolution — use ×0.9734 derived value |

 

---

 

## §16 — QUICK REFERENCE: SEGMENT-LEVEL PRICING SUMMARY

 

| Segment | Rate Sheet(s) | Co-Pay Method | # Base Cells to Price |

|---|---|---|---|

| Ind DXB-NE — NC & Mednet | Ind Rates - DXB-NE | Post-hoc factor (0% base only) | 210 |

| Ind DXB-NE — NAS | Ind Rates - DXB-NE | Post-hoc factor (0% base only) | 210 |

| Ind DXB-NE — Aafiya | Ind Rates - DXB-NE | Post-hoc factor (0% base only) | 90 |

| Ind AUH — NC & Mednet | Ind Rates - AUH | Base → ×0.9450 (10%), ×0.9800 (20%) | 192 |

| Ind AUH — NAS | Ind Rates - AUH | Base → ×0.9450 (10%), ×0.9734 (20%) | 192 |

| Ind AUH — Aafiya | Ind Rates - AUH | Base → ×0.9800 (10%), ×0.9450 (20%) | 32 |

| SME DXB-NE — NAS | SME Rates - DXB-NE | Post-hoc factor (0% base only) | 96 |

| SME DXB-NE — Nextcare | SME Rates - DXB-NE | Post-hoc factor (0% base only) | 96 |

| SME DXB-NE — Mednet | SME Rates - DXB-NE | Post-hoc factor (0% base only) | 96 |

| SME AUH — NAS | SME Rates - AUH | Post-hoc factor (0% base only) | 96 |

| SME AUH — Nextcare | SME Rates - AUH | Post-hoc factor (0% base only) | 96 |

| SME AUH — Mednet | SME Rates - AUH | Post-hoc factor (0% base only) | 96 |

| AUH Basic | AUH Basic Rates | None — single rate | ~20 |

| NE Basic | NE Rates | None — single rate | 3 |

| NE Enhanced 1 | NE Rates | None — single rate | 5 |

| NE Enhanced 2 | NE Rates | None — single rate | 3 |

| **TOTAL** | | | **~1,527** |

 

> All base rates are 0% / Nil co-pay. Co-pay variants for all segments derive mechanically from the multipliers in §3. The reinsurer submits base rates only; UFIC/Marsh Re derive the rest.

 

---

 

*Document generated by Marsh Re | Source: UFIC Product Catalogue V10 14.1 | For reinsurance tender use only*


