"""FastAPI app — wires routes, CORS, scheduler, and the static dashboard."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.routes.leads import router as leads_router
from app.routes.outcomes import router as outcomes_router
from app.routes.analytics import router as analytics_router
from app.routes.config_api import router as config_router
from app.scheduler import start_scheduler, shutdown_scheduler
from app.settings import get_settings

logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    logger.info("Starting app (env=%s)", settings.app_env)
    if settings.app_env != "test":
        start_scheduler()
    yield
    if settings.app_env != "test":
        shutdown_scheduler()
    logger.info("App stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="TechGropse Lead Scoring API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    app.include_router(leads_router, prefix="/api")
    app.include_router(outcomes_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    app.include_router(config_router, prefix="/api")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/", include_in_schema=False)
        async def index():
            return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
