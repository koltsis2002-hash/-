# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

---

## Repository Status

JARVIS — Phase 1 (local core and database) implemented. See `PROJECT_STATUS.md` for the current phase, decisions and next step.

---

## Project Overview

- **What it does:** JARVIS, a local-first, single-user assistant for a financial & insurance advisor (CRM, planner, KPIs/goals, product knowledge, prospecting). The spec is `docs/JARVIS_Master_Implementation_Plan_v1.docx` and is the source of truth.
- **Primary language(s):** Python 3.11+
- **Key dependencies:** standard library only at runtime (sqlite3, http.server); pytest for tests
- **Core rule:** JARVIS proposes → user reviews → user confirms → system executes. Work one phase at a time and update `PROJECT_STATUS.md` at the end of each session.

---

## Repository Structure

```
/
├── CLAUDE.md             # This file — AI assistant guidance
├── PROJECT_STATUS.md     # Current phase, decisions, blockers, next step
├── app/                  # Application package (`python -m app`)
│   ├── core/             # Settings, errors, time helpers
│   ├── models/           # Dataclass entities
│   ├── database/         # Connection, migrations/*.sql, repositories (only SQL here), backup
│   ├── services/         # Business logic used by UI and CLI
│   └── ui/               # Local web UI — imports services only (enforced by tests/test_app.py)
├── config/               # settings.example.toml (settings.toml is git-ignored)
├── data/                 # Local DB — git-ignored
├── backups/              # Backups — git-ignored
├── docs/                 # Specification
└── tests/                # pytest suite
```

---

## Development Workflow

### Branching Strategy

- `main` — production-ready code; never push directly
- `claude/<description>-<id>` — AI-generated changes
- `feat/<description>` — human feature branches
- `fix/<description>` — bug fix branches

### Commit Messages

Use the imperative mood, present tense, and keep the subject line under 72 characters:

```
Add user authentication module
Fix null pointer in payment handler
Refactor data pipeline for clarity
```

Do **not** include AI session URLs, task IDs, or issue references in the subject line unless the project explicitly requires it.

### Pull Requests

- All changes land via PR; no direct pushes to `main`
- AI-authored PRs should be created as **drafts** for human review
- PR descriptions should explain *why*, not just *what* changed

### Testing

Tests live in `tests/` and use pytest with temporary databases (never the real `data/`). Run before committing:

```bash
python -m pytest
```

---

## Code Conventions

### General

- Prefer editing existing files over creating new ones
- Do not add error handling for impossible scenarios — trust internal guarantees
- Three similar lines of code is better than a premature abstraction
- No half-finished implementations; a complete, simple solution beats an elegant, incomplete one

### Comments

- Default to **no comments**
- Only add a comment when the *why* is non-obvious: a hidden constraint, a subtle invariant, or a workaround for a known external bug
- Never write comments that restate what well-named identifiers already say
- No multi-paragraph docstrings or multi-line comment blocks

### Security

- Never commit secrets, credentials, `.env` files, or API keys
- Validate input only at system boundaries (user input, external APIs)
- Avoid command injection, XSS, SQL injection, and OWASP Top 10 vulnerabilities
- Use parameterized queries; never interpolate user input into SQL or shell commands

### File Naming

`snake_case.py` modules; SQL migrations are `app/database/migrations/NNNN_description.sql` and are never edited once released — add a new one instead.

---

## Environment Setup

```bash
git clone https://github.com/koltsis2002-hash/-.git
cd -
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app init && python -m app seed   # fictional sample data
python -m app                              # http://127.0.0.1:8765
```

---

## Key Files & Entry Points

| File/Directory | Purpose |
|----------------|---------|
| `app/__main__.py` | CLI entry point: init, status, seed, backup, restore, serve |
| `app/core/config.py` | Settings from `config/settings.toml` + `JARVIS_*` env vars |
| `app/models/entities.py` | Dataclasses and allowed values for all entities |
| `app/database/connection.py` | Connection setup (foreign keys, Greek-aware search function) and migration runner |
| `app/database/repositories.py` | CRUD and queries; the only module that runs SQL |
| `app/database/backup.py` | Verified backup and restore |
| `app/services/context.py` | `Services.open(db_path)` — what the UI and CLI use |
| `app/ui/server.py` | Local UI: dashboard and contacts |
| `PROJECT_STATUS.md` | Where the project is and what comes next |

---

## AI Assistant Instructions

When working in this repository:

1. **Read this file first** before making changes
2. **Check the branch** — develop on the feature branch, never on `main`
3. **Prefer minimal changes** — do not refactor or clean up code outside the scope of the task
4. **No speculative features** — implement only what is explicitly requested
5. **Run tests** after every non-trivial change
6. **Update this file** if the codebase structure, conventions, or workflows change materially
7. **Create draft PRs** for all AI-authored changes; let a human merge

### Forbidden Actions

- Force-pushing to `main`
- Committing `.env` or credential files
- Skipping pre-commit hooks (`--no-verify`)
- Amending already-pushed commits
- Adding unused backward-compatibility shims or re-exports

---

## Updating This File

When the project evolves, update the relevant sections:

- Add the project overview once purpose and stack are decided
- Replace placeholder `TODO` blocks with real content
- Add language-specific linting/formatting commands
- Document any non-obvious architecture decisions
