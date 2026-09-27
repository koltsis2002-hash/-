import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config" / "settings.toml"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    backup_dir: Path
    knowledge_dir: Path
    host: str
    port: int


def _resolve(path, base: Path) -> Path:
    path = Path(path).expanduser()
    return path if path.is_absolute() else base / path


def load_settings(env=None) -> Settings:
    env = os.environ if env is None else env
    config_file = Path(env.get("JARVIS_CONFIG", DEFAULT_CONFIG_FILE))
    values = tomllib.loads(config_file.read_text("utf-8")) if config_file.exists() else {}

    data_dir = _resolve(env.get("JARVIS_DATA_DIR", values.get("data_dir", "data")), PROJECT_ROOT)
    return Settings(
        data_dir=data_dir,
        db_path=_resolve(env.get("JARVIS_DB_PATH", values.get("db_path", "database/jarvis.db")), data_dir),
        backup_dir=_resolve(env.get("JARVIS_BACKUP_DIR", values.get("backup_dir", "backups")), data_dir),
        knowledge_dir=_resolve(values.get("knowledge_dir", "knowledge/products"), data_dir),
        host=env.get("JARVIS_HOST", values.get("host", "127.0.0.1")),
        port=int(env.get("JARVIS_PORT", values.get("port", 8765))),
    )
