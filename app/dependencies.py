import os

from fastapi import HTTPException, Security, status  # pyright: ignore[reportMissingImports]
from fastapi.security import APIKeyHeader  # pyright: ignore[reportMissingImports]

_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Security(_KEY_HEADER)) -> None:
    admin_key = os.getenv("ADMIN_API_KEY", "")
    if admin_key and key != admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
