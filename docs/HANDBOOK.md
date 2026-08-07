# Handbook — the monthly loop

This is the step-by-step guide for the recurring monthly cycle, once
`/setup` has already run and `config/` exists. If you haven't run
`/setup` yet, do that first — everything below assumes it's done.

## The loop

### 1. Export from your ERP

Pull actuals and budget (and transactions/stats, if you use them) for
the month you're closing. See `docs/DATA_REQUIREMENTS.md` if you need a
reminder of what each export should look like — but by now your system
should already be set up to produce these in the format `/setup`
confirmed.

### 2. Drop the files in `inbox/`

Name them `{ENTITY}_{TYPE}_{PERIOD}.csv` — see the file-naming reference
below. `inbox/` can hold more than one month at a time if you're
catching up, but `/analysis` with no arguments processes the most
recent period it finds, so name and drop files for one month at a time
if you're running the loop as intended.

### 3. Run `/analysis`

```
/analysis
```

or, to scope it: `/analysis for 001, 003` (specific entities) or
`/analysis 02-2026` (a specific period). This validates the files,
computes the full P&L, flags deviations, and writes the narrative. Read
the summary it prints — how many entities processed, how many flags
raised, and whether anything was skipped (and why).

### 4. Review the analyst report

Open `outputs/{ENTITY}-Analysis_{PERIOD}.html` for each entity. This is
the plain, numbers-forward version — your working copy before anything
goes to an audience. If something in the narrative looks wrong, that's
a signal worth acting on: either the underlying data has an issue (fix
it and rerun `/analysis`), or `config/` needs a correction (a threshold
that's miscalibrated, an investigation heuristic that's stale) — fix the
config, not the output.

### 5. Run `/dashboard`

```
/dashboard
```

Same scoping rules as `/analysis`. This turns the same numbers and
narrative into the polished, brand-styled version your actual audience
sees: `outputs/{ENTITY}-Dashboard_{PERIOD}.html`.

### 6. Distribute

Email the dashboard file, drop it on a shared drive, or use whichever
deployment tier you set up (see `docs/DEPLOYMENT.md`). The dashboard is
self-contained — no server needed for the default tier.

## File-naming reference

| File | Pattern | Required? |
|---|---|---|
| Actuals | `{ENTITY}_actuals_{PERIOD}.csv` | Yes |
| Budget | `{ENTITY}_budget_{PERIOD}.csv` | Yes |
| Transactions | `{ENTITY}_transactions_{PERIOD}.csv` | Optional |
| Stats | `{ENTITY}_stats_{PERIOD}.csv` | Optional |
| Last Year | `{ENTITY}_lastyear_{PERIOD}.csv` | Optional, only if configured |

`{ENTITY}` is the entity code from your `config/entities.csv`.
`{PERIOD}` is `MM-YYYY` (e.g. `02-2026`).

Outputs follow their own pattern, written to `outputs/`:

| Output | Pattern |
|---|---|
| Intermediate P&L | `{ENTITY}-Intermediate_{PERIOD}.csv` |
| Analysis JSON | `analysis_{ENTITY}_{PERIOD}.json` |
| Narrative JSON | `narrative_{ENTITY}_{PERIOD}.json` |
| Analyst report | `{ENTITY}-Analysis_{PERIOD}.html` |
| Dashboard | `{ENTITY}-Dashboard_{PERIOD}.html` |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `config/ is missing required file(s)` | `/setup` hasn't been run, or ran incompletely | Run `/setup` |
| `missing required file(s) [..._actuals_..., ..._budget_...]` | The export wasn't dropped in `inbox/`, or is misnamed | Check the file is in `inbox/` and named exactly `{ENTITY}_{TYPE}_{PERIOD}.csv` |
| `entity_code does not match filename entity` | A row in the file has the wrong entity code — often from copy-pasting a template between entities | Fix the source export, don't hand-edit the CSV |
| `gl_account is not in account-mapping.csv` (error) | A new GL account was added in your chart of accounts since `/setup` ran, and it's posting a meaningful amount | Run `/setup` to update `account-mapping.csv` — don't ignore this, it means real activity isn't being categorized |
| `gl_account is not in account-mapping.csv` (warning) | Same as above, but the amount is small (below the materiality floor) | Safe to ignore for one month; worth fixing in `account-mapping.csv` if it recurs |
| `doesn't match data-dictionary.md's sign_convention` | The ERP export changed format (e.g. a system upgrade flipped how it signs debits/credits) | Confirm the new convention with a real sample, update `data-dictionary.md`'s conventions block via `/setup` |
| `is not a number` | A cell has text, a stray currency symbol, or an empty value where a number is expected | Fix the source export — this is almost always an export-template issue, not a framework issue |
| A category is flagged every month even though it's expected (e.g. an annual charge) | No seasonality note exists for it yet | Add it to `config/thresholds.yaml`'s `seasonality_notes` (and `company-profile.md`'s narrative version) via `/setup` — the engine will still flag it (correct), but the narrative will stop treating it as a surprise |
| A KPI is silently missing from a dashboard | Its formula needs a stats field the entity's `stats` file doesn't have (or there's no stats file at all) | Check `data-dictionary.md`'s stats-file section; either supply the field or accept that KPI won't show for entities without it |
| `/dashboard` says to run `/analysis` first | There's no `analysis_{ENTITY}_{PERIOD}.json` for that entity/period yet | Run `/analysis` before `/dashboard` — always in that order |
