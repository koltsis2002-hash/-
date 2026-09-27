# PROJECT_STATUS

**Current phase:** Phase 0 + Phase 1 complete. Waiting for user confirmation before Phase 2 (Dashboard + Goals + KPI engine).

## Completed

- **Phase 0 (skeleton):** module/folder structure from the spec (section 18), `pyproject.toml`, `requirements.txt`,
  `.gitignore`, config strategy (`config/settings.example.toml` + env vars, no secrets in code), spec copied to `docs/`.
- **Phase 1 (local core):**
  - SQLite schema v1 (`app/core/migrations/0001_initial.sql`): contacts, activities, follow_ups, appointments, goals, production.
  - Migration runner using `PRAGMA user_version`. Each migration is atomic, and an existing database is backed up before migrating.
  - Repository layer with CRUD for all six entities, plus contact search, untouched leads, due/overdue follow-ups and appointments by day.
  - Backup (SQLite online backup API + integrity check) and restore (validates the file and keeps a safety copy of the replaced DB).
  - Fictional sample data generator (`python -m app seed`).
  - Minimal local UI: Dashboard shell (today's appointments, due/overdue follow-ups, untouched leads) and Contacts list/search/profile with timeline.
  - CLI: `init`, `seed`, `backup`, `restore`, `serve`.
  - 21 tests: CRUD, constraints, persistence after restart, migration rollback, backup/restore to a clean location, UI pages, CLI.

## Acceptance (Phase 1 exit criterion: "Database CRUD and restore tested")

`python -m pytest` → 21 passed. Manual: `python -m app init && python -m app seed && python -m app`, then open http://127.0.0.1:8765.

## Decisions

- **Python stdlib only at runtime** (sqlite3, http.server). No framework yet, so there is nothing to install to run the app.
- **UI is a local web page** served on 127.0.0.1. Desktop packaging comes in Phase 10.
- **Timestamps** are local-time ISO 8601 text (`YYYY-MM-DDTHH:MM`), so they compare correctly as strings. This is a single-user, single-timezone app.
- **Search** folds case and Greek accents (`Γιώργο` matches `γιωργος`) through a SQLite function registered in `connect()`.
- **Deletion rules:** deleting a contact cascades its activities and follow-ups, unlinks its appointments, and is refused if it has production records.
- `profession/company` from the spec is stored as `contacts.company`.
- KPI snapshots, business prospects, documents and document chunks get their tables in the migrations for the phases that use them (2, 7, 5).
- UI is read-only for now. Editing through the UI arrives with Call Mode and the confirmation gate (Phase 3).

## Open questions / blockers

- Conversion-rate denominators (spec section 6) must be fixed before Phase 2 KPIs are built. In particular: what is the "relevant opportunity base" for contract conversion?
- Backups are verified but **not encrypted** yet. Encryption and a user-chosen off-machine location are planned for Phase 10; set `JARVIS_BACKUP_DIR` to control the location now.
- The audit log (spec section 15) will be added together with the confirmation gate in Phase 3.

## Next step

Phase 2: KPI engine computed from stored events, goal cascade (annual → monthly → weekly → daily), dashboard KPI cards.
Needs the denominator definitions above first.
