#!/usr/bin/env python3
"""Normalize one entity/period's actuals + Budget (+ Last Year, if the
company has it) into the standard intermediate shape PLAN.md §6 step 3
describes: Category; Act; Act %; <comparison>; <comparison> %; Diff; Diff
pp[; LY; LY %]. Subtotals are always recomputed bottom-up from leaf
category totals via pnl-structure.yaml — never read from a source file,
because there's nothing to read: data-dictionary.md's file shapes are
GL-account-level only, so any subtotal-shaped row would already be an
unmapped account (validate_data.py's job, not this script's).

Importable: preprocess_period() returns a PeriodData with the aggregated
category totals, computed subtotals/ratios/KPIs, and presentation-ready
rows — used by analyze.py and by tests. Refuses to run (raises
PreprocessError) if validate_data.py finds hard errors for that
entity/period.
"""
import argparse
import csv
import operator
import sys
from dataclasses import dataclass
from pathlib import Path

from config_loader import ConfigError, load_config
from validate_data import validate_period


class PreprocessError(Exception):
    """Raised when validation fails for an entity/period — the caller
    should skip that entity/period rather than compute on bad data."""


@dataclass
class PeriodData:
    entity_code: str
    period: str
    pnl_actual: dict        # category_id/subtotal_id -> amount
    pnl_budget: dict
    ratios_actual: dict     # ratio_id -> value
    ratios_budget: dict
    kpis: dict              # kpi_id -> {"actual": value, "budget": value}
    stats: dict
    rows: list               # presentation-ready P&L rows, in presentation_order
    has_transactions: bool
    has_last_year: bool


def eval_formula(formula: str, values: dict, config) -> float:
    """A tiny DSL: 'sum_group(GROUP)', 'A - B', or 'A / B' (division by
    zero returns 0.0 rather than raising — an entity with no revenue yet
    should show a blank ratio, not crash the run)."""
    formula = formula.strip()
    if formula.startswith("sum_group(") and formula.endswith(")"):
        group = formula[len("sum_group(") : -1].strip()
        return sum(values.get(cid, 0.0) for cid in config.categories_by_group.get(group, []))
    for op_str, fn in ((" - ", operator.sub), (" / ", operator.truediv)):
        if op_str in formula:
            left, right = (part.strip() for part in formula.split(op_str, 1))
            left_v, right_v = values[left], values[right]
            if fn is operator.truediv and right_v == 0:
                return 0.0
            return fn(left_v, right_v)
    raise ValueError(f"cannot evaluate formula: {formula!r}")


def load_account_amounts(path: Path) -> dict:
    amounts = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            amounts[row["gl_account"]] = amounts.get(row["gl_account"], 0.0) + float(row["amount"])
    return amounts


def aggregate_categories(account_amounts: dict, config) -> dict:
    """Sums leaf GL accounts into category totals. Every category id is
    present (defaulting to 0.0) so sum_group() and later formulas never
    KeyError on a category with no postings this period (e.g. Spa &
    Wellness for a Compact-brand entity)."""
    totals = {cid: 0.0 for cid in config.category_to_group}
    for gl_account, amount in account_amounts.items():
        category_id = config.account_to_category.get(gl_account)
        if category_id is not None:
            totals[category_id] += amount
    return totals


def compute_pnl(category_totals: dict, config) -> dict:
    values = dict(category_totals)
    for subtotal in config.subtotals:
        values[subtotal["id"]] = eval_formula(subtotal["formula"], values, config)
    return values


def compute_ratios(pnl_values: dict, config) -> dict:
    return {r["id"]: eval_formula(r["formula"], pnl_values, config) for r in config.ratios}


def compute_kpis(pnl_actual: dict, pnl_budget: dict, stats_row: dict, config) -> dict:
    """stats_row is {} when a company has no stats file (it's optional —
    see validate_data.py). A KPI whose formula needs a stats field that
    isn't present (e.g. "rooms_sold / rooms_available" with no stats
    file at all) is silently omitted from the result rather than
    crashing the run — a pure-P&L KPI like GOP % still computes fine."""
    kpis = {}
    values_actual = dict(pnl_actual)
    values_budget = dict(pnl_budget)
    if "rooms_sold_actual" in stats_row:
        values_actual["rooms_sold"] = float(stats_row["rooms_sold_actual"])
        values_budget["rooms_sold"] = float(stats_row["rooms_sold_budget"])
    if "rooms_available" in stats_row:
        values_actual["rooms_available"] = float(stats_row["rooms_available"])
        values_budget["rooms_available"] = float(stats_row["rooms_available"])
    if "fte_actual" in stats_row:
        values_actual["fte"] = float(stats_row["fte_actual"])
        values_budget["fte"] = float(stats_row["fte_budget"])

    for kpi in config.kpis:
        try:
            kpis[kpi["id"]] = {
                "actual": eval_formula(kpi["formula"], values_actual, config),
                "budget": eval_formula(kpi["formula"], values_budget, config),
            }
        except KeyError:
            continue
    return kpis


def build_rows(pnl_actual: dict, pnl_budget: dict, pnl_last_year: dict, config) -> list:
    total_revenue_actual = pnl_actual["total_revenue"]
    total_revenue_budget = pnl_budget["total_revenue"]
    total_revenue_ly = pnl_last_year.get("total_revenue") if pnl_last_year else None

    rows = []
    for item_id in config.presentation_order:
        act = pnl_actual.get(item_id, 0.0)
        fct = pnl_budget.get(item_id, 0.0)
        act_pct = (act / total_revenue_actual * 100) if total_revenue_actual else 0.0
        fct_pct = (fct / total_revenue_budget * 100) if total_revenue_budget else 0.0
        row = {
            "category_id": item_id,
            "category": config.category_labels[item_id],
            "act": round(act, 2),
            "act_pct": round(act_pct, 2),
            "comparison": round(fct, 2),
            "comparison_pct": round(fct_pct, 2),
            "diff": round(act - fct, 2),
            "diff_pp": round(act_pct - fct_pct, 2),
        }
        if pnl_last_year is not None:
            ly = pnl_last_year.get(item_id, 0.0)
            ly_pct = (ly / total_revenue_ly * 100) if total_revenue_ly else 0.0
            row["ly"] = round(ly, 2)
            row["ly_pct"] = round(ly_pct, 2)
        rows.append(row)
    return rows


def preprocess_period(entity_code: str, period: str, config, inbox_dir: Path) -> PeriodData:
    result = validate_period(period, [entity_code], config, inbox_dir)
    if not result.ok:
        raise PreprocessError(
            f"entity '{entity_code}', period '{period}': validation failed:\n"
            + "\n".join(f"  - {e}" for e in result.errors)
        )

    actual_accounts = load_account_amounts(inbox_dir / f"{entity_code}_actuals_{period}.csv")
    budget_accounts = load_account_amounts(inbox_dir / f"{entity_code}_budget_{period}.csv")
    pnl_actual = compute_pnl(aggregate_categories(actual_accounts, config), config)
    pnl_budget = compute_pnl(aggregate_categories(budget_accounts, config), config)

    pnl_last_year = None
    has_last_year = False
    if config.terminology.get("last_year_available"):
        ly_path = inbox_dir / f"{entity_code}_lastyear_{period}.csv"
        if ly_path.exists():
            pnl_last_year = compute_pnl(aggregate_categories(load_account_amounts(ly_path), config), config)
            has_last_year = True

    stats_path = inbox_dir / f"{entity_code}_stats_{period}.csv"
    stats_row = {}
    if stats_path.exists():
        with open(stats_path, newline="") as f:
            stats_row = next(csv.DictReader(f))

    return PeriodData(
        entity_code=entity_code,
        period=period,
        pnl_actual=pnl_actual,
        pnl_budget=pnl_budget,
        ratios_actual=compute_ratios(pnl_actual, config),
        ratios_budget=compute_ratios(pnl_budget, config),
        kpis=compute_kpis(pnl_actual, pnl_budget, stats_row, config),
        stats=stats_row,
        rows=build_rows(pnl_actual, pnl_budget, pnl_last_year, config),
        has_transactions=(inbox_dir / f"{entity_code}_transactions_{period}.csv").exists(),
        has_last_year=has_last_year,
    )


def write_intermediate_csv(data: PeriodData, config, outputs_dir: Path):
    comparison_label = config.terminology["comparison_label"]
    fieldnames = ["Category", "Act", "Act %", comparison_label, f"{comparison_label} %", "Diff", "Diff pp"]
    if data.has_last_year:
        fieldnames += ["LY", "LY %"]

    outputs_dir.mkdir(parents=True, exist_ok=True)
    path = outputs_dir / f"{data.entity_code}-Intermediate_{data.period}.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(fieldnames)
        for row in data.rows:
            line = [row["category"], row["act"], row["act_pct"], row["comparison"], row["comparison_pct"], row["diff"], row["diff_pp"]]
            if data.has_last_year:
                line += [row.get("ly", ""), row.get("ly_pct", "")]
            w.writerow(line)
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
    processed, skipped = [], []
    for entity_code in entity_codes:
        try:
            data = preprocess_period(entity_code, args.period, config, args.inbox_dir)
        except PreprocessError as e:
            print(f"SKIPPED: {e}", file=sys.stderr)
            skipped.append(entity_code)
            continue
        path = write_intermediate_csv(data, config, args.outputs_dir)
        print(f"{entity_code}: wrote {path}")
        processed.append(entity_code)

    print(f"\n{len(processed)} entity(ies) processed, {len(skipped)} skipped")
    sys.exit(1 if not processed else 0)


if __name__ == "__main__":
    main()
