"""Registre des connecteurs et des plateformes.

`access` :
- api / rss   : collecte automatique autorisée (connecteur dédié)
- websearch   : pas de collecte directe ; recherche via l'index Tavily restreint au domaine
                + lien de recherche prérempli à ouvrir soi-même
- profile     : plateforme où l'on crée un profil / candidature au réseau (pas de liste d'offres à collecter)

`check` : résultat du contrôle d'accessibilité du 16/11/2026 (HTTP depuis Abidjan).
"""
from urllib.parse import quote_plus

from .job_feeds import RemoteOKConnector, RemotiveConnector, WeWorkRemotelyConnector
from .tavily import TavilyJobsConnector

CONNECTORS = {c.name: c for c in [RemotiveConnector(), RemoteOKConnector(), WeWorkRemotelyConnector(), TavilyJobsConnector()]}

PLATFORMS = [
    # Côte d'Ivoire
    {"name": "Emploi.ci", "region": "cote_ivoire", "domain": "emploi.ci", "url": "https://www.emploi.ci", "access": "websearch", "check": "active, accès robots refusé (403)", "kinds": ["job"]},
    {"name": "Novojob Côte d'Ivoire", "region": "cote_ivoire", "domain": "novojob.com", "url": "https://www.novojob.com/cote-d-ivoire", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "JobIvoire", "region": "cote_ivoire", "domain": "jobivoire.ci", "url": "https://jobivoire.ci", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "Educarriere", "region": "cote_ivoire", "domain": "educarriere.ci", "url": "https://educarriere.ci", "access": "websearch", "check": "active", "kinds": ["job"]},
    # Afrique
    {"name": "Jobberman", "region": "afrique", "domain": "jobberman.com", "url": "https://www.jobberman.com", "search": "https://www.jobberman.com/jobs?q={q}", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "BrighterMonday", "region": "afrique", "domain": "brightermonday.co.ke", "url": "https://www.brightermonday.co.ke", "search": "https://www.brightermonday.co.ke/jobs?q={q}", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "Fuzu", "region": "afrique", "domain": "fuzu.com", "url": "https://www.fuzu.com", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "Andela", "region": "afrique", "domain": "andela.com", "url": "https://www.andela.com", "access": "profile", "check": "active — réseau de talents, candidature par profil", "kinds": ["freelance"]},
    {"name": "Gebeya", "region": "afrique", "domain": "gebeya.com", "url": "https://www.gebeya.com", "access": "profile", "check": "ne répond pas — à vérifier manuellement", "kinds": ["freelance"]},
    {"name": "AfricaJobs", "region": "afrique", "domain": "africajobs.net", "url": "https://www.africajobs.net", "access": "websearch", "check": "ne répond pas — à vérifier manuellement", "kinds": ["job"]},
    # International — emploi
    {"name": "LinkedIn Jobs", "region": "international", "domain": "linkedin.com", "url": "https://www.linkedin.com/jobs", "search": "https://www.linkedin.com/jobs/search/?keywords={q}&location={l}", "access": "websearch", "check": "active — collecte automatique interdite par les CGU", "kinds": ["job"]},
    {"name": "Indeed", "region": "international", "domain": "indeed.com", "url": "https://www.indeed.com", "search": "https://www.indeed.com/jobs?q={q}&l={l}", "access": "websearch", "check": "active, accès robots refusé (403)", "kinds": ["job"]},
    {"name": "Glassdoor", "region": "international", "domain": "glassdoor.com", "url": "https://www.glassdoor.com", "search": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}", "access": "websearch", "check": "active, accès robots refusé (403)", "kinds": ["job"]},
    {"name": "Wellfound", "region": "international", "domain": "wellfound.com", "url": "https://wellfound.com/jobs", "access": "websearch", "check": "active", "kinds": ["job"]},
    {"name": "Remotive", "region": "international", "domain": "remotive.com", "url": "https://remotive.com", "access": "api", "connector": "remotive", "check": "active — API publique", "kinds": ["job", "freelance"]},
    {"name": "Remote OK", "region": "international", "domain": "remoteok.com", "url": "https://remoteok.com", "access": "api", "connector": "remoteok", "check": "active — API publique", "kinds": ["job"]},
    {"name": "We Work Remotely", "region": "international", "domain": "weworkremotely.com", "url": "https://weworkremotely.com", "search": "https://weworkremotely.com/remote-jobs/search?term={q}", "access": "rss", "connector": "weworkremotely", "check": "active — flux RSS", "kinds": ["job"]},
    {"name": "Arc", "region": "international", "domain": "arc.dev", "url": "https://arc.dev/remote-jobs", "access": "websearch", "check": "active", "kinds": ["job", "freelance"]},
    {"name": "FlexJobs", "region": "international", "domain": "flexjobs.com", "url": "https://www.flexjobs.com", "access": "websearch", "check": "ne répond pas — abonnement payant, à vérifier", "kinds": ["job"]},
    # International — freelance
    {"name": "Upwork", "region": "international", "domain": "upwork.com", "url": "https://www.upwork.com", "search": "https://www.upwork.com/nx/search/jobs/?q={q}", "access": "websearch", "check": "active, accès robots refusé (403) — API sur approbation", "kinds": ["freelance"]},
    {"name": "Freelancer", "region": "international", "domain": "freelancer.com", "url": "https://www.freelancer.com", "search": "https://www.freelancer.com/search/projects?q={q}", "access": "websearch", "check": "active", "kinds": ["freelance"]},
    {"name": "PeoplePerHour", "region": "international", "domain": "peopleperhour.com", "url": "https://www.peopleperhour.com/freelance-jobs", "access": "websearch", "check": "active", "kinds": ["freelance"]},
    {"name": "Contra", "region": "international", "domain": "contra.com", "url": "https://contra.com", "access": "profile", "check": "active", "kinds": ["freelance"]},
    {"name": "Toptal", "region": "international", "domain": "toptal.com", "url": "https://www.toptal.com", "access": "profile", "check": "active — réseau sélectif, candidature par profil", "kinds": ["freelance"]},
    {"name": "Malt", "region": "international", "domain": "malt.fr", "url": "https://www.malt.fr", "access": "profile", "check": "active, accès robots refusé — les clients viennent au profil", "kinds": ["freelance"]},
    {"name": "ComeUp", "region": "international", "domain": "comeup.com", "url": "https://comeup.com", "access": "profile", "check": "active — vente de services (micro-prestations)", "kinds": ["freelance"]},
    {"name": "Fiverr", "region": "international", "domain": "fiverr.com", "url": "https://www.fiverr.com", "access": "profile", "check": "active — on publie des offres de service, on ne postule pas", "kinds": ["freelance"]},
]


def platform_links(query: str, location: str = "") -> list[dict]:
    """Ajoute à chaque plateforme un lien de recherche prérempli (à ouvrir soi-même)."""
    out = []
    for p in PLATFORMS:
        link = p.get("search", "").format(q=quote_plus(query), l=quote_plus(location)) if p.get("search") else p["url"]
        out.append({**p, "search_link": link})
    return out
