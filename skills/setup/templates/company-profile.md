# Company Profile — [COMPANY NAME]

*Captured by `/setup` Phases A and B. Written in the second person
("your") — this is narrated back to the user, not read by them raw.*

## Company & entities

[How many entities/properties/locations, each becoming its own
dashboard? One sentence per entity or a short table — see
`entities.csv` for the structured version. Note any brand/segment
distinctions that change how entities are treated (e.g. one brand has a
department another doesn't — model that in `pnl-structure.yaml` via
`applies_to_brands`, not here).]

| Code | Name | Country | Currency | [other categorization columns] |
|------|------|---------|----------|---------------------------------|

## Industry & seasonality

Industry: [industry name].

[List known seasonality and recurring anomalies the analysis should
already expect, not flag as anomalous: recurring payroll events,
seasonal revenue swings per entity, annual fixed-charge invoicing
patterns, regulatory costs, typical margin structure. Each item here
should also get a matching entry in `thresholds.yaml`'s
`seasonality_notes` — this section is the narrative version, that one
is the structured version the engine reads.]

## Audience & reporting focus

- **Primary audience:** [who reads the dashboard — role, financial
  competence, jargon tolerance.]
- **Focus metric:** [which P&L subtotal this audience cares about most
  — must match `pnl-structure.yaml` → `terminology.focus_metric`.]
- [Any standing areas of interest beyond the focus metric — e.g. a
  particular cost category the audience always wants explained.]

## Tone

[Direct guidance for the narrative pass: formality level, sentence
length, whether exclamation points/enthusiasm markers are wanted,
how to frame concerns (PLAN.md's default: investigation prompts, never
accusations; lead with wins).]

## Languages

[Report language(s). If different audiences need different languages,
say which audience gets which.]
