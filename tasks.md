# finance-reporting-framework — implementation tasks

Derived from `PLAN.md` §11 (implementation phases), expanded into commit-sized units.
Read `PLAN.md` for the "why" and the acceptance criteria behind each phase — this file just
tracks status and dependencies.

**Workflow:** commit after each finished task; ask before pushing to GitHub.
**Archon:** this repo is Archon-initialized (`.archon/`, git repo on `main`). Delegate larger
independent tasks with `archon workflow run <workflow> --branch <branch> "<message>"` — always
in the background, always with `--branch` for worktree isolation. Good fits here:
`archon-plan-to-pr` / `archon-feature-development` for phase-sized chunks, `archon-assist` for
one-offs, `archon-comprehensive-pr-review` before merging anything substantial.

---

## Phase 0 — Repo groundwork

- [x] 0. Initialize git (`main`) + Archon scaffold (`.archon/{commands,workflows,scripts}`, `.archon/config.yaml`), seed `.gitignore`

## Phase 1 — Demo data foundation

- [ ] 1. Scaffold repo structure per PLAN §3: `skills/`, `config/`, `inbox/`, `outputs/`, `references/`, `examples/`, `docs/`, `tests/` with `.gitkeep`s; MIT `LICENSE`; extend `.gitignore`; `CLAUDE.md` stub (PLAN §8)
- [ ] 2. Hand-write the Example Hotels config layer (`examples/example-hotels/config/`) — all 9 files from PLAN §5.2: `company-profile.md`, `entities.csv` (4 entities + country), `pnl-structure.yaml`, `account-mapping.csv` (~25–35 categories over ~150 GL accounts), `thresholds.yaml`, `investigation-guide.md` (6 cost categories), `kpi-definitions.yaml` (Occupancy %, RevPAR, Revenue per FTE, GOP %), `data-dictionary.md`, `brand.md`. This doubles as the reference example of every config schema — blocked by 1
- [ ] 3. Build `examples/example-hotels/generate_demo_data.py` — 3 months (01-2026…03-2026) × 4 entities of P&L actuals, budget/forecast, and GL transactions, each in its entity's local currency (NOK/SEK/DKK) — blocked by 2
- [ ] 4. Plant the stories in the generated data (energy gap from a missing invoice in M2; F&B COGS spike with inventory adjustment; payroll deviation tracking occupancy; one entity cleanly beating forecast) and document them in `examples/example-hotels/README.md` so a reviewer can verify the analysis catches them — blocked by 3
  - *Acceptance:* demo config validates; generated CSVs match the demo data dictionary; planted deviations measurably present in the numbers

## Phase 2 — Analysis engine

- [ ] 5. `skills/analysis/scripts/validate_data.py` — schema/convention checks against `data-dictionary.md`; hard-fail with file/row/column specifics; unmapped GL accounts above the materiality floor are a hard fail, below it a warning list — blocked by 4
- [ ] 6. `skills/analysis/scripts/preprocess.py` — normalize actuals + forecast/budget + LY into one intermediate CSV per entity per period (`Category; Act; Act %; Fct; Fct %; Diff; Diff pp; LY; LY %`, labels from config terminology); recompute all subtotals from `pnl-structure.yaml` and warn on source mismatch — blocked by 5
- [ ] 7. `skills/analysis/scripts/analyze.py` — deterministic flagging engine: apply `thresholds.yaml` per category and KPI, emit `analysis_{ENTITY}_{PERIOD}.json` (status ON TARGET / NOTE / INVESTIGATE, deviations, revenue-mix shifts, per-flagged-category transaction drill-down grouped by vendor/account/type). Document the JSON schema — blocked by 6
- [ ] 8. `tests/test_preprocess.py`, `tests/test_analyze.py` + `tests/fixtures/` (tiny synthetic CSVs derived from demo data) — blocked by 7
- [ ] 9. Analyst-facing report renderer → `outputs/{ENTITY}-Analysis_{PERIOD}.html` — blocked by 7
- [ ] 10. `skills/analysis/SKILL.md` — discovery/batch behavior (no args = whole inbox for detected period, `for 001, 003` scoping), missing-config refusal pointing at `/setup`, graceful degradation (no transactions → skip drill-down; no LY → drop LY columns), and the Claude narrative-pass instructions (exec summary, per-flag explanation using `investigation-guide.md`, profitability summary, tone per `company-profile.md`, lead with wins, frame concerns as investigation prompts) — blocked by 9
  - *Acceptance:* `/analysis` on Example Hotels month 2 flags the planted energy + F&B stories, doesn't flag the clean entity's core categories, recomputed subtotals match, JSON schema stable

## Phase 3 — Dashboard

- [ ] 11. `skills/dashboard/templates/dashboard_base.html` — header/brand, KPI cards, profitability summary, P&L table, deviation highlights, collapsible `<details>` drill-down; inline CSS only; print-friendly; mobile-sensible; color-blind-safe statuses (color + icon/label) — blocked by 7
- [ ] 12. `skills/dashboard/scripts/render_dashboard.py` — brand-token injection from `brand.md` (with default theme fallback), base64 logo embedding, inline data, zero external requests → `outputs/{ENTITY}-Dashboard_{PERIOD}.html` — blocked by 11
- [ ] 13. `skills/dashboard/SKILL.md` — invocation/scoping, missing-config refusal, and the closing deployment-tier recommendation dialogue (asks about tools/permissions) — blocked by 12
  - *Acceptance:* renders offline with zero network requests (verify in devtools), applies Example Hotels brand tokens, prints cleanly, drill-down present for flagged categories only

## Phase 4 — Setup skill

- [ ] 14. `skills/setup/SKILL.md` — the full A–I interview (PLAN §5.1), one topic at a time, re-runnable with section-level updates, including the required Phase D validation dry-run playback and the Phase I wrap-up smoke test — blocked by 10, 13
- [ ] 15. `skills/setup/templates/` — a template per config file the interview fills in — blocked by 14
- [ ] 16. Dry-run test: run `/setup` as a new company against a *modified* copy of the demo samples (different delimiter + sign convention); the resulting config must let `/analysis` run correctly with zero script changes — blocked by 15

## Phase 5 — Docs, demo outputs, polish

- [ ] 17. Pre-generate and commit all Example Hotels outputs (per-entity analysis HTML + dashboards, all 3 months); capture README screenshots — blocked by 13
- [ ] 18. `docs/DATA_REQUIREMENTS.md` — required exports, generic ERP guidance, the conventions `/setup` asks about — blocked by 5
- [ ] 19. `docs/HANDBOOK.md` — the monthly loop for the controller persona, file-naming reference, troubleshooting table of common validation failures — blocked by 13
- [ ] 20. `docs/DEPLOYMENT.md` — the three tiers (file-based; Google Apps Script web app with `Code.gs` walkthrough + sandbox caveat; static hosting with the never-publish-real-financials warning) — blocked by 13
- [ ] 21. `docs/LESSONS_LEARNED.md` — genericized case studies: GAS iframe sandbox blocking write-backs, self-contained HTML over a served app, deterministic flagging separated from LLM narrative — blocked by 20
- [ ] 22. `ROADMAP.md` — PLAN §10 items, explicitly marked out of scope for v1
- [ ] 23. `README.md` — pitch → screenshots → live demo link → problem → how it works → demo quickstart → own-company quickstart → architecture → deployment summary → roadmap → license. Budget real effort; this is the portfolio's front door — blocked by 17, 19, 20, 21, 22
- [ ] 24. CI (GitHub Actions): run tests + regenerate the demo analysis on push; deploy one demo dashboard to GitHub Pages — blocked by 17
- [ ] 25. Final review — fresh-clone test (README quickstart → rendered dashboard using only committed files), CI green, and PLAN's publish checklist: grep for real company names/brands/property codes/benchmarks (zero hits), all demo numbers synthetic, no company specifics outside `config/` and `examples/`, dashboards verified offline, screenshots current — blocked by 23, 24

---

## Notes for picking this up in a new session

- `PLAN.md` is the contract. Anything marked **DECISION** there must not be deviated from without asking first.
- Two non-negotiables to re-read before every task: engine vs. config separation (nothing company-specific in `skills/` or `scripts/` — it belongs in `config/`) and Python computes / Claude interprets (all numbers deterministic and testable; Claude only narrates).
- Clean-room rule: no real company names, benchmarks, account codes, thresholds, or property codes from any prior employer, anywhere. Task 25 greps for this, but it's cheaper to never write it.
- Everything in PLAN §10 (ROADMAP) is out of scope for v1 — including partially. Resist YTD views, consolidation, and multi-currency roll-ups even when the data makes them look easy.
- Demo entity codes are plain numerics (`001`–`004`); currency follows the entity's country via the demo config's country → currency map, not a hardcoded table.
