#!/usr/bin/env python3
"""Deterministic flagging engine (PLAN.md §6 step 4). Applies
thresholds.yaml to every P&L category, every subtotal, and every KPI,
and writes analysis_{ENTITY}_{PERIOD}.json — the machine-readable
contract the Claude narrative pass (SKILL.md) and /dashboard both read.
No interpretation happens here: status, direction, and drill-down data
are all mechanical. See CLAUDE.md's Python-computes/Claude-interprets rule.

Importable: analyze_period() returns a plain dict (the JSON body) built
from preprocess.py's PeriodData, so tests can assert on it directly
without going through a file.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

from config_loader import ConfigError, load_config
from preprocess import PreprocessError, preprocess_period

STATUS_ON_TARGET = "ON TARGET"
STATUS_NOTE = "NOTE"
STATUS_INVESTIGATE = "INVESTIGATE"

# Categories in these pnl-structure.yaml groups are costs: actual below
# Budget is favorable. Everything else (revenue, and every profit
# subtotal) is favorable when actual is above Budget. Subtotals don't
# carry a `group` in pnl-structure.yaml, so the cost-like ones are named
# explicitly here.
EXPENSE_GROUPS = {"departmental_expense", "undistributed_expense", "fixed_charge", "below_ebitda"}
EXPENSE_LIKE_SUBTOTALS = {"total_departmental_expenses", "total_undistributed_expenses", "total_fixed_charges"}

# occupancy_pct/gop_pct are already ratios, so their kpi_thresholds
# (thresholds.yaml) are in percentage points of absolute deviation;
# revpar/revenue_per_fte are currency-per-unit, so theirs are relative %.
KPI_THRESHOLD_KIND = {"occupancy_pct": "pp", "gop_pct": "pp", "revpar": "pct", "revenue_per_fte": "pct"}


def compute_variance(act: float, budget: float):
    """Returns (diff, relative_pct). relative_pct is None when budget is
    0 (an infinite relative change isn't JSON-safe) — callers must treat
    None as 'any nonzero actual is a breach', not as 'no variance'."""
    diff = act - budget
    pct = (diff / budget * 100) if budget else None
    return diff, pct


def is_pct_breach(pct, threshold_pct, act) -> bool:
    if pct is None:
        return act != 0
    return abs(pct) >= threshold_pct


def get_category_threshold(config, item_id) -> dict:
    return config.thresholds["category_overrides"].get(item_id, config.thresholds["default"])


def classify_category(item_id: str, act: float, budget: float, config, currency: str) -> dict:
    diff, pct = compute_variance(act, budget)
    threshold = get_category_threshold(config, item_id)
    pct_hit = is_pct_breach(pct, threshold["pct"], act)
    absolute_hit = abs(diff) >= threshold["absolute_by_currency"][currency]

    if pct_hit and absolute_hit:
        status = STATUS_INVESTIGATE
    elif pct_hit or absolute_hit:
        status = STATUS_NOTE
    else:
        status = STATUS_ON_TARGET

    return dict(diff=round(diff, 2), diff_pct=(round(pct, 2) if pct is not None else None), status=status,
                threshold_pct=threshold["pct"], threshold_absolute=threshold["absolute_by_currency"][currency])


def classify_kpi(kpi_id: str, act: float, budget: float, config) -> dict:
    threshold = config.kpi_thresholds[kpi_id]
    diff = act - budget
    kind = KPI_THRESHOLD_KIND[kpi_id]
    if kind == "pp":
        deviation = abs(diff) * 100
        notice, investigate = threshold["notice_pp"], threshold["investigate_pp"]
    else:
        _, pct = compute_variance(act, budget)
        deviation = abs(pct) if pct is not None else (100.0 if act else 0.0)
        notice, investigate = threshold["notice_pct"], threshold["investigate_pct"]

    if deviation >= investigate:
        status = STATUS_INVESTIGATE
    elif deviation >= notice:
        status = STATUS_NOTE
    else:
        status = STATUS_ON_TARGET
    return dict(diff=diff, status=status)


def is_favorable(item_id: str, diff: float, config):
    if diff == 0:
        return None
    expense_like = (
        config.category_to_group.get(item_id) in EXPENSE_GROUPS
        if item_id in config.category_to_group
        else item_id in EXPENSE_LIKE_SUBTOTALS
    )
    return (diff < 0) if expense_like else (diff > 0)


def build_pnl_entries(data, config, currency: str) -> list:
    subtotal_ids = {s["id"] for s in config.subtotals}
    entries = []
    for item_id in config.presentation_order:
        act = data.pnl_actual.get(item_id, 0.0)
        budget = data.pnl_budget.get(item_id, 0.0)
        classification = classify_category(item_id, act, budget, config, currency)
        entries.append(dict(
            id=item_id,
            label=config.category_labels[item_id],
            kind="subtotal" if item_id in subtotal_ids else "category",
            act=round(act, 2),
            budget=round(budget, 2),
            favorable=is_favorable(item_id, classification["diff"], config),
            **classification,
        ))
    return entries


def build_kpi_entries(data, config) -> list:
    entries = []
    for kpi in config.kpis:
        kpi_id = kpi["id"]
        act, budget = data.kpis[kpi_id]["actual"], data.kpis[kpi_id]["budget"]
        classification = classify_kpi(kpi_id, act, budget, config)
        entries.append(dict(
            id=kpi_id, label=kpi["name"], format=kpi["format"],
            act=round(act, 4), budget=round(budget, 4),
            favorable=(classification["diff"] > 0) if classification["diff"] != 0 else None,
            **classification,
        ))
    return entries


def build_revenue_mix(data, config) -> list:
    total_revenue_actual = data.pnl_actual["total_revenue"]
    total_revenue_budget = data.pnl_budget["total_revenue"]
    mix = []
    for category_id in config.categories_by_group.get("revenue", []):
        act = data.pnl_actual.get(category_id, 0.0)
        budget = data.pnl_budget.get(category_id, 0.0)
        mix_act = (act / total_revenue_actual * 100) if total_revenue_actual else 0.0
        mix_budget = (budget / total_revenue_budget * 100) if total_revenue_budget else 0.0
        mix.append(dict(
            id=category_id, label=config.category_labels[category_id],
            mix_actual_pct=round(mix_act, 2), mix_budget_pct=round(mix_budget, 2),
            mix_shift_pp=round(mix_act - mix_budget, 2),
        ))
    return mix


def load_transactions(entity_code: str, period: str, inbox_dir: Path) -> list:
    path = inbox_dir / f"{entity_code}_transactions_{period}.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def build_drill_down(category_id: str, transactions: list, config) -> dict:
    rows = [t for t in transactions if config.account_to_category.get(t["gl_account"]) == category_id]
    if not rows:
        return None
    by_vendor, by_account = {}, {}
    for t in rows:
        amount = float(t["amount"])
        by_vendor[t["vendor"]] = by_vendor.get(t["vendor"], 0.0) + amount
        acct = t["gl_account"]
        by_account.setdefault(acct, {"account_name": config.account_names.get(acct, ""), "amount": 0.0})
        by_account[acct]["amount"] += amount
    return dict(
        transaction_count=len(rows),
        by_vendor=sorted(({"vendor": v, "amount": round(a, 2)} for v, a in by_vendor.items()),
                          key=lambda r: -r["amount"]),
        by_account=sorted(({"gl_account": k, **v, "amount": round(v["amount"], 2)} for k, v in by_account.items()),
                           key=lambda r: -r["amount"]),
        transactions=sorted(rows, key=lambda t: t["date"]),
    )


def analyze_period(entity_code: str, period: str, config, inbox_dir: Path) -> dict:
    data = preprocess_period(entity_code, period, config, inbox_dir)
    entity = config.entities[entity_code]
    currency = entity["currency"]

    pnl_entries = build_pnl_entries(data, config, currency)
    kpi_entries = build_kpi_entries(data, config)
    flags = [e for e in pnl_entries if e["status"] != STATUS_ON_TARGET] + \
            [e for e in kpi_entries if e["status"] != STATUS_ON_TARGET]

    transactions = load_transactions(entity_code, period, inbox_dir)
    drill_downs = {}
    for entry in pnl_entries:
        if entry["kind"] == "category" and entry["status"] != STATUS_ON_TARGET:
            drill_down = build_drill_down(entry["id"], transactions, config)
            if drill_down:
                drill_downs[entry["id"]] = drill_down

    return dict(
        entity_code=entity_code,
        entity_name=entity["name"],
        period=period,
        currency=currency,
        comparison_label=config.terminology["comparison_label"],
        focus_metric=config.terminology["focus_metric"],
        secondary_metric=config.terminology["secondary_metric"],
        pnl=pnl_entries,
        kpis=kpi_entries,
        revenue_mix=build_revenue_mix(data, config),
        flags=flags,
        drill_downs=drill_downs,
        has_transactions=data.has_transactions,
        has_last_year=data.has_last_year,
    )


def write_analysis_json(analysis: dict, outputs_dir: Path) -> Path:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    path = outputs_dir / f"analysis_{analysis['entity_code']}_{analysis['period']}.json"
    with open(path, "w") as f:
        json.dump(analysis, f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all in entities.csv)")
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--inbox-dir", default="inbox", type=Path)
    parser.add_argument("--outputs-dir", default="outputs", type=Path)
    args = parser.parse_args()

    try:
        config = load_config(args.config_dir)
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    entity_codes = args.entities.split(",") if args.entities else list(config.entities.keys())
    processed, skipped, total_flags = [], [], 0
    for entity_code in entity_codes:
        try:
            analysis = analyze_period(entity_code, args.period, config, args.inbox_dir)
        except PreprocessError as e:
            print(f"SKIPPED: {e}", file=sys.stderr)
            skipped.append(entity_code)
            continue
        path = write_analysis_json(analysis, args.outputs_dir)
        flag_count = len(analysis["flags"])
        total_flags += flag_count
        print(f"{entity_code}: wrote {path} ({flag_count} flag(s))")
        processed.append(entity_code)

    print(f"\n{len(processed)} entity(ies) processed, {len(skipped)} skipped, {total_flags} total flag(s) raised")
    sys.exit(1 if not processed else 0)


if __name__ == "__main__":
    main()
