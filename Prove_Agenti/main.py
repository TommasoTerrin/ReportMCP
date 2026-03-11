# ENTRY POINT UVICORN

"""
OpenRouter OAuth PKCE - FastAPI Application
Entry point: avvia sia il frontend (static) che le API
"""
import uvicorn
from app.server import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3000,
        reload=True,
        log_level="info",
    )