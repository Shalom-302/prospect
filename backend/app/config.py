"""Configuration centralisée. Tous les secrets viennent de l'environnement (.env / Dokploy),
jamais du code ni du frontend."""
import json
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from typing import Annotated

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"), extra="ignore")

    environment: str = "dev"  # dev | prod
    database_url: str = "postgresql+psycopg://kortex:kortex@localhost:5432/kortex_prospect"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: Path = BASE_DIR.parent / "storage"
    frontend_origin: str = "http://localhost:3100"  # plusieurs origines : séparées par des virgules
    public_url: str = "http://localhost:3100"  # URL publique (liens de désinscription, retour OAuth)

    # LLM — n'importe quelle API compatible OpenAI (Mistral, DeepSeek, Groq, Ollama, OpenRouter…)
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.4

    # Recherche web
    tavily_api_key: str = ""

    # Zoho Mail OAuth2 (brouillons)
    zoho_client_id: str = ""
    zoho_client_secret: str = ""
    zoho_accounts_domain: str = "https://accounts.zoho.com"  # .eu / .in selon la région du compte
    zoho_mail_domain: str = "https://mail.zoho.com"
    zoho_redirect_uri: str = "http://localhost:3100/api/email/zoho/callback"

    # Envoi par lots (SMTP Zoho) + suivi des réponses (IMAP Zoho)
    # Compte avec domaine : smtppro.zoho.com / imappro.zoho.com (.eu selon la région).
    # Mot de passe : « mot de passe d'application » Zoho si la double authentification est active.
    smtp_host: str = "smtppro.zoho.com"
    smtp_port: int = 465
    imap_host: str = "imappro.zoho.com"
    imap_port: int = 993
    mail_user: str = ""
    mail_password: str = ""
    sender_email: str = "contact@kortexdigital.net"
    sender_name: str = "Shalom Tehe - KORTEX DIGITAL"
    campaign_daily_max: int = 30  # plafond absolu par jour, montée en charge progressive en dessous
    campaign_min_interval_s: int = 180  # délai minimal entre deux envois (+ aléa)
    campaign_max_interval_s: int = 420
    campaign_hours: str = "8-17"  # heures d'envoi (Africa/Abidjan), jours ouvrés
    recontact_days: int = 90  # pas de recontact d'une même entreprise avant ce délai

    # Chiffrement (Fernet) des jetons stockés en base + signature des liens de désinscription
    secret_key: str = ""

    # Authentification : code WhatsApp via la passerelle gowa (comme Foody)
    token_secret_key: str = ""
    admin_phones: Annotated[list[str], NoDecode] = []
    phone_default_country_code: str = "225"
    gowa_url: str = ""
    gowa_basic_user: str = ""
    gowa_basic_pass: str = ""
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_max_sends_per_hour: int = 5
    session_days: int = 30
    cookie_secure: bool = False

    # Identification polie auprès des sites consultés
    http_user_agent: str = "KortexProspect/1.0 (+https://www.kortexdigital.net)"
    crawl_delay_seconds: float = 1.5

    @field_validator("admin_phones", mode="before")
    @classmethod
    def _phones(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                return json.loads(v)
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def auth_enabled(self) -> bool:
        return self.environment != "dev" or bool(self.admin_phones)

    @property
    def mail_configured(self) -> bool:
        return bool(self.mail_user and self.mail_password)

    def check_production(self) -> None:
        if self.environment == "dev":
            return
        missing = [k for k in ("token_secret_key", "secret_key", "public_url") if not getattr(self, k)]
        if not self.admin_phones:
            missing.append("admin_phones")
        if missing:
            raise RuntimeError(f"Configuration de production incomplète : {', '.join(m.upper() for m in missing)}")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    return s
