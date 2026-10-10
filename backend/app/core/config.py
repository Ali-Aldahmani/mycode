"""Settings, read from environment variables (or backend/.env)."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://trainer:trainer@localhost:5432/trainer"
    challenges_dir: Path = REPO_DIR / "challenges"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # v1 has a single seeded user; every row still carries a user_id.
    default_username: str = "me"


settings = Settings()
