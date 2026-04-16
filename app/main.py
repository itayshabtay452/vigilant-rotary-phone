from fastapi import FastAPI  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]

from app.database import Base, engine
from app.routers import vehicles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Garage Management API", version="0.1.0")

app.include_router(vehicles.router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "Garage Management API"}


app.mount("/admin", StaticFiles(directory="frontend", html=True), name="admin")
