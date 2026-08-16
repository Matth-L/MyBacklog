# MyBacklog

*My backlog, locally, safely, anywhere.*

A local, [Backloggd](https://backloggd.com/)-style app for managing your video game backlog from
your existing Excel/CSV file — customizable dashboard, "Completed" / "Backlog" grids, notes,
markdown reviews, cover art, and export to `.xlsx`/`.csv` at any time. Your data always stays
yours.

**Free and open-source — nobody should have to pay for this.**

Works identically on **Windows** and **Linux** (it's a small local web app: a Python server + a
page that opens in your browser), and can also run via **Docker**.

## Quick start

**Windows/Linux (no Docker)** — requires [Python 3.10+](https://www.python.org/downloads/):

```bash
./my_backlog_linux.sh       # Linux/macOS
my_backlog_windows.bat      # Windows (double-click, or run from a terminal)
```

This creates a virtual environment, installs dependencies, starts the server, and opens
`http://127.0.0.1:5000` in your browser.

**Docker**:

```bash
docker compose up -d --build
```

Then open `http://localhost:5000`.

## Features

- **Import/export**: your `My_Backlog.xlsx` or 3 CSVs (Backlog/Reviews/Completed), preserving your
  original file's logic (year markers, ignored summary columns, bold/italic reviews converted to
  markdown). Export anytime to a formatted `.xlsx` or a CSV zip. Import another session at any
  time, or start empty.
- **Dashboard**: hours played, ratings, pace (avg hours/month, time to clear your backlog),
  longest/shortest/best/worst-rated game, yearly progress, monthly trend, rating distribution, DLC
  counts, and a **"My Year Review"** Wrapped-style annual summary.
- **Grids**: SteamGridDB-style covers, tile-size slider, filters (availability, year, DLC,
  abandoned), sort modes, year separators, and a **Random Pick** animation to decide what to play
  next.
- **Cover art**: search across Steam/RAWG/Giant Bomb/Wikipedia, or upload your own — either way, an
  interactive **Discord/GitHub-style editor** (crop, fill, stretch, drag, zoom) 
  Every fetched image is validated before being accepted.
- **HowLongToBeat**: fetch an estimated playtime on demand (Main/Main+Extra/Completionist), never
  automatically.
- **Sanitize Game Names**: suggests canonical titles (fixing abbreviations/incomplete names)
- **Backups**: triggered only by explicit actions (new game, edited review, import) — never a
  background timer. Each backup writes a timestamped `.xlsx` + `.csv` to `backup_backlog/`; the 3
  most recent of each are kept. Restorable from Settings.

## External services

Cover art search can query the following, only when you use it explicitly and only after you
consent:

- **Steam Store** — public search, no key needed.
- **RAWG.io** — free API key (optional, add it in Settings); skipped without one.
- **Giant Bomb** — free API key (optional, add it in Settings); skipped without one.
- **Wikipedia** — last-resort fallback if nothing else is found.

*Steam is a trademark of Valve Corporation. RAWG.io, Giant Bomb, and Wikipedia belong to their
respective owners. Fetched images/metadata belong to their owners; MyBacklog doesn't redistribute
them and has no commercial purpose — everything is stored locally, for your personal use only.*

## Where's my data?

- `data/backlog.db`, `data/covers/`, `data/config.json` — database, covers, settings (created next
  to `app.py`, or in `/app/data` with Docker).
- `cover_art/` — your own manually-dropped covers, at the project root.
- `backup_backlog/` — `.xlsx`/`.csv` backups, at the project root.

Nothing is sent anywhere except the cover-art lookups described above, and only when you trigger
them.

---

# For devs

## Stack

Flask (single process, no build step) + vanilla JS/HTML/CSS frontend + SQLite. No ORM, no
frontend framework, no bundler — `static/js/app.js` is loaded directly by the browser.

## Project layout

```
app.py                  Flask routes
backend/
  db.py                 SQLite connection, schema + migrations
  importer.py            Excel/CSV import, review-matching pipeline
  exporter.py            xlsx/csv export (incl. formula-injection neutralization)
  covers.py               Cover art search (Steam/RAWG/Giant Bomb/Wikipedia) + local cache
  sanitize.py            Canonical-name suggestion pipeline + hash-based cache
  sequel_guard.py         Shared "don't confuse Dark Souls II with III" guard
  duplicates.py          Backlog/Completed duplicate detection (computed live, never cached)
  hltb.py                howlongtobeatpy wrapper
  stats.py                Dashboard + Year Review aggregation
  backup.py / session.py Backup/restore, import-a-new-session-at-any-time
  applog.py               Curated terminal logging (no per-request access log spam)
  data/aliases_seed.json  Bundled canonical-name dictionary (seed for sanitize.py)
static/
  js/app.js               All frontend logic
  js/translations/        fr.js / en.js (add a locale by copying one + registering in index.js)
  css/style.css
tests/                     pytest, one file per backend module
```

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -q
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `BACKLOG_DATA_DIR` | `./data` | DB, covers, config.json |
| `BACKLOG_BACKUP_DIR` | `./backup_backlog` | Backup files |
| `BACKLOG_COVER_ART_DIR` | `./cover_art` | User-dropped covers |
| `BACKLOG_NO_BROWSER` | unset | Skip auto-opening a browser tab on startup |
| `PORT` | `5000` | Server port |

## Notable design decisions

- **Matching order** (reviews, cover art, name sanitization): exact local match → alias →
  normalized → fuzzy → external API, always local-first. A fuzzy/external suggestion is never
  auto-applied — it's surfaced for confirmation. `sequel_guard.py` penalizes/rejects candidates
  whose extracted sequel number (roman or arabic) disagrees, since plain text similarity can't
  tell *II* from *III* apart.
- **Offline-first**: `sanitize.py` folds confident external-API hits into a local
  `data/aliases_learned.json` cache, so the app gets faster and more offline-capable the more it's
  used. No external service is ever required for core functionality.
- **Security**: all SQL is parameterized; user-controlled text (titles/reviews/notes) is escaped
  via `escapeHtml()` before any `innerHTML` interpolation; exports neutralize Excel/CSV formula
  injection (leading `=`/`+`/`-`/`@` get a literal-text prefix); path-accepting endpoints reject
  traversal attempts; `defusedxml` is pinned explicitly for XXE protection in `openpyxl`;
  `MAX_CONTENT_LENGTH` caps request body size.
- **No background jobs**: backups, cover-art bulk-fill, and sanitize scans all run in a
  daemon thread on explicit user action, with a polled `/status` endpoint for progress — nothing
  runs on a timer.
