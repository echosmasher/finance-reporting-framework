"""Load a company's config/ layer (PLAN.md §5.2). Shared by both the
/analysis and /dashboard skills — it lives under skills/analysis/scripts/
since that's where it was needed first, but skills/dashboard/scripts/
render_dashboard.py imports it too (see that file's sys.path setup).

Generic across companies: nothing here or in the callers references
Example Hotels or any other company by name — every company-specific
value comes from the config/ directory passed in. See CLAUDE.md's
engine/config separation rule.
"""
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED_CONFIG_FILES = [
    "company-profile.md",
    "entities.csv",
    "pnl-structure.yaml",
    "account-mapping.csv",
    "thresholds.yaml",
    "investigation-guide.md",
    "kpi-definitions.yaml",
    "data-dictionary.md",
    "brand.md",
]


class ConfigError(Exception):
    """Raised when config/ is missing or incomplete. Callers (SKILL.md's
    instructions) should catch this and point the user to /setup."""


@dataclass
class Config:
    config_dir: Path
    entities: dict          # entity_code -> {name, country, currency, brand, size, segment_notes}
    account_to_category: dict   # gl_account -> category_id
    account_names: dict         # gl_account -> gl_account_name
    category_to_group: dict     # category_id -> group (revenue/departmental_expense/...)
    category_labels: dict       # category_id -> label
    categories_by_group: dict   # group -> [category_id, ...], in pnl-structure.yaml order
    category_applies_to: dict   # category_id -> [entity attribute value, ...] or None (applies to all)
    subtotals: list             # [{id, label, formula, is_focus_metric?}, ...], in dependency order
    ratios: list                # [{id, label, formula}, ...]
    presentation_order: list    # category/subtotal ids, interleaved P&L row order
    terminology: dict
    thresholds: dict
    kpis: list
    kpi_thresholds: dict = field(default_factory=dict)


def check_required_files(config_dir: Path) -> list:
    """Returns the list of required files missing from config_dir (empty if complete)."""
    return [name for name in REQUIRED_CONFIG_FILES if not (config_dir / name).exists()]


def require_config(config_dir: Path):
    missing = check_required_files(config_dir)
    if missing:
        raise ConfigError(
            f"config/ at {config_dir} is missing required file(s): {', '.join(missing)}. "
            "Run /setup to generate the config layer before using /analysis or /dashboard."
        )


def load_config(config_dir: Path) -> Config:
    config_dir = Path(config_dir)
    require_config(config_dir)

    entities = {}
    with open(config_dir / "entities.csv", newline="") as f:
        for row in csv.DictReader(f):
            entities[row["entity_code"]] = row

    account_to_category = {}
    account_names = {}
    with open(config_dir / "account-mapping.csv", newline="") as f:
        for row in csv.DictReader(f):
            account_to_category[row["gl_account"]] = row["category_id"]
            account_names[row["gl_account"]] = row["gl_account_name"]

    with open(config_dir / "pnl-structure.yaml") as f:
        pnl = yaml.safe_load(f)

    category_to_group = {c["id"]: c["group"] for c in pnl["categories"]}
    category_labels = {c["id"]: c["label"] for c in pnl["categories"]}
    category_applies_to = {c["id"]: c.get("applies_to_brands") for c in pnl["categories"]}
    for s in pnl["subtotals"]:
        category_labels[s["id"]] = s["label"]

    categories_by_group = {}
    for c in pnl["categories"]:
        categories_by_group.setdefault(c["group"], []).append(c["id"])

    with open(config_dir / "thresholds.yaml") as f:
        thresholds = yaml.safe_load(f)

    with open(config_dir / "kpi-definitions.yaml") as f:
        kpi_doc = yaml.safe_load(f)

    return Config(
        config_dir=config_dir,
        entities=entities,
        account_to_category=account_to_category,
        account_names=account_names,
        category_to_group=category_to_group,
        category_labels=category_labels,
        categories_by_group=categories_by_group,
        category_applies_to=category_applies_to,
        subtotals=pnl["subtotals"],
        ratios=pnl["ratios"],
        presentation_order=pnl["presentation_order"],
        terminology=pnl["terminology"],
        thresholds=thresholds,
        kpis=kpi_doc["kpis"],
        kpi_thresholds=thresholds.get("kpi_thresholds", {}),
    )


BRAND_YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)


def load_brand(config_dir: Path) -> dict:
    """brand.md is a human-readable doc (tables + prose) for the /setup
    interview, with one fenced ```yaml block of the same tokens for
    render_dashboard.py to read. Returns that block parsed; raises
    ConfigError if brand.md has no such block (e.g. someone hand-edited
    it and deleted it — fail loudly rather than rendering with silently
    wrong colors)."""
    config_dir = Path(config_dir)
    brand_path = config_dir / "brand.md"
    text = brand_path.read_text()
    match = BRAND_YAML_BLOCK_RE.search(text)
    if not match:
        raise ConfigError(f"{brand_path} has no fenced ```yaml token block — see the demo's brand.md for the expected shape.")
    return yaml.safe_load(match.group(1))


def fail(message: str):
    """Hard-fail with a specific, actionable message (PLAN.md §2 rule 5:
    fail loudly and specifically, never silently produce a wrong number)."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)
