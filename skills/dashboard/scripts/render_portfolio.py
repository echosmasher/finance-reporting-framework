#!/usr/bin/env python3
"""Render outputs/Portfolio-Overview_{PERIOD}.html (docs/IMPROVEMENT_IDEAS.md
idea 2, tasks.md task 28): a side-by-side card per entity — KPIs, the focus
metric vs Budget, and flag counts — each linking into that entity's own
`/dashboard` output. Deliberately NOT consolidation: nothing here sums or
converts across entities/currencies, it's a same-page view of independently
computed per-entity numbers, same inputs `render_dashboard.py` already
renders per entity (analysis_{ENTITY}_{PERIOD}.json), never a second source
of them.

Reuses render_dashboard.py's brand loading, color tokens, and bar-drawing
helper rather than duplicating them — see _rounded_top_rect / tint / STATUS_CLASS.
Single file, inline CSS, inline data, zero external requests, logo embedded
as base64 if one is configured — never add a <link>/<script src>/external URL
here.
"""
import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_dashboard import (  # noqa: E402
    STATUS_CLASS, _rounded_top_rect, get_brand, render_logo_html, tint,
)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "portfolio_base.html"


def fmt_kpi_value(value: float, fmt: str, currency: str) -> str:
    if fmt == "percent":
        return f"{value * 100:.1f}%"
    return f"{value:,.0f} {currency}"


def render_focus_metric_bars_svg(label: str, budget: float, actual: float, favorable: bool,
                                  currency: str, colors: dict, status_colors: dict) -> str:
    """A compact Budget-vs-Actual comparison, not a bridge: with only two
    bars there's no small-delta-against-a-large-total problem task 27's
    waterfall had, so this stays honest with an ordinary zero baseline."""
    total_color = colors["primary"]
    delta_color = status_colors["ON TARGET"]["hex"] if favorable else status_colors["INVESTIGATE"]["hex"]
    text_color = colors["neutral_dark"]
    grid_color = colors["border"]

    width, height = 260, 130
    margin_left, margin_right, margin_top, margin_bottom = 10, 10, 24, 28
    chart_top, chart_bottom = margin_top, height - margin_bottom
    chart_left, chart_right = margin_left, width - margin_right

    max_val = max(budget, actual, 1.0)

    def y_px(v):
        return chart_bottom - (v / max_val) * (chart_bottom - chart_top)

    slot = (chart_right - chart_left) / 2
    bar_w = min(46.0, slot * 0.5)

    bars, labels = [], []
    for i, (bar_label, value, color) in enumerate(
        [("Budget", budget, total_color), ("Actual", actual, delta_color)]
    ):
        cx = chart_left + slot * i + slot / 2
        top_y = y_px(value)
        h = chart_bottom - top_y
        title = f"{bar_label}: {value:,.0f} {currency}"
        bars.append(_rounded_top_rect(cx - bar_w / 2, top_y, bar_w, h, color, title=title))
        labels.append(f'<text x="{cx:.1f}" y="{top_y - 7:.1f}" text-anchor="middle" font-size="11" '
                       f'font-weight="700" fill="{text_color}">{value:,.0f}</text>')
        labels.append(f'<text x="{cx:.1f}" y="{chart_bottom + 15:.1f}" text-anchor="middle" font-size="10" '
                       f'fill="{text_color}" fill-opacity="0.7">{bar_label}</text>')

    axis = (f'<line x1="{chart_left:.1f}" y1="{chart_bottom:.1f}" x2="{chart_right:.1f}" y2="{chart_bottom:.1f}" '
            f'stroke="{grid_color}" stroke-width="1.5"/>')

    return (f'<svg viewBox="0 0 {width} {height}" role="img" '
            f'aria-label="{html.escape(label)}: Budget vs Actual">{axis}{"".join(bars)}{"".join(labels)}</svg>')


def render_flag_summary(flags: list, status_colors: dict) -> str:
    counts = {"INVESTIGATE": 0, "NOTE": 0}
    for f in flags:
        if f["status"] in counts:
            counts[f["status"]] += 1
    if not counts["INVESTIGATE"] and not counts["NOTE"]:
        icon = status_colors["ON TARGET"]["icon"]
        return f'<span class="status-pill status-on-target">{icon} On target</span>'
    pills = []
    for status in ("INVESTIGATE", "NOTE"):
        if counts[status]:
            icon = status_colors[status]["icon"]
            noun = status.title()
            plural = "s" if counts[status] != 1 else ""
            pills.append(f'<span class="status-pill {STATUS_CLASS[status]}">{icon} {counts[status]} {noun}{plural}</span>')
    return "".join(pills)


def render_entity_card(analysis: dict, period: str, colors: dict, status_colors: dict) -> str:
    focus_id = analysis["focus_metric"]
    focus_entry = next((e for e in analysis["pnl"] if e["id"] == focus_id), None)
    chart_html = ""
    delta_pill = ""
    if focus_entry:
        chart_html = render_focus_metric_bars_svg(
            focus_entry["label"], focus_entry["budget"], focus_entry["act"], focus_entry["favorable"],
            analysis["currency"], colors, status_colors,
        )
        sign = "+" if focus_entry["diff_pct"] >= 0 else ""
        status_class = STATUS_CLASS[focus_entry["status"]]
        delta_pill = (f'<div style="text-align:center;margin-top:0.35rem">'
                      f'<span class="status-pill {status_class}">{sign}{focus_entry["diff_pct"]:.1f}% vs Budget</span></div>')

    kpi_rows = "".join(
        f'<div class="kpi-mini-row"><span class="kpi-label">{html.escape(k["label"])}</span>'
        f'<span class="kpi-value">{fmt_kpi_value(k["act"], k["format"], analysis["currency"])}</span></div>'
        for k in analysis["kpis"]
    )

    return f"""
    <div class="portfolio-card">
      <div class="card-header">
        <h2>{html.escape(analysis['entity_name'])} <span class="entity-code">{html.escape(analysis['entity_code'])}</span></h2>
      </div>
      <div class="flag-summary">{render_flag_summary(analysis['flags'], status_colors)}</div>
      <div class="mini-chart">
        <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.04em;opacity:0.6">
          {html.escape(focus_entry['label']) if focus_entry else 'Focus metric'} vs Budget
        </div>
        {chart_html}
        {delta_pill}
      </div>
      <div class="kpi-mini-list">{kpi_rows}</div>
      <a class="card-link" href="{html.escape(analysis['entity_code'])}-Dashboard_{html.escape(period)}.html">View full dashboard &rarr;</a>
    </div>"""


def render_portfolio_html(analyses: list, brand: dict, config_dir: Path, period: str) -> str:
    colors = brand["colors"]
    status_colors = brand["status_colors"]
    surface = colors["surface"]
    comparison_label = analyses[0]["comparison_label"] if analyses else "Budget"

    tokens = {
        "PERIOD": html.escape(period),
        "COMPARISON_LABEL": html.escape(comparison_label),
        "LOGO_HTML": render_logo_html(brand, config_dir),
        "PORTFOLIO_CARDS_HTML": "".join(render_entity_card(a, period, colors, status_colors) for a in analyses),
        "PRIMARY_COLOR": colors["primary"],
        "SECONDARY_COLOR": colors["secondary"],
        "NEUTRAL_DARK": colors["neutral_dark"],
        "NEUTRAL_LIGHT": colors["neutral_light"],
        "SURFACE": surface,
        "BORDER": colors["border"],
        "FONT_FAMILY_STACK": brand["typography"]["fallback_stack"],
        "STATUS_ON_TARGET_COLOR": status_colors["ON TARGET"]["hex"],
        "STATUS_ON_TARGET_BG": tint(status_colors["ON TARGET"]["hex"], surface),
        "STATUS_NOTE_COLOR": status_colors["NOTE"]["hex"],
        "STATUS_NOTE_BG": tint(status_colors["NOTE"]["hex"], surface),
        "STATUS_INVESTIGATE_COLOR": status_colors["INVESTIGATE"]["hex"],
        "STATUS_INVESTIGATE_BG": tint(status_colors["INVESTIGATE"]["hex"], surface),
    }

    html_out = TEMPLATE_PATH.read_text()
    for token, value in tokens.items():
        html_out = html_out.replace("{{" + token + "}}", value)
    return html_out


def render_portfolio_report(period: str, config_dir: Path, outputs_dir: Path, entity_codes: list = None) -> Path:
    if entity_codes:
        analysis_paths = [outputs_dir / f"analysis_{code}_{period}.json" for code in entity_codes]
    else:
        analysis_paths = sorted(outputs_dir.glob(f"analysis_*_{period}.json"))
    analyses = []
    for path in analysis_paths:
        if not path.exists():
            print(f"SKIPPED: {path} not found — run /analysis first", file=sys.stderr)
            continue
        with open(path) as f:
            analyses.append(json.load(f))
    analyses.sort(key=lambda a: a["entity_code"])

    brand = get_brand(config_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = outputs_dir / f"Portfolio-Overview_{period}.html"
    with open(out_path, "w") as f:
        f.write(render_portfolio_html(analyses, brand, config_dir, period))
    return out_path, len(analyses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all analysis_*.json found)")
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--outputs-dir", default="outputs", type=Path)
    args = parser.parse_args()

    entity_codes = args.entities.split(",") if args.entities else None
    out_path, count = render_portfolio_report(args.period, args.config_dir, args.outputs_dir, entity_codes)
    if count == 0:
        print(f"SKIPPED: no analysis JSON found for {args.period} — run /analysis first", file=sys.stderr)
        sys.exit(1)
    print(f"wrote {out_path} ({count} entity(ies))")


if __name__ == "__main__":
    main()
