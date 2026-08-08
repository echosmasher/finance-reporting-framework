# Regenerates docs/screenshots/demo.gif — the README's "the loop" GIF.
#
# Requires https://github.com/charmbracelet/vhs (`brew install vhs`) and
# PyYAML on the `python3` that ends up on PATH (`pip install -r
# requirements.txt`, same as the README's own Quickstart). Run from the
# repo root:
#
#   vhs docs/demo.tape
#
# Deterministic: every command below is the same read-only-input,
# byte-identical-output pipeline CI's regenerate-demo job already checks
# (skills/analysis/scripts/{validate_data,preprocess,analyze}.py +
# skills/dashboard/scripts/render_dashboard.py against the committed
# Example Hotels demo data) — re-running this should reproduce the same
# terminal output every time, modulo timing.

Output docs/screenshots/demo.gif

Set Shell "zsh"
Set FontSize 16
Set Width 1180
Set Height 640
Set Theme "OneHalfDark"
Set TypingSpeed 45ms
Set Padding 24
Set PlaybackSpeed 1.0

Hide
Type "clear"
Enter
Type "export PROMPT='%1~ %# '"
Enter
Type "clear"
Enter
Show

Type "ls examples/example-hotels/inbox/ | grep 02-2026"
Enter
Sleep 1800ms

Type "python3 skills/analysis/scripts/validate_data.py 02-2026 --config-dir examples/example-hotels/config --inbox-dir examples/example-hotels/inbox"
Enter
Sleep 1800ms

Type "python3 skills/analysis/scripts/preprocess.py 02-2026 --config-dir examples/example-hotels/config --inbox-dir examples/example-hotels/inbox --outputs-dir examples/example-hotels/outputs"
Enter
Sleep 1800ms

Type "python3 skills/analysis/scripts/analyze.py 02-2026 --config-dir examples/example-hotels/config --inbox-dir examples/example-hotels/inbox --outputs-dir examples/example-hotels/outputs"
Enter
Sleep 3000ms

Type "python3 skills/dashboard/scripts/render_dashboard.py 02-2026 --entities 001 --config-dir examples/example-hotels/config --outputs-dir examples/example-hotels/outputs"
Enter
Sleep 2500ms

# Deliberately not pressing Enter here -- this would launch a real browser
# window (outside the recorded terminal, so it wouldn't even show up in
# the GIF) as a side effect of recording. The typed-but-not-submitted
# command is the "about to open" beat; the README's screenshot table
# right below the GIF shows what actually opens.
Type "open examples/example-hotels/outputs/001-Dashboard_02-2026.html"
Sleep 2000ms
