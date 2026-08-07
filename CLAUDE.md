# finance-reporting-framework — Claude Code instructions

An AI-assisted monthly financial reporting framework for accountants and
financial controllers. See `PLAN.md` for the full spec and `tasks.md` for
build status.

## The three skills

- **`/setup`** — one-time (re-runnable) interview that produces the config
  layer in `config/`. Run this first for a new company.
- **`/analysis`** — turns ERP exports dropped in `inbox/` into a structured,
  per-entity analysis (`outputs/*-Analysis_*.html` + a machine-readable JSON).
- **`/dashboard`** — turns an entity's analysis JSON into a polished,
  brand-styled, self-contained HTML dashboard (`outputs/*-Dashboard_*.html`).

`/analysis` and `/dashboard` both refuse to run with a clear message if
required `config/` files are missing — they point the user back to `/setup`.

## Engine vs. config (non-negotiable)

`skills/` and `scripts/` are generic engines. Everything company-specific —
entities, account mapping, thresholds, KPI definitions, tone, investigation
heuristics, branding — lives in `config/`, produced by `/setup`. If something
feels company-specific, it belongs in `config/`, not in a skill or script.

## Python computes, Claude interprets

All parsing, variance calculation, aggregation, and threshold flagging
happens in deterministic, testable Python (`skills/*/scripts/`). Claude's
role is narrative only: explaining deviations, writing recommendations,
adapting tone to the audience. Analysis output must be reproducible and
auditable — never let an LLM produce a number that isn't traceable back to
Python.

## Where things live

- `config/` — populated by `/setup`; the contract every other skill reads.
- `inbox/` — user drops monthly ERP exports here.
- `outputs/` — generated analyses and dashboards.
- `references/` — user-maintained reference data (mapping files, samples).
- `examples/example-hotels/` — the fully configured demo company, end to end.
  Treat it as the reference example of every config schema.

## After changing scripts

Run the test suite: `pytest tests/`.
