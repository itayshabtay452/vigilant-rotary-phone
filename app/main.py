from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]
from starlette.types import Scope  # pyright: ignore[reportMissingImports]

from app.database import Base, engine
from app.routers import vehicles, whatsapp
from app.settings import ALLOWED_ORIGINS


class NoCacheStatic(StaticFiles):
    """StaticFiles that forces revalidation on every request.

    `no-cache` lets browsers reuse the cached body but only after a 304
    check, so admins always pick up new `app.js` / `index.html` bytes
    without a manual hard-refresh.
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

_FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Garage Management API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.include_router(vehicles.router)
app.include_router(whatsapp.router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "Garage Management API"}


app.mount("/admin", NoCacheStatic(directory=str(_FRONTEND_DIR), html=True), name="admin")
