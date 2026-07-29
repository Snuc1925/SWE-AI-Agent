from __future__ import annotations

import os
from pathlib import Path

# ── Database ─────────────────────────────────────────────────────────────────
DEFAULT_POSTGRES_DSN = "postgresql://skill:skill@postgres:5432/skills"
_SHARED_DIR = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = str(_SHARED_DIR / "skills.db")
# DEFAULT_SQLITE_PATH = "/data/skills.db"


def get_database_url() -> str:
    """Return the DB connection URL.

    Priority:
      1. SKILL_DB_URL (full DSN, any dialect)
      2. POSTGRES_DSN  (alias, postgres-specific)
      3. SKILL_DB_PATH (sqlite fallback)
    """
    url = os.getenv("SKILL_DB_URL") or os.getenv("POSTGRES_DSN")
    if url:
        return url
    db_path = os.getenv("SKILL_DB_PATH", DEFAULT_SQLITE_PATH)
    if db_path.startswith("sqlite:///"):
        return db_path
    return f"sqlite:///{db_path}"


# ── Skill library ─────────────────────────────────────────────────────────────
_DEFAULT_SKILLS_DIR = (
    Path(__file__).resolve().parents[2]
    / "skill-library"
)


def get_skills_dir() -> Path:
    """Return the directory where SKILL.md files live."""
    env = os.getenv("SKILLS_DIR")
    if env:
        return Path(env)
    return _DEFAULT_SKILLS_DIR
