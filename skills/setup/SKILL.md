---
description: One-time (re-runnable) interview that builds config/ — the complete config layer /analysis and /dashboard depend on. Conversational, one topic at a time, nothing written until the user confirms.
argument-hint: "[section to update, if re-running]"
---

# /setup

Builds `config/` — the nine files listed below, the contract every
other skill depends on. Conversational: one topic at a time, always
confirm your understanding back to the user *before* writing a file,
never fabricate a number or category the user didn't give you. If
something feels company-specific, it belongs in a file you write here,
never hardcoded into `skills/analysis/scripts/*.py` or
`skills/dashboard/scripts/*.py` — those must stay generic.

**Templates:** `skills/setup/templates/` has a skeleton for every file
below with the structure and comments explaining each field — start
from those, not from a blank file. `examples/example-hotels/config/`
has a fully populated *reference example* of every schema — when a
template's comments aren't enough to see the shape of real content
(the `pnl-structure.yaml` cascade, `thresholds.yaml`'s per-category
overrides, `brand.md`'s fenced `yaml` block), look at the matching demo
file. Never copy demo *content* — Example Hotels is fictional, its
numbers, categories, and heuristics are not this user's company.

**Re-running:** if `config/` already has some or all of these files,
list what exists and ask which section(s) to update rather than
restarting the whole interview. Updating one file (say, `thresholds.yaml`)
shouldn't require re-asking Phase A's entity questions.

## Phase A — Company & entities

Ask: how many entities (each becomes its own dashboard)? Ask the user to
type or upload entity names + whatever categorizations they use (brand,
country, size, region — don't assume these four, ask what they actually
track). Ask the industry, and any industry-specific factors the analysis
should know (seasonality, regulatory costs, typical margin structure).

→ `config/entities.csv` (whatever columns the user's categorizations
need — `entity_code`, `name`, `country`, `currency` are the only ones
the engine assumes exist; everything else is free-form) and the
industry/seasonality notes into `config/company-profile.md`.

## Phase B — Audience & reporting focus

Ask: who reads the dashboard (CFO, GM, board, controller), and their
financial competence — this sets tone and jargon level. What does the
audience focus on (personnel costs, revenue, EBITDA vs. GOP, cash)?
Report language(s), and whether different audiences need different
languages. Optionally: an existing report sample, to calibrate tone —
extract tone notes from it, never copy its content or numbers.

→ audience/tone/focus sections of `config/company-profile.md`.

## Phase C — P&L structure & terminology

Ask: comparison basis — budget, forecast, last year, which of these
exist, and what does the user *call* each one? Record the term verbatim;
it's used in every output exactly as they say it (`Budget`, not
`Forecast`, if that's their word). Ask for subtotal structure as an
*ordered* cascade — which categories roll into which subtotal, how
EBITDA/GOP/contribution margin (or whatever they call their profit
levels) are computed, what sits below the line. Ask for their GL → P&L
mapping file; parse it and report back category count and any
unmapped-account risk before treating the mapping as final.

→ `config/account-mapping.csv` and the full cascade (`categories`,
`subtotals`, `ratios`, and — this is easy to miss, see task 6's
tasks.md notes — `presentation_order`, the exact interleaved row order
subtotals sit in relative to categories) into `config/pnl-structure.yaml`.
If any category only applies to some entities (a department some
properties don't have, the way Example Hotels' Spa & Wellness only
exists for the Signature brand), give it an `applies_to_brands` list —
`validate_data.py` reads this generically, so this is how you model
"doesn't apply everywhere" without inventing a special case for it.

## Phase D — Sample data & data conventions

Ask for sample exports: actual P&L, budget/forecast, a transactions
sample, anything else used in reporting. For each file, explicitly
determine and confirm: delimiter, decimal/thousand separators, encoding,
date format, sign convention (are costs positive or negative? is revenue
ever stored negative?), currency (and multi-currency handling if
relevant), fiscal calendar (calendar months or 4-4-5?), month vs. YTD
columns.

**Required validation dry run:** before writing anything, parse each
sample and play it back in plain language — "Here's how I read your
P&L: 32 categories, Gross Revenue = 4.2M, costs are positive, forecast
in column F. Correct?" Only write files after the user confirms.

→ `config/data-dictionary.md` (documented structure of every input file
type, with one real sample row each — see the demo's version for the
level of detail expected: conventions table, one file-type section per
input, a validation-rules section listing exactly what `validate_data.py`
will check) and copy the samples into `references/samples/`, **renamed**
to the `{ENTITY}_{TYPE}_{PERIOD}.csv` convention you just documented —
Phase I's smoke test runs `validate_data.py` directly against this
folder, and `validate_data.py` discovers files by that exact naming
pattern, not by content. A sample that keeps its original ERP export
name won't be found.

## Phase E — Thresholds & materiality

Ask: what counts as an acceptable gap vs. the comparison basis? Capture
**both** a percentage and an absolute-currency form (e.g. "2% / 20,000
NOK") — `analyze.py` flags INVESTIGATE only when *both* are breached,
NOTE when only one is, so both numbers matter. Ask whether revenue and
cost categories should have different bands (they usually do), and
which of the user's largest categories need their own override rather
than the default. **Size the absolute floor against the category's real
Budget scale** — a floor sized for a small category will trigger on
routine noise for a large one; see task 7's tasks.md notes for the
`floor ≈ Budget × pct × 1.3` approach used for the demo, and reuse the
same reasoning here rather than guessing round numbers. Ask about known
seasonality and recurring anomalies (vacation-pay months, annual
license/audit fees) so the analysis doesn't flag expected patterns —
these still flag mechanically (that's correct), they're recorded here so
the narrative pass in `/analysis` recognizes them as expected instead of
alarming.

→ `config/thresholds.yaml` (`default`, `category_overrides`,
`unmapped_account_materiality_floor`, `seasonality_notes`, and
`kpi_thresholds` — see Phase G below, write this section once the KPIs
are known).

## Phase F — Investigation heuristics (the differentiator)

For the user's 5-8 largest cost categories, ask: "When this is
unexpectedly HIGH, what do you check first? When it's unexpectedly LOW?"
Capture their answers as short, imperative checklists in their own
words — this is the controller's tacit knowledge, not something to
paraphrase into generic advice. Also ask for any benchmark ranges they
apply (e.g. "F&B cost of goods should be 28-33% of F&B revenue for our
full-service sites"), scoped by entity category if it varies.

→ `config/investigation-guide.md`, one section per category with a HIGH
checklist, a LOW checklist, and a benchmark line if they gave one.

## Phase G — KPIs

Ask which KPIs to display (recommend 3-6 if they're unsure). For each:
name, formula, denominator definition, data source/format, and whether
it's measured against the comparison basis or a fixed target (if fixed:
collect the target, per entity if it varies). A KPI that's a pure P&L
ratio (like GOP %) needs nothing beyond what Phase C already captured.
A KPI that needs operational data the P&L doesn't have (Example Hotels'
Occupancy %/RevPAR/Revenue per FTE all need rooms/FTE data) needs a
sample of that data too — if Phase D didn't already cover it, go back
and ask now, and add a "stats"-equivalent file section to
`data-dictionary.md`. This is a real engine limitation worth knowing:
the stats file's *columns* are currently fixed to the hotel-shaped
rooms/FTE schema (`validate_data.py`/`preprocess.py`), not derived from
config — a KPI needing a genuinely different operational-data shape
(e.g. "units produced" for a manufacturer) isn't supported without an
engine change. Say so plainly rather than forcing the user's data into
a rooms/FTE-shaped file it doesn't fit; a pure P&L ratio KPI is always
available as a fallback that avoids this limitation entirely.
**Formula variable names must work for both an actual and a budget
evaluation pass** — don't bake `_actual` or `_budget` into a formula's
variable name (see task 6's tasks.md notes for why `total_revenue / fte`
is correct and `total_revenue / fte_actual` is not).

→ `config/kpi-definitions.yaml`. Each KPI's `format` (`percent` or
`currency`) determines how `analyze.py` thresholds it (percentage-point
vs. relative-%) — set it correctly, it's not just a display hint. Then
go back and write `thresholds.yaml`'s `kpi_thresholds` section, one
entry per KPI id, in the matching shape for its format.

## Phase H — Branding

Ask for anything showing the brand: a presentation, website, existing
report, or logo file. Extract primary/secondary colors (hex), fonts
with web-safe fallbacks, logo treatment, and overall feel
(minimal/rich, formal/friendly). If nothing is provided, apply a
tasteful default theme and say so plainly — don't present a guessed
theme as if it came from the user.

→ `config/brand.md`: the human-readable tables/prose (for anyone
reading this file later) *and* the fenced ` ```yaml ` token block
`render_dashboard.py` actually reads — keep them in sync, see the
demo's `brand.md` for the exact block shape. If a logo file was
provided, store it under `references/brand/` and set `logo.file` to
its path relative to `config/`; otherwise set `logo.wordmark` to the
company name and leave `logo.file: null`.

## Phase I — Wrap-up

Summarize everything captured and list every config file written. Run
the validation smoke test:

```bash
python3 skills/analysis/scripts/validate_data.py <a period from the samples> --config-dir config --inbox-dir references/samples
```

If this reports errors, something in the interview doesn't match what
`validate_data.py` actually expects — fix the config file, don't
weaken the check. Once it's clean, tell the user they're ready for the
monthly loop and point them to `docs/HANDBOOK.md`.
