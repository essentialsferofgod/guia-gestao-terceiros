"""Configuração por variáveis de ambiente, com leitura opcional do arquivo .env."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8000"))
DATABASE_PATH = _path("DATABASE_PATH", ROOT / "data" / "app.db")
MEDIA_DIR = _path("MEDIA_DIR", ROOT / "media")
DIST_DIR = _path("DIST_DIR", ROOT / "frontend" / "dist")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "168"))
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "14"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "300"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@2026")
SEED_ON_START = os.environ.get("SEED_ON_START", "true").lower() == "true"

VIDEO_DIR = MEDIA_DIR / "videos"
THUMB_DIR = MEDIA_DIR / "thumbs"
COOKIE_NAME = "gt_session"
MAX_PROFILES = 3
