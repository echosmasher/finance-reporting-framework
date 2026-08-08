#!/usr/bin/env python3
"""Store and apply post-render feedback: reader comments pinned to a P&L
row/KPI, and edits to the LLM-written narrative for a flagged item.

Deliberately narrow — this is the in-scope half of ROADMAP.md's
"Feedback / correction workflow" item: a person reviewing the rendered
dashboard tells Claude Code (via /feedback) what to add or change, never
a write-back request made *by* the served HTML itself. See
docs/LESSONS_LEARNED.md case study 1 for why that distinction matters:
nothing here ever needs the dashboard's own JavaScript to reach a
server, so the Google Apps Script sandbox problem that blocked the
GM-facing version of this feature never applies.

Feedback lives in its own top-level `feedback/` directory, not
`outputs/` — `outputs/` is treated as fully regenerable by /analysis and
/dashboard (PLAN.md §3); feedback is user-authored input, like
`config/`, and must survive a `rm -rf outputs/`.

This module never touches a number. It only ever writes/reads comment
text and narrative-override text; row-id validation checks that an id
*exists* in the analysis JSON, never what its value is. See CLAUDE.md's
Python-computes/Claude-interprets rule — the same split applies here:
Claude resolves what the user meant ("F&B Revenue" -> "fb_revenue") and
decides whether a request is a comment or a narrative edit; this module
only enforces the schema and writes the file.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SUMMARY_KEYS = {"executive_summary", "profitability_summary"}


class FeedbackError(Exception):
    """Raised for anything a caller should treat as a hard failure —
    an unknown row_id, a missing analysis JSON, a missing comment id.
    Callers (SKILL.md's instructions) surface the message verbatim."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def feedback_path(feedback_dir: Path, entity_code: str, period: str) -> Path:
    return Path(feedback_dir) / f"feedback_{entity_code}_{period}.json"


def _empty() -> dict:
    return {"comments": [], "narrative_overrides": {}}


def load_feedback(feedback_dir: Path, entity_code: str, period: str) -> dict:
    path = feedback_path(feedback_dir, entity_code, period)
    if not path.exists():
        return _empty()
    with open(path) as f:
        data = json.load(f)
    data.setdefault("comments", [])
    data.setdefault("narrative_overrides", {})
    return data


def save_feedback(feedback_dir: Path, entity_code: str, period: str, data: dict) -> Path:
    path = feedback_path(feedback_dir, entity_code, period)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return path


def _load_json(path: Path, what: str) -> dict:
    if not path.exists():
        raise FeedbackError(f"{what} not found at {path} — run /analysis first.")
    with open(path) as f:
        return json.load(f)


def valid_row_ids(analysis: dict) -> set:
    """Every id a comment or narrative override can be pinned to: every
    P&L category/subtotal and every KPI. Deliberately not narrower than
    that — a comment is allowed on an ON TARGET row (e.g. "confirmed,
    nothing to add"), only narrative overrides are restricted further
    (see valid_narrative_ids)."""
    return {e["id"] for e in analysis["pnl"]} | {k["id"] for k in analysis["kpis"]}


def valid_narrative_ids(analysis: dict, narrative: dict) -> set:
    """Narrative overrides only make sense where narrative prose already
    exists: a flagged item's category_narratives entry, or one of the
    two summary fields. Editing prose that was never written is a
    contradiction in terms — that's a comment (a new note), not an edit
    to an existing one."""
    narrative = narrative or {}
    ids = set((narrative.get("category_narratives") or {}).keys())
    ids |= {k for k in SUMMARY_KEYS if narrative.get(k)}
    return ids


def add_comment(feedback_dir: Path, outputs_dir: Path, entity_code: str, period: str,
                 row_id: str, text: str, author: str) -> dict:
    analysis = _load_json(Path(outputs_dir) / f"analysis_{entity_code}_{period}.json", "analysis JSON")
    valid = valid_row_ids(analysis)
    if row_id not in valid:
        raise FeedbackError(f"'{row_id}' is not a P&L category, subtotal, or KPI id for {entity_code}/{period}.")

    data = load_feedback(feedback_dir, entity_code, period)
    next_n = len(data["comments"]) + 1
    comment = {
        "id": f"c{next_n}",
        "row_id": row_id,
        "text": text,
        "author": author,
        "created_at": _now(),
    }
    data["comments"].append(comment)
    save_feedback(feedback_dir, entity_code, period, data)
    return comment


def remove_comment(feedback_dir: Path, entity_code: str, period: str, comment_id: str) -> bool:
    data = load_feedback(feedback_dir, entity_code, period)
    before = len(data["comments"])
    data["comments"] = [c for c in data["comments"] if c["id"] != comment_id]
    if len(data["comments"]) == before:
        raise FeedbackError(f"No comment '{comment_id}' found for {entity_code}/{period}.")
    save_feedback(feedback_dir, entity_code, period, data)
    return True


def _current_narrative_text(narrative: dict, row_id: str) -> str:
    narrative = narrative or {}
    if row_id in SUMMARY_KEYS:
        return narrative.get(row_id) or ""
    return (narrative.get("category_narratives") or {}).get(row_id) or ""


def set_narrative_override(feedback_dir: Path, outputs_dir: Path, entity_code: str, period: str,
                            row_id: str, text, author: str) -> dict:
    """text=None suppresses the narrative for row_id (the status pill and
    flagged row stay visible, just the prose is hidden); a string
    replaces it. `supersedes` captures the LLM text this was written
    against, so a later /analysis re-run that changes that text can be
    flagged as stale instead of silently applying an edit to prose that
    no longer exists."""
    narrative = _load_json(Path(outputs_dir) / f"narrative_{entity_code}_{period}.json", "narrative JSON")
    analysis = _load_json(Path(outputs_dir) / f"analysis_{entity_code}_{period}.json", "analysis JSON")
    valid = valid_narrative_ids(analysis, narrative)
    if row_id not in valid:
        raise FeedbackError(
            f"'{row_id}' has no existing narrative to edit for {entity_code}/{period} "
            "(only flagged items and the two summary fields have narrative text) — "
            "use add_comment instead if this is a new note, not an edit."
        )

    data = load_feedback(feedback_dir, entity_code, period)
    data["narrative_overrides"][row_id] = {
        "text": text,
        "supersedes": _current_narrative_text(narrative, row_id),
        "author": author,
        "created_at": _now(),
    }
    save_feedback(feedback_dir, entity_code, period, data)
    return data["narrative_overrides"][row_id]


def clear_narrative_override(feedback_dir: Path, entity_code: str, period: str, row_id: str) -> bool:
    data = load_feedback(feedback_dir, entity_code, period)
    if row_id not in data["narrative_overrides"]:
        raise FeedbackError(f"No narrative override on '{row_id}' for {entity_code}/{period}.")
    del data["narrative_overrides"][row_id]
    save_feedback(feedback_dir, entity_code, period, data)
    return True


def apply_overrides_to_narrative(narrative: dict, feedback: dict) -> dict:
    """Pure merge used by render_dashboard.py: returns a new narrative
    dict with feedback's narrative_overrides applied on top. Never
    mutates the input. A suppressed entry (text=None) is deleted from
    category_narratives entirely — render_deviation_highlights then
    falls back to its existing "no narrative" placeholder for that
    item, same as an item that was never narrated."""
    narrative = narrative or {}
    overrides = (feedback or {}).get("narrative_overrides") or {}
    if not overrides:
        return narrative

    merged = json.loads(json.dumps(narrative))  # deep copy, JSON-safe by construction
    category_narratives = merged.setdefault("category_narratives", {})
    for row_id, override in overrides.items():
        text = override.get("text")
        if row_id in SUMMARY_KEYS:
            if text is None:
                merged.pop(row_id, None)
            else:
                merged[row_id] = text
        else:
            if text is None:
                category_narratives.pop(row_id, None)
            else:
                category_narratives[row_id] = text
    return merged


def stale_overrides(narrative: dict, feedback: dict) -> list:
    """row_ids whose narrative_override was written against LLM text
    that no longer matches the current narrative JSON — a sign
    /analysis was re-run and the override may no longer apply cleanly.
    Non-fatal: render_dashboard.py warns, doesn't refuse to render."""
    overrides = (feedback or {}).get("narrative_overrides") or {}
    stale = []
    for row_id, override in overrides.items():
        if _current_narrative_text(narrative, row_id) != override.get("supersedes", ""):
            stale.append(row_id)
    return stale


def comments_by_row(feedback: dict) -> dict:
    """Groups feedback['comments'] by row_id, preserving insertion order —
    the shape render_dashboard.py's renderers want directly."""
    grouped = {}
    for c in (feedback or {}).get("comments", []):
        grouped.setdefault(c["row_id"], []).append(c)
    return grouped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback-dir", default="feedback", type=Path)
    parser.add_argument("--outputs-dir", default="outputs", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("add-comment", help="Pin a comment to a P&L row or KPI.")
    p.add_argument("entity_code")
    p.add_argument("period")
    p.add_argument("--row-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--author", required=True)

    p = sub.add_parser("remove-comment", help="Delete a comment by id.")
    p.add_argument("entity_code")
    p.add_argument("period")
    p.add_argument("--comment-id", required=True)

    p = sub.add_parser("set-narrative", help="Replace the narrative text for a flagged item or summary field.")
    p.add_argument("entity_code")
    p.add_argument("period")
    p.add_argument("--row-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--author", required=True)

    p = sub.add_parser("suppress-narrative", help="Hide the narrative text for a flagged item (status/row stay visible).")
    p.add_argument("entity_code")
    p.add_argument("period")
    p.add_argument("--row-id", required=True)
    p.add_argument("--author", required=True)

    p = sub.add_parser("clear-narrative", help="Remove a previously set/suppressed narrative override, reverting to the original LLM text.")
    p.add_argument("entity_code")
    p.add_argument("period")
    p.add_argument("--row-id", required=True)

    p = sub.add_parser("list", help="Print current feedback as JSON (for confirming before/after a change).")
    p.add_argument("entity_code")
    p.add_argument("period")

    args = parser.parse_args()

    try:
        if args.command == "add-comment":
            result = add_comment(args.feedback_dir, args.outputs_dir, args.entity_code, args.period,
                                  args.row_id, args.text, args.author)
        elif args.command == "remove-comment":
            result = {"removed": remove_comment(args.feedback_dir, args.entity_code, args.period, args.comment_id)}
        elif args.command == "set-narrative":
            result = set_narrative_override(args.feedback_dir, args.outputs_dir, args.entity_code, args.period,
                                              args.row_id, args.text, args.author)
        elif args.command == "suppress-narrative":
            result = set_narrative_override(args.feedback_dir, args.outputs_dir, args.entity_code, args.period,
                                              args.row_id, None, args.author)
        elif args.command == "clear-narrative":
            result = {"cleared": clear_narrative_override(args.feedback_dir, args.entity_code, args.period, args.row_id)}
        elif args.command == "list":
            result = load_feedback(args.feedback_dir, args.entity_code, args.period)
    except FeedbackError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
