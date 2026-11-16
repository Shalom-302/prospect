from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..connectors.base import RawCompany
from ..db import get_db
from ..models import Activity, Application, Company, Contact, GeneratedDocument, Opportunity
from ..services import llm
from ..services.ingest import scan_company, upsert_company
from ..services.qualification import heuristic_company, llm_company
from ..services.textutil import domain_of, normalize_name
from .common import activity_out, app_out, change_status, company_out, contact_out, gen_out, get_or_404, log, opp_out, profiles_map

router = APIRouter(prefix="/api/companies", tags=["entreprises"])
contacts_router = APIRouter(prefix="/api/contacts", tags=["entreprises"])


@router.get("")
def list_companies(q: str | None = None, status: str | None = None, country: str | None = None, city: str | None = None,
                   sector: str | None = None, has_email: bool = False, min_score: float | None = None,
                   sort: str = "score", limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    qry = db.query(Company).options(selectinload(Company.contacts))
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(Company.name.ilike(like), Company.description.ilike(like), Company.domain.ilike(like)))
    if status:
        qry = qry.filter(Company.status.in_(status.split(",")))
    else:
        qry = qry.filter(Company.status != "archive")
    for col, val in ((Company.country, country), (Company.city, city), (Company.sector, sector)):
        if val:
            qry = qry.filter(col.ilike(f"%{val}%"))
    if has_email:
        qry = qry.filter(Company.contacts.any(Contact.kind == "email"))
    if min_score is not None:
        qry = qry.filter(Company.score >= min_score)
    order = {"score": Company.score.desc().nulls_last(), "name": Company.name.asc(), "collected": Company.collected_at.desc()}.get(sort, Company.score.desc().nulls_last())
    total = qry.count()
    return {"total": total, "items": [company_out(c) for c in qry.order_by(order, Company.id.desc()).offset(offset).limit(min(limit, 500))]}


class CompanyIn(BaseModel):
    name: str
    website: str | None = None
    sector: str = ""
    country: str = "Côte d'Ivoire"
    city: str = ""
    address: str = ""
    description: str = ""
    source_url: str = ""
    scan: bool = True


@router.post("")
def create_company(body: CompanyIn, db: Session = Depends(get_db)):
    website = body.website.strip() if body.website else None
    if website and "://" not in website:
        website = "https://" + website
    c, created = upsert_company(db, RawCompany(name=body.name, website=website, source="Saisie manuelle",
                                               source_url=body.source_url or (website or ""), sector=body.sector,
                                               country=body.country, city=body.city, description=body.description))
    if body.address:
        c.address = body.address
    db.commit()
    scan = scan_company(db, c) if created and body.scan and website else None
    if created:
        a = heuristic_company(c)
        c.analysis, c.score = a, a["total"]
        db.commit()
    return {"created": created, "company": company_out(c, full=True), "scan": scan}


@router.get("/{company_id}")
def get_company(company_id: int, db: Session = Depends(get_db)):
    c = get_or_404(db, Company, company_id)
    d = company_out(c, full=True)
    d["opportunities"] = [opp_out(o) for o in db.query(Opportunity).filter_by(company_id=c.id)]
    d["generated"] = [gen_out(g) for g in db.query(GeneratedDocument).filter_by(company_id=c.id).order_by(GeneratedDocument.created_at.desc())]
    d["applications"] = [app_out(a) for a in db.query(Application).filter_by(company_id=c.id).order_by(Application.created_at.desc())]
    d["activities"] = [activity_out(a) for a in db.query(Activity).filter_by(company_id=c.id).order_by(Activity.occurred_at.desc())]
    return d


class CompanyPatch(BaseModel):
    name: str | None = None
    website: str | None = None
    sector: str | None = None
    country: str | None = None
    city: str | None = None
    address: str | None = None
    description: str | None = None
    notes: str | None = None
    status: str | None = None
    next_action: str | None = None
    next_action_date: datetime | None = None


@router.patch("/{company_id}")
def patch_company(company_id: int, body: CompanyPatch, db: Session = Depends(get_db)):
    c = get_or_404(db, Company, company_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        change_status(db, c, data.pop("status"))
    if "name" in data:
        c.normalized_name = normalize_name(data["name"])
    if "website" in data:
        c.domain = domain_of(data["website"])
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    return company_out(c, full=True)


@router.delete("/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Company, company_id))
    db.commit()
    return {"ok": True}


@router.post("/{company_id}/scan")
def scan(company_id: int, db: Session = Depends(get_db)):
    c = get_or_404(db, Company, company_id)
    res = scan_company(db, c)
    log(db, "note", f"Site scanné : {res.get('contacts_added', 0)} contact(s) ajouté(s)", company_id=c.id)
    db.commit()
    return {**res, "company": company_out(c, full=True)}


@router.post("/{company_id}/qualify")
def qualify(company_id: int, method: str = "auto", db: Session = Depends(get_db)):
    c = get_or_404(db, Company, company_id)
    if method == "llm" or (method == "auto" and llm.get_settings().llm_configured):
        try:
            a = llm_company(c, profiles_map(db))
        except llm.LLMNotConfigured as e:
            raise HTTPException(503, str(e))
        except Exception as e:
            raise HTTPException(502, f"Échec de l'analyse IA : {type(e).__name__}: {e}")
    else:
        a = heuristic_company(c)
    c.analysis, c.score = a, a["total"]
    if c.status in ("decouverte", "a_qualifier"):
        change_status(db, c, "pertinent" if c.score >= 60 else "a_qualifier")
    log(db, "note", f"Qualification ({a['method']}) : {c.score:.0f}/100", company_id=c.id)
    db.commit()
    return company_out(c, full=True)


class ContactIn(BaseModel):
    kind: str = "email"
    value: str
    label: str = "general"
    person_name: str = ""
    confidence: str = "estimated"
    source_url: str = ""


@router.post("/{company_id}/contacts")
def add_contact(company_id: int, body: ContactIn, db: Session = Depends(get_db)):
    c = get_or_404(db, Company, company_id)
    if body.confidence == "verified" and not body.source_url:
        raise HTTPException(422, "Un contact « vérifié » doit indiquer l'URL où il est publié.")
    ct = Contact(company_id=c.id, **body.model_dump())
    db.add(ct)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ce contact existe déjà.")
    return contact_out(ct)


class ContactPatch(BaseModel):
    label: str | None = None
    person_name: str | None = None
    confidence: str | None = None
    source_url: str | None = None


@contacts_router.patch("/{contact_id}")
def patch_contact(contact_id: int, body: ContactPatch, db: Session = Depends(get_db)):
    ct = get_or_404(db, Contact, contact_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(ct, k, v)
    db.commit()
    return contact_out(ct)


@contacts_router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Contact, contact_id))
    db.commit()
    return {"ok": True}


@router.post("/{company_id}/find-website")
def find_website(company_id: int, db: Session = Depends(get_db)):
    """Propose des sites candidats via la recherche web. Rien n'est enregistré : l'utilisateur choisit."""
    from ..connectors.tavily import NON_COMPANY_DOMAINS, TavilyNotConfigured, tavily_search

    c = get_or_404(db, Company, company_id)
    try:
        results = tavily_search(f"{c.name} {c.city} {c.country} site officiel", max_results=8)
    except TavilyNotConfigured as e:
        raise HTTPException(503, str(e))
    out, seen = [], set()
    for r in results:
        d = domain_of(r.get("url"))
        if not d or d in seen or any(d == n or d.endswith("." + n) for n in NON_COMPANY_DOMAINS) or d.endswith((".gouv.ci", "cb-umoa.org")):
            continue
        seen.add(d)
        out.append({"domain": d, "url": f"https://{d}", "title": r.get("title", ""), "snippet": (r.get("content") or "")[:200]})
    return out[:5]
