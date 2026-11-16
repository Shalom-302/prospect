"""Envoi par lots : constitution → génération → relecture → validation unique → envoi étalé par le worker."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..models import Application, Campaign, Company, Opportunity, Profile, Suppression, now
from ..services import llm
from ..services import outreach as o
from .common import get_or_404, iso

router = APIRouter(prefix="/api/campaigns", tags=["campagnes"])
outreach_router = APIRouter(prefix="/api/outreach", tags=["campagnes"])
public_router = APIRouter(prefix="/api/public", tags=["public"])
log = logging.getLogger("prospect.campaigns")


def item_out(a: Application, db: Session) -> dict:
    c = db.get(Company, a.company_id) if a.company_id else None
    opp = db.get(Opportunity, a.opportunity_id) if a.opportunity_id else None
    return {"id": a.id, "status": a.status, "recipient": a.recipient, "subject": a.subject, "body": a.body, "error": a.error,
            "delivery": a.delivery, "sent_at": iso(a.sent_at), "company_id": a.company_id, "opportunity_id": a.opportunity_id,
            "target": c.name if c else (opp.company_name if opp else ""), "target_title": opp.title if opp else (c.sector if c else ""),
            "warnings": o.lint(a.subject, a.body, c.name if c else (opp.company_name if opp else "")) if a.status in ("brouillon", "approuvee") else []}


def campaign_out(c: Campaign, db: Session, items: bool = False) -> dict:
    rows = db.query(Application).filter_by(campaign_id=c.id).all()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
    d = {"id": c.id, "name": c.name, "profile_key": c.profile_key, "language": c.language, "instructions": c.instructions,
         "attachment_ids": c.attachment_ids, "status": c.status, "paused_reason": c.paused_reason, "next_send_at": iso(c.next_send_at),
         "approved_at": iso(c.approved_at), "created_at": iso(c.created_at), "total": len(rows), "counts": counts,
         "replies": sum(1 for r in rows if r.delivery == "replied"), "bounces": sum(1 for r in rows if r.delivery == "bounced")}
    if items:
        d["items"] = [item_out(r, db) for r in sorted(rows, key=lambda x: x.id)]
    return d


class CampaignIn(BaseModel):
    name: str
    profile_key: str = "kortex"
    language: str = "fr"
    instructions: str = ""
    company_ids: list[int] = Field(default_factory=list)
    opportunity_ids: list[int] = Field(default_factory=list)
    attachment_ids: list[int] = Field(default_factory=list)


def _generate(campaign_id: int):
    with SessionLocal() as db:
        camp = db.get(Campaign, campaign_id)
        profile = db.query(Profile).filter_by(key=camp.profile_key).one()
        for a in db.query(Application).filter_by(campaign_id=camp.id, status="brouillon").order_by(Application.id):
            if a.body:
                continue
            company = db.get(Company, a.company_id) if a.company_id else None
            opp = db.get(Opportunity, a.opportunity_id) if a.opportunity_id else None
            try:
                out = o.generate_cold_email(profile, company, opp, camp.language, camp.instructions)
                a.subject, a.body = out["subject"], out["body"] + "\n\n" + o.signature(profile, camp.language)
            except Exception as e:
                a.status, a.error = "ignoree", f"Génération impossible : {type(e).__name__}: {e}"[:800]
            db.commit()
        camp.status = "review"
        db.commit()


@router.post("")
def create_campaign(body: CampaignIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not llm.get_settings().llm_configured:
        raise HTTPException(503, "LLM non configuré : la personnalisation de chaque email est obligatoire.")
    if not (body.company_ids or body.opportunity_ids):
        raise HTTPException(422, "Sélectionner au moins une entreprise ou une opportunité.")
    camp = Campaign(name=body.name, profile_key=body.profile_key, language=body.language, instructions=body.instructions,
                    attachment_ids=body.attachment_ids, status="generating")
    db.add(camp)
    db.flush()
    seen_recipients: set[str] = set()
    targets = [(db.get(Company, i), None) for i in body.company_ids]
    for oid in body.opportunity_ids:
        opp = db.get(Opportunity, oid)
        if opp:
            targets.append((opp.company, opp))
    for company, opp in targets:
        if company is None and opp is None:
            continue
        recipient = o.pick_recipient(company, job=body.profile_key == "shalom")[0] if company else ""
        reason = o.eligibility(db, company, recipient)
        if not reason and recipient.lower() in seen_recipients:
            reason = "Même destinataire déjà présent dans ce lot."
        seen_recipients.add(recipient.lower())
        db.add(Application(profile_key=body.profile_key, campaign_id=camp.id, company_id=company.id if company else None,
                           opportunity_id=opp.id if opp else None, channel="email", recipient=recipient,
                           status="ignoree" if reason else "brouillon", error=reason or "", attach_letter_format="none"))
    db.commit()
    tasks.add_task(_generate, camp.id)
    return campaign_out(camp, db)


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    return [campaign_out(c, db) for c in db.query(Campaign).order_by(Campaign.created_at.desc())]


@router.get("/{cid}")
def get_campaign(cid: int, db: Session = Depends(get_db)):
    return campaign_out(get_or_404(db, Campaign, cid), db, items=True)


class ItemPatch(BaseModel):
    recipient: str | None = None
    subject: str | None = None
    body: str | None = None
    include: bool | None = None


@router.patch("/{cid}/items/{item_id}")
def patch_item(cid: int, item_id: int, body: ItemPatch, db: Session = Depends(get_db)):
    camp = get_or_404(db, Campaign, cid)
    a = get_or_404(db, Application, item_id)
    if a.campaign_id != camp.id or a.status in ("envoyee", "echec"):
        raise HTTPException(422, "Cet email n'est plus modifiable.")
    data = body.model_dump(exclude_unset=True)
    include = data.pop("include", None)
    for k, v in data.items():
        setattr(a, k, v)
    if include is False:
        a.status, a.error = "ignoree", "Retiré du lot par l'utilisateur."
    elif include is True:
        company = db.get(Company, a.company_id) if a.company_id else None
        reason = o.eligibility(db, company, a.recipient)
        if reason:
            raise HTTPException(422, reason)
        a.status, a.error = ("approuvee" if camp.status == "sending" else "brouillon"), ""
    db.commit()
    return item_out(a, db)


@router.post("/{cid}/items/{item_id}/regenerate")
def regenerate_item(cid: int, item_id: int, db: Session = Depends(get_db)):
    camp = get_or_404(db, Campaign, cid)
    a = get_or_404(db, Application, item_id)
    if a.campaign_id != camp.id or a.status in ("envoyee", "echec"):
        raise HTTPException(422, "Cet email n'est plus modifiable.")
    profile = db.query(Profile).filter_by(key=camp.profile_key).one()
    out = o.generate_cold_email(profile, db.get(Company, a.company_id) if a.company_id else None,
                                db.get(Opportunity, a.opportunity_id) if a.opportunity_id else None, camp.language, camp.instructions)
    a.subject, a.body = out["subject"], out["body"] + "\n\n" + o.signature(profile, camp.language)
    db.commit()
    return item_out(a, db)


@router.post("/{cid}/approve")
def approve(cid: int, db: Session = Depends(get_db)):
    """Validation explicite du lot par l'utilisateur : seuls les emails relus et inclus partent, un par un, étalés."""
    camp = get_or_404(db, Campaign, cid)
    if camp.status != "review":
        raise HTTPException(422, "Le lot doit être en relecture pour être validé.")
    if not get_settings().mail_configured:
        raise HTTPException(422, "Renseigner MAIL_USER et MAIL_PASSWORD (Zoho SMTP) avant de valider un envoi.")
    items = db.query(Application).filter_by(campaign_id=camp.id, status="brouillon").all()
    bad = [a.id for a in items if not a.subject.strip() or not a.body.strip() or "[À COMPLÉTER]" in a.body]
    if bad:
        raise HTTPException(422, f"{len(bad)} email(s) incomplet(s) : compléter ou retirer avant validation.")
    if not items:
        raise HTTPException(422, "Aucun email à envoyer dans ce lot.")
    for a in items:
        a.status = "approuvee"
    camp.status, camp.approved_at, camp.next_send_at, camp.paused_reason = "sending", now(), now(), ""
    db.commit()
    limit, phase = o.daily_limit(db)
    return {**campaign_out(camp, db), "message": f"{len(items)} email(s) validé(s). Rythme : {limit}/jour ({phase}), "
                                                 f"un toutes les {get_settings().campaign_min_interval_s // 60}-{get_settings().campaign_max_interval_s // 60} min en heures ouvrées."}


@router.post("/{cid}/pause")
def pause(cid: int, db: Session = Depends(get_db)):
    camp = get_or_404(db, Campaign, cid)
    if camp.status == "sending":
        camp.status, camp.paused_reason = "paused", "Mis en pause manuellement."
        db.commit()
    return campaign_out(camp, db)


@router.post("/{cid}/resume")
def resume(cid: int, db: Session = Depends(get_db)):
    camp = get_or_404(db, Campaign, cid)
    if camp.status == "paused":
        camp.status, camp.paused_reason, camp.next_send_at = "sending", "", now()
        db.commit()
    return campaign_out(camp, db)


@router.delete("/{cid}")
def delete_campaign(cid: int, db: Session = Depends(get_db)):
    camp = get_or_404(db, Campaign, cid)
    if db.query(Application).filter_by(campaign_id=cid, status="envoyee").first():
        raise HTTPException(422, "Des emails de ce lot ont été envoyés : le lot est conservé pour l'historique (mettez-le en pause).")
    db.delete(camp)
    db.commit()
    return {"ok": True}


# ---------- État de la délivrabilité ----------

@outreach_router.get("/status")
def outreach_status(db: Session = Depends(get_db)):
    s = get_settings()
    limit, phase = o.daily_limit(db)
    sent = db.query(Application).filter(Application.campaign_id.isnot(None), Application.status == "envoyee")
    total = sent.count()
    bounced = sent.filter(Application.delivery == "bounced").count()
    replied = sent.filter(Application.delivery == "replied").count()
    return {"mail_configured": s.mail_configured, "sender": f"{s.sender_name} <{s.sender_email}>", "smtp_host": s.smtp_host,
            "imap_host": s.imap_host, "daily_limit": limit, "phase": phase, "sent_today": o.sent_today(db),
            "in_window": o.in_send_window(), "hours": s.campaign_hours, "interval": [s.campaign_min_interval_s, s.campaign_max_interval_s],
            "recontact_days": s.recontact_days, "total_sent": total, "bounced": bounced, "replied": replied,
            "bounce_rate": round(bounced / total * 100, 1) if total else 0, "reply_rate": round(replied / total * 100, 1) if total else 0,
            "suppressions": db.query(Suppression).count(), "dns": o.dns_report(s.sender_email.split("@")[1])}


@outreach_router.post("/test-connection")
def test_connection():
    return o.smtp_check()


@outreach_router.post("/scan-inbox")
def scan_inbox_now(db: Session = Depends(get_db)):
    try:
        return o.scan_inbox(db)
    except Exception as e:
        raise HTTPException(502, f"IMAP : {type(e).__name__}: {e}")


@outreach_router.get("/suppressions")
def list_suppressions(db: Session = Depends(get_db)):
    return [{"id": x.id, "email": x.email, "reason": x.reason, "note": x.note, "created_at": iso(x.created_at)}
            for x in db.query(Suppression).order_by(Suppression.created_at.desc())]


class SuppressIn(BaseModel):
    email: str
    reason: str = "manual"
    note: str = ""


@outreach_router.post("/suppressions")
def add_suppression(body: SuppressIn, db: Session = Depends(get_db)):
    o.suppress(db, body.email, body.reason, body.note)
    db.commit()
    return {"ok": True}


@outreach_router.delete("/suppressions/{sid}")
def delete_suppression(sid: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Suppression, sid))
    db.commit()
    return {"ok": True}


# ---------- Désinscription publique (lien dans chaque email + one-click RFC 8058) ----------

def _unsubscribe(db: Session, token: str) -> str:
    addr = o.email_from_token(token)
    if not addr:
        raise HTTPException(404, "Lien invalide.")
    o.suppress(db, addr, "unsubscribe")
    for a in db.query(Application).filter(Application.recipient.ilike(addr), Application.status == "approuvee"):
        a.status, a.error = "ignoree", "Désinscrit."
    for a in db.query(Application).filter(Application.recipient.ilike(addr), Application.status == "envoyee"):
        a.delivery = "unsubscribed"
    db.commit()
    return addr


@public_router.post("/unsubscribe/{token}")
def unsubscribe_post(token: str, db: Session = Depends(get_db)):
    return {"ok": True, "email": _unsubscribe(db, token)}


@public_router.get("/unsubscribe/{token}")
def unsubscribe_get(token: str):
    return RedirectResponse(f"{get_settings().public_url.rstrip('/')}/u/{token}")


@public_router.get("/unsubscribe-info/{token}")
def unsubscribe_info(token: str):
    addr = o.email_from_token(token)
    if not addr:
        raise HTTPException(404, "Lien invalide.")
    return {"email": addr}


__all__ = ["router", "outreach_router", "public_router", "HTMLResponse", "log"]
