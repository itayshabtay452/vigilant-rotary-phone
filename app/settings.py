import os

ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]
DB_URL: str = os.getenv("DATABASE_URL", "")
