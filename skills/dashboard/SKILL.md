---
description: Turn an entity's analysis into a polished, brand-styled, self-contained HTML dashboard for the GM/CFO/board — and recommend how to get it in front of them.
argument-hint: "[period] [for <entity>[, <entity>...]]"
---

# /dashboard

Turns `outputs/analysis_{ENTITY}_{PERIOD}.json` (and the narrative
written during `/analysis`) into `outputs/{ENTITY}-Dashboard_{PERIOD}.html`
— a polished, audience-facing, brand-styled, fully self-contained
report. This is a different *presentation* of the same numbers
`/analysis` already computed and narrated, never a second source of
them: `/dashboard` doesn't recompute anything and doesn't write new
narrative text.

## 0. Dependency check

`/dashboard` depends on `/analysis` having already run for this
period — it reads `analysis_{ENTITY}_{PERIOD}.json`, it doesn't produce
it. If that file is missing for an entity:

```bash
ls outputs/analysis_*_<period>.json 2>/dev/null
```

tell the user to run `/analysis <period>` first and stop for that
entity (this is also how a missing/incomplete `config/` surfaces
indirectly — `/analysis` already refused and pointed to `/setup` before
`/dashboard` would ever be reached).

If `outputs/narrative_{ENTITY}_{PERIOD}.json` is missing but the
analysis JSON exists, `render_dashboard.py` still renders a complete
dashboard — the KPI cards, P&L table, and drill-downs all come from the
analysis JSON regardless. Only the profitability summary and each
flagged item's explanation show a placeholder ("narrative not yet
written") instead of prose. Mention this to the user rather than
silently shipping a dashboard with unwritten narrative sections.

**Demo mode:** if the user asks to run this against the Example Hotels
demo, use `examples/example-hotels/config` and
`examples/example-hotels/outputs` instead of `config`/`outputs`.

## 1. Resolve scope

Same rules as `/analysis`: no arguments → every entity with an
`analysis_*.json` for the latest period found in `outputs/`; `for 001,
003` → just those entity codes; an explicit period overrides detection.

## 2. Render

```bash
python3 skills/dashboard/scripts/render_dashboard.py <period> [--entities <codes>]
```

Reads the analysis + narrative JSON, applies brand tokens from
`config/brand.md`'s fenced `yaml` block (falling back to a clean default
theme if the company has none), and writes
`outputs/{ENTITY}-Dashboard_{PERIOD}.html` — single file, inline CSS,
inline data, zero external requests, logo embedded as base64 if one is
configured. Print the script's own summary to the user (entities
rendered, any skipped for a missing analysis JSON).

Don't hand-edit or regenerate the HTML yourself — if a dashboard looks
wrong, the fix belongs in `dashboard_base.html` or `render_dashboard.py`
(a rendering bug) or in the narrative JSON from `/analysis` (a content
issue), not in the rendered output directly.

## 3. Recommend a deployment tier

After rendering, ask the user how they plan to get this in front of its
audience, and recommend a tier based on their answer. Three tiers exist
(full walkthroughs in `docs/DEPLOYMENT.md`):

1. **File-based (default, zero infrastructure).** Email the HTML file
   as an attachment, or drop it on a shared drive. Works because the
   file is genuinely self-contained — no server, no setup, opens in any
   browser offline. Recommend this unless the user specifically wants
   something else; it's the right default for most controllers.
2. **Google Apps Script web app.** For a company already on Google
   Workspace that wants dashboards reachable by URL instead of email
   attachments: a Drive folder holds the HTML files, a small `Code.gs`
   serves them by entity/period parameter. Static serving only — flag
   this explicitly if the user wants interactive features (comments,
   approval clicks, anything that writes back): the GAS iframe sandbox
   blocks that (see `docs/LESSONS_LEARNED.md` for why). Recommend this
   tier only if the user confirms Google Workspace admin access to set
   up the Apps Script project.
3. **Static hosting (GitHub Pages, internal web server).** For an
   organization that already has one and allows publishing to it.
   **Never recommend a public host (like GitHub Pages) for real
   financials** — that tier is for the public demo and genuinely
   internal servers only; say this plainly if the user's company data
   is involved, don't just let them assume it's fine because the demo
   uses it.

Ask what they actually have access to before recommending — don't
default to the most sophisticated-sounding option.
