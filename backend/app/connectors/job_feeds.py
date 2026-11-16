"""Sources d'offres disposant d'une API ou d'un flux public officiel.

- Remotive : API publique. Conditions : lien retour vers l'annonce, appels limités (cache 6 h).
- Remote OK : API publique. Conditions : lien retour et mention de Remote OK comme source.
- We Work Remotely : flux RSS publics par catégorie.
"""
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from ..config import get_settings
from ..services.textutil import html_to_text
from .base import OpportunityConnector, RawOpportunity, SearchParams

_CACHE: dict[str, tuple[float, object]] = {}
CACHE_TTL = 6 * 3600


def _cached_get_json(url: str, params: dict | None = None):
    key = url + repr(sorted((params or {}).items()))
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    r = httpx.get(url, params=params, headers={"User-Agent": get_settings().http_user_agent}, timeout=30, follow_redirects=True)
    r.raise_for_status()
    data = json.loads(r.content)  # octets → UTF-8 (certaines API omettent le charset)
    _CACHE[key] = (time.time(), data)
    return data


def _matches(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    t = text.lower()
    return any(k.lower() in t for k in keywords)


class RemotiveConnector(OpportunityConnector):
    name = "remotive"
    label = "Remotive (API)"

    def search(self, params: SearchParams) -> list[RawOpportunity]:
        out: list[RawOpportunity] = []
        terms = params.keywords or ["python"]
        seen: set[str] = set()
        for term in terms[:4]:
            data = _cached_get_json("https://remotive.com/api/remote-jobs", {"search": term, "limit": params.limit})
            for j in data.get("jobs", []):
                jid = str(j.get("id"))
                if jid in seen:
                    continue
                seen.add(jid)
                pub = j.get("publication_date")
                out.append(RawOpportunity(
                    title=j.get("title", ""), company_name=j.get("company_name", ""), source="Remotive",
                    source_url=j.get("url", ""), apply_url=j.get("url", ""), external_id=f"remotive:{jid}",
                    description=html_to_text(j.get("description", "")), skills=j.get("tags") or [],
                    contract_type=j.get("job_type", ""), salary=j.get("salary", ""),
                    location=j.get("candidate_required_location", ""), remote=True, language="en",
                    published_at=datetime.fromisoformat(pub).replace(tzinfo=timezone.utc) if pub else None,
                    kind="freelance" if j.get("job_type") in ("contract", "freelance") else "job",
                ))
        return out


class RemoteOKConnector(OpportunityConnector):
    name = "remoteok"
    label = "Remote OK (API)"

    def search(self, params: SearchParams) -> list[RawOpportunity]:
        data = _cached_get_json("https://remoteok.com/api")
        out: list[RawOpportunity] = []
        for j in data[1:] if isinstance(data, list) else []:  # data[0] = mentions légales
            blob = " ".join([j.get("position", ""), " ".join(j.get("tags") or []), j.get("description", "")[:2000]])
            if not _matches(blob, params.keywords):
                continue
            smin, smax = j.get("salary_min") or 0, j.get("salary_max") or 0
            salary = f"{smin:,} – {smax:,}".replace(",", " ") if smin or smax else ""
            out.append(RawOpportunity(
                title=j.get("position", ""), company_name=j.get("company", ""), source="Remote OK",
                source_url=j.get("url", ""), apply_url=j.get("apply_url") or j.get("url", ""),
                external_id=f"remoteok:{j.get('id')}", description=html_to_text(j.get("description", "")),
                skills=j.get("tags") or [], salary=salary, currency="USD" if salary else "",
                location=j.get("location", "") or "Remote", remote=True, language="en",
                published_at=datetime.fromtimestamp(j["epoch"], tz=timezone.utc) if j.get("epoch") else None,
            ))
            if len(out) >= params.limit:
                break
        return out


WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


class WeWorkRemotelyConnector(OpportunityConnector):
    name = "weworkremotely"
    label = "We Work Remotely (RSS)"

    def search(self, params: SearchParams) -> list[RawOpportunity]:
        out: list[RawOpportunity] = []
        ua = get_settings().http_user_agent
        for feed_url in WWR_FEEDS:
            r = httpx.get(feed_url, headers={"User-Agent": ua}, timeout=30)
            r.raise_for_status()
            for e in feedparser.parse(r.content).entries:
                desc = html_to_text(e.get("summary", ""))
                if not _matches(e.get("title", "") + " " + desc, params.keywords):
                    continue
                company, _, title = e.get("title", "").partition(": ")
                pub = None
                if e.get("published"):
                    try:
                        pub = parsedate_to_datetime(e.published)
                    except (TypeError, ValueError):
                        pub = None
                out.append(RawOpportunity(
                    title=title or company, company_name=company if title else "", source="We Work Remotely",
                    source_url=e.get("link", ""), apply_url=e.get("link", ""), external_id=f"wwr:{e.get('id') or e.get('link')}",
                    description=desc, location=e.get("region", "") or "Remote", remote=True, language="en",
                    contract_type=e.get("type", ""), published_at=pub,
                ))
        return out[: params.limit]
