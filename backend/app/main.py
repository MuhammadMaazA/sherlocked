"""Sherlocked API. Serves the built frontend when frontend/dist exists."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.routes import router
from app.config import database_path, frontend_dist, reasoning_provider_name, video_provider_name
from app.providers.base import ProviderError
from app.providers.mock import MockVideoProvider
from app.providers.reasoning import NullReasoner, WandbReasoner
from app.providers.vast import VastVideoProvider
from app.store import Store


def build_provider():
    name = video_provider_name()
    if name == "mock":
        return MockVideoProvider()
    if name == "vast":
        return VastVideoProvider()
    raise RuntimeError(f"Unknown VIDEO_PROVIDER '{name}'. Use vast or mock.")


def build_reasoner():
    if reasoning_provider_name() == "none":
        return NullReasoner()
    return WandbReasoner()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.provider.close()
        await app.state.reasoner.close()

    app = FastAPI(title="Sherlocked", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = Store(database_path())
    app.state.provider = build_provider()
    app.state.reasoner = build_reasoner()
    app.include_router(router, prefix="/api")

    @app.get("/health")
    def probe() -> dict[str, str]:
        return {"status": "ok"}

    @app.exception_handler(ProviderError)
    async def provider_error(_request, exc: ProviderError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "provider_error": True})

    dist = frontend_dist()
    if dist.is_dir():
        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(dist / "index.html")

        @app.get("/{full_path:path}")
        def spa(full_path: str):
            if full_path.startswith("api/") or full_path == "api":
                return JSONResponse({"detail": "Not found"}, status_code=404)
            root = dist.resolve()
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                return JSONResponse({"detail": "Not found"}, status_code=404)
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
