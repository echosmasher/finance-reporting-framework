# Data Dictionary — Example Hotels

*Captured by `/setup` Phase D, confirmed via the validation dry-run
playback. This is the contract `validate_data.py`, `preprocess.py`, and
`examples/example-hotels/generate_demo_data.py` all implement exactly.*

## Conventions (apply to every file below)

| Convention | Value |
|---|---|
| Delimiter | comma (`,`) |
| Decimal separator | period (`.`) |
| Thousands separator | none — plain numeric strings |
| Encoding | UTF-8 |
| Date format | ISO 8601, `YYYY-MM-DD` |
| Period format | `MM-YYYY` (e.g. `01-2026`) |
| Fiscal calendar | standard calendar months (no 4-4-5) |
| Sign convention | **all amounts are positive.** Revenue vs. expense is inferred from the account's `category_id` in `account-mapping.csv` (its `group` in `pnl-structure.yaml`), never from the sign in the source file. |
| Currency | implied by the entity (see `entities.csv`); no currency column in the files themselves — one file = one entity = one currency, never mixed |
| Month vs. YTD | every file holds **single-month** figures only. No YTD columns (YTD views are out of scope for v1 — `PLAN.md` §10) |

## File naming

`{ENTITY}_{FILE_TYPE}_{PERIOD}.csv`, entity code zero-padded to 3 digits,
e.g. `001_actuals_01-2026.csv`.

## File types

### 1. Actuals — `{ENTITY}_actuals_{PERIOD}.csv`

GL-account-level actual postings for the period. One row per account per
period (accounts with no activity may be omitted).

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | matches `entities.csv` |
| `period` | string | `MM-YYYY` |
| `gl_account` | string | matches `account-mapping.csv` `gl_account` |
| `amount` | number | positive, local currency |

Sample row:
```
entity_code,period,gl_account,amount
001,01-2026,4000,412500.00
```

### 2. Budget — `{ENTITY}_budget_{PERIOD}.csv`

Same shape as Actuals; this is the only comparison basis configured for
this company (`pnl-structure.yaml` `terminology.comparison_basis: budget`
— no rolling forecast, no Last Year data in this demo).

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `gl_account` | string | |
| `amount` | number | budgeted amount, positive, local currency |

Sample row:
```
entity_code,period,gl_account,amount
001,01-2026,4000,405000.00
```

### 3. Transactions — `{ENTITY}_transactions_{PERIOD}.csv`

GL detail used for the drill-down under flagged categories. Optional per
entity/period — if absent, `/analysis` skips the drill-down section with
a note (graceful degradation, `PLAN.md` §6).

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `date` | string | `YYYY-MM-DD`, within the period |
| `gl_account` | string | |
| `vendor` | string | |
| `description` | string | free text |
| `department` | string | one of: Rooms, F&B, Spa & Wellness, Other Operated, Administrative, Sales & Marketing, Property Operations, IT, HR, Security, Fixed Charges |
| `amount` | number | positive, local currency |

Sample row:
```
entity_code,period,date,gl_account,vendor,description,department,amount
001,03-2026,2026-03-08,6300,Oslo Energi AS,Electricity invoice — catch-up billing includes unpaid February charges,Property Operations,202900.91
```

### 4. Stats — `{ENTITY}_stats_{PERIOD}.csv`

Non-P&L operational data needed by the KPIs in `kpi-definitions.yaml`
(Occupancy %, RevPAR, Revenue per FTE all need rooms-available and/or FTE
data that doesn't live on the P&L). One row per entity per period.
Optional — a company whose KPIs are all pure P&L ratios (GOP % alone,
say) doesn't need one; `preprocess.py` omits any KPI that needs a stats
field from the analysis JSON rather than failing.

**v1 limitation, disclosed rather than hidden:** the columns below are
fixed by `validate_data.py`/`preprocess.py`, not derived from this
company's own config — they're hotel-shaped (rooms, FTE) because this
demo is a hotel chain. A different industry wanting operational-data
KPIs with a genuinely different shape (e.g. "units produced" instead of
"rooms sold") would need an engine change here, not just a config
change. `/setup` Phase G can still define any KPI that's a pure P&L
ratio (no stats dependency) for any industry without this limitation
applying.

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `rooms_available` | integer | room-nights available in the period (room count × days, less any out-of-order rooms) |
| `rooms_sold_actual` | integer | room-nights sold |
| `rooms_sold_budget` | integer | budgeted room-nights sold |
| `fte_actual` | number | average FTE headcount across all departments, one decimal |
| `fte_budget` | number | budgeted average FTE headcount |

Sample row:
```
entity_code,period,rooms_available,rooms_sold_actual,rooms_sold_budget,fte_actual,fte_budget
001,01-2026,7440,5210,5100,142.5,140.0
```

### 5. Last Year (optional) — `{ENTITY}_lastyear_{PERIOD}.csv`

Same shape as Actuals — prior-year actuals for the same calendar period,
for companies with `pnl-structure.yaml` → `terminology.last_year_available:
true`. Not used by this company (`last_year_available: false` — comparison
basis is Budget only); omitted entirely from this demo's `inbox/`. If
present, `preprocess.py` adds LY/LY % columns to the intermediate output;
if absent (or the company doesn't have LY at all), those columns are
dropped rather than shown empty (graceful degradation, `PLAN.md` §6).

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `gl_account` | string | |
| `amount` | number | positive, local currency, prior year's actual for this period |

Sample row:
```
entity_code,period,gl_account,amount
001,01-2026,4000,538100.00
```

## Validation rules `validate_data.py` enforces

- Every `gl_account` in Actuals/Budget/Transactions must exist in
  `account-mapping.csv`. Unmapped accounts posting at or above
  `thresholds.yaml` → `unmapped_account_materiality_floor` (by the
  entity's currency) are a **hard fail**, named by file/account/amount;
  below the floor, a warning list.
- `entity_code` must exist in `entities.csv`.
- `period` must match `MM-YYYY` and be a valid calendar month.
- `amount` (and stats numeric columns) must parse as a non-negative
  number — this data dictionary's sign convention means a negative
  value is always a data error, never a legitimate credit/contra entry.
- A category whose `pnl-structure.yaml` entry has `applies_to_brands`
  set is a warning, not a hard fail, if it posts for an entity whose
  `entities.csv` `brand` isn't in that list — the engine reads this
  generically off `pnl-structure.yaml`, it doesn't hardcode which
  categories or brands this applies to. For Example Hotels: Spa &
  Wellness (`spa_revenue`, `spa_payroll`, `spa_other_exp`) is scoped to
  `[Signature]`, since the Compact brand genuinely has no Spa
  department — but a stray posting should still surface for review
  rather than being silently accepted or hard-failing.
