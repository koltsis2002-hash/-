# JARVIS

Local-first personal operating system for a financial & insurance advisor.
The authoritative specification is [`docs/JARVIS_Master_Implementation_Plan_v1.docx`](docs/JARVIS_Master_Implementation_Plan_v1.docx);
current progress lives in [`PROJECT_STATUS.md`](PROJECT_STATUS.md).

Core rule: **JARVIS proposes → user reviews → user confirms → system executes.**

## Requirements

- Python 3.11+ (the app itself uses only the standard library)
- `pytest` for the test suite

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional: copy `config/settings.example.toml` to `config/settings.toml` to change the data folder, backup folder or port.
Environment variables (`JARVIS_DATA_DIR`, `JARVIS_DB_PATH`, `JARVIS_BACKUP_DIR`, `JARVIS_HOST`, `JARVIS_PORT`) override the file.

## Usage

```bash
python -m app init                 # create / migrate data/database/jarvis.db
python -m app seed                 # load fictional sample data (refuses if contacts exist)
python -m app                      # start the local UI at http://127.0.0.1:8765
python -m app backup               # write a verified backup to data/backups/
python -m app restore <file.db>    # restore a backup (stop the app first; current DB is saved first)
```

## Tests

```bash
python -m pytest
```

## Layout

```
app/
  config.py          settings (file + environment)
  core/              database connection, migrations, backup/restore, base repository, sample data
  crm/               contacts and activities
  planner/           follow-ups, appointments, today's overview
  analytics/         goals and production
  ui/                local web UI (dashboard + contacts)
  knowledge/ prospecting/ voice/ integrations/   reserved for later phases
data/                local database, backups, product PDFs (git-ignored)
config/              settings example
tests/               pytest suite
docs/                specification
```
