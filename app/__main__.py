import argparse
import sys
from datetime import date

if sys.version_info < (3, 11):
    sys.exit("JARVIS needs Python 3.11 or newer (on macOS: brew install python@3.12).")

from app.core.config import load_settings  # noqa: E402
from app.core.errors import BackupError  # noqa: E402
from app.services import maintenance  # noqa: E402


def cmd_init(settings, args):
    version = maintenance.init_database(settings)
    print(f"Database ready at {settings.db_path} (schema v{version})")


def cmd_status(settings, args):
    version, counts = maintenance.database_summary(settings)
    print(f"Database: {settings.db_path}\nSchema version: {version}")
    for table, count in counts.items():
        print(f"  {table:<14}{count:>6}")


def cmd_seed(settings, args):
    counts = maintenance.load_sample_data(settings, date.today(), force=args.force)
    if counts is None:
        print("Database already has contacts; refusing to add sample data (use --force).", file=sys.stderr)
        return 1
    print("Sample data added: " + ", ".join(f"{k}={v}" for k, v in counts.items()))


def cmd_backup(settings, args):
    print(f"Backup written to {maintenance.create_backup(settings)}")


def cmd_restore(settings, args):
    try:
        safety = maintenance.restore_backup(settings, args.backup_file)
    except BackupError as exc:
        print(f"Restore aborted: {exc}", file=sys.stderr)
        return 1
    if safety:
        print(f"Previous database saved to {safety}")
    print(f"Restored {args.backup_file} to {settings.db_path}")


def cmd_serve(settings, args):
    from app.ui.server import make_server

    maintenance.init_database(settings)
    server = make_server(settings.db_path, settings.host, settings.port)
    print(f"JARVIS running at http://{settings.host}:{server.server_address[1]}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="JARVIS local assistant")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="create or migrate the local database")
    sub.add_parser("status", help="show schema version and row counts")
    seed_parser = sub.add_parser("seed", help="load fictional sample data")
    seed_parser.add_argument("--force", action="store_true", help="add sample data even if contacts exist")
    sub.add_parser("backup", help="write a verified backup of the database")
    restore_parser = sub.add_parser("restore", help="replace the database with a backup (stop the app first)")
    restore_parser.add_argument("backup_file")
    sub.add_parser("serve", help="start the local read-only UI (default)")
    args = parser.parse_args(argv)

    commands = {"init": cmd_init, "status": cmd_status, "seed": cmd_seed, "backup": cmd_backup,
                "restore": cmd_restore, "serve": cmd_serve}
    return commands[args.command or "serve"](load_settings(), args) or 0


if __name__ == "__main__":
    sys.exit(main())
