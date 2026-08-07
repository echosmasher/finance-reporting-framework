# Implementation Plan — AI-Assisted Financial Reporting Framework (v1)

**Working name:** `finance-reporting-framework` (rename freely)
**Purpose of this document:** Complete implementation plan for Claude Code. Build the repo exactly as specified here, in the phase order given. Ask before deviating from any DECISION marked below.

---

## 1. Project Overview

A public, portfolio-quality GitHub repo: an AI-assisted monthly financial reporting framework for accountants and financial controllers. The user (a controller who already produces reports manually and knows their own company's reporting standards) configures the framework once via an interview skill, then runs a monthly loop: drop ERP exports in an inbox → run analysis → generate branded HTML dashboards for their audience (CFO, GM, board, etc.).

**Target audience for the repo itself:** hiring managers and technical reviewers. The repo must demonstrate value in under 2 minutes via the README and a pre-built demo — without anyone running the setup interview.

**Elevator pitch (use in README):** "Monthly management reporting takes controllers days of manual work. This framework compresses it to an upload-and-review loop: deterministic Python computes the numbers, Claude interprets them using *your* company's thresholds, terminology, and institutional knowledge — captured once during setup."

---

## 2. Core Design Principles (non-negotiable)

1. **Engine vs. config separation.** Skills and scripts are generic engines. Everything company-specific — entities, account mapping, thresholds, KPI definitions, tone, investigation heuristics, branding — lives in `config/`, produced by `/setup`. No company-specific values hardcoded anywhere in `skills/` or `scripts/`.
2. **Python computes, Claude interprets.** All parsing, variance calculation, aggregation, and threshold flagging happens in deterministic, testable Python scripts. Claude's role is narrative: explaining deviations, writing recommendations, adapting tone to the audience. Analysis output must be reproducible and auditable.
3. **Self-contained HTML output.** Dashboards are single HTML files with inline CSS, inline data, no CDN calls, no external requests. They must render offline, from a shared drive, as an email attachment, or via any static host.
4. **Demo-first.** The repo ships with a fully configured fictional company and pre-generated outputs in `examples/`. The demo is the portfolio; the skills prove it generalizes.
5. **Fail loudly and specifically.** Data validation errors must name the file, row/column, and expected format. Never silently produce a wrong number.
6. **Clean-room content.** No real company names, benchmarks, account codes, thresholds, property codes, or workflow details from any prior employer. All reference values in the demo are synthetic and clearly plausible-but-fictional.

---

## 3. Repository Structure

```
finance-reporting-framework/
├── README.md                      ← See §9. The most important file in the repo.
├── ROADMAP.md                     ← v2 ideas (see §10)
├── LICENSE                        ← MIT
├── .gitignore                     ← ignores inbox/*, outputs/*, config/* (except .gitkeep + demo)
├── CLAUDE.md                      ← Claude Code project instructions (see §8)
│
├── skills/
│   ├── setup/
│   │   ├── SKILL.md               ← /setup interview skill (see §5)
│   │   └── templates/             ← config file templates the skill fills in
│   ├── analysis/
│   │   ├── SKILL.md               ← /analysis skill (see §6)
│   │   └── scripts/
│   │       ├── validate_data.py
│   │       ├── preprocess.py
│   │       └── analyze.py
│   └── dashboard/
│       ├── SKILL.md               ← /dashboard skill (see §7)
│       ├── scripts/
│       │   └── render_dashboard.py
│       └── templates/
│           └── dashboard_base.html
│
├── config/                        ← Populated by /setup. Only demo config committed.
│   └── .gitkeep
│
├── inbox/                         ← User drops monthly ERP exports here
│   └── .gitkeep
│
├── outputs/                       ← Generated analyses and dashboards
│   └── .gitkeep
│
├── references/                    ← User-maintained reference data (mapping files, samples)
│   └── .gitkeep
│
├── examples/                      ← Complete demo company, end to end (see §4)
│   └── example-hotels/
│       ├── config/                ← fully populated config layer
│       ├── inbox/                 ← 3 months of synthetic ERP exports
│       ├── outputs/               ← pre-generated analyses + dashboards
│       └── README.md              ← how the demo was generated, how to re-run it
│
├── docs/
│   ├── HANDBOOK.md                ← monthly workflow, step by step
│   ├── DEPLOYMENT.md              ← three-tier deployment guide (see §7.4)
│   ├── DATA_REQUIREMENTS.md       ← what exports the framework needs and how to produce them
│   └── LESSONS_LEARNED.md         ← architectural findings (see §9.3)
│
└── tests/
    ├── test_preprocess.py
    ├── test_analyze.py
    └── fixtures/                  ← tiny synthetic CSVs for tests
```

---

## 4. Demo Company: Example Hotels (synthetic)

**DECISION:** Build the demo first (Phase 1 below), because it defines the data shapes everything else consumes, and it lets every later component be tested against real files.

- **Example Hotels** — fictional Nordic hospitality group. 4 entities, with plain numeric identifier codes:
  - `001` Example Hotel Oslo (Norway, "Signature" brand, large)
  - `002` Example Hotel Bergen (Norway, "Signature", medium)
  - `003` Example Hotel Stockholm (Sweden, "Compact" brand, small)
  - `004` Example Hotel Copenhagen (Denmark, "Signature", conference-heavy)
- **Currency:** each entity reports in its country's local currency — the currency is determined by the entity's country (`001`/`002` NOK, `003` SEK, `004` DKK). `entities.csv` carries a country column, and the country → currency mapping lives in the demo config. Each dashboard is per-entity in local currency; cross-currency consolidation stays on the roadmap (§10). **Language:** English reports (keep demo accessible to international reviewers).
- **Synthetic data generator:** `examples/example-hotels/generate_demo_data.py` — produces 3 months (e.g. 01-2026 through 03-2026) of:
  - Per-entity P&L exports (actuals by GL account)
  - A budget/forecast file per entity
  - A transactions file (GL detail: date, account, vendor, description, amount, entity, department)
- Data must contain **planted stories** the analysis should find, e.g.: an energy cost gap from a missing invoice in month 2; F&B cost of goods spiking with an inventory adjustment; payroll deviation correlated with occupancy; one entity beating forecast cleanly (so not everything is a problem). Document the planted stories in `examples/example-hotels/README.md` so a reviewer can verify the analysis caught them.
- Demo config includes: account mapping (~25–35 P&L categories over ~150 synthetic GL accounts), thresholds, 4 KPIs (Occupancy %, RevPAR, Revenue per FTE, GOP %), a simple brand file (two colors + font), investigation heuristics for 6 cost categories.
- Pre-generate and commit all outputs: per-entity analysis HTML + dashboards for all 3 months. Take screenshots for the README.

---

## 5. Skill: `/setup`

**Purpose:** One-time (re-runnable) interview that produces the complete config layer. Conversational, one topic at a time, confirming understanding before writing files. If config already exists, offer to update specific sections rather than restart.

### 5.1 Interview phases

**Phase A — Company & entities**
- How many entities, processed as individual dashboards? Ask user to type or upload a file of entity names + categorizations (brand, country, size, region — whatever they use).
- Industry (or industries), and any industry-specific factors the analysis should know (seasonality patterns, regulatory costs, typical margin structure).
- → writes `config/entities.csv` and industry notes into `config/company-profile.md`.

**Phase B — Audience & reporting focus**
- Who reads the dashboard (CFO, GM, board, controller)? What is their financial competence? → determines tone and jargon level.
- What does the audience focus on (personnel costs, revenue, EBITDA vs GOP, cash)?
- Report language(s); whether different audiences get different languages.
- Optional: upload an existing report sample to calibrate tone of voice — extract tone notes, never copy content.
- → writes audience/tone/focus sections of `config/company-profile.md`.

**Phase C — P&L structure & terminology**
- Comparison basis: budget, forecast, last year — which of these exist, and what does the user *call* them? (Terminology is recorded and used verbatim in all output.)
- Subtotal definitions: how the P&L cascades — which categories roll into which subtotals, how EBITDA/GOP/contribution margin are computed, what sits below the line. Elicit as an ordered hierarchy.
- GL → P&L group mapping: ask user to upload their mapping file. Parse it, report back category count and any unmapped-account risks.
- → writes `config/account-mapping.csv` and the hierarchy into `config/pnl-structure.yaml`.

**Phase D — Sample data & data conventions**
- Ask for sample exports from the ERP: actual P&L report, budget/forecast, transactions sample, and any other data used in reporting.
- For each file, explicitly determine and confirm: delimiter, decimal & thousand separators, encoding, date format, sign convention (are costs positive or negative? is revenue stored negative?), currency (and multi-currency handling if applicable), fiscal calendar (calendar months? 4-4-5?), month vs YTD columns.
- **Validation dry run (required):** parse each sample and play it back — "Here's how I read your P&L: 32 categories, Gross Revenue = 4.2M, costs are positive, forecast in column F. Correct?" Only after confirmation:
- → writes `config/data-dictionary.md` (documented structure of every input file type, with a sample row each) and copies samples into `references/samples/`.

**Phase E — Thresholds & materiality**
- What counts as an acceptable gap vs forecast/budget? Capture **both** percentage and absolute forms (e.g. 2% / 20 000 NOK), and allow per-category overrides (revenue vs cost categories usually differ).
- Known seasonality and recurring anomalies (vacation pay months, annual license/audit fees) so the analysis doesn't flag expected patterns.
- → writes `config/thresholds.yaml`.

**Phase F — Investigation heuristics (the differentiator)**
- For the user's 5–8 largest cost categories, ask: "When this is unexpectedly HIGH, what do you check first? When it's unexpectedly LOW?" Capture the controller's tacit knowledge as short, imperative checklists.
- Also: any benchmark ranges the user applies (e.g. "F&B cost of goods should be 28–33% of F&B revenue for our full-service sites"), scoped by entity category if relevant.
- → writes `config/investigation-guide.md`.

**Phase G — KPIs**
- Which KPIs to display (recommend 3–6). For each: **name, formula, denominator definition**, data source/format (ask for a sample), and whether measured against forecast or fixed targets. If fixed targets: collect them (per entity if applicable).
- → writes `config/kpi-definitions.yaml`.

**Phase H — Branding**
- Ask for anything displaying the brand (presentation, website URL, existing report, logo file). Extract: primary/secondary colors (hex), fonts with web-safe fallbacks, logo treatment, overall feel (minimal/rich, formal/friendly).
- If nothing provided: apply a tasteful default theme and say so.
- → writes `config/brand.md` (design tokens) and stores any logo in `references/brand/`.

**Phase I — Wrap-up**
- Summarize everything captured, list the config files written, and run `validate_data.py` against the samples as a final smoke test. Tell the user they're ready for the monthly loop and point to `docs/HANDBOOK.md`.

### 5.2 Config layer (contract for all other skills)

```
config/
├── company-profile.md        ← audience, tone, focus, industry notes, languages
├── entities.csv              ← entity code; name; categorizations…
├── pnl-structure.yaml        ← ordered category hierarchy + subtotal formulas + terminology
├── account-mapping.csv       ← GL account → P&L category
├── thresholds.yaml           ← default + per-category materiality (pct and absolute), seasonality notes
├── investigation-guide.md    ← per-category HIGH/LOW checklists + benchmark ranges
├── kpi-definitions.yaml      ← name, formula, source, target mode, targets
├── data-dictionary.md        ← input file formats, conventions, sample rows
└── brand.md                  ← design tokens
```

`/analysis` and `/dashboard` must **refuse to run with a clear message** if required config files are missing, pointing the user to `/setup`.

---

## 6. Skill: `/analysis`

**Purpose:** For a given period (and optionally a subset of entities), turn inbox files into a structured analysis per entity.

**Flow:**
1. Discover input files in `inbox/` per the naming conventions in `config/data-dictionary.md`. Report what was found and what's missing per entity.
2. `validate_data.py` — schema/convention checks against the data dictionary. Hard-fail with file/row/column specifics on violations (unmapped GL accounts above a materiality floor are a hard fail; below it, a warning list).
3. `preprocess.py` — normalize each entity's actuals + forecast/budget + LY (if available) into one standard intermediate CSV per entity per period: `Category; Act; Act %; Fct; Fct %; Diff; Diff pp; LY; LY %` (labels taken from the user's terminology in config). Compute subtotals from `pnl-structure.yaml` — never trust subtotal rows in the source export; recompute and warn on mismatch.
4. `analyze.py` — deterministic flagging engine: applies `thresholds.yaml` to every category and KPI, outputs a machine-readable `analysis_{ENTITY}_{PERIOD}.json` containing per-category status (ON TARGET / NOTE / INVESTIGATE), deviation values, revenue-mix shifts, and (if a transactions file exists) a per-flagged-category transaction drill-down grouped by vendor/account/type.
5. **Claude narrative pass:** using the JSON + `investigation-guide.md` + `company-profile.md`, write the narrative: an executive summary, per-flagged-category explanation with the user's own investigation prompts, and a profitability summary. Tone and jargon per audience config. Frame concerns as investigation prompts, not accusations; lead with wins.
6. Output per entity: `outputs/{ENTITY}-Analysis_{PERIOD}.html` (readable analyst-facing report) plus the JSON (consumed by `/dashboard`). Print a run summary: entities processed, flags raised, files skipped.

Batch behavior: no arguments → process everything in inbox for the detected period; accept `for 001, 003`-style scoping.

Graceful degradation: no transactions file → skip drill-down section with a note; no LY data → omit LY columns.

---

## 7. Skill: `/dashboard`

**Purpose:** Turn an entity's analysis JSON into a polished, audience-facing, brand-styled, fully self-contained HTML dashboard.

### 7.1 Content sections
1. Header: entity name, period, logo/brand treatment.
2. KPI cards (from `kpi-definitions.yaml`): value, target/forecast, delta, status color.
3. Profitability summary: the audience's focus metric (GOP/EBITDA per config) with narrative.
4. P&L table: category, actual, %, forecast, diff, status — statuses color-coded; the audience's focus categories visually emphasized.
5. Deviation highlights: flagged categories with the narrative explanations and investigation prompts.
6. Drill-down: collapsible `<details>` per flagged cost category with transaction breakdown (only if transaction data exists).

### 7.2 Technical requirements
- Single file, inline CSS, inline data, zero external requests. Logo embedded as base64 if provided.
- Brand tokens from `config/brand.md`; clean default theme as fallback.
- Print-friendly (people will PDF these); sensible on mobile.
- Status colors must remain distinguishable for color-blind readers (pair color with icon/label).

### 7.3 Invocation
`/dashboard` (all entities with analysis JSON for latest period) or scoped by entity/period. Output: `outputs/{ENTITY}-Dashboard_{PERIOD}.html`.

### 7.4 `docs/DEPLOYMENT.md` — three tiers
1. **File-based (zero infrastructure, default):** shared drive or email attachment. Works because dashboards are self-contained.
2. **Google Apps Script web app:** step-by-step guide — Drive folder, `Code.gs` serving HTML by token/entity parameter, deploy-as-web-app walkthrough, access control notes. Explicit caveat: static serving only; in-page write-backs (comments/forms) are blocked by the GAS iframe sandbox — link to LESSONS_LEARNED.md.
3. **Static hosting (GitHub Pages / internal web server):** for orgs that allow it; used for the live demo. Warn clearly: never publish real financials to a public host — this tier is for demos and internal servers only.

The `/dashboard` SKILL.md should end by asking the user about their tools/permissions and recommending a tier.

---

## 8. `CLAUDE.md` (project instructions for Claude Code users of the repo)

Short file covering: the three skills and when to use them; the engine/config principle ("never hardcode company specifics — if something feels company-specific, it belongs in config/"); the Python-computes/Claude-interprets rule; where inputs and outputs live; run tests after changing scripts.

---

## 9. Documentation

### 9.1 README.md (build last, budget real effort)
Order: one-line pitch → 2–3 dashboard screenshots → link to live demo (GitHub Pages, Example Hotels) → problem statement (manual reporting cost) → how it works (setup once / monthly loop diagram) → quickstart with the demo (`clone → open examples/example-hotels/outputs/… → or re-run /analysis on demo data`) → quickstart for your own company (`/setup`) → architecture section (config-layer diagram, determinism principle) → deployment summary → roadmap link → license.

### 9.2 HANDBOOK.md
The monthly loop, step by step, written for the controller persona: export from ERP → drop in inbox → `/analysis` → review analyst HTML → `/dashboard` → distribute. Include file-naming reference and a troubleshooting table (common validation failures and fixes).

### 9.3 LESSONS_LEARNED.md
Genericized architectural findings, written as short case studies. Include: (a) why interactive comment submission from statically-served dashboards fails under the Google Apps Script iframe sandbox (fetch to localhost/private hosts is silently blocked), and the viable alternatives (native platform features, or avoiding the sandbox); (b) why self-contained HTML was chosen over a served app; (c) why deterministic flagging is separated from LLM narrative. No employer-identifying details.

### 9.4 DATA_REQUIREMENTS.md
What exports the framework needs (actuals by GL account, budget/forecast, optional transactions), with generic guidance for producing them from common ERPs, and the conventions `/setup` will ask about.

---

## 10. ROADMAP.md (explicitly out of scope for v1)

- Feedback/correction workflow (reviewer comments, adjustment cascade through subtotals, versioned dashboards)
- YTD and trailing-12 views; multi-period trend charts
- Consolidation across entities with eliminations
- Multi-currency consolidation
- Non-P&L statements (balance sheet, cash flow)
- Automated inbox watcher / scheduled runs
- Localization packs for report languages

Do **not** build any of these in v1, even partially.

---

## 11. Implementation Phases (execute in order)

**Phase 1 — Demo data foundation**
1. Scaffold repo structure, LICENSE, .gitignore, CLAUDE.md stub.
2. Build `generate_demo_data.py` + Example Hotels config layer (hand-write config; it doubles as the reference example of every config schema).
3. Generate 3 months of demo inbox files with planted stories; document stories in `examples/example-hotels/README.md`.
   - *Acceptance:* demo config validates; generated CSVs match the demo data dictionary; planted deviations are present in the numbers.

**Phase 2 — Analysis engine**
4. `validate_data.py`, `preprocess.py`, `analyze.py` + tests against fixtures derived from demo data.
5. `/analysis` SKILL.md, including the Claude narrative-pass instructions.
   - *Acceptance:* running `/analysis` on Example Hotels month 2 flags the planted energy and F&B stories, does not flag the clean entity's core categories, recomputed subtotals match, JSON schema stable and documented.

**Phase 3 — Dashboard**
6. `dashboard_base.html` + `render_dashboard.py` (brand-token injection, KPI cards, table, drill-down).
7. `/dashboard` SKILL.md incl. deployment-tier recommendation dialogue.
   - *Acceptance:* dashboard renders offline with zero network requests (verify in devtools), applies Example Hotels brand tokens, prints cleanly, drill-down present for flagged categories only.

**Phase 4 — Setup skill**
8. `/setup` SKILL.md with the full Phase A–I interview, config templates, and the validation dry-run behavior.
   - *Acceptance:* dry-run test — run `/setup` pretending to be a new company using a *modified* copy of demo samples (different delimiter + sign convention); resulting config must let `/analysis` run correctly without script changes.

**Phase 5 — Docs, demo outputs, polish**
9. Pre-generate and commit all Example Hotels outputs; screenshots.
10. HANDBOOK, DEPLOYMENT, DATA_REQUIREMENTS, LESSONS_LEARNED, ROADMAP, README.
11. CI: run tests + regenerate demo analysis on push (GitHub Actions); deploy one demo dashboard to GitHub Pages.
    - *Acceptance:* fresh-clone test — a new user can follow README quickstart to a rendered dashboard using only committed files; CI green.

**Final review checklist before publishing:**
- [ ] Grep the repo for any real company names, brands, property codes, or benchmark values — must be zero hits.
- [ ] All demo numbers synthetic; planted stories documented.
- [ ] No hardcoded company specifics outside `config/` and `examples/`.
- [ ] Dashboards verified offline / zero external requests.
- [ ] README screenshots current with latest output styling.
