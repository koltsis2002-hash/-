# JARVIS

Local-first productivity, CRM and assistant tool for a financial & insurance advisor.
Single user, runs entirely on your Mac, no cloud database, no paid APIs.

- Specification: [`docs/JARVIS_Master_Implementation_Plan_v1.docx`](docs/JARVIS_Master_Implementation_Plan_v1.docx)
- Progress: [`PROJECT_STATUS.md`](PROJECT_STATUS.md)

**Current scope: Phase 1 (local core and database).** No AI, voice, PDF search, Google, Maps or external APIs yet.

## Architecture

```
UI (app/ui)  ─┐
CLI (app/__main__.py) ─┴─>  Services (app/services)  ─>  Repositories (app/database)  ─>  SQLite (data/jarvis.db)
                               business logic            the only code that runs SQL
                                        │                           │
                                        └──── Models (app/models) ──┘   plain dataclasses shared by all layers
```

| Folder | Responsibility |
|--------|----------------|
| `app/core` | Settings (`config.py`), error types, time helpers. No database or UI code. |
| `app/models` | Dataclasses for Contact, Activity, FollowUp, Appointment, Goal, Production and their allowed values. |
| `app/database` | Connection setup, numbered SQL migrations, repositories (CRUD and queries), backup/restore. |
| `app/services` | Business operations used by the UI/CLI: CRM, planner, goals/production, maintenance, sample data. |
| `app/ui` | Local read-only web UI (Dashboard, Contacts). It imports services only; a test enforces this. |
| `data/` | The live database (git-ignored). |
| `backups/` | Database backups (git-ignored). |
| `config/` | `settings.example.toml`. Your own `settings.toml` is git-ignored. |
| `docs/` | Specification. |
| `tests/` | pytest suite; each test uses a temporary database, never `data/`. |

Key design choices (the simplest that stay maintainable):

- **Python standard library only at runtime.** `sqlite3` for storage, `http.server` for the local UI. Nothing to install to run the app.
- **No ORM.** SQL lives only in `app/database/repositories.py` and the migration files, and every value is passed as a query parameter.
- **Migrations:** `app/database/migrations/NNNN_name.sql` files applied in order. The applied version is stored in SQLite's `PRAGMA user_version`. Each migration runs in one transaction, and an existing database is backed up automatically before it is migrated.
- **Data integrity is enforced by the database itself:** foreign keys, CHECK constraints for statuses/types, and no negative values. Violations reach the services as `ValidationError`.
- **Relationships:** deleting a contact deletes its activities and follow-ups and unlinks its appointments. It is **refused** if the contact has production records.
- **Times** are stored as local ISO 8601 text (`2026-09-28T10:30`).
- **Search** ignores case and Greek accents (`γιωργο` finds `Γιώργος`).

## Setup (macOS)

JARVIS needs **Python 3.11 or newer**. The `python3` that ships with macOS is usually 3.9, so install a current one with [Homebrew](https://brew.sh):

```bash
brew install python@3.12
```

Then, from the project folder:

```bash
python3.12 -m venv .venv          # create the virtual environment (once)
source .venv/bin/activate         # activate it (every new terminal)
pip install -r requirements.txt   # installs pytest, the only dependency (tests only)
```

Optional: `cp config/settings.example.toml config/settings.toml` to change the database path, backup folder or port.

## Dependencies

- Runtime: none beyond the Python 3.11+ standard library.
- Development: `pytest` (in `requirements.txt`).

## Running the tests

```bash
python -m pytest            # all tests
python -m pytest -v         # one line per test
```

## Running the application

```bash
python -m app init          # create / migrate data/jarvis.db
python -m app seed          # load 30 fictional contacts with activity (refuses if contacts exist)
python -m app status        # schema version and row count per table
python -m app               # start the UI, then open http://127.0.0.1:8765
python -m app backup        # write a verified backup to backups/
python -m app restore backups/<file>.db   # restore (stop the UI first; the current DB is saved first)
```

The UI listens on `127.0.0.1` only, so it is not reachable from other machines.
