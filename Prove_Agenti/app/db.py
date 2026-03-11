import json
import os
from pathlib import Path
from typing import Dict, Optional

DB_FILE = Path("users_db.json")

def load_db() -> Dict:
    if not DB_FILE.exists():
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(data: Dict):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_user_api_key(user_id: str) -> Optional[str]:
    db = load_db()
    user_data = db.get(user_id)
    if user_data:
        return user_data.get("api_key")
    return None

def save_user_api_key(user_id: str, api_key: str):
    db = load_db()
    db[user_id] = {
        "api_key": api_key,
        "valid": True
    }
    save_db(db)

from fastapi import Request, HTTPException

async def get_current_api_key(request: Request) -> str:
    # 1. Prova dalla sessione
    api_key = request.session.get("api_key")
    if api_key:
        return api_key
    
    # 2. Se non c'è in sessione, prova dal DB usando l'user_id in sessione (se esiste)
    user_id = request.session.get("user_id")
    if user_id:
        api_key = get_user_api_key(user_id)
        if api_key:
            # Ripristina in sessione per la prossima volta
            request.session["api_key"] = api_key
            return api_key
            
    # 3. Se ancora nulla, l'utente non è autenticato
    # In un'app reale potremmo fare un redirect 302 a /api/auth/login-url
    # Ma qui restituiamo un 401 che il frontend può gestire rimandando al login
    raise HTTPException(
        status_code=401, 
        detail="Autenticazione richiesta. Per favore effettua il login via OAuth."
    )
