from pathlib import Path

import pytest

from config_loader import load_config
from preprocess import (
    PreprocessError,
    aggregate_categories,
    compute_kpis,
    compute_pnl,
    compute_ratios,
    eval_formula,
    preprocess_period,
)

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG_DIR = FIXTURES / "config"
CONFIG_WITH_LY_DIR = FIXTURES / "config_with_ly"
INBOX_DIR = FIXTURES / "inbox"


@pytest.fixture
def config():
    return load_config(CONFIG_DIR)


def test_eval_formula_sum_group(config):
    values = {"room_revenue": 100.0, "other_revenue": 50.0}
    assert eval_formula("sum_group(revenue)", values, config) == 150.0


def test_eval_formula_subtraction(config):
    values = {"a": 100.0, "b": 40.0}
    assert eval_formula("a - b", values, config) == 60.0


def test_eval_formula_division(config):
    values = {"a": 50.0, "b": 200.0}
    assert eval_formula("a / b", values, config) == 0.25


def test_eval_formula_division_by_zero_returns_zero(config):
    values = {"a": 50.0, "b": 0.0}
    assert eval_formula("a / b", values, config) == 0.0


def test_eval_formula_unknown_shape_raises(config):
    with pytest.raises(ValueError):
        eval_formula("a * b", {"a": 1.0, "b": 2.0}, config)


def test_aggregate_categories_defaults_missing_to_zero(config):
    # supply_cost (4000) has no postings this period.
    totals = aggregate_categories({"1000": 500.0}, config)
    assert totals["room_revenue"] == 500.0
    assert totals["supply_cost"] == 0.0
    assert set(totals) == set(config.category_to_group)


def test_aggregate_categories_ignores_unmapped_accounts(config):
    totals = aggregate_categories({"1000": 500.0, "9999": 999.0}, config)
    assert totals["room_revenue"] == 500.0
    assert 999.0 not in totals.values()


def test_compute_pnl_subtotal_cascade(config):
    category_totals = {"room_revenue": 10000.0, "other_revenue": 2000.0,
                        "staff_cost": 5000.0, "supply_cost": 1000.0, "admin_cost": 1500.0}
    pnl = compute_pnl(category_totals, config)
    assert pnl["total_revenue"] == 12000.0
    assert pnl["total_departmental_expense"] == 6000.0
    assert pnl["departmental_profit"] == 6000.0
    assert pnl["total_undistributed_expense"] == 1500.0
    assert pnl["net_profit"] == 4500.0


def test_compute_ratios(config):
    pnl = {"net_profit": 4500.0, "total_revenue": 12000.0}
    ratios = compute_ratios(pnl, config)
    assert ratios["net_profit_pct"] == pytest.approx(0.375)


def test_compute_kpis_actual_and_budget_namespaces_dont_cross(config):
    pnl_actual = {"room_revenue": 10800.0}
    pnl_budget = {"room_revenue": 10000.0}
    stats_row = {"rooms_available": "100", "rooms_sold_actual": "80",
                 "rooms_sold_budget": "75", "fte_actual": "10.0", "fte_budget": "10.0"}
    kpis = compute_kpis(pnl_actual, pnl_budget, stats_row, config)
    assert kpis["revenue_per_available_room"]["actual"] == pytest.approx(108.0)
    assert kpis["revenue_per_available_room"]["budget"] == pytest.approx(100.0)


class TestPreprocessPeriodEndToEnd:
    def test_pnl_and_subtotals(self):
        config = load_config(CONFIG_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert data.pnl_actual["room_revenue"] == 10800.0
        assert data.pnl_actual["total_revenue"] == pytest.approx(12820.0)
        assert data.pnl_budget["total_revenue"] == pytest.approx(12000.0)
        assert data.pnl_actual["net_profit"] == pytest.approx(5070.0)
        assert data.pnl_budget["net_profit"] == pytest.approx(4500.0)

    def test_rows_are_in_presentation_order(self):
        config = load_config(CONFIG_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert [r["category_id"] for r in data.rows] == config.presentation_order

    def test_kpis_present(self):
        config = load_config(CONFIG_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert data.kpis["revenue_per_available_room"]["actual"] == pytest.approx(108.0)

    def test_has_transactions_true(self):
        config = load_config(CONFIG_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert data.has_transactions is True

    def test_no_last_year_when_not_configured(self):
        config = load_config(CONFIG_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert data.has_last_year is False
        assert "ly" not in data.rows[0]

    def test_last_year_included_when_configured_and_file_present(self):
        config = load_config(CONFIG_WITH_LY_DIR)
        data = preprocess_period("T01", "01-2024", config, INBOX_DIR)
        assert data.has_last_year is True
        room_revenue_row = next(r for r in data.rows if r["category_id"] == "room_revenue")
        assert room_revenue_row["ly"] == 9500.0

    def test_raises_on_missing_required_file(self, tmp_path):
        config = load_config(CONFIG_DIR)
        # An empty inbox dir has none of the required files for T01.
        with pytest.raises(PreprocessError):
            preprocess_period("T01", "01-2024", config, tmp_path)
