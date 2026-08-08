---
description: Add reviewer comments to dashboard rows, or edit/remove the LLM-written narrative for a flagged item — after /dashboard has rendered, in plain language, re-rendering the dashboard when done.
argument-hint: "<what to add/change> [for <entity> [period]]"
---

# /feedback

Lets whoever is reviewing a rendered dashboard tell Claude Code things
like *"remove the note on F&B revenue"* or *"add a comment to Sales &
Marketing: we received a delayed invoice from XXX"*, and have the
dashboard reflect it. This is the reviewer talking to Claude Code, not
the dashboard talking to a server — nothing here makes the rendered
HTML itself write anywhere, so the Google Apps Script sandbox problem
in `docs/LESSONS_LEARNED.md` case study 1 never comes up. GM-facing
write-back from inside the deployed dashboard is a separate, explicitly
out-of-scope idea — see `ROADMAP.md`.

Everything you write goes through `skills/feedback/scripts/feedback_store.py`,
never a hand-edited JSON file — it's the thing that validates a row id
actually exists and keeps `feedback/feedback_{ENTITY}_{PERIOD}.json` well-formed.

## 0. Dependency check

Needs `outputs/analysis_{ENTITY}_{PERIOD}.json` to exist (same
requirement `/dashboard` has). If it's missing, tell the user to run
`/analysis` (and then `/dashboard`) first.

**Demo mode:** if the user asks to run this against the Example Hotels
demo, use `examples/example-hotels/outputs` and
`examples/example-hotels/feedback` instead of `outputs`/`feedback` in
every command below.

## 1. Resolve scope

If the user names an entity/period, use it. Otherwise, find the most
recently rendered dashboard (`ls -t outputs/*-Dashboard_*.html | head -1`)
and infer entity/period from its filename — that's almost always the one
they're looking at.

## 2. Read the two JSON files feedback is written against

```bash
cat outputs/analysis_{ENTITY}_{PERIOD}.json
cat outputs/narrative_{ENTITY}_{PERIOD}.json   # may not exist
```

You need these to resolve what the user means: `analysis` JSON's
`pnl[].id`/`.label` and `kpis[].id`/`.label` are every valid target for
a comment; `narrative.category_narratives` keys (plus
`profitability_summary`/`executive_summary`) are every valid target for
a narrative edit.

## 3. Parse the request into discrete edits

A single message can contain several edits ("remove the note on X and
add a comment to Y") — handle each independently. For each one, classify
it as one of:

- **A new comment.** A freeform note pinned to a row — a fact, context,
  or explanation the reviewer wants attached, in their own words. Works
  on any row (flagged or not).
- **A narrative edit.** Replacing the LLM-written explanation for a
  flagged item (or the profitability/executive summary) with different
  wording. Only valid where narrative text already exists.
- **A narrative removal.** "Remove the note on X" — same target as
  above, but suppressing rather than replacing.

If the request doesn't fit either — most commonly, asking to change a
**status** (ON TARGET/NOTE/INVESTIGATE) or a **number** — refuse it here
and say why: those are computed by `thresholds.yaml`/`analyze.py`
(`CLAUDE.md`'s Python-computes/Claude-interprets rule), not something a
comment can override. Point the user at `/setup` (to adjust a threshold)
or `/analysis` (if a number looks wrong because of bad input data)
instead. **Never work around this by writing the requested status or
number into a comment as if it were fact** — a comment is reviewer
commentary, not a replacement data source.

**Resolving what row the user means:** match their words against the
analysis JSON's `label` fields (case-insensitive, no need for an exact
string) to find the `id`. If more than one row is plausible, or the
match is a stretch, ask rather than guess. **Suppressing narrative is
never the same as hiding a flag** — "remove the note" clears the prose,
the flagged row and its status pill stay visible either way; if what the
user actually wants is for a row to stop being flagged at all, that's a
threshold question, not a feedback one — redirect as above.

## 4. Confirm, then write

Echo back your interpretation of every edit *before* writing anything —
"Utilities (`utilities`) — removing the narrative note. Sales &
Marketing (`sales_marketing`) — adding your comment: '...'" — one batch
confirmation covering everything in the request, not one per edit. Once
confirmed:

```bash
# new comment
python3 skills/feedback/scripts/feedback_store.py add-comment {ENTITY} {PERIOD} \
  --row-id {ID} --text "{TEXT}" --author "{name the user gave, or 'Reviewer' if none}"

# narrative edit
python3 skills/feedback/scripts/feedback_store.py set-narrative {ENTITY} {PERIOD} \
  --row-id {ID} --text "{NEW TEXT}" --author "{AUTHOR}"

# narrative removal
python3 skills/feedback/scripts/feedback_store.py suppress-narrative {ENTITY} {PERIOD} \
  --row-id {ID} --author "{AUTHOR}"

# undo a previous edit/removal, reverting to the original LLM text
python3 skills/feedback/scripts/feedback_store.py clear-narrative {ENTITY} {PERIOD} --row-id {ID}

# remove a previously added comment
python3 skills/feedback/scripts/feedback_store.py remove-comment {ENTITY} {PERIOD} --comment-id {ID}
```

Each command validates the row id and prints the resulting record (or a
specific `ERROR:` on stderr — read it, don't retry blindly; an unknown
row id usually means your label match in step 3 was wrong, not that the
row doesn't exist). `add-comment`/`set-narrative`/`suppress-narrative`
all require `--author`; ask the user for a name once per session if they
haven't given one rather than defaulting silently every time.

## 5. Re-render

```bash
python3 skills/dashboard/scripts/render_dashboard.py {PERIOD} --entities {ENTITY}
```

`render_dashboard.py` picks up `feedback/feedback_{ENTITY}_{PERIOD}.json`
automatically (default `--feedback-dir feedback`; demo mode needs
`--feedback-dir examples/example-hotels/feedback` alongside the other
demo paths). Comments render inline on their P&L row or KPI card,
attributed and dated, visually distinct from generated narrative. A
suppressed narrative shows who removed it and when, in place of the
original prose — never a bare, unexplained blank.

If `render_dashboard.py` prints a `WARNING: narrative override on
'{id}' ... was written against LLM text that has since changed` to
stderr, surface it to the user: it means `/analysis` was re-run since
this override was made, the override still applied, but the number or
explanation underneath it may no longer match what they edited.

## 6. Report

Point to the re-rendered `outputs/{ENTITY}-Dashboard_{PERIOD}.html` and
summarize what changed in a sentence or two. Don't repeat the full
comment/narrative text back — the dashboard is the deliverable.
