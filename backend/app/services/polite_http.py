"""Récupération HTTP respectueuse : robots.txt, délai entre requêtes par domaine,
User-Agent identifié. Aucun contournement d'authentification, de CAPTCHA ou d'anti-bot :
un 401/403/429 est simplement signalé."""
import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

from ..config import get_settings


class FetchBlocked(Exception):
    """La page est interdite par robots.txt ou protégée : on n'insiste pas."""


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_last_hit: dict[str, float] = {}


def _client() -> httpx.Client:
    s = get_settings()
    return httpx.Client(headers={"User-Agent": s.http_user_agent, "Accept-Language": "fr,en;q=0.8"}, timeout=20, follow_redirects=True)


def _robots_for(base: str) -> urllib.robotparser.RobotFileParser | None:
    if base in _robots:
        return _robots[base]
    rp = urllib.robotparser.RobotFileParser()
    try:
        with _client() as c:
            r = c.get(base + "/robots.txt")
        if r.status_code == 200:
            rp.parse(r.text.splitlines())
        else:
            rp = None  # pas de robots.txt → autorisé
    except httpx.HTTPError:
        rp = None
    _robots[base] = rp
    return rp


def allowed(url: str) -> bool:
    p = urlparse(url)
    rp = _robots_for(f"{p.scheme}://{p.netloc}")
    return True if rp is None else rp.can_fetch(get_settings().http_user_agent, url)


def fetch(url: str, check_robots: bool = True) -> httpx.Response:
    s = get_settings()
    if check_robots and not allowed(url):
        raise FetchBlocked(f"robots.txt interdit l'accès à {url}")
    host = urlparse(url).netloc
    wait = s.crawl_delay_seconds - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    with _client() as c:
        r = c.get(url)
    _last_hit[host] = time.monotonic()
    if r.status_code in (401, 403, 429):
        raise FetchBlocked(f"{url} refuse l'accès automatisé (HTTP {r.status_code}) — à consulter manuellement")
    r.raise_for_status()
    return r
