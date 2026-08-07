# Brand — [COMPANY NAME]

*Captured by `/setup` Phase H. Design tokens consumed by
`skills/dashboard/scripts/render_dashboard.py`. If nothing was provided,
apply a tasteful default theme and say so plainly in the prose below —
don't present a guessed theme as if the user gave it to you.*

## Machine-readable tokens

The tables/prose below are for a human reading this file.
`render_dashboard.py` reads *only* the fenced block below — keep it in
sync with the tables if you edit either by hand. `logo.file` is a path
relative to this config directory; `null` means no logo, so the
renderer falls back to `logo.wordmark`.

```yaml
colors:
  primary: "#000000"
  secondary: "#000000"
  neutral_dark: "#000000"
  neutral_light: "#FFFFFF"
  surface: "#FFFFFF"
  border: "#DDDDDD"
status_colors:
  ON TARGET: { hex: "#2E7D4F", icon: "✓" }
  NOTE: { hex: "#B8860B", icon: "●" }
  INVESTIGATE: { hex: "#B23A3A", icon: "▲" }
typography:
  font_family: "Replace Me"
  fallback_stack: 'Replace Me, "Segoe UI", Helvetica, Arial, sans-serif'
logo:
  file: null
  wordmark: "REPLACE ME"
```

## Colors

| Token | Hex | Usage |
|---|---|---|
| `primary` | | header background, primary headings |
| `secondary` | | highlights, focus-metric accent |
| `neutral-dark` | | body text |
| `neutral-light` | | page background |
| `surface` | | card / table background |
| `border` | | table and card borders |

## Status colors

Paired with an icon/label, never color alone (color-blind accessibility
requirement) — the defaults above are a reasonable, tested-for-contrast
starting point; only change them with a specific reason.

## Typography

- **Font:** [name]
- **Fallback stack:** [web-safe fallback chain]

## Logo treatment

[Describe what was provided, or state plainly that nothing was and a
text wordmark is used instead.]

## Overall feel

[Minimal/rich, formal/friendly — a sentence or two guiding the overall
visual character.]
