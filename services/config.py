"""Configuration is server-side. No browser key inputs or secret logging."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    model: str
    database_url: str
    mode: str
    allowed_emails: tuple[str, ...]


def settings(secrets=None):
    load_dotenv(override=False)
    secrets = secrets or {}

    def get(key, default=""):
        return str(os.getenv(key) or secrets.get(key, default))

    result = Settings(
        get("OPENAI_API_KEY"),
        get("OPENAI_MODEL"),
        get("DATABASE_URL", "sqlite:///local_data/plans.db"),
        get("DEPLOYMENT_MODE", "local"),
        tuple(s.strip().casefold() for s in get("ALLOWED_EMAILS").split(",") if s.strip()),
    )
    if result.mode not in ("local", "shared"):
        raise ValueError("DEPLOYMENT_MODE must be local or shared")
    if result.mode == "shared":
        if not result.database_url.startswith("postgresql+psycopg://") or not result.allowed_emails:
            raise ValueError(
                "Shared mode requires durable PostgreSQL and an explicit ALLOWED_EMAILS allowlist"
            )
    return result
