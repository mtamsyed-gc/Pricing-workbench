# Cedant rate workbook — fill guide (SPEC §8.5, work order WS5)

The cedant's current (expiring) catalogue comes into the workbench through a workbook the tool generates in its own
layout. GC fills it from the cedant's catalogue; the tool reads it back into the EXPIRING catalogue that drives
Existing Rates, V5, B2, B1 and A. One layout, two modes: the rate sheets are the same blocks as the reinsurer tender
template, so a reinsurer template generated from the read-back shows the same blocks with Existing Rates filled.

**The filled copy holds client rates. Keep it in `runs\<RunID>\` only — never in the repo, never sent to a reinsurer.**

## Steps

```
py tools\pw.py t cedant <template_spec.json> --out runs\<RunID>\cedant_workbook.xlsx
   ... GC fills the yellow cells ...
py tools\pw.py t cedant-read runs\<RunID>\cedant_filled.xlsx --spec <template_spec.json> --out runs\<RunID>\expiring.json
py tools\pw.py t generate <template_spec.json> --expiring runs\<RunID>\expiring.json --out runs\<RunID>\tender_template.xlsx
```

`t cedant-read` stops (exit code 2, no catalogue written) until the workbook is complete and consistent. Every
problem is listed with sheet and cell, on screen and in `expiring_read_report.csv` beside `--out`. Fix the cells
and run it again.

## What goes where

| Sheet | Enter | Rule |
|---|---|---|
| Rate sheets (one block per product × emirate × TPA) | Annual premium per member, every yellow cell | **Nil / 0% co-pay base** at the reference options stated under the sheet title. **Before the TPA factor.** Grey cells are referred (not priced). |
| Factors | `Factor` per row | One row per option (and per key where the factor varies by network, plan or TPA, else `ANY`). The row with `Reference = Y` is the option the base assumes. It must read **1.0**, and there must be exactly one per key. A key without its own reference row uses the `ANY` row's. |
| Riders | `Rate` per row | Rider premium per limit option and key, in the unit shown (per member / per eligible female); a multiplier where the unit says so. `Key on` shows which source column a plan takes where the spec says so. |
| Plan defaults | `Option` (list) | The option each plan is sold with (catalogue default, SPEC §3.4). It is used where the exposure does not carry the option. Riders: `NONE` = not purchased. |
| Benefits | `Value`, `Condition text` | As the benefit code needs: amount, number, Y / N, or a listed value. Keep the source wording in Condition text. Value blank + text = MANUAL_REVIEW; whole row blank = benefit not applicable. |

## The Nil-base rule

Co-pay variants are **never** entered. Where the cedant's source shows side-by-side co-pay blocks (Nil / 10% / 20%),
enter only the Nil block on the rate sheet. Enter the block multipliers as a factor table (Nil = reference = 1.0).
The variants are then generated, as the reinsurer's will be.

## The TPA basis (SPEC §8.0, final)

Each TPA block holds the rate **before** the TPA factor, and the TPA factor goes in Factors (family `tpa`). Do not
build the TPA difference into the block as well. Where the source shares one table between TPAs, enter the same
values in each TPA's block.

## Source flags (SPEC §12)

The cedant example's Cover lists the flags that change what is typed:
- **F2:** swap the 10% / 20% block labels where the source has them the wrong way round.
- **F3:** the TPA whose co-pay blocks are flat multipliers uses its own factor table.
- **F4:** keep the flagged source value.
- **F6:** use the derived multiplier, not the erroneous cells.
- **F7:** premium basis per sheet.

The structure (which tables exist for which TPAs) is set in the template spec, so GC only types values.

## Adding rows

Each long table ends with yellow spare rows. Use them to add an option, a key or a benefit line to an **existing**
table: pick product, emirate, TPAs and family (or benefit code) from the lists, then fill the value. A spare row
cannot create a new table. Add the table to the template spec and regenerate instead.

## Read-back gate (stops, never defaults)

The read stops on any of the following:
- a blank, non-numeric or ≤ 0 mandatory rate, factor or rider rate;
- a factor table key with no reference row, or with more than one;
- a reference row that is not 1.0, or a reference flag other than Y / blank;
- a plan default that is blank, or names an option its table lacks;
- an unknown benefit code, ladder value or Y / N value;
- a duplicate row in a long table;
- a row naming an unknown product, emirate, TPA group, plan or table;
- a missing sheet or a lost header.

Numbers typed as text are read with a warning. A lost `_KEYS` sheet falls back to the issued positions, also with a
warning.

## What the workbook does not carry

The workbook does not carry loadings and loading caps, fees, UW / referral rules, plan attributes (clinic
restriction, split IP/OP) or structured co-pay objects for benefits. These are listed in the spec's
`cedant_workbook.not_carried` when it was authored from a catalogue. Pricing at loading 0 (the base comparison) does
not need them. Terms and UW rules input follow in a later work order.
