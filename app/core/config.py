import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config" / "settings.toml"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    backup_dir: Path
    host: str
    port: int


def _resolve(path) -> Path:
    path = Path(path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_settings(env=None) -> Settings:
    env = os.environ if env is None else env
    config_file = Path(env.get("JARVIS_CONFIG", DEFAULT_CONFIG_FILE))
    values = tomllib.loads(config_file.read_text("utf-8")) if config_file.exists() else {}
    return Settings(
        db_path=_resolve(env.get("JARVIS_DB_PATH", values.get("db_path", "data/jarvis.db"))),
        backup_dir=_resolve(env.get("JARVIS_BACKUP_DIR", values.get("backup_dir", "backups"))),
        host=env.get("JARVIS_HOST", values.get("host", "127.0.0.1")),
        port=int(env.get("JARVIS_PORT", values.get("port", 8765))),
    )
