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
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "analysis" / "scripts"))
from config_loader import ConfigError, load_brand  # noqa: E402

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


def render_kpi_cards(analysis: dict) -> str:
    cards = []
    for kpi in analysis["kpis"]:
        status_class = STATUS_CLASS[kpi["status"]]
        arrow = "+" if kpi["diff"] > 0 else ("−" if kpi["diff"] < 0 else "±")
        cards.append(f"""
          <div class="kpi-card">
            <div class="label">{html.escape(kpi['label'])}</div>
            <div class="value">{fmt_kpi_value(kpi['act'], kpi['format'], analysis['currency'])}</div>
            <div class="delta status-pill {status_class}">{arrow} vs {fmt_kpi_value(kpi['budget'], kpi['format'], analysis['currency'])} {html.escape(analysis['comparison_label'])}</div>
          </div>""")
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def render_pnl_table(analysis: dict) -> str:
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
        rows.append(f"""
          <tr class="{' '.join(classes)}">
            <td>{html.escape(entry['label'])}</td>
            <td>{fmt_amount(entry['act'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['budget'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['diff'], analysis['currency'])}</td>
            <td>{diff_pct}</td>
            <td><span class="status-pill {status_class}">{html.escape(entry['status'])}</span></td>
          </tr>""")
    return f"""
    <table>
      <thead><tr><th>Category</th><th>Actual</th><th>{html.escape(analysis['comparison_label'])}</th>
        <th>Diff</th><th>Diff %</th><th>Status</th></tr></thead>
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


def render_deviation_highlights(analysis: dict, narrative: dict) -> str:
    category_narratives = (narrative or {}).get("category_narratives", {})
    if not analysis["flags"]:
        return "<p>No categories or KPIs breached threshold this period.</p>"
    blocks = []
    for flag in analysis["flags"]:
        status_class = STATUS_CLASS[flag["status"]]
        text = category_narratives.get(flag["id"])
        narrative_html = html.escape(text) if text else "Narrative not yet written for this item."
        drill_down_html = ""
        if flag["id"] in analysis["drill_downs"]:
            drill_down_html = render_drill_down(analysis["drill_downs"][flag["id"]], analysis["currency"])
        blocks.append(f"""
        <div class="highlight-card">
          <h3><span class="status-pill {status_class}">{html.escape(flag['status'])}</span> {html.escape(flag['label'])}</h3>
          <p>{narrative_html}</p>
          {drill_down_html}
        </div>""")
    return "".join(blocks)


def render_profitability_summary(narrative: dict) -> str:
    text = (narrative or {}).get("profitability_summary")
    if text:
        return f"<p>{html.escape(text)}</p>"
    return "<p>Narrative not yet written — run /analysis via Claude Code to generate it before /dashboard.</p>"


def render_dashboard_html(analysis: dict, narrative: dict, brand: dict, config_dir: Path) -> str:
    colors = brand["colors"]
    status_colors = brand["status_colors"]
    surface = colors["surface"]

    tokens = {
        "ENTITY_NAME": html.escape(analysis["entity_name"]),
        "PERIOD": html.escape(analysis["period"]),
        "COMPARISON_LABEL": html.escape(analysis["comparison_label"]),
        "LOGO_HTML": render_logo_html(brand, config_dir),
        "KPI_CARDS_HTML": render_kpi_cards(analysis),
        "PROFITABILITY_SUMMARY_HTML": render_profitability_summary(narrative),
        "PNL_TABLE_HTML": render_pnl_table(analysis),
        "DEVIATION_HIGHLIGHTS_HTML": render_deviation_highlights(analysis, narrative),
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


def render_dashboard_report(analysis_path: Path, narrative_path: Path, config_dir: Path, outputs_dir: Path) -> Path:
    with open(analysis_path) as f:
        analysis = json.load(f)
    narrative = None
    if narrative_path.exists():
        with open(narrative_path) as f:
            narrative = json.load(f)
    brand = get_brand(config_dir)

    outputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = outputs_dir / f"{analysis['entity_code']}-Dashboard_{analysis['period']}.html"
    with open(out_path, "w") as f:
        f.write(render_dashboard_html(analysis, narrative, brand, config_dir))
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all analysis_*.json found)")
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--outputs-dir", default="outputs", type=Path)
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
        out_path = render_dashboard_report(analysis_path, narrative_path, args.config_dir, outputs_dir)
        print(f"{entity_code}: wrote {out_path}" + ("" if narrative_path.exists() else " (no narrative found)"))
        rendered.append(entity_code)

    print(f"\n{len(rendered)} dashboard(s) rendered")
    sys.exit(1 if not rendered else 0)


if __name__ == "__main__":
    main()
