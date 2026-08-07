#!/usr/bin/env python3
"""Generate 3 months of synthetic Example Hotels demo data.

Produces, per entity (see config/entities.csv) per period (01-2026,
02-2026, 03-2026), into inbox/:
  - {ENTITY}_actuals_{PERIOD}.csv       — GL account actuals
  - {ENTITY}_budget_{PERIOD}.csv        — GL account budget
  - {ENTITY}_stats_{PERIOD}.csv         — rooms/FTE data for KPIs
  - {ENTITY}_transactions_{PERIOD}.csv  — GL detail, expense accounts only

File shapes and conventions follow config/data-dictionary.md exactly.
Category economics (occupancy, ADR, expense ratios) are declared as
constants below; run parameters are seeded for reproducibility.

Deliberate design decisions (see tasks.md task 3/4 notes for the "why"):
  - Transactions are generated only for expense-side accounts (revenue is
    PMS-posted, not vendor-invoiced, in a real hotel — there's nothing to
    drill into on the revenue side) and never for depreciation/interest,
    which are system journal entries with no vendor.
  - January's Property & Liability Insurance and Administrative & General
    actuals include the one-off annual-premium / audit-fee lump sums
    described in config/company-profile.md and config/thresholds.yaml
    seasonality_notes, while their Budget stays flat month to month — so
    the deterministic engine will flag them, and the narrative pass is
    the one that recognizes them as expected (see investigation-guide.md).
  - Planted stories (energy missing-invoice gap, F&B COGS inventory
    adjustment, payroll-vs-occupancy deviation) are injected via
    STORY_ACCOUNT_SPLITS/STORY_TRANSACTIONS, which override the normal
    weighted GL-account split and vendor/description generation for just
    the affected accounts. See README.md for the full list and why each
    is there.
"""
import csv
import random
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
INBOX_DIR = BASE_DIR / "inbox"

RNG_SEED = 20260101

# Noise standard deviations. Kept deliberately small: each is applied at
# one level of the revenue/expense driver chain (e.g. a departmental
# expense's own noise stacks on top of its already-noisy revenue driver),
# so they compound. Sized so the compounded result mostly stays inside
# thresholds.yaml's 3-4% bands — most categories land ON TARGET most
# months, the way a real property's numbers mostly do, leaving the
# deliberate January insurance/admin_general seasonality and the four
# planted stories (task 4, STORY_ACCOUNT_SPLITS) as the standout signals
# rather than noise drowning them out.
OCCUPANCY_NOISE_SD = 0.015
ADR_NOISE_SD = 0.010
REVENUE_CATEGORY_NOISE_SD = 0.015
DEPARTMENTAL_EXPENSE_NOISE_SD = 0.020
FLAT_RATIO_NOISE_SD = 0.015
FTE_NOISE_SD = 0.015

PERIODS = ["01-2026", "02-2026", "03-2026"]
DAYS_IN_MONTH = {"01-2026": 31, "02-2026": 28, "03-2026": 31}

ENTITIES = {
    "001": dict(
        name="Example Hotel Oslo", currency="NOK", brand="Signature", rooms=240,
        adr_budget=1450.0,
        occupancy_budget={"01-2026": 0.60, "02-2026": 0.63, "03-2026": 0.68},
        fte_budget=145.0,
    ),
    "002": dict(
        name="Example Hotel Bergen", currency="NOK", brand="Signature", rooms=140,
        adr_budget=1250.0,
        occupancy_budget={"01-2026": 0.45, "02-2026": 0.48, "03-2026": 0.52},
        fte_budget=85.0,
    ),
    "003": dict(
        name="Example Hotel Stockholm", currency="SEK", brand="Compact", rooms=90,
        adr_budget=950.0,
        occupancy_budget={"01-2026": 0.55, "02-2026": 0.58, "03-2026": 0.62},
        fte_budget=40.0,
    ),
    "004": dict(
        name="Example Hotel Copenhagen", currency="DKK", brand="Signature", rooms=160,
        adr_budget=1100.0,
        occupancy_budget={"01-2026": 0.58, "02-2026": 0.70, "03-2026": 0.65},
        fte_budget=95.0,
    ),
}

# Revenue categories as a ratio of Rooms Revenue. Compact brand (Stockholm)
# has a reduced F&B ratio and no Spa & Wellness department (see
# pnl-structure.yaml applies_to_brands / entities.csv brand column).
REVENUE_RATIOS = {
    "Signature": {"fb_revenue": 0.45, "spa_revenue": 0.08, "other_ops_revenue": 0.05, "misc_income": 0.02},
    "Compact": {"fb_revenue": 0.15, "spa_revenue": 0.0, "other_ops_revenue": 0.04, "misc_income": 0.02},
}

# Departmental expense categories as a ratio of their own department's
# revenue category.
DEPARTMENTAL_EXPENSE_RATIOS = {
    "rooms_payroll": ("rooms_revenue", 0.18),
    "rooms_other_exp": ("rooms_revenue", 0.08),
    "fb_cogs": ("fb_revenue", 0.30),
    "fb_payroll": ("fb_revenue", 0.35),
    "fb_other_exp": ("fb_revenue", 0.10),
    "spa_payroll": ("spa_revenue", 0.30),
    "spa_other_exp": ("spa_revenue", 0.15),
    "other_ops_exp": ("other_ops_revenue", 0.40),
}

# Undistributed operating expenses + fixed charges + below-EBITDA, as a
# ratio of Total Revenue for the period.
FLAT_RATIOS_OF_TOTAL_REVENUE = {
    "admin_general": 0.08,
    "sales_marketing": 0.07,
    "property_ops_maint": 0.05,
    "utilities": 0.05,
    "it_systems": 0.02,
    "hr_training": 0.02,
    "security": 0.015,
    "management_fees": 0.03,
    "franchise_fees": 0.03,
    "insurance": 0.015,
    "property_tax": 0.01,
    "rent_lease": 0.02,
    "depreciation": 0.06,
    "interest_expense": 0.015,
}

REVENUE_CATEGORIES = ["rooms_revenue", "fb_revenue", "spa_revenue", "other_ops_revenue", "misc_income"]

# Categories that never generate transactions: revenue (PMS-posted, no
# vendor) and below-EBITDA system journal entries (no vendor).
NO_TRANSACTION_CATEGORIES = set(REVENUE_CATEGORIES) | {"depreciation", "interest_expense"}

DEPARTMENT_BY_CATEGORY = {
    "rooms_payroll": "Rooms", "rooms_other_exp": "Rooms",
    "fb_cogs": "F&B", "fb_payroll": "F&B", "fb_other_exp": "F&B",
    "spa_payroll": "Spa & Wellness", "spa_other_exp": "Spa & Wellness",
    "other_ops_exp": "Other Operated",
    "admin_general": "Administrative",
    "sales_marketing": "Sales & Marketing",
    "property_ops_maint": "Property Operations",
    "utilities": "Property Operations",
    "it_systems": "IT",
    "hr_training": "HR",
    "security": "Security",
    "management_fees": "Fixed Charges", "franchise_fees": "Fixed Charges",
    "insurance": "Fixed Charges", "property_tax": "Fixed Charges", "rent_lease": "Fixed Charges",
}

PAYROLL_CATEGORIES = {"rooms_payroll", "fb_payroll", "spa_payroll"}


def is_payroll_account(category_id, account_name):
    """A category being payroll-flavored (rooms/F&B/spa payroll) or an
    individual account name containing 'Salaries' (e.g. admin_general's
    "Finance & Accounting Salaries") both mean: no vendor invoice exists
    for this line, it's an internal payroll run."""
    return category_id in PAYROLL_CATEGORIES or "Salaries" in account_name

UTILITIES_VENDORS_BY_CURRENCY = {
    "NOK": ["Oslo Energi AS", "Bergen Kraft AS", "Nordic District Heating", "City Water Utility"],
    "SEK": ["Stockholm Energi AB", "Nordic District Heating", "City Water Utility"],
    "DKK": ["Copenhagen Varme A/S", "Nordic District Heating", "City Water Utility"],
}

VENDOR_POOLS = {
    "rooms_other_exp": ["Nordic Linen Services", "GuestSupply Nordic AB", "Reservation Systems Partners", "CleanPro Contract Services"],
    "fb_cogs": ["Nordic Food Distributors AS", "Fresh Fjord Seafood", "Baltic Beverage Supply", "Urban Produce Co"],
    "fb_other_exp": ["TableSet Supply Co", "Nordic Uniform & Linen", "Kitchen Equipment Services"],
    "spa_other_exp": ["Wellness Supply Nordic", "Spa Retail Distributors"],
    "other_ops_exp": ["ParkTech Systems", "Business Services Nordic"],
    "admin_general": ["Nordheim Legal Partners", "Baltic Audit & Assurance", "Office Plus Nordic", "Nordic Payments Processing"],
    "sales_marketing": ["Scandinavian Media Group", "BookingBridge OTA Services", "Nordic PR Partners", "Nordic Print & Signage"],
    "property_ops_maint": ["Nordic Facilities Services", "ElevateTech Elevator Co", "GreenScape Landscaping", "CoolFlow HVAC Services"],
    "it_systems": ["CloudHost Nordic", "PMS Systems AB", "TeleNordic Communications"],
    "hr_training": ["Nordic Recruitment Partners", "SkillUp Training Institute"],
    "security": ["SecureNordic Services"],
    "management_fees": ["Group Management Services"],
    "franchise_fees": ["Group Brand Licensing Corp"],
    "insurance": ["Nordic Property Insurers"],
    "property_tax": ["Municipal Tax Authority"],
    "rent_lease": ["Property Holdings Lease Co"],
}

DESCRIPTION_PREFIX_BY_CATEGORY = {
    "fb_cogs": "Food & beverage supply delivery",
    "utilities": "Monthly utility invoice",
    "admin_general": "Professional services invoice",
    "sales_marketing": "Marketing services invoice",
    "property_ops_maint": "Maintenance contract charge",
    "it_systems": "Systems & telecom invoice",
    "hr_training": "HR services invoice",
    "security": "Security services contract",
    "management_fees": "Management fee accrual",
    "franchise_fees": "Brand franchise fee accrual",
    "insurance": "Insurance premium",
    "property_tax": "Property tax / license fee",
    "rent_lease": "Lease payment",
}

# Planted stories — see README.md for the full narrative and why each one
# is there. Each entry replaces the normal weighted GL-account split
# (split_across_accounts) for one (entity, period, category) with a custom
# split that CONCENTRATES the deviation into the specific account(s) a real
# instance of that story would hit — e.g. a missing electricity invoice
# shows up entirely in the Electricity account, not spread evenly across
# every utilities account — so the transaction drill-down (grouped by
# vendor/account) tells the same story the P&L number does, not just a
# uniformly-scaled version of a normal month.
#
# Signature: fn(weights: dict[gl_account, float], budget_total: float)
#            -> dict[gl_account, float]
# `weights` are this category's normal account-split weights (see
# build_account_weights); `budget_total` is the category's Budget amount
# for this entity/period, used as the baseline every account (and the
# story's concentrated extra/missing amount) scales from.

def story_utilities_missing_invoice(weights, budget_total):
    """Oslo, February: the electricity invoice never arrives. Every other
    utility account posts normally; Electricity posts only a token
    estimated accrual, dragging the whole category well below Budget."""
    electricity = "6300"
    split = {acct: round(budget_total * w, 2) for acct, w in weights.items()}
    split[electricity] = round(budget_total * weights[electricity] * 0.05, 2)
    return split


def story_utilities_catchup_invoice(weights, budget_total):
    """Oslo, March: the missing February invoice arrives bundled with
    March's — Electricity alone carries ~2.6x its normal month (its own
    March usage plus February's backlog); every other account is normal."""
    electricity = "6300"
    split = {acct: round(budget_total * w, 2) for acct, w in weights.items()}
    split[electricity] = round(budget_total * weights[electricity] * 2.6, 2)
    return split


def story_fb_cogs_inventory_writeoff(weights, budget_total):
    """Bergen, February: normal cost of sales continues in every account;
    a physical inventory count finds obsolete/spoiled stock and books a
    40%-of-budget write-off entirely to F&B Inventory Adjustment."""
    adjustment_account = "5203"
    split = {acct: round(budget_total * w, 2) for acct, w in weights.items()}
    split[adjustment_account] = round(split[adjustment_account] + budget_total * 0.40, 2)
    return split


def story_rooms_payroll_overtime(weights, budget_total):
    """Copenhagen, March: Front Office/Housekeeping/Concierge salaries are
    normal; a staffing vacancy is covered with overtime and temporary
    labor, concentrated in those two accounts, adding 25% of budget on
    top — while occupancy (see stats file) stays within ~2% of its own
    Budget, so payroll and occupancy don't move together this month."""
    overtime, temp_labor = "5002", "5005"
    split = {acct: round(budget_total * w, 2) for acct, w in weights.items()}
    extra = budget_total * 0.25
    split[overtime] = round(split[overtime] + extra * 0.55, 2)
    split[temp_labor] = round(split[temp_labor] + extra * 0.45, 2)
    return split


STORY_ACCOUNT_SPLITS = {
    ("001", "02-2026", "utilities"): story_utilities_missing_invoice,
    ("001", "03-2026", "utilities"): story_utilities_catchup_invoice,
    ("002", "02-2026", "fb_cogs"): story_fb_cogs_inventory_writeoff,
    ("004", "03-2026", "rooms_payroll"): story_rooms_payroll_overtime,
}

# Narrative transaction lines for the story categories, replacing the
# generic auto-generated vendor/description pairing for just those
# accounts so the drill-down reads as a specific, investigable event
# rather than routine noise. (day, gl_account, vendor, description,
# amount_fraction_of_account_total) — fractions per account sum to 1.0.
STORY_TRANSACTIONS = {
    ("001", "02-2026", "utilities"): [
        (27, "6300", "Oslo Energi AS", "Estimated electricity accrual — invoice not yet received from supplier", 1.0),
    ],
    ("001", "03-2026", "utilities"): [
        (8, "6300", "Oslo Energi AS", "Electricity invoice — catch-up billing, includes unpaid February charges", 0.62),
        (8, "6300", "Oslo Energi AS", "Electricity invoice — March usage", 0.38),
    ],
    ("002", "02-2026", "fb_cogs"): [
        (24, "5203", "Internal Adjustment", "F&B inventory adjustment — obsolete and spoiled stock write-off following physical count", 1.0),
    ],
    ("004", "03-2026", "rooms_payroll"): [
        (16, "5002", "Internal Payroll", "Overtime — Front Office (covering extended staff leave)", 0.6),
        (16, "5002", "Internal Payroll", "Overtime — Housekeeping (covering extended staff leave)", 0.4),
        (18, "5005", "Nordic Staffing Partners", "Temporary housekeeping labor — staffing gap coverage", 1.0),
    ],
}


def load_account_mapping():
    accounts_by_category = {}
    account_names = {}
    with open(CONFIG_DIR / "account-mapping.csv", newline="") as f:
        for row in csv.DictReader(f):
            accounts_by_category.setdefault(row["category_id"], []).append(row["gl_account"])
            account_names[row["gl_account"]] = row["gl_account_name"]
    return accounts_by_category, account_names


def build_account_weights(accounts_by_category, rng):
    """Deterministic per-category split of a category total across its GL
    accounts. Same weights are reused for every entity/period — simpler,
    and realistic enough for a demo (the split is a property of the chart
    of accounts, not of any one month)."""
    weights = {}
    for category_id, accounts in accounts_by_category.items():
        raw = [rng.uniform(0.4, 1.0) for _ in accounts]
        total = sum(raw)
        weights[category_id] = {acct: w / total for acct, w in zip(accounts, raw)}
    return weights


def compute_period_economics(entity_code, entity, period, rng):
    """Returns (budget, actual, stats) for one entity/period, before
    STORY_OVERRIDES are applied."""
    days = DAYS_IN_MONTH[period]
    rooms_available = entity["rooms"] * days

    occ_budget = entity["occupancy_budget"][period]
    occ_actual = max(0.0, min(1.0, occ_budget * (1 + rng.gauss(0, OCCUPANCY_NOISE_SD))))
    adr_budget = entity["adr_budget"]
    adr_actual = adr_budget * (1 + rng.gauss(0, ADR_NOISE_SD))

    rooms_sold_budget = round(rooms_available * occ_budget)
    rooms_sold_actual = round(rooms_available * occ_actual)
    fte_actual = round(entity["fte_budget"] * (1 + rng.gauss(0, FTE_NOISE_SD)), 1)

    stats = dict(
        entity_code=entity_code, period=period,
        rooms_available=rooms_available,
        rooms_sold_actual=rooms_sold_actual, rooms_sold_budget=rooms_sold_budget,
        fte_actual=fte_actual, fte_budget=entity["fte_budget"],
    )

    budget, actual = {}, {}
    budget["rooms_revenue"] = rooms_sold_budget * adr_budget
    actual["rooms_revenue"] = rooms_sold_actual * adr_actual

    for category_id, ratio in REVENUE_RATIOS[entity["brand"]].items():
        budget[category_id] = budget["rooms_revenue"] * ratio
        actual[category_id] = max(0.0, actual["rooms_revenue"] * ratio * (1 + rng.gauss(0, REVENUE_CATEGORY_NOISE_SD)))

    total_revenue_budget = sum(budget[c] for c in REVENUE_CATEGORIES)
    total_revenue_actual = sum(actual[c] for c in REVENUE_CATEGORIES)

    for category_id, (driver, ratio) in DEPARTMENTAL_EXPENSE_RATIOS.items():
        budget[category_id] = budget[driver] * ratio
        actual[category_id] = max(0.0, actual[driver] * ratio * (1 + rng.gauss(0, DEPARTMENTAL_EXPENSE_NOISE_SD)))

    for category_id, ratio in FLAT_RATIOS_OF_TOTAL_REVENUE.items():
        budget[category_id] = total_revenue_budget * ratio
        if period == "01-2026" and category_id == "insurance":
            # Annual premium invoiced as a single January charge — Budget
            # stays flat (spread ratio), Actual carries the full year.
            actual[category_id] = total_revenue_actual * ratio * 12 * (1 + rng.gauss(0, FLAT_RATIO_NOISE_SD))
        elif period == "01-2026" and category_id == "admin_general":
            # Incremental external-audit-fee bump on top of the normal run rate.
            actual[category_id] = total_revenue_actual * ratio * 1.15 * (1 + rng.gauss(0, FLAT_RATIO_NOISE_SD))
        else:
            actual[category_id] = max(0.0, total_revenue_actual * ratio * (1 + rng.gauss(0, FLAT_RATIO_NOISE_SD)))

    return budget, actual, stats


def split_across_accounts(category_id, amount, accounts_by_category, weights):
    accounts = accounts_by_category.get(category_id, [])
    if not accounts or amount <= 0:
        return {}
    return {acct: round(amount * weights[category_id][acct], 2) for acct in accounts}


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def vendor_for(category_id, account_name, currency, rng):
    if is_payroll_account(category_id, account_name):
        return "Internal Payroll"
    if category_id == "utilities":
        return rng.choice(UTILITIES_VENDORS_BY_CURRENCY[currency])
    return rng.choice(VENDOR_POOLS[category_id])


def description_for(category_id, account_name):
    if is_payroll_account(category_id, account_name):
        return f"Payroll run — {account_name}"
    prefix = DESCRIPTION_PREFIX_BY_CATEGORY.get(category_id, "Invoice")
    return f"{prefix} — {account_name}"


def generate_transactions(entity_code, entity, period, account_amounts, account_names, rng):
    rows = []
    days = DAYS_IN_MONTH[period]
    for category_id, amounts_by_account in account_amounts.items():
        if category_id in NO_TRANSACTION_CATEGORIES:
            continue

        story_lines = STORY_TRANSACTIONS.get((entity_code, period, category_id), [])
        story_accounts = {gl_account for _, gl_account, *_ in story_lines}
        for day, gl_account, vendor, description, fraction in story_lines:
            total = amounts_by_account.get(gl_account, 0)
            if total <= 0:
                continue
            rows.append(dict(
                entity_code=entity_code,
                period=period,
                date=f"{period[3:]}-{period[:2]}-{day:02d}",
                gl_account=gl_account,
                vendor=vendor,
                description=description,
                department=DEPARTMENT_BY_CATEGORY[category_id],
                amount=round(total * fraction, 2),
            ))

        for gl_account, amount in amounts_by_account.items():
            if gl_account in story_accounts or amount <= 0:
                continue
            account_name = account_names[gl_account]
            k = 1 if is_payroll_account(category_id, account_name) else rng.randint(1, 3)
            line_amounts = [round(amount / k, 2) for _ in range(k)]
            line_amounts[-1] = round(amount - sum(line_amounts[:-1]), 2)
            for line_amount in line_amounts:
                if line_amount <= 0:
                    continue
                day = rng.randint(1, days)
                rows.append(dict(
                    entity_code=entity_code,
                    period=period,
                    date=f"{period[3:]}-{period[:2]}-{day:02d}",
                    gl_account=gl_account,
                    vendor=vendor_for(category_id, account_name, entity["currency"], rng),
                    description=description_for(category_id, account_name),
                    department=DEPARTMENT_BY_CATEGORY[category_id],
                    amount=line_amount,
                ))
    rows.sort(key=lambda r: r["date"])
    return rows


def main():
    rng = random.Random(RNG_SEED)
    accounts_by_category, account_names = load_account_mapping()
    weights = build_account_weights(accounts_by_category, rng)

    for entity_code, entity in ENTITIES.items():
        for period in PERIODS:
            budget, actual, stats = compute_period_economics(entity_code, entity, period, rng)

            budget_accounts = {c: split_across_accounts(c, amt, accounts_by_category, weights) for c, amt in budget.items()}
            actual_accounts = {}
            for category_id, amount in actual.items():
                story_split_fn = STORY_ACCOUNT_SPLITS.get((entity_code, period, category_id))
                if story_split_fn:
                    actual_accounts[category_id] = story_split_fn(weights[category_id], budget[category_id])
                else:
                    actual_accounts[category_id] = split_across_accounts(category_id, amount, accounts_by_category, weights)

            budget_rows = [
                dict(entity_code=entity_code, period=period, gl_account=acct, amount=amt)
                for accts in budget_accounts.values() for acct, amt in accts.items() if amt > 0
            ]
            actual_rows = [
                dict(entity_code=entity_code, period=period, gl_account=acct, amount=amt)
                for accts in actual_accounts.values() for acct, amt in accts.items() if amt > 0
            ]
            transaction_rows = generate_transactions(entity_code, entity, period, actual_accounts, account_names, rng)

            write_csv(INBOX_DIR / f"{entity_code}_budget_{period}.csv", ["entity_code", "period", "gl_account", "amount"], budget_rows)
            write_csv(INBOX_DIR / f"{entity_code}_actuals_{period}.csv", ["entity_code", "period", "gl_account", "amount"], actual_rows)
            write_csv(INBOX_DIR / f"{entity_code}_stats_{period}.csv",
                      ["entity_code", "period", "rooms_available", "rooms_sold_actual", "rooms_sold_budget", "fte_actual", "fte_budget"],
                      [stats])
            write_csv(INBOX_DIR / f"{entity_code}_transactions_{period}.csv",
                      ["entity_code", "period", "date", "gl_account", "vendor", "description", "department", "amount"],
                      transaction_rows)

    print(f"Generated {len(ENTITIES)} entities x {len(PERIODS)} periods into {INBOX_DIR}")


if __name__ == "__main__":
    main()
