# Lessons Learned

Architectural findings from building this framework, written as short
case studies. Genericized — no employer- or project-identifying details
from any prior work.

## 1. Why the Google Apps Script iframe sandbox blocks interactive dashboards

**The temptation.** A static, self-contained dashboard (this framework's
tier 1/2 deployment) is easy to distribute but one-directional — the
audience can read it, not respond to it. The natural next step looks
simple: add a comment box or an "acknowledge" button, have it `fetch()`
a small endpoint to record the response, done.

**What actually happens.** Served through the Google Apps Script `Code.gs`
pattern in `docs/DEPLOYMENT.md`, the HTML renders inside a **sandboxed
iframe** Apps Script controls, not a normal top-level page. That sandbox
enforces its own restrictive policy on outbound requests — and critically,
it blocks requests to `localhost`, to private/internal network ranges,
and in practice to a wide swath of endpoints that would work fine from
an ordinary page. The failure mode is the worst kind: the request doesn't
error loudly, it just silently never completes, or fails with a
generic, unhelpful network error that gives no indication the sandbox is
the actual cause. A write-back that works perfectly in local development
(where nothing is sandboxed) can fail completely once actually deployed
through Apps Script, with no code change to explain why.

**Why this is easy to miss.** The failure only shows up at the exact
deployment tier this framework recommends for a company without its own
infrastructure — which is precisely the audience most likely to reach
for "just add a form" as the next feature, and least likely to have
budget to debug a sandboxing issue that doesn't reproduce locally.

**The viable alternatives**, in order of how much they change the
architecture:

1. **Don't fight the sandbox — use a native platform feature instead.**
   If the goal is "let the reader respond," a comment thread on the
   Drive file itself, or a linked Google Form, accomplishes the same
   goal without needing the dashboard's own JavaScript to make any
   request at all.
2. **Move off the sandboxed tier entirely.** If real interactivity is a
   requirement, not a nice-to-have, that's a signal the deployment tier
   itself needs to change — a genuinely served app (tier 3 territory,
   with a real backend) rather than a statically-served file dressed up
   to look interactive.
3. **Don't build the write-back path at all if the read-only version
   already serves the actual need.** The cheapest fix is recognizing
   the feature wasn't necessary — this framework's dashboards are
   monthly, reviewed, then acted on elsewhere (email, a meeting, the
   controller's own follow-up); the interactivity often isn't actually
   load-bearing once you ask what happens with the response after it's
   submitted.

This framework deliberately ships with none of the above built in for a
*reader submitting from inside the served dashboard* — see
`docs/ROADMAP.md` for that half of the feedback/comment workflow as an
explicit, still-deferred idea, not an oversight.

**Resolution, for the half of this that doesn't need any of the
above.** Alternative #1 above generalizes further than "use a native
platform feature": the write-back only has to happen somewhere that
isn't the sandboxed iframe — it doesn't have to be a platform feature
at all if the "somewhere" is a person with filesystem access instead of
the browser. The `/feedback` skill is exactly that: a reviewer (in
practice, the controller, not the GM reading the deployed dashboard)
tells Claude Code what to add or change, Claude Code edits
`feedback/feedback_{ENTITY}_{PERIOD}.json` locally and re-renders — no
`fetch()`, no server, so no sandbox to hit. This covers reviewer
comments and narrative edits/removals; it deliberately does not cover a
GM commenting directly from the dashboard they're viewing, which is
still exactly the problem described above and still unsolved for the
zero-infrastructure deployment tiers.

## 2. Why self-contained HTML over a served app

The obvious "better" architecture for a reporting tool is a real web
app: a backend, a database of historical reports, auth, a proper URL
per dashboard. This framework deliberately isn't that, for v1.

**The actual constraint isn't technical, it's organizational.** The
target user is a financial controller, not someone with a budget line
for hosting, a relationship with IT, or the authority to stand up a new
internal service. Every dependency this framework could add — a
database, a running server, an auth provider — is a dependency someone
else has to approve, provision, or maintain. A single HTML file has
none of those blockers: it can be emailed, and it renders. That's the
entire deployment story for the majority of realistic users, and it's
available on day one with zero infrastructure decisions.

**The tradeoff, made explicitly rather than accidentally.** This does
give up things a served app would have for free: no built-in history
browser, no access control finer than "whoever has the file/link," no
live data (each file is a point-in-time snapshot). `docs/DEPLOYMENT.md`'s
three tiers are the deliberate answer to "but what if I want more than
a file" — file-based by default, a served-but-static URL via Google
Apps Script if that's wanted, real static hosting if the organization
already has one. None of the three tiers require this framework itself
to run a server, which is the actual design invariant being protected.

**When this tradeoff should be revisited**: if a real deployment
consistently needs cross-period history in one place, or genuinely
needs interactivity (see case study 1), that's a signal the "no server"
constraint has stopped paying for itself for that specific user — not
evidence the constraint was wrong in general.

## 3. Why deterministic flagging is separated from LLM narrative

Every number a user of this framework sees — a P&L actual, a variance
percentage, a threshold breach — comes from plain, deterministic Python
(`skills/analysis/scripts/*.py`). An LLM never computes a number, only
writes prose about numbers Python already computed.

**Why not just have the model do both.** A capable model can parse a
CSV, compute a variance, and write a sentence about it, all in one pass
— and for a one-off it would probably get it right most of the time.
"Most of the time" is the problem: this is a monthly financial report a
controller signs their name to and a CFO or board reads as a factual
account of the business. A subtly wrong number that reads as authoritative
prose is far more dangerous than an obviously-wrong number, because
nothing about confident, well-written text signals "double-check this."
Determinism also means **reproducibility** — the same input data
produces the same numbers every time, which matters when a number gets
questioned three weeks later and someone needs to reconstruct exactly
how it was derived.

**What the split actually buys, concretely**: the Python layer is
unit-testable in the ordinary sense (`tests/test_analyze.py` asserts on
exact figures, not on "does this look reasonable") — a threshold-flagging
bug shows up as a failing test, not as an occasionally-wrong sentence
that's hard to even notice, let alone reproduce. The narrative layer,
in turn, is free to be genuinely good at what LLMs are actually good at:
adapting tone to an audience, recognizing that a flagged deviation
matches a known seasonal pattern, writing an investigation prompt that
reads like it came from someone who understands the business — all
without ever being in a position to quietly get a number wrong.

**The place this gets subtle**: the narrative layer still exercises
real judgment — e.g. recognizing that a "favorable" cost variance might
actually be a missing invoice, not a genuine saving (see
`config/investigation-guide.md`'s LOW-side checklists). That judgment
is exactly the kind of institutional-knowledge interpretation an LLM
should be doing. The discipline isn't "the model never reasons about
the numbers" — it's "the model never *produces* a number." Interpretation
is the LLM's job; arithmetic never is.
