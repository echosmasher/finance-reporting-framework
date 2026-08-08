#!/usr/bin/env python3
"""Render outputs/{ENTITY}-Dashboard_{PERIOD}.html (PLAN.md §7): a
polished, audience-facing, brand-styled, fully self-contained dashboard
built from analyze.py's JSON + the Claude narrative pass's JSON (same
inputs as render_analysis.py — this is a different presentation of the
same numbers, not a second source of them).

Brand tokens come from config/brand.md's fenced ```yaml block (see
config_loader.load_brand); a company with no brand.md tokens still gets
a complete dashboard via DEFAULT_BRAND. Single file, inline CSS, inline
data, zero external requests, logo embedded as base64 if one is
configured — never add a <link>/<script src>/external URL here.
"""
import argparse
import base64
import html
import json
import math
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "analysis" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "feedback" / "scripts"))
from config_loader import ConfigError, load_brand  # noqa: E402
from feedback_store import apply_overrides_to_narrative, comments_by_row, load_feedback, stale_overrides  # noqa: E402

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "dashboard_base.html"

DEFAULT_BRAND = {
    "colors": {
        "primary": "#1B3A4B", "secondary": "#C9A05C", "neutral_dark": "#20242A",
        "neutral_light": "#F4F1EC", "surface": "#FFFFFF", "border": "#DDD8CE",
    },
    "status_colors": {
        "ON TARGET": {"hex": "#2E7D4F", "icon": "✓"},
        "NOTE": {"hex": "#B8860B", "icon": "●"},
        "INVESTIGATE": {"hex": "#B23A3A", "icon": "▲"},
    },
    "typography": {"font_family": "system-ui", "fallback_stack": "system-ui, -apple-system, Helvetica, Arial, sans-serif"},
    "logo": {"file": None, "wordmark": None},
}

STATUS_CLASS = {"ON TARGET": "status-on-target", "NOTE": "status-note", "INVESTIGATE": "status-investigate"}


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def tint(hex_color: str, surface_hex: str, opacity: float = 0.14) -> str:
    """Blends hex_color into surface_hex at a fixed opacity, precomputed
    in Python rather than via CSS color-mix() — color-mix() is recent
    enough that some print/PDF engines and older browsers may not
    support it, and these dashboards need to "just work" wherever
    they're opened (PLAN.md §7.2, §7.4 tier 1)."""
    r1, g1, b1 = hex_to_rgb(hex_color)
    r2, g2, b2 = hex_to_rgb(surface_hex)
    r = round(r1 * opacity + r2 * (1 - opacity))
    g = round(g1 * opacity + g2 * (1 - opacity))
    b = round(b1 * opacity + b2 * (1 - opacity))
    return f"rgb({r},{g},{b})"


def get_brand(config_dir: Path) -> dict:
    try:
        return load_brand(config_dir)
    except (ConfigError, FileNotFoundError):
        return DEFAULT_BRAND


def render_logo_html(brand: dict, config_dir: Path) -> str:
    logo = brand.get("logo") or {}
    file_path = logo.get("file")
    if file_path:
        path = config_dir / file_path
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode()
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        return f'<img src="data:{mime};base64,{b64}" alt="logo" style="height:28px;display:block;margin-bottom:0.3rem">'
    wordmark = logo.get("wordmark")
    if wordmark:
        return f'<div class="wordmark">{html.escape(wordmark)}</div>'
    return ""


def fmt_amount(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def fmt_kpi_value(value: float, fmt: str, currency: str) -> str:
    if fmt == "percent":
        return f"{value * 100:.1f}%"
    return f"{value:,.0f} {currency}"


def compute_gop_bridge(analysis: dict) -> dict:
    """Builds a Budget -> Actual bridge for the focus metric (config's
    terminology.focus_metric, e.g. GOP) purely by recombining fields
    analyze.py already computed on every pnl entry (diff, favorable) — no
    new thresholds or business logic, just arithmetic. Generic across any
    company config: 'contributing categories' are simply every kind=='category'
    row that precedes the focus metric's row in pnl-structure.yaml's
    presentation_order, which by construction (see tasks.md task 6 notes)
    always places a subtotal's inputs ahead of it. Because every subtotal in
    this framework's formula language is a sum/difference of its inputs (see
    eval_formula's DSL), the per-category contributions below always sum
    exactly to the focus metric's own actual-vs-budget diff.

    Categories already flagged (status != ON TARGET) become their own bar;
    everything else is netted into one 'Other categories' bar so the bridge
    reconciles to the cent, not just thematically.
    """
    pnl = analysis["pnl"]
    focus_idx = next((i for i, e in enumerate(pnl) if e["id"] == analysis["focus_metric"]), None)
    if focus_idx is None:
        return None
    focus_entry = pnl[focus_idx]
    contributing = [e for e in pnl[:focus_idx] if e["kind"] == "category"]

    def contribution(entry):
        diff = entry["diff"]
        if diff == 0:
            return 0.0
        return diff if (diff > 0) == entry["favorable"] else -diff

    bars = [
        {"label": e["label"], "delta": contribution(e), "favorable": e["favorable"]}
        for e in contributing
        if e["status"] != "ON TARGET"
    ]
    unflagged = [e for e in contributing if e["status"] == "ON TARGET"]
    other_total = sum(contribution(e) for e in unflagged)
    if unflagged and abs(other_total) > 0.005:
        bars.append({
            "label": f"Other categories ({len(unflagged)})",
            "delta": other_total,
            "favorable": other_total >= 0,
        })

    return {
        "focus_label": focus_entry["label"],
        "budget": focus_entry["budget"],
        "actual": focus_entry["act"],
        "bars": bars,
    }


def _nice_ticks(lo: float, hi: float, count: int = 4) -> list:
    if hi <= lo:
        return [lo]
    raw_step = (hi - lo) / count
    magnitude = 10 ** math.floor(math.log10(raw_step)) if raw_step > 0 else 1
    residual = raw_step / magnitude
    step = 10 * magnitude if residual > 5 else 5 * magnitude if residual > 2 else 2 * magnitude if residual > 1 else magnitude
    ticks = []
    v = math.floor(lo / step) * step
    while v <= hi + step * 0.001:
        if v >= lo - step * 0.001:
            ticks.append(v)
        v += step
    return ticks


def _rounded_top_rect(x: float, y: float, w: float, h: float, fill: str, radius: float = 4.0, title: str = "") -> str:
    """A bar with rounded top corners, square base — the dataviz mark spec
    (4px rounded data-end, square at the baseline) applied uniformly to every
    bar in the bridge, including floating delta segments, so the visual
    language stays consistent across bar types."""
    if h <= 0:
        return ""
    r = min(radius, h / 2, w / 2)
    title_el = f"<title>{html.escape(title)}</title>" if title else ""
    if r <= 0.5:
        return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}">{title_el}</rect>'
    d = (
        f"M{x:.1f},{y + h:.1f} L{x:.1f},{y + r:.1f} "
        f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"L{x + w - r:.1f},{y:.1f} Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f} "
        f"L{x + w:.1f},{y + h:.1f} Z"
    )
    return f'<path d="{d}" fill="{fill}">{title_el}</path>'


def render_waterfall_svg(bridge: dict, currency: str, colors: dict, status_colors: dict) -> str:
    """Inline SVG only (PLAN §7.2 zero-external-requests, no chart library),
    dataviz-skill mark specs: <=24px bars, rounded data-ends, hairline
    recessive gridlines, direct value labels at the tip, a legend (status
    colors are never color-alone). Colors reuse the same brand/status tokens
    every other status-pill on this dashboard already uses, so 'favorable'
    means the same green everywhere in the document."""
    total_color = colors["primary"]
    favorable_color = status_colors["ON TARGET"]["hex"]
    unfavorable_color = status_colors["INVESTIGATE"]["hex"]
    text_color = colors["neutral_dark"]
    grid_color = colors["border"]

    focus_label = bridge["focus_label"]
    sequence = [{"type": "start", "label": "Budget", "value": bridge["budget"]}]
    running = bridge["budget"]
    for bar in bridge["bars"]:
        base = running
        running += bar["delta"]
        sequence.append({
            "type": "delta", "label": bar["label"], "delta": bar["delta"],
            "favorable": bar["favorable"], "base": min(base, running), "top": max(base, running),
        })
    sequence.append({"type": "end", "label": "Actual", "value": bridge["actual"]})

    # Domain deliberately does NOT include 0: a bridge chart's story is the
    # size of each step, and those steps are typically a small fraction of
    # the total (a real GOP swing of a few percent). Forcing a zero baseline
    # (mandatory for an ordinary bar chart) would render every delta as an
    # invisible sliver against the full total bars. A floating y-axis, with
    # every bar segment — including the Budget/Actual totals — drawn against
    # the same non-zero floor, is the standard convention for this chart
    # type; the axis ticks still show the true absolute scale, so nothing is
    # hidden, only zoomed.
    domain_values = []
    for item in sequence:
        if item["type"] == "delta":
            domain_values.append(item["base"])
            domain_values.append(item["top"])
        else:
            domain_values.append(item["value"])
    data_min, data_max = min(domain_values), max(domain_values)
    pad = (data_max - data_min) * 0.3 if data_max > data_min else max(abs(data_max) * 0.1, 1.0)
    y_min, y_max = data_min - pad, data_max + pad

    width, height = 900, 340
    margin_left, margin_right, margin_top, margin_bottom = 90, 20, 30, 100
    chart_top, chart_bottom = margin_top, height - margin_bottom
    chart_left, chart_right = margin_left, width - margin_right

    def y_px(value):
        if y_max == y_min:
            return chart_bottom
        return chart_bottom - (value - y_min) / (y_max - y_min) * (chart_bottom - chart_top)

    n = len(sequence)
    slot = (chart_right - chart_left) / n
    bar_w = min(24.0, slot * 0.6)

    grid_svg = []
    for tick in _nice_ticks(y_min, data_max, count=4):
        ty = y_px(tick)
        grid_svg.append(f'<line x1="{chart_left:.1f}" y1="{ty:.1f}" x2="{chart_right:.1f}" y2="{ty:.1f}" '
                         f'stroke="{grid_color}" stroke-width="1"/>')
        grid_svg.append(f'<text x="{chart_left - 8:.1f}" y="{ty + 3:.1f}" text-anchor="end" font-size="10" '
                         f'fill="{text_color}" fill-opacity="0.65">{tick:,.0f}</text>')

    bars_svg = []
    labels_svg = []
    connectors_svg = []
    prev_top_x = None
    prev_top_y = None
    for i, item in enumerate(sequence):
        cx = chart_left + slot * i + slot / 2
        x = cx - bar_w / 2
        if item["type"] in ("start", "end"):
            top_y = y_px(item["value"])
            base_y = chart_bottom
            h = base_y - top_y
            title = f"{item['label']}: {item['value']:,.0f} {currency}"
            bars_svg.append(_rounded_top_rect(x, top_y, bar_w, h, total_color, title=title))
            labels_svg.append(f'<text x="{cx:.1f}" y="{top_y - 8:.1f}" text-anchor="middle" font-size="11" '
                               f'font-weight="700" fill="{text_color}">{item["value"]:,.0f}</text>')
            bar_top_x, bar_top_y = cx, top_y
        else:
            top_y = y_px(item["top"])
            base_y = y_px(item["base"])
            h = base_y - top_y
            color = favorable_color if item["favorable"] else unfavorable_color
            sign = "+" if item["delta"] >= 0 else "−"
            title = f"{item['label']}: {sign}{abs(item['delta']):,.0f} {currency}"
            bars_svg.append(_rounded_top_rect(x, top_y, bar_w, h, color, title=title))
            label_y = (top_y - 8) if item["delta"] >= 0 else (base_y + 16)
            labels_svg.append(f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="11" '
                               f'font-weight="700" fill="{text_color}">{sign}{abs(item["delta"]):,.0f}</text>')
            bar_top_x, bar_top_y = cx, top_y if item["delta"] >= 0 else base_y
        if prev_top_x is not None:
            connectors_svg.append(f'<line x1="{prev_top_x:.1f}" y1="{prev_top_y:.1f}" x2="{cx - bar_w / 2:.1f}" '
                                   f'y2="{prev_top_y:.1f}" stroke="{grid_color}" stroke-width="1" '
                                   f'stroke-dasharray="2,2"/>')
        prev_top_x, prev_top_y = bar_top_x, bar_top_y

        # category label, rotated to fit narrow bar slots
        label = item["label"]
        if len(label) > 26:
            label = label[:24] + "…"
        labels_svg.append(f'<text x="{cx:.1f}" y="{chart_bottom + 14:.1f}" text-anchor="end" font-size="10" '
                           f'fill="{text_color}" fill-opacity="0.75" transform="rotate(-40 {cx:.1f} '
                           f'{chart_bottom + 14:.1f})">{html.escape(label)}</text>')

    axis_line = (f'<line x1="{chart_left:.1f}" y1="{chart_bottom:.1f}" x2="{chart_right:.1f}" y2="{chart_bottom:.1f}" '
                 f'stroke="{grid_color}" stroke-width="1.5"/>')

    svg = f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(focus_label)} bridge from Budget to Actual"
         style="width:100%;height:auto;display:block;font-family:inherit">
      {''.join(grid_svg)}
      {axis_line}
      {''.join(connectors_svg)}
      {''.join(b for b in bars_svg if b)}
      {''.join(labels_svg)}
    </svg>"""

    legend = f"""
    <div class="bridge-legend">
      <span class="legend-item"><span class="swatch" style="background:{total_color}"></span>{html.escape(focus_label)} total</span>
      <span class="legend-item"><span class="swatch" style="background:{favorable_color}"></span>Increases {html.escape(focus_label)}</span>
      <span class="legend-item"><span class="swatch" style="background:{unfavorable_color}"></span>Decreases {html.escape(focus_label)}</span>
    </div>"""

    return f'<div class="bridge-chart">{legend}{svg}</div>'


def _period_sort_key(period: str):
    mm, yyyy = period.split("-")
    return (int(yyyy), int(mm))


def _entry_by_id(analysis: dict, entry_id: str):
    for e in analysis["pnl"]:
        if e["id"] == entry_id:
            return e
    for e in analysis["kpis"]:
        if e["id"] == entry_id:
            return e
    return None


def load_entity_trend(entity_code: str, outputs_dir: Path, current_period: str) -> dict:
    """Loads every committed analysis_{ENTITY}_*.json for one entity up to
    and including `current_period`, sorted in calendar order (MM-YYYY
    doesn't sort correctly as a plain string across a year boundary, e.g.
    '12-2025' vs '01-2026'). Shared by the GOP-by-month chart and
    flag-history grid below, and by task 30's KPI/row sparklines -- one
    loader, one read of the same already-computed per-period JSON, never a
    second source of the numbers.

    Deliberately excludes any period AFTER `current_period`, even if it's
    already committed (true of every period in the demo, since all 3
    months exist at once): a report for February must not show March's
    status as its 'current' trend point just because March happens to be
    sitting in outputs/ already -- a real company would never have that
    data yet when February's report is generated, and the dashboard for a
    given month should only ever reflect what was knowable as of that
    month. The forward-looking story ("the dip in Feb reversed in Mar") is
    still tellable -- it shows up when March's own dashboard is opened.

    Returns None if fewer than 2 qualifying periods exist: a trend needs at
    least two points, and a brand-new company simply won't have one yet --
    graceful degradation, not an error, matching this codebase's existing
    patterns for optional LY data / an optional stats file."""
    paths = list(outputs_dir.glob(f"analysis_{entity_code}_*.json"))
    analyses = []
    for path in paths:
        with open(path) as f:
            analyses.append(json.load(f))
    analyses.sort(key=lambda a: _period_sort_key(a["period"]))
    cutoff = _period_sort_key(current_period)
    analyses = [a for a in analyses if _period_sort_key(a["period"]) <= cutoff]
    if len(analyses) < 2:
        return None
    return {"periods": [a["period"] for a in analyses], "analyses": analyses}


def render_gop_by_month_svg(trend: dict, colors: dict, status_colors: dict) -> str:
    """One bar per period for the focus metric's Actual (colored by that
    period's favorable/unfavorable direction), with a tick marking that
    period's Budget -- an actual-vs-target convention, not a bridge, so
    (unlike render_waterfall_svg) this uses an honest zero baseline: it's
    a plain magnitude-over-time comparison, none of the small-delta-
    against-a-large-total problem the waterfall's floating axis exists
    to solve."""
    focus_id = trend["analyses"][0]["focus_metric"]
    currency = trend["analyses"][0]["currency"]
    points = []
    for a in trend["analyses"]:
        entry = _entry_by_id(a, focus_id)
        if entry is not None:
            points.append({"period": a["period"], "act": entry["act"], "budget": entry["budget"],
                            "favorable": entry["favorable"], "label": entry["label"]})
    if not points:
        return ""

    total_color = colors["primary"]
    favorable_color = status_colors["ON TARGET"]["hex"]
    unfavorable_color = status_colors["INVESTIGATE"]["hex"]
    text_color = colors["neutral_dark"]
    grid_color = colors["border"]

    width, height = 900, 220
    margin_left, margin_right, margin_top, margin_bottom = 90, 20, 30, 40
    chart_top, chart_bottom = margin_top, height - margin_bottom
    chart_left, chart_right = margin_left, width - margin_right

    max_val = max(max(p["act"], p["budget"]) for p in points) * 1.15 or 1.0

    def y_px(v):
        return chart_bottom - (v / max_val) * (chart_bottom - chart_top)

    n = len(points)
    slot = (chart_right - chart_left) / n
    bar_w = min(56.0, slot * 0.45)

    grid_svg = []
    for tick in _nice_ticks(0, max_val, count=4):
        ty = y_px(tick)
        grid_svg.append(f'<line x1="{chart_left:.1f}" y1="{ty:.1f}" x2="{chart_right:.1f}" y2="{ty:.1f}" '
                         f'stroke="{grid_color}" stroke-width="1"/>')
        grid_svg.append(f'<text x="{chart_left - 8:.1f}" y="{ty + 3:.1f}" text-anchor="end" font-size="10" '
                         f'fill="{text_color}" fill-opacity="0.65">{tick:,.0f}</text>')

    bars_svg, ticks_svg, labels_svg = [], [], []
    for i, p in enumerate(points):
        cx = chart_left + slot * i + slot / 2
        color = favorable_color if p["favorable"] else unfavorable_color
        top_y = y_px(p["act"])
        h = chart_bottom - top_y
        title = f"{p['period']}: {p['act']:,.0f} {currency} actual vs {p['budget']:,.0f} {currency} budget"
        bars_svg.append(_rounded_top_rect(cx - bar_w / 2, top_y, bar_w, h, color, title=title))
        budget_y = y_px(p["budget"])
        # Clear whichever sits higher on screen (smaller y-pixel) -- the bar
        # top or the budget tick -- so the value label never collides with
        # the tick when Actual and Budget are close together.
        label_y = min(top_y, budget_y) - 10
        labels_svg.append(f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" font-size="11" '
                           f'font-weight="700" fill="{text_color}">{p["act"]:,.0f}</text>')
        labels_svg.append(f'<text x="{cx:.1f}" y="{chart_bottom + 18:.1f}" text-anchor="middle" font-size="11" '
                           f'fill="{text_color}" fill-opacity="0.75">{html.escape(p["period"])}</text>')
        ticks_svg.append(f'<line x1="{cx - bar_w / 2 - 4:.1f}" y1="{budget_y:.1f}" x2="{cx + bar_w / 2 + 4:.1f}" '
                          f'y2="{budget_y:.1f}" stroke="{total_color}" stroke-width="2.5">'
                          f'<title>Budget: {p["budget"]:,.0f} {currency}</title></line>')

    axis_line = (f'<line x1="{chart_left:.1f}" y1="{chart_bottom:.1f}" x2="{chart_right:.1f}" y2="{chart_bottom:.1f}" '
                 f'stroke="{grid_color}" stroke-width="1.5"/>')

    svg = f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(points[0]['label'])} actual by month, vs Budget"
         style="width:100%;height:auto;display:block;font-family:inherit">
      {''.join(grid_svg)}
      {axis_line}
      {''.join(b for b in bars_svg if b)}
      {''.join(ticks_svg)}
      {''.join(labels_svg)}
    </svg>"""

    legend = f"""
    <div class="bridge-legend">
      <span class="legend-item"><span class="swatch" style="background:{favorable_color}"></span>Favorable month</span>
      <span class="legend-item"><span class="swatch" style="background:{unfavorable_color}"></span>Unfavorable month</span>
      <span class="legend-item"><span class="swatch" style="background:{total_color};height:3px;width:14px;border-radius:0"></span>Budget</span>
    </div>"""

    return f'<div class="bridge-chart">{legend}{svg}</div>'


def render_flag_history_grid(trend: dict, status_colors: dict) -> str:
    """A compact per-category table across every committed period for this
    entity -- which categories were flagged when, and in which direction.
    Restricted to kind=='category' leaf rows, not subtotals/KPIs, which are
    just downstream echoes of the same category-level story (see how
    render_deviation_highlights' narrative for EBITDA/EBIT/Pre-tax Income
    all say 'same driver as GOP above')."""
    first = trend["analyses"][0]
    order = [e["id"] for e in first["pnl"] if e["kind"] == "category"]
    ever_flagged = {f["id"] for a in trend["analyses"] for f in a["flags"] if f.get("kind") == "category"}
    ids = [cid for cid in order if cid in ever_flagged]
    if not ids:
        return "<p>No category was flagged in any committed period for this entity.</p>"

    labels = {e["id"]: e["label"] for e in first["pnl"]}
    header_cells = "".join(f"<th>{html.escape(p)}</th>" for p in trend["periods"])
    rows = []
    for cid in ids:
        cells = []
        for a in trend["analyses"]:
            entry = _entry_by_id(a, cid)
            if entry is None:
                cells.append("<td>&mdash;</td>")
                continue
            icon = status_colors[entry["status"]]["icon"]
            status_class = STATUS_CLASS[entry["status"]]
            direction = "favorable" if entry["favorable"] else "unfavorable"
            pct = entry.get("diff_pct")
            title = f"{entry['status']} ({direction}): {pct:+.1f}%" if pct is not None else entry["status"]
            cells.append(f'<td><span class="status-pill {status_class}" title="{html.escape(title)}">{icon}</span></td>')
        rows.append(f"<tr><td>{html.escape(labels.get(cid, cid))}</td>{''.join(cells)}</tr>")

    return f"""
    <table class="flag-history">
      <thead><tr><th>Category</th>{header_cells}</tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def render_sparkline_svg(values: list, statuses: list, muted_color: str, status_colors: dict,
                          width: int = 64, height: int = 22) -> str:
    """A minimal trend line -- dataviz skill's stat-tile spec: the line
    drawn in a de-emphasis (muted) hue, the current (last) period's point
    highlighted in its own status color, no axes/gridlines/labels. Needs
    at least 2 points; the caller is responsible for not calling this with
    fewer (mirrors load_entity_trend's own >=2-periods rule)."""
    n = len(values)
    if n < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or max(abs(hi), 1.0)
    pad = 3.0

    def x(i):
        return pad + i * (width - 2 * pad) / (n - 1)

    def y(v):
        return height - pad - (v - lo) / span * (height - 2 * pad)

    pts = [(x(i), y(v)) for i, v in enumerate(values)]
    path_d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    end_color = status_colors[statuses[-1]]["hex"]
    line = f'<path d="{path_d}" fill="none" stroke="{muted_color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
    dot = f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="2.5" fill="{end_color}"/>'
    return (f'<svg class="sparkline" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="trend over {n} periods">{line}{dot}</svg>')


def _entry_trend_series(trend: dict, entry_id: str):
    """Actual-value series for one pnl/kpi id across every period in
    `trend`, skipping periods where the id doesn't resolve (e.g. a
    Compact-brand entity with no Spa categories). Returns (values,
    statuses) both possibly shorter than trend['analyses'] -- the caller
    checks length before rendering a sparkline."""
    values, statuses = [], []
    for a in trend["analyses"]:
        entry = _entry_by_id(a, entry_id)
        if entry is not None:
            values.append(entry["act"])
            statuses.append(entry["status"])
    return values, statuses


def render_trend_section_html(trend: dict, colors: dict, status_colors: dict) -> str:
    if trend is None:
        return "<p>Trend view needs at least 2 analyzed periods for this entity — only 1 committed so far.</p>"
    focus_entry = _entry_by_id(trend["analyses"][0], trend["analyses"][0]["focus_metric"])
    focus_label = focus_entry["label"] if focus_entry else "Focus metric"
    return f"""
    <div class="trend-block">
      <h3>{html.escape(focus_label)} by month</h3>
      {render_gop_by_month_svg(trend, colors, status_colors)}
    </div>
    <div class="trend-block">
      <h3>Flag history by category</h3>
      {render_flag_history_grid(trend, status_colors)}
    </div>"""


def render_comment_notes(comments: list) -> str:
    """Renders a row's/KPI's pinned comments — reviewer notes added via
    /feedback, visually distinct from the LLM-written narrative (no
    status-color styling, an attribution line instead) so a reader can
    always tell a human annotation from generated prose."""
    if not comments:
        return ""
    notes = "".join(
        f'<div class="comment-note"><p>{html.escape(c["text"])}</p>'
        f'<div class="comment-byline">{html.escape(c["author"])} &middot; {html.escape(c["created_at"][:10])}</div></div>'
        for c in comments
    )
    return f'<div class="comments">{notes}</div>'


def render_kpi_cards(analysis: dict, comments_by_row: dict = None, trend: dict = None,
                      colors: dict = None, status_colors: dict = None) -> str:
    comments_by_row = comments_by_row or {}
    cards = []
    for kpi in analysis["kpis"]:
        status_class = STATUS_CLASS[kpi["status"]]
        arrow = "+" if kpi["diff"] > 0 else ("−" if kpi["diff"] < 0 else "±")
        sparkline_html = ""
        if trend is not None:
            values, statuses = _entry_trend_series(trend, kpi["id"])
            if len(values) >= 2:
                sparkline_html = (f'<div class="sparkline-wrap">'
                                   f'{render_sparkline_svg(values, statuses, colors["border"], status_colors)}</div>')
        cards.append(f"""
          <div class="kpi-card">
            <div class="label">{html.escape(kpi['label'])}</div>
            <div class="value">{fmt_kpi_value(kpi['act'], kpi['format'], analysis['currency'])}</div>
            <div class="delta status-pill {status_class}">{arrow} vs {fmt_kpi_value(kpi['budget'], kpi['format'], analysis['currency'])} {html.escape(analysis['comparison_label'])}</div>
            {sparkline_html}
            {render_comment_notes(comments_by_row.get(kpi['id']))}
          </div>""")
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def render_pnl_table(analysis: dict, comments_by_row: dict = None, trend: dict = None,
                      colors: dict = None, status_colors: dict = None) -> str:
    comments_by_row = comments_by_row or {}
    emphasize = {analysis["focus_metric"], analysis["secondary_metric"]}
    rows = []
    for entry in analysis["pnl"]:
        classes = []
        if entry["kind"] == "subtotal":
            classes.append("subtotal")
        if entry["id"] in emphasize:
            classes.append("focus-metric")
        diff_pct = f"{entry['diff_pct']:+.1f}%" if entry["diff_pct"] is not None else "—"
        status_class = STATUS_CLASS[entry["status"]]
        trend_cell = "—"
        if trend is not None and entry["status"] != "ON TARGET":
            values, statuses = _entry_trend_series(trend, entry["id"])
            if len(values) >= 2:
                trend_cell = render_sparkline_svg(values, statuses, colors["border"], status_colors)
        rows.append(f"""
          <tr class="{' '.join(classes)}">
            <td>{html.escape(entry['label'])}</td>
            <td>{fmt_amount(entry['act'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['budget'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['diff'], analysis['currency'])}</td>
            <td>{diff_pct}</td>
            <td><span class="status-pill {status_class}">{html.escape(entry['status'])}</span></td>
            <td>{trend_cell}</td>
          </tr>""")
        row_comments = comments_by_row.get(entry["id"])
        if row_comments:
            rows.append(f'<tr class="comment-row"><td colspan="7">{render_comment_notes(row_comments)}</td></tr>')
    return f"""
    <table>
      <thead><tr><th>Category</th><th>Actual</th><th>{html.escape(analysis['comparison_label'])}</th>
        <th>Diff</th><th>Diff %</th><th>Status</th><th>Trend</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def render_drill_down(drill_down: dict, currency: str) -> str:
    vendor_rows = "".join(
        f"<tr><td>{html.escape(v['vendor'])}</td><td>{fmt_amount(v['amount'], currency)}</td></tr>"
        for v in drill_down["by_vendor"]
    )
    return f"""
    <details>
      <summary>Transaction drill-down ({drill_down['transaction_count']} transaction(s))</summary>
      <table class="drill-table">
        <thead><tr><th>Vendor</th><th>Amount</th></tr></thead>
        <tbody>{vendor_rows}</tbody>
      </table>
    </details>"""


def render_audit_trail_html(flag: dict, currency: str) -> str:
    """The 'why was this flagged?' expander (docs/IMPROVEMENT_IDEAS.md idea
    6, tasks.md task 33): every value here is a field analyze.py already
    computed and wrote to the analysis JSON -- this function only formats
    them, it never decides anything itself, so the audit trail is provably
    the same data the flag itself was built from, not a second, separately
    -maintained description of it. Two shapes: category/subtotal (pct +
    absolute AND logic) and KPI (single two-tier deviation, no absolute
    floor) -- see thresholds.yaml's own header comment and analyze.py's
    classify_category/classify_kpi, which this mirrors exactly."""
    if "threshold_kind" in flag:
        unit = "pp" if flag["threshold_kind"] == "pp" else "%"
        notice = f"{flag['threshold_notice']:.1f}{unit}"
        investigate = f"{flag['threshold_investigate']:.1f}{unit}"
        deviation = f"{flag['threshold_deviation']:.1f}{unit}"
        rule = (f"KPI thresholds are a single two-tier deviation check (no AND logic): "
                f"NOTE at or above {notice} deviation from Budget, INVESTIGATE at or above "
                f"{investigate}. No absolute-currency floor applies to KPIs.")
        computed = f"This period's deviation: <strong>{deviation}</strong> from Budget."
    else:
        pct_limit = f"{flag['threshold_pct']:.1f}%"
        abs_limit = f"{flag['threshold_absolute']:,.0f} {currency}"
        rule = (f"INVESTIGATE requires breaching <strong>both</strong> the {pct_limit} threshold "
                f"<strong>and</strong> the {abs_limit} threshold vs Budget; NOTE requires breaching "
                f"either one alone; otherwise ON TARGET.")
        pct_state = "breached" if flag["pct_breached"] else "not breached"
        abs_state = "breached" if flag["absolute_breached"] else "not breached"
        diff_pct_str = f"{abs(flag['diff_pct']):.1f}%" if flag["diff_pct"] is not None else "n/a (zero Budget)"
        computed = (f"This period: {diff_pct_str} ({fmt_amount(abs(flag['diff']), currency)}) vs Budget — "
                    f"percentage threshold <strong>{pct_state}</strong> ({diff_pct_str} vs {pct_limit} limit), "
                    f"absolute threshold <strong>{abs_state}</strong> "
                    f"({fmt_amount(abs(flag['diff']), currency)} vs {abs_limit} limit).")
    return f"""
    <details class="audit-trail">
      <summary>Why was this flagged?</summary>
      <dl class="audit-fields">
        <dt>Rule</dt><dd>{rule}</dd>
        <dt>This period</dt><dd>{computed}</dd>
        <dt>Config source</dt><dd><code>thresholds.yaml &rarr; {html.escape(flag['threshold_source'])}</code></dd>
      </dl>
    </details>"""


def render_deviation_highlights(analysis: dict, narrative: dict, feedback: dict = None) -> str:
    category_narratives = (narrative or {}).get("category_narratives", {})
    overrides = (feedback or {}).get("narrative_overrides", {})
    if not analysis["flags"]:
        return "<p>No categories or KPIs breached threshold this period.</p>"
    blocks = []
    for flag in analysis["flags"]:
        status_class = STATUS_CLASS[flag["status"]]
        override = overrides.get(flag["id"])
        if override and override.get("text") is None:
            narrative_html = (
                f'<em>Narrative note removed by {html.escape(override["author"])} '
                f'on {html.escape(override["created_at"][:10])}.</em>'
            )
        else:
            text = category_narratives.get(flag["id"])
            narrative_html = html.escape(text) if text else "Narrative not yet written for this item."
        drill_down_html = ""
        if flag["id"] in analysis["drill_downs"]:
            drill_down_html = render_drill_down(analysis["drill_downs"][flag["id"]], analysis["currency"])
        audit_trail_html = render_audit_trail_html(flag, analysis["currency"])
        blocks.append(f"""
        <div class="highlight-card">
          <h3><span class="status-pill {status_class}">{html.escape(flag['status'])}</span> {html.escape(flag['label'])}</h3>
          <p>{narrative_html}</p>
          {audit_trail_html}
          {drill_down_html}
        </div>""")
    return "".join(blocks)


def render_profitability_summary(narrative: dict, feedback: dict = None) -> str:
    override = ((feedback or {}).get("narrative_overrides", {})).get("profitability_summary")
    if override and override.get("text") is None:
        return (
            f'<p><em>Summary removed by {html.escape(override["author"])} '
            f'on {html.escape(override["created_at"][:10])}.</em></p>'
        )
    text = (narrative or {}).get("profitability_summary")
    if text:
        return f"<p>{html.escape(text)}</p>"
    return "<p>Narrative not yet written — run /analysis via Claude Code to generate it before /dashboard.</p>"


def render_dashboard_html(analysis: dict, narrative: dict, brand: dict, config_dir: Path, feedback: dict = None,
                           outputs_dir: Path = None) -> str:
    colors = brand["colors"]
    status_colors = brand["status_colors"]
    surface = colors["surface"]
    rows_with_comments = comments_by_row(feedback)

    bridge = compute_gop_bridge(analysis)
    if bridge:
        focus_metric_label = bridge["focus_label"]
        waterfall_html = render_waterfall_svg(bridge, analysis["currency"], colors, status_colors)
    else:
        focus_metric_label = "Variance"
        waterfall_html = "<p>No variance bridge available for this metric.</p>"

    trend = (load_entity_trend(analysis["entity_code"], outputs_dir, analysis["period"])
             if outputs_dir is not None else None)
    trend_html = render_trend_section_html(trend, colors, status_colors)

    tokens = {
        "ENTITY_NAME": html.escape(analysis["entity_name"]),
        "PERIOD": html.escape(analysis["period"]),
        "COMPARISON_LABEL": html.escape(analysis["comparison_label"]),
        "LOGO_HTML": render_logo_html(brand, config_dir),
        "FOCUS_METRIC_LABEL": html.escape(focus_metric_label),
        "WATERFALL_HTML": waterfall_html,
        "TREND_SECTION_HTML": trend_html,
        "KPI_CARDS_HTML": render_kpi_cards(analysis, rows_with_comments, trend, colors, status_colors),
        "PROFITABILITY_SUMMARY_HTML": render_profitability_summary(narrative, feedback),
        "PNL_TABLE_HTML": render_pnl_table(analysis, rows_with_comments, trend, colors, status_colors),
        "DEVIATION_HIGHLIGHTS_HTML": render_deviation_highlights(analysis, narrative, feedback),
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
        "FOCUS_METRIC_BG": tint(colors["secondary"], surface),
    }

    html_out = TEMPLATE_PATH.read_text()
    for token, value in tokens.items():
        html_out = html_out.replace("{{" + token + "}}", value)
    return html_out


def render_dashboard_report(analysis_path: Path, narrative_path: Path, config_dir: Path, outputs_dir: Path,
                             feedback_dir: Path = None) -> Path:
    with open(analysis_path) as f:
        analysis = json.load(f)
    narrative = None
    if narrative_path.exists():
        with open(narrative_path) as f:
            narrative = json.load(f)
    brand = get_brand(config_dir)

    feedback = None
    if feedback_dir is not None:
        feedback = load_feedback(feedback_dir, analysis["entity_code"], analysis["period"])
        for row_id in stale_overrides(narrative, feedback):
            print(
                f"WARNING: narrative override on '{row_id}' for {analysis['entity_code']}/{analysis['period']} "
                "was written against LLM text that has since changed (narrative JSON was regenerated) — "
                "the override still applied, but review it.",
                file=sys.stderr,
            )
        narrative = apply_overrides_to_narrative(narrative, feedback)

    outputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = outputs_dir / f"{analysis['entity_code']}-Dashboard_{analysis['period']}.html"
    with open(out_path, "w") as f:
        f.write(render_dashboard_html(analysis, narrative, brand, config_dir, feedback, outputs_dir))
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all analysis_*.json found)")
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--outputs-dir", default="outputs", type=Path)
    parser.add_argument("--feedback-dir", default="feedback", type=Path,
                         help="directory of feedback_{ENTITY}_{PERIOD}.json files (default: feedback); "
                              "pass a nonexistent dir to render with no feedback applied")
    args = parser.parse_args()

    outputs_dir = args.outputs_dir
    if args.entities:
        entity_codes = args.entities.split(",")
    else:
        entity_codes = sorted(
            p.stem.split("_")[1] for p in outputs_dir.glob(f"analysis_*_{args.period}.json")
        )

    rendered = []
    for entity_code in entity_codes:
        analysis_path = outputs_dir / f"analysis_{entity_code}_{args.period}.json"
        if not analysis_path.exists():
            print(f"SKIPPED: {analysis_path} not found — run /analysis first", file=sys.stderr)
            continue
        narrative_path = outputs_dir / f"narrative_{entity_code}_{args.period}.json"
        out_path = render_dashboard_report(analysis_path, narrative_path, args.config_dir, outputs_dir, args.feedback_dir)
        print(f"{entity_code}: wrote {out_path}" + ("" if narrative_path.exists() else " (no narrative found)"))
        rendered.append(entity_code)

    print(f"\n{len(rendered)} dashboard(s) rendered")
    sys.exit(1 if not rendered else 0)


if __name__ == "__main__":
    main()
