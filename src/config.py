"""Application settings loaded from .env via pydantic-settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="",
    )

    app_env: str = "development"
    log_level: str = "DEBUG"

    raw_dir: Path = ROOT_DIR / "data" / "raw"
    persist_dir: Path = ROOT_DIR / "data" / "chroma"
    collection_name: str = "documents"
    chunk_size: int = 800
    overlap: int = 100

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
