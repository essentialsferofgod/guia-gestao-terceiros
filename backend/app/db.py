"""Acesso ao SQLite. Cada operação abre uma conexão curta, com chaves estrangeiras ativas."""
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import config

PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (user_id, name)
);
"""
PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS {name} (
  profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  video_id INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  position_seconds REAL NOT NULL DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0,
  first_watched_at TEXT NOT NULL,
  last_watched_at TEXT NOT NULL,
  PRIMARY KEY (profile_id, video_id)
);
"""
SAVED_PATHS_TABLE = """
CREATE TABLE IF NOT EXISTS {name} (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  situation TEXT NOT NULL,
  answers_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (profile_id, fingerprint)
);
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'subscriber' CHECK (role IN ('admin','subscriber')),
  plan TEXT NOT NULL DEFAULT 'trial' CHECK (plan IN ('trial','premium')),
  trial_ends_at TEXT,
  company TEXT NOT NULL DEFAULT '',
  job_title TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  offer_activated_at TEXT
);
""" + PROFILES_TABLE + """
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  slug TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
  access_level TEXT NOT NULL DEFAULT 'premium' CHECK (access_level IN ('intro','premium')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
  duration_seconds INTEGER NOT NULL DEFAULT 0,
  file_name TEXT,
  thumb_name TEXT,
  license_note TEXT NOT NULL DEFAULT '',
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
""" + PROGRESS_TABLE.format(name="progress") + SAVED_PATHS_TABLE.format(name="saved_paths") + """
CREATE INDEX IF NOT EXISTS idx_progress_profile ON progress(profile_id, last_watched_at DESC);
CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);
"""


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.isoformat()


def now_iso() -> str:
    return iso(now())


def days_from_now(days: int) -> str:
    return iso(now() + timedelta(days=days))


def hours_from_now(hours: int) -> str:
    return iso(now() + timedelta(hours=hours))


def unaccent(value) -> str:
    """Remove acentos e caixa para que 'documentacao' encontre 'Documentação'."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.create_function("unaccent", 1, unaccent, deterministic=True)
    return conn


@contextmanager
def transaction():
    conn = _connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def add_profile(conn, user_id: int, name: str) -> int | None:
    """Cria o perfil em um único comando, para que pedidos simultâneos não ultrapassem o limite."""
    cur = conn.execute(
        "INSERT INTO profiles (user_id,name,created_at) SELECT ?,?,? "
        "WHERE (SELECT COUNT(*) FROM profiles WHERE user_id = ?) < ?",
        (user_id, name, now_iso(), user_id, config.MAX_PROFILES),
    )
    return cur.lastrowid if cur.rowcount else None


def _columns(conn, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _migrate_to_profiles(conn) -> None:
    """Bancos anteriores aos perfis: cada conta ganha um perfil, que herda progresso e trilhas."""
    if "user_id" not in _columns(conn, "progress"):
        return
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(PROFILES_TABLE)
        conn.execute("INSERT INTO profiles (user_id,name,created_at) SELECT id,name,created_at FROM users")
        conn.execute("ALTER TABLE sessions ADD COLUMN profile_id INTEGER REFERENCES profiles(id) ON DELETE SET NULL")
        conn.execute("UPDATE sessions SET profile_id = (SELECT id FROM profiles WHERE user_id = sessions.user_id)")
        conn.execute(PROGRESS_TABLE.format(name="progress_new"))
        conn.execute(
            "INSERT INTO progress_new (profile_id,video_id,position_seconds,completed,first_watched_at,last_watched_at) "
            "SELECT f.id,p.video_id,p.position_seconds,p.completed,p.first_watched_at,p.last_watched_at "
            "FROM progress p JOIN profiles f ON f.user_id = p.user_id"
        )
        conn.execute("DROP TABLE progress")
        conn.execute("ALTER TABLE progress_new RENAME TO progress")
        conn.execute(SAVED_PATHS_TABLE.format(name="saved_paths_new"))
        conn.execute(
            "INSERT INTO saved_paths_new (id,profile_id,situation,answers_json,result_json,fingerprint,created_at) "
            "SELECT s.id,f.id,s.situation,s.answers_json,s.result_json,s.fingerprint,s.created_at "
            "FROM saved_paths s JOIN profiles f ON f.user_id = s.user_id"
        )
        conn.execute("DROP TABLE saved_paths")
        conn.execute("ALTER TABLE saved_paths_new RENAME TO saved_paths")


def _migrate_offer(conn) -> None:
    columns = _columns(conn, "users")
    if columns and "offer_activated_at" not in columns:
        with conn:
            conn.execute("ALTER TABLE users ADD COLUMN offer_activated_at TEXT")


def init_db() -> None:
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        _migrate_to_profiles(conn)
        _migrate_offer(conn)
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
