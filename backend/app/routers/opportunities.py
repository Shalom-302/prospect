from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Activity, Application, GeneratedDocument, Opportunity, now
from ..services import llm
from ..services.ingest import apply_heuristic, parse_posting, simple_parse, upsert_opportunity
from ..services.polite_http import FetchBlocked, fetch
from ..services.qualification import llm_opportunity
from ..services.textutil import html_to_text
from .common import activity_out, app_out, change_status, gen_out, get_or_404, log, opp_out, profiles_map

router = APIRouter(prefix="/api/opportunities", tags=["opportunités"])


@router.get("")
def list_opportunities(kind: str | None = None, status: str | None = None, profile_key: str | None = None,
                       q: str | None = None, min_score: float | None = None, remote: bool | None = None,
                       source: str | None = None, verified_only: bool = False, sort: str = "score",
                       limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    qry = db.query(Opportunity)
    if kind:
        qry = qry.filter(Opportunity.kind.in_(kind.split(",")))
    if status:
        qry = qry.filter(Opportunity.status.in_(status.split(",")))
    else:
        qry = qry.filter(Opportunity.status != "archive")
    if profile_key:
        qry = qry.filter(Opportunity.profile_key == profile_key)
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(Opportunity.title.ilike(like), Opportunity.company_name.ilike(like), Opportunity.description.ilike(like), Opportunity.location.ilike(like)))
    if min_score is not None:
        qry = qry.filter(Opportunity.score >= min_score)
    if remote is not None:
        qry = qry.filter(Opportunity.remote == remote)
    if source:
        qry = qry.filter(Opportunity.source.ilike(f"%{source}%"))
    if verified_only:
        qry = qry.filter(Opportunity.needs_verification.is_(False))
    order = {"score": Opportunity.score.desc().nulls_last(), "date": Opportunity.published_at.desc().nulls_last(),
             "collected": Opportunity.collected_at.desc()}.get(sort, Opportunity.score.desc().nulls_last())
    total = qry.count()
    items = qry.order_by(order, Opportunity.id.desc()).offset(offset).limit(min(limit, 500)).all()
    return {"total": total, "items": [opp_out(o) for o in items]}


@router.get("/{opp_id}")
def get_opportunity(opp_id: int, db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, opp_id)
    d = opp_out(o, full=True)
    d["generated"] = [gen_out(g) for g in db.query(GeneratedDocument).filter_by(opportunity_id=o.id).order_by(GeneratedDocument.created_at.desc())]
    d["applications"] = [app_out(a) for a in db.query(Application).filter_by(opportunity_id=o.id).order_by(Application.created_at.desc())]
    d["activities"] = [activity_out(a) for a in db.query(Activity).filter_by(opportunity_id=o.id).order_by(Activity.occurred_at.desc())]
    return d


class OppPatch(BaseModel):
    status: str | None = None
    notes: str | None = None
    next_action: str | None = None
    next_action_date: datetime | None = None
    profile_key: str | None = None
    kind: str | None = None
    company_id: int | None = None
    language: str | None = None
    deadline: datetime | None = None
    needs_verification: bool | None = None


@router.patch("/{opp_id}")
def patch_opportunity(opp_id: int, body: OppPatch, db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, opp_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        change_status(db, o, data.pop("status"))
    for k, v in data.items():
        setattr(o, k, v)
    db.commit()
    return opp_out(o, full=True)


@router.delete("/{opp_id}")
def delete_opportunity(opp_id: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Opportunity, opp_id))
    db.commit()
    return {"ok": True}


class ImportBody(BaseModel):
    url: str = ""
    text: str = ""
    title: str = ""
    company_name: str = ""
    kind: str = "job"
    profile_key: str = "shalom"


@router.post("/import")
def import_posting(body: ImportBody, db: Session = Depends(get_db)):
    """Import d'une annonce : texte collé (LinkedIn, Indeed…) et/ou URL d'une page publique."""
    text = body.text.strip()
    if not text and body.url:
        try:
            text = html_to_text(fetch(body.url).text)
        except FetchBlocked as e:
            raise HTTPException(422, f"{e}. Copiez le texte de l'annonce et collez-le ici.")
    if not text:
        raise HTTPException(422, "Fournir le texte de l'annonce ou une URL accessible.")
    extra = {}
    if llm.get_settings().llm_configured:
        raw, extra = parse_posting(text, body.url)
        if body.kind and body.kind != "job":
            raw.kind = body.kind
    else:
        raw = simple_parse(text, body.url, body.title, body.company_name, body.kind)
    opp, st = upsert_opportunity(db, raw, body.profile_key)
    if st == "fraud" or extra.get("looks_fraudulent"):
        db.rollback()
        raise HTTPException(422, f"Annonce écartée : signaux de fraude ({extra.get('fraud_reason') or 'demande de paiement / contact suspect'}).")
    if st == "expired":
        raise HTTPException(422, "Annonce écartée : date limite dépassée ou publication trop ancienne.")
    if st == "created":
        apply_heuristic(opp)
        log(db, "note", f"Annonce importée ({raw.source})", opportunity_id=opp.id)
    db.commit()
    return {"status": st, "opportunity": opp_out(opp, full=True)}


@router.post("/{opp_id}/fetch")
def fetch_full_posting(opp_id: int, db: Session = Depends(get_db)):
    """Pour un résultat web : récupère la page publique et en extrait l'annonce complète."""
    o = get_or_404(db, Opportunity, opp_id)
    if not o.source_url:
        raise HTTPException(422, "Pas d'URL source.")
    try:
        text = html_to_text(fetch(o.source_url).text)
    except FetchBlocked as e:
        raise HTTPException(422, f"{e}. Ouvrez l'annonce et collez son texte via « Importer ».")
    if llm.get_settings().llm_configured:
        raw, extra = parse_posting(text, o.source_url)
        for field in ("title", "company_name", "description", "skills", "contract_type", "salary", "currency", "location",
                      "remote", "language", "published_at", "deadline", "apply_url"):
            val = getattr(raw, field)
            if val not in (None, "", []):
                setattr(o, field, val)
        if extra.get("looks_fraudulent"):
            o.notes = (o.notes + f"\n⚠ Signal de fraude : {extra.get('fraud_reason')}").strip()
    else:
        o.description = text[:15000]
    o.needs_verification = False
    o.last_checked_at = now()
    if o.deadline and o.deadline < now():
        change_status(db, o, "archive")
        o.notes = (o.notes + "\nArchivée automatiquement : date limite dépassée.").strip()
    apply_heuristic(o)
    log(db, "note", "Annonce complète récupérée depuis la source", opportunity_id=o.id)
    db.commit()
    return opp_out(o, full=True)


@router.post("/{opp_id}/qualify")
def qualify_opportunity(opp_id: int, method: str = "auto", db: Session = Depends(get_db)):
    o = get_or_404(db, Opportunity, opp_id)
    use_llm = method == "llm" or (method == "auto" and llm.get_settings().llm_configured)
    if use_llm:
        try:
            a = llm_opportunity(o, profiles_map(db))
        except llm.LLMNotConfigured as e:
            raise HTTPException(503, str(e))
        except Exception as e:
            raise HTTPException(502, f"Échec de l'analyse IA : {type(e).__name__}: {e}")
        o.analysis, o.score = a, a["total"]
        if a.get("recommended_profile") in ("shalom", "kortex"):
            o.profile_key = a["recommended_profile"]
        if a.get("language") in ("fr", "en") and not o.language:
            o.language = a["language"]
    else:
        apply_heuristic(o)
    if o.status in ("decouverte", "a_qualifier"):
        change_status(db, o, "pertinent" if (o.score or 0) >= 60 else "a_qualifier")
    log(db, "note", f"Qualification ({o.analysis.get('method')}) : {o.score:.0f}/100", opportunity_id=o.id)
    db.commit()
    return opp_out(o, full=True)
