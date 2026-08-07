#!/usr/bin/env python3
"""Render the analyst-facing report (PLAN.md §6 step 6):
outputs/{ENTITY}-Analysis_{PERIOD}.html — a readable, self-contained
single file combining analyze.py's numbers with the Claude narrative
pass's prose (PLAN.md §6 step 5).

This script is purely a renderer: it never writes narrative text itself.
It reads analysis_{ENTITY}_{PERIOD}.json (analyze.py's output, required)
and narrative_{ENTITY}_{PERIOD}.json (Claude-written, optional — see
SKILL.md for the narrative-writing instructions and this file's shape).
Without a narrative file, it still renders a complete numbers-only
report (useful for testing the renderer itself, or for a quick look
before the narrative pass runs) with a visible note that the narrative
hasn't been written yet.

Narrative JSON shape:
{
  "executive_summary": "...",
  "profitability_summary": "...",
  "category_narratives": {"<category_or_kpi_id>": "...", ...}
}
"""
import argparse
import html
import json
import sys
from pathlib import Path

STATUS_COLORS = {
    "ON TARGET": ("#2E7D4F", "#EAF5EE", "✓"),
    "NOTE": ("#B8860B", "#FBF3DE", "●"),
    "INVESTIGATE": ("#B23A3A", "#FBEAEA", "▲"),
}

CSS = """
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #20242A;
         background: #F7F7F5; margin: 0; padding: 2rem; line-height: 1.5; }
  .report { max-width: 960px; margin: 0 auto; background: #fff; border: 1px solid #DDD8CE;
            border-radius: 8px; padding: 2rem 2.5rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.25rem; }
  .subtitle { color: #55606B; margin: 0 0 1.5rem; }
  h2 { font-size: 1.05rem; text-transform: uppercase; letter-spacing: 0.04em; color: #55606B;
       border-bottom: 1px solid #E4E1D9; padding-bottom: 0.4rem; margin-top: 2.2rem; }
  p.narrative { white-space: pre-wrap; }
  table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.92rem; }
  th, td { text-align: right; padding: 0.4rem 0.6rem; border-bottom: 1px solid #EEECE5; }
  th:first-child, td:first-child { text-align: left; }
  th { font-weight: 600; color: #55606B; font-size: 0.82rem; text-transform: uppercase; }
  tr.subtotal td { font-weight: 700; border-top: 1px solid #C9C4B8; }
  .status-pill { display: inline-block; padding: 0.05rem 0.5rem; border-radius: 999px;
                 font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 0.75rem; margin-top: 0.75rem; }
  .kpi-card { border: 1px solid #E4E1D9; border-radius: 6px; padding: 0.75rem 1rem; }
  .kpi-card .label { font-size: 0.8rem; color: #55606B; }
  .kpi-card .value { font-size: 1.3rem; font-weight: 700; margin: 0.15rem 0; }
  .flag-block { border: 1px solid #E4E1D9; border-radius: 6px; padding: 1rem 1.2rem; margin-top: 1rem; }
  .flag-block h3 { margin: 0 0 0.4rem; font-size: 1rem; }
  details { margin-top: 0.6rem; }
  summary { cursor: pointer; color: #55606B; font-size: 0.88rem; }
  .drill-table { margin-top: 0.5rem; }
  .missing-narrative { color: #55606B; font-style: italic; }
  @media print { body { background: #fff; padding: 0; } .report { border: none; } }
"""


def status_pill(status: str) -> str:
    color, bg, icon = STATUS_COLORS[status]
    return f'<span class="status-pill" style="color:{color};background:{bg}">{icon} {html.escape(status)}</span>'


def fmt_amount(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def fmt_kpi_value(value: float, fmt: str, currency: str) -> str:
    if fmt == "percent":
        return f"{value * 100:.1f}%"
    return f"{value:,.0f} {currency}"


def render_pnl_table(analysis: dict) -> str:
    rows = []
    for entry in analysis["pnl"]:
        row_class = "subtotal" if entry["kind"] == "subtotal" else ""
        diff_pct = f"{entry['diff_pct']:+.1f}%" if entry["diff_pct"] is not None else "—"
        rows.append(f"""
          <tr class="{row_class}">
            <td>{html.escape(entry['label'])}</td>
            <td>{fmt_amount(entry['act'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['budget'], analysis['currency'])}</td>
            <td>{fmt_amount(entry['diff'], analysis['currency'])}</td>
            <td>{diff_pct}</td>
            <td>{status_pill(entry['status'])}</td>
          </tr>""")
    return f"""
    <table>
      <thead><tr><th>Category</th><th>Actual</th><th>{html.escape(analysis['comparison_label'])}</th>
        <th>Diff</th><th>Diff %</th><th>Status</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>"""


def render_kpi_grid(analysis: dict) -> str:
    cards = []
    for kpi in analysis["kpis"]:
        color, _, icon = STATUS_COLORS[kpi["status"]]
        cards.append(f"""
          <div class="kpi-card">
            <div class="label">{html.escape(kpi['label'])}</div>
            <div class="value" style="color:{color}">{fmt_kpi_value(kpi['act'], kpi['format'], analysis['currency'])}</div>
            <div>{icon} vs {fmt_kpi_value(kpi['budget'], kpi['format'], analysis['currency'])} {html.escape(analysis['comparison_label'])}</div>
          </div>""")
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


def render_drill_down(drill_down: dict, currency: str) -> str:
    vendor_rows = "".join(
        f"<tr><td>{html.escape(v['vendor'])}</td><td>{fmt_amount(v['amount'], currency)}</td></tr>"
        for v in drill_down["by_vendor"]
    )
    txn_rows = "".join(
        f"<tr><td>{html.escape(t['date'])}</td><td>{html.escape(t['vendor'])}</td>"
        f"<td>{html.escape(t['description'])}</td><td>{fmt_amount(float(t['amount']), currency)}</td></tr>"
        for t in drill_down["transactions"]
    )
    return f"""
    <details>
      <summary>Transaction drill-down ({drill_down['transaction_count']} transaction(s))</summary>
      <table class="drill-table">
        <thead><tr><th>Vendor</th><th>Amount</th></tr></thead>
        <tbody>{vendor_rows}</tbody>
      </table>
      <table class="drill-table">
        <thead><tr><th>Date</th><th>Vendor</th><th>Description</th><th>Amount</th></tr></thead>
        <tbody>{txn_rows}</tbody>
      </table>
    </details>"""


def render_flags(analysis: dict, narrative: dict) -> str:
    category_narratives = narrative.get("category_narratives", {}) if narrative else {}
    blocks = []
    for flag in analysis["flags"]:
        item_id = flag["id"]
        text = category_narratives.get(item_id)
        narrative_html = (
            f'<p class="narrative">{html.escape(text)}</p>' if text
            else '<p class="missing-narrative">Narrative not yet written for this item.</p>'
        )
        drill_down_html = ""
        if item_id in analysis["drill_downs"]:
            drill_down_html = render_drill_down(analysis["drill_downs"][item_id], analysis["currency"])
        blocks.append(f"""
        <div class="flag-block">
          <h3>{status_pill(flag['status'])} {html.escape(flag['label'])}</h3>
          {narrative_html}
          {drill_down_html}
        </div>""")
    return "".join(blocks) if blocks else "<p>No categories or KPIs breached threshold this period.</p>"


def render_revenue_mix(analysis: dict) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(m['label'])}</td><td>{m['mix_actual_pct']:.1f}%</td>"
        f"<td>{m['mix_budget_pct']:.1f}%</td><td>{m['mix_shift_pp']:+.1f}pp</td></tr>"
        for m in analysis["revenue_mix"]
    )
    return f"""
    <table>
      <thead><tr><th>Category</th><th>Actual mix</th><th>{html.escape(analysis['comparison_label'])} mix</th><th>Shift</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>"""


def render_html(analysis: dict, narrative: dict) -> str:
    executive_summary = (narrative or {}).get("executive_summary")
    profitability_summary = (narrative or {}).get("profitability_summary")

    executive_html = (
        f'<p class="narrative">{html.escape(executive_summary)}</p>' if executive_summary
        else '<p class="missing-narrative">Narrative not yet written — run /analysis via Claude Code to generate it.</p>'
    )
    profitability_html = (
        f'<p class="narrative">{html.escape(profitability_summary)}</p>' if profitability_summary
        else '<p class="missing-narrative">Narrative not yet written for the profitability summary.</p>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(analysis['entity_name'])} — Analysis {html.escape(analysis['period'])}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="report">
    <h1>{html.escape(analysis['entity_name'])}</h1>
    <p class="subtitle">Analysis for {html.escape(analysis['period'])} — vs {html.escape(analysis['comparison_label'])}</p>

    <h2>Executive Summary</h2>
    {executive_html}

    <h2>Key Performance Indicators</h2>
    {render_kpi_grid(analysis)}

    <h2>Profitability Summary</h2>
    {profitability_html}

    <h2>P&amp;L</h2>
    {render_pnl_table(analysis)}

    <h2>Revenue Mix</h2>
    {render_revenue_mix(analysis)}

    <h2>Flagged Items</h2>
    {render_flags(analysis, narrative)}
  </div>
</body>
</html>
"""


def render_analysis_report(analysis_path: Path, narrative_path: Path, outputs_dir: Path) -> Path:
    with open(analysis_path) as f:
        analysis = json.load(f)
    narrative = None
    if narrative_path.exists():
        with open(narrative_path) as f:
            narrative = json.load(f)

    outputs_dir.mkdir(parents=True, exist_ok=True)
    out_path = outputs_dir / f"{analysis['entity_code']}-Analysis_{analysis['period']}.html"
    with open(out_path, "w") as f:
        f.write(render_html(analysis, narrative))
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all analysis_*.json found)")
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
            print(f"SKIPPED: {analysis_path} not found — run analyze.py first", file=sys.stderr)
            continue
        narrative_path = outputs_dir / f"narrative_{entity_code}_{args.period}.json"
        out_path = render_analysis_report(analysis_path, narrative_path, outputs_dir)
        print(f"{entity_code}: wrote {out_path}" + ("" if narrative_path.exists() else " (no narrative found)"))
        rendered.append(entity_code)

    print(f"\n{len(rendered)} report(s) rendered")
    sys.exit(1 if not rendered else 0)


if __name__ == "__main__":
    main()
