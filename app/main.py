from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]

from app.database import Base, engine
from app.routers import vehicles, whatsapp
from app.settings import ALLOWED_ORIGINS

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


app.mount("/admin", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="admin")
