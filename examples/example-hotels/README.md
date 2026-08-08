# Example Hotels — demo company

A fictional 4-property Nordic hospitality group, fully configured end to
end, used to demonstrate the framework without anyone running `/setup`.
See `config/` for the complete config layer (the reference example of
every config schema) and `generate_demo_data.py` for how the data below
was produced.

All figures are synthetic. No real company names, benchmarks, account
codes, or property codes appear anywhere in this repo.

## Regenerating the data

```
python3 examples/example-hotels/generate_demo_data.py
```

Deterministic (seeded RNG) — running it again reproduces `inbox/`
byte-for-byte. It generates, per entity per period (01-2026, 02-2026,
03-2026): GL actuals, budget, an occupancy/FTE stats file, and GL-detail
transactions. See `config/data-dictionary.md` for the exact file/column
contract.

## Planted stories

Four deliberate stories are built into the numbers below, so a reviewer
can run `/analysis` against this data and check that it finds exactly
these — no more, no fewer — once `analyze.py` (task 7) is built. Every
number here is reproducible straight from the committed CSVs in `inbox/`.

### 1. Missing electricity invoice — Example Hotel Oslo (001), Utilities

- **February:** actual 391,068 NOK vs. Budget 491,144 NOK (**−20.4%**).
  The Electricity account (`6300`) posts only a token 5,267 NOK
  "estimated accrual" — the real invoice never arrived that month.
  Every other utilities account (heating, water, waste, fuel) is normal.
- **March:** actual 788,234 NOK vs. Budget 586,844 NOK (**+34.3%**).
  Electricity alone carries 327,260 NOK — a specific transaction labeled
  *"catch-up billing, includes unpaid February charges"* plus March's own
  usage.
- **What the analysis should do:** flag both months INVESTIGATE on
  Utilities, and the transaction drill-down for each should make the
  cause obvious — a missing invoice in February, recognized in March.
  `investigation-guide.md`'s Utilities checklist (item 1 under both HIGH
  and LOW) names exactly this pattern.

### 2. F&B inventory write-off — Example Hotel Bergen (002), F&B – Cost of Sales

- **February:** actual 444,623 NOK vs. Budget 317,588 NOK (**+40.0%**).
  A single transaction on the `F&B Inventory Adjustment` account (`5203`)
  for 203,321 NOK, described as *"obsolete and spoiled stock write-off
  following physical count"* — every other F&B COGS account (food,
  beverage, banquet) is at its normal level.
- **What the analysis should do:** flag Bergen F&B – Cost of Sales
  INVESTIGATE for February only (January and March are within
  threshold). `investigation-guide.md`'s F&B COGS checklist item 1
  ("pull the transaction drill-down... a manual inventory adjustment can
  land the whole month's variance in one entry") applies directly.
- **`/feedback` demo:** this dashboard (`002-Dashboard_02-2026.html`)
  also carries two committed edits from `examples/example-hotels/feedback/feedback_002_02-2026.json`,
  applied via `/feedback` after the fact — a real before/after for the
  skill, not just a description of it. A comment on F&B – Cost of Sales
  confirms with the F&B manager that the write-off was a scheduled stock
  count, not a control issue; the Pre-tax Income narrative (which just
  repeated "same driver as GOP/EBITDA/EBIT above" a third time) is
  suppressed as redundant once GOP's narrative already explains it. Diff
  it against `git log` to see exactly what `/feedback` changed.

### 3. Payroll not tracking occupancy — Example Hotel Copenhagen (004), Rooms – Payroll & Related

- **March:** Rooms Payroll actual 797,940 DKK vs. Budget 638,352 DKK
  (**+25.0%**) — while occupancy (see `004_stats_03-2026.csv`) is
  3,151 rooms sold vs. 3,224 budgeted, i.e. **−2.3%**, essentially on
  target.
- The transaction drill-down shows why: two `Rooms Division Overtime`
  (`5002`) entries ("covering extended staff leave") plus a `Rooms
  Division Temporary Labor` (`5005`) entry from an external staffing
  agency, on top of normal Front Office/Housekeeping/Concierge salaries.
- **What the analysis should do:** flag INVESTIGATE, and the narrative
  should note that payroll moved independently of occupancy this month —
  the specific signal `investigation-guide.md`'s Rooms Payroll benchmark
  calls out ("a payroll variance materially larger... than the occupancy
  variance in the same period is the signal worth chasing").

### 4. A clean quarter — Example Hotel Stockholm (003)

No planted deviation here — the point is that not every entity has a
problem. Stockholm's Gross Operating Profit (GOP) beats Budget in all
three months (Jan +1.6%, Feb +2.6%, Mar +0.5%), and no category outside
the group-wide January seasonality (below) breaches its threshold. The
narrative pass should lead with this as a genuine win, not manufacture a
concern to fill space.

## Group-wide January seasonality (not one of the four stories, but worth knowing)

Every entity's `insurance` and `admin_general` actuals carry a real,
deliberate spike every January — the annual Property & Liability
Insurance premium and external audit fee are invoiced as a single
January charge (see `config/company-profile.md` and
`config/thresholds.yaml` → `seasonality_notes`), while each entity's
Budget stays flat month to month. The deterministic engine (`analyze.py`)
will mechanically flag both categories INVESTIGATE every January, for
every entity — that's correct and expected. The point is what happens
next: the narrative pass is supposed to recognize this via
`investigation-guide.md`'s Administrative & General checklist and the
seasonality note, and explain it as expected rather than alarming. This
is a live exercise of that mechanism, not a bug — if a January run ever
stops flagging Insurance/Admin & General, something in the generator or
the thresholds changed.

## Entities at a glance

| Code | Name | Brand | Currency | Story |
|------|------|-------|----------|-------|
| 001 | Example Hotel Oslo | Signature | NOK | Missing electricity invoice (Feb → Mar) |
| 002 | Example Hotel Bergen | Signature | NOK | F&B inventory write-off (Feb) |
| 003 | Example Hotel Stockholm | Compact | SEK | Clean quarter, beats Budget on GOP |
| 004 | Example Hotel Copenhagen | Signature | DKK | Payroll/occupancy divergence (Mar) |
