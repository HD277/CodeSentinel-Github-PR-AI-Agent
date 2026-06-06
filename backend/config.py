import os
from pathlib import Path


class Settings:
    """Centralized configuration loaded from environment variables."""

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")
    GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    # GitHub API
    GITHUB_API_BASE: str = "https://api.github.com"
    MAX_DIFF_SIZE: int = 50_000  # Max characters per diff to send to LLM
    MAX_FILES_PER_REVIEW: int = 20  # Skip reviews with too many files

    # LLM
    LLM_TIMEOUT: int = 60  # seconds
    LLM_MAX_RETRIES: int = 3

    # Database
    DB_PATH: str = str(Path(__file__).parent.parent / "data" / "reviews.db")

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
