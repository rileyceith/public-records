from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import access_requests, attachments, audit, auth, lookups, records
from app.core.config import ALLOWED_ORIGINS, PUBLIC_MODE, STATIC_DIR
from app.database import engine, initialize_database
from app.schemas import HealthResponse


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield
    engine.dispose()


app = FastAPI(
    title="Public Records API",
    description="Search, manage, and audit public records and their supporting documents.",
    version="2.0.0",
    docs_url=None if PUBLIC_MODE else "/api/docs",
    redoc_url=None if PUBLIC_MODE else "/api/redoc",
    openapi_url=None if PUBLIC_MODE else "/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return HealthResponse()


app.include_router(auth.router, prefix="/api")
app.include_router(lookups.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(attachments.router, prefix="/api")
app.include_router(access_requests.router, prefix="/api")
app.include_router(audit.router, prefix="/api")

# Serves the built frontend from the same origin so a single tunnel exposes the whole app.
_static = Path(STATIC_DIR) if STATIC_DIR else None
if _static and (_static / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = (_static / path).resolve()
        if path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_static / "index.html")
