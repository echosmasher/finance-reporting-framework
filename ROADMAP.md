# Roadmap

Explicitly out of scope for v1 (see `PLAN.md` §10) — listed here so it's
clear these were considered and deliberately deferred, not overlooked.

## Feedback / correction workflow

**Reviewer-side comments and narrative edits shipped** (`/feedback`,
Phase 6 task 26 in `tasks.md`) — after `/dashboard` renders, tell Claude
Code in plain language to pin a comment to a row/KPI, or edit/remove the
LLM-written narrative for a flagged item; it re-renders the dashboard
with the change applied. This works because it's Claude Code editing a
local JSON file and re-rendering, not the deployed dashboard's own
JavaScript making a write-back request — so the Google Apps Script
sandbox problem below never applies to it.

Still out of scope, deliberately:

- **GM-facing write-back from inside the served dashboard itself** —
  a reader submitting a comment directly from the HTML they're viewing,
  with no Claude Code session in the loop. `docs/LESSONS_LEARNED.md`'s
  first case study covers why this is harder than "just add a comment
  box" once a dashboard is served through the Google Apps Script tier —
  any real version of this needs to either avoid that sandbox entirely
  (a served app, tier 3 territory) or lean on a native platform feature
  (Drive comments, a linked form) instead of the dashboard's own
  JavaScript making the request.
- **An adjustment cascade through subtotals when a number is
  corrected.** `/feedback` deliberately never touches a number or a
  status — see `CLAUDE.md`'s Python-computes/Claude-interprets rule. A
  wrong number is a `/setup`/`/analysis` problem (bad threshold, bad
  input data), not something a comment should be able to override.
- **Versioned dashboards** — no history of a dashboard's prior states,
  before/after a `/feedback` edit, is kept beyond `feedback/`'s own
  edit-attribution fields (`author`, `created_at`, `supersedes`).

## YTD and trailing-12 views; multi-period trend charts

Every file and every output in v1 is single-month. A YTD or
trailing-12-month view needs its own aggregation logic (which periods
roll up, how a mid-year config change — a new threshold, a category
added mid-year — is handled retroactively) that doesn't exist yet.

## Consolidation across entities with eliminations

Each entity gets its own dashboard; there's no "group total" view, and
no intercompany elimination logic. Straightforward for entities sharing
a currency; genuinely harder once multi-currency consolidation (below)
is also in play.

## Multi-currency consolidation

Each entity currently reports in its own local currency, full stop — no
FX conversion, no group-level currency anywhere. Real consolidation
needs a documented FX rate source (spot vs. average vs. period-end,
and where the rate comes from) before it's trustworthy enough to ship,
not just a conversion function.

## Non-P&L statements (balance sheet, cash flow)

The entire config layer (`pnl-structure.yaml`, `thresholds.yaml`,
`investigation-guide.md`) is P&L-shaped. A balance sheet or cash flow
statement needs its own structure — different subtotal logic (a balance
sheet balances, it doesn't cascade to a single bottom line the way a
P&L does), different materiality intuitions, and likely its own config
files rather than an extension of the existing ones.

## Automated inbox watcher / scheduled runs

`/analysis` and `/dashboard` are run on demand. A watcher that triggers
automatically when new files land in `inbox/` (or on a schedule) is a
reasonable next step once the manual loop is well-worn enough to
automate — see `docs/HANDBOOK.md` for the current manual loop.

## Localization packs for report languages

`/setup` Phase B captures a report language, and every generated
narrative is written in it — but there's no packaged set of
pre-translated UI strings, date/number formatting per locale, or
right-to-left layout support in the dashboard template. Each company's
`/setup` run currently produces narrative in one language via the LLM
directly; a proper localization pack would be about the surrounding
scaffolding (labels, formatting conventions) a single interview
currently doesn't systematize across companies.

---

## A cross-industry operational-data schema (found during v1, not planned originally)

Not in PLAN's original roadmap, but worth recording since it's a real,
disclosed v1 limitation discovered while building: the `stats` file's
columns (`rooms_available`, `fte_actual`, etc. — see
`data-dictionary.md`) are currently fixed to a hospitality-shaped
schema. A KPI needing genuinely different operational data (e.g. "units
produced" for a manufacturer) isn't supported without an engine change.
Generalizing this — letting `kpi-definitions.yaml` or
`data-dictionary.md` declare an arbitrary stats schema that
`preprocess.py` builds its KPI-evaluation namespace from generically —
is a real piece of work, not a config change, and is a natural
companion to the industries roadmap above once this framework is used
somewhere other than hospitality.
