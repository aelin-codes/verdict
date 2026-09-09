"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router


def create_app(allow_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(
        title="Verdict API",
        description="Lie detector for coding agents.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")
    return app


# Default application instance (used by `uvicorn verdict.api.app:app`)
app = create_app()
