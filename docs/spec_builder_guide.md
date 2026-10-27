# Spec Builder — setting up a tender's structure in Excel

For GC users who set up or change a tender without editing JSON or running Python by hand. SPEC §8.6 is the
contract; this guide is the how-to. Every example below is fictional.

## What it is
Every tender has one structure file, `inputs\template_spec.json`. It decides which rate sheets, TPA blocks, plans, age
bands and columns the reinsurers' template and the cedant workbook contain. The **Spec Builder** is an Excel view of
that file: dropdowns and yellow cells instead of JSON.

**The JSON stays the master.** The builder is only an editing view. The tool reads it back into the JSON, and every
other step (cedant workbook, tender template, evaluation) uses the JSON.

## The loop
1. Double-click **`0a_make_spec_builder.bat`**. It writes `work\spec_builder.xlsx`, pre-filled from the current
   `inputs\template_spec.json`, or blank when there is none.
2. Open it, fill or change the yellow cells (\* = mandatory), and save it as **`inputs\spec_builder.xlsx`**.
3. Double-click **`0b_read_spec_builder.bat`**.
   - **SPEC READ PASS** writes `inputs\template_spec.json`. The previous one is kept as `template_spec.previous.json`.
   - **SPEC READ FAIL** lists each problem with its sheet and cell (for example `Blocks!G7 age band set 'X' is not
     defined`). The spec is not touched. Fix the cells and run 0b again. The full list is in
     `inputs\template_spec_read_report.csv`.
4. Check the result: run step 1 (cedant workbook) and step 3 (tender template) and look at them before issuing.

You may fix and re-read the same builder as often as needed, also after a PASS. If someone else changed
`template_spec.json` after you made your builder, step 0b stops ("the template spec changed since this builder was
made"). Make a new builder with 0a and copy your changes into it, so nobody's edit is lost.

## Colours and lists
- **Yellow**: input cells.
- **Grey**: information only.
- **Dropdowns**: fixed lists (product type, regulator, gender, marital status, member category, Y/N, units, benefit
  codes) refuse other values. User lists (TPAs, rating regions, networks, band sets, column sets) live on the **Lists**
  sheet: add a new name there first, then pick it elsewhere. A value typed past a dropdown is still checked on
  read-back.
- **Spare rows**: each long table has spare formatted rows. You may also insert rows. Rows are read until the end of
  the sheet, and blank rows are skipped.
- Do not rename or delete the builder's sheets, or the rows of the Tender and Cedant workbook sheets.

## The sheets
| Sheet | One row per | Notes |
|---|---|---|
| Tender | field | Cedant, tender id, currency, basis, dates, contact; the reference sheets shown to reinsurers; options. Blank = not set (the tool's default applies). |
| Lists | value | Dropdown sources for TPAs, rating regions, networks, band sets, column sets. Not read back. |
| Age bands | band | Band set name, label, age from, age to (whole years; open top band = to 120). Both ages blank = a label-only row. **Source "file …"**: the band lives in the tender's age bands file. Change that file, not these rows. |
| Columns | column key | The rate columns. Two rows with the same set and label make one column (e.g. "M/SF" = male, and single female). MF (Male, Female) and RATE (one rate) are built in. |
| Sheets | rate sheet | Product × emirate. Name (max 31 characters), title, product, regulator, rating region, row source (an age band set, or rows on Sections / Custom rows), column set, refer text, formula. |
| Co-pay basis | family | The basis the base rates are quoted at (e.g. copay_op_diag = 0%). |
| Blocks | TPA block | Block id, TPA, label, splits (Y/N), overrides of the sheet's band set or column set, comment. |
| Plans | plan of a block | Plan id, label, the TPA's network label, plan number; in column order. |
| Sections | row section | See below. |
| Custom rows | row key | See below. |
| Refer cells | refer rule | See below. |
| Factor tables | cedant factor table | Family, key on, TPAs. Options are on the Options sheet. |
| Riders | cedant rider | Family (module_…), key on, unit, mode, eligibility. Limits are on the Options sheet. |
| Options | option of a table or rider | Key, option, Reference = Y for the factor-1.0 option (one per key), key label. |
| Plan defaults | option family | Families each plan is asked "sold with" in the cedant workbook. |
| Benefits | benefit code | Codes asked per plan in the cedant workbook (Plans blank = every plan). |
| Cedant workbook | field | Catalogue id, version, effective date, spare rows. |
| Cedant notes | note | Lines shown on the cedant workbook's Cover. |

## The five structured fields
These used to be the hard part of the JSON. Each now has its own table.

**1. Formula** (Sheets: Formula order, rounding, min premium, max premium). This tells the tool how the cedant's
premium is built when the cedant workbook is read back. The order is *BASE, FACTORS, MODULES* (base rate × co-pay /
AML / TPA factors, then riders) or *BASE, MODULES, FACTORS*. Blank means the default order and the tender's rounding.
One sheet has one formula.

**2. Splits** (Sheets: *Marital split columns*; Blocks: *Marital split*, *Member split*). Extra splits that a block
switches on only where the cedant prices them:
- **Marital split = Y**: the block uses the sheet's *Marital split columns* (e.g. a column set "M/SF" + "Married-F").
- **Member split = Y**: the block uses the sheet's member sections (Sections rows with *Applies to = Member split*,
  e.g. "Employee" on a band set without under-18 rows, and "Dependant" on the full set).

**3. Sections** (Sections sheet). Row sections, each with its own member category and age band set, or one row label
when it has no bands. *Applies to* says where they are used:
- `Sheet rows`: every block of the sheet.
- `Member split`: blocks with the member split on.
- a block id: that block only.

Example: a basic-plan sheet with six member categories, each on its own band set.

**4. Custom rows** (Custom rows sheet). Hand-built rows for irregular tables. Two lines with the same row label and
section make **one** row covering both keys. Example:

| Applies to | Row label | Section label | Member category | Age from | Age to |
|---|---|---|---|---|---|
| BLOCK_X | 00-64 | Employee & Dependants | EMPLOYEE | 0 | 64 |
| BLOCK_X | 00-64 | Employee & Dependants | DEPENDANT | 0 | 64 |
| BLOCK_X | 65+ | Parents | PARENT | 65 | 120 |

A block (or sheet) takes **one** row source: an age band set, sections, or custom rows.

**5. Refer cells** (Refer cells sheet). Cells the reinsurer does not quote; they show the sheet's *Refer text*. Each row
is a rule. A blank field matches anything, so a cell matching every filled field is a refer cell. Examples:
- Member category = PARENT: the whole parents row.
- Plan = P6, Age 70 to 120: plan P6 above age 70, both genders.

## What the builder does not show
Notes, source flags, pending items, the owner's decision records and any field the builder has no table for are
**kept from the current JSON** when step 0b runs. The builder's Cover lists them under "Kept from the spec". A table
or block whose meaning you did not change keeps its exact JSON form.

## Data boundary
A builder pre-filled from a client spec holds the tender's **structure** only: labels, never rates. Keep it in the
tender folder on the GC laptop, never in the repository or a release.
