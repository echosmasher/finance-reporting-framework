# Company Profile — Example Hotels

*Captured by `/setup` Phases A and B. Written in the second person ("your")
because this is what the interview produces — narrated back to the user.*

## Company & entities

Example Hotels is a 4-property Nordic hospitality group, reporting each
property as its own entity/dashboard (no cross-entity consolidation — see
`entities.csv` and PLAN.md §10 roadmap).

| Code | Name | Country | Currency | Brand | Size |
|------|------|---------|----------|-------|------|
| 001 | Example Hotel Oslo | Norway | NOK | Signature | Large |
| 002 | Example Hotel Bergen | Norway | NOK | Signature | Medium |
| 003 | Example Hotel Stockholm | Sweden | SEK | Compact | Small |
| 004 | Example Hotel Copenhagen | Denmark | DKK | Signature | Medium |

**Brands:** "Signature" is the group's full-service brand (all departments —
Rooms, F&B, Spa & Wellness). "Compact" is the limited-service brand (Rooms
plus a minimal F&B offering — no Spa & Wellness department).

## Industry & seasonality

Industry: hospitality / hotel operations. The P&L structure follows a
simplified USALI-style departmental cascade (see `pnl-structure.yaml`).

Seasonality and regulatory factors the analysis should already expect,
not flag as anomalies:
- **Norwegian holiday pay ("feriepenger")**: a statutory lump-sum holiday
  pay accrual/payout concentrated in June, distinct from ordinary monthly
  payroll. Applies to entities 001 and 002.
- **Summer leisure peak** (June–August) at Bergen (002): coastal leisure
  and cruise-ship day traffic drive Rooms and F&B revenue well above the
  rest of the year.
- **Conference/MICE seasonality** at Copenhagen (004): demand concentrates
  midweek and in spring/autumn conference seasons; weaker weekends and a
  quieter August (European conference calendar lull).
- **Annual insurance and audit fees**: Property & Liability Insurance and
  external audit fees (booked to Administrative & General) are typically
  invoiced as a single annual charge in January, producing an expected
  spike in that category in period 1 of the fiscal year.

## Audience & reporting focus

- **Primary audience:** the General Manager of each property (financially
  literate but not a trained accountant — avoid unexplained accounting
  jargon; explain any subtotal that isn't self-evident) and the Group CFO
  (financially expert; can take a denser, faster-paced narrative).
- **Board audience:** a quarterly board summary rolls up the same
  per-entity dashboards; no separate board-only artifact in v1.
- **Focus metric:** **Gross Operating Profit (GOP)** — the group's
  standard measure of operating performance, above fixed charges like
  management fees and rent, which the GM does not control. EBITDA is
  shown as a secondary, informational figure.
- Personnel costs (payroll & related, across every department) are a
  standing area of interest — labor is the group's largest controllable
  cost category.

## Tone

Direct, professional, and specific — this audience reads reports monthly
and does not need scene-setting. Lead with what went well before raising
concerns. Frame deviations as investigation prompts ("check X, then Y"),
never as accusations or verdicts. No exclamation points, no filler
enthusiasm ("great job!"); confidence should come from being specific and
correct, not from tone.

## Languages

English only. All four properties report to a Nordic HQ where English is
the working language for management reporting.
