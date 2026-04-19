import os

from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]

# Load variables from a project-root `.env` file if present. Real OS env vars
# always take precedence (override=False), so production deployments can still
# inject values via the platform's own secret manager without a file on disk.
load_dotenv(override=False)

ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]


def _normalize_db_url(raw: str) -> str:
    """Force psycopg3 driver for managed Postgres URLs.

    Hosting providers (Neon, Render, Heroku) hand out URLs as `postgres://`
    or `postgresql://`, which SQLAlchemy resolves to psycopg2 by default.
    We want psycopg v3 (the wheel we ship in requirements.txt), so rewrite
    the scheme explicitly. SQLite and other backends pass through untouched.
    """
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


DB_URL: str = _normalize_db_url(os.getenv("DATABASE_URL", ""))

GREEN_API_BASE_URL: str = os.getenv("GREEN_API_BASE_URL", "https://api.green-api.com").rstrip("/")
GREEN_API_ID_INSTANCE: str = os.getenv("GREEN_API_ID_INSTANCE", "")
GREEN_API_TOKEN_INSTANCE: str = os.getenv("GREEN_API_TOKEN_INSTANCE", "")
GREEN_API_WEBHOOK_TOKEN: str = os.getenv("GREEN_API_WEBHOOK_TOKEN", "")

WHATSAPP_ENABLED: bool = os.getenv("WHATSAPP_ENABLED", "false").strip().lower() == "true"


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


WHATSAPP_HTTP_TIMEOUT_SECONDS: float = _read_float("WHATSAPP_HTTP_TIMEOUT_SECONDS", 10.0)
