"""Préparation des emails — JAMAIS d'envoi.

Trois modes, tous sous contrôle de l'utilisateur :
1. Fichier .eml « non envoyé » (en-tête X-Unsent: 1) : s'ouvre comme brouillon dans Outlook / Thunderbird,
   avec destinataire, objet, corps et pièces jointes validées.
2. Lien mailto: prérempli (sans pièces jointes — limite du protocole).
3. Brouillon Zoho Mail via l'API officielle (mode "draft") : il apparaît dans le dossier Brouillons,
   l'utilisateur relit et clique lui-même sur Envoyer.

Ce module ne contient volontairement AUCUNE fonction d'envoi.
"""
import json
import mimetypes
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Credential

SENDER = "contact@kortexdigital.net"


def build_eml(sender: str, to: str, cc: str, subject: str, body: str, attachments: list[tuple[str, bytes]]) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="kortexdigital.net")
    msg["X-Unsent"] = "1"  # Outlook : ouvre en mode composition, rien n'est envoyé
    msg.set_content(body)
    for filename, data in attachments:
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return bytes(msg)


def mailto_link(to: str, cc: str, subject: str, body: str) -> str:
    q = {"subject": subject, "body": body}
    if cc:
        q["cc"] = cc
    return f"mailto:{quote(to)}?" + urlencode(q, quote_via=quote)


# ---------- Zoho Mail (OAuth2) ----------

ZOHO_SCOPES = "ZohoMail.accounts.READ,ZohoMail.messages.CREATE"


class ZohoError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().secret_key
    if not key:
        raise ZohoError("SECRET_KEY manquante dans .env (générer avec : python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\")")
    return Fernet(key.encode())


def save_tokens(db: Session, provider: str, payload: dict) -> None:
    enc = _fernet().encrypt(json.dumps(payload).encode()).decode()
    cred = db.query(Credential).filter_by(provider=provider).one_or_none()
    if cred:
        cred.encrypted_payload = enc
    else:
        db.add(Credential(provider=provider, encrypted_payload=enc))
    db.commit()


def load_tokens(db: Session, provider: str) -> dict | None:
    cred = db.query(Credential).filter_by(provider=provider).one_or_none()
    if not cred:
        return None
    try:
        return json.loads(_fernet().decrypt(cred.encrypted_payload.encode()))
    except (InvalidToken, ZohoError):
        return None


def zoho_configured() -> bool:
    s = get_settings()
    return bool(s.zoho_client_id and s.zoho_client_secret and s.secret_key)


def zoho_authorize_url(state: str) -> str:
    s = get_settings()
    q = {"scope": ZOHO_SCOPES, "client_id": s.zoho_client_id, "response_type": "code", "access_type": "offline",
         "redirect_uri": s.zoho_redirect_uri, "prompt": "consent", "state": state}
    return f"{s.zoho_accounts_domain}/oauth/v2/auth?{urlencode(q)}"


def zoho_exchange_code(db: Session, code: str) -> dict:
    s = get_settings()
    r = httpx.post(f"{s.zoho_accounts_domain}/oauth/v2/token", data={
        "grant_type": "authorization_code", "client_id": s.zoho_client_id, "client_secret": s.zoho_client_secret,
        "redirect_uri": s.zoho_redirect_uri, "code": code}, timeout=30)
    data = r.json()
    if "access_token" not in data:
        raise ZohoError(f"Échec OAuth Zoho : {data.get('error', data)}")
    data["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
    account = _zoho_account(data["access_token"])
    data["account_id"], data["email"] = account
    save_tokens(db, "zoho", data)
    return data


def _zoho_token(db: Session) -> dict:
    tok = load_tokens(db, "zoho")
    if not tok:
        raise ZohoError("Compte Zoho non connecté")
    if time.time() > tok.get("expires_at", 0):
        s = get_settings()
        r = httpx.post(f"{s.zoho_accounts_domain}/oauth/v2/token", data={
            "grant_type": "refresh_token", "client_id": s.zoho_client_id, "client_secret": s.zoho_client_secret,
            "refresh_token": tok["refresh_token"]}, timeout=30)
        new = r.json()
        if "access_token" not in new:
            raise ZohoError(f"Rafraîchissement du jeton Zoho impossible : {new.get('error', new)} — reconnecter le compte")
        tok["access_token"] = new["access_token"]
        tok["expires_at"] = time.time() + int(new.get("expires_in", 3600)) - 60
        save_tokens(db, "zoho", tok)
    return tok


def _zoho_account(access_token: str) -> tuple[str, str]:
    s = get_settings()
    r = httpx.get(f"{s.zoho_mail_domain}/api/accounts", headers={"Authorization": f"Zoho-oauthtoken {access_token}"}, timeout=30)
    r.raise_for_status()
    accounts = r.json().get("data", [])
    if not accounts:
        raise ZohoError("Aucun compte Zoho Mail trouvé")
    preferred = next((a for a in accounts if SENDER in json.dumps(a)), accounts[0])
    return str(preferred["accountId"]), preferred.get("primaryEmailAddress") or preferred.get("mailboxAddress", "")


def zoho_status(db: Session) -> dict:
    tok = load_tokens(db, "zoho") if get_settings().secret_key else None
    return {"configured": zoho_configured(), "connected": bool(tok), "email": (tok or {}).get("email", "")}


def zoho_create_draft(db: Session, to: str, cc: str, subject: str, body: str, attachments: list[tuple[str, bytes]]) -> str:
    """Crée un BROUILLON (mode=draft). Ne déclenche aucun envoi."""
    tok = _zoho_token(db)
    s = get_settings()
    headers = {"Authorization": f"Zoho-oauthtoken {tok['access_token']}"}
    base = f"{s.zoho_mail_domain}/api/accounts/{tok['account_id']}"
    uploaded = []
    for filename, data in attachments:
        r = httpx.post(f"{base}/messages/attachments", params={"uploadType": "multipart"}, headers=headers,
                       files={"attach": (filename, data, mimetypes.guess_type(filename)[0] or "application/octet-stream")}, timeout=60)
        r.raise_for_status()
        for att in r.json().get("data", []):
            uploaded.append({"storeName": att["storeName"], "attachmentPath": att["attachmentPath"], "attachmentName": att["attachmentName"]})
    payload = {"fromAddress": tok.get("email") or SENDER, "toAddress": to, "subject": subject,
               "content": body.replace("\n", "<br>"), "mailFormat": "html", "mode": "draft"}
    if cc:
        payload["ccAddress"] = cc
    if uploaded:
        payload["attachments"] = uploaded
    assert payload["mode"] == "draft"  # garde-fou : ce module ne crée que des brouillons
    r = httpx.post(f"{base}/messages", json=payload, headers=headers, timeout=60)
    if r.status_code >= 400:
        raise ZohoError(f"Zoho a refusé le brouillon : HTTP {r.status_code} {r.text[:300]}")
    data = r.json().get("data", {})
    return str(data.get("messageId", "")) if isinstance(data, dict) else ""


def read_attachment(path: str) -> bytes:
    return Path(path).read_bytes()
