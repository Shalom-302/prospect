"""Recherche web via l'API Tavily (https://docs.tavily.com).

Les résultats web ne sont PAS des offres confirmées : ils sont marqués `needs_verification`
jusqu'à ce que l'annonce complète soit récupérée et analysée."""
import httpx

from ..config import get_settings
from ..services.textutil import domain_of
from .base import OpportunityConnector, RawCompany, RawOpportunity, SearchParams

TAVILY_URL = "https://api.tavily.com/search"


class TavilyNotConfigured(RuntimeError):
    pass


def tavily_search(query: str, max_results: int = 10, include_domains: list[str] | None = None,
                  exclude_domains: list[str] | None = None, topic: str = "general", days: int | None = None) -> list[dict]:
    key = get_settings().tavily_api_key
    if not key:
        raise TavilyNotConfigured("TAVILY_API_KEY manquante dans .env")
    payload: dict = {"query": query, "max_results": max(1, min(max_results, 20)), "search_depth": "advanced", "topic": topic}
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains
    if days:
        payload["days"] = days
    r = httpx.post(TAVILY_URL, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=60)
    r.raise_for_status()
    return r.json().get("results", [])


# Domaines qui ne sont pas des sites d'entreprise (annuaires, réseaux sociaux, presse…)
NON_COMPANY_DOMAINS = {
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "wikipedia.org",
    "fr.wikipedia.org", "en.wikipedia.org", "google.com", "pagesjaunes.fr", "goafricaonline.com", "abidjan.net",
    "indeed.com", "glassdoor.com", "emploi.ci", "novojob.com", "educarriere.ci", "jobivoire.ci", "kompass.com",
    "africa-business.com", "tiktok.com", "medium.com", "reddit.com", "crunchbase.com", "bloomberg.com",
}


class TavilyJobsConnector(OpportunityConnector):
    name = "tavily"
    label = "Recherche web (Tavily)"
    requires = "TAVILY_API_KEY"

    def available(self) -> bool:
        return bool(get_settings().tavily_api_key)

    def search(self, params: SearchParams) -> list[RawOpportunity]:
        loc = " ".join(x for x in [params.city, params.country] if x)
        word = {"freelance": "mission freelance", "b2b": "appel d'offres prestataire"}.get(params.kind, "offre d'emploi")
        query = f"{word} {params.query} {loc}".strip()
        results = tavily_search(query, max_results=params.limit, include_domains=params.include_domains or None, days=60)
        out = []
        for r in results:
            url = r.get("url", "")
            out.append(RawOpportunity(
                title=r.get("title", "")[:400], company_name="", source=f"Web · {domain_of(url)}", source_url=url,
                apply_url=url, external_id=f"web:{url}", description=r.get("content", ""), location=loc,
                kind=params.kind, needs_verification=True,
            ))
        return out


def search_companies_raw(params: SearchParams) -> tuple[str, list[dict]]:
    parts = [params.sector or "entreprises", params.query, params.city, params.country]
    query = " ".join(p for p in parts if p) + " site officiel contact"
    return query, tavily_search(query, max_results=params.limit, include_domains=params.include_domains or None)


def companies_from_results(results: list[dict], params: SearchParams) -> list[RawCompany]:
    """Sans LLM : un résultat dont le domaine n'est pas un annuaire = candidat entreprise (à qualifier)."""
    out, seen = [], set()
    for r in results:
        d = domain_of(r.get("url"))
        if not d or d in seen or any(d == n or d.endswith("." + n) for n in NON_COMPANY_DOMAINS):
            continue
        seen.add(d)
        title = (r.get("title") or d).split(" | ")[0].split(" - ")[0].strip()
        out.append(RawCompany(name=title[:200], website=f"https://{d}", source="Tavily", source_url=r.get("url", ""),
                              sector=params.sector, country=params.country, city=params.city,
                              description=(r.get("content") or "")[:1000]))
    return out
