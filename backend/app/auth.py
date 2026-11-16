"""Connexion sans mot de passe : numéro WhatsApp autorisé + code à usage unique.

Repris de Foody / SignalLab : le code est envoyé via la passerelle gowa
(``POST {GOWA_URL}/send/message``, auth Basic), stocké dans Redis avec TTL et
compteur d'essais. Seuls les numéros listés dans ADMIN_PHONES peuvent se connecter :
c'est un outil personnel, pas un service ouvert. La session est un JWT dans un
cookie httpOnly, posé sur l'origine du frontend (qui proxifie /api).
En dev sans GOWA_URL, le code est écrit dans les logs.
"""
import base64
import logging
import secrets
import time

import httpx
import jwt
import redis
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .config import get_settings

log = logging.getLogger("prospect.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "prospect_session"
PUBLIC_PREFIXES = ("/api/auth/", "/api/health", "/api/public/", "/docs", "/openapi.json")
_WA = "@s.whatsapp.net"

_redis: redis.Redis | None = None


def r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(get_settings().redis_url, decode_responses=True, socket_timeout=5)
    return _redis


def normalize_phone(value: str) -> str:
    """« +225 07 12 11 62 58 », « 00225… » ou « 07 12 11 62 58 » → « 2250712116258 »."""
    raw = (value or "").strip()
    digits = "".join(c for c in raw if c.isdigit())
    if not raw.startswith("+") and digits.startswith("00"):
        digits = digits[2:]
    elif not raw.startswith("+") and digits.startswith("0"):
        digits = get_settings().phone_default_country_code + digits
    if not 8 <= len(digits) <= 15:
        raise HTTPException(422, "Numéro invalide (indicatif + numéro).")
    return digits


def _allowed() -> set[str]:
    out = set()
    for p in get_settings().admin_phones:
        try:
            out.add(normalize_phone(p))
        except HTTPException:
            log.warning("ADMIN_PHONES : numéro ignoré %r", p)
    return out


def _wa_candidates(phone: str) -> list[str]:
    # Côte d'Ivoire : passage à 10 chiffres en 2021, mais beaucoup de comptes WhatsApp
    # sont encore enregistrés sous l'ancien numéro à 8 chiffres.
    if phone.startswith("2250") and len(phone) == 13:
        return [phone, "225" + phone[5:]]
    return [phone]


def _send_whatsapp(phone: str, message: str) -> None:
    s = get_settings()
    if not s.gowa_url:
        if s.environment == "dev":
            log.warning("[dev] GOWA_URL absent — message WhatsApp pour %s : %s", phone, message)
            print(f"[dev] code WhatsApp pour {phone} : {message}", flush=True)
            return
        raise HTTPException(503, "Service WhatsApp non configuré (GOWA_URL).")
    headers = {"Content-Type": "application/json"}
    if s.gowa_basic_user or s.gowa_basic_pass:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{s.gowa_basic_user}:{s.gowa_basic_pass}".encode()).decode()
    for cand in _wa_candidates(phone):
        try:
            resp = httpx.post(f"{s.gowa_url.rstrip('/')}/send/message", json={"phone": cand + _WA, "message": message},
                              headers=headers, timeout=20)
        except httpx.HTTPError as e:
            log.error("gowa injoignable : %s", e)
            raise HTTPException(503, "Envoi du code WhatsApp impossible pour le moment.")
        if resp.status_code in (401, 403):
            log.error("gowa refuse nos identifiants (%s)", resp.status_code)
            raise HTTPException(503, "Envoi du code WhatsApp impossible pour le moment.")
        if resp.status_code < 400:
            return
    raise HTTPException(403, "Ce numéro n'est pas joignable sur WhatsApp.")


class PhoneIn(BaseModel):
    phone: str


class VerifyIn(BaseModel):
    phone: str
    code: str


@router.post("/request-otp")
def request_otp(body: PhoneIn):
    s = get_settings()
    phone = normalize_phone(body.phone)
    # Réponse identique que le numéro soit autorisé ou non : on ne révèle pas qui a accès.
    if phone not in _allowed():
        log.warning("Tentative de connexion d'un numéro non autorisé : %s", phone)
        return {"sent": True, "expires_in": s.otp_ttl_seconds}
    sends = r().incr(f"otp:sends:{phone}")
    if sends == 1:
        r().expire(f"otp:sends:{phone}", 3600)
    if sends > s.otp_max_sends_per_hour:
        raise HTTPException(429, "Trop de codes demandés. Réessayez dans une heure.")
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    r().hset(f"otp:{phone}", mapping={"code": code, "attempts": 0})
    r().expire(f"otp:{phone}", s.otp_ttl_seconds)
    _send_whatsapp(phone, f"KORTEX Prospect : votre code de connexion est {code}. Il expire dans {s.otp_ttl_seconds // 60} minutes. Ne le partagez avec personne.")
    return {"sent": True, "expires_in": s.otp_ttl_seconds}


def _issue(phone: str) -> str:
    s = get_settings()
    now = int(time.time())
    return jwt.encode({"sub": phone, "iat": now, "exp": now + s.session_days * 86400}, s.token_secret_key or s.secret_key, algorithm="HS256")


@router.post("/verify-otp")
def verify_otp(body: VerifyIn, response: Response):
    s = get_settings()
    phone = normalize_phone(body.phone)
    key = f"otp:{phone}"
    data = r().hgetall(key)
    if not data or phone not in _allowed():
        raise HTTPException(403, "Code expiré ou introuvable. Demandez un nouveau code.")
    attempts = int(data.get("attempts", 0)) + 1
    if attempts > s.otp_max_attempts:
        r().delete(key)
        raise HTTPException(403, "Trop de tentatives. Demandez un nouveau code.")
    if not secrets.compare_digest(str(data["code"]), body.code.strip()):
        r().hset(key, "attempts", attempts)
        raise HTTPException(403, f"Code incorrect ({s.otp_max_attempts - attempts} essai(s) restant(s)).")
    r().delete(key)
    response.set_cookie(COOKIE, _issue(phone), max_age=s.session_days * 86400, httponly=True, samesite="lax",
                        secure=s.cookie_secure or s.environment != "dev", path="/")
    return {"ok": True, "phone": phone}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


def session_phone(request: Request) -> str | None:
    s = get_settings()
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        data = jwt.decode(token, s.token_secret_key or s.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return data["sub"] if data.get("sub") in _allowed() else None


@router.get("/me")
def me(request: Request):
    s = get_settings()
    if not s.auth_enabled:
        return {"authenticated": True, "auth_enabled": False, "phone": None}
    phone = session_phone(request)
    if not phone:
        raise HTTPException(401, "Non connecté")
    return {"authenticated": True, "auth_enabled": True, "phone": phone}


async def auth_middleware(request: Request, call_next):
    s = get_settings()
    path = request.url.path
    if s.auth_enabled and path.startswith("/api/") and not path.startswith(PUBLIC_PREFIXES) and request.method != "OPTIONS":
        if not session_phone(request):
            return JSONResponse({"detail": "Non connecté"}, status_code=401)
    return await call_next(request)
