#!/usr/bin/env python3
"""Validate inbox/ files against config/data-dictionary.md's contract
before any analysis runs on them (PLAN.md §6 step 2, §2 rule 5: fail
loudly and specifically, naming the file/row/column, never silently
produce a wrong number).

Importable: validate_period() returns a ValidationResult with no side
effects, used by preprocess.py (refuses to run on hard errors) and by
tests. Run directly for a human-readable report and a process exit code.
"""
import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from config_loader import EXPENSE_GROUPS, Config, ConfigError, load_config, load_data_conventions

PERIOD_RE = re.compile(r"^(0[1-9]|1[0-2])-(\d{4})$")

REQUIRED_FILE_TYPES = ["actuals", "budget"]
# "stats" is optional: a company whose KPIs are all pure P&L ratios
# (e.g. GOP %) has no need to supply operational data (rooms/FTE for
# Example Hotels) it doesn't have. Any KPI whose formula needs a stats
# field that isn't present is skipped, not hard-required — see
# preprocess.py's compute_kpis(). The stats file's own column names
# (rooms_available, fte_actual, ...) are still fixed by this engine,
# not derived from config — a real v1 limitation for a company whose
# operational-data KPIs don't fit that hotel-shaped schema (e.g. "units
# produced" instead of "rooms sold"); see data-dictionary.md.
OPTIONAL_FILE_TYPES = ["stats", "transactions"]

FILE_COLUMNS = {
    "actuals": ["entity_code", "period", "gl_account", "amount"],
    "budget": ["entity_code", "period", "gl_account", "amount"],
    "stats": ["entity_code", "period", "rooms_available", "rooms_sold_actual",
              "rooms_sold_budget", "fte_actual", "fte_budget"],
    "transactions": ["entity_code", "period", "date", "gl_account", "vendor",
                      "description", "department", "amount"],
}
NUMERIC_COLUMNS = {
    "actuals": ["amount"],
    "budget": ["amount"],
    "stats": ["rooms_available", "rooms_sold_actual", "rooms_sold_budget", "fte_actual", "fte_budget"],
    "transactions": ["amount"],
}


@dataclass
class ValidationResult:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    files_found: dict = field(default_factory=dict)   # entity_code -> {file_type: bool}

    @property
    def ok(self) -> bool:
        return not self.errors


def is_valid_period(period: str) -> bool:
    return bool(PERIOD_RE.match(period))


def unmapped_account_floor(config: Config, currency: str) -> float:
    return float(config.thresholds["unmapped_account_materiality_floor"][currency])


def amount_sign_ok(value: float, category_id, config: Config, sign_convention: str) -> bool:
    """actuals/budget/transactions "amount" column only — stats numeric
    columns (rooms_available, etc.) are operational counts, always
    checked as plain non-negative regardless of sign_convention, not
    routed through this function."""
    if sign_convention == "all_positive" or category_id is None:
        return value >= 0
    if sign_convention == "costs_negative":
        is_expense = config.category_to_group.get(category_id) in EXPENSE_GROUPS
        return value <= 0 if is_expense else value >= 0
    return True  # unrecognized convention: permissive rather than crashing


def validate_file(path: Path, file_type: str, entity_code: str, period: str,
                   config: Config, result: ValidationResult, conventions: dict):
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=conventions["delimiter"])
        expected = FILE_COLUMNS[file_type]
        if reader.fieldnames != expected:
            result.errors.append(
                f"{path.name}: expected columns {expected}, found {reader.fieldnames}"
            )
            return

        entity = config.entities.get(entity_code, {})
        currency = entity.get("currency")
        brand = entity.get("brand")
        is_pnl_file = file_type in ("actuals", "budget", "transactions")
        sign_convention = conventions["sign_convention"]

        for row_num, row in enumerate(reader, start=2):  # header is row 1
            if row["entity_code"] != entity_code:
                result.errors.append(
                    f"{path.name} row {row_num}: entity_code '{row['entity_code']}' "
                    f"does not match filename entity '{entity_code}'"
                )
            if row["period"] != period:
                result.errors.append(
                    f"{path.name} row {row_num}: period '{row['period']}' "
                    f"does not match filename period '{period}'"
                )

            category_id = config.account_to_category.get(row["gl_account"]) if is_pnl_file else None

            for col in NUMERIC_COLUMNS[file_type]:
                try:
                    value = float(row[col])
                except ValueError:
                    result.errors.append(
                        f"{path.name} row {row_num}, column '{col}': "
                        f"'{row[col]}' is not a number"
                    )
                    continue
                if col == "amount" and is_pnl_file:
                    if not amount_sign_ok(value, category_id, config, sign_convention):
                        result.errors.append(
                            f"{path.name} row {row_num}, column '{col}': "
                            f"{value} doesn't match data-dictionary.md's sign_convention "
                            f"'{sign_convention}' for category '{category_id}'"
                        )
                elif value < 0:
                    result.errors.append(
                        f"{path.name} row {row_num}, column '{col}': "
                        f"{value} is negative (must be non-negative)"
                    )

            if is_pnl_file:
                gl_account = row["gl_account"]
                if category_id is None:
                    amount = _safe_float(row.get("amount"))
                    floor = unmapped_account_floor(config, currency) if currency else None
                    message = (
                        f"{path.name} row {row_num}: gl_account '{gl_account}' "
                        f"is not in account-mapping.csv (amount {row.get('amount')})"
                    )
                    if floor is not None and amount is not None and amount >= floor:
                        result.errors.append(message)
                    else:
                        result.warnings.append(message)
                else:
                    allowed_brands = config.category_applies_to.get(category_id)
                    if allowed_brands and brand and brand not in allowed_brands:
                        result.warnings.append(
                            f"{path.name} row {row_num}: gl_account '{gl_account}' "
                            f"({category_id}) posted for {brand}-brand entity '{entity_code}', "
                            f"but pnl-structure.yaml scopes this category to {allowed_brands}"
                        )


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_period(period: str, entity_codes: list, config: Config, inbox_dir: Path) -> ValidationResult:
    result = ValidationResult()

    if not is_valid_period(period):
        result.errors.append(f"period '{period}' is not a valid MM-YYYY calendar month")
        return result

    conventions = load_data_conventions(config.config_dir)

    for entity_code in entity_codes:
        if entity_code not in config.entities:
            result.errors.append(f"entity_code '{entity_code}' is not in entities.csv")
            continue

        found = {}
        for file_type in REQUIRED_FILE_TYPES + OPTIONAL_FILE_TYPES:
            path = inbox_dir / f"{entity_code}_{file_type}_{period}.csv"
            found[file_type] = path.exists()
            if path.exists():
                validate_file(path, file_type, entity_code, period, config, result, conventions)
        result.files_found[entity_code] = found

        missing_required = [ft for ft in REQUIRED_FILE_TYPES if not found[ft]]
        if missing_required:
            result.errors.append(
                f"entity '{entity_code}', period '{period}': missing required file(s) "
                f"{[f'{entity_code}_{ft}_{period}.csv' for ft in missing_required]}"
            )

    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("period", help="MM-YYYY, e.g. 02-2026")
    parser.add_argument("--entities", help="comma-separated entity codes (default: all in entities.csv)")
    parser.add_argument("--config-dir", default="config", type=Path)
    parser.add_argument("--inbox-dir", default="inbox", type=Path)
    args = parser.parse_args()

    try:
        config = load_config(args.config_dir)
    except ConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    entity_codes = args.entities.split(",") if args.entities else list(config.entities.keys())
    result = validate_period(args.period, entity_codes, config, args.inbox_dir)

    for entity_code, found in result.files_found.items():
        found_types = [ft for ft, present in found.items() if present]
        missing_types = [ft for ft, present in found.items() if not present]
        print(f"{entity_code}: found {found_types}" + (f", missing {missing_types}" if missing_types else ""))

    for w in result.warnings:
        print(f"WARNING: {w}")
    for e in result.errors:
        print(f"ERROR: {e}", file=sys.stderr)

    print(f"\n{len(result.errors)} error(s), {len(result.warnings)} warning(s)")
    sys.exit(1 if not result.ok else 0)


if __name__ == "__main__":
    main()
