# Data Requirements

What this framework needs from your ERP/accounting system, and how to
get it. Read this before running `/setup` — having the right exports
ready makes the interview much faster, especially Phase D's validation
dry run.

## What you need

Two exports are **required**, for every entity, every month:

1. **Actuals by GL account** — a P&L export at the general-ledger-account
   level (not pre-summarized into your reporting categories; `/setup`
   handles the account → category mapping). One row per account per
   period, with an amount.
2. **Budget** (or Forecast, or whatever your comparison basis is) —
   same shape as actuals, for the same accounts and period.

Two more are **optional**, but each unlocks something specific:

3. **Transactions (GL detail)** — vendor, description, date, and amount
   for individual postings. Without this, `/analysis` still produces a
   full P&L and flags deviations — it just can't show *which specific
   invoice or vendor* is driving a flagged category. If your controller
   workflow already involves pulling transaction detail to investigate a
   variance, this is the file that makes that step automatic instead of
   manual.
4. **Operational stats** (occupancy, headcount, units — whatever your
   KPIs need beyond the P&L) — only required if you want KPIs like
   RevPAR or Revenue per FTE that need data the P&L doesn't carry. A
   company whose KPIs are all pure P&L ratios (GOP % alone, say) doesn't
   need this at all. See `data-dictionary.md`'s note on this in your own
   `config/` once `/setup` has run — the columns are currently fixed to
   a hospitality-shaped schema (rooms/FTE); see that file for the
   detail.

## Where these come from

Every accounting system calls this something slightly different — look
for whichever of these your system uses:

- **Actuals by account**: "Trial Balance," "GL Detail by Account," "P&L
  by Account," or a "Profit & Loss" report with the export/drill-down
  option set to account-level rather than summary-level.
- **Budget**: "Budget vs. Actual," "Budget Report," or a separate budget
  module's export — some systems only let you export Budget alongside
  Actuals in one combined report; that's fine, `/setup`'s Phase D will
  ask how to split it.
- **Transactions**: "GL Detail," "Journal Entries," "AP Transaction
  Detail," or a "Drill-down" export from the account-level report.
- **Operational stats**: usually outside the accounting system entirely
  — a PMS (property management system), POS, or operations spreadsheet
  someone already maintains for exactly this kind of reporting.

If your system can filter/export by entity and by period directly, do
that — one file per entity per month is the shape `/setup`'s
`data-dictionary.md` documents and `validate_data.py` expects. If it
can't, exporting everything and splitting it (in a spreadsheet, or by
asking `/setup` to help write a one-off script) is a reasonable
workaround for the first month; after that, most systems can be
scheduled or saved as a repeatable report so the monthly pull takes
seconds.

## Conventions `/setup` will ask about (Phase D)

Have one real sample of each file in hand — `/setup` needs to see the
actual export, not a description of it, to confirm these correctly:

- **Delimiter** — comma, semicolon, tab? (Both are supported by the
  engine; whatever your export uses is fine.)
- **Decimal format** — plain period-decimal, no thousands separator
  (`1234.56`). If your system exports European-style numbers
  (`1.234,56`) or with thousands separators (`1,234.56`), you'll need a
  conversion step before the framework can read the file — this is a
  known v1 limitation, not something `/setup` can configure around.
- **Sign convention** — are all amounts positive, with revenue/expense
  inferred from the account itself? Or are costs stored as negative
  numbers, revenue positive? Both are supported; get this one exactly
  right, since it's genuinely how the numbers are interpreted, not just
  a display setting.
- **Currency** — one file always means one entity means one currency;
  no mixed-currency files.
- **Date format** — for the transactions file's date column.
- **Fiscal calendar** — standard calendar months, or a 4-4-5 retail
  calendar? (4-4-5 support depends on how your periods map to `MM-YYYY`
  — flag this early in the interview if it applies to you.)
- **Month vs. YTD** — the framework works with single-month figures.
  If your system only exports year-to-date columns, `/setup` will ask
  how you currently derive the monthly delta.

## Try the demo first

If you want to see what a validated, working data set looks like before
gathering your own, `examples/example-hotels/inbox/` has three real
months of synthetic exports in exactly the format `/analysis` expects —
open one alongside your own export to get a feel for the shape before
Phase D's dry run.
