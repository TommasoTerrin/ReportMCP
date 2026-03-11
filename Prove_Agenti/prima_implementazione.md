# OpenRouter OAuth PKCE — FastAPI Demo

Applicazione demo che implementa il flusso **OAuth PKCE** di OpenRouter tramite un backend **FastAPI** e un frontend HTML vanilla.

## Struttura del progetto

```
openrouter-oauth/
├── main.py                   ← Entry point uvicorn
├── requirements.txt
├── .env.example              ← Copia in .env e personalizza
├── app/
│   ├── __init__.py
│   ├── server.py             ← Factory dell'app FastAPI
│   ├── config.py             ← Settings via pydantic-settings
│   └── routers/
│       ├── __init__.py
│       ├── auth.py           ← Endpoints OAuth PKCE
│       └── chat.py           ← Endpoint chat/completions
└── static/
    └── index.html            ← Frontend SPA (login + chat)
```

## Flusso OAuth PKCE

```
Browser                  FastAPI Backend              OpenRouter
   │                          │                           │
   │  GET /api/auth/login-url │                           │
   │─────────────────────────▶│                           │
   │  { auth_url, verifier }  │                           │
   │◀─────────────────────────│                           │
   │                          │                           │
   │  Redirect → auth_url ────────────────────────────────▶│
   │                          │           login/authorize  │
   │◀───────────────────────────────────────── ?code=XXX ─ │
   │                          │                           │
   │  POST /api/auth/callback │                           │
   │  { code, verifier }      │                           │
   │─────────────────────────▶│                           │
   │                          │  POST /api/v1/auth/keys   │
   │                          │─────────────────────────▶│
   │                          │  { key, user_id }         │
   │                          │◀─────────────────────────│
   │  { api_key, user_id }    │                           │
   │◀─────────────────────────│                           │
   │                          │                           │
   │  POST /api/chat/completions (Bearer api_key)          │
   │─────────────────────────▶│                           │
   │                          │  POST /chat/completions   │
   │                          │─────────────────────────▶│
   │                          │  { choices: [...] }       │
   │                          │◀─────────────────────────│
   │  { reply, model, usage } │                           │
   │◀─────────────────────────│                           │
```

## Setup rapido

```bash
# 1. Clona / scarica il progetto
cd openrouter-oauth

# 2. Crea e attiva virtualenv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Configura l'ambiente
cp .env.example .env
# Modifica .env se necessario (il default funziona in locale)

# 5. Avvia il server
python main.py
# Oppure: uvicorn main:app --reload --port 3000
```

Apri **http://localhost:3000** nel browser.

## API Endpoints

### `GET /api/auth/login-url`
Genera il PKCE code verifier/challenge e restituisce l'URL di redirect.

| Parametro | Tipo   | Note                          |
|-----------|--------|-------------------------------|
| `limit`   | float  | Opzionale. Tetto spesa in USD |

**Response:**
```json
{
  "auth_url": "https://openrouter.ai/auth?callback_url=...&code_challenge=...&code_challenge_method=S256",
  "code_verifier": "..."
}
```

### `POST /api/auth/callback`
Scambia il codice OAuth per una API key OpenRouter.

**Body:**
```json
{
  "code": "<codice dalla redirect>",
  "code_verifier": "<verifier salvato in sessionStorage>"
}
```

**Response:**
```json
{
  "api_key": "sk-or-...",
  "user_id": "user_...",
  "message": "Autenticazione completata con successo"
}
```

### `POST /api/chat/completions`
Invia un messaggio al modello configurato. Richiede `Authorization: Bearer <api_key>`.

**Body:**
```json
{
  "message": "Ciao! Presentati.",
  "model": "meta-llama/llama-3.1-8b-instruct:free"
}
```

**Response:**
```json
{
  "reply": "Ciao! Sono un assistente AI...",
  "model_used": "meta-llama/llama-3.1-8b-instruct:free",
  "usage": { "prompt_tokens": 12, "completion_tokens": 48, "total_tokens": 60 }
}
```

## Note sulla registrazione

OpenRouter **non distingue** il flusso OAuth tra utenti nuovi ed esistenti: se un utente non ha account, viene invitato a crearne uno direttamente nella pagina di autorizzazione di OpenRouter. Il pulsante "Registrati" nel frontend apre direttamente `https://openrouter.ai/signup` in una nuova tab.

## Sicurezza

- Il `code_verifier` è generato server-side con `os.urandom(64)` ed è crittograficamente sicuro.
- Il metodo S256 (SHA-256) è usato per il challenge (raccomandato da RFC 7636).
- La API key viene salvata solo in `sessionStorage` del browser (non in localStorage o cookie).
- Non viene mai loggata né esposta dal backend.

## Docs interattive

Con il server avviato, visita:
- Swagger UI: http://localhost:3000/docs
- ReDoc:       http://localhost:3000/redoc