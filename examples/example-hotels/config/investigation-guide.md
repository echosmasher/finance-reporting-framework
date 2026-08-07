# Investigation Guide — Example Hotels

*Captured by `/setup` Phase F. This is the controller's tacit knowledge,
written as short imperative checklists. `/analysis` attaches the relevant
checklist to every flagged category's narrative so the reader gets an
investigation prompt, not just a number.*

## Utilities

**When unexpectedly HIGH:**
1. Check for a missing or estimated invoice in the prior period that
   reversed/caught up this period (energy invoices routinely arrive a
   month behind meter reads).
2. Compare degree-days / outside temperature to Budget assumptions —
   a cold snap moves district heating cost independent of occupancy.
3. Check occupancy vs Budget — utilities has a variable component tied to
   rooms sold, not just a fixed base load.
4. Check for one-off maintenance events (boiler repair, generator testing)
   that were booked to Utilities instead of Property Operations &
   Maintenance.

**When unexpectedly LOW:**
1. Confirm the period's invoice was actually received and posted — a
   low Utilities number is often a missing invoice, not genuine savings.
2. Check for an unusually warm/mild period reducing heating load.

## F&B – Cost of Sales

**When unexpectedly HIGH:**
1. Pull the transaction drill-down for large or unusual vendor postings —
   a manual inventory adjustment can land the whole month's variance in
   one entry.
2. Check the F&B revenue mix — a swing toward banquet/group business
   typically carries a different (often higher) cost ratio than à la
   carte.
3. Confirm no obsolete/wasted inventory write-off was booked this period.
4. Check for a supplier price increase not yet reflected in the Budget.

**When unexpectedly LOW:**
1. Confirm month-end inventory count was actually performed and posted —
   a skipped count understates cost of sales until the next count
   corrects it.
2. Check whether a planned banquet/event shifted into an adjacent period.

**Benchmark:** F&B Cost of Sales as % of F&B Revenue should run
**28–33%** for Signature-brand (full-service) properties, and
**30–36%** for the Compact brand (smaller-scale purchasing, simpler menu
so less room to average down high-cost items).

## Rooms – Payroll & Related

**When unexpectedly HIGH:**
1. Compare to occupancy vs Budget first — payroll should track
   occupancy, not the calendar; check whether staffing wasn't scaled
   down for a soft period.
2. Check for overtime postings — a staffing gap (leave, vacancy) covered
   by overtime is more expensive than the vacant role's budgeted cost.
3. Check headcount vs the budgeted FTE count for the department.

**When unexpectedly LOW:**
1. Check for open vacancies — savings from an unfilled role are real but
   usually come with a service-level cost worth flagging to the GM
   separately.
2. Confirm occupancy wasn't unexpectedly high without matching payroll —
   a service-quality risk, not just a favorable variance.

**Benchmark:** Rooms Payroll & Related should move roughly in line with
Occupancy % — a payroll variance materially larger or smaller than the
occupancy variance in the same period is the signal worth chasing, not
the payroll number in isolation.

## F&B – Payroll & Related

**When unexpectedly HIGH:**
1. Check for banquet/group events requiring temporary or agency staff —
   temp labor costs more per hour than core staff.
2. Check for overtime driven by a short-staffed shift.

**When unexpectedly LOW:**
1. Check whether a scheduled banquet/event was cancelled or postponed —
   confirm against the same period's F&B revenue.

## Property Operations & Maintenance

**When unexpectedly HIGH:**
1. Pull the transaction drill-down — this category is lumpy by nature;
   one large repair (roof, elevator, HVAC) can be the entire variance.
2. Check whether the spend was capital in nature and should have been
   capitalized rather than expensed.

**When unexpectedly LOW:**
1. Check whether planned preventive maintenance was deferred — a
   favorable variance here can become a larger repair cost later; flag
   for the GM's awareness even when it's "good news" on the P&L.

## Administrative & General

**When unexpectedly HIGH:**
1. Check for the annual insurance/audit fee timing (see
   `company-profile.md` seasonality notes) — expected in January, not
   an anomaly if that's the period.
2. Pull the transaction drill-down for one-off professional fees (legal,
   consulting) not in the Budget.
3. Check for bad debt write-offs.

**When unexpectedly LOW:**
1. Confirm no invoice is simply late/unposted rather than genuinely
   absent.
