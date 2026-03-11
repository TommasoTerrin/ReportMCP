"""
Server factory: assembla l'app FastAPI con tutti i router e i file statici.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.routers import auth, chat


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="OpenRouter OAuth Demo",
        description="Demo di OAuth PKCE con OpenRouter e FastAPI",
        version="1.0.0",
    )

    # --- Session Middleware ---
    from starlette.middleware.sessions import SessionMiddleware
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    # --- API Routers ---
    app.include_router(auth.router, prefix="/api/auth", tags=["OAuth"])
    app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

    # --- Frontend statico ---
    static_dir = Path(__file__).parent.parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(static_dir / "index.html")

    @app.get("/callback", include_in_schema=False)
    async def serve_callback():
        """La callback OAuth viene gestita dal frontend (SPA)."""
        return FileResponse(static_dir / "index.html")

    return app