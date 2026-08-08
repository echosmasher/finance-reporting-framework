import json
from pathlib import Path

import pytest

from feedback_store import (
    FeedbackError,
    add_comment,
    apply_overrides_to_narrative,
    clear_narrative_override,
    comments_by_row,
    load_feedback,
    remove_comment,
    set_narrative_override,
    stale_overrides,
)

# Reuses tests/fixtures/config (entity T01) — the same tiny hand-crafted
# schema test_analyze.py uses. T01/01-2024 flags room_revenue, staff_cost,
# total_departmental_expense, departmental_profit, net_profit,
# revenue_per_available_room, and occupancy_rate (verified against
# analyze_period directly); other_revenue and admin_cost are ON TARGET
# and unflagged — used below to test the "no narrative to edit" rejection.

ANALYSIS = {
    "entity_code": "T01",
    "period": "01-2024",
    "pnl": [
        {"id": "room_revenue", "status": "INVESTIGATE"},
        {"id": "other_revenue", "status": "ON TARGET"},
        {"id": "staff_cost", "status": "NOTE"},
        {"id": "admin_cost", "status": "ON TARGET"},
    ],
    "kpis": [
        {"id": "occupancy_rate", "status": "NOTE"},
    ],
}

NARRATIVE = {
    "executive_summary": "Overall the month ran hot on room revenue.",
    "profitability_summary": "Departmental profit beat budget on strong occupancy.",
    "category_narratives": {
        "room_revenue": "Room revenue ran well ahead of budget on higher occupancy.",
        "staff_cost": "Staff cost crept up in line with the extra covers.",
    },
}


@pytest.fixture
def outputs_dir(tmp_path):
    d = tmp_path / "outputs"
    d.mkdir()
    (d / "analysis_T01_01-2024.json").write_text(json.dumps(ANALYSIS))
    (d / "narrative_T01_01-2024.json").write_text(json.dumps(NARRATIVE))
    return d


@pytest.fixture
def feedback_dir(tmp_path):
    return tmp_path / "feedback"


class TestComments:
    def test_add_comment_on_valid_row(self, outputs_dir, feedback_dir):
        comment = add_comment(feedback_dir, outputs_dir, "T01", "01-2024",
                               "admin_cost", "Confirmed, nothing unusual.", "A. Controller")
        assert comment["row_id"] == "admin_cost"
        assert comment["id"] == "c1"
        data = load_feedback(feedback_dir, "T01", "01-2024")
        assert data["comments"] == [comment]

    def test_add_comment_on_kpi_id(self, outputs_dir, feedback_dir):
        comment = add_comment(feedback_dir, outputs_dir, "T01", "01-2024",
                               "occupancy_rate", "Matches the events calendar.", "A. Controller")
        assert comment["row_id"] == "occupancy_rate"

    def test_add_comment_unknown_row_id_raises_and_writes_nothing(self, outputs_dir, feedback_dir):
        with pytest.raises(FeedbackError, match="not a P&L category, subtotal, or KPI id"):
            add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "not_a_real_id", "x", "A")
        assert not (feedback_dir / "feedback_T01_01-2024.json").exists()

    def test_add_comment_missing_analysis_json_raises(self, tmp_path, feedback_dir):
        empty_outputs = tmp_path / "empty-outputs"
        empty_outputs.mkdir()
        with pytest.raises(FeedbackError, match="analysis JSON"):
            add_comment(feedback_dir, empty_outputs, "T01", "01-2024", "room_revenue", "x", "A")

    def test_comment_ids_increment(self, outputs_dir, feedback_dir):
        add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "first", "A")
        c2 = add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "staff_cost", "second", "A")
        assert c2["id"] == "c2"

    def test_remove_comment(self, outputs_dir, feedback_dir):
        comment = add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "x", "A")
        assert remove_comment(feedback_dir, "T01", "01-2024", comment["id"]) is True
        assert load_feedback(feedback_dir, "T01", "01-2024")["comments"] == []

    def test_remove_unknown_comment_raises(self, outputs_dir, feedback_dir):
        add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "x", "A")
        with pytest.raises(FeedbackError, match="No comment"):
            remove_comment(feedback_dir, "T01", "01-2024", "c999")

    def test_comments_by_row_groups_in_insertion_order(self, outputs_dir, feedback_dir):
        add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "first", "A")
        add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "staff_cost", "second", "A")
        add_comment(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "third", "A")
        data = load_feedback(feedback_dir, "T01", "01-2024")
        grouped = comments_by_row(data)
        assert [c["text"] for c in grouped["room_revenue"]] == ["first", "third"]
        assert [c["text"] for c in grouped["staff_cost"]] == ["second"]


class TestNarrativeOverrides:
    def test_set_narrative_override_on_flagged_item(self, outputs_dir, feedback_dir):
        override = set_narrative_override(feedback_dir, outputs_dir, "T01", "01-2024",
                                            "room_revenue", "Edited note.", "A. Controller")
        assert override["text"] == "Edited note."
        assert override["supersedes"] == NARRATIVE["category_narratives"]["room_revenue"]

    def test_set_narrative_override_on_summary_key(self, outputs_dir, feedback_dir):
        override = set_narrative_override(feedback_dir, outputs_dir, "T01", "01-2024",
                                            "profitability_summary", "New summary.", "A. Controller")
        assert override["supersedes"] == NARRATIVE["profitability_summary"]

    def test_set_narrative_override_on_unflagged_id_raises(self, outputs_dir, feedback_dir):
        with pytest.raises(FeedbackError, match="no existing narrative to edit"):
            set_narrative_override(feedback_dir, outputs_dir, "T01", "01-2024",
                                     "admin_cost", "New text.", "A")

    def test_set_narrative_missing_narrative_json_raises(self, tmp_path, feedback_dir):
        outputs = tmp_path / "outputs-no-narrative"
        outputs.mkdir()
        (outputs / "analysis_T01_01-2024.json").write_text(json.dumps(ANALYSIS))
        with pytest.raises(FeedbackError, match="narrative JSON"):
            set_narrative_override(feedback_dir, outputs, "T01", "01-2024", "room_revenue", "x", "A")

    def test_suppress_sets_text_none(self, outputs_dir, feedback_dir):
        override = set_narrative_override(feedback_dir, outputs_dir, "T01", "01-2024",
                                            "staff_cost", None, "A. Controller")
        assert override["text"] is None
        assert override["supersedes"] == NARRATIVE["category_narratives"]["staff_cost"]

    def test_clear_narrative_override(self, outputs_dir, feedback_dir):
        set_narrative_override(feedback_dir, outputs_dir, "T01", "01-2024", "room_revenue", "x", "A")
        assert clear_narrative_override(feedback_dir, "T01", "01-2024", "room_revenue") is True
        assert load_feedback(feedback_dir, "T01", "01-2024")["narrative_overrides"] == {}

    def test_clear_unknown_override_raises(self, outputs_dir, feedback_dir):
        with pytest.raises(FeedbackError, match="No narrative override"):
            clear_narrative_override(feedback_dir, "T01", "01-2024", "room_revenue")


class TestApplyOverridesToNarrative:
    def test_no_overrides_returns_same_object(self):
        feedback = {"comments": [], "narrative_overrides": {}}
        result = apply_overrides_to_narrative(NARRATIVE, feedback)
        assert result is NARRATIVE

    def test_replacement_text_merges_in(self):
        feedback = {"narrative_overrides": {
            "room_revenue": {"text": "Replaced.", "supersedes": NARRATIVE["category_narratives"]["room_revenue"]}
        }}
        result = apply_overrides_to_narrative(NARRATIVE, feedback)
        assert result["category_narratives"]["room_revenue"] == "Replaced."
        # original untouched
        assert NARRATIVE["category_narratives"]["room_revenue"].startswith("Room revenue ran")
        # other entries unaffected
        assert result["category_narratives"]["staff_cost"] == NARRATIVE["category_narratives"]["staff_cost"]

    def test_suppression_removes_category_key(self):
        feedback = {"narrative_overrides": {
            "room_revenue": {"text": None, "supersedes": NARRATIVE["category_narratives"]["room_revenue"]}
        }}
        result = apply_overrides_to_narrative(NARRATIVE, feedback)
        assert "room_revenue" not in result["category_narratives"]

    def test_summary_key_replacement(self):
        feedback = {"narrative_overrides": {
            "profitability_summary": {"text": "New summary.", "supersedes": NARRATIVE["profitability_summary"]}
        }}
        result = apply_overrides_to_narrative(NARRATIVE, feedback)
        assert result["profitability_summary"] == "New summary."

    def test_summary_key_suppression_removes_key(self):
        feedback = {"narrative_overrides": {
            "executive_summary": {"text": None, "supersedes": NARRATIVE["executive_summary"]}
        }}
        result = apply_overrides_to_narrative(NARRATIVE, feedback)
        assert "executive_summary" not in result

    def test_handles_none_narrative(self):
        feedback = {"narrative_overrides": {
            "room_revenue": {"text": "x", "supersedes": ""}
        }}
        result = apply_overrides_to_narrative(None, feedback)
        assert result["category_narratives"]["room_revenue"] == "x"


class TestStaleOverrides:
    def test_no_overrides_not_stale(self):
        assert stale_overrides(NARRATIVE, {"narrative_overrides": {}}) == []

    def test_matching_supersedes_not_stale(self):
        feedback = {"narrative_overrides": {
            "room_revenue": {"text": "x", "supersedes": NARRATIVE["category_narratives"]["room_revenue"]}
        }}
        assert stale_overrides(NARRATIVE, feedback) == []

    def test_changed_narrative_is_stale(self):
        feedback = {"narrative_overrides": {
            "room_revenue": {"text": "x", "supersedes": "some old text that no longer matches"}
        }}
        assert stale_overrides(NARRATIVE, feedback) == ["room_revenue"]
