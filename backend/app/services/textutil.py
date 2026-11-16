import hashlib
import re
import unicodedata
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_LEGAL_SUFFIXES = r"\b(sarl|sa|sas|sasu|suarl|ltd|llc|inc|gmbh|plc|ci|cote d ivoire|group|groupe)\b"


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(name: str) -> str:
    s = strip_accents(name or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(_LEGAL_SUFFIXES, " ", s)
    return re.sub(r"\s+", " ", s).strip()


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


def fingerprint(*parts: str) -> str:
    key = "|".join(normalize_name(p or "") for p in parts)
    return hashlib.sha256(key.encode()).hexdigest()


def html_to_text(html: str, limit: int = 20000) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:limit]


def fix_mojibake(s: str) -> str:
    """Répare un texte UTF-8 décodé en latin-1 par la source (ex. « â€“ » au lieu de « – »)."""
    if not s or not any(m in s for m in ("Ã", "â", "Â")):
        return s
    try:
        return s.encode("cp1252", errors="strict").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s
