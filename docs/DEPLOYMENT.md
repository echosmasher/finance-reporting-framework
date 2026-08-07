# Deployment

Three tiers for getting a dashboard in front of its audience, in order
of increasing infrastructure. `/dashboard` asks about your tools and
access at the end of each run and recommends one of these — this doc is
the full walkthrough for whichever tier you land on.

Every tier relies on the same property: a dashboard file
(`outputs/{ENTITY}-Dashboard_{PERIOD}.html`) is completely
self-contained — inline CSS, inline data, zero external requests. It
renders identically whether it's opened from disk, attached to an
email, or served from a URL.

## Tier 1 — File-based (default, zero infrastructure)

Email the HTML file as an attachment, or put it on a shared drive
everyone already has access to. That's it — no setup, no account, no
IT ticket. Because the file has no external dependencies, it opens
correctly offline, from any browser, on any device.

This is the right default for most controllers. Reach for tier 2 or 3
only when there's a specific reason a URL is better than a file (a
recurring audience that wants a bookmark instead of an email search, or
an existing internal portal to publish into).

## Tier 2 — Google Apps Script web app

For a company already on Google Workspace that wants dashboards
reachable by a stable URL instead of an email attachment each month.
Static serving only — see the caveat at the end of this section before
committing to this tier if you want anything interactive.

### Setup

1. **Create a Drive folder** to hold dashboard files, e.g.
   `Finance Reports/dashboards/`. Upload each month's
   `{ENTITY}-Dashboard_{PERIOD}.html` files there (manually, or scripted
   via `rclone`/the Drive API if you want to automate the upload step).

2. **Create an Apps Script project** attached to that folder (Drive →
   New → More → Google Apps Script, or script.google.com → New Project).

3. **Add this `Code.gs`**, adjusting `FOLDER_ID` to your folder's ID
   (visible in the folder's URL):

   ```javascript
   const FOLDER_ID = 'YOUR_FOLDER_ID_HERE';

   function doGet(e) {
     const entity = e.parameter.entity;
     const period = e.parameter.period;
     if (!entity || !period) {
       return HtmlService.createHtmlOutput('Missing entity or period parameter.');
     }

     const filename = entity + '-Dashboard_' + period + '.html';
     const folder = DriveApp.getFolderById(FOLDER_ID);
     const files = folder.getFilesByName(filename);

     if (!files.hasNext()) {
       return HtmlService.createHtmlOutput('Not found: ' + filename);
     }

     const html = files.next().getBlob().getDataAsString();
     return HtmlService.createHtmlOutput(html)
       .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
   }
   ```

4. **Deploy as a web app**: Deploy → New deployment → type "Web app" →
   execute as yourself, access to whoever should be able to view reports
   (your Workspace domain, or specific users — never "Anyone" for real
   financials). Copy the deployment URL.

5. **Share links** in the form `<deployment-url>?entity=001&period=02-2026`.
   Anyone with the right domain/user access can open that link directly.

### Access control

Apps Script web app access is set at deploy time (step 4). To change who
can view, create a new deployment version — updating an existing
deployment's code doesn't let you widen or narrow access without
redeploying. Review who has access periodically; it's easy to forget a
web app exists once the link is bookmarked.

### Caveat: static serving only

This tier serves the HTML file as-is — it cannot support anything that
writes data back (approval clicks, inline comments, editable fields).
The Apps Script `HtmlOutput` renders inside a **sandboxed iframe**, and
that sandbox blocks outbound requests to arbitrary hosts (including
`localhost` or any private network address) even when the request looks
like it should be same-origin. If you want interactive dashboards later,
see `docs/LESSONS_LEARNED.md` for why this happens and what the viable
alternatives are — don't try to work around the sandbox with this tier.

## Tier 3 — Static hosting (GitHub Pages, internal web server)

For an organization that already has a static host and allows
publishing to it — an internal web server, an intranet portal, or (for
public, non-financial use — see the warning below) GitHub Pages.

### GitHub Pages (used for this repo's own live demo)

1. Commit dashboard files to a `docs/` folder or a dedicated branch
   (this repo publishes `examples/example-hotels/outputs/` — see the CI
   workflow in `.github/workflows/`).
2. Repo Settings → Pages → set the source to that folder/branch.
3. Dashboards are then reachable at
   `https://<username>.github.io/<repo>/{ENTITY}-Dashboard_{PERIOD}.html`.

### Internal web server

Drop the HTML files into whatever directory your internal server
already serves static files from — no special configuration needed
beyond what any static file already requires, since there's no backend
logic, database, or build step involved.

### Warning: never publish real financials to a public host

GitHub Pages (and any other publicly-reachable static host) is fine for
**this repo's own demo** — Example Hotels is fictional, and the whole
point is a reviewer being able to see it without cloning the repo. It is
**not** fine for a real company's actual numbers. A public host has no
access control by default; anyone with the URL (or who finds it via a
search engine, a leaked link, or brute-forcing predictable filenames)
can see it. Use this tier for demos and genuinely internal servers only
— if there's any doubt about whether a "static host" is actually
private, treat it as public and use tier 1 or 2 instead.
