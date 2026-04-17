import os

ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]
DB_URL: str = os.getenv("DATABASE_URL", "")

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
