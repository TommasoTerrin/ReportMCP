"""
Router OAuth PKCE per OpenRouter.

Flusso:
  1. GET  /api/auth/login-url  → genera code_verifier/challenge, restituisce l'URL di redirect
  2. POST /api/auth/callback   → riceve il ?code= e lo scambia per la API key
  3. GET  /api/auth/me         → info sull'utente autenticato (opzionale, debug)
"""
import hashlib
import os
import base64
import httpx

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional

from app.config import get_settings
from app.db import save_user_api_key, get_current_api_key

router = APIRouter()


# ─── Modelli Pydantic ──────────────────────────────────────────────────────────

class LoginUrlResponse(BaseModel):
    auth_url: str
    code_verifier: str  # il frontend DEVE salvarlo (sessionStorage) e ripassarlo al callback


class CallbackRequest(BaseModel):
    code: str = Field(..., description="Il ?code= ricevuto da OpenRouter nella redirect")
    code_verifier: str = Field(..., description="Il code_verifier generato al momento del login")


class CallbackResponse(BaseModel):
    api_key: str
    user_id: Optional[str] = None
    message: str = "Autenticazione completata con successo"


class UserInfo(BaseModel):
    user_id: Optional[str]
    api_key_preview: str   # mostro solo i primi/ultimi caratteri


# ─── Helpers PKCE ──────────────────────────────────────────────────────────────

def generate_code_verifier(length: int = 64) -> str:
    """
    Genera un code_verifier crittograficamente sicuro (RFC 7636).
    Usa caratteri URL-safe: A-Z, a-z, 0-9, '-', '_', '.', '~'
    """
    token = os.urandom(length)
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode("ascii")


def generate_code_challenge_s256(verifier: str) -> str:
    """
    Genera il code_challenge con metodo S256:
      BASE64URL( SHA256( ASCII(verifier) ) )
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/login-url",
    response_model=LoginUrlResponse,
    summary="Genera l'URL di login OAuth OpenRouter (PKCE S256)",
)
async def get_login_url(
    limit: Optional[float] = Query(
        default=None,
        ge=0.01,
        description="Limite massimo di spesa in dollari (es. 5.0 = $5)",
    )
):
    """
    Restituisce:
    - **auth_url**: dove mandare l'utente per il login
    - **code_verifier**: da salvare in sessionStorage; serve per /api/auth/callback

    Il parametro **limit** imposta un tetto massimo di spesa sull'API key generata.
    """
    settings = get_settings()

    verifier = generate_code_verifier()
    challenge = generate_code_challenge_s256(verifier)
    callback_url = f"{settings.app_base_url}/callback"

    params = {
        "callback_url": callback_url,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if limit is not None:
        params["limit"] = str(limit)

    # Costruisce la query string manualmente per preservare l'ordine
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{settings.openrouter_auth_url}?{query_string}"

    return LoginUrlResponse(auth_url=auth_url, code_verifier=verifier)


@router.post(
    "/callback",
    response_model=CallbackResponse,
    summary="Scambia il codice OAuth per una API key OpenRouter",
)
async def exchange_code(body: CallbackRequest, request: Request):
    """
    Riceve il **code** dalla redirect di OpenRouter e il **code_verifier**
    salvato dal frontend, poi chiama l'endpoint di OpenRouter per ottenere
    la API key utente.
    """
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.openrouter_api_base}/auth/keys",
            json={
                "code": body.code,
                "code_verifier": body.code_verifier,
                "code_challenge_method": "S256",
            },
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )

    if resp.status_code == 400:
        raise HTTPException(status_code=400, detail="Codice non valido o scaduto")
    if resp.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail="code_verifier non corrispondente o utente non loggato su OpenRouter",
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter ha risposto con status {resp.status_code}: {resp.text}",
        )

    data = resp.json()
    api_key = data.get("key")
    user_id = str(data.get("user_id") or "unknown_user")

    if not api_key:
        raise HTTPException(status_code=502, detail="OpenRouter non ha restituito una API key")

    # Salva in sessione
    request.session["api_key"] = api_key
    request.session["user_id"] = user_id

    # Salva nel "DB" JSON
    save_user_api_key(user_id, api_key)

    return CallbackResponse(
        api_key=api_key,
        user_id=user_id,
        message="Autenticazione completata e salvata in sessione"
    )


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Info sull'utente autenticato (da sessione o DB)",
)
async def get_me(
    request: Request,
    api_key: str = Depends(get_current_api_key)
):
    """
    Verifica se l'utente ha una API key valida in sessione o nel DB.
    Se non ce l'ha, get_current_api_key solleva un 401.
    """
    user_id = request.session.get("user_id")
    # Mostro solo l'inizio e la fine della chiave per sicurezza
    preview = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
    
    return UserInfo(
        user_id=user_id,
        api_key_preview=preview
    )