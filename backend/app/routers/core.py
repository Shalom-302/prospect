import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import PIPELINE_LABELS, Activity, Application, Company, Contact, Credential, Document, GeneratedDocument, Opportunity, Profile, now
from ..services import llm
from ..services.mail import ZohoError, zoho_authorize_url, zoho_configured, zoho_exchange_code, zoho_status
from .common import activity_out, company_out, get_or_404, log, opp_out

router = APIRouter(prefix="/api", tags=["général"])


# ---------- Profils ----------

@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db)):
    return [{"key": p.key, "display_name": p.display_name, "kind": p.kind, "data": p.data} for p in db.query(Profile).order_by(Profile.id)]


@router.put("/profiles/{key}")
def update_profile(key: str, body: dict, db: Session = Depends(get_db)):
    p = db.query(Profile).filter_by(key=key).one_or_none()
    if not p:
        raise HTTPException(404, "Profil introuvable")
    if "data" in body and isinstance(body["data"], dict):
        p.data = body["data"]
    if body.get("display_name"):
        p.display_name = body["display_name"]
    db.commit()
    return {"key": p.key, "display_name": p.display_name, "kind": p.kind, "data": p.data}


# ---------- Pipeline / CRM ----------

@router.get("/pipeline/statuses")
def statuses():
    return [{"key": k, "label": v} for k, v in PIPELINE_LABELS.items()]


@router.get("/pipeline")
def pipeline(profile_key: str | None = None, db: Session = Depends(get_db)):
    """Vue kanban : opportunités + entreprises (prospects B2B) par statut."""
    cols = {k: [] for k in PIPELINE_LABELS}
    oq = db.query(Opportunity).filter(Opportunity.status != "decouverte")
    cq = db.query(Company).filter(Company.status != "decouverte")
    if profile_key:
        oq = oq.filter_by(profile_key=profile_key)
        cq = cq.filter_by(profile_key=profile_key)
    for o in oq.order_by(Opportunity.score.desc().nulls_last()).limit(600):
        cols[o.status].append({"type": "opportunity", "id": o.id, "title": o.title, "subtitle": o.company_name, "score": o.score,
                               "kind": o.kind, "profile_key": o.profile_key, "next_action": o.next_action,
                               "next_action_date": o.next_action_date.isoformat() if o.next_action_date else None})
    for c in cq.order_by(Company.score.desc().nulls_last()).limit(600):
        cols[c.status].append({"type": "company", "id": c.id, "title": c.name, "subtitle": " · ".join(x for x in [c.sector, c.city] if x),
                               "score": c.score, "kind": "b2b", "profile_key": c.profile_key, "next_action": c.next_action,
                               "next_action_date": c.next_action_date.isoformat() if c.next_action_date else None})
    return [{"key": k, "label": PIPELINE_LABELS[k], "items": v} for k, v in cols.items()]


class ActivityIn(BaseModel):
    type: str = "note"  # note | reply | meeting | follow_up | interview
    summary: str
    company_id: int | None = None
    opportunity_id: int | None = None
    application_id: int | None = None
    occurred_at: datetime | None = None
    set_status: str | None = None


@router.post("/activities")
def add_activity(body: ActivityIn, db: Session = Depends(get_db)):
    from .common import change_status
    log(db, body.type, body.summary, body.company_id, body.opportunity_id, body.application_id, body.occurred_at)
    auto = {"reply": "reponse_recue", "meeting": "rdv_programme", "interview": "entretien_realise"}.get(body.type)
    new_status = body.set_status or auto
    if new_status:
        for model, id_ in ((Opportunity, body.opportunity_id), (Company, body.company_id)):
            obj = db.get(model, id_) if id_ else None
            if obj:
                change_status(db, obj, new_status)
    db.commit()
    return {"ok": True}


@router.get("/activities")
def list_activities(limit: int = 50, db: Session = Depends(get_db)):
    return [activity_out(a) for a in db.query(Activity).order_by(Activity.occurred_at.desc()).limit(limit)]


# ---------- Dashboard ----------

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    def count(q):
        return q.scalar() or 0

    since = now() - timedelta(days=1)
    stats = {
        "companies": count(db.query(func.count(Company.id))),
        "jobs": count(db.query(func.count(Opportunity.id)).filter(Opportunity.kind == "job", Opportunity.status != "archive")),
        "freelance": count(db.query(func.count(Opportunity.id)).filter(Opportunity.kind == "freelance", Opportunity.status != "archive")),
        "b2b_prospects": count(db.query(func.count(Company.id)).filter(Company.status.notin_(["decouverte", "archive", "refuse"])))
                         + count(db.query(func.count(Opportunity.id)).filter(Opportunity.kind == "b2b", Opportunity.status != "archive")),
        "emails_found": count(db.query(func.count(Contact.id)).filter(Contact.kind == "email")),
        "emails_verified": count(db.query(func.count(Contact.id)).filter(Contact.kind == "email", Contact.confidence == "verified")),
        "letters_generated": count(db.query(func.count(GeneratedDocument.id)).filter(GeneratedDocument.doc_type.in_(["cover_letter", "b2b_proposal"]))),
        "applications_prepared": count(db.query(func.count(Application.id))),
        "applications_sent": count(db.query(func.count(Application.id)).filter(Application.status == "envoyee")),
        "replies": count(db.query(func.count(Activity.id)).filter(Activity.type == "reply")),
        "meetings": count(db.query(func.count(Activity.id)).filter(Activity.type == "meeting")),
        "new_last_24h": count(db.query(func.count(Opportunity.id)).filter(Opportunity.collected_at >= since)),
    }
    top = (db.query(Opportunity).filter(Opportunity.status.in_(["decouverte", "a_qualifier", "pertinent", "lettre_a_generer", "pret_a_postuler"]))
           .order_by(Opportunity.score.desc().nulls_last()).limit(8).all())
    top_companies = (db.query(Company).filter(Company.status.in_(["a_qualifier", "pertinent", "lettre_a_generer", "pret_a_postuler"]))
                     .order_by(Company.score.desc().nulls_last()).limit(6).all())
    due = []
    horizon = now() + timedelta(days=3)
    for o in db.query(Opportunity).filter(Opportunity.next_action_date.isnot(None), Opportunity.next_action_date <= horizon).limit(20):
        due.append({"type": "opportunity", "id": o.id, "title": o.title, "action": o.next_action, "date": o.next_action_date.isoformat()})
    for c in db.query(Company).filter(Company.next_action_date.isnot(None), Company.next_action_date <= horizon).limit(20):
        due.append({"type": "company", "id": c.id, "title": c.name, "action": c.next_action, "date": c.next_action_date.isoformat()})
    deadlines = [opp_out(o) for o in db.query(Opportunity).filter(Opportunity.deadline.isnot(None), Opportunity.deadline >= now(),
                 Opportunity.deadline <= now() + timedelta(days=7), Opportunity.status.notin_(["archive", "refuse", "envoyee_manuellement"]))
                 .order_by(Opportunity.deadline).limit(10)]
    return {"stats": stats, "top_opportunities": [opp_out(o) for o in top], "top_companies": [company_out(c) for c in top_companies],
            "due_actions": sorted(due, key=lambda x: x["date"]), "deadlines": deadlines,
            "recent_activity": [activity_out(a) for a in db.query(Activity).order_by(Activity.occurred_at.desc()).limit(12)]}


# ---------- Paramètres ----------

@router.get("/settings/status")
def settings_status(db: Session = Depends(get_db)):
    s = get_settings()
    return {
        "llm": {"configured": s.llm_configured, "base_url": s.llm_base_url, "model": s.llm_model},
        "tavily": {"configured": bool(s.tavily_api_key)},
        "zoho": zoho_status(db),
        "secret_key": bool(s.secret_key),
        "documents": db.query(func.count(Document.id)).scalar(),
        "rules": [
            "Aucun email n'est envoyé par l'application : brouillons uniquement.",
            "Aucune pièce jointe sans validation explicite.",
            "Aucun envoi en masse : une candidature = une action manuelle.",
            "Collecte limitée aux API, flux publics et pages autorisées par robots.txt.",
        ],
    }


@router.post("/settings/llm-test")
def llm_test():
    try:
        out = llm.chat("Tu réponds en un mot.", "Réponds simplement : OK", max_tokens=10)
        return {"ok": True, "model": llm.model_name(), "reply": out}
    except llm.LLMNotConfigured as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"{type(e).__name__}: {e}")


# ---------- Email (Zoho OAuth) ----------

_oauth_states: set[str] = set()


@router.get("/email/status")
def email_status(db: Session = Depends(get_db)):
    return zoho_status(db)


@router.get("/email/zoho/authorize")
def zoho_authorize():
    if not zoho_configured():
        raise HTTPException(422, "Renseigner ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET et SECRET_KEY dans .env")
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    return {"url": zoho_authorize_url(state)}


@router.get("/email/zoho/callback", response_class=HTMLResponse)
def zoho_callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    front = get_settings().frontend_origin.split(",")[0].strip()
    if error or state not in _oauth_states:
        return HTMLResponse(f"<p>Connexion Zoho refusée ou invalide ({error or 'state'}). <a href='{front}/email'>Retour</a></p>", 400)
    _oauth_states.discard(state)
    try:
        zoho_exchange_code(db, code)
    except (ZohoError, Exception) as e:
        return HTMLResponse(f"<p>Échec : {e}. <a href='{front}/email'>Retour</a></p>", 400)
    return HTMLResponse(f"<script>location.href='{front}/email?connected=1'</script>")


@router.delete("/email/zoho")
def zoho_disconnect(db: Session = Depends(get_db)):
    db.query(Credential).filter_by(provider="zoho").delete()
    db.commit()
    return {"ok": True}


__all__ = ["router", "get_or_404", "log"]
