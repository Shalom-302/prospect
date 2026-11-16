"""Exécution des recherches et enregistrement des résultats : déduplication,
écart des offres expirées / frauduleuses, traçabilité (source + date)."""
import json
import re
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from ..connectors.base import RawCompany, RawOpportunity, SearchParams
from ..connectors.registry import CONNECTORS
from ..connectors.tavily import companies_from_results, search_companies_raw
from ..models import Company, Contact, Opportunity, SearchRun, now
from . import llm
from .contact_extractor import scan_website
from .qualification import heuristic_opportunity
from .textutil import domain_of, fingerprint, fix_mojibake, normalize_name, strip_accents

MAX_AGE_DAYS = 60
FRAUD_PATTERNS = ["frais de dossier", "frais d'inscription", "payer pour postuler", "western union", "moneygram",
                  "pay a fee", "application fee", "registration fee", "send money", "telegram only", "whatsapp uniquement",
                  "gagnez 5000", "earn $5000 per week", "no experience needed, earn"]


def _fraud_reason(text: str) -> str | None:
    t = strip_accents(text.lower())
    for p in FRAUD_PATTERNS:
        if strip_accents(p) in t:
            return p
    return None


def _opp_fingerprint(r: RawOpportunity) -> str:
    if r.company_name and r.title:
        return fingerprint(r.title, r.company_name)
    if r.external_id or r.source_url:
        return fingerprint(r.external_id or r.source_url)
    return fingerprint(r.title, r.description[:800])


def upsert_opportunity(db: Session, r: RawOpportunity, profile_key: str) -> tuple[Opportunity | None, str]:
    """Retourne (opportunité, statut) avec statut ∈ created | duplicate | expired | fraud."""
    nowdt = now()
    r.title, r.company_name, r.description = fix_mojibake(r.title), fix_mojibake(r.company_name), fix_mojibake(r.description)
    if r.deadline and r.deadline < nowdt:
        return None, "expired"
    if r.published_at and r.published_at < nowdt - timedelta(days=MAX_AGE_DAYS) and not r.needs_verification:
        return None, "expired"
    if _fraud_reason(r.title + " " + r.description):
        return None, "fraud"
    fp = _opp_fingerprint(r)
    existing = db.query(Opportunity).filter_by(fingerprint=fp).one_or_none()
    if existing is None and r.company_name:
        # doublon inter-sources : même entreprise, intitulé quasi identique
        for o in db.query(Opportunity).filter(Opportunity.company_name.ilike(r.company_name)).limit(50):
            if fuzz.token_set_ratio(normalize_name(o.title), normalize_name(r.title)) >= 92:
                existing = o
                break
    if existing:
        existing.last_checked_at = nowdt
        return existing, "duplicate"
    opp = Opportunity(
        kind=r.kind, profile_key="kortex" if r.kind == "b2b" else profile_key, title=r.title[:400],
        company_name=r.company_name[:300], description=r.description, skills=r.skills[:30], contract_type=r.contract_type[:80],
        salary=r.salary[:200], currency=r.currency, location=r.location[:300], remote=r.remote, language=r.language,
        published_at=r.published_at, deadline=r.deadline, apply_url=r.apply_url[:800], source=r.source[:100],
        source_url=r.source_url[:800], external_id=r.external_id[:200], fingerprint=fp,
        needs_verification=r.needs_verification, status="decouverte" if not r.needs_verification else "a_qualifier",
    )
    db.add(opp)
    db.flush()
    return opp, "created"


def apply_heuristic(opp: Opportunity) -> None:
    a = heuristic_opportunity(opp, opp.profile_key)
    opp.analysis, opp.score = a, a["total"]


def run_opportunity_search(db: Session, connector_names: list[str], params: SearchParams) -> list[SearchRun]:
    runs = []
    for name in connector_names:
        conn = CONNECTORS.get(name)
        run = SearchRun(target="opportunities", connector=name, params=params.__dict__.copy())
        db.add(run)
        db.flush()
        if conn is None or not conn.available():
            run.status, run.message = "error", f"Connecteur « {name} » indisponible ({conn.requires if conn else 'inconnu'} manquant ?)"
        else:
            try:
                raws = conn.search(params)
                stats = {"created": 0, "duplicate": 0, "expired": 0, "fraud": 0}
                for r in raws:
                    if params.kind and r.kind != params.kind and name == "tavily":
                        r.kind = params.kind
                    opp, st = upsert_opportunity(db, r, params.profile_key)
                    if st == "created":
                        apply_heuristic(opp)
                    stats[st] += 1
                run.found, run.created, run.duplicates = len(raws), stats["created"], stats["duplicate"]
                run.status = "done"
                run.message = f"{stats['expired']} expirée(s) et {stats['fraud']} suspecte(s) écartée(s)"
            except Exception as e:
                run.status, run.message = "error", f"{type(e).__name__}: {e}"[:1000]
        run.finished_at = now()
        db.commit()
        runs.append(run)
    return runs


# ---------- Entreprises ----------

def upsert_company(db: Session, rc: RawCompany, profile_key: str = "kortex") -> tuple[Company, bool]:
    dom = domain_of(rc.website)
    q = db.query(Company)
    existing = (q.filter_by(domain=dom).first() if dom else None) or q.filter_by(normalized_name=normalize_name(rc.name)).first()
    if existing:
        return existing, False
    c = Company(name=rc.name[:300], normalized_name=normalize_name(rc.name), domain=dom, website=rc.website,
                sector=rc.sector, country=rc.country, city=rc.city, description=rc.description,
                source_url=rc.source_url[:800], source_name=rc.source, profile_key=profile_key, status="a_qualifier")
    db.add(c)
    db.flush()
    return c, True


EXTRACT_COMPANIES_SYSTEM = """Tu extrais des entreprises RÉELLES citées dans des résultats de recherche web.
N'invente rien : une entreprise doit être nommée dans les résultats. Le site web n'est renseigné que si son URL ou son
domaine apparaît dans les résultats ; sinon null. Exclus les annuaires, médias, réseaux sociaux et plateformes d'emploi."""


def _llm_extract_companies(results: list[dict], params: SearchParams) -> list[RawCompany]:
    blob = json.dumps([{"url": r.get("url"), "title": r.get("title"), "content": (r.get("content") or "")[:1500]} for r in results], ensure_ascii=False)
    data = llm.chat_json(EXTRACT_COMPANIES_SYSTEM, f"""Recherche : secteur « {params.sector} », lieu « {params.city} {params.country} », mots-clés « {params.query} ».
Résultats :\n{blob}\n\nRéponds : {{"companies": [{{"name": str, "website": str|null, "sector": str, "city": str, "country": str, "description": str, "source_url": "URL du résultat qui la cite"}}]}}""", max_tokens=3000)
    haystack = blob.lower()
    out = []
    for c in data.get("companies", []):
        site = c.get("website")
        dom = domain_of(site) if site else None
        if dom and dom not in haystack:
            site = None  # domaine non présent dans les sources : on ne le garde pas
        if c.get("name"):
            out.append(RawCompany(name=c["name"], website=site, source="Tavily + extraction IA", source_url=c.get("source_url") or "",
                                  sector=c.get("sector") or params.sector, country=c.get("country") or params.country,
                                  city=c.get("city") or params.city, description=c.get("description") or ""))
    return out


def run_company_search(db: Session, params: SearchParams) -> SearchRun:
    run = SearchRun(target="companies", connector="tavily", params=params.__dict__.copy())
    db.add(run)
    db.flush()
    try:
        query, results = search_companies_raw(params)
        raws = _llm_extract_companies(results, params) if llm.get_settings().llm_configured else companies_from_results(results, params)
        created = 0
        for rc in raws:
            _, is_new = upsert_company(db, rc)
            created += is_new
        run.found, run.created, run.duplicates = len(raws), created, len(raws) - created
        run.status, run.message = "done", f"Requête : {query}"
    except Exception as e:
        run.status, run.message = "error", f"{type(e).__name__}: {e}"[:1000]
    run.finished_at = now()
    db.commit()
    return run


def scan_company(db: Session, company: Company) -> dict:
    if not company.website:
        return {"ok": False, "message": "Aucun site web connu pour cette entreprise."}
    scan = scan_website(company.website)
    added = 0
    existing = {(c.kind, c.value) for c in company.contacts}
    for fc in scan.contacts:
        if (fc.kind, fc.value) in existing:
            continue
        company.contacts.append(Contact(kind=fc.kind, value=fc.value, label=fc.label, confidence=fc.confidence, source_url=fc.source_url))
        added += 1
    if not company.description and scan.description:
        company.description = scan.description
    elif scan.text_sample and len(company.description) < 200:
        company.description = (company.description + "\n\n" + scan.text_sample[:1500]).strip()
    if scan.pages_visited:
        company.verified_at = now()
    db.commit()
    return {"ok": bool(scan.pages_visited), "pages_visited": scan.pages_visited, "blocked": scan.blocked, "contacts_added": added}


# ---------- Import manuel d'une annonce (texte collé ou URL) ----------

EXTRACT_OPP_SYSTEM = """Tu extrais les informations d'une annonce d'emploi / mission. N'invente rien : champ absent = chaîne vide ou null.
Dates au format ISO (YYYY-MM-DD)."""


def parse_posting(text: str, url: str = "") -> RawOpportunity:
    data = llm.chat_json(EXTRACT_OPP_SYSTEM, f"""URL : {url}\nTEXTE :\n{text[:12000]}\n
Réponds : {{"title": str, "company_name": str, "description": "description complète nettoyée", "skills": [str],
"contract_type": str, "salary": str, "currency": str, "location": str, "remote": bool|null, "language": "fr"|"en",
"published_at": str|null, "deadline": str|null, "apply_url": str, "kind": "job"|"freelance"|"b2b",
"looks_fraudulent": bool, "fraud_reason": str}}""", max_tokens=3500)

    def dt(v):
        if not v:
            return None
        try:
            d = datetime.fromisoformat(str(v)[:10])
            return d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return RawOpportunity(
        title=data.get("title") or "Annonce sans titre", company_name=data.get("company_name") or "",
        source="Import manuel" if not url else f"Import · {domain_of(url)}", source_url=url, apply_url=data.get("apply_url") or url,
        external_id=f"manual:{url}" if url else "", description=data.get("description") or text,
        skills=[s for s in data.get("skills") or [] if isinstance(s, str)], contract_type=data.get("contract_type") or "",
        salary=data.get("salary") or "", currency=data.get("currency") or "", location=data.get("location") or "",
        remote=data.get("remote"), language=data.get("language") or "", published_at=dt(data.get("published_at")),
        deadline=dt(data.get("deadline")), kind=data.get("kind") if data.get("kind") in ("job", "freelance", "b2b") else "job",
    ), data


def simple_parse(text: str, url: str, title: str, company: str, kind: str) -> RawOpportunity:
    """Import sans LLM : l'utilisateur fournit titre / entreprise, la description est le texte collé."""
    return RawOpportunity(title=title or (text.strip().splitlines() or ["Annonce"])[0][:200], company_name=company,
                          source="Import manuel", source_url=url, apply_url=url, external_id=f"manual:{url}" if url else "",
                          description=text, kind=kind, remote=bool(re.search(r"remote|t[ée]l[ée]travail", text, re.I)) or None)
