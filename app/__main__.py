import argparse
import sys
from datetime import date

from app.config import load_settings
from app.core.backup import BackupError, create_backup, restore_backup
from app.core.db import open_database, schema_version
from app.core.sample_data import seed
from app.crm.repository import ContactRepository


def cmd_init(settings, args):
    conn = open_database(settings)
    print(f"Database ready at {settings.db_path} (schema v{schema_version(conn)})")
    conn.close()


def cmd_seed(settings, args):
    conn = open_database(settings)
    try:
        if ContactRepository(conn).count() and not args.force:
            print("Database already has contacts; refusing to add sample data (use --force).", file=sys.stderr)
            return 1
        counts = seed(conn, date.today())
        print("Sample data added: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    finally:
        conn.close()


def cmd_backup(settings, args):
    conn = open_database(settings)
    try:
        print(f"Backup written to {create_backup(conn, settings.backup_dir)}")
    finally:
        conn.close()


def cmd_restore(settings, args):
    try:
        safety = restore_backup(args.backup_file, settings.db_path, backup_dir=settings.backup_dir)
    except BackupError as exc:
        print(f"Restore aborted: {exc}", file=sys.stderr)
        return 1
    if safety:
        print(f"Previous database saved to {safety}")
    print(f"Restored {args.backup_file} to {settings.db_path}")


def cmd_serve(settings, args):
    from app.ui.server import make_server

    open_database(settings).close()
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
    seed_parser = sub.add_parser("seed", help="load fictional sample data")
    seed_parser.add_argument("--force", action="store_true", help="add sample data even if contacts exist")
    sub.add_parser("backup", help="write a verified backup of the database")
    restore_parser = sub.add_parser("restore", help="replace the database with a backup (stop the app first)")
    restore_parser.add_argument("backup_file")
    sub.add_parser("serve", help="start the local UI (default)")
    args = parser.parse_args(argv)

    commands = {"init": cmd_init, "seed": cmd_seed, "backup": cmd_backup, "restore": cmd_restore, "serve": cmd_serve}
    return commands[args.command or "serve"](load_settings(), args) or 0


if __name__ == "__main__":
    sys.exit(main())
