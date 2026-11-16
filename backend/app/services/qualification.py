"""Qualification des opportunités et des entreprises : score /100 expliqué.

Grille (cahier des charges §5) :
  compétences 30 · secteur 20 · géographie 15 · contrat 15 · expériences 20

Deux méthodes :
- `heuristic` : déterministe, sans LLM, toujours disponible (explication par règle)
- `llm`       : analyse complète (7 questions + score), si un LLM est configuré
"""
import json
import re

from ..models import Company, Opportunity, Profile
from . import llm
from .textutil import strip_accents

CRITERIA = {
    "skills": ("Correspondance des compétences", 30),
    "sector": ("Correspondance du secteur", 20),
    "geography": ("Compatibilité géographique", 15),
    "contract": ("Compatibilité du contrat", 15),
    "experience": ("Adéquation avec les expériences", 20),
}

STRONG_SKILLS = ["python", "fastapi", "langchain", "langgraph", "llm", "llms", "rag", "mcp", "ai agents", "agentic", "genai",
                 "generative ai", "ia generative", "sqlalchemy", "celery", "qdrant", "ai engineer", "prompt engineering"]
GENERIC_SKILLS = ["postgresql", "postgres", "docker", "redis", "api", "rest", "backend", "back-end", "alembic", "vector",
                  "nlp", "openai", "linux", "ci/cd", "microservices"]
OTHER_STACKS = ["magento", "php", "laravel", "wordpress", "java ", "spring", ".net", "c#", "ruby", "rails", "golang", " go ",
                "react native", "ios", "android", "swift", "kotlin", "salesforce", "sap ", "shopify", "unity", "flutter", "rust"]
TECH_ROLE_WORDS = ["engineer", "developer", "developpeur", "ingenieur", "backend", "back-end", "software", "ai ", "ia ",
                   "llm", "python", "tech lead", "lead dev", "architect", "devops", "consultant", "data"]
KORTEX_TARGET_SECTORS = ["banque", "bank", "assurance", "insurance", "sante", "health", "clinique", "hopital", "energie",
                         "energy", "petrol", "telecom", "education", "ecole", "universite", "industrie", "logistique",
                         "transport", "commerce", "distribution", "sport", "ong", "ngo", "administration", "microfinance",
                         "immobilier", "hotel", "agro", "mines", "btp"]
AFRICA = ["cote d'ivoire", "cote d ivoire", "abidjan", "ivory coast", "senegal", "ghana", "nigeria", "kenya", "rwanda",
          "south africa", "afrique", "africa", "maroc", "morocco", "benin", "togo", "cameroun", "cameroon", "emea"]
RESTRICTED_GEO = ["us only", "usa only", "united states only", "must be located in the us", "us-based", "eu only",
                  "europe only", "uk only", "canada only", "us citizens", "security clearance"]
WORLDWIDE = ["worldwide", "anywhere", "global", "remote - anywhere", "international"]


def _norm(s: str) -> str:
    return strip_accents((s or "").lower())


def _crit(key: str, score: float, reason: str) -> dict:
    label, mx = CRITERIA[key]
    return {"label": label, "score": round(max(0, min(mx, score))), "max": mx, "reason": reason}


def heuristic_opportunity(opp: Opportunity, profile_key: str) -> dict:
    text = _norm(" ".join([opp.title, opp.description[:6000], " ".join(opp.skills or []), opp.contract_type, opp.location]))
    title = _norm(opp.title)
    def hits(words):
        return sorted({k for k in words if re.search(r"(?<![a-z])" + re.escape(k.strip()) + r"(?![a-z])", text)})

    strong, generic = hits(STRONG_SKILLS), hits(GENERIC_SKILLS)
    other = [w.strip() for w in OTHER_STACKS if w in f" {title} "]
    skill_score = len(strong) * 7 + len(generic) * 2
    reason = f"Compétences clés trouvées : {', '.join(strong) or 'aucune'}"
    if generic:
        reason += f" ; compétences générales : {', '.join(generic)}"
    off_stack = bool(other) and "python" not in title
    if off_stack:
        skill_score = min(skill_score, 8)
        reason += f". Stack principale différente ({', '.join(other)}) : faible adéquation"
    crit = {}
    crit["skills"] = _crit("skills", skill_score, reason + ".")

    is_tech = any(w in title + " " for w in TECH_ROLE_WORDS) and not off_stack
    crit["sector"] = _crit("sector", 20 if is_tech else 6,
                           "Poste technique logiciel / IA." if is_tech else "Intitulé hors cœur de métier (logiciel / IA).")

    loc = _norm(opp.location + " " + opp.description[:3000])
    if any(r in loc for r in RESTRICTED_GEO):
        crit["geography"] = _crit("geography", 2, "L'annonce semble restreinte à une zone géographique (ex. US/EU only).")
    elif any(a in loc for a in AFRICA):
        crit["geography"] = _crit("geography", 15, "Localisation Côte d'Ivoire / Afrique compatible.")
    elif opp.remote and any(w in loc for w in WORLDWIDE):
        crit["geography"] = _crit("geography", 15, "Télétravail ouvert à l'international.")
    elif opp.remote:
        crit["geography"] = _crit("geography", 10, "Télétravail, mais zone éligible non précisée : à vérifier.")
    else:
        crit["geography"] = _crit("geography", 5, "Poste sur site hors Côte d'Ivoire : relocalisation probable.")

    ct = _norm(opp.contract_type + " " + title)
    if any(w in ct for w in ["intern", "stage", "stagiaire"]):
        crit["contract"] = _crit("contract", 3, "Stage : ne correspond pas aux contrats recherchés.")
    elif ct.strip():
        crit["contract"] = _crit("contract", 15, f"Type de contrat « {opp.contract_type or 'indiqué'} » compatible (CDI, CDD, freelance, contrat).")
    else:
        crit["contract"] = _crit("contract", 9, "Type de contrat non précisé.")

    years = [int(y) for y in re.findall(r"(\d{1,2})\s*\+?\s*(?:years|ans|yrs)", text)]
    need = max(years) if years else None
    if off_stack:
        crit["experience"] = _crit("experience", 6, "Expériences du profil centrées Python / IA, pas sur la stack demandée.")
    elif any(w in title for w in ["principal", "staff", "head of", "director", "vp "]):
        crit["experience"] = _crit("experience", 8, "Niveau très senior (staff/principal/direction) : écart probable avec 3+ ans d'expérience.")
    elif need and need > 6:
        crit["experience"] = _crit("experience", 7, f"{need}+ ans demandés, profil à 3+ ans d'expérience.")
    elif need and need > 4:
        crit["experience"] = _crit("experience", 13, f"{need}+ ans demandés : légèrement au-dessus, compensé par Shaapi et le rôle de Lead.")
    else:
        crit["experience"] = _crit("experience", 18, "Niveau d'expérience compatible (3+ ans, lead developer, projets en production).")

    total = sum(c["score"] for c in crit.values())
    return {
        "method": "heuristic",
        "total": total,
        "criteria": crit,
        "recommended_profile": "kortex" if opp.kind == "b2b" else profile_key,
        "summary": "Score calculé par règles (sans IA). Configurez un LLM pour l'analyse complète.",
        "documents_to_attach": ["cv_en" if (opp.language or "en") == "en" else "cv_fr", "cover_letter"],
        "red_flags": ["Annonce issue d'une recherche web : vérifier qu'elle est réelle et ouverte."] if opp.needs_verification else [],
    }


def heuristic_company(c: Company) -> dict:
    text = _norm(" ".join([c.name, c.sector, c.description, c.city, c.country]))
    crit = {}
    sec = [s for s in KORTEX_TARGET_SECTORS if s in text]
    crit["sector"] = _crit("sector", 20 if sec else 8, f"Secteur cible : {', '.join(sec)}." if sec else "Secteur non identifié parmi les cibles.")
    digital = [w for w in ["digital", "numerique", "logiciel", "plateforme", "application", "en ligne", "automatisation", "donnees", "data", "ia", "ai"] if re.search(rf"\b{w}\b", text)]
    crit["skills"] = _crit("skills", 10 + len(digital) * 4, f"Signaux de besoin numérique : {', '.join(digital) or 'aucun signal explicite'}.")
    geo = _norm(c.country + " " + c.city)
    crit["geography"] = _crit("geography", 15 if any(a in geo for a in AFRICA[:3]) else 10 if any(a in geo for a in AFRICA) else 7,
                              "Côte d'Ivoire : marché prioritaire." if "cote" in geo or "abidjan" in geo else "Hors Côte d'Ivoire : approche à distance.")
    crit["contract"] = _crit("contract", 10, "Mode de collaboration à confirmer (prestation, sous-traitance, référencement).")
    crit["experience"] = _crit("experience", 12, "Réalisations KORTEX à rapprocher du secteur (santé, énergie, sport).")
    has_contact = any(ct.kind in ("email", "contact_form") for ct in c.contacts)
    flags = [] if has_contact else ["Aucun email ni formulaire public trouvé : scanner le site ou passer par LinkedIn."]
    flags.append("Une entreprise n'est pas une opportunité confirmée : aucun besoin exprimé publiquement.")
    return {"method": "heuristic", "total": sum(v["score"] for v in crit.values()), "criteria": crit,
            "recommended_profile": "kortex", "summary": "Score calculé par règles (sans IA).",
            "documents_to_attach": ["plaquette", "presentation", "b2b_proposal"], "red_flags": flags}


# ---------- LLM ----------

QUALIF_SYSTEM = """Tu es l'analyste business development de Shalom Tehe (ingénieur backend & IA) et de son entreprise KORTEX DIGITAL (Abidjan).
Tu qualifies une opportunité de façon honnête et critique. Tu ne surévalues jamais. Tu n'inventes aucun fait :
si une information manque dans l'annonce, dis-le. Une entreprise qui a un email n'est PAS une opportunité confirmée.
Grille : skills /30, sector /20, geography /15, contract /15, experience /20."""

QUALIF_SCHEMA = """{
 "relevant_shalom": bool, "relevant_kortex": bool,
 "recommended_profile": "shalom" | "kortex",
 "matched": ["compétences ou services KORTEX qui répondent au besoin"],
 "criteria": {"skills": {"score": int, "reason": str}, "sector": {...}, "geography": {...}, "contract": {...}, "experience": {...}},
 "contact_to_target": "qui contacter (fonction) et par quel canal",
 "documents_to_attach": ["cv_fr" | "cv_en" | "portfolio" | "plaquette" | "presentation" | "certificat" | "cover_letter" | "b2b_proposal"],
 "approach": "approche recommandée en 2-3 phrases",
 "language": "fr" | "en",
 "red_flags": ["risques : fraude possible, zone restreinte, offre expirée, écart d'expérience…"],
 "summary": "synthèse en une phrase"
}"""


def _profiles_brief(profiles: dict[str, Profile]) -> str:
    s, k = profiles["shalom"].data, profiles["kortex"].data
    return json.dumps({
        "shalom": {"headline": s.get("headline"), "summary": s.get("summary"), "skills": s.get("skills"),
                   "target_roles": s.get("target_roles"), "contract_types": s.get("contract_types"),
                   "experiences": [f"{e['title']} — {e['company']} ({e['period']})" for e in s.get("experiences", [])],
                   "projects": [p["name"] + " : " + p["description"] for p in s.get("projects", [])],
                   "location": s.get("location"), "languages": s.get("languages")},
        "kortex": {"pitch": k.get("pitch"), "services": k.get("services"), "products": k.get("products"),
                   "client_sectors": k.get("client_sectors"), "context": k.get("context")},
    }, ensure_ascii=False)


def _finalize(data: dict) -> dict:
    crit = {}
    for key, (label, mx) in CRITERIA.items():
        c = (data.get("criteria") or {}).get(key) or {}
        try:
            sc = float(c.get("score", 0))
        except (TypeError, ValueError):
            sc = 0
        crit[key] = {"label": label, "score": round(max(0, min(mx, sc))), "max": mx, "reason": str(c.get("reason", ""))}
    data["criteria"] = crit
    data["total"] = sum(c["score"] for c in crit.values())
    data["method"] = "llm"
    data["model"] = llm.model_name()
    return data


def llm_opportunity(opp: Opportunity, profiles: dict[str, Profile]) -> dict:
    user = f"""PROFILS :\n{_profiles_brief(profiles)}\n\nOPPORTUNITÉ ({opp.kind}) :
Intitulé : {opp.title}\nEntreprise : {opp.company_name}\nLieu : {opp.location} | Remote : {opp.remote}
Contrat : {opp.contract_type} | Rémunération : {opp.salary} {opp.currency}
Source : {opp.source} — {opp.source_url}\nPubliée : {opp.published_at} | Date limite : {opp.deadline}
Compétences listées : {', '.join(opp.skills or [])}
Description :\n{opp.description[:9000]}\n\nRéponds au format :\n{QUALIF_SCHEMA}"""
    return _finalize(llm.chat_json(QUALIF_SYSTEM, user))


def llm_company(c: Company, profiles: dict[str, Profile]) -> dict:
    contacts = [f"{ct.kind}:{ct.value} ({ct.label}, {ct.confidence})" for ct in c.contacts]
    user = f"""PROFILS :\n{_profiles_brief(profiles)}\n\nENTREPRISE (prospect B2B potentiel, aucun besoin confirmé) :
Nom : {c.name}\nSite : {c.website}\nSecteur : {c.sector}\nPays/Ville : {c.country} / {c.city}
Description : {c.description[:5000]}\nContacts publics : {contacts}\n
Pour une entreprise : 'skills' = adéquation des services KORTEX aux besoins probables, 'contract' = faisabilité d'une
collaboration (prestation, sous-traitance, référencement), 'experience' = pertinence des réalisations KORTEX pour ce secteur.
Réponds au format :\n{QUALIF_SCHEMA}"""
    return _finalize(llm.chat_json(QUALIF_SYSTEM, user))
