# PROJECT_STATUS

## Current phase

**Phase 1: local core and database layer. Complete; waiting for approval.** Phase 2 has not been started.

## Completed work

- Project structure: `app/core`, `app/database`, `app/models`, `app/services`, `app/ui`, `tests`, `data`, `backups`, `config`, `docs`.
- SQLite schema v1 (`app/database/migrations/0001_initial.sql`) for Contacts, Activities, Follow-ups, Appointments, Goals and Production with every requested field. Each table also has `created_at` / `updated_at`.
- Versioned migrations (`PRAGMA user_version`). Each migration is atomic, and an existing database is backed up before migrating.
- Dataclass models (`app/models/entities.py`).
- Repositories with CRUD for all six entities, plus contact search (ignores case and Greek accents), timelines, due/overdue follow-ups, appointments by day and active goals.
- Services layer (CRM, planner, performance, maintenance). The UI and CLI use only this layer.
- Backup (SQLite online backup + integrity check) and restore (validates the file, keeps a safety copy of the replaced database).
- Fictional sample data (`python -m app seed`): example.com emails, 69000xxxxx phones.
- Minimal read-only local UI: Dashboard (today's appointments, due/overdue follow-ups, untouched leads) and Contacts (search, profile with timeline).
- CLI: `init`, `status`, `seed`, `backup`, `restore`, `serve`.
- `.gitignore` covers the virtual environment, `.env`, `config/settings.toml`, the database, backups and `.DS_Store`. No credentials exist in the code.
- README with architecture, macOS setup, dependencies, tests and how to run.

## Tests passed

`python -m pytest`: **36 passed** (Python 3.11, SQLite 3.45).

| File | Covers |
|------|--------|
| `test_database.py` | Database creation, schema version, idempotent migrations, models match tables, failed migration rolls back, Greek search folding |
| `test_crud.py` | Create/read/update/delete for all six entities, invalid values rejected, duplicate goals rejected, search |
| `test_persistence.py` | Data survives closing and reopening the database |
| `test_relationships.py` | Foreign keys enforced, contact timeline, cascade/unlink on delete, production blocks contact deletion, untouched leads |
| `test_backup.py` | Backup and restore to a clean location, restore over an existing DB with safety copy, invalid backups rejected |
| `test_app.py` | UI never imports `sqlite3`/`app.database`, sample data, today overview, UI pages and HTML escaping, CLI end to end |

## Known issues / limitations

- The UI is read-only. Creating and editing records goes through the service layer (tests, CLI seed). Forms arrive with Call Mode and the confirmation gate in Phase 3.
- Backups are verified but **not encrypted**. Planned for hardening (Phase 10). The backup folder can be moved with `JARVIS_BACKUP_DIR`.
- The audit log (spec section 15) is not implemented yet; it belongs with the confirmation gate (Phase 3).
- Restore must be run while the UI is stopped.
- Tested on Linux with Python 3.11. Nothing here is Linux-specific, but it has not been run on macOS yet.
- The conversion-rate denominators (spec section 6) must be defined before Phase 2 KPIs are built.

## Next step

Waiting for approval of Phase 1. Phase 2 would add the Dashboard + Goals + KPI engine, which first needs the conversion-rate definitions:
1. Does "successful contact" mean a call with outcome *reached*?
2. What is the base for contract conversion: first meetings, third meetings, or something else?
