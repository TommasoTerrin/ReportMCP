"""
Router Chat — usa la API key ottenuta via OAuth per fare una richiesta
al modello configurato su OpenRouter.
"""
import httpx

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.config import get_settings
from app.db import get_current_api_key

router = APIRouter()


# ─── Modelli Pydantic ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Il messaggio da inviare al modello")
    model: Optional[str] = Field(
        default=None,
        description="Override del modello. Se omesso si usa quello in settings.",
    )


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatResponse(BaseModel):
    reply: str
    model_used: str
    usage: Optional[dict] = None


# ─── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/completions",
    response_model=ChatResponse,
    summary="Invia un messaggio al modello via OpenRouter",
)
async def chat_completion(
    body: ChatRequest,
    api_key: str = Depends(get_current_api_key),
):
    """
    Richiede l'header **Authorization: Bearer <api_key>** ottenuta tramite OAuth.

    Il frontend passa la chiave salvata in sessionStorage dopo il callback.
    """
    settings = get_settings()
    model = body.model or settings.test_model

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": body.message}
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.openrouter_api_base}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.app_base_url,
                "X-Title": settings.app_name,
            },
            timeout=30.0,
        )

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="API key non valida o scaduta")
    if resp.status_code == 402:
        raise HTTPException(status_code=402, detail="Credito insufficiente su OpenRouter")
    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail="Rate limit raggiunto su OpenRouter")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter ha risposto con status {resp.status_code}: {resp.text}",
        )

    data = resp.json()

    try:
        reply = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise HTTPException(status_code=502, detail="Risposta malformata da OpenRouter")

    return ChatResponse(
        reply=reply,
        model_used=data.get("model", model),
        usage=data.get("usage"),
    )