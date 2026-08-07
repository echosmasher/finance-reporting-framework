# Data Dictionary — [COMPANY NAME]

*Captured by `/setup` Phase D, confirmed via the required validation
dry-run playback. This is the contract `validate_data.py` and
`preprocess.py` implement exactly — get every convention below
explicitly confirmed with the user before writing it down.*

## Conventions (apply to every file below)

| Convention | Value |
|---|---|
| Delimiter | [comma / semicolon / tab / ...] |
| Decimal separator | [period / comma] |
| Thousands separator | [none / period / comma / space] |
| Encoding | [UTF-8 / ...] |
| Date format | [ISO 8601 `YYYY-MM-DD` / ...] |
| Period format | `MM-YYYY` |
| Fiscal calendar | [standard calendar months / 4-4-5 / ...] |
| Sign convention | [all amounts positive, sign inferred from category / costs negative / revenue negative / ...] — get this one explicitly right, it changes how every number is read |
| Currency | [implied by entity / a column in the file / ...] |
| Month vs. YTD | [single-month figures only / YTD with a separate monthly-delta step / ...] |

## File naming

`{ENTITY}_{FILE_TYPE}_{PERIOD}.csv`, matching `entities.csv`'s
`entity_code` values.

## File types

`validate_data.py` requires `actuals` and `budget` for every entity;
`stats` and `transactions` are both optional (see notes below).

### 1. Actuals — `{ENTITY}_actuals_{PERIOD}.csv`

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | `MM-YYYY` |
| `gl_account` | string | matches `account-mapping.csv` |
| `amount` | number | |

Sample row: `[paste one real, de-identified sample row here]`

### 2. Budget — `{ENTITY}_budget_{PERIOD}.csv`

Same shape as Actuals.

### 3. Transactions (optional) — `{ENTITY}_transactions_{PERIOD}.csv`

If absent for an entity/period, `/analysis` skips the transaction
drill-down for that entity with a note — not an error.

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `date` | string | |
| `gl_account` | string | |
| `vendor` | string | |
| `description` | string | |
| `department` | string | |
| `amount` | number | |

### 4. Stats (optional) — `{ENTITY}_stats_{PERIOD}.csv`

Only needed if a KPI in `kpi-definitions.yaml` requires operational data
beyond the P&L. **v1 limitation:** the columns below are currently fixed
by the engine to a hotel-shaped schema (rooms/FTE) — see
`kpi-definitions.yaml`'s template for what this means for a KPI that
doesn't fit that shape.

| Column | Type | Notes |
|---|---|---|
| `entity_code` | string | |
| `period` | string | |
| `rooms_available` | integer | |
| `rooms_sold_actual` | integer | |
| `rooms_sold_budget` | integer | |
| `fte_actual` | number | |
| `fte_budget` | number | |

### 5. Last Year (optional) — `{ENTITY}_lastyear_{PERIOD}.csv`

Only if `pnl-structure.yaml` → `terminology.last_year_available: true`.
Same shape as Actuals.

## Validation rules `validate_data.py` enforces

- Every `gl_account` in Actuals/Budget/Transactions must exist in
  `account-mapping.csv`. Unmapped accounts posting at or above
  `thresholds.yaml` → `unmapped_account_materiality_floor` are a hard
  fail, named by file/account/amount; below it, a warning.
- `entity_code` must exist in `entities.csv`.
- `period` must match `MM-YYYY` and be a valid calendar month.
- `amount` (and stats numeric columns) must parse as a non-negative
  number if this company's sign convention is "all positive" (see
  Conventions above) — adjust this rule if the confirmed sign
  convention is different.
- A category with `pnl-structure.yaml` → `applies_to_brands` set is a
  warning (not a hard fail) if it posts for an entity whose
  categorization isn't in that list.
