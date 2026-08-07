# Brand — Example Hotels

*Captured by `/setup` Phase H. Design tokens consumed by
`skills/dashboard/scripts/render_dashboard.py` when building each
entity's dashboard. No logo image supplied — a text wordmark is used
instead of a base64-embedded image (see "Logo treatment" below).*

## Machine-readable tokens

The tables and prose below are for a human reading this file (during
`/setup`, or reviewing what got captured). `render_dashboard.py` reads
*only* the fenced block below — keep it in sync with the tables if you
edit either by hand. `logo.file` is a path relative to this config
directory (e.g. `../../references/brand/logo.png`); `null` means no
logo was supplied, so the renderer falls back to `logo.wordmark`.

```yaml
colors:
  primary: "#1B3A4B"
  secondary: "#C9A05C"
  neutral_dark: "#20242A"
  neutral_light: "#F4F1EC"
  surface: "#FFFFFF"
  border: "#DDD8CE"
status_colors:
  ON TARGET: { hex: "#2E7D4F", icon: "✓" }
  NOTE: { hex: "#B8860B", icon: "●" }
  INVESTIGATE: { hex: "#B23A3A", icon: "▲" }
typography:
  font_family: "Inter"
  fallback_stack: 'Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif'
logo:
  file: null
  wordmark: "EXAMPLE HOTELS"
```

## Colors

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#1B3A4B` | header background, primary headings, KPI card accents |
| `secondary` | `#C9A05C` | highlights, focus-metric accent, section dividers |
| `neutral-dark` | `#20242A` | body text |
| `neutral-light` | `#F4F1EC` | page background, table zebra striping |
| `surface` | `#FFFFFF` | card / table background |
| `border` | `#DDD8CE` | table and card borders |

## Status colors

Paired with an icon/label, never color alone (color-blind accessibility
requirement, `PLAN.md` §7.2):

| Status | Hex | Icon/label |
|---|---|---|
| ON TARGET | `#2E7D4F` | ✓ "On target" |
| NOTE | `#B8860B` | ● "Note" |
| INVESTIGATE | `#B23A3A` | ▲ "Investigate" |

## Typography

- **Font:** Inter
- **Fallback stack:** `Inter, "Segoe UI", "Helvetica Neue", Arial, sans-serif`
- **Headings:** 600 weight, `primary` color
- **Body:** 400 weight, `neutral-dark` color
- **Tabular figures** (`font-variant-numeric: tabular-nums`) for every
  number in the P&L table and KPI cards, so columns of figures align.

## Logo treatment

No logo file was supplied. Use a text wordmark: **"EXAMPLE HOTELS"** in
small caps, `secondary` color, `primary` background, in the dashboard
header next to the entity name and period.

## Overall feel

Minimal, formal, confidence-through-restraint. Generous white space, no
gradients or drop shadows, thin 1px borders (`border` token) rather than
heavy card outlines. This is a management report read by a GM and a CFO,
not a marketing page — the design should get out of the way of the
numbers and the narrative.
