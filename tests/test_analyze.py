from pathlib import Path

import pytest

from analyze import (
    STATUS_INVESTIGATE,
    STATUS_NOTE,
    STATUS_ON_TARGET,
    analyze_period,
    build_drill_down,
    classify_category,
    classify_kpi,
    is_favorable,
)
from config_loader import load_config

FIXTURES = Path(__file__).parent / "fixtures"
CONFIG_DIR = FIXTURES / "config"
INBOX_DIR = FIXTURES / "inbox"

EXAMPLE_HOTELS_CONFIG_DIR = Path(__file__).parent.parent / "examples" / "example-hotels" / "config"
EXAMPLE_HOTELS_INBOX_DIR = Path(__file__).parent.parent / "examples" / "example-hotels" / "inbox"


@pytest.fixture
def config():
    return load_config(CONFIG_DIR)


class TestClassifyCategory:
    def test_on_target_when_neither_threshold_breached(self, config):
        result = classify_category("other_revenue", act=2020.0, budget=2000.0, config=config, currency="USD")
        assert result["status"] == STATUS_ON_TARGET

    def test_note_when_only_pct_breached(self, config):
        # default pct=5%, absolute=1000. 6% over but only 300 diff.
        result = classify_category("staff_cost", act=5300.0, budget=5000.0, config=config, currency="USD")
        assert result["status"] == STATUS_NOTE
        assert result["diff_pct"] == pytest.approx(6.0)
        assert result["pct_breached"] is True
        assert result["absolute_breached"] is False

    def test_note_when_only_absolute_breached(self, config):
        # default pct=5%, absolute=1000. 4% under threshold but 1200 diff over it.
        result = classify_category("staff_cost", act=31200.0, budget=30000.0, config=config, currency="USD")
        assert result["status"] == STATUS_NOTE
        assert result["diff_pct"] == pytest.approx(4.0)
        assert result["pct_breached"] is False
        assert result["absolute_breached"] is True

    def test_investigate_when_both_breached(self, config):
        # room_revenue override: pct=2%, absolute=500.
        result = classify_category("room_revenue", act=10800.0, budget=10000.0, config=config, currency="USD")
        assert result["status"] == STATUS_INVESTIGATE
        assert result["pct_breached"] is True
        assert result["absolute_breached"] is True

    def test_zero_budget_nonzero_actual_is_a_breach(self, config):
        result = classify_category("admin_cost", act=500.0, budget=0.0, config=config, currency="USD")
        assert result["diff_pct"] is None
        assert result["status"] in (STATUS_NOTE, STATUS_INVESTIGATE)

    def test_zero_budget_zero_actual_is_on_target(self, config):
        result = classify_category("admin_cost", act=0.0, budget=0.0, config=config, currency="USD")
        assert result["status"] == STATUS_ON_TARGET

    def test_threshold_source_names_the_override_that_applied(self, config):
        result = classify_category("room_revenue", act=10800.0, budget=10000.0, config=config, currency="USD")
        assert result["threshold_source"] == "category_overrides.room_revenue"
        assert result["threshold_pct"] == 2.0
        assert result["threshold_absolute"] == 500

    def test_threshold_source_is_default_for_an_unlisted_category(self, config):
        result = classify_category("staff_cost", act=5300.0, budget=5000.0, config=config, currency="USD")
        assert result["threshold_source"] == "default"
        assert result["threshold_pct"] == 5.0
        assert result["threshold_absolute"] == 1000


class TestFavorability:
    def test_revenue_above_budget_is_favorable(self, config):
        assert is_favorable("room_revenue", diff=100.0, config=config) is True

    def test_revenue_below_budget_is_unfavorable(self, config):
        assert is_favorable("room_revenue", diff=-100.0, config=config) is False

    def test_expense_above_budget_is_unfavorable(self, config):
        assert is_favorable("staff_cost", diff=100.0, config=config) is False

    def test_expense_below_budget_is_favorable(self, config):
        assert is_favorable("staff_cost", diff=-100.0, config=config) is True

    def test_expense_like_subtotal_uses_same_rule_as_leaf_categories(self, config):
        assert is_favorable("total_departmental_expense", diff=100.0, config=config) is False
        assert is_favorable("net_profit", diff=100.0, config=config) is True

    def test_zero_diff_has_no_direction(self, config):
        assert is_favorable("room_revenue", diff=0.0, config=config) is None


class TestClassifyKpi:
    def test_percent_format_uses_percentage_point_deviation(self, config):
        # occupancy_rate is "percent" format -- notice_pp=3, investigate_pp=6.
        # |0.68-0.60|*100 = 8pp, over investigate_pp.
        result = classify_kpi("occupancy_rate", act=0.68, budget=0.60, kpi_format="percent", config=config)
        assert result["diff"] == pytest.approx(0.08)
        assert result["status"] == STATUS_INVESTIGATE

    def test_currency_format_uses_relative_pct_deviation(self, config):
        result = classify_kpi("revenue_per_available_room", act=108.0, budget=100.0, kpi_format="currency", config=config)
        assert result["status"] == STATUS_NOTE  # 8% is >= notice_pct(5) but < investigate_pct(10)

    def test_currency_format_investigate_tier(self, config):
        result = classify_kpi("revenue_per_available_room", act=115.0, budget=100.0, kpi_format="currency", config=config)
        assert result["status"] == STATUS_INVESTIGATE  # 15% >= investigate_pct(10)

    def test_threshold_fields_reflect_pp_kind(self, config):
        result = classify_kpi("occupancy_rate", act=0.68, budget=0.60, kpi_format="percent", config=config)
        assert result["threshold_kind"] == "pp"
        assert result["threshold_notice"] == 3.0
        assert result["threshold_investigate"] == 6.0
        assert result["threshold_source"] == "kpi_thresholds.occupancy_rate"
        assert result["threshold_deviation"] == pytest.approx(8.0)

    def test_threshold_fields_reflect_pct_kind(self, config):
        result = classify_kpi("revenue_per_available_room", act=108.0, budget=100.0, kpi_format="currency", config=config)
        assert result["threshold_kind"] == "pct"
        assert result["threshold_notice"] == 5.0
        assert result["threshold_investigate"] == 10.0
        assert result["threshold_source"] == "kpi_thresholds.revenue_per_available_room"
        assert result["threshold_deviation"] == pytest.approx(8.0)


class TestDrillDown:
    def test_groups_by_vendor_and_account(self, config):
        transactions = [
            {"gl_account": "3000", "vendor": "Acme Staffing", "amount": "300.00", "date": "2024-01-05"},
            {"gl_account": "3000", "vendor": "Acme Staffing", "amount": "50.00", "date": "2024-01-06"},
            {"gl_account": "4000", "vendor": "Other Vendor", "amount": "1000.00", "date": "2024-01-10"},
        ]
        result = build_drill_down("staff_cost", transactions, config)
        assert result["transaction_count"] == 2
        assert result["by_vendor"][0] == {"vendor": "Acme Staffing", "amount": 350.0}
        assert len(result["by_account"]) == 1
        assert result["by_account"][0]["amount"] == 350.0

    def test_returns_none_when_no_matching_transactions(self, config):
        assert build_drill_down("admin_cost", [], config) is None


class TestAnalyzePeriodEndToEnd:
    def test_shape_and_flags(self):
        config = load_config(CONFIG_DIR)
        analysis = analyze_period("T01", "01-2024", config, INBOX_DIR)
        assert analysis["entity_code"] == "T01"
        assert {"pnl", "kpis", "revenue_mix", "flags", "drill_downs"} <= set(analysis)
        room_revenue = next(e for e in analysis["pnl"] if e["id"] == "room_revenue")
        assert room_revenue["status"] == STATUS_INVESTIGATE
        assert room_revenue in analysis["flags"]

    def test_drill_down_present_for_flagged_category_with_transactions(self):
        config = load_config(CONFIG_DIR)
        analysis = analyze_period("T01", "01-2024", config, INBOX_DIR)
        assert "staff_cost" in analysis["drill_downs"]

    def test_json_serializable(self):
        import json
        config = load_config(CONFIG_DIR)
        analysis = analyze_period("T01", "01-2024", config, INBOX_DIR)
        json.dumps(analysis)  # raises if anything isn't JSON-safe (e.g. Infinity)


@pytest.mark.skipif(not EXAMPLE_HOTELS_CONFIG_DIR.exists(), reason="Example Hotels demo data not present")
class TestExampleHotelsPlantedStories:
    """PLAN.md Sec11 Phase 2 acceptance criterion: running /analysis on
    Example Hotels month 2 flags the planted energy and F&B stories, and
    does not flag the clean entity's core categories."""

    def setup_method(self):
        self.config = load_config(EXAMPLE_HOTELS_CONFIG_DIR)

    def test_oslo_february_utilities_flagged(self):
        analysis = analyze_period("001", "02-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        utilities = next(e for e in analysis["pnl"] if e["id"] == "utilities")
        assert utilities["status"] == STATUS_INVESTIGATE
        assert utilities["diff"] < 0  # the missing-invoice gap, not a catch-up spike

    def test_oslo_march_utilities_catchup_flagged(self):
        analysis = analyze_period("001", "03-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        utilities = next(e for e in analysis["pnl"] if e["id"] == "utilities")
        assert utilities["status"] == STATUS_INVESTIGATE
        assert utilities["diff"] > 0  # the catch-up spike

    def test_bergen_february_fb_cogs_flagged(self):
        analysis = analyze_period("002", "02-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        fb_cogs = next(e for e in analysis["pnl"] if e["id"] == "fb_cogs")
        assert fb_cogs["status"] == STATUS_INVESTIGATE

    def test_copenhagen_march_rooms_payroll_flagged(self):
        analysis = analyze_period("004", "03-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        rooms_payroll = next(e for e in analysis["pnl"] if e["id"] == "rooms_payroll")
        assert rooms_payroll["status"] == STATUS_INVESTIGATE

    def test_stockholm_core_categories_not_flagged_march(self):
        # March is Stockholm's quietest planted month (see README.md) --
        # its core revenue/departmental categories should be clean.
        analysis = analyze_period("003", "03-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        for category_id in ("rooms_revenue", "fb_revenue", "rooms_payroll", "fb_cogs"):
            entry = next(e for e in analysis["pnl"] if e["id"] == category_id)
            assert entry["status"] == STATUS_ON_TARGET, f"{category_id} unexpectedly flagged: {entry}"

    def test_stockholm_gop_beats_budget_every_month(self):
        for period in ("01-2026", "02-2026", "03-2026"):
            analysis = analyze_period("003", period, self.config, EXAMPLE_HOTELS_INBOX_DIR)
            gop = next(e for e in analysis["pnl"] if e["id"] == "gop")
            assert gop["diff"] > 0, f"Stockholm GOP not favorable in {period}: {gop}"

    def test_recomputed_subtotals_match_manual_cascade(self):
        # departmental_profit must equal total_revenue - total_departmental_expenses,
        # recomputed bottom-up -- never trusted from a source row (PLAN.md Sec6 step 3).
        analysis = analyze_period("001", "02-2026", self.config, EXAMPLE_HOTELS_INBOX_DIR)
        by_id = {e["id"]: e["act"] for e in analysis["pnl"]}
        assert by_id["departmental_profit"] == pytest.approx(by_id["total_revenue"] - by_id["total_departmental_expenses"])
        assert by_id["gop"] == pytest.approx(by_id["departmental_profit"] - by_id["total_undistributed_expenses"])
