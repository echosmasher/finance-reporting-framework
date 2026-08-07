---
description: Turn this month's ERP exports in inbox/ into a per-entity analysis — deterministic Python computes every number, Claude writes the narrative using the company's own tone, terminology, and investigation heuristics from config/.
argument-hint: "[period] [for <entity>[, <entity>...]]"
---

# /analysis

Turns the files in `inbox/` into a structured, narrated analysis per
entity: `outputs/{ENTITY}-Analysis_{PERIOD}.html` (readable, self-contained)
plus `outputs/analysis_{ENTITY}_{PERIOD}.json` (machine-readable, consumed
by `/dashboard`).

**Non-negotiable:** every number in the output comes from
`skills/analysis/scripts/*.py` — deterministic, reproducible, auditable.
Your only job is the narrative: explaining what the numbers mean, in this
company's own words. Never compute, adjust, or restate a number yourself;
if a number looks wrong, that's a bug in the scripts or the input data,
not something to paper over in prose.

## 0. Config check

Before anything else, confirm `config/` has all nine files
`skills/analysis/scripts/config_loader.py` requires (`company-profile.md`,
`entities.csv`, `pnl-structure.yaml`, `account-mapping.csv`,
`thresholds.yaml`, `investigation-guide.md`, `kpi-definitions.yaml`,
`data-dictionary.md`, `brand.md`). Any script below will refuse to run
and print exactly which files are missing if config/ is incomplete — if
you see that error, stop and tell the user to run `/setup` first. Don't
try to work around a missing config file by guessing its contents.

**Demo mode:** if the user asks to run this against the Example Hotels
demo (rather than their own company), use `examples/example-hotels/config`,
`examples/example-hotels/inbox`, and `examples/example-hotels/outputs` in
every command below instead of `config`/`inbox`/`outputs`.

## 1. Resolve period and entity scope

Parse the user's request for a period and an optional entity scope
(`for 001, 003`). If no period is given, detect it:

```bash
ls inbox/*.csv 2>/dev/null | grep -oE '[0-9]{2}-[0-9]{4}' | sort -u
```

Use the most recent period found. If nothing is found, tell the user
`inbox/` is empty and stop. If no entity scope is given, process every
entity in `config/entities.csv`.

## 2. Discover and validate

```bash
python3 skills/analysis/scripts/validate_data.py <period> [--entities <codes>]
```

This reports, per entity, which files were found (`actuals`, `budget`,
`stats` are required; `transactions` is optional) and which are missing,
plus every validation warning/error with file/row/column specifics. Read
the output before continuing:

- **Any error** for an entity (missing required file, bad schema, unmapped
  account above the materiality floor, negative amount, entity/period
  mismatch) — skip that entity for this run, tell the user exactly why
  (quote the specific error), and continue with the rest.
- **Warnings** (unmapped account below the materiality floor, a Spa &
  Wellness posting for a Compact-brand entity) don't block the run — note
  them briefly in your final summary, don't dwell on them in the narrative.

## 3. Preprocess and analyze

For each entity that validated cleanly:

```bash
python3 skills/analysis/scripts/preprocess.py <period> --entities <code>
python3 skills/analysis/scripts/analyze.py <period> --entities <code>
```

`preprocess.py` writes `outputs/{ENTITY}-Intermediate_{PERIOD}.csv` (the
normalized P&L, subtotals recomputed bottom-up — never trust a subtotal
in a source file). `analyze.py` writes `outputs/analysis_{ENTITY}_{PERIOD}.json`:
every P&L category, subtotal, and KPI with a status (`ON TARGET` / `NOTE`
/ `INVESTIGATE`), a `favorable`/`unfavorable` direction, revenue-mix
shifts, and — for any flagged category with transaction data — a
drill-down grouped by vendor and by account. Read that JSON now; it's
the only source of numbers for the narrative you write next.

**Graceful degradation**, already handled by the scripts, not something
you need to work around: if an entity has no `transactions` file, flagged
categories simply have no `drill_downs` entry — don't invent transaction
detail that isn't there. If the company has no Last Year data
(`pnl-structure.yaml` → `terminology.last_year_available: false`, or no
`{ENTITY}_lastyear_{PERIOD}.csv` file), the intermediate CSV and JSON
simply have no LY columns — don't ask the user for it or apologize for
its absence.

## 4. Write the narrative

This is the actual work of `/analysis` — everything above is retrieval.
For each entity, read:

- `outputs/analysis_{ENTITY}_{PERIOD}.json` — the numbers and flags
- `config/investigation-guide.md` — HIGH/LOW checklists and benchmarks
  for the categories that have them (not every category will)
- `config/company-profile.md` — audience, tone, focus metric, and
  seasonality notes (recurring patterns that should NOT read as alarming)
- `config/thresholds.yaml` → `seasonality_notes` — specific
  category/period combinations with known, expected causes

Write `outputs/narrative_{ENTITY}_{PERIOD}.json`:

```json
{
  "executive_summary": "2-4 sentences.",
  "profitability_summary": "1-3 sentences on the focus_metric (and secondary_metric if relevant).",
  "category_narratives": {
    "<id>": "Narrative for one flagged item, keyed by its id from the analysis JSON's pnl/kpis entries."
  }
}
```

Write one `category_narratives` entry for every item in the JSON's
`flags` list — every NOTE or INVESTIGATE category, subtotal, or KPI.
Nothing else needs an entry (ON TARGET items don't get narrated).

**How to write each piece:**

- **Tone and jargon**: match `company-profile.md`'s audience section
  exactly — a GM and a CFO in the same company profile may call for
  different density, but never invent jargon the config doesn't use.
  Use the company's own terminology for the comparison basis
  (`pnl-structure.yaml` → `terminology.comparison_label`) verbatim —
  never say "forecast" if the config calls it "Budget."
- **Lead with wins.** If GOP (or the configured focus metric) beat the
  comparison basis, or an entity's flags are all favorable, say that
  first — in the executive summary and in that entity's place in your
  overall response to the user, not buried after a list of concerns.
- **Frame concerns as investigation prompts, never accusations.** "Check
  whether the February electricity invoice was received" — not "Utilities
  is under-reported." If the category has an `investigation-guide.md`
  checklist, use it: pick the relevant HIGH or LOW items (based on the
  entry's `favorable` field — HIGH items are for `favorable: false` on an
  expense, LOW items for `favorable: true` on an expense) and adapt them
  to the specific numbers, don't just paste the checklist verbatim.
- **Check seasonality before treating anything as a surprise.** If a
  flagged category/period matches a `thresholds.yaml` seasonality note,
  say so plainly ("this is the annual insurance premium, invoiced every
  January — expected, not a concern") rather than writing an investigation
  prompt for something the company already told you to expect. The
  numbers still show the flag (that's correct, deterministic behavior) —
  your job is recognizing it's not news.
- **A favorable flag is not automatically good news.** A cost category
  running well under Budget is `favorable: true` by the numbers, but
  can just as easily mean a missing invoice as genuine savings — if
  `investigation-guide.md` has a LOW-side checklist for that category,
  use it even though the number looks "favorable."
- **Revenue-mix shifts** (`revenue_mix` in the JSON) are context, not
  automatically narrative-worthy on their own — mention a shift only if
  it's large enough to be worth a sentence, or if it explains a flagged
  category's story (e.g. a shift toward group business explaining an F&B
  cost ratio move).
- **KPI narratives** follow the same rules as categories, using
  `kpi-definitions.yaml`'s `denominator` text if you need to explain what
  a KPI measures, and citing the comparison basis by its configured label.

## 5. Render

```bash
python3 skills/analysis/scripts/render_analysis.py <period> --entities <code>
```

Reads the analysis JSON and the narrative JSON you just wrote and
produces `outputs/{ENTITY}-Analysis_{PERIOD}.html` — self-contained,
inline CSS, zero external requests. If you skip step 4 for some reason,
this still renders a complete numbers-only report with a visible note
that the narrative wasn't written; that's a fallback for testing, not a
substitute for doing step 4.

## 6. Run summary

Print a summary to the user: entities processed, entities skipped (and
why, quoting the validation error), total flags raised across the batch,
and point to the output files. Don't repeat the full narrative in your
chat response — the HTML report is the deliverable; a couple of
sentences highlighting anything genuinely notable (a real INVESTIGATE
item, not routine NOTE-tier variance) is enough.

## Batch behavior

No arguments → every entity in `config/entities.csv`, detected period.
`for 001, 003` → just those entity codes. A period the user names
explicitly (a month name, `02-2026`, "February") always overrides
detection.
